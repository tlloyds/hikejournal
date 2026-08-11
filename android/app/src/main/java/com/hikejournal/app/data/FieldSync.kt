package com.hikejournal.app.data

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.MediaMetadataRetriever
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import android.provider.OpenableColumns
import androidx.core.content.ContextCompat
import androidx.core.app.NotificationCompat
import androidx.exifinterface.media.ExifInterface
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.room.withTransaction
import com.hikejournal.app.data.local.OfflineDatabase
import com.hikejournal.app.data.local.FieldMarkEntity
import com.hikejournal.app.data.local.PendingOperationEntity
import com.hikejournal.app.MainActivity
import com.hikejournal.app.R
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.StandardCopyOption
import java.text.SimpleDateFormat
import java.time.Instant
import java.util.Date
import java.util.Locale
import java.util.UUID
import java.util.concurrent.TimeUnit
import kotlin.math.roundToInt

object OperationKind {
    const val CreateHike = "create_hike"
    const val UpdateHike = "update_hike"
    const val ArchiveHike = "archive_hike"
    const val DeleteHike = "delete_hike"
    const val UploadPhoto = "upload_photo"
    const val UploadRoute = "upload_route"
    const val SetHikeCover = "set_hike_cover"
    const val UpdateCaption = "update_caption"
    const val DeletePhoto = "delete_photo"
    const val QueueSpeciesReview = "queue_species_review"
    const val AssignKnownSpecies = "assign_known_species"
    const val ReviewDecision = "review_decision"
    const val UpdateSpeciesQuest = "update_species_quest"
    const val CreateFieldMark = "create_field_mark"
    const val UpdateNaturalHistory = "update_natural_history"
}

private const val MAX_LOCAL_MEDIA_BYTES = 30L * 1024L * 1024L
private const val QUEUED_PHOTO_MAX_DIMENSION = 1_600
private const val QUEUED_PHOTO_JPEG_QUALITY = 86
private const val MAX_PARALLEL_PHOTO_UPLOADS = 2
private const val LONG_RUNNING_PHOTO_UPLOAD_THRESHOLD = 10
private val fieldSyncMutex = Mutex()
internal val journalCacheMutex = Mutex()

data class HikeDeletionStatus(
    val pending: Boolean,
    val needsAttention: Boolean,
    val cleanupFailures: Int,
    val lastError: String? = null,
)

data class RecordedRouteUpload(
    val file: File,
    val startedAt: String,
    val durationSeconds: Long,
    val distanceMiles: Double,
    val pointCount: Int,
    val routeSegments: List<List<RoutePoint>>,
)

data class FieldSyncProgress(
    val totalPhotoCount: Int,
    val completedPhotoCount: Int,
    val remainingPhotoCount: Int,
)

internal fun PendingOperationEntity.targetHikeId(): String? = parentId ?: entityId.takeIf {
    kind in setOf(
        OperationKind.CreateHike,
        OperationKind.UpdateHike,
        OperationKind.ArchiveHike,
        OperationKind.DeleteHike,
        OperationKind.SetHikeCover,
    )
}

private data class SyncSelectionContext(
    val deletingHikeIds: Set<String>,
    val pendingCreateHikeIds: Set<String>,
    val pendingPhotoIds: Set<String>,
    val selectedCoverPhotoIds: Set<String>,
)

private fun syncSelectionContext(operations: List<PendingOperationEntity>) = SyncSelectionContext(
    deletingHikeIds = operations
        .filter { it.kind == OperationKind.DeleteHike }
        .mapTo(mutableSetOf()) { it.entityId },
    pendingCreateHikeIds = operations
        .filter { it.kind == OperationKind.CreateHike }
        .mapTo(mutableSetOf()) { it.entityId },
    pendingPhotoIds = operations
        .filter { it.kind == OperationKind.UploadPhoto }
        .mapTo(mutableSetOf()) { it.entityId },
    selectedCoverPhotoIds = operations
        .asSequence()
        .filter { it.kind == OperationKind.SetHikeCover && it.state in setOf("queued", "syncing") }
        .mapNotNull { operation ->
            runCatching {
                JSONObject(operation.payloadJson).let { payload ->
                    payload.optString("photo_id").takeUnless { payload.isNull("photo_id") }
                }
            }.getOrNull()
        }
        .toSet(),
)

private fun PendingOperationEntity.isEligibleForSync(context: SyncSelectionContext): Boolean {
    val targetHikeId = targetHikeId()
    val waitingForRecordedHike = kind == OperationKind.CreateFieldMark &&
        runCatching { JSONObject(payloadJson).optBoolean("wait_for_hike_create") }
            .getOrDefault(false)
    val waitingForCoverPhoto = kind == OperationKind.SetHikeCover &&
        runCatching {
            JSONObject(payloadJson).let { payload ->
                payload.optString("photo_id")
                    .takeUnless { payload.isNull("photo_id") }
                    ?.let(context.pendingPhotoIds::contains)
                    ?: false
            }
        }.getOrDefault(false)
    return state in setOf("queued", "syncing") &&
        !(waitingForRecordedHike && targetHikeId !in context.pendingCreateHikeIds) &&
        !waitingForCoverPhoto &&
        (kind == OperationKind.DeleteHike || targetHikeId !in context.deletingHikeIds) &&
        (kind in setOf(OperationKind.CreateHike, OperationKind.DeleteHike) ||
            targetHikeId !in context.pendingCreateHikeIds)
}

internal fun selectNextSyncOperation(
    operations: List<PendingOperationEntity>,
    prioritizedPhotoId: String? = null,
): PendingOperationEntity? {
    val context = syncSelectionContext(operations)
    return operations.firstOrNull {
        it.kind == OperationKind.UploadPhoto &&
            it.entityId == prioritizedPhotoId &&
            it.isEligibleForSync(context)
    } ?: operations.firstOrNull {
        // A cover chosen during a large import should not wait behind every other upload.
        // Upload its own photo first, then apply the cover as soon as that photo exists remotely.
        it.kind == OperationKind.UploadPhoto &&
            it.entityId in context.selectedCoverPhotoIds &&
            it.isEligibleForSync(context)
    } ?: operations.firstOrNull {
        it.kind == OperationKind.SetHikeCover && it.isEligibleForSync(context)
    } ?: operations.firstOrNull { it.isEligibleForSync(context) }
}

internal fun selectNextSyncBatch(
    operations: List<PendingOperationEntity>,
    prioritizedPhotoId: String? = null,
    maxParallelPhotoUploads: Int = MAX_PARALLEL_PHOTO_UPLOADS,
): List<PendingOperationEntity> {
    val first = selectNextSyncOperation(operations, prioritizedPhotoId) ?: return emptyList()
    if (first.kind != OperationKind.UploadPhoto || maxParallelPhotoUploads <= 1) return listOf(first)
    val context = syncSelectionContext(operations)
    if (first.entityId in context.selectedCoverPhotoIds) return listOf(first)
    return buildList {
        add(first)
        operations.asSequence()
            .filter { operation ->
                operation.id != first.id &&
                    operation.kind == OperationKind.UploadPhoto &&
                    operation.entityId !in context.selectedCoverPhotoIds &&
                    operation.isEligibleForSync(context)
            }
            .take(maxParallelPhotoUploads - 1)
            .forEach(::add)
    }
}

internal fun pendingReviewUploadOperations(
    operations: List<PendingOperationEntity>,
): List<PendingOperationEntity> = operations.filter { operation ->
    operation.kind == OperationKind.UploadPhoto &&
        operation.state != "completed" &&
        runCatching {
            initialProcessingStatus(
                JSONObject(operation.payloadJson).optBoolean("queue_for_review"),
                operation.contentType ?: "image/jpeg",
            ) == "in_review"
        }.getOrDefault(false)
}

internal enum class HikeDeletionMode {
    DELETE_REMOTE_NOW,
    QUEUE_LOCAL_DRAFT_DELETION,
    REQUIRE_CONNECTION,
}

internal fun selectHikeDeletionMode(
    operations: List<PendingOperationEntity>,
    hikeId: String,
    remoteDeletionAllowed: Boolean,
): HikeDeletionMode {
    val hasPendingCreate = operations.any { operation ->
        operation.kind == OperationKind.CreateHike && operation.entityId == hikeId
    }
    if (hasPendingCreate) return HikeDeletionMode.QUEUE_LOCAL_DRAFT_DELETION
    if (remoteDeletionAllowed) return HikeDeletionMode.DELETE_REMOTE_NOW
    val hasDeletionIntent = operations.any { operation ->
        operation.kind == OperationKind.DeleteHike && operation.entityId == hikeId
    }
    return if (hasDeletionIntent) {
        HikeDeletionMode.QUEUE_LOCAL_DRAFT_DELETION
    } else {
        HikeDeletionMode.REQUIRE_CONNECTION
    }
}

private suspend fun invalidateHikeDeletionCaches(context: Context, hikeId: String): List<String> =
    journalCacheMutex.withLock {
        withContext(Dispatchers.IO) {
            val cacheDirectory = File(context.filesDir, "journal-cache")
            val failures = mutableListOf<String>()
            val hikesCache = File(cacheDirectory, "hikes.json")
            if (hikesCache.exists()) {
                runCatching {
                    val cached = JSONArray(hikesCache.readText())
                    val filtered = JSONArray()
                    for (index in 0 until cached.length()) {
                        cached.optJSONObject(index)
                            ?.takeUnless { it.optString("id") == hikeId }
                            ?.let(filtered::put)
                    }
                    hikesCache.writeText(filtered.toString())
                }.onFailure {
                    if (!hikesCache.delete()) failures += hikesCache.absolutePath
                }
            }
            cacheDirectory.listFiles().orEmpty()
                .filter { file ->
                    file.name == "hike-$hikeId.json" ||
                        file.name == "species.json" ||
                        file.name.startsWith("species-") ||
                        file.name == "sightings.json" ||
                        file.name.startsWith("nearby-") ||
                        file.name.startsWith("quest-sightings-")
                }
                .forEach { file ->
                    if (!file.deleteRecursively() && file.exists()) failures += file.absolutePath
                }
            failures
        }
    }

