package com.hikejournal.app.data

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.ListenableWorker.Result
import com.hikejournal.app.MainActivity
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.UUID
import java.util.concurrent.TimeUnit

internal data class PublishBatchRequest(
    val requestId: String,
    val groups: List<List<String>>,
    val options: PublishOptions,
)

/**
 * Owns the durable client-side half of a grouped iNaturalist publish batch.
 *
 * WorkManager keeps the start request and status polling alive while Android is
 * backgrounded or the app process is recreated. The request ID makes a lost
 * start response safe to retry without creating a second batch job.
 */
object PublishBatchWork {
    const val WorkName = "hikejournal-species-publish-batch"

    internal const val ProgressJobId = "job_id"
    internal const val ProgressState = "state"
    internal const val ProgressTotalGroups = "total_groups"
    internal const val ProgressProcessedGroupCount = "processed_group_count"
    internal const val ProgressPostedGroupCount = "posted_group_count"
    internal const val ProgressFailedGroupCount = "failed_group_count"
    internal const val ProgressPartialGroupCount = "partial_group_count"
    internal const val ProgressTotalPhotos = "total_photos"
    internal const val ProgressProcessedPhotoCount = "processed_photo_count"
    internal const val ProgressCurrentGroup = "current_group"
    internal const val ProgressCurrentGroupPhotoCount = "current_group_photo_count"
    internal const val ProgressError = "error"
    internal const val ProgressErrors = "errors"

    private const val PreferencesName = "species-publish-batch"
    private const val RequestKey = "request"
    private const val JobIdKey = "job_id"
    private const val NotificationChannelId = "species-publish-batch"
    private const val NotificationId = 4104

    fun enqueue(context: Context, groups: List<List<String>>, options: PublishOptions): UUID {
        val requestId = UUID.randomUUID().toString()
        val requestJson = JSONObject()
            .put("request_id", requestId)
            .put(
                "groups",
                JSONArray().apply {
                    groups.forEach { observationIds -> put(JSONArray(observationIds)) }
                },
            )
            .put(
                "options",
                JSONObject()
                    .put("description", options.description)
                    .put("tags", JSONArray(options.tags))
                    .put("geoprivacy", options.geoprivacy)
                    .put("captive", options.captive),
            )
            .toString()
        context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
            .edit()
            .clear()
            .putString(RequestKey, requestJson)
            .commit()

        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val request = OneTimeWorkRequestBuilder<PublishBatchWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(
            WorkName,
            ExistingWorkPolicy.REPLACE,
            request,
        )
        return request.id
    }

    internal fun loadRequest(context: Context): PublishBatchRequest? {
        val raw = context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
            .getString(RequestKey, null)
            ?.takeIf(String::isNotBlank)
            ?: return null
        val root = runCatching { JSONObject(raw) }.getOrNull() ?: return null
        val requestId = root.optString("request_id").takeIf(String::isNotBlank) ?: return null
        val groupsArray = root.optJSONArray("groups") ?: return null
        val groups = List(groupsArray.length()) { groupIndex ->
            val group = groupsArray.optJSONArray(groupIndex) ?: JSONArray()
            List(group.length()) { observationIndex -> group.optString(observationIndex) }
                .filter(String::isNotBlank)
        }.filter(List<String>::isNotEmpty)
        if (groups.isEmpty()) return null
        val options = root.optJSONObject("options") ?: JSONObject()
        val tagsArray = options.optJSONArray("tags") ?: JSONArray()
        return PublishBatchRequest(
            requestId = requestId,
            groups = groups,
            options = PublishOptions(
                observationIds = emptyList(),
                description = options.optString("description"),
                tags = List(tagsArray.length()) { index -> tagsArray.optString(index) },
                geoprivacy = options.optString("geoprivacy", "open"),
                captive = options.optBoolean("captive"),
            ),
        )
    }

    internal fun loadJobId(context: Context): String? = context
        .getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
        .getString(JobIdKey, null)
        ?.takeIf(String::isNotBlank)

