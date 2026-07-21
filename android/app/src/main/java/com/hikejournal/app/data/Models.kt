package com.hikejournal.app.data

import org.json.JSONArray
import org.json.JSONObject

data class Hike(
    val id: String,
    val title: String,
    val hikeDate: String,
    val distanceMiles: Double?,
    val locationName: String,
    val notes: String,
    val isArchived: Boolean,
    val coverUrl: String,
    val photoCount: Int,
    val speciesCount: Int,
    val syncState: String = "synced",
    val photos: List<Photo> = emptyList(),
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
    val processingStatus: String,
    val syncState: String = "synced",
    val species: List<SpeciesLabel>,
)

data class SpeciesLabel(
    val commonName: String,
    val scientificName: String,
    val status: String,
    val isPrimary: Boolean,
)

data class HikeDraft(
    val title: String,
    val hikeDate: String,
    val distanceMiles: Double?,
    val locationName: String,
    val notes: String,
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
    val latestSeen: String?,
    val coverUrl: String,
    val encounters: List<Encounter> = emptyList(),
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
)

data class PublishQueue(
    val connected: Boolean,
    val readyCount: Int,
    val needsAttentionCount: Int,
    val postedCount: Int,
    val items: List<PublishItem>,
)

data class LoadResult<T>(val value: T, val fromCache: Boolean)

fun parseHikes(json: String): List<Hike> {
    val array = JSONArray(json)
    return List(array.length()) { index -> parseHike(array.getJSONObject(index)) }
}

fun parseHike(json: String): Hike = parseHike(JSONObject(json))

fun parseSpeciesList(json: String): List<SpeciesRecord> {
    val array = JSONArray(json)
    return List(array.length()) { index -> parseSpecies(array.getJSONObject(index)) }
}

fun parseSpecies(json: String): SpeciesRecord = parseSpecies(JSONObject(json))

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
    return Hike(
        id = json.optString("id"),
        title = json.optString("title", "Untitled hike"),
        hikeDate = json.optString("hike_date"),
        distanceMiles = json.optNullableDouble("distance_miles"),
        locationName = json.optString("location_name"),
        notes = json.optString("notes"),
        isArchived = json.optBoolean("is_archived"),
        coverUrl = json.optString("cover_url"),
        photoCount = json.optInt("photo_count"),
        speciesCount = json.optInt("species_count"),
        syncState = json.optString("sync_state", "synced"),
        photos = List(photosJson.length()) { index -> parsePhoto(photosJson.getJSONObject(index)) },
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
        processingStatus = json.optString("processing_status", "ready"),
        syncState = json.optString("sync_state", "synced"),
        species = List(speciesJson.length()) { index ->
            val item = speciesJson.getJSONObject(index)
            SpeciesLabel(
                commonName = item.optString("common_name"),
                scientificName = item.optString("scientific_name"),
                status = item.optString("status"),
                isPrimary = item.optBoolean("is_primary"),
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
        wikipediaSummary = json.optString("wikipedia_summary"),
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