private suspend fun invalidateRouteCaches(context: Context) = journalCacheMutex.withLock {
    withContext(Dispatchers.IO) {
        val cacheDirectory = File(context.filesDir, "journal-cache")
        File(cacheDirectory, "map-routes.json").delete()
    }
}

class FieldOperationQueue(private val context: Context) {
    private val database = OfflineDatabase.get(context)
    private val dao = database.operations()
    private val fieldMarks = database.fieldMarks()
    private val preferences = context.getSharedPreferences("hikejournal_sync", Context.MODE_PRIVATE)
    private val photoDirectory = File(context.filesDir, "field-photos").apply { mkdirs() }
    private val routeDirectory = File(context.filesDir, "field-routes").apply { mkdirs() }
    private val networkMonitor = NetworkMonitor(context)

    val status: Flow<SyncStatus> = combine(
        dao.observeAll(),
        networkMonitor.connected,
    ) { operations, connected ->
        SyncStatus(
            pendingCount = operations.count { it.state == "queued" },
            syncingCount = operations.count { it.state == "syncing" },
            needsAttentionCount = operations.count { it.state == "needs_attention" },
            connected = connected,
            lastSyncedAt = preferences.getLong("last_synced_at", 0L).takeIf { it > 0 },
            attentionItems = operations
                .filter { it.state == "needs_attention" }
                .map { operation ->
                    SyncAttention(
                        kind = operation.kind,
                        detail = operation.parentId ?: operation.entityId,
                        error = operation.lastError ?: "Sync failed without a server message.",
                    )
                },
            pendingCreateHikeIds = operations
                .filter { it.kind == OperationKind.CreateHike }
                .mapTo(mutableSetOf()) { it.entityId },
            coverSyncHikeIds = operations
                .filter { it.kind == OperationKind.SetHikeCover }
                .mapTo(mutableSetOf()) { it.entityId },
            pendingPhotoCount = operations.count {
                it.kind == OperationKind.UploadPhoto && it.state == "queued"
            },
            syncingPhotoCount = operations.count {
                it.kind == OperationKind.UploadPhoto && it.state == "syncing"
            },
        )
    }.distinctUntilChanged()

    suspend fun queueFieldMark(mark: FieldMark): FieldMark {
        val markedAtEpochMs = runCatching { Instant.parse(mark.markedAt).toEpochMilli() }
            .getOrDefault(System.currentTimeMillis())
        val now = System.currentTimeMillis()
        val payload = JSONObject()
            .put("recording_session_id", mark.recordingSessionId ?: JSONObject.NULL)
            .put("marked_at", mark.markedAt)
            .put("lat", mark.latitude)
            .put("lng", mark.longitude)
            .put("accuracy_meters", mark.accuracyMeters ?: JSONObject.NULL)
            .put("mark_type", mark.markType)
            .put("note", mark.note)
            .put("wait_for_hike_create", true)
        fieldSyncMutex.withLock {
            database.withTransaction {
                fieldMarks.upsert(
                    FieldMarkEntity(
                        id = mark.id,
                        hikeId = mark.hikeId,
                        recordingSessionId = mark.recordingSessionId,
                        markedAtEpochMs = markedAtEpochMs,
                        latitude = mark.latitude,
                        longitude = mark.longitude,
                        accuracyMeters = mark.accuracyMeters,
                        markType = mark.markType,
                        note = mark.note,
                        syncState = "queued",
                        createdAtEpochMs = now,
                        updatedAtEpochMs = now,
                    )
                )
                dao.upsert(
                    PendingOperationEntity(
                        id = UUID.randomUUID().toString(),
                        kind = OperationKind.CreateFieldMark,
                        entityId = mark.id,
                        parentId = mark.hikeId,
                        payloadJson = payload.toString(),
                        localFilePath = null,
                        contentType = null,
                        fileName = null,
                        state = "queued",
                        attemptCount = 0,
                        createdAt = now,
                        updatedAt = now,
                        lastError = null,
                    )
                )
            }
        }
        SyncScheduler.schedule(context)
        return mark.copy(syncState = "queued")
    }

    suspend fun localFieldMarks(hikeId: String): List<FieldMark> =
        fieldMarks.listForHike(hikeId).map(FieldMarkEntity::toFieldMark)

    suspend fun discardRecordingFieldMarks(hikeId: String) = fieldSyncMutex.withLock {
        database.withTransaction {
            dao.deleteChildrenByKind(OperationKind.CreateFieldMark, hikeId)
            fieldMarks.deleteForHike(hikeId)
        }
    }

    suspend fun queueNaturalHistory(
        observationId: String,
        hikeId: String?,
        confidence: String,
        phenophases: List<String>,
    ) {
        coalesce(OperationKind.UpdateNaturalHistory, observationId)
        enqueue(
            OperationKind.UpdateNaturalHistory,
            observationId,
            hikeId,
            JSONObject()
                .put("confidence", confidence)
                .put("provenance", "user")
                .put("phenophases", org.json.JSONArray(phenophases)),
        )
    }

    suspend fun queueCreateHike(
        draft: HikeDraft,
        hikeId: String = UUID.randomUUID().toString(),
    ): Hike {
        val existing = dao.find(OperationKind.CreateHike, hikeId)
        if (existing == null) {
            enqueue(OperationKind.CreateHike, hikeId, null, draft.toQueueJson())
        } else if (existing.state != "syncing") {
            dao.upsert(
                existing.copy(
                    payloadJson = draft.toQueueJson().toString(),
                    state = "queued",
                    attemptCount = 0,
                    updatedAt = System.currentTimeMillis(),
                    lastError = null,
                ),
            )
            SyncScheduler.schedule(context)
        }
        return localHike(hikeId, draft)
    }

    suspend fun queueUpdateHike(hikeId: String, draft: HikeDraft) {
        val pendingCreate = dao.find(OperationKind.CreateHike, hikeId)
        if (pendingCreate != null && pendingCreate.state != "syncing") {
            dao.upsert(
                pendingCreate.copy(
                    payloadJson = draft.toQueueJson().toString(),
                    state = "queued",
                    attemptCount = 0,
                    updatedAt = System.currentTimeMillis(),
                    lastError = null,
                ),
            )
            SyncScheduler.schedule(context)
            return
        }
        coalesce(OperationKind.UpdateHike, hikeId)
        enqueue(OperationKind.UpdateHike, hikeId, null, draft.toQueueJson())
    }

    suspend fun queueArchive(hikeId: String, archived: Boolean) {
        coalesce(OperationKind.ArchiveHike, hikeId)
        enqueue(
            OperationKind.ArchiveHike,
            hikeId,
            null,
            JSONObject().put("is_archived", archived),
        )
    }

    suspend fun queueHikeCover(hikeId: String, photoId: String?, coverUrl: String) {
        val now = System.currentTimeMillis()
        val payload = JSONObject()
            .put("photo_id", photoId ?: JSONObject.NULL)
            .put("cover_url", coverUrl)
        // Do not take fieldSyncMutex here. The sync worker deliberately holds it while a
        // batch drains, which used to leave cover changes waiting behind hundreds of uploads.
        // Room provides the atomic replacement, and the worker re-reads this table after each
        // operation, so it can safely discover the latest cover intent while already running.
        database.withTransaction {
            if (dao.find(OperationKind.DeleteHike, hikeId) != null) {
                throw IOException("This hike is already being deleted.")
            }
            dao.deleteReplaceable(OperationKind.SetHikeCover, hikeId)
            dao.upsert(
                PendingOperationEntity(
                    id = UUID.randomUUID().toString(),
                    kind = OperationKind.SetHikeCover,
                    entityId = hikeId,
                    parentId = null,
                    payloadJson = payload.toString(),
                    localFilePath = null,
                    contentType = null,
                    fileName = null,
                    state = "queued",
                    attemptCount = 0,
                    createdAt = now,
                    updatedAt = now,
                    lastError = null,
                ),
            )
        }
        SyncScheduler.schedule(context)
    }

