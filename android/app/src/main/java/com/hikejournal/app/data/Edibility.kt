package com.hikejournal.app.data

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit
import org.json.JSONObject
import java.net.URI
import java.time.Instant

enum class FoodUseStatus { Documented, Conditional, Disputed, Unknown }
enum class ToxicityStatus { DocumentedConcern, Unknown }

enum class FoodUseIndicator(val label: String, val warning: Boolean) {
    FoodUses("Food uses", false),
    Conditional("Conditional food use", true),
    Toxicity("Toxicity concerns", true),
    Conflict("Conflicting evidence", true),
}

data class FoodUseSource(
    val title: String,
    val version: String,
    val url: String,
    val attribution: String,
    val publisher: String,
    val license: String,
    val licenseUrl: String?,
    val modifications: String,
)

data class EdibilityReference(
    val taxonId: Long,
    val scientificName: String,
    val rank: String,
    val datasetVersion: String,
    val foodUse: FoodUseStatus,
    val toxicity: ToxicityStatus,
    val evidenceConflict: Boolean,
    val hasDocumentedFoodUse: Boolean,
    val documentedParts: List<String>,
    val foodUseNotes: String?,
    val toxicityNotes: String?,
    val sources: List<FoodUseSource>,
    val expiresAt: Instant,
    val reviewed: Boolean,
) {
    val indicator: FoodUseIndicator?
        get() = when {
            toxicity == ToxicityStatus.DocumentedConcern -> FoodUseIndicator.Toxicity
            evidenceConflict || foodUse == FoodUseStatus.Disputed -> FoodUseIndicator.Conflict
            foodUse == FoodUseStatus.Conditional -> FoodUseIndicator.Conditional
            foodUse == FoodUseStatus.Documented -> FoodUseIndicator.FoodUses
            else -> null
        }

    fun currentFor(
        id: Long?,
        name: String,
        taxonomicRank: String = "",
        now: Instant = Instant.now(),
    ): EdibilityReference? = takeIf {
        id == taxonId && now.isBefore(expiresAt) &&
            name.trim().replace(Whitespace, " ").equals(scientificName, ignoreCase = true) &&
            (taxonomicRank.isBlank() || rank.equals(taxonomicRank, ignoreCase = true))
    }
}

private val Whitespace = Regex("\\s+")
private val supportedRanks = setOf("species", "subspecies", "variety", "form")

internal fun parseEdibility(json: JSONObject?): EdibilityReference? {
    json ?: return null
    val taxonId = json.optLong("taxon_id").takeIf { it > 0 } ?: return null
    val name = json.nonblank("scientific_name")?.replace(Whitespace, " ") ?: return null
    val version = json.nonblank("dataset_version") ?: return null
    val rank = json.optString("rank").takeIf { it in supportedRanks } ?: return null
    val review = json.optString("review_status")
    if (review != "source_matched" && review != "reviewed") return null
    val expiresAt = runCatching { Instant.parse(json.optString("expires_at")) }.getOrNull() ?: return null
    val items = json.optJSONArray("sources") ?: return null
    val sources = (0 until items.length()).mapNotNull { index ->
        val source = items.optJSONObject(index) ?: return@mapNotNull null
        FoodUseSource(
            title = source.nonblank("title") ?: return@mapNotNull null,
            version = source.nonblank("version") ?: return@mapNotNull null,
            url = source.httpsUrl("url") ?: return@mapNotNull null,
            attribution = source.nonblank("attribution") ?: return@mapNotNull null,
            publisher = source.nonblank("publisher").orEmpty(),
            license = source.nonblank("license") ?: return@mapNotNull null,
            licenseUrl = source.httpsUrl("license_url"),
            modifications = source.nonblank("modifications").orEmpty(),
        )
    }
    if (sources.isEmpty()) return null
    val foodUse = when (json.optString("food_use_status")) {
        "documented" -> FoodUseStatus.Documented
        "conditional" -> FoodUseStatus.Conditional
        "disputed" -> FoodUseStatus.Disputed
        else -> FoodUseStatus.Unknown
    }
    val parts = json.optJSONArray("documented_parts")
    return EdibilityReference(
        taxonId = taxonId,
        scientificName = name,
        rank = rank,
        datasetVersion = version,
        foodUse = foodUse,
        toxicity = if (json.optString("toxicity_status") == "documented_concern") {
            ToxicityStatus.DocumentedConcern
        } else {
            ToxicityStatus.Unknown
        },
        evidenceConflict = json.optBoolean("evidence_conflict"),
        hasDocumentedFoodUse = foodUse == FoodUseStatus.Documented || foodUse == FoodUseStatus.Conditional ||
            (foodUse == FoodUseStatus.Disputed && json.optBoolean("has_documented_food_use")),
        documentedParts = if (parts == null) emptyList() else
            (0 until parts.length()).mapNotNull { (parts.opt(it) as? String)?.trim()?.takeIf(String::isNotEmpty) },
        foodUseNotes = json.nonblank("food_use_notes"),
        toxicityNotes = json.nonblank("toxicity_notes"),
        sources = sources,
        expiresAt = expiresAt,
        reviewed = review == "reviewed",
    )
}