    internal fun saveJobId(context: Context, jobId: String) {
        context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
            .edit()
            .putString(JobIdKey, jobId)
            .commit()
    }

    internal fun emptyStatus(request: PublishBatchRequest, state: String = "queued") = PublishBatchStatus(
        jobId = "",
        state = state,
        totalGroups = request.groups.size,
        processedGroupCount = 0,
        postedGroupCount = 0,
        failedGroupCount = 0,
        partialGroupCount = 0,
        totalPhotos = request.groups.sumOf(List<String>::size),
        processedPhotoCount = 0,
        currentGroup = 0,
        currentGroupPhotoCount = 0,
        processedObservationIds = emptyList(),
        processedPhotoIds = emptyList(),
        errors = emptyList(),
        error = null,
    )

    internal fun statusData(status: PublishBatchStatus): Data = Data.Builder()
        .putString(ProgressJobId, status.jobId)
        .putString(ProgressState, status.state)
        .putInt(ProgressTotalGroups, status.totalGroups)
        .putInt(ProgressProcessedGroupCount, status.processedGroupCount)
        .putInt(ProgressPostedGroupCount, status.postedGroupCount)
        .putInt(ProgressFailedGroupCount, status.failedGroupCount)
        .putInt(ProgressPartialGroupCount, status.partialGroupCount)
        .putInt(ProgressTotalPhotos, status.totalPhotos)
        .putInt(ProgressProcessedPhotoCount, status.processedPhotoCount)
        .putInt(ProgressCurrentGroup, status.currentGroup)
        .putInt(ProgressCurrentGroupPhotoCount, status.currentGroupPhotoCount)
        .putString(ProgressError, status.error.orEmpty())
        .putString(ProgressErrors, status.errors.firstOrNull().orEmpty())
        .build()

    internal fun statusFromData(data: Data): PublishBatchStatus? {
        val state = data.getString(ProgressState)?.takeIf(String::isNotBlank) ?: return null
        return PublishBatchStatus(
            jobId = data.getString(ProgressJobId).orEmpty(),
            state = state,
            totalGroups = data.getInt(ProgressTotalGroups, 0),
            processedGroupCount = data.getInt(ProgressProcessedGroupCount, 0),
            postedGroupCount = data.getInt(ProgressPostedGroupCount, 0),
            failedGroupCount = data.getInt(ProgressFailedGroupCount, 0),
            partialGroupCount = data.getInt(ProgressPartialGroupCount, 0),
            totalPhotos = data.getInt(ProgressTotalPhotos, 0),
            processedPhotoCount = data.getInt(ProgressProcessedPhotoCount, 0),
            currentGroup = data.getInt(ProgressCurrentGroup, 0),
            currentGroupPhotoCount = data.getInt(ProgressCurrentGroupPhotoCount, 0),
            processedObservationIds = emptyList(),
            processedPhotoIds = emptyList(),
            errors = data.getString(ProgressErrors)?.takeIf(String::isNotBlank)?.let(::listOf).orEmpty(),
            error = data.getString(ProgressError)?.takeIf(String::isNotBlank),
        )
    }

    internal fun failureData(status: PublishBatchStatus): Data = Data.Builder()
        .putString(ProgressState, "failed")
        .putString(ProgressJobId, status.jobId)
        .putInt(ProgressTotalGroups, status.totalGroups)
        .putInt(ProgressProcessedGroupCount, status.processedGroupCount)
        .putInt(ProgressPostedGroupCount, status.postedGroupCount)
        .putInt(ProgressFailedGroupCount, status.failedGroupCount)
        .putInt(ProgressPartialGroupCount, status.partialGroupCount)
        .putInt(ProgressTotalPhotos, status.totalPhotos)
        .putInt(ProgressProcessedPhotoCount, status.processedPhotoCount)
        .putString(ProgressError, status.error.orEmpty())
        .build()

    internal fun notificationId(): Int = NotificationId

    internal fun notificationChannelId(): String = NotificationChannelId
}