    suspend fun queuePhoto(
        hikeId: String,
        uri: Uri,
        caption: String,
        queueForReview: Boolean,
        scheduleSync: Boolean = true,
    ): Photo = withContext(Dispatchers.IO) {
        val photoId = UUID.randomUUID().toString()
        val selectedContentType = selectedMediaContentType(context, uri)
        val extension = when (selectedContentType.lowercase(Locale.US)) {
            "image/png" -> "png"
            "image/heic", "image/heif" -> "heic"
            "video/mp4" -> "mp4"
            "video/quicktime" -> "mov"
            "video/x-m4v" -> "m4v"
            "video/3gpp" -> "3gp"
            "video/webm" -> "webm"
            else -> "jpg"
        }
        val selectedFile = File(photoDirectory, "$photoId-source.$extension")
        copySelectedMedia(context, uri, selectedFile, requestOriginal = true)
        val pickerTakenAt = readPickerTakenAt(context, uri)
        val fileMetadata = readMediaMetadata(selectedFile, selectedContentType)
        val metadata = fileMetadata.copy(takenAt = fileMetadata.takenAt ?: pickerTakenAt)
        val queuedMedia = if (selectedContentType.startsWith("video/", ignoreCase = true)) {
            QueuedMedia(
                file = selectedFile,
                contentType = selectedContentType,
                width = metadata.width,
                height = metadata.height,
            )
        } else {
            prepareQueuedPhoto(
                source = selectedFile,
                destination = File(photoDirectory, "$photoId.jpg"),
            ) ?: QueuedMedia(
                file = selectedFile,
                contentType = selectedContentType,
                width = metadata.width,
                height = metadata.height,
            )
        }
        val payload = JSONObject()
            .put("caption", caption.trim())
            .put("queue_for_review", queueForReview)
            .put("taken_at", metadata.takenAt ?: JSONObject.NULL)
            .put("lat", metadata.latitude ?: JSONObject.NULL)
            .put("lng", metadata.longitude ?: JSONObject.NULL)
            .put("width", queuedMedia.width ?: JSONObject.NULL)
            .put("height", queuedMedia.height ?: JSONObject.NULL)
        enqueueDuringSync(
            kind = OperationKind.UploadPhoto,
            entityId = photoId,
            parentId = hikeId,
            payload = payload,
            localFilePath = queuedMedia.file.absolutePath,
            contentType = queuedMedia.contentType,
            fileName = queuedMedia.file.name,
            scheduleSync = scheduleSync,
        )
        Photo(
            id = photoId,
            hikeId = hikeId,
            url = Uri.fromFile(queuedMedia.file).toString(),
            caption = caption.trim(),
            takenAt = metadata.takenAt,
            createdAt = Date().toInstant().toString(),
            latitude = metadata.latitude,
            longitude = metadata.longitude,
            width = queuedMedia.width,
            height = queuedMedia.height,
            contentType = queuedMedia.contentType,
            processingStatus = initialProcessingStatus(queueForReview, queuedMedia.contentType),
            syncState = "queued",
            species = emptyList(),
        )
    }

    suspend fun queueRoute(hikeId: String, uri: Uri) = withContext(Dispatchers.IO) {
        val filename = selectedFileName(context, uri) ?: "route.tcx"
        if (!filename.lowercase(Locale.US).endsWith(".tcx") && !filename.lowercase(Locale.US).endsWith(".tcx.txt")) {
            throw IOException("Choose a .tcx or .tcx.txt route file.")
        }
        val destination = File(routeDirectory, "${UUID.randomUUID()}.tcx")
        copySelectedMedia(context, uri, destination, requestOriginal = true)
        if (destination.length() > MAX_LOCAL_MEDIA_BYTES) {
            destination.delete()
            throw IOException("TCX files must be 30 MB or smaller.")
        }
        enqueue(
            kind = OperationKind.UploadRoute,
            entityId = UUID.randomUUID().toString(),
            parentId = hikeId,
            payload = JSONObject(),
            localFilePath = destination.absolutePath,
            contentType = "application/vnd.garmin.tcx+xml",
            fileName = filename,
        )
    }

    suspend fun queueRecordedRoute(hikeId: String, route: RecordedRouteUpload) = withContext(Dispatchers.IO) {
        if (!route.file.exists()) throw IOException("The recorded route is no longer available on this phone.")
        if (route.file.length() > MAX_LOCAL_MEDIA_BYTES) throw IOException("Recorded routes must be 30 MB or smaller.")
        val operationEntityId = "recorded-route:$hikeId"
        val destination = File(routeDirectory, "$hikeId-recorded.tcx")
        val temporary = File(routeDirectory, "$hikeId-recorded.tcx.tmp")
        val payload = JSONObject()
            .put("source_type", "hikejournal_android_gps")
            .put("started_at", route.startedAt)
            .put("duration_seconds", route.durationSeconds)
            .put("distance_miles", route.distanceMiles)
            .put("track_point_count", route.pointCount)
            .put("route_segments", route.routeSegments.toJson())
        fieldSyncMutex.withLock {
            try {
                route.file.inputStream().use { input ->
                    temporary.outputStream().use { output -> input.copyTo(output) }
                }
                try {
                    java.nio.file.Files.move(
                        temporary.toPath(),
                        destination.toPath(),
                        StandardCopyOption.ATOMIC_MOVE,
                        StandardCopyOption.REPLACE_EXISTING,
                    )
                } catch (_: AtomicMoveNotSupportedException) {
                    java.nio.file.Files.move(
                        temporary.toPath(),
                        destination.toPath(),
                        StandardCopyOption.REPLACE_EXISTING,
                    )
                }
            } catch (error: IOException) {
                throw IOException("Could not preserve the recorded route for background sync.", error)
            } finally {
                if (temporary.exists()) temporary.delete()
            }
            val existing = dao.find(OperationKind.UploadRoute, operationEntityId)
            dao.upsert(
                PendingOperationEntity(
                    id = existing?.id ?: UUID.randomUUID().toString(),
                    kind = OperationKind.UploadRoute,
                    entityId = operationEntityId,
                    parentId = hikeId,
                    payloadJson = payload.toString(),
                    localFilePath = destination.absolutePath,
                    contentType = "application/vnd.garmin.tcx+xml",
                    fileName = "hikejournal-recording.tcx",
                    state = "queued",
                    attemptCount = 0,
                    createdAt = existing?.createdAt ?: System.currentTimeMillis(),
                    updatedAt = System.currentTimeMillis(),
                    lastError = null,
                ),
            )
        }
        SyncScheduler.schedule(context)
    }

    suspend fun inspectMediaLocations(uris: List<Uri>): MediaLocationSummary =
        withContext(Dispatchers.IO) {
            val geotaggedCount = uris.count { uri ->
                runCatching {
                    val contentType = selectedMediaContentType(context, uri)
                    readSelectedMediaLocation(context, uri, contentType) != null
                }.getOrDefault(false)
            }
            MediaLocationSummary(
                totalCount = uris.size,
                geotaggedCount = geotaggedCount,
            )
        }

    suspend fun queueCaption(photoId: String, hikeId: String?, caption: String) {
        val updatedPendingUpload = fieldSyncMutex.withLock {
            val pendingUpload = dao.find(OperationKind.UploadPhoto, photoId)
            if (pendingUpload == null || pendingUpload.state == "syncing") return@withLock false
            val targetHikeId = pendingUpload.parentId
            if (targetHikeId != null && dao.find(OperationKind.DeleteHike, targetHikeId) != null) {
                throw IOException("This hike is already being deleted.")
            }
            dao.upsert(
                pendingUpload.copy(
                    payloadJson = JSONObject(pendingUpload.payloadJson)
                        .put("caption", caption.trim())
                        .toString(),
                    state = "queued",
                    attemptCount = 0,
                    updatedAt = System.currentTimeMillis(),
                    lastError = null,
                ),
            )
            true
        }
        if (updatedPendingUpload) {
            SyncScheduler.schedule(context)
            return
        }
        coalesce(OperationKind.UpdateCaption, photoId)
        enqueue(
            OperationKind.UpdateCaption,
            photoId,
            hikeId,
            JSONObject().put("caption", caption.trim()),
        )
    }

    suspend fun queueDeletePhoto(photoId: String, hikeId: String?) {
        val pendingUpload = dao.find(OperationKind.UploadPhoto, photoId)
        if (pendingUpload != null && pendingUpload.state != "syncing") {
            pendingUpload.localFilePath?.let { path ->
                val localFile = File(path)
                if (localFile.exists() && !localFile.delete()) {
                    throw IOException("Could not remove this unsynced photo from the phone.")
                }
            }
            dao.delete(pendingUpload.id)
            coalesce(OperationKind.AssignKnownSpecies, photoId)
            return
        }
        coalesce(OperationKind.UpdateCaption, photoId)
        coalesce(OperationKind.QueueSpeciesReview, photoId)
        coalesce(OperationKind.AssignKnownSpecies, photoId)
        enqueue(OperationKind.DeletePhoto, photoId, hikeId, JSONObject())
    }

    suspend fun queueSpeciesReview(photoId: String, hikeId: String?, queued: Boolean) {
        val updatedPendingUpload = fieldSyncMutex.withLock {
            val pendingUpload = dao.find(OperationKind.UploadPhoto, photoId)
            if (pendingUpload == null || pendingUpload.state == "syncing") return@withLock false
            val targetHikeId = pendingUpload.parentId
            if (targetHikeId != null && dao.find(OperationKind.DeleteHike, targetHikeId) != null) {
                throw IOException("This hike is already being deleted.")
            }
            dao.upsert(
                pendingUpload.copy(
                    payloadJson = JSONObject(pendingUpload.payloadJson)
                        .put("queue_for_review", queued)
                        .toString(),
                    state = "queued",
                    attemptCount = 0,
                    updatedAt = System.currentTimeMillis(),
                    lastError = null,
                ),
            )
            true
        }
        if (updatedPendingUpload) {
            SyncScheduler.schedule(context)
            return
        }
        coalesce(OperationKind.QueueSpeciesReview, photoId)
        enqueue(
            OperationKind.QueueSpeciesReview,
            photoId,
            hikeId,
            JSONObject().put("queued", queued),
        )
    }

