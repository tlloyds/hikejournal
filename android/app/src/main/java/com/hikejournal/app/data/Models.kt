package com.hikejournal.app.data

import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.round

data class Hike(
    val id: String,
    val title: String,
    val hikeDate: String,
    val distanceMiles: Double?,
    val durationSeconds: Long? = null,
    val routeStartedAt: String? = null,
    val locationName: String,
    val notes: String,
    val isArchived: Boolean,
    val isStandalone: Boolean = false,
    val coverUrl: String,
    val coverPhotoId: String? = null,
    val photoCount: Int,
    val speciesCount: Int,
    val syncState: String = "synced",
    val photos: List<Photo> = emptyList(),
    val routeSegments: List<List<RoutePoint>> = emptyList(),
)

data class RoutePoint(
    val latitude: Double,
    val longitude: Double,
)

internal data class MapRoute(
    val hikeId: String,
    val segments: List<List<RoutePoint>>,
)

data class Photo(
    val id: String,
    val hikeId: String?,
    val url: String,
    val caption: String,
    val takenAt: String?,
    val createdAt: String?,
    val latitude: Double?,
    val longitude: Double?,
    val width: Int?,
    val height: Int?,
    val contentType: String,
    val processingStatus: String,
    val syncState: String = "synced",
    val species: List<SpeciesLabel>,
)

data class MediaLocationSummary(
    val totalCount: Int,
    val geotaggedCount: Int,
) {
    val missingCount: Int get() = (totalCount - geotaggedCount).coerceAtLeast(0)
    val allGeotagged: Boolean get() = totalCount > 0 && missingCount == 0
}

data class SpeciesLabel(
    val commonName: String,
    val scientificName: String,
    val status: String,
    val isPrimary: Boolean,
    val taxonId: Long? = null,
    val wikipediaUrl: String = "",
    val wikipediaSummary: String = "",
)

data class HikeDraft(
    val title: String,
    val hikeDate: String,
    val distanceMiles: Double?,
    val locationName: String,
    val notes: String,
    val locationId: String? = null,
)

data class HikeLocation(
    val id: String,
    val name: String,
)

data class SpeciesRecord(
    val key: String,
    val taxonId: Long?,
    val commonName: String,
    val scientificName: String,
    val rank: String,
    val iconicTaxonName: String,
    val wikipediaUrl: String,
    val wikipediaSummary: String,
    val encounterCount: Int,
    val hikeCount: Int,
    val hikeIds: List<String>,
    val hikeEncounterCounts: Map<String, Int>,
    val hikeCoverUrls: Map<String, String>,
    val hikeLatestSeen: Map<String, String>,
    val latestSeen: String?,
    val coverUrl: String,
    val encounters: List<Encounter> = emptyList(),
)

data class DiscoveryArea(
    val id: String,
    val name: String,
    val latitude: Double,
    val longitude: Double,
    val locationType: String,
)

fun filterDiscoveryAreas(
    areas: List<DiscoveryArea>,
    query: String,
    limit: Int = 6,
): List<DiscoveryArea> {
    val normalizedQuery = query.trim()
    return areas
        .asSequence()
        .filter { normalizedQuery.isBlank() || it.name.contains(normalizedQuery, ignoreCase = true) }
        .take(limit)
        .toList()
}

data class DiscoveryPhoto(
    val url: String,
    val attribution: String,
    val licenseCode: String,
)

data class DiscoveryTaxon(
    val taxonId: Long,
    val commonName: String,
    val scientificName: String,
    val iconicTaxonName: String,
    val observationCount: Int,
    val nearbyRank: Int,
    val frequencyBand: String,
    val referencePhoto: DiscoveryPhoto?,
    val collected: Boolean,
    val collectedAt: String?,
    val collectionPhotoUrl: String?,
    val wikipediaUrl: String,
    val wikipediaSummary: String,
    val matchReason: String,
    val focusOrder: Int?,
    val pendingCredit: Boolean,
)

data class DiscoveryProgress(
    val collectedCount: Int,
    val totalCount: Int,
    val remainingCount: Int,
)

