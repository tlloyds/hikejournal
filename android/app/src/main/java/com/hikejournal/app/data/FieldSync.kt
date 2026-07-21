package com.hikejournal.app.data

import android.content.Context
import android.graphics.BitmapFactory
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.Uri
import androidx.exifinterface.media.ExifInterface
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.hikejournal.app.data.local.OfflineDatabase
import com.hikejournal.app.data.local.PendingOperationEntity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import java.util.concurrent.TimeUnit

object OperationKind {
    const val CreateHike = "create_hike"
    const val UpdateHike = "update_hike"
    const val ArchiveHike = "archive_hike"
    const val UploadPhoto = "upload_photo"
    const val UpdateCaption = "update_caption"
    const val DeletePhoto = "delete_photo"
    const val QueueSpeciesReview = "queue_species_review"
    const val ReviewDecision = "review_decision"
}

private const val MAX_LOCAL_PHOTO_BYTES = 30L * 1024L * 1024L

class FieldOperationQueue(private val context: Context) {
    private val dao = OfflineDatabase.get(context).operations()
    private val preferences = context.getSharedPreferences("hikejournal_sync", Context.MODE_PRIVATE)
    private val photoDirectory = File(context.filesDir, "field-photos").apply { mkdirs() }
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
        )
    }.distinctUntilChanged()

    suspend fun queueCreateHike(draft: HikeDraft): Hike {
        val hikeId = UUID.randomUUID().toString()
        enqueue(OperationKind.CreateHike, hikeId, null, draft.toQueueJson())
        return localHike(hikeId, draft)
    }

    suspend fun queueUpdateHike(hikeId: String, draft: HikeDraft) {
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

    suspend fun queuePhoto(
        hikeId: String,
        uri: Uri,
        caption: String,
        queueForReview: Boolean,
    ): Photo = withContext(Dispatchers.IO) {
        val photoId = UUID.randomUUID().toString()
        val contentType = context.contentResolver.getType(uri) ?: "image/jpeg"
        val extension = when (contentType) {
            "image/png" -> "png"
            "image/heic", "image/heif" -> "heic"
            else -> "jpg"
        }
        val destination = File(photoDirectory, "$photoId.$extension")
        var copied = 0L
        context.contentResolver.openInputStream(uri)?.use { input ->
            destination.outputStream().use { output ->
                val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    copied += count
                    if (copied > MAX_LOCAL_PHOTO_BYTES) {
                        throw IOException("Photos must be 30 MB or smaller.")
                    }
                    output.write(buffer, 0, count)
                }
            }
        } ?: throw IOException("The selected photo could not be copied into field storage.")
        val metadata = readPhotoMetadata(destination)
        val payload = JSONObject()
            .put("caption", caption.trim())
            .put("queue_for_review", queueForReview)
            .put("taken_at", metadata.takenAt ?: JSONObject.NULL)
            .put("lat", metadata.latitude ?: JSONObject.NULL)
            .put("lng", metadata.longitude ?: JSONObject.NULL)
            .put("width", metadata.width ?: JSONObject.NULL)
            .put("height", metadata.height ?: JSONObject.NULL)
        enqueue(
            kind = OperationKind.UploadPhoto,
            entityId = photoId,
            parentId = hikeId,
            payload = payload,
            localFilePath = destination.absolutePath,
            contentType = contentType,
            fileName = destination.name,
        )
        Photo(
            id = photoId,
            hikeId = hikeId,
            url = Uri.fromFile(destination).toString(),
            caption = caption.trim(),
            takenAt = metadata.takenAt,
            createdAt = Date().toInstant().toString(),
            latitude = metadata.latitude,
            longitude = metadata.longitude,
            width = metadata.width,
            height = metadata.height,
            processingStatus = if (queueForReview) "in_review" else "ready",
            syncState = "queued",
            species = emptyList(),
        )
    }

    suspend fun queueCaption(photoId: String, hikeId: String?, caption: String) {
        val pendingUpload = dao.find(OperationKind.UploadPhoto, photoId)
        if (pendingUpload != null) {
            val payload = JSONObject(pendingUpload.payloadJson).put("caption", caption.trim())
            dao.upsert(pendingUpload.copy(payloadJson = payload.toString(), updatedAt = System.currentTimeMillis()))
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
        if (pendingUpload != null) {
            pendingUpload.localFilePath?.let { File(it).delete() }
            dao.delete(pendingUpload.id)
            return
        }
        coalesce(OperationKind.UpdateCaption, photoId)
        coalesce(OperationKind.QueueSpeciesReview, photoId)
        enqueue(OperationKind.DeletePhoto, photoId, hikeId, JSONObject())
    }

    suspend fun queueSpeciesReview(photoId: String, hikeId: String?) {
        val pendingUpload = dao.find(OperationKind.UploadPhoto, photoId)
        if (pendingUpload != null) {
            val payload = JSONObject(pendingUpload.payloadJson).put("queue_for_review", true)
            dao.upsert(pendingUpload.copy(payloadJson = payload.toString(), updatedAt = System.currentTimeMillis()))
            SyncScheduler.schedule(context)
            return
        }
        coalesce(OperationKind.QueueSpeciesReview, photoId)
        enqueue(OperationKind.QueueSpeciesReview, photoId, hikeId, JSONObject())
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
                    .put("confidence", it.confidence ?: JSONObject.NULL),
            )
        }
        enqueue(OperationKind.ReviewDecision, item.id, item.hikeId, payload)
    }

    suspend fun retryAttention() {
        dao.retryAttention(System.currentTimeMillis())
        SyncScheduler.schedule(context)
    }

    suspend fun overlayHikes(serverHikes: List<Hike>): List<Hike> {
        val operations = dao.listAll()
        val hikes = serverHikes.associateBy { it.id }.toMutableMap()
        operations.filter { it.kind == OperationKind.CreateHike }.forEach { operation ->
            hikes.putIfAbsent(operation.entityId, localHike(operation.entityId, draft(operation)))
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
            }
        }
        return hikes.values.sortedWith(
            compareBy<Hike> { it.isArchived }.thenByDescending { it.hikeDate },
        )
    }

    suspend fun overlayHike(serverHike: Hike?, hikeId: String): Hike? {
        val operations = dao.listAll()
        var hike = serverHike ?: operations.firstOrNull {
            it.kind == OperationKind.CreateHike && it.entityId == hikeId
        }?.let { localHike(hikeId, draft(it)) }
        if (hike == null) return null
        operations.forEach { operation ->
            when {
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
                operation.kind == OperationKind.UploadPhoto && operation.parentId == hikeId -> {
                    val photo = operation.toLocalPhoto()
                    hike = hike?.copy(
                        photos = hike!!.photos.filterNot { it.id == photo.id } + photo,
                        coverUrl = hike!!.coverUrl.ifBlank { photo.url },
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
                    hike = hike?.copy(
                        photos = hike!!.photos.map { photo ->
                            if (photo.id == operation.entityId) {
                                photo.copy(processingStatus = "in_review", syncState = operation.state)
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

    private suspend fun coalesce(kind: String, entityId: String) {
        dao.deleteQueued(kind, entityId)
    }

    private suspend fun enqueue(
        kind: String,
        entityId: String,
        parentId: String?,
        payload: JSONObject,
        localFilePath: String? = null,
        contentType: String? = null,
        fileName: String? = null,
    ) {
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
        processingStatus = if (payload.optBoolean("queue_for_review")) "in_review" else "ready",
        syncState = state,
        species = emptyList(),
    )
}

private fun HikeDraft.toQueueJson(): JSONObject = JSONObject()
    .put("title", title)
    .put("hike_date", hikeDate)
    .put("distance_miles", distanceMiles ?: JSONObject.NULL)
    .put("location_name", locationName)
    .put("notes", notes)

class FieldSyncEngine(private val context: Context) {
    private val dao = OfflineDatabase.get(context).operations()
    private val api = HikeJournalApi(context)
    private val preferences = context.getSharedPreferences("hikejournal_sync", Context.MODE_PRIVATE)

    suspend fun drain(): Boolean = syncMutex.withLock {
        var shouldRetry = false
        for (operation in dao.listAll().filter { it.state != "needs_attention" }) {
            dao.updateState(
                operation.id,
                "syncing",
                operation.attemptCount,
                System.currentTimeMillis(),
                null,
            )
            try {
                execute(operation)
                operation.localFilePath?.takeIf { operation.kind == OperationKind.UploadPhoto }?.let { File(it).delete() }
                dao.delete(operation.id)
            } catch (error: Exception) {
                val attempts = operation.attemptCount + 1
                val permanent = error is ApiException && error.statusCode in 400..499 && error.statusCode !in setOf(408, 429)
                val needsAttention = permanent || attempts >= 5
                dao.updateState(
                    operation.id,
                    if (needsAttention) "needs_attention" else "queued",
                    attempts,
                    System.currentTimeMillis(),
                    error.message ?: "Sync failed.",
                )
                if (!needsAttention) {
                    shouldRetry = true
                    break
                }
            }
        }
        if (!shouldRetry && dao.listAll().none { it.state == "queued" || it.state == "syncing" }) {
            preferences.edit().putLong("last_synced_at", System.currentTimeMillis()).apply()
        }
        shouldRetry
    }

    private suspend fun execute(operation: PendingOperationEntity) {
        val payload = JSONObject(operation.payloadJson)
        when (operation.kind) {
            OperationKind.CreateHike -> api.createHike(payload.toHikeDraft(), operation.entityId)
            OperationKind.UpdateHike -> api.updateHike(operation.entityId, payload.toHikeDraft())
            OperationKind.ArchiveHike -> api.setArchived(operation.entityId, payload.optBoolean("is_archived"))
            OperationKind.UploadPhoto -> api.uploadPhotoFile(
                hikeId = requireNotNull(operation.parentId),
                photoId = operation.entityId,
                file = File(requireNotNull(operation.localFilePath)),
                contentType = operation.contentType ?: "image/jpeg",
                fileName = operation.fileName ?: "hike-photo.jpg",
                caption = payload.optString("caption"),
                queueForReview = payload.optBoolean("queue_for_review"),
            )
            OperationKind.UpdateCaption -> api.updateCaption(operation.entityId, payload.optString("caption"))
            OperationKind.DeletePhoto -> api.deletePhoto(operation.entityId)
            OperationKind.QueueSpeciesReview -> api.queueSpeciesReview(operation.entityId)
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
                            confidence = it.optDouble("confidence").takeUnless { value -> value.isNaN() || it.isNull("confidence") },
                        )
                    },
                )
            }
            else -> throw IOException("Unknown offline operation: ${operation.kind}")
        }
    }

    companion object {
        private val syncMutex = Mutex()
    }
}

private fun JSONObject.toHikeDraft() = HikeDraft(
    title = optString("title"),
    hikeDate = optString("hike_date"),
    distanceMiles = optDouble("distance_miles").takeUnless { it.isNaN() || isNull("distance_miles") },
    locationName = optString("location_name"),
    notes = optString("notes"),
)

class FieldSyncWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result = if (FieldSyncEngine(applicationContext).drain()) Result.retry() else Result.success()
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