    suspend fun queueKnownSpecies(photoId: String, hikeId: String?, species: SpeciesRecord) {
        coalesce(OperationKind.AssignKnownSpecies, photoId)
        coalesce(OperationKind.QueueSpeciesReview, photoId)
        enqueue(
            OperationKind.AssignKnownSpecies,
            photoId,
            hikeId,
            JSONObject()
                .put("taxon_id", species.taxonId ?: JSONObject.NULL)
                .put("common_name", species.commonName)
                .put("scientific_name", species.scientificName),
        )
    }

    suspend fun queueReview(item: ReviewItem, action: String, candidate: ReviewCandidate?) {
        coalesce(OperationKind.ReviewDecision, item.id)
        val payload = JSONObject()
            .put("action", action)
            .put("observation_id", item.observationId ?: JSONObject.NULL)
        candidate?.let {
            payload.put(
                "candidate",
                JSONObject()
                    .put("taxon_id", it.taxonId ?: JSONObject.NULL)
                    .put("common_name", it.commonName)
                    .put("scientific_name", it.scientificName)
                    .put("confidence", normalizedReviewConfidence(it.confidence) ?: JSONObject.NULL),
            )
        }
        enqueue(OperationKind.ReviewDecision, item.id, item.hikeId, payload)
    }

    suspend fun queueQuestFocus(questId: String, focusTaxonIds: List<Long>) {
        coalesce(OperationKind.UpdateSpeciesQuest, questId)
        enqueue(
            OperationKind.UpdateSpeciesQuest,
            questId,
            null,
            JSONObject().put("focus_taxon_ids", org.json.JSONArray(focusTaxonIds.take(10))),
        )
    }

    suspend fun retryAttention() {
        dao.retryAttention(System.currentTimeMillis())
        SyncScheduler.schedule(context)
    }

    suspend fun discardAttention() = fieldSyncMutex.withLock {
        dao.listAttention().forEach { operation ->
            val discardedOperations = if (operation.kind == OperationKind.DeleteHike) {
                dao.listForHike(operation.entityId)
            } else {
                listOf(operation)
            }
            withContext(Dispatchers.IO) {
                discardedOperations.forEach { discarded ->
                    discarded.localFilePath?.let { path ->
                        val localFile = File(path)
                        if (localFile.exists() && !localFile.delete()) {
                            throw IOException("Could not remove the local file for this unsynced change.")
                        }
                    }
                }
            }
            discardedOperations
                .filterNot { discarded -> discarded.id == operation.id }
                .forEach { discarded -> dao.delete(discarded.id) }
            dao.delete(operation.id)
        }
    }

    suspend fun overlayHikes(serverHikes: List<Hike>): List<Hike> {
        val operations = dao.listAll()
        val hikes = serverHikes.associateBy { it.id }.toMutableMap()
        operations.filter { it.kind == OperationKind.CreateHike }.forEach { operation ->
            val next = draft(operation)
            val existing = hikes[operation.entityId]
            hikes[operation.entityId] = existing?.copy(
                title = next.title,
                hikeDate = next.hikeDate,
                distanceMiles = next.distanceMiles,
                locationName = next.locationName,
                notes = next.notes,
                syncState = operation.state,
            ) ?: localHike(operation.entityId, next)
        }
        operations.forEach { operation ->
            when (operation.kind) {
                OperationKind.UpdateHike -> hikes[operation.entityId]?.let {
                    val next = draft(operation)
                    hikes[operation.entityId] = it.copy(
                        title = next.title,
                        hikeDate = next.hikeDate,
                        distanceMiles = next.distanceMiles,
                        locationName = next.locationName,
                        notes = next.notes,
                        syncState = operation.state,
                    )
                }
                OperationKind.ArchiveHike -> hikes[operation.entityId]?.let {
                    hikes[operation.entityId] = it.copy(
                        isArchived = JSONObject(operation.payloadJson).optBoolean("is_archived"),
                        syncState = operation.state,
                    )
                }
                OperationKind.SetHikeCover -> hikes[operation.entityId]?.let {
                    val payload = JSONObject(operation.payloadJson)
                    hikes[operation.entityId] = it.copy(
                        coverPhotoId = payload.optString("photo_id").takeUnless { payload.isNull("photo_id") },
                        coverUrl = payload.optString("cover_url", it.coverUrl),
                        syncState = operation.state,
                    )
                }
                OperationKind.UploadPhoto -> hikes[operation.parentId]?.let {
                    val cover = it.coverUrl.ifBlank {
                        operation.localFilePath?.let { path -> Uri.fromFile(File(path)).toString() }.orEmpty()
                    }
                    hikes[it.id] = it.copy(
                        coverUrl = cover,
                        photoCount = it.photoCount + 1,
                        syncState = operation.state,
                    )
                }
                OperationKind.UploadRoute -> hikes[operation.parentId]?.let {
                    val payload = JSONObject(operation.payloadJson)
                    hikes[it.id] = it.copy(
                        durationSeconds = payload.optLong("duration_seconds")
                            .takeUnless { _ -> payload.isNull("duration_seconds") },
                        routeStartedAt = payload.optString("started_at").takeIf(String::isNotBlank),
                        syncState = operation.state,
                    )
                }
                OperationKind.DeleteHike -> hikes.remove(operation.entityId)
            }
        }
        return hikes.values.sortedWith(
            compareBy<Hike> { it.isArchived }.thenByDescending { it.hikeDate },
        )
    }

    suspend fun overlayHike(serverHike: Hike?, hikeId: String): Hike? {
        val operations = dao.listAll()
        if (operations.any { it.kind == OperationKind.DeleteHike && it.entityId == hikeId }) return null
        var hike = serverHike ?: operations.firstOrNull {
            it.kind == OperationKind.CreateHike && it.entityId == hikeId
        }?.let { localHike(hikeId, draft(it)) }
        if (hike == null) return null
        operations.forEach { operation ->
            when {
                operation.kind == OperationKind.CreateHike && operation.entityId == hikeId -> {
                    val next = draft(operation)
                    hike = hike?.copy(
                        title = next.title,
                        hikeDate = next.hikeDate,
                        distanceMiles = next.distanceMiles,
                        locationName = next.locationName,
                        notes = next.notes,
                        syncState = operation.state,
                    )
                }
                operation.kind == OperationKind.UpdateHike && operation.entityId == hikeId -> {
                    val next = draft(operation)
                    hike = hike?.copy(
                        title = next.title,
                        hikeDate = next.hikeDate,
                        distanceMiles = next.distanceMiles,
                        locationName = next.locationName,
                        notes = next.notes,
                        syncState = operation.state,
                    )
                }
                operation.kind == OperationKind.ArchiveHike && operation.entityId == hikeId -> {
                    hike = hike?.copy(
                        isArchived = JSONObject(operation.payloadJson).optBoolean("is_archived"),
                        syncState = operation.state,
                    )
                }
                operation.kind == OperationKind.SetHikeCover && operation.entityId == hikeId -> {
                    val payload = JSONObject(operation.payloadJson)
                    hike = hike?.copy(
                        coverPhotoId = payload.optString("photo_id").takeUnless { payload.isNull("photo_id") },
                        coverUrl = payload.optString("cover_url", hike!!.coverUrl),
                        syncState = operation.state,
                    )
                }
                operation.kind == OperationKind.UploadPhoto && operation.parentId == hikeId -> {
                    val photo = operation.toLocalPhoto()
                    hike = hike?.copy(
                        photos = hike!!.photos.filterNot { it.id == photo.id } + photo,
                        coverUrl = hike!!.coverUrl.ifBlank { photo.url },
                        syncState = operation.state,
                    )
                }
                operation.kind == OperationKind.UploadRoute && operation.parentId == hikeId -> {
                    val payload = JSONObject(operation.payloadJson)
                    hike = hike?.copy(
                        distanceMiles = payload.optDouble("distance_miles")
                            .takeUnless { it.isNaN() || payload.isNull("distance_miles") }
                            ?: hike!!.distanceMiles,
                        durationSeconds = payload.optLong("duration_seconds")
                            .takeUnless { payload.isNull("duration_seconds") }
                            ?: hike!!.durationSeconds,
                        routeStartedAt = payload.optString("started_at").takeIf(String::isNotBlank)
                            ?: hike!!.routeStartedAt,
                        routeSegments = payload.optJSONArray("route_segments")
                            ?.toRouteSegments()
                            ?.takeIf { it.isNotEmpty() }
                            ?: hike!!.routeSegments,
                        syncState = operation.state,
                    )
                }
                operation.kind == OperationKind.UpdateCaption && operation.parentId == hikeId -> {
                    val caption = JSONObject(operation.payloadJson).optString("caption")
                    hike = hike?.copy(
                        photos = hike!!.photos.map { photo ->
                            if (photo.id == operation.entityId) photo.copy(caption = caption, syncState = operation.state) else photo
                        },
                    )
                }
                operation.kind == OperationKind.DeletePhoto && operation.parentId == hikeId -> {
                    hike = hike?.copy(photos = hike!!.photos.filterNot { it.id == operation.entityId })
                }
                operation.kind == OperationKind.QueueSpeciesReview && operation.parentId == hikeId -> {
                    val queued = JSONObject(operation.payloadJson).optBoolean("queued", true)
                    hike = hike?.copy(
                        photos = hike!!.photos.map { photo ->
                            if (photo.id == operation.entityId) {
                                photo.copy(
                                    processingStatus = if (queued) "in_review" else "ready",
                                    syncState = operation.state,
                                )
                            } else {
                                photo
                            }
                        },
                    )
                }
                operation.kind == OperationKind.AssignKnownSpecies && operation.parentId == hikeId -> {
                    val payload = JSONObject(operation.payloadJson)
                    val label = SpeciesLabel(
                        commonName = payload.optString("common_name"),
                        scientificName = payload.optString("scientific_name"),
                        status = "confirmed",
                        isPrimary = true,
                    )
                    hike = hike?.copy(
                        photos = hike!!.photos.map { photo ->
                            if (photo.id == operation.entityId) {
                                photo.copy(
                                    processingStatus = "ready",
                                    syncState = operation.state,
                                    species = listOf(label) + photo.species.filterNot { it.isPrimary },
                                )
                            } else {
                                photo
                            }
                        },
                    )
                }
            }
        }
        return hike?.copy(photoCount = hike!!.photos.size)
    }

