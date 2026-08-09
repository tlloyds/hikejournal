package com.hikejournal.app.data

import android.content.Context
import android.net.Uri
import com.hikejournal.app.tracking.TrackingRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.StandardCopyOption
import java.time.Instant

data class HikeDeletionResult(
    val notice: String? = null,
    val warning: String? = null,
)

data class CachedMapData(
    val sightings: List<Sighting>,
    val routeSegments: List<List<RoutePoint>>,
    val available: Boolean,
)

class HikeJournalRepository(context: Context) {
    private val appContext = context.applicationContext
    private val api = HikeJournalApi(appContext)
    private val fieldQueue = FieldOperationQueue(appContext)
    private val trackingRepository = TrackingRepository.get(appContext)
    private val cacheDirectory = File(context.filesDir, "journal-cache").apply { mkdirs() }

    val syncStatus = fieldQueue.status

    val serverUrl: String get() = api.serverUrl
    val pairingKey: String get() = api.pairingKey

    suspend fun loadCompanionConfig(): CompanionConfig = api.getCompanionConfig()

    fun updateServerUrl(value: String) {
        api.serverUrl = value
    }

    fun updateConnection(serverUrl: String, pairingKey: String) {
        api.serverUrl = serverUrl
        api.pairingKey = pairingKey
        SyncScheduler.schedule(appContext)
    }

    suspend fun loadHikes(): LoadResult<List<Hike>> {
        val resultAttempt = runCatching {
            loadWithCache(
                cacheFile = File(cacheDirectory, "hikes.json"),
                fetch = api::getHikesJson,
                parse = ::parseHikes,
            )
        }
        val cachedDetails = loadCachedHikeFiles()
        val result = resultAttempt.getOrElse { networkError ->
            if (cachedDetails.none { it.isLocalDraft }) throw networkError
            LoadResult(emptyList(), fromCache = true)
        }
        val hikes = result.value.associateBy { it.id }.toMutableMap()
        cachedDetails.forEach { cached ->
            when {
                result.fromCache && (cached.isLocalDraft || cached.hike.id in hikes) -> {
                    // A detail cache is newer than a stale list cache after an offline edit.
                    hikes[cached.hike.id] = cached.hike
                }
                cached.isLocalDraft -> hikes.putIfAbsent(cached.hike.id, cached.hike)
            }
        }
        if (!result.fromCache) {
            clearVerifiedLocalDraftMarkers(result.value.mapTo(mutableSetOf()) { it.id })
        }
        return result.copy(value = fieldQueue.overlayHikes(hikes.values.toList()))
    }

    /**
     * Returns the last archive snapshot without waiting for the companion service.
     *
     * The archive list is intentionally separate from [loadHikes]: callers can show this
     * immediately at launch, then use [loadHikes] to revalidate it in the background.
     */
    suspend fun loadCachedHikes(): List<Hike>? {
        val cachedList = withContext(Dispatchers.IO) {
            File(cacheDirectory, "hikes.json")
                .takeIf(File::exists)
                ?.readText()
                ?.takeIf(String::isNotBlank)
        }?.let { json -> withContext(Dispatchers.Default) { parseHikes(json) } }
        val cachedDetails = loadCachedHikeFiles()
        if (cachedList == null && cachedDetails.none { it.isLocalDraft }) return null

        val hikes = cachedList.orEmpty().associateBy { it.id }.toMutableMap()
        cachedDetails.forEach { cached ->
            // A detail cache is newer than the archive snapshot after an offline edit.
            if (cached.isLocalDraft || cached.hike.id in hikes) hikes[cached.hike.id] = cached.hike
        }
        return fieldQueue.overlayHikes(hikes.values.toList())
    }

    suspend fun loadHikeLocations(): LoadResult<List<HikeLocation>> = loadWithCache(
        cacheFile = File(cacheDirectory, "hike-locations.json"),
        fetch = api::getHikeLocationsJson,
        parse = ::parseHikeLocations,
    )