data class NearbySpecies(
    val areaId: String,
    val areaName: String,
    val latitude: Double?,
    val longitude: Double?,
    val radiusKm: Int,
    val targetDate: String,
    val periodLabel: String,
    val iconicTaxon: String?,
    val resultLimit: Int,
    val dataDensity: String,
    val dataDensityMessage: String,
    val sourceGuidance: String,
    val fromCache: Boolean,
    val progress: DiscoveryProgress,
    val taxa: List<DiscoveryTaxon>,
)

data class FieldQuest(
    val id: String,
    val title: String,
    val status: String,
    val linkedHikeId: String?,
    val areaId: String,
    val areaName: String,
    val latitude: Double?,
    val longitude: Double?,
    val radiusKm: Int,
    val targetDate: String,
    val periodLabel: String,
    val iconicTaxon: String?,
    val progress: DiscoveryProgress,
    val taxa: List<DiscoveryTaxon>,
    val pendingFocusSync: Boolean = false,
)

data class QuestSighting(
    val id: String,
    val latitude: Double,
    val longitude: Double,
    val observedOn: String,
    val placeGuess: String,
    val observer: String,
    val uri: String,
    val photoUrl: String,
    val photoAttribution: String,
    val photoLicenseCode: String,
    val positionalAccuracyMeters: Int?,
    val obscured: Boolean,
)

data class QuestSightingsMap(
    val questId: String,
    val questTitle: String,
    val areaName: String,
    val latitude: Double,
    val longitude: Double,
    val radiusKm: Int,
    val periodLabel: String,
    val taxonId: Long,
    val commonName: String,
    val scientificName: String,
    val totalResults: Int,
    val mappedCount: Int,
    val limited: Boolean,
    val sourceGuidance: String,
    val sightings: List<QuestSighting>,
)

data class Encounter(
    val photo: Photo,
    val hikeId: String?,
    val hikeTitle: String,
    val hikeDate: String,
    val locationName: String,
    val observedOn: String?,
)

data class Sighting(
    val id: String,
    val hikeId: String?,
    val hikeTitle: String,
    val hikeDate: String,
    val locationName: String,
    val url: String,
    val caption: String,
    val takenAt: String?,
    val latitude: Double,
    val longitude: Double,
    val speciesName: String,
    val scientificName: String,
    val confirmed: Boolean,
)

data class ReviewCandidate(
    val taxonId: Long?,
    val commonName: String,
    val scientificName: String,
    val confidence: Double?,
)

/**
 * iNaturalist responses have used both fractional confidence (0.98) and
 * percentage-point confidence (98). The mobile decision API always expects a
 * fraction, so convert at the persistence and request boundaries.
 */
fun normalizedReviewConfidence(confidence: Double?): Double? = confidence?.let { value ->
    if (!value.isFinite()) return@let null
    (if (value > 1.0) value / 100.0 else value).coerceIn(0.0, 1.0)
}

data class ReviewItem(
    val id: String,
    val photo: Photo,
    val hikeId: String?,
    val hikeTitle: String,
    val hikeDate: String,
    val locationName: String,
    val state: String,
    val observationId: String?,
    val candidates: List<ReviewCandidate>,
)

data class ReviewBatchResult(
    val items: List<ReviewItem>,
    val processedPhotoIds: List<String>,
    val groupedCount: Int,
    val individualCount: Int,
    val warnings: List<String>,
)

data class ReviewBatchStatus(
    val jobId: String,
    val state: String,
    val totalPhotos: Int,
    val processedCount: Int,
    val processedPhotoIds: List<String>,
    val currentPhotoNumber: Int,
    val currentPhotoId: String?,
    val totalGroups: Int,
    val currentGroup: Int,
    val groupedCount: Int,
    val individualCount: Int,
    val warnings: List<String>,
    val error: String?,
    val items: List<ReviewItem>,
)

data class PublishItem(
    val id: String,
    val photo: Photo,
    val hikeId: String?,
    val hikeTitle: String,
    val hikeDate: String,
    val locationName: String,
    val taxonId: Long?,
    val commonName: String,
    val scientificName: String,
    val state: String,
    val inatObservationId: Long?,
    val inatUrl: String,
    val postedAt: String?,
    val photoAttached: Boolean?,
    val relatedObservationIds: List<String>,
    val relatedPhotoCount: Int,
)