class PublishBatchWorker(
    context: Context,
    parameters: WorkerParameters,
) : CoroutineWorker(context, parameters) {
    private val appContext = applicationContext

    override suspend fun doWork(): Result {
        val request = PublishBatchWork.loadRequest(appContext) ?: return Result.failure()
        var status = PublishBatchWork.emptyStatus(request)
        publish(status)

        return try {
            val storedJobId = PublishBatchWork.loadJobId(appContext)
            status = if (storedJobId == null) {
                repository().startPublishBatch(request.groups, request.options, request.requestId).also { started ->
                    PublishBatchWork.saveJobId(appContext, started.jobId)
                }
            } else {
                repository().getPublishBatchStatus(storedJobId)
            }
            publish(status)

            var statusCheckFailures = 0
            while (status.state == "queued" || status.state == "running") {
                if (isStopped) return Result.retry()
                delay(1_500)
                status = try {
                    repository().getPublishBatchStatus(status.jobId)
                } catch (error: IOException) {
                    statusCheckFailures += 1
                    if (statusCheckFailures >= 3) throw error
                    continue
                }
                statusCheckFailures = 0
                publish(status)
            }

            if (status.state == "completed") {
                Result.success(PublishBatchWork.statusData(status))
            } else {
                Result.failure(PublishBatchWork.failureData(status))
            }
        } catch (error: ApiException) {
            val message = error.message ?: "HikeJournal could not complete the iNaturalist publish batch."
            if (error.statusCode == 408 || error.statusCode == 425 || error.statusCode == 429 || error.statusCode >= 500) {
                Result.retry()
            } else {
                val failed = status.copy(state = "failed", error = message)
                publish(failed)
                Result.failure(PublishBatchWork.failureData(failed))
            }
        } catch (_: IOException) {
            Result.retry()
        } catch (error: Exception) {
            val failed = status.copy(
                state = "failed",
                error = error.message ?: "HikeJournal could not complete the iNaturalist publish batch.",
            )
            publish(failed)
            Result.failure(PublishBatchWork.failureData(failed))
        }
    }

    private fun repository(): HikeJournalRepository = HikeJournalRepository(appContext)

    private suspend fun publish(status: PublishBatchStatus) {
        setProgress(PublishBatchWork.statusData(status))
        setForeground(createForegroundInfo(status))
    }

    private fun createForegroundInfo(status: PublishBatchStatus): ForegroundInfo {
        val notificationManager = appContext.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            notificationManager.createNotificationChannel(
                NotificationChannel(
                    PublishBatchWork.notificationChannelId(),
                    "iNaturalist publishing",
                    NotificationManager.IMPORTANCE_LOW,
                ).apply {
                    description = "Progress while HikeJournal publishes grouped iNaturalist observations"
                },
            )
        }

        val total = status.totalGroups.coerceAtLeast(1)
        val current = status.processedGroupCount.coerceIn(0, total)
        val label = when (status.state) {
            "queued" -> "Preparing grouped observations…"
            "running" -> "Posting observation ${status.currentGroup} of ${status.totalGroups}…"
            "completed" -> "iNaturalist publish batch complete"
            "failed" -> "iNaturalist publish batch stopped"
            else -> "Updating iNaturalist publish batch…"
        }
        val launchIntent = PendingIntent.getActivity(
            appContext,
            4105,
            Intent(appContext, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(appContext, PublishBatchWork.notificationChannelId())
            .setSmallIcon(com.hikejournal.app.R.drawable.ic_tracking_notification)
            .setContentTitle("HikeJournal iNaturalist publishing")
            .setContentText(label)
            .setContentIntent(launchIntent)
            .setOnlyAlertOnce(true)
            .setOngoing(status.state == "queued" || status.state == "running")
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setProgress(total, current, status.state == "queued")
            .build()
        val serviceType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
        } else {
            0
        }
        return ForegroundInfo(PublishBatchWork.notificationId(), notification, serviceType)
    }
}