    suspend fun loadHike(hikeId: String): LoadResult<Hike> = journalCacheMutex.withLock {
        val cacheFile = File(cacheDirectory, "hike-$hikeId.json")
        try {
            val json = api.getHikeJson(hikeId)
            val payload = JSONObject(json)
            val photos = JSONArray()
            var offset = 0
            do {
                val page = JSONObject(api.getHikePhotosJson(hikeId, offset))
                val pagePhotos = page.optJSONArray("photos") ?: JSONArray()
                for (index in 0 until pagePhotos.length()) photos.put(pagePhotos.getJSONObject(index))
                offset = if (page.isNull("next_offset")) -1 else page.optInt("next_offset", -1)
            } while (offset >= 0)
            payload.put("photos", photos)
            payload.put("photo_count", photos.length())
            if (payload.optString("cover_url").isBlank()) {
                val coverId = payload.optString("cover_photo_id")
                val cover = (0 until photos.length())
                    .asSequence()
                    .map { photos.getJSONObject(it) }
                    .firstOrNull { it.optString("id") == coverId }
                    ?: (if (photos.length() > 0) photos.getJSONObject(photos.length() - 1) else null)
                payload.put("cover_url", cover?.optString("url").orEmpty())
            }
            val routePayload = JSONObject(api.getHikeRouteJson(hikeId))
            payload.put("route_segments", routePayload.optJSONArray("route_segments") ?: JSONArray())
            if (!routePayload.isNull("duration_seconds")) {
                payload.put("duration_seconds", routePayload.optLong("duration_seconds"))
            }
            if (!routePayload.isNull("started_at")) {
                payload.put("route_started_at", routePayload.optString("started_at"))
            }
            withContext(Dispatchers.IO) {
                val preserveLocalDraft = runCatching {
                    cacheFile.takeIf(File::exists)
                        ?.readText()
                        ?.let(::JSONObject)
                        ?.optBoolean(LOCAL_DRAFT_MARKER)
                }.getOrNull() == true
                if (preserveLocalDraft) payload.put(LOCAL_DRAFT_MARKER, true)
                writeJsonAtomically(cacheFile, payload)
            }
            val completeJson = payload.toString()
            val parsed = withContext(Dispatchers.Default) { parseHike(completeJson) }
            if (parsed.routeSegments.isNotEmpty()) trackingRepository.clearFinished(hikeId)
            val overlay = fieldQueue.overlayHike(parsed, hikeId)
                ?: throw IllegalStateException("Hike not found.")
            LoadResult(overlayRetainedTrackingRoute(overlay, hikeId), fromCache = false)
        } catch (networkError: Exception) {
            val cached = withContext(Dispatchers.IO) { cacheFile.takeIf { it.exists() }?.readText() }
            val parsed = withContext(Dispatchers.Default) { cached?.let(::parseHike) }
            val overlay = fieldQueue.overlayHike(parsed, hikeId)
            if (overlay == null) throw networkError
            LoadResult(overlayRetainedTrackingRoute(overlay, hikeId), fromCache = true)
        }
    }

    suspend fun loadCachedHike(hikeId: String, expectedPhotoCount: Int? = null): Hike? = journalCacheMutex.withLock {
        val cacheFile = File(cacheDirectory, "hike-$hikeId.json")
        val parsed = withContext(Dispatchers.IO) {
            cacheFile
                .takeIf { it.exists() }
                ?.readText()
                ?.takeIf { it.isNotBlank() }
                ?.let(::parseHike)
        }
        val cached = fieldQueue.overlayHike(parsed, hikeId)?.let {
            overlayRetainedTrackingRoute(it, hikeId)
        }
        if (expectedPhotoCount != null && cached?.photoCount != expectedPhotoCount) null else cached
    }

    suspend fun loadSpecies(): LoadResult<List<SpeciesRecord>> {
        val result = loadWithCache(
            cacheFile = File(cacheDirectory, "species.json"),
            fetch = api::getSpeciesJson,
            parse = ::parseSpeciesList,
        )
        val deletedHikeIds = fieldQueue.deletedHikeIds()
        return result.copy(
            value = result.value.mapNotNull { it.withoutHikes(deletedHikeIds) },
        )
    }

    suspend fun loadSpeciesDetail(key: String): LoadResult<SpeciesRecord> {
        val result = loadWithCache(
            cacheFile = File(cacheDirectory, "species-${key.hashCode()}.json"),
            fetch = { api.getSpeciesDetailJson(key) },
            parse = ::parseSpecies,
        )
        val filtered = result.value.withoutHikes(fieldQueue.deletedHikeIds())
            ?: throw IllegalStateException("This species record was removed with its hike.")
        return result.copy(value = filtered)
    }