data class PublishOptions(
    val observationIds: List<String>,
    val description: String = "",
    val tags: List<String> = emptyList(),
    val geoprivacy: String = "open",
    val captive: Boolean = false,
)

data class SyncStatus(
    val pendingCount: Int = 0,
    val syncingCount: Int = 0,
    val needsAttentionCount: Int = 0,
    val connected: Boolean = true,
    val lastSyncedAt: Long? = null,
    val attentionItems: List<SyncAttention> = emptyList(),
    val pendingCreateHikeIds: Set<String> = emptySet(),
)

data class SyncAttention(
    val kind: String,
    val detail: String,
    val error: String,
)

data class PublishQueue(
    val connected: Boolean,
    val readyCount: Int,
    val needsAttentionCount: Int,
    val postedCount: Int,
    val items: List<PublishItem>,
)

data class LoadResult<T>(val value: T, val fromCache: Boolean)

fun roundedDiscoveryCoordinate(value: Double): Double = round(value * 100.0) / 100.0

fun parseHikes(json: String): List<Hike> {
    val array = JSONArray(json)
    return List(array.length()) { index -> parseHike(array.getJSONObject(index)) }
}

fun parseHikeLocations(json: String): List<HikeLocation> {
    val array = JSONArray(json)
    return List(array.length()) { index ->
        val item = array.getJSONObject(index)
        HikeLocation(
            id = item.optString("id"),
            name = item.optString("name"),
        )
    }.filter { it.id.isNotBlank() && it.name.isNotBlank() }
}

fun parseHike(json: String): Hike = parseHike(JSONObject(json))

internal fun parseMapRoutes(json: String): List<MapRoute> {
    val routes = JSONArray(json)
    return List(routes.length()) { routeIndex ->
        val route = routes.getJSONObject(routeIndex)
        val segments = route.optJSONArray("route_segments") ?: JSONArray()
        MapRoute(
            hikeId = route.optString("hike_id"),
            segments = List(segments.length()) { segmentIndex ->
                val segment = segments.optJSONArray(segmentIndex) ?: JSONArray()
                List(segment.length()) { pointIndex ->
                    val point = segment.getJSONObject(pointIndex)
                    RoutePoint(point.optDouble("lat"), point.optDouble("lng"))
                }
            }.filter { it.size >= 2 },
        )
    }
}

fun parseMapRouteSegments(json: String): List<List<RoutePoint>> =
    parseMapRoutes(json).flatMap(MapRoute::segments)

fun parseSpeciesList(json: String): List<SpeciesRecord> {
    val array = JSONArray(json)
    return List(array.length()) { index -> parseSpecies(array.getJSONObject(index)) }
}

fun parseSpecies(json: String): SpeciesRecord = parseSpecies(JSONObject(json))

fun parseDiscoveryAreas(json: String): List<DiscoveryArea> {
    val array = JSONArray(json)
    return List(array.length()) { index ->
        val item = array.getJSONObject(index)
        DiscoveryArea(
            id = item.optString("id"),
            name = item.optString("name", "Unnamed area"),
            latitude = item.optDouble("lat"),
            longitude = item.optDouble("lng"),
            locationType = item.optString("location_type"),
        )
    }
}

fun parseNearbySpecies(json: String): NearbySpecies {
    val root = JSONObject(json)
    val area = root.optJSONObject("area") ?: JSONObject()
    val period = root.optJSONObject("period") ?: JSONObject()
    val filters = root.optJSONObject("filters") ?: JSONObject()
    val density = root.optJSONObject("data_density") ?: JSONObject()
    val source = root.optJSONObject("source") ?: JSONObject()
    return NearbySpecies(
        areaId = area.optString("id"),
        areaName = area.optString("name", "Selected area"),
        latitude = area.optNullableDouble("lat"),
        longitude = area.optNullableDouble("lng"),
        radiusKm = area.optInt("radius_km", 10),
        targetDate = period.optString("target_date"),
        periodLabel = period.optString("label"),
        iconicTaxon = filters.optNullableString("iconic_taxon"),
        resultLimit = filters.optInt("result_limit", 50),
        dataDensity = density.optString("level", "normal"),
        dataDensityMessage = density.optString("message"),
        sourceGuidance = source.optString(
            "guidance",
            "Reporting frequency is not a probability of encounter.",
        ),
        fromCache = source.optBoolean("from_cache"),
        progress = parseDiscoveryProgress(root),
        taxa = parseDiscoveryTaxa(root),
    )
}

