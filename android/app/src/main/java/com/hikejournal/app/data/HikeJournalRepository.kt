package com.hikejournal.app.data

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
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

    suspend fun loadDiscoveryAreas(query: String = ""): LoadResult<List<DiscoveryArea>> = loadWithCache(
        cacheFile = File(cacheDirectory, "discovery-areas.json"),
        fetch = { api.getDiscoveryAreasJson(query) },
        parse = ::parseDiscoveryAreas,
    )

    suspend fun loadNearbySpecies(
        areaId: String?,
        targetDate: String,
        radiusKm: Int,
        iconicTaxon: String?,
        latitude: Double? = null,
        longitude: Double? = null,
        limit: Int = 50,
    ): LoadResult<NearbySpecies> {
        val cacheKey = listOf(
            areaId.orEmpty(),
            targetDate,
            radiusKm.toString(),
            iconicTaxon.orEmpty(),
            latitude?.let { "%.2f".format(java.util.Locale.US, it) }.orEmpty(),
            longitude?.let { "%.2f".format(java.util.Locale.US, it) }.orEmpty(),
            limit.toString(),
        ).joinToString("|").hashCode()
        val result = loadWithCache(
            cacheFile = File(cacheDirectory, "nearby-$cacheKey.json"),
            fetch = {
                api.getNearbySpeciesJson(
                    areaId = areaId,
                    targetDate = targetDate,
                    radiusKm = radiusKm,
                    iconicTaxon = iconicTaxon,
                    latitude = latitude,
                    longitude = longitude,
                    limit = limit,
                )
            },
            parse = ::parseNearbySpecies,
        )
        return result.copy(value = overlayPendingCredit(result.value))
    }

    suspend fun loadSpeciesQuests(): LoadResult<List<FieldQuest>> {
        val result = loadWithCache(
            cacheFile = File(cacheDirectory, "species-quests.json"),
            fetch = api::getSpeciesQuestsJson,
            parse = ::parseFieldQuests,
        )
        return result.copy(value = overlayPendingQuests(result.value))
    }

    suspend fun loadSpeciesQuest(questId: String): LoadResult<FieldQuest> {
        val result = loadWithCache(
            cacheFile = File(cacheDirectory, "species-quest-$questId.json"),
            fetch = { api.getSpeciesQuestJson(questId) },
            parse = ::parseFieldQuest,
        )
        return result.copy(value = overlayPendingQuests(listOf(result.value)).first())
    }

    suspend fun createSpeciesQuest(
        areaId: String,
        targetDate: String,
        radiusKm: Int,
        iconicTaxon: String?,
        title: String,
        linkedHikeId: String?,
        focusTaxonIds: List<Long>,
        resultLimit: Int,
    ): FieldQuest {
        var questJson = api.createSpeciesQuest(
            areaId = areaId,
            targetDate = targetDate,
            radiusKm = radiusKm,
            iconicTaxon = iconicTaxon,
            title = title,
            linkedHikeId = linkedHikeId,
            resultLimit = resultLimit,
        )
        var quest = parseFieldQuest(questJson)
        if (focusTaxonIds.isNotEmpty()) {
            questJson = api.updateSpeciesQuest(quest.id, focusTaxonIds = focusTaxonIds.take(10))
            quest = parseFieldQuest(questJson)
        }
        withContext(Dispatchers.IO) {
            val listCache = File(cacheDirectory, "species-quests.json")
            val cachedItems = runCatching {
                listCache.takeIf { it.exists() }?.readText()?.let(::JSONArray)
            }.getOrNull() ?: JSONArray()
            val nextItems = JSONArray().put(JSONObject(questJson))
            for (index in 0 until cachedItems.length()) {
                val item = cachedItems.optJSONObject(index)
                if (item?.optString("id") != quest.id) nextItems.put(item)
            }
            listCache.writeText(nextItems.toString())
            File(cacheDirectory, "species-quest-${quest.id}.json").writeText(questJson)
        }
        return quest
    }

    suspend fun queueQuestFocus(quest: FieldQuest, focusTaxonIds: List<Long>): FieldQuest {
        fieldQueue.queueQuestFocus(quest.id, focusTaxonIds.take(10))
        return quest.withFocus(focusTaxonIds, pending = true)
    }

    suspend fun updateSpeciesQuest(
        questId: String,
        title: String? = null,
        status: String? = null,
        linkedHikeId: String? = null,
        setLinkedHike: Boolean = false,
    ): FieldQuest {
        val quest = parseFieldQuest(
            api.updateSpeciesQuest(
                questId = questId,
                title = title,
                status = status,
                linkedHikeId = linkedHikeId,
                setLinkedHike = setLinkedHike,
            ),
        )
        withContext(Dispatchers.IO) {
            File(cacheDirectory, "species-quests.json").delete()
            File(cacheDirectory, "species-quest-$questId.json").delete()
        }
        return quest
    }

    suspend fun deleteSpeciesQuest(questId: String) {
        api.deleteSpeciesQuest(questId)
        withContext(Dispatchers.IO) {
            File(cacheDirectory, "species-quests.json").delete()
            File(cacheDirectory, "species-quest-$questId.json").delete()
        }
    }

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

    suspend fun getInatAuthorizationUrl(): String = api.getInatAuthorizationUrl()

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

    suspend fun clearSyncAttention() = fieldQueue.clearAttention()

    private suspend fun overlayPendingCredit(nearby: NearbySpecies): NearbySpecies {
        val pendingTaxonIds = fieldQueue.pendingCreditTaxonIds()
        if (pendingTaxonIds.isEmpty()) return nearby
        return nearby.copy(
            taxa = nearby.taxa.map { taxon ->
                if (!taxon.collected && taxon.taxonId in pendingTaxonIds) {
                    taxon.copy(pendingCredit = true)
                } else {
                    taxon
                }
            },
        )
    }

    private suspend fun overlayPendingQuests(quests: List<FieldQuest>): List<FieldQuest> {
        val pendingFocus = fieldQueue.pendingQuestFocus()
        val pendingCredits = fieldQueue.pendingCreditTaxonIds()
        return quests.map { quest ->
            val focus = pendingFocus[quest.id]
            val focused = if (focus == null) quest else quest.withFocus(focus, pending = true)
            focused.copy(
                taxa = focused.taxa.map { taxon ->
                    if (!taxon.collected && taxon.taxonId in pendingCredits) {
                        taxon.copy(pendingCredit = true)
                    } else {
                        taxon
                    }
                },
            )
        }
    }

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

private fun FieldQuest.withFocus(focusTaxonIds: List<Long>, pending: Boolean): FieldQuest {
    val order = focusTaxonIds.take(10).withIndex().associate { (index, taxonId) -> taxonId to index + 1 }
    return copy(
        taxa = taxa.map { it.copy(focusOrder = order[it.taxonId]) },
        pendingFocusSync = pending,
    )
}