    suspend fun loadDiscoveryAreas(query: String = ""): LoadResult<List<DiscoveryArea>> = loadWithCache(
        cacheFile = File(cacheDirectory, "discovery-areas.json"),
        fetch = { api.getDiscoveryAreasJson(query) },
        parse = ::parseDiscoveryAreas,
    )

    suspend fun loadNearbySpecies(
        areaId: String?,
        targetDate: String,
        radiusKm: Int,
        iconicTaxa: List<String>,
        latitude: Double? = null,
        longitude: Double? = null,
        limit: Int = 50,
    ): LoadResult<NearbySpecies> {
        val cacheKey = listOf(
            areaId.orEmpty(),
            targetDate,
            radiusKm.toString(),
            iconicTaxa.joinToString(","),
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
                    iconicTaxa = iconicTaxa,
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

    suspend fun loadNearbySightings(
        nearby: NearbySpecies,
        taxonId: Long,
    ): LoadResult<QuestSightingsMap> {
        val cacheKey = listOf(
            nearby.areaId,
            nearby.latitude?.toString().orEmpty(),
            nearby.longitude?.toString().orEmpty(),
            nearby.targetDate,
            nearby.radiusKm.toString(),
            taxonId.toString(),
        ).joinToString("|").hashCode()
        return loadWithCache(
            cacheFile = File(cacheDirectory, "nearby-sightings-$cacheKey.json"),
            fetch = { api.getNearbySightingsJson(nearby, taxonId) },
            parse = ::parseQuestSightingsMap,
        )
    }

    suspend fun loadQuestSightings(questId: String, taxonId: Long): LoadResult<QuestSightingsMap> =
        loadWithCache(
            cacheFile = File(cacheDirectory, "quest-sightings-$questId-$taxonId.json"),
            fetch = { api.getQuestSightingsJson(questId, taxonId) },
            parse = ::parseQuestSightingsMap,
        )

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

    suspend fun loadSightings(): LoadResult<List<Sighting>> {
        val result = loadWithCache(
            cacheFile = File(cacheDirectory, "sightings.json"),
            fetch = api::getSightingsJson,
            parse = ::parseSightings,
        )
        val deletedHikeIds = fieldQueue.deletedHikeIds()
        return result.copy(value = result.value.filterNot { it.hikeId in deletedHikeIds })
    }

    /**
     * Reads the last complete map snapshot without waiting for the companion service.
     * The caller can render this immediately and revalidate both feeds in the background.
     */
    suspend fun loadCachedMapData(): CachedMapData {
        val (sightingsJson, routesJson) = journalCacheMutex.withLock {
            withContext(Dispatchers.IO) {
                File(cacheDirectory, "sightings.json").takeIf(File::exists)?.readText() to
                    File(cacheDirectory, "map-routes.json").takeIf(File::exists)?.readText()
            }
        }
        val deletedHikeIds = fieldQueue.deletedHikeIds()
        val sightings = sightingsJson
            ?.takeIf(String::isNotBlank)
            ?.let { json -> withContext(Dispatchers.Default) { parseSightings(json) } }
            .orEmpty()
            .filterNot { it.hikeId in deletedHikeIds }
        val cachedRoutes = routesJson
            ?.takeIf(String::isNotBlank)
            ?.let { json -> withContext(Dispatchers.Default) { parseMapRoutes(json) } }
            .orEmpty()
        return CachedMapData(
            sightings = sightings,
            routeSegments = overlayLocalMapRoutes(cachedRoutes, deletedHikeIds),
            available = !sightingsJson.isNullOrBlank() || !routesJson.isNullOrBlank(),
        )
    }

    suspend fun loadMapRouteSegments(): LoadResult<List<List<RoutePoint>>> {
        val pendingRoutes = fieldQueue.pendingRoutesByHikeId()
        val retainedRoutes = trackingRepository.allFinishedRoutesByHikeId()
            .mapValues { (_, segments) ->
                segments.map { segment ->
                    segment.map { point -> RoutePoint(point.latitude, point.longitude) }
                }.filter { it.size >= 2 }
            }
            .filterValues { it.isNotEmpty() }
        val deletedHikeIds = fieldQueue.deletedHikeIds()
        val result = try {
            loadWithCache(
                cacheFile = File(cacheDirectory, "map-routes.json"),
                fetch = api::getMapRoutesJson,
                parse = ::parseMapRoutes,
            )
        } catch (networkError: Exception) {
            val localRoutes = (retainedRoutes + pendingRoutes)
                .filterKeys { it !in deletedHikeIds }
                .values
                .flatten()
            if (localRoutes.isEmpty()) throw networkError
            return LoadResult(localRoutes, fromCache = true)
        }

        return LoadResult(
            value = overlayLocalMapRoutes(
                serverRoutes = result.value,
                deletedHikeIds = deletedHikeIds,
                retainedRoutes = retainedRoutes,
                pendingRoutes = pendingRoutes,
            ),
            fromCache = result.fromCache,
        )
    }

    private suspend fun overlayLocalMapRoutes(
        serverRoutes: List<MapRoute>,
        deletedHikeIds: Set<String>,
        retainedRoutes: Map<String, List<List<RoutePoint>>>? = null,
        pendingRoutes: Map<String, List<List<RoutePoint>>>? = null,
    ): List<List<RoutePoint>> {
        val localRetainedRoutes = retainedRoutes ?: trackingRepository.allFinishedRoutesByHikeId()
            .mapValues { (_, segments) ->
                segments.map { segment ->
                    segment.map { point -> RoutePoint(point.latitude, point.longitude) }
                }.filter { it.size >= 2 }
            }
            .filterValues { it.isNotEmpty() }
        val localPendingRoutes = pendingRoutes ?: fieldQueue.pendingRoutesByHikeId()
        val mergedRoutes = serverRoutes.associate { it.hikeId to it.segments }.toMutableMap()
        localRetainedRoutes.forEach { (hikeId, segments) ->
            if (mergedRoutes[hikeId].isNullOrEmpty()) mergedRoutes[hikeId] = segments
        }
        localPendingRoutes.forEach { (hikeId, segments) -> mergedRoutes[hikeId] = segments }
        deletedHikeIds.forEach(mergedRoutes::remove)
        return mergedRoutes.values.flatten()
    }

    suspend fun loadReviewQueue(): LoadResult<List<ReviewItem>> {
        val result = loadWithCache(
            cacheFile = File(cacheDirectory, "species-review.json"),
            fetch = api::getReviewQueueJson,
            parse = ::parseReviewQueue,
        )
        val pending = fieldQueue.pendingReviewPhotoIds()
        val deletedHikeIds = fieldQueue.deletedHikeIds()
        return result.copy(
            value = result.value.filterNot { it.id in pending || it.hikeId in deletedHikeIds },
        )
    }

    suspend fun requestReviewRecommendation(photoId: String): ReviewItem {
        val item = parseReviewItem(api.requestReviewRecommendation(photoId))
        withContext(Dispatchers.IO) {
            File(cacheDirectory, "species-review.json").delete()
        }
        return item
    }

    suspend fun requestReviewBatch(groups: List<List<String>>): ReviewBatchResult {
        val result = parseReviewBatchResult(api.requestReviewBatch(groups))
        withContext(Dispatchers.IO) {
            File(cacheDirectory, "species-review.json").delete()
        }
        return result
    }

    suspend fun startReviewBatch(groups: List<List<String>>, clientRequestId: String? = null): ReviewBatchStatus =
        parseReviewBatchStatus(api.startReviewBatch(groups, clientRequestId))

    suspend fun getReviewBatchStatus(jobId: String): ReviewBatchStatus =
        parseReviewBatchStatus(api.getReviewBatchStatus(jobId))

    suspend fun getInatAuthorizationUrl(): String = api.getInatAuthorizationUrl()

    suspend fun loadPublishQueue(): LoadResult<PublishQueue> {
        val result = loadWithCache(
            cacheFile = File(cacheDirectory, "species-publish.json"),
            fetch = api::getPublishQueueJson,
            parse = ::parsePublishQueue,
        )
        val deletedHikeIds = fieldQueue.deletedHikeIds()
        val items = result.value.items.filterNot { it.hikeId in deletedHikeIds }
        return result.copy(
            value = result.value.copy(
                readyCount = items.count { it.state == "ready" },
                needsAttentionCount = items.count { it.state == "needs_attention" },
                postedCount = items.count { it.state == "posted" },
                items = items,
            ),
        )
    }

    suspend fun publishObservation(item: PublishItem, options: PublishOptions): PublishItem {
        val published = parsePublishItem(api.publishObservation(item.id, options))
        withContext(Dispatchers.IO) {
            File(cacheDirectory, "species-publish.json").delete()
            File(cacheDirectory, "species.json").delete()
            File(cacheDirectory, "sightings.json").delete()
        }
        return published
    }

    suspend fun startPublishBatch(
        groups: List<List<String>>,
        options: PublishOptions,
        clientRequestId: String? = null,
    ): PublishBatchStatus = parsePublishBatchStatus(api.startPublishBatch(groups, options, clientRequestId))

    suspend fun getPublishBatchStatus(jobId: String): PublishBatchStatus =
        parsePublishBatchStatus(api.getPublishBatchStatus(jobId))

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

    suspend fun createHike(draft: HikeDraft): Hike {
        val hike = fieldQueue.queueCreateHike(draft)
        cacheLocalDraft(hike)
        return hike
    }

    suspend fun createRecordedHike(
        hikeId: String,
        draft: HikeDraft,
        route: RecordedRouteUpload?,
    ): Hike {
        val hike = fieldQueue.queueCreateHike(draft, hikeId)
        route?.let { fieldQueue.queueRecordedRoute(hikeId, it) }
        val recorded = hike.copy(
            durationSeconds = route?.durationSeconds,
            routeStartedAt = route?.startedAt,
            routeSegments = route?.routeSegments.orEmpty(),
        )
        cacheLocalDraft(recorded)
        return recorded
    }

    private suspend fun overlayRetainedTrackingRoute(hike: Hike, hikeId: String): Hike {
        val recording = trackingRepository.finished(hikeId) ?: return hike
        val routeSegments = recording.routeSegments
            .map { segment ->
                segment.map { point -> RoutePoint(point.latitude, point.longitude) }
            }
            .filter { it.size >= 2 }
        return hike.copy(
            distanceMiles = hike.distanceMiles
                ?: (recording.distanceMeters / METERS_PER_MILE).coerceAtLeast(0.0),
            durationSeconds = hike.durationSeconds
                ?: ((recording.activeElapsedMs + 500L) / 1_000L).coerceAtLeast(0L),
            routeStartedAt = hike.routeStartedAt
                ?: Instant.ofEpochMilli(recording.startedAtEpochMs).toString(),
            routeSegments = hike.routeSegments.ifEmpty { routeSegments },
        )
    }

    private suspend fun cacheLocalDraft(hike: Hike) = journalCacheMutex.withLock {
        withContext(Dispatchers.IO) {
            writeJsonAtomically(
                File(cacheDirectory, "hike-${hike.id}.json"),
                hike.toLocalDraftJson(),
            )
        }
    }

    private suspend fun updateCachedDraft(hikeId: String, draft: HikeDraft) = journalCacheMutex.withLock {
        withContext(Dispatchers.IO) {
            val cacheFile = File(cacheDirectory, "hike-$hikeId.json")
            if (!cacheFile.exists()) return@withContext
            val payload = runCatching { JSONObject(cacheFile.readText()) }.getOrNull()
                ?: return@withContext
            payload
                .put("title", draft.title)
                .put("hike_date", draft.hikeDate)
                .put("distance_miles", draft.distanceMiles ?: JSONObject.NULL)
                .put("location_name", draft.locationName)
                .put("notes", draft.notes)
            writeJsonAtomically(cacheFile, payload)
        }
    }

    private suspend fun loadCachedHikeFiles(): List<CachedHikeFile> = journalCacheMutex.withLock {
        withContext(Dispatchers.IO) {
            cacheDirectory.listFiles()
                .orEmpty()
                .asSequence()
                .filter { it.isFile && it.name.startsWith("hike-") && it.extension == "json" }
                .mapNotNull { file ->
                    runCatching {
                        val payload = JSONObject(file.readText())
                        val hike = parseHike(payload.toString()).takeIf { it.id.isNotBlank() }
                            ?: return@runCatching null
                        CachedHikeFile(
                            hike = hike,
                            isLocalDraft = payload.optBoolean(LOCAL_DRAFT_MARKER),
                        )
                    }.getOrNull()
                }
                .toList()
        }
    }

    private suspend fun clearVerifiedLocalDraftMarkers(verifiedHikeIds: Set<String>) =
        journalCacheMutex.withLock {
            withContext(Dispatchers.IO) {
                verifiedHikeIds.forEach { hikeId ->
                    val cacheFile = File(cacheDirectory, "hike-$hikeId.json")
                    runCatching {
                        if (!cacheFile.exists()) return@runCatching
                        val payload = JSONObject(cacheFile.readText())
                        if (!payload.optBoolean(LOCAL_DRAFT_MARKER)) return@runCatching
                        payload.remove(LOCAL_DRAFT_MARKER)
                        writeJsonAtomically(cacheFile, payload)
                    }
                }
            }
        }

    suspend fun updateHike(hikeId: String, draft: HikeDraft) {
        fieldQueue.queueUpdateHike(hikeId, draft)
        updateCachedDraft(hikeId, draft)
    }

    suspend fun setArchived(hikeId: String, archived: Boolean) {
        fieldQueue.queueArchive(hikeId, archived)
    }

    suspend fun deleteHike(
        hikeId: String,
        remoteDeletionAllowed: Boolean,
    ): HikeDeletionResult {
        val result = FieldSyncEngine(appContext).deleteHike(
            hikeId = hikeId,
            remoteDeletionAllowed = remoteDeletionAllowed,
        )
        return when {
            result.needsAttention -> HikeDeletionResult(
                warning = "Deletion needs sync attention: ${result.lastError ?: "check the companion service"}.",
            )
            result.cleanupFailures > 0 -> HikeDeletionResult(
                notice = "Hike deleted. Android will finish removing ${result.cleanupFailures} temporary local " +
                    "file${if (result.cleanupFailures == 1) "" else "s"} during sync.",
            )
            result.pending -> HikeDeletionResult(
                notice = "Deletion queued. It will finish automatically when the companion service is reachable.",
            )
            else -> HikeDeletionResult(notice = "Hike deleted.")
        }
    }

    suspend fun setHikeCover(hikeId: String, photoId: String?, coverUrl: String) {
        fieldQueue.queueHikeCover(hikeId, photoId, coverUrl)
        journalCacheMutex.withLock {
            withContext(Dispatchers.IO) {
                val cacheFile = File(cacheDirectory, "hike-$hikeId.json")
                runCatching {
                    if (!cacheFile.exists()) return@runCatching
                    val payload = JSONObject(cacheFile.readText())
                        .put("cover_photo_id", photoId ?: JSONObject.NULL)
                        .put("cover_url", coverUrl)
                    writeJsonAtomically(cacheFile, payload)
                }
            }
        }
    }

    suspend fun uploadPhoto(
        hikeId: String,
        uri: Uri,
        caption: String,
        queueForReview: Boolean,
    ): Photo = fieldQueue.queuePhoto(hikeId, uri, caption, queueForReview)

    suspend fun uploadRoute(hikeId: String, uri: Uri) {
        fieldQueue.queueRoute(hikeId, uri)
    }

    suspend fun inspectMediaLocations(uris: List<Uri>): MediaLocationSummary =
        fieldQueue.inspectMediaLocations(uris)

    suspend fun updateCaption(photoId: String, hikeId: String?, caption: String) =
        fieldQueue.queueCaption(photoId, hikeId, caption)

    suspend fun deletePhoto(photoId: String, hikeId: String?) = fieldQueue.queueDeletePhoto(photoId, hikeId)

    suspend fun setSpeciesReview(photoId: String, hikeId: String?, queued: Boolean) {
        fieldQueue.queueSpeciesReview(photoId, hikeId, queued)
        withContext(Dispatchers.IO) { File(cacheDirectory, "species-review.json").delete() }
    }

    suspend fun assignKnownSpecies(photoId: String, hikeId: String?, species: SpeciesRecord) {
        fieldQueue.queueKnownSpecies(photoId, hikeId, species)
        withContext(Dispatchers.IO) {
            File(cacheDirectory, "species-review.json").delete()
            File(cacheDirectory, "species-publish.json").delete()
            File(cacheDirectory, "sightings.json").delete()
        }
    }

    suspend fun syncNow(): Boolean = FieldSyncEngine(appContext).drain()

    suspend fun syncPhotoNow(photoId: String): Boolean = FieldSyncEngine(appContext).drain(photoId)

    suspend fun retryAttention() = fieldQueue.retryAttention()

    suspend fun discardSyncAttention() = fieldQueue.discardAttention()

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
        val deletedHikeIds = fieldQueue.deletedHikeIds()
        return quests.map { quest ->
            val focus = pendingFocus[quest.id]
            val unlinked = if (quest.linkedHikeId in deletedHikeIds) {
                quest.copy(linkedHikeId = null)
            } else {
                quest
            }
            val focused = if (focus == null) unlinked else unlinked.withFocus(focus, pending = true)
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
    ): LoadResult<T> = journalCacheMutex.withLock {
        try {
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

private const val METERS_PER_MILE = 1_609.344
private const val LOCAL_DRAFT_MARKER = "local_android_draft"

private data class CachedHikeFile(
    val hike: Hike,
    val isLocalDraft: Boolean,
)

private fun Hike.toLocalDraftJson(): JSONObject = JSONObject()
    .put("id", id)
    .put("title", title)
    .put("hike_date", hikeDate)
    .put("distance_miles", distanceMiles ?: JSONObject.NULL)
    .put("duration_seconds", durationSeconds ?: JSONObject.NULL)
    .put("route_started_at", routeStartedAt ?: JSONObject.NULL)
    .put("location_name", locationName)
    .put("notes", notes)
    .put("is_archived", isArchived)
    .put("is_standalone", isStandalone)
    .put("cover_url", coverUrl)
    .put("cover_photo_id", coverPhotoId ?: JSONObject.NULL)
    .put("photo_count", photoCount)
    .put("species_count", speciesCount)
    // Pending operations are overlaid from Room. The durable cache represents the last locally
    // complete hike once those operations have been acknowledged and removed.
    .put("sync_state", "synced")
    .put("photos", JSONArray())
    .put(
        "route_segments",
        JSONArray().apply {
            routeSegments.filter { it.size >= 2 }.forEach { segment ->
                put(JSONArray().apply {
                    segment.forEach { point ->
                        put(JSONObject().put("lat", point.latitude).put("lng", point.longitude))
                    }
                })
            }
        },
    )
    .put(LOCAL_DRAFT_MARKER, true)

private fun writeJsonAtomically(destination: File, payload: JSONObject) {
    destination.parentFile?.mkdirs()
    val temporary = File(destination.parentFile, ".${destination.name}.${System.nanoTime()}.tmp")
    try {
        temporary.writeText(payload.toString())
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
    } finally {
        if (temporary.exists()) temporary.delete()
    }
}

private fun FieldQuest.withFocus(focusTaxonIds: List<Long>, pending: Boolean): FieldQuest {
    val order = focusTaxonIds.take(10).withIndex().associate { (index, taxonId) -> taxonId to index + 1 }
    return copy(
        taxa = taxa.map { it.copy(focusOrder = order[it.taxonId]) },
        pendingFocusSync = pending,
    )
}

internal fun SpeciesRecord.withoutHikes(deletedHikeIds: Set<String>): SpeciesRecord? {
    if (deletedHikeIds.isEmpty() || hikeIds.none { it in deletedHikeIds }) return this
    val removedEncounterCount = deletedHikeIds.sumOf { hikeEncounterCounts[it] ?: 0 }
    val remainingEncounterCount = (encounterCount - removedEncounterCount).coerceAtLeast(0)
    val remainingHikeCounts = hikeEncounterCounts.filterKeys { it !in deletedHikeIds }
    val removedCoverUrls = hikeCoverUrls.filterKeys { it in deletedHikeIds }.values.toSet()
    val remainingCoverUrls = hikeCoverUrls.filterKeys { it !in deletedHikeIds }
    val remainingLatestSeen = hikeLatestSeen.filterKeys { it !in deletedHikeIds }
    val remainingEncounters = encounters.filterNot { it.hikeId in deletedHikeIds }
    if (remainingEncounterCount == 0 && remainingEncounters.isEmpty()) return null
    val nextCoverUrl = if (coverUrl in removedCoverUrls) {
        remainingCoverUrls.values.firstOrNull()
            ?: remainingEncounters.firstOrNull()?.photo?.url.orEmpty()
    } else {
        coverUrl
    }
    val removedLatestSeen = hikeLatestSeen.filterKeys { it in deletedHikeIds }.values.toSet()
    val nextLatestSeen = if (latestSeen in removedLatestSeen) {
        latestObservedValue(remainingLatestSeen.values + remainingEncounters.mapNotNull { it.observedOn })
    } else {
        latestSeen
    }
    return copy(
        encounterCount = remainingEncounterCount,
        hikeCount = remainingHikeCounts.size,
        hikeIds = hikeIds.filterNot { it in deletedHikeIds },
        hikeEncounterCounts = remainingHikeCounts,
        hikeCoverUrls = remainingCoverUrls,
        hikeLatestSeen = remainingLatestSeen,
        latestSeen = nextLatestSeen,
        coverUrl = nextCoverUrl,
        encounters = remainingEncounters,
    )
}