fun parseFieldQuest(json: String): FieldQuest = parseFieldQuest(JSONObject(json))

fun parseFieldQuests(json: String): List<FieldQuest> {
    val array = JSONArray(json)
    return List(array.length()) { index -> parseFieldQuest(array.getJSONObject(index)) }
}

fun parseQuestSightingsMap(json: String): QuestSightingsMap {
    val root = JSONObject(json)
    val quest = root.optJSONObject("quest") ?: JSONObject()
    val taxon = root.optJSONObject("taxon") ?: JSONObject()
    val source = root.optJSONObject("source") ?: JSONObject()
    val sightings = root.optJSONArray("sightings") ?: JSONArray()
    return QuestSightingsMap(
        questId = quest.optString("id"),
        questTitle = quest.optString("title", "Field Quest"),
        areaName = quest.optString("area_name", "Selected area"),
        latitude = quest.optDouble("lat"),
        longitude = quest.optDouble("lng"),
        radiusKm = quest.optInt("radius_km", 10),
        periodLabel = quest.optString("period_label"),
        taxonId = taxon.optLong("taxon_id"),
        commonName = taxon.optString("common_name", "Unknown species"),
        scientificName = taxon.optString("scientific_name"),
        totalResults = root.optInt("total_results"),
        mappedCount = root.optInt("mapped_count"),
        limited = root.optBoolean("limited"),
        sourceGuidance = source.optString(
            "guidance",
            "Markers use locations iNaturalist makes public.",
        ),
        sightings = List(sightings.length()) { index ->
            val item = sightings.getJSONObject(index)
            QuestSighting(
                id = item.optString("id"),
                latitude = item.optDouble("lat"),
                longitude = item.optDouble("lng"),
                observedOn = item.optString("observed_on"),
                placeGuess = item.optString("place_guess"),
                observer = item.optString("observer"),
                uri = item.optString("uri"),
                photoUrl = item.optString("photo_url"),
                photoAttribution = item.optString("photo_attribution"),
                photoLicenseCode = item.optString("photo_license_code"),
                positionalAccuracyMeters = item.optNullableInt("positional_accuracy_m"),
                obscured = item.optBoolean("obscured"),
            )
        },
    )
}

fun parseSightings(json: String): List<Sighting> {
    val array = JSONArray(json)
    return List(array.length()) { index ->
        val item = array.getJSONObject(index)
        Sighting(
            id = item.optString("id"),
            hikeId = item.optNullableString("hike_id"),
            hikeTitle = item.optString("hike_title", "Everyday sighting"),
            hikeDate = item.optString("hike_date"),
            locationName = item.optString("location_name"),
            url = item.optString("url"),
            caption = item.optString("caption"),
            takenAt = item.optNullableString("taken_at"),
            latitude = item.optDouble("lat"),
            longitude = item.optDouble("lng"),
            speciesName = item.optString("species_name"),
            scientificName = item.optString("scientific_name"),
            confirmed = item.optBoolean("confirmed"),
        )
    }
}

fun parseReviewQueue(json: String): List<ReviewItem> {
    val array = JSONArray(json)
    return List(array.length()) { index -> parseReviewItem(array.getJSONObject(index)) }
}

fun parseReviewBatchResult(json: String): ReviewBatchResult {
    val root = JSONObject(json)
    val items = root.optJSONArray("items") ?: JSONArray()
    val processed = root.optJSONArray("processed_photo_ids") ?: JSONArray()
    val warnings = root.optJSONArray("warnings") ?: JSONArray()
    return ReviewBatchResult(
        items = List(items.length()) { index -> parseReviewItem(items.getJSONObject(index)) },
        processedPhotoIds = List(processed.length()) { index -> processed.optString(index) },
        groupedCount = root.optInt("grouped_count"),
        individualCount = root.optInt("individual_count"),
        warnings = List(warnings.length()) { index -> warnings.optString(index) },
    )
}