    suspend fun pendingReviewPhotoIds(): Set<String> = dao.listAll()
        .filter { it.kind == OperationKind.ReviewDecision }
        .mapTo(mutableSetOf()) { it.entityId }

    suspend fun pendingReviewUploads(): List<Photo> = pendingReviewUploadOperations(dao.listAll())
        .map(PendingOperationEntity::toLocalPhoto)

    suspend fun pendingRoutesByHikeId(): Map<String, List<List<RoutePoint>>> = dao.listAll()
        .asSequence()
        .filter { it.kind == OperationKind.UploadRoute && it.state != "completed" }
        .mapNotNull { operation ->
            val hikeId = operation.parentId ?: return@mapNotNull null
            val segments = JSONObject(operation.payloadJson)
                .optJSONArray("route_segments")
                ?.toRouteSegments()
                .orEmpty()
            hikeId.takeIf { segments.isNotEmpty() }?.let { it to segments }
        }
        .toMap()

    suspend fun deletedHikeIds(): Set<String> = dao.listAll()
        .filter { it.kind == OperationKind.DeleteHike }
        .mapTo(mutableSetOf()) { it.entityId }

    suspend fun pendingCreditTaxonIds(): Set<Long> = dao.listAll()
        .asSequence()
        .filter { it.kind == OperationKind.ReviewDecision }
        .map { JSONObject(it.payloadJson) }
        .filter { it.optString("action") == "confirm" }
        .mapNotNull { payload ->
            payload.optJSONObject("candidate")
                ?.takeUnless { it.isNull("taxon_id") }
                ?.optLong("taxon_id")
        }
        .toSet()

    suspend fun pendingQuestFocus(): Map<String, List<Long>> = dao.listAll()
        .asSequence()
        .filter { it.kind == OperationKind.UpdateSpeciesQuest }
        .associate { operation ->
            val ids = JSONObject(operation.payloadJson).optJSONArray("focus_taxon_ids")
            operation.entityId to List(ids?.length() ?: 0) { index -> ids!!.optLong(index) }
        }

    private suspend fun coalesce(kind: String, entityId: String) {
        dao.deleteReplaceable(kind, entityId)
    }

    private suspend fun enqueue(
        kind: String,
        entityId: String,
        parentId: String?,
        payload: JSONObject,
        localFilePath: String? = null,
        contentType: String? = null,
        fileName: String? = null,
    ) = fieldSyncMutex.withLock {
        val targetHikeId = parentId ?: entityId.takeIf {
            kind in setOf(
                OperationKind.CreateHike,
                OperationKind.UpdateHike,
                OperationKind.ArchiveHike,
                OperationKind.SetHikeCover,
            )
        }
        if (targetHikeId != null && dao.find(OperationKind.DeleteHike, targetHikeId) != null) {
            withContext(Dispatchers.IO) { localFilePath?.let { File(it).delete() } }
            throw IOException("This hike is already being deleted.")
        }
        val now = System.currentTimeMillis()
        dao.upsert(
            PendingOperationEntity(
                id = UUID.randomUUID().toString(),
                kind = kind,
                entityId = entityId,
                parentId = parentId,
                payloadJson = payload.toString(),
                localFilePath = localFilePath,
                contentType = contentType,
                fileName = fileName,
                state = "queued",
                attemptCount = 0,
                createdAt = now,
                updatedAt = now,
                lastError = null,
            ),
        )
        SyncScheduler.schedule(context)
    }

    private suspend fun enqueueDuringSync(
        kind: String,
        entityId: String,
        parentId: String?,
        payload: JSONObject,
        localFilePath: String? = null,
        contentType: String? = null,
        fileName: String? = null,
        scheduleSync: Boolean = true,
    ) {
        val targetHikeId = parentId ?: entityId.takeIf {
            kind in setOf(
                OperationKind.CreateHike,
                OperationKind.UpdateHike,
                OperationKind.ArchiveHike,
                OperationKind.SetHikeCover,
            )
        }
        val now = System.currentTimeMillis()
        try {
            database.withTransaction {
                if (targetHikeId != null && dao.find(OperationKind.DeleteHike, targetHikeId) != null) {
                    throw IOException("This hike is already being deleted.")
                }
                dao.upsert(
                    PendingOperationEntity(
                        id = UUID.randomUUID().toString(),
                        kind = kind,
                        entityId = entityId,
                        parentId = parentId,
                        payloadJson = payload.toString(),
                        localFilePath = localFilePath,
                        contentType = contentType,
                        fileName = fileName,
                        state = "queued",
                        attemptCount = 0,
                        createdAt = now,
                        updatedAt = now,
                        lastError = null,
                    ),
                )
            }
        } catch (error: Exception) {
            localFilePath?.let { File(it).delete() }
            throw error
        }
        if (scheduleSync) SyncScheduler.schedule(context)
    }

    private fun draft(operation: PendingOperationEntity): HikeDraft = JSONObject(operation.payloadJson).let { payload ->
        HikeDraft(
            title = payload.optString("title"),
            hikeDate = payload.optString("hike_date"),
            distanceMiles = payload.optDouble("distance_miles").takeUnless { it.isNaN() || payload.isNull("distance_miles") },
            locationName = payload.optString("location_name"),
            notes = payload.optString("notes"),
        )
    }

    private fun localHike(id: String, draft: HikeDraft): Hike = Hike(
        id = id,
        title = draft.title,
        hikeDate = draft.hikeDate,
        distanceMiles = draft.distanceMiles,
        locationName = draft.locationName,
        notes = draft.notes,
        isArchived = false,
        coverUrl = "",
        photoCount = 0,
        speciesCount = 0,
        syncState = "queued",
        photos = emptyList(),
    )
}

private data class LocalPhotoMetadata(
    val takenAt: String?,
    val latitude: Double?,
    val longitude: Double?,
    val width: Int?,
    val height: Int?,
)

private data class QueuedMedia(
    val file: File,
    val contentType: String,
    val width: Int?,
    val height: Int?,
)

private fun prepareQueuedPhoto(source: File, destination: File): QueuedMedia? {
    val temporary = File(destination.parentFile, "${destination.name}.tmp")
    temporary.delete()
    return runCatching {
        val bounds = BitmapFactory.Options().also { options ->
            options.inJustDecodeBounds = true
            BitmapFactory.decodeFile(source.absolutePath, options)
        }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return@runCatching null
        var sampleSize = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / sampleSize > QUEUED_PHOTO_MAX_DIMENSION * 2) {
            sampleSize *= 2
        }
        val decoded = BitmapFactory.decodeFile(
            source.absolutePath,
            BitmapFactory.Options().apply {
                inSampleSize = sampleSize
                inPreferredConfig = Bitmap.Config.ARGB_8888
            },
        ) ?: return@runCatching null
        val orientation = runCatching {
            ExifInterface(source.absolutePath).getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL,
            )
        }.getOrDefault(ExifInterface.ORIENTATION_NORMAL)
        val oriented = orientBitmap(decoded, orientation)
        val targetDimensions = constrainedPhotoDimensions(oriented.width, oriented.height)
        val prepared = if (
            targetDimensions.first != oriented.width || targetDimensions.second != oriented.height
        ) {
            Bitmap.createScaledBitmap(
                oriented,
                targetDimensions.first,
                targetDimensions.second,
                true,
            )
        } else {
            oriented
        }
        try {
            temporary.outputStream().buffered().use { output ->
                if (!prepared.compress(Bitmap.CompressFormat.JPEG, QUEUED_PHOTO_JPEG_QUALITY, output)) {
                    throw IOException("The selected photo could not be prepared for upload.")
                }
            }
            if (temporary.length() <= 0L) throw IOException("The prepared photo was empty.")
            try {
                java.nio.file.Files.move(
                    temporary.toPath(),
                    destination.toPath(),
                    StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING,
                )
            } catch (_: AtomicMoveNotSupportedException) {
                java.nio.file.Files.move(
                    temporary.toPath(),
                    destination.toPath(),
                    StandardCopyOption.REPLACE_EXISTING,
                )
            }
            source.delete()
            QueuedMedia(destination, "image/jpeg", prepared.width, prepared.height)
        } finally {
            if (prepared !== oriented) prepared.recycle()
            if (oriented !== decoded) oriented.recycle()
            decoded.recycle()
        }
    }.getOrNull().also { prepared ->
        temporary.delete()
        if (prepared == null) destination.delete()
    }
}

internal fun constrainedPhotoDimensions(
    width: Int,
    height: Int,
    maxDimension: Int = QUEUED_PHOTO_MAX_DIMENSION,
): Pair<Int, Int> {
    val longestSide = maxOf(width, height)
    if (width <= 0 || height <= 0 || maxDimension <= 0 || longestSide <= maxDimension) {
        return width to height
    }
    val scale = maxDimension.toFloat() / longestSide
    return (width * scale).roundToInt().coerceAtLeast(1) to
        (height * scale).roundToInt().coerceAtLeast(1)
}