private fun JSONObject.nonblank(key: String): String? =
    (opt(key) as? String)?.trim()?.takeIf(String::isNotEmpty)

private fun JSONObject.httpsUrl(key: String): String? = nonblank(key)?.takeIf { value ->
    runCatching { URI(value).let { it.scheme == "https" && !it.host.isNullOrBlank() } }.getOrDefault(false)
}

internal fun SpeciesRecord.currentEdibility(now: Instant = Instant.now()): EdibilityReference? =
    edibility?.currentFor(taxonId, scientificName, rank, now)

internal fun SpeciesRecord.showsEdibilityReference(currentDatasetVersion: String?): Boolean =
    edibilityReferenceEnabled && (currentDatasetVersion == null || edibilityDatasetVersion == currentDatasetVersion)

internal fun SpeciesLabel.currentEdibility(now: Instant = Instant.now()): EdibilityReference? =
    if (status == "confirmed" && !observationId.isNullOrBlank() &&
        (iconicTaxonName.isBlank() || iconicTaxonName.equals("Plantae", true) || iconicTaxonName.equals("Other", true))
    ) edibility?.currentFor(taxonId, scientificName, now = now) else null

internal fun Photo.foodUseTags(
    show: Boolean,
    identityChangedAt: Long,
    now: Instant = Instant.now(),
    currentDatasetVersion: String? = null,
): List<Pair<SpeciesLabel, EdibilityReference>> {
    if (!show || isVideo || syncState != "synced" || edibilityReadStartedAt <= identityChangedAt) return emptyList()
    return species.mapNotNull { tag ->
        tag.currentEdibility(now)?.takeIf {
            it.indicator != null && (currentDatasetVersion == null || it.datasetVersion == currentDatasetVersion)
        }?.let { tag to it }
    }
}

internal class FoodUsePreferences(context: Context) {
    private val display = context.applicationContext.getSharedPreferences("hikejournal_food_use", Context.MODE_PRIVATE)
    private val referenceState = context.applicationContext.getSharedPreferences("hikejournal_sync", Context.MODE_PRIVATE)

    var showPhotoIndicators: Boolean
        get() = display.getBoolean("show_photo_indicators", false)
        set(value) = display.edit { putBoolean("show_photo_indicators", value) }

    fun identityChangedAt(photoId: String): Long = referenceState.getLong(identityKey(photoId), 0)

    // In-flight journal reads carry their local start time through the JSON
    // cache. An earlier response remains ineligible even if it arrives later.
    fun invalidatePhotoIdentity(photoId: String) {
        referenceState.edit { putLong(identityKey(photoId), System.currentTimeMillis()) }
    }

    // Empty means a refreshed server explicitly has no active references.
    fun datasetVersion(): String? = referenceState.getString(DatasetVersionKey, null)

    fun recordDatasetVersion(version: String?, readStartedAt: Long) = synchronized(VersionLock) {
        if (readStartedAt > referenceState.getLong(DatasetReadStartedAtKey, 0)) {
            referenceState.edit {
                putLong(DatasetReadStartedAtKey, readStartedAt)
                putString(DatasetVersionKey, version.orEmpty())
            }
        }
    }

    fun observeDatasetVersion(onChange: () -> Unit): () -> Unit =
        observeReferenceState(DatasetVersionKey, onChange)

    fun observePhotoIdentity(photoId: String, onChange: () -> Unit): () -> Unit =
        observeReferenceState(identityKey(photoId), onChange)

    private fun observeReferenceState(key: String, onChange: () -> Unit): () -> Unit {
        val listener = SharedPreferences.OnSharedPreferenceChangeListener { _, changed ->
            if (changed == key || changed == null) onChange()
        }
        referenceState.registerOnSharedPreferenceChangeListener(listener)
        return { referenceState.unregisterOnSharedPreferenceChangeListener(listener) }
    }

    private fun identityKey(photoId: String) = "food_use_identity_$photoId"

    private companion object {
        val VersionLock = Any()
        const val DatasetVersionKey = "food_use_dataset_version"
        const val DatasetReadStartedAtKey = "food_use_dataset_read_started_at"
    }
}

internal const val EdibilityReadStartedAt = "local_android_edibility_read_started_at"

internal fun JSONObject.edibilityDatasetVersion(): String? = nonblank("edibility_dataset_version")