fun parseReviewBatchStatus(json: String): ReviewBatchStatus {
    val root = JSONObject(json)
    val processed = root.optJSONArray("processed_photo_ids") ?: JSONArray()
    val warnings = root.optJSONArray("warnings") ?: JSONArray()
    val items = root.optJSONArray("items") ?: JSONArray()
    return ReviewBatchStatus(
        jobId = root.optString("job_id"),
        state = root.optString("state", "queued"),
        totalPhotos = root.optInt("total_photos"),
        processedCount = root.optInt("processed_count", processed.length()),
        processedPhotoIds = List(processed.length()) { index -> processed.optString(index) },
        currentPhotoNumber = root.optInt("current_photo_number"),
        currentPhotoId = root.optNullableString("current_photo_id"),
        totalGroups = root.optInt("total_groups"),
        currentGroup = root.optInt("current_group"),
        groupedCount = root.optInt("grouped_count"),
        individualCount = root.optInt("individual_count"),
        warnings = List(warnings.length()) { index -> warnings.optString(index) },
        error = root.optNullableString("error"),
        items = List(items.length()) { index -> parseReviewItem(items.getJSONObject(index)) },
    )
}

fun parseReviewItem(json: String): ReviewItem = parseReviewItem(JSONObject(json))

private fun parseReviewItem(json: JSONObject): ReviewItem {
    val candidates = json.optJSONArray("candidates") ?: JSONArray()
    return ReviewItem(
        id = json.optString("id"),
        photo = parsePhoto(json.getJSONObject("photo")),
        hikeId = json.optNullableString("hike_id"),
        hikeTitle = json.optString("hike_title", "Everyday sighting"),
        hikeDate = json.optString("hike_date"),
        locationName = json.optString("location_name"),
        state = json.optString("state", "waiting"),
        observationId = json.optNullableString("observation_id"),
        candidates = List(candidates.length()) { candidateIndex ->
            val candidate = candidates.getJSONObject(candidateIndex)
            ReviewCandidate(
                taxonId = candidate.optNullableLong("taxon_id"),
                commonName = candidate.optString("common_name", "Unknown species"),
                scientificName = candidate.optString("scientific_name"),
                confidence = candidate.optNullableDouble("confidence"),
            )
        },
    )
}

fun parsePublishQueue(json: String): PublishQueue {
    val root = JSONObject(json)
    val counts = root.optJSONObject("counts") ?: JSONObject()
    val items = root.optJSONArray("items") ?: JSONArray()
    return PublishQueue(
        connected = root.optBoolean("connected"),
        readyCount = counts.optInt("ready"),
        needsAttentionCount = counts.optInt("needs_attention"),
        postedCount = counts.optInt("posted"),
        items = List(items.length()) { index -> parsePublishItem(items.getJSONObject(index)) },
    )
}

fun parsePublishItem(json: String): PublishItem = parsePublishItem(JSONObject(json))

private fun parsePublishItem(item: JSONObject): PublishItem = PublishItem(
    id = item.optString("id"),
    photo = parsePhoto(item.getJSONObject("photo")),
    hikeId = item.optNullableString("hike_id"),
    hikeTitle = item.optString("hike_title", "Everyday sighting"),
    hikeDate = item.optString("hike_date"),
    locationName = item.optString("location_name"),
    taxonId = item.optNullableLong("taxon_id"),
    commonName = item.optString("common_name", "Unknown species"),
    scientificName = item.optString("scientific_name"),
    state = item.optString("state", "ready"),
    inatObservationId = item.optNullableLong("inat_observation_id"),
    inatUrl = item.optString("inat_url"),
    postedAt = item.optNullableString("posted_at"),
    photoAttached = item.optNullableBoolean("photo_attached"),
    relatedObservationIds = item.optJSONArray("related_observation_ids")?.let { array ->
        List(array.length()) { index -> array.optString(index) }
    }.orEmpty(),
    relatedPhotoCount = item.optInt("related_photo_count", 1),
)