private fun orientBitmap(source: Bitmap, orientation: Int): Bitmap {
    val matrix = Matrix()
    when (orientation) {
        ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.setScale(-1f, 1f)
        ExifInterface.ORIENTATION_ROTATE_180 -> matrix.setRotate(180f)
        ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.setScale(1f, -1f)
        ExifInterface.ORIENTATION_TRANSPOSE -> {
            matrix.setRotate(90f)
            matrix.postScale(-1f, 1f)
        }
        ExifInterface.ORIENTATION_ROTATE_90 -> matrix.setRotate(90f)
        ExifInterface.ORIENTATION_TRANSVERSE -> {
            matrix.setRotate(-90f)
            matrix.postScale(-1f, 1f)
        }
        ExifInterface.ORIENTATION_ROTATE_270 -> matrix.setRotate(270f)
        else -> return source
    }
    return Bitmap.createBitmap(source, 0, 0, source.width, source.height, matrix, true)
}

private fun copySelectedMedia(
    context: Context,
    uri: Uri,
    destination: File,
    requestOriginal: Boolean,
) {
    val candidates = selectedMediaCandidates(context, uri, requestOriginal)
    var lastError: Exception? = null
    for (candidate in candidates) {
        destination.delete()
        try {
            val input = context.contentResolver.openInputStream(candidate)
                ?: throw IOException("The selected photo could not be opened.")
            input.use {
                destination.outputStream().use { output ->
                    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                    var copied = 0L
                    while (true) {
                        val count = it.read(buffer)
                        if (count < 0) break
                        copied += count
                        if (copied > MAX_LOCAL_MEDIA_BYTES) {
                            throw IOException("Photos and videos must be 30 MB or smaller.")
                        }
                        output.write(buffer, 0, count)
                    }
                }
            }
            return
        } catch (error: Exception) {
            lastError = error
        }
    }
    destination.delete()
    throw IOException(
        lastError?.message ?: "The selected photo could not be copied into field storage.",
        lastError,
    )
}

private fun selectedMediaContentType(context: Context, uri: Uri): String =
    runCatching { context.contentResolver.getType(uri) }.getOrNull()
        ?: uri.lastPathSegment?.let(::mediaContentType)
        ?: "image/jpeg"

private fun mediaContentType(fileName: String): String? =
    when (fileName.substringAfterLast('.', "").lowercase()) {
        "jpg", "jpeg" -> "image/jpeg"
        "png" -> "image/png"
        "heic" -> "image/heic"
        "heif" -> "image/heif"
        "webp" -> "image/webp"
        "gif" -> "image/gif"
        "mp4" -> "video/mp4"
        "mov" -> "video/quicktime"
        "m4v" -> "video/x-m4v"
        "3gp" -> "video/3gpp"
        "webm" -> "video/webm"
        else -> null
    }

private fun selectedMediaCandidates(
    context: Context,
    uri: Uri,
    requestOriginal: Boolean,
): List<Uri> {
    val canRequestOriginal = requestOriginal &&
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q &&
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_MEDIA_LOCATION) ==
        PackageManager.PERMISSION_GRANTED
    return buildList {
        if (canRequestOriginal) add(MediaStore.setRequireOriginal(uri))
        add(uri)
    }.distinct()
}

private fun readPickerTakenAt(context: Context, uri: Uri): String? = runCatching {
    context.contentResolver.query(uri, arrayOf("datetaken"), null, null, null)?.use { cursor ->
        if (!cursor.moveToFirst()) return@use null
        val column = cursor.getColumnIndex("datetaken")
        if (column < 0 || cursor.isNull(column)) return@use null
        cursor.getLong(column)
            .takeIf { it > 0L }
            ?.let(Instant::ofEpochMilli)
            ?.toString()
    }
}.getOrNull()

private fun readSelectedMediaLocation(
    context: Context,
    uri: Uri,
    contentType: String,
): Pair<Double, Double>? {
    for (candidate in selectedMediaCandidates(context, uri, requestOriginal = true)) {
        val coordinates = if (contentType.startsWith("video/")) {
            runCatching {
                context.contentResolver.openFileDescriptor(candidate, "r")?.use { descriptor ->
                    val retriever = MediaMetadataRetriever()
                    try {
                        retriever.setDataSource(descriptor.fileDescriptor)
                        parseVideoLocation(
                            retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_LOCATION),
                        )
                    } finally {
                        retriever.release()
                    }
                }
            }.getOrNull()
        } else {
            runCatching {
                context.contentResolver.openInputStream(candidate)?.use { input ->
                    ExifInterface(input).latLong?.let { coordinates ->
                        coordinates[0] to coordinates[1]
                    }
                }
            }.getOrNull()
        }
        if (coordinates != null) return coordinates
    }
    return null
}

private fun readMediaMetadata(file: File, contentType: String): LocalPhotoMetadata =
    if (contentType.startsWith("video/")) readVideoMetadata(file) else readPhotoMetadata(file)

private fun readPhotoMetadata(file: File): LocalPhotoMetadata {
    val exif = runCatching { ExifInterface(file.absolutePath) }.getOrNull()
    val coordinates = exif?.latLong
    val rawDate = exif?.getAttribute(ExifInterface.TAG_DATETIME_ORIGINAL)
        ?: exif?.getAttribute(ExifInterface.TAG_DATETIME)
    val takenAt = rawDate?.let { value ->
        runCatching {
            val parser = SimpleDateFormat("yyyy:MM:dd HH:mm:ss", Locale.US)
            parser.parse(value)?.toInstant()?.toString()
        }.getOrNull()
    }
    val bounds = BitmapFactory.Options().also { it.inJustDecodeBounds = true }
    BitmapFactory.decodeFile(file.absolutePath, bounds)
    return LocalPhotoMetadata(
        takenAt = takenAt,
        latitude = coordinates?.getOrNull(0),
        longitude = coordinates?.getOrNull(1),
        width = bounds.outWidth.takeIf { it > 0 },
        height = bounds.outHeight.takeIf { it > 0 },
    )
}

private fun readVideoMetadata(file: File): LocalPhotoMetadata = runCatching {
    val retriever = MediaMetadataRetriever()
    try {
        retriever.setDataSource(file.absolutePath)
        val coordinates = parseVideoLocation(
            retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_LOCATION),
        )
        LocalPhotoMetadata(
            takenAt = null,
            latitude = coordinates?.first,
            longitude = coordinates?.second,
            width = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toIntOrNull(),
            height = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toIntOrNull(),
        )
    } finally {
        retriever.release()
    }
}.getOrElse {
    LocalPhotoMetadata(null, null, null, null, null)
}

private val VIDEO_LOCATION_PATTERN =
    Regex("""^([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?).*$""")

internal fun parseVideoLocation(value: String?): Pair<Double, Double>? {
    val match = value?.let(VIDEO_LOCATION_PATTERN::matchEntire) ?: return null
    val latitude = match.groupValues[1].toDoubleOrNull() ?: return null
    val longitude = match.groupValues[2].toDoubleOrNull() ?: return null
    if (latitude !in -90.0..90.0 || longitude !in -180.0..180.0) return null
    return latitude to longitude
}

private fun PendingOperationEntity.toLocalPhoto(): Photo {
    val payload = JSONObject(payloadJson)
    return Photo(
        id = entityId,
        hikeId = parentId,
        url = localFilePath?.let { Uri.fromFile(File(it)).toString() }.orEmpty(),
        caption = payload.optString("caption"),
        takenAt = payload.optString("taken_at").takeIf { it.isNotBlank() },
        createdAt = Date(createdAt).toInstant().toString(),
        latitude = payload.optDouble("lat").takeUnless { it.isNaN() || payload.isNull("lat") },
        longitude = payload.optDouble("lng").takeUnless { it.isNaN() || payload.isNull("lng") },
        width = payload.optInt("width").takeUnless { payload.isNull("width") },
        height = payload.optInt("height").takeUnless { payload.isNull("height") },
        contentType = contentType ?: "image/jpeg",
        processingStatus = initialProcessingStatus(
            payload.optBoolean("queue_for_review"),
            contentType ?: "image/jpeg",
        ),
        syncState = state,
        species = emptyList(),
    )
}

internal fun initialProcessingStatus(queueForReview: Boolean, contentType: String): String =
    if (queueForReview && !contentType.startsWith("video/", ignoreCase = true)) "in_review" else "ready"

private fun HikeDraft.toQueueJson(): JSONObject = JSONObject()
    .put("title", title)
    .put("hike_date", hikeDate)
    .put("distance_miles", distanceMiles ?: JSONObject.NULL)
    .put("location_name", locationName)
    .put("notes", notes)
    .put("location_id", locationId ?: JSONObject.NULL)

private fun List<List<RoutePoint>>.toJson(): JSONArray {
    val nonEmpty = filter { it.isNotEmpty() }
    if (nonEmpty.isEmpty()) return JSONArray()
    val perSegmentLimit = (1_500 / nonEmpty.size).coerceAtLeast(2)
    return JSONArray().apply {
        nonEmpty.forEach { segment ->
            val step = kotlin.math.ceil(segment.size.toDouble() / perSegmentLimit).toInt().coerceAtLeast(1)
            val sampled = segment.filterIndexed { index, _ -> index % step == 0 }.toMutableList()
            if (sampled.lastOrNull() != segment.last()) sampled += segment.last()
            put(JSONArray().apply {
                sampled.forEach { point ->
                    put(JSONObject().put("lat", point.latitude).put("lng", point.longitude))
                }
            })
        }
    }
}

