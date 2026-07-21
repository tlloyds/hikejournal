package com.hikejournal.app.data

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

class HikeJournalRepository(context: Context) {
    private val appContext = context.applicationContext
    private val api = HikeJournalApi(appContext)
    private val fieldQueue = FieldOperationQueue(appContext)
    private val cacheDirectory = File(context.filesDir, "journal-cache").apply { mkdirs() }

    val syncStatus = fieldQueue.status

    val serverUrl: String get() = api.serverUrl
    val pairingKey: String get() = api.pairingKey

    fun updateServerUrl(value: String) {
        api.serverUrl = value
    }

    fun updateConnection(serverUrl: String, pairingKey: String) {
        api.serverUrl = serverUrl
        api.pairingKey = pairingKey
        SyncScheduler.schedule(appContext)
    }

    suspend fun loadHikes(): LoadResult<List<Hike>> {
        val result = loadWithCache(
            cacheFile = File(cacheDirectory, "hikes.json"),
            fetch = api::getHikesJson,
            parse = ::parseHikes,
        )
        return result.copy(value = fieldQueue.overlayHikes(result.value))
    }

    suspend fun loadHike(hikeId: String): LoadResult<Hike> {
        val cacheFile = File(cacheDirectory, "hike-$hikeId.json")
        return try {
            val json = api.getHikeJson(hikeId)
            withContext(Dispatchers.IO) { cacheFile.writeText(json) }
            val overlay = fieldQueue.overlayHike(parseHike(json), hikeId)
                ?: throw IllegalStateException("Hike not found.")
            LoadResult(overlay, fromCache = false)
        } catch (networkError: Exception) {
            val cached = withContext(Dispatchers.IO) { cacheFile.takeIf { it.exists() }?.readText() }
            val overlay = fieldQueue.overlayHike(cached?.let(::parseHike), hikeId)
            if (overlay == null) throw networkError
            LoadResult(overlay, fromCache = true)
        }
    }

    suspend fun loadSpecies(): LoadResult<List<SpeciesRecord>> = loadWithCache(
        cacheFile = File(cacheDirectory, "species.json"),
        fetch = api::getSpeciesJson,
        parse = ::parseSpeciesList,
    )

    suspend fun loadSpeciesDetail(key: String): LoadResult<SpeciesRecord> = loadWithCache(
        cacheFile = File(cacheDirectory, "species-${key.hashCode()}.json"),
        fetch = { api.getSpeciesDetailJson(key) },
        parse = ::parseSpecies,
    )

    suspend fun loadSightings(): LoadResult<List<Sighting>> = loadWithCache(
        cacheFile = File(cacheDirectory, "sightings.json"),
        fetch = api::getSightingsJson,
        parse = ::parseSightings,
    )

    suspend fun loadReviewQueue(): LoadResult<List<ReviewItem>> {
        val result = loadWithCache(
            cacheFile = File(cacheDirectory, "species-review.json"),
            fetch = api::getReviewQueueJson,
            parse = ::parseReviewQueue,
        )
        val pending = fieldQueue.pendingReviewPhotoIds()
        return result.copy(value = result.value.filterNot { it.id in pending })
    }

    suspend fun requestReviewRecommendation(photoId: String): ReviewItem {
        val item = parseReviewItem(api.requestReviewRecommendation(photoId))
        withContext(Dispatchers.IO) {
            File(cacheDirectory, "species-review.json").delete()
        }
        return item
    }

    suspend fun loadPublishQueue(): LoadResult<PublishQueue> = loadWithCache(
        cacheFile = File(cacheDirectory, "species-publish.json"),
        fetch = api::getPublishQueueJson,
        parse = ::parsePublishQueue,
    )

    suspend fun publishObservation(item: PublishItem, options: PublishOptions): PublishItem {
        val published = parsePublishItem(api.publishObservation(item.id, options))
        withContext(Dispatchers.IO) {
            File(cacheDirectory, "species-publish.json").delete()
            File(cacheDirectory, "species.json").delete()
            File(cacheDirectory, "sightings.json").delete()
        }
        return published
    }

    suspend fun decideReview(
        item: ReviewItem,
        action: String,
        candidate: ReviewCandidate?,
    ) {
        fieldQueue.queueReview(item, action, candidate)
        withContext(Dispatchers.IO) {
            File(cacheDirectory, "species-review.json").delete()
            File(cacheDirectory, "species.json").delete()
            File(cacheDirectory, "sightings.json").delete()
        }
    }

    suspend fun createHike(draft: HikeDraft): Hike = fieldQueue.queueCreateHike(draft)

    suspend fun updateHike(hikeId: String, draft: HikeDraft) {
        fieldQueue.queueUpdateHike(hikeId, draft)
    }

    suspend fun setArchived(hikeId: String, archived: Boolean) {
        fieldQueue.queueArchive(hikeId, archived)
    }

    suspend fun uploadPhoto(
        hikeId: String,
        uri: Uri,
        caption: String,
        queueForReview: Boolean,
    ): Photo = fieldQueue.queuePhoto(hikeId, uri, caption, queueForReview)

    suspend fun updateCaption(photoId: String, hikeId: String?, caption: String) =
        fieldQueue.queueCaption(photoId, hikeId, caption)

    suspend fun deletePhoto(photoId: String, hikeId: String?) = fieldQueue.queueDeletePhoto(photoId, hikeId)

    suspend fun queueSpeciesReview(photoId: String, hikeId: String?) {
        fieldQueue.queueSpeciesReview(photoId, hikeId)
        withContext(Dispatchers.IO) { File(cacheDirectory, "species-review.json").delete() }
    }

    suspend fun syncNow(): Boolean = FieldSyncEngine(appContext).drain()

    suspend fun retryAttention() = fieldQueue.retryAttention()

    private suspend fun <T> loadWithCache(
        cacheFile: File,
        fetch: suspend () -> String,
        parse: (String) -> T,
    ): LoadResult<T> {
        return try {
            val json = fetch()
            withContext(Dispatchers.IO) { cacheFile.writeText(json) }
            LoadResult(parse(json), fromCache = false)
        } catch (networkError: Exception) {
            val cached = withContext(Dispatchers.IO) {
                cacheFile.takeIf { it.exists() }?.readText()
            }
            if (cached.isNullOrBlank()) throw networkError
            LoadResult(parse(cached), fromCache = true)
        }
    }
}