private fun parseHike(json: JSONObject): Hike {
    val photosJson = json.optJSONArray("photos") ?: JSONArray()
    val routeSegmentsJson = json.optJSONArray("route_segments") ?: JSONArray()
    return Hike(
        id = json.optString("id"),
        title = json.optString("title", "Untitled hike"),
        hikeDate = json.optString("hike_date"),
        distanceMiles = json.optNullableDouble("distance_miles"),
        durationSeconds = json.optNullableLong("duration_seconds"),
        routeStartedAt = json.optNullableString("route_started_at")
            ?: json.optNullableString("started_at"),
        locationName = json.optString("location_name"),
        notes = json.optString("notes"),
        isArchived = json.optBoolean("is_archived"),
        isStandalone = json.optBoolean("is_standalone"),
        coverUrl = json.optString("cover_url"),
        coverPhotoId = json.optNullableString("cover_photo_id"),
        photoCount = json.optInt("photo_count"),
        speciesCount = json.optInt("species_count"),
        syncState = json.optString("sync_state", "synced"),
        photos = List(photosJson.length()) { index -> parsePhoto(photosJson.getJSONObject(index)) },
        routeSegments = List(routeSegmentsJson.length()) { segmentIndex ->
            val segment = routeSegmentsJson.optJSONArray(segmentIndex) ?: JSONArray()
            List(segment.length()) { pointIndex ->
                val point = segment.getJSONObject(pointIndex)
                RoutePoint(
                    latitude = point.optDouble("lat"),
                    longitude = point.optDouble("lng"),
                )
            }
        }.filter { it.size >= 2 },
    )
}

private fun parsePhoto(json: JSONObject): Photo {
    val speciesJson = json.optJSONArray("species") ?: JSONArray()
    return Photo(
        id = json.optString("id"),
        hikeId = json.optNullableString("hike_id"),
        url = json.optString("url"),
        caption = json.optString("caption"),
        takenAt = json.optNullableString("taken_at"),
        createdAt = json.optNullableString("created_at"),
        latitude = json.optNullableDouble("lat"),
        longitude = json.optNullableDouble("lng"),
        width = json.optNullableInt("width"),
        height = json.optNullableInt("height"),
        contentType = json.optString("content_type", "image/jpeg"),
        processingStatus = json.optString("processing_status", "ready"),
        syncState = json.optString("sync_state", "synced"),
        species = List(speciesJson.length()) { index ->
            val item = speciesJson.getJSONObject(index)
            SpeciesLabel(
                commonName = item.optString("common_name"),
                scientificName = item.optString("scientific_name"),
                status = item.optString("status"),
                isPrimary = item.optBoolean("is_primary"),
                taxonId = item.optNullableLong("taxon_id"),
                wikipediaUrl = item.optString("wikipedia_url"),
                wikipediaSummary = plainWikipediaSummary(item.optString("wikipedia_summary")),
            )
        },
    )
}

private fun parseSpecies(json: JSONObject): SpeciesRecord {
    val encountersJson = json.optJSONArray("encounters") ?: JSONArray()
    return SpeciesRecord(
        key = json.optString("key"),
        taxonId = json.optNullableLong("taxon_id"),
        commonName = json.optString("common_name", "Unknown species"),
        scientificName = json.optString("scientific_name"),
        rank = json.optString("rank"),
        iconicTaxonName = json.optString("iconic_taxon_name", "Other"),
        wikipediaUrl = json.optString("wikipedia_url"),
        wikipediaSummary = plainWikipediaSummary(json.optString("wikipedia_summary")),
        encounterCount = json.optInt("encounter_count"),
        hikeCount = json.optInt("hike_count"),
        hikeIds = json.optJSONArray("hike_ids")?.let { array ->
            List(array.length()) { index -> array.optString(index) }
        }.orEmpty(),
        hikeEncounterCounts = json.optJSONObject("hike_encounter_counts")?.let { counts ->
            counts.keys().asSequence().associateWith { hikeId -> counts.optInt(hikeId) }
        }.orEmpty(),
        hikeCoverUrls = json.optJSONObject("hike_cover_urls")?.let { urls ->
            urls.keys().asSequence().associateWith { hikeId -> urls.optString(hikeId) }
        }.orEmpty(),
        hikeLatestSeen = json.optJSONObject("hike_latest_seen")?.let { dates ->
            dates.keys().asSequence().associateWith { hikeId -> dates.optString(hikeId) }
        }.orEmpty(),
        latestSeen = json.optNullableString("latest_seen"),
        coverUrl = json.optString("cover_url"),
        encounters = List(encountersJson.length()) { index ->
            val encounter = encountersJson.getJSONObject(index)
            Encounter(
                photo = parsePhoto(encounter.getJSONObject("photo")),
                hikeId = encounter.optNullableString("hike_id"),
                hikeTitle = encounter.optString("hike_title", "Everyday sighting"),
                hikeDate = encounter.optString("hike_date"),
                locationName = encounter.optString("location_name"),
                observedOn = encounter.optNullableString("observed_on"),
            )
        },
    )
}