private fun JSONArray.toRouteSegments(): List<List<RoutePoint>> = List(length()) { segmentIndex ->
    val segment = optJSONArray(segmentIndex) ?: JSONArray()
    List(segment.length()) { pointIndex ->
        val point = segment.optJSONObject(pointIndex) ?: JSONObject()
        RoutePoint(point.optDouble("lat"), point.optDouble("lng"))
    }
}.filter { it.size >= 2 }

class FieldSyncEngine(private val context: Context) {
    private val database = OfflineDatabase.get(context)
    private val dao = database.operations()
    private val fieldMarks = database.fieldMarks()
    private val api = HikeJournalApi(context)
    private val preferences = context.getSharedPreferences("hikejournal_sync", Context.MODE_PRIVATE)

    private suspend fun discardHikeWork(hikeId: String, keepOperationId: String): List<String> {
        val operations = dao.listForHike(hikeId).filterNot { it.id == keepOperationId }
        val cleanupFailures = withContext(Dispatchers.IO) {
            operations.mapNotNull { operation ->
                operation.localFilePath?.let { path ->
                    val file = File(path)
                    file.absolutePath.takeIf { file.exists() && !file.delete() }
                }
            }
        }.toSet()
        operations
            .filterNot { it.localFilePath in cleanupFailures }
            .forEach { operation -> dao.delete(operation.id) }
        fieldMarks.deleteForHike(hikeId)
        return cleanupFailures.toList()
    }

    private suspend fun releaseRecordedHikeChildren(hikeId: String) {
        dao.listForHike(hikeId)
            .filter { it.kind == OperationKind.CreateFieldMark }
            .forEach { operation ->
                val payload = JSONObject(operation.payloadJson).put("wait_for_hike_create", false)
                dao.upsert(
                    operation.copy(
                        payloadJson = payload.toString(),
                        updatedAt = System.currentTimeMillis(),
                    )
                )
            }
    }

    suspend fun pendingPhotoCount(): Int = dao.listAll().count { operation ->
        operation.kind == OperationKind.UploadPhoto && operation.state in setOf("queued", "syncing")
    }

    suspend fun drain(
        prioritizedPhotoId: String? = null,
        onProgress: suspend (FieldSyncProgress) -> Unit = {},
    ): Boolean = fieldSyncMutex.withLock {
        var shouldRetry = false
        var completedPhotoCount = 0
        var totalPhotoCount = pendingPhotoCount()

        suspend fun reportProgress() {
            val remainingPhotoCount = pendingPhotoCount()
            totalPhotoCount = maxOf(totalPhotoCount, completedPhotoCount + remainingPhotoCount)
            onProgress(
                FieldSyncProgress(
                    totalPhotoCount = totalPhotoCount,
                    completedPhotoCount = completedPhotoCount,
                    remainingPhotoCount = remainingPhotoCount,
                )
            )
        }

        reportProgress()
        while (true) {
            val operations = dao.listAll()
            val batch = selectNextSyncBatch(operations, prioritizedPhotoId)
            if (batch.isEmpty()) break
            batch.forEach { operation ->
                dao.updateState(
                    operation.id,
                    "syncing",
                    operation.attemptCount,
                    System.currentTimeMillis(),
                    null,
                )
            }
            val results = coroutineScope {
                batch.map { operation ->
                    async {
                        operation to try {
                            execute(operation)
                            null
                        } catch (cancelled: CancellationException) {
                            throw cancelled
                        } catch (error: Exception) {
                            error
                        }
                    }
                }.awaitAll()
            }
            var batchNeedsRetry = false
            results.forEach { (operation, error) ->
                if (error == null) {
                    if (operation.kind == OperationKind.CreateHike) {
                        releaseRecordedHikeChildren(operation.entityId)
                    }
                    if (operation.kind == OperationKind.CreateFieldMark) {
                        fieldMarks.updateSyncState(operation.entityId, "synced", System.currentTimeMillis())
                    }
                    if (operation.kind == OperationKind.UploadRoute) {
                        invalidateRouteCaches(context)
                    }
                    operation.localFilePath?.takeIf {
                        operation.kind == OperationKind.UploadPhoto || operation.kind == OperationKind.UploadRoute
                    }?.let { File(it).delete() }
                    if (operation.kind == OperationKind.DeleteHike) {
                        dao.updateState(
                            operation.id,
                            "completed",
                            operation.attemptCount,
                            System.currentTimeMillis(),
                            null,
                        )
                    } else {
                        dao.delete(operation.id)
                    }
                    if (operation.kind == OperationKind.UploadPhoto) completedPhotoCount += 1
                } else {
                    val attempts = operation.attemptCount + 1
                    val permanent = error is ApiException &&
                        error.statusCode in 400..499 && error.statusCode !in setOf(408, 429)
                    val needsAttention = permanent || attempts >= 5
                    dao.updateState(
                        operation.id,
                        if (needsAttention) "needs_attention" else "queued",
                        attempts,
                        System.currentTimeMillis(),
                        error.message ?: "Sync failed.",
                    )
                    if (operation.kind == OperationKind.CreateFieldMark) {
                        fieldMarks.updateSyncState(
                            operation.entityId,
                            if (needsAttention) "needs_attention" else "queued",
                            System.currentTimeMillis(),
                        )
                    }
                    if (!needsAttention) batchNeedsRetry = true
                }
            }
            reportProgress()
            if (batchNeedsRetry) {
                shouldRetry = true
                break
            }
        }
        if (!shouldRetry && dao.listAll().none { it.state == "queued" || it.state == "syncing" }) {
            preferences.edit().putLong("last_synced_at", System.currentTimeMillis()).apply()
        }
        shouldRetry
    }

    /** Persist the deletion intent before touching the network so a crash or lost
     * connection cannot let queued uploads recreate the hike later. */
    suspend fun deleteHike(
        hikeId: String,
        remoteDeletionAllowed: Boolean,
    ): HikeDeletionStatus = fieldSyncMutex.withLock {
        val existingDeletion = dao.find(OperationKind.DeleteHike, hikeId)
        val operations = dao.listForHike(hikeId)
        val deletionMode = selectHikeDeletionMode(
            operations = operations,
            hikeId = hikeId,
            remoteDeletionAllowed = remoteDeletionAllowed,
        )
        if (deletionMode == HikeDeletionMode.REQUIRE_CONNECTION) {
            throw IOException("Connect HikeJournal before deleting an outing and all of its stored files.")
        }
        val now = System.currentTimeMillis()
        val deletion = existingDeletion?.copy(
            state = "queued",
            attemptCount = 0,
            updatedAt = now,
            lastError = null,
        ) ?: PendingOperationEntity(
            id = UUID.randomUUID().toString(),
            kind = OperationKind.DeleteHike,
            entityId = hikeId,
            parentId = null,
            payloadJson = JSONObject().toString(),
            localFilePath = null,
            contentType = null,
            fileName = null,
            state = "queued",
            attemptCount = 0,
            createdAt = operations.minOfOrNull { it.createdAt }?.minus(1) ?: now,
            updatedAt = now,
            lastError = null,
        )
        dao.upsert(deletion)
        SyncScheduler.schedule(context)
        if (deletionMode == HikeDeletionMode.QUEUE_LOCAL_DRAFT_DELETION) {
            val localCleanupFailures = discardHikeWork(hikeId, deletion.id)
            val cacheFailures = invalidateHikeDeletionCaches(context, hikeId)
            val cleanupFailureCount = localCleanupFailures.size + cacheFailures.size
            val detail = cleanupFailureCount.takeIf { it > 0 }?.let { failureCount ->
                "Android still needs to remove $failureCount local file" +
                    if (failureCount == 1) "." else "s."
            }
            dao.updateState(
                deletion.id,
                "queued",
                deletion.attemptCount,
                System.currentTimeMillis(),
                detail,
            )
            return@withLock HikeDeletionStatus(
                pending = true,
                needsAttention = false,
                cleanupFailures = cleanupFailureCount,
                lastError = detail,
            )
        }
        try {
            api.deleteHike(hikeId)
        } catch (error: Exception) {
            val permanent = error is ApiException &&
                error.statusCode in 400..499 && error.statusCode !in setOf(408, 429)
            dao.updateState(
                deletion.id,
                if (permanent) "needs_attention" else "queued",
                1,
                System.currentTimeMillis(),
                error.message ?: "Deletion has not synced yet.",
            )
            return@withLock HikeDeletionStatus(
                pending = true,
                needsAttention = permanent,
                cleanupFailures = 0,
                lastError = error.message,
            )
        }

        val localCleanupFailures = discardHikeWork(hikeId, deletion.id)
        val cacheFailures = invalidateHikeDeletionCaches(context, hikeId)
        val cleanupFailureCount = localCleanupFailures.size + cacheFailures.size
        if (cleanupFailureCount == 0) {
            dao.updateState(
                deletion.id,
                "completed",
                deletion.attemptCount,
                System.currentTimeMillis(),
                null,
            )
            HikeDeletionStatus(
                pending = false,
                needsAttention = false,
                cleanupFailures = 0,
            )
        } else {
            val detail = "Android still needs to remove $cleanupFailureCount local file" +
                if (cleanupFailureCount == 1) "." else "s."
            dao.updateState(
                deletion.id,
                "queued",
                1,
                System.currentTimeMillis(),
                detail,
            )
            SyncScheduler.schedule(context)
            HikeDeletionStatus(
                pending = true,
                needsAttention = false,
                cleanupFailures = cleanupFailureCount,
                lastError = detail,
            )
        }
    }

