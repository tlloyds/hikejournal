package com.hikejournal.app.tracking

import android.Manifest
import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.location.Location
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.os.Looper
import android.speech.tts.TextToSpeech
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.hikejournal.app.MainActivity
import com.hikejournal.app.R
import java.util.Locale
import kotlin.math.floor
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.distinctUntilChangedBy
import kotlinx.coroutines.launch

class HikeTrackingService : Service() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val repository by lazy { TrackingRepository.get(applicationContext) }
    private val notificationManager by lazy {
        ContextCompat.getSystemService(this, NotificationManager::class.java)
            ?: error("NotificationManager is unavailable")
    }
    private val fusedLocationClient by lazy {
        LocationServices.getFusedLocationProviderClient(this)
    }
    private var requestingLocations = false
    private var stateCollection: Job? = null
    private var recoveryComplete = false
    private var startupRejected = false
    private lateinit var progressAnnouncer: TrackingProgressAnnouncer
    private val locationBatches = Channel<List<Location>>(Channel.UNLIMITED)

    private val locationCallback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            if (result.locations.isEmpty()) return
            locationBatches.trySend(
                result.locations.sortedWith(
                    compareBy<Location> { it.elapsedRealtimeNanos }.thenBy { it.time },
                ),
            )
        }
    }

    override fun onCreate() {
        super.onCreate()
        progressAnnouncer = TrackingProgressAnnouncer(applicationContext)
        createNotificationChannel()
        if (!TrackingPrerequisites.check(this).allSatisfied) {
            rejectStartup()
            return
        }
        try {
            startForegroundImmediately()
        } catch (_: RuntimeException) {
            // Android 14 rejects a location-typed foreground service if its while-in-use
            // permission was revoked. Pause durably instead of crashing in onCreate.
            rejectStartup()
            return
        }
        serviceScope.launch(Dispatchers.IO) {
            for (batch in locationBatches) {
                batch.forEach { repository.acceptLocation(it) }
            }
        }
        stateCollection = serviceScope.launch {
            repository.snapshots
                .distinctUntilChangedBy { snapshot ->
                    snapshot?.let { Triple(it.status, it.distanceMeters, it.pointCount) }
                }
                .collectLatest { snapshot ->
                    if (!recoveryComplete) return@collectLatest
                    if (snapshot == null) {
                        stopServiceNow()
                        return@collectLatest
                    }
                    applySnapshot(snapshot)
                }
        }
        serviceScope.launch {
            while (true) {
                delay(CHECKPOINT_INTERVAL_MS)
                repository.checkpoint()
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (startupRejected) return START_NOT_STICKY
        serviceScope.launch {
            try {
                if (!recoveryComplete) {
                    val recovered = repository.recover()
                    recoveryComplete = true
                    when (recovered?.status) {
                        null -> {
                            stopServiceNow()
                            return@launch
                        }
                        TrackingStatus.STARTING -> repository.beginRecording()
                        else -> applySnapshot(recovered)
                    }
                }
                when (intent?.action) {
                    ACTION_PAUSE -> repository.pause()
                    ACTION_RESUME -> repository.resumeFromService()
                    else -> Unit
                }
            } catch (_: TrackingStateException) {
                // Notification actions can race a UI action; the durable state is authoritative.
            } catch (_: TrackingPrerequisiteException) {
                repository.recover()
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        stopLocationUpdates()
        locationBatches.close()
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stateCollection?.cancel()
        progressAnnouncer.close()
        serviceScope.cancel()
        super.onDestroy()
    }

    @SuppressLint("MissingPermission")
    private fun startLocationUpdates() {
        if (requestingLocations) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            serviceScope.launch { repository.pause() }
            return
        }
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, LOCATION_INTERVAL_MS)
            .setMinUpdateIntervalMillis(MIN_LOCATION_INTERVAL_MS)
            .setMinUpdateDistanceMeters(MIN_LOCATION_DISTANCE_METERS)
            .setMaxUpdateAgeMillis(0L)
            .setWaitForAccurateLocation(true)
            .build()
        try {
            fusedLocationClient.requestLocationUpdates(request, locationCallback, Looper.getMainLooper())
            requestingLocations = true
        } catch (_: SecurityException) {
            serviceScope.launch { repository.pause() }
        }
    }

    private fun stopLocationUpdates() {
        if (!requestingLocations) return
        fusedLocationClient.removeLocationUpdates(locationCallback)
        requestingLocations = false
    }

    private fun applySnapshot(snapshot: TrackingSnapshot) {
        when (snapshot.status) {
            TrackingStatus.RECORDING -> startLocationUpdates()
            else -> stopLocationUpdates()
        }
        notificationManager.notify(NOTIFICATION_ID, notification(snapshot))
        if (snapshot.status == TrackingStatus.RECORDING) progressAnnouncer.announce(snapshot)
    }

    private fun rejectStartup() {
        startupRejected = true
        serviceScope.launch {
            runCatching {
                repository.pauseAfterServiceFailure(
                    "Hike tracking paused because Android could not restart location tracking.",
                )
            }
            stopServiceNow()
        }
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            NOTIFICATION_CHANNEL_ID,
            getString(R.string.tracking_notification_channel_name),
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = getString(R.string.tracking_notification_channel_description)
            setShowBadge(false)
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
        }
        notificationManager.createNotificationChannel(channel)
    }

    private fun startForegroundImmediately() {
        val foregroundType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
        } else {
            0
        }
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            startingNotification(),
            foregroundType,
        )
    }

    private fun startingNotification(): Notification = notificationBuilder()
        .setContentTitle(getString(R.string.tracking_notification_starting))
        .setContentText(formatDistance(0.0))
        .setContentIntent(openTrackingIntent("active"))
        .build()

    private fun notification(snapshot: TrackingSnapshot): Notification {
        val builder = notificationBuilder()
            .setContentIntent(openTrackingIntent("active"))
        when (snapshot.status) {
            TrackingStatus.STARTING -> builder
                .setContentTitle(getString(R.string.tracking_notification_starting))
                .setContentText(formatDistance(snapshot.distanceMeters))
            TrackingStatus.RECORDING -> builder
                .setContentTitle(getString(R.string.tracking_notification_recording))
                .setContentText(formatDistance(snapshot.distanceMeters))
                .setWhen(System.currentTimeMillis() - snapshot.activeElapsedMs)
                .setShowWhen(true)
                .setUsesChronometer(true)
                .addAction(
                    R.drawable.ic_tracking_pause,
                    getString(R.string.tracking_action_pause),
                    serviceAction(ACTION_PAUSE, REQUEST_PAUSE),
                )
            TrackingStatus.PAUSED -> builder
                .setContentTitle(getString(R.string.tracking_notification_paused))
                .setContentText(
                    "${formatDistance(snapshot.distanceMeters)} • ${formatElapsed(snapshot.activeElapsedMs)}",
                )
                .addAction(
                    R.drawable.ic_tracking_resume,
                    getString(R.string.tracking_action_resume),
                    serviceAction(ACTION_RESUME, REQUEST_RESUME),
                )
                .addAction(
                    R.drawable.ic_tracking_end,
                    getString(R.string.tracking_action_end),
                    openTrackingIntent("end"),
                )
            TrackingStatus.FINALIZING -> builder
                .setContentTitle(getString(R.string.tracking_notification_paused))
                .setContentText(formatDistance(snapshot.distanceMeters))
            TrackingStatus.FINISHED -> builder
                .setContentTitle(getString(R.string.app_name))
                .setContentText(formatDistance(snapshot.distanceMeters))
        }
        return builder.build()
    }

    private fun notificationBuilder(): NotificationCompat.Builder =
        NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_tracking_notification)
            .setColor(ContextCompat.getColor(this, R.color.launcher_background))
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)

    private fun serviceAction(action: String, requestCode: Int): PendingIntent = PendingIntent.getService(
        this,
        requestCode,
        Intent(this, HikeTrackingService::class.java).setAction(action),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
    )

    private fun openTrackingIntent(path: String): PendingIntent = PendingIntent.getActivity(
        this,
        if (path == "end") REQUEST_END else REQUEST_OPEN,
        Intent(Intent.ACTION_VIEW, Uri.parse("hikejournal://tracking/$path"), this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
    )

    private fun stopServiceNow() {
        stopLocationUpdates()
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    companion object {
        private const val NOTIFICATION_CHANNEL_ID = "hike_tracking"
        private const val NOTIFICATION_ID = 7_041
        private const val ACTION_SYNC = "com.hikejournal.app.tracking.SYNC"
        private const val ACTION_PAUSE = "com.hikejournal.app.tracking.PAUSE"
        private const val ACTION_RESUME = "com.hikejournal.app.tracking.RESUME"
        // Frequent only while a hike is actively recording. The filter rejects poor fixes, so
        // these extra checkpoints preserve turns without accepting GPS noise.
        private const val LOCATION_INTERVAL_MS = 2_000L
        private const val MIN_LOCATION_INTERVAL_MS = 1_000L
        private const val MIN_LOCATION_DISTANCE_METERS = 1.5f
        private const val CHECKPOINT_INTERVAL_MS = 15_000L
        private const val REQUEST_OPEN = 20
        private const val REQUEST_PAUSE = 21
        private const val REQUEST_RESUME = 22
        private const val REQUEST_END = 23

        fun start(context: Context) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, HikeTrackingService::class.java).setAction(ACTION_SYNC),
            )
        }

        fun pause(context: Context) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, HikeTrackingService::class.java).setAction(ACTION_PAUSE),
            )
        }

        fun resume(context: Context) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, HikeTrackingService::class.java).setAction(ACTION_RESUME),
            )
        }

        fun stopAfterFinished(context: Context) {
            context.stopService(Intent(context, HikeTrackingService::class.java))
        }

        fun stopAfterDiscard(context: Context) = stopAfterFinished(context)
    }
}