internal fun plainWikipediaSummary(value: String): String = value
    .replace(Regex("<[^>]*>"), " ")
    .replace("&nbsp;", " ")
    .replace("&amp;", "&")
    .replace("&quot;", "\"")
    .replace("&#39;", "'")
    .replace(Regex("\\s+"), " ")
    .trim()

private fun parseFieldQuest(root: JSONObject): FieldQuest {
    val area = root.optJSONObject("area") ?: JSONObject()
    val period = root.optJSONObject("period") ?: JSONObject()
    val filters = root.optJSONObject("filters") ?: JSONObject()
    return FieldQuest(
        id = root.optString("id"),
        title = root.optString("title", "Field Quest"),
        status = root.optString("status", "active"),
        linkedHikeId = root.optNullableString("linked_hike_id"),
        areaId = area.optString("id"),
        areaName = area.optString("name", "Selected area"),
        latitude = area.optNullableDouble("lat"),
        longitude = area.optNullableDouble("lng"),
        radiusKm = area.optInt("radius_km", 10),
        targetDate = period.optString("target_date"),
        periodLabel = period.optString("label"),
        iconicTaxon = filters.optNullableString("iconic_taxon"),
        progress = parseDiscoveryProgress(root),
        taxa = parseDiscoveryTaxa(root),
    )
}

private fun parseDiscoveryProgress(root: JSONObject): DiscoveryProgress {
    val progress = root.optJSONObject("progress") ?: JSONObject()
    return DiscoveryProgress(
        collectedCount = progress.optInt("collected_count"),
        totalCount = progress.optInt("total_count"),
        remainingCount = progress.optInt("remaining_count"),
    )
}

private fun parseDiscoveryTaxa(root: JSONObject): List<DiscoveryTaxon> {
    val taxa = root.optJSONArray("taxa") ?: JSONArray()
    return List(taxa.length()) { index ->
        val item = taxa.getJSONObject(index)
        val photo = item.optJSONObject("reference_photo")
        DiscoveryTaxon(
            taxonId = item.optLong("taxon_id"),
            commonName = item.optString("common_name", "Unknown species"),
            scientificName = item.optString("scientific_name"),
            iconicTaxonName = item.optString("iconic_taxon_name", "Other"),
            observationCount = item.optInt("observation_count"),
            nearbyRank = item.optInt("nearby_rank", index + 1),
            frequencyBand = item.optString("frequency_band", "Less often reported"),
            referencePhoto = photo?.optString("url")?.takeIf { it.isNotBlank() }?.let { url ->
                DiscoveryPhoto(
                    url = url,
                    attribution = photo.optString("attribution"),
                    licenseCode = photo.optString("license_code"),
                )
            },
            collected = item.optBoolean("collected"),
            collectedAt = item.optNullableString("collected_at"),
            collectionPhotoUrl = item.optNullableString("collection_photo_url"),
            wikipediaUrl = item.optString("wikipedia_url"),
            wikipediaSummary = item.optString("wikipedia_summary"),
            matchReason = item.optString("match_reason"),
            focusOrder = item.optNullableInt("focus_order"),
            pendingCredit = item.optBoolean("pending_credit"),
        )
    }
}

private fun JSONObject.optNullableString(key: String): String? =
    if (!has(key) || isNull(key)) null else optString(key).takeIf { it.isNotBlank() }

private fun JSONObject.optNullableDouble(key: String): Double? =
    if (!has(key) || isNull(key)) null else optDouble(key).takeUnless { it.isNaN() }

private fun JSONObject.optNullableInt(key: String): Int? =
    if (!has(key) || isNull(key)) null else optInt(key)

private fun JSONObject.optNullableLong(key: String): Long? =
    if (!has(key) || isNull(key)) null else optLong(key)

private fun JSONObject.optNullableBoolean(key: String): Boolean? =
    if (!has(key) || isNull(key)) null else optBoolean(key)