    private suspend fun execute(operation: PendingOperationEntity) {
        val payload = JSONObject(operation.payloadJson)
        when (operation.kind) {
            OperationKind.CreateHike -> api.createHike(payload.toHikeDraft(), operation.entityId)
            OperationKind.UpdateHike -> api.updateHike(operation.entityId, payload.toHikeDraft())
            OperationKind.ArchiveHike -> api.setArchived(operation.entityId, payload.optBoolean("is_archived"))
            OperationKind.DeleteHike -> {
                api.deleteHike(operation.entityId)
                val localFailures = discardHikeWork(operation.entityId, operation.id)
                val cacheFailures = invalidateHikeDeletionCaches(context, operation.entityId)
                val failureCount = localFailures.size + cacheFailures.size
                if (failureCount > 0) {
                    throw IOException(
                        "The hike is deleted, but Android still needs to remove $failureCount local file" +
                            if (failureCount == 1) "." else "s.",
                    )
                }
            }
            OperationKind.SetHikeCover -> {
                val response = JSONObject(
                    api.setHikeCover(
                        operation.entityId,
                        payload.optString("photo_id").takeUnless { payload.isNull("photo_id") },
                    ),
                )
                cacheHikeCover(
                    context = context,
                    hikeId = operation.entityId,
                    photoId = response.optString("cover_photo_id")
                        .takeUnless { response.isNull("cover_photo_id") || it.isBlank() },
                    coverUrl = response.optString("cover_url"),
                )
            }
            OperationKind.UploadPhoto -> api.uploadPhotoFile(
                hikeId = requireNotNull(operation.parentId),
                photoId = operation.entityId,
                file = File(requireNotNull(operation.localFilePath)),
                contentType = operation.contentType ?: "image/jpeg",
                fileName = operation.fileName ?: "hike-photo.jpg",
                caption = payload.optString("caption"),
                queueForReview = payload.optBoolean("queue_for_review"),
                takenAt = payload.optString("taken_at").takeIf { it.isNotBlank() },
                latitude = payload.optDouble("lat").takeUnless { it.isNaN() || payload.isNull("lat") },
                longitude = payload.optDouble("lng").takeUnless { it.isNaN() || payload.isNull("lng") },
            )
            OperationKind.UploadRoute -> api.uploadRouteFile(
                hikeId = requireNotNull(operation.parentId),
                file = File(requireNotNull(operation.localFilePath)),
                fileName = operation.fileName ?: "route.tcx",
                sourceType = payload.optString("source_type").takeIf(String::isNotBlank),
            )
            OperationKind.UpdateCaption -> api.updateCaption(operation.entityId, payload.optString("caption"))
            OperationKind.DeletePhoto -> api.deletePhoto(operation.entityId)
            OperationKind.QueueSpeciesReview -> api.setSpeciesReview(
                operation.entityId,
                payload.optBoolean("queued", true),
            )
            OperationKind.AssignKnownSpecies -> api.assignKnownSpecies(
                operation.entityId,
                payload.optLong("taxon_id").takeUnless { payload.isNull("taxon_id") },
                payload.optString("common_name"),
                payload.optString("scientific_name"),
            )
            OperationKind.ReviewDecision -> {
                val candidateJson = payload.optJSONObject("candidate")
                api.decideReview(
                    photoId = operation.entityId,
                    observationId = payload.optString("observation_id").takeIf { it.isNotBlank() },
                    action = payload.optString("action"),
                    candidate = candidateJson?.let {
                        ReviewCandidate(
                            taxonId = it.optLong("taxon_id").takeUnless { _ -> it.isNull("taxon_id") },
                            commonName = it.optString("common_name"),
                            scientificName = it.optString("scientific_name"),
                            confidence = normalizedReviewConfidence(
                                it.optDouble("confidence").takeUnless { value -> value.isNaN() || it.isNull("confidence") },
                            ),
                        )
                    },
                )
            }
            OperationKind.UpdateSpeciesQuest -> {
                val ids = payload.optJSONArray("focus_taxon_ids")
                api.updateSpeciesQuest(
                    questId = operation.entityId,
                    focusTaxonIds = List(ids?.length() ?: 0) { index -> ids!!.optLong(index) },
                )
            }
            OperationKind.CreateFieldMark -> api.createFieldMark(
                FieldMark(
                    id = operation.entityId,
                    hikeId = requireNotNull(operation.parentId),
                    recordingSessionId = payload.optString("recording_session_id")
                        .takeUnless { payload.isNull("recording_session_id") || it.isBlank() },
                    markedAt = payload.optString("marked_at"),
                    latitude = payload.getDouble("lat"),
                    longitude = payload.getDouble("lng"),
                    accuracyMeters = payload.optDouble("accuracy_meters")
                        .takeUnless { it.isNaN() || payload.isNull("accuracy_meters") },
                    markType = payload.optString("mark_type", "note"),
                    note = payload.optString("note"),
                    syncState = operation.state,
                )
            )
            OperationKind.UpdateNaturalHistory -> api.updateObservationNaturalHistory(
                observationId = operation.entityId,
                confidence = payload.optString("confidence", "tentative"),
                provenance = payload.optString("provenance", "user"),
                phenophases = payload.optJSONArray("phenophases")?.let { values ->
                    List(values.length()) { index -> values.optString(index) }
                }.orEmpty(),
            )
            else -> throw IOException("Unknown offline operation: ${operation.kind}")
        }
    }

}

private fun FieldMarkEntity.toFieldMark() = FieldMark(
    id = id,
    hikeId = hikeId,
    recordingSessionId = recordingSessionId,
    markedAt = Instant.ofEpochMilli(markedAtEpochMs).toString(),
    latitude = latitude,
    longitude = longitude,
    accuracyMeters = accuracyMeters,
    markType = markType,
    note = note,
    syncState = syncState,
)

private fun JSONObject.toHikeDraft() = HikeDraft(
    title = optString("title"),
    hikeDate = optString("hike_date"),
    distanceMiles = optDouble("distance_miles").takeUnless { it.isNaN() || isNull("distance_miles") },
    locationName = optString("location_name"),
    notes = optString("notes"),
    locationId = optString("location_id").takeUnless { isNull("location_id") || it.isBlank() },
)

private fun selectedFileName(context: Context, uri: Uri): String? =
    context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        if (cursor.moveToFirst()) cursor.getString(0) else null
    }

class FieldSyncWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val engine = FieldSyncEngine(applicationContext)
        val initialPhotoCount = engine.pendingPhotoCount()
        var foregroundTransfer = initialPhotoCount >= LONG_RUNNING_PHOTO_UPLOAD_THRESHOLD
        if (foregroundTransfer) {
            setForeground(createForegroundInfo(FieldSyncProgress(initialPhotoCount, 0, initialPhotoCount)))
        }
        val shouldRetry = engine.drain { progress ->
            if (progress.totalPhotoCount >= LONG_RUNNING_PHOTO_UPLOAD_THRESHOLD) {
                foregroundTransfer = true
            }
            if (foregroundTransfer) setForeground(createForegroundInfo(progress))
        }
        return if (shouldRetry) Result.retry() else Result.success()
    }

    private fun createForegroundInfo(progress: FieldSyncProgress): ForegroundInfo {
        val manager = applicationContext.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                SYNC_NOTIFICATION_CHANNEL_ID,
                "Photo uploads",
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = "Progress for HikeJournal photo transfers"
            }
        )
        val openApp = PendingIntent.getActivity(
            applicationContext,
            0,
            Intent(applicationContext, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val progressMax = progress.totalPhotoCount.coerceAtLeast(1)
        val uploaded = progress.completedPhotoCount.coerceAtMost(progressMax)
        val notification = NotificationCompat.Builder(applicationContext, SYNC_NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_tracking_notification)
            .setContentTitle("Uploading HikeJournal photos")
            .setContentText(
                if (progress.remainingPhotoCount == 0) {
                    "Finishing photo sync…"
                } else {
                    "$uploaded of ${progress.totalPhotoCount} uploaded · ${progress.remainingPhotoCount} remaining"
                }
            )
            .setContentIntent(openApp)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .setProgress(progressMax, uploaded, false)
            .build()
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ForegroundInfo(
                SYNC_NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
            )
        } else {
            ForegroundInfo(SYNC_NOTIFICATION_ID, notification)
        }
    }

    private companion object {
        const val SYNC_NOTIFICATION_CHANNEL_ID = "hikejournal-photo-sync"
        const val SYNC_NOTIFICATION_ID = 4202
    }
}

object SyncScheduler {
    private const val WorkName = "hikejournal-field-sync"

    fun schedule(context: Context) {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val request = OneTimeWorkRequestBuilder<FieldSyncWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(WorkName, ExistingWorkPolicy.APPEND_OR_REPLACE, request)
    }
}

private class NetworkMonitor(context: Context) {
    private val manager = context.getSystemService(ConnectivityManager::class.java)

    val connected: Flow<Boolean> = callbackFlow {
        fun current(): Boolean = manager.activeNetwork
            ?.let(manager::getNetworkCapabilities)
            ?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true
        trySend(current())
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) { trySend(current()) }
            override fun onLost(network: Network) { trySend(current()) }
            override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) {
                trySend(current())
            }
        }
        manager.registerNetworkCallback(NetworkRequest.Builder().build(), callback)
        awaitClose { manager.unregisterNetworkCallback(callback) }
    }.distinctUntilChanged()
}