private class TrackingProgressAnnouncer(context: Context) : TextToSpeech.OnInitListener {
    private val appContext = context.applicationContext
    private val preferences = appContext.getSharedPreferences("tracking_progress", Context.MODE_PRIVATE)
    private var textToSpeech: TextToSpeech? = TextToSpeech(appContext, this)
    private var ready = false

    override fun onInit(status: Int) {
        ready = status == TextToSpeech.SUCCESS
        if (ready) textToSpeech?.language = Locale.US
    }

    fun announce(snapshot: TrackingSnapshot) {
        val completedMiles = floor(snapshot.distanceMeters / METERS_PER_MILE).toInt()
        val storedSessionId = preferences.getString("session_id", null)
        if (storedSessionId != snapshot.sessionId) {
            preferences.edit().putString("session_id", snapshot.sessionId)
                .putInt("last_announced_mile", completedMiles).apply()
            return
        }
        val lastAnnounced = preferences.getInt("last_announced_mile", 0)
        if (completedMiles <= lastAnnounced) return
        preferences.edit().putInt("last_announced_mile", completedMiles).apply()
        if (!ready) return
        val mileLabel = if (completedMiles == 1) "mile" else "miles"
        val message = "$completedMiles $mileLabel complete. Total time: ${formatElapsed(snapshot.activeElapsedMs)}"
        textToSpeech?.speak(message, TextToSpeech.QUEUE_ADD, null, "hike-mile-$completedMiles")
    }

    fun close() {
        textToSpeech?.stop()
        textToSpeech?.shutdown()
        textToSpeech = null
    }
}

private fun formatDistance(meters: Double): String =
    String.format(Locale.US, "%.2f mi", meters.coerceAtLeast(0.0) / 1_609.344)

private fun formatElapsed(elapsedMs: Long): String {
    val seconds = elapsedMs.coerceAtLeast(0L) / 1_000L
    val hours = seconds / 3_600L
    val minutes = (seconds % 3_600L) / 60L
    val remainingSeconds = seconds % 60L
    return if (hours > 0) {
        String.format(Locale.US, "%d:%02d:%02d", hours, minutes, remainingSeconds)
    } else {
        String.format(Locale.US, "%02d:%02d", minutes, remainingSeconds)
    }
}

private const val METERS_PER_MILE = 1_609.344
