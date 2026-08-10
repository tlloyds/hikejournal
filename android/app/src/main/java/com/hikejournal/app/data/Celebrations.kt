package com.hikejournal.app.data

import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeParseException
import java.util.Locale

enum class CelebrationKind { Identification, Discovery, Rediscovery, Milestone }

data class CelebrationHighlight(
    val value: String,
    val label: String,
)

data class FieldCelebration(
    val id: String,
    val kind: CelebrationKind,
    val eyebrow: String,
    val title: String,
    val detail: String,
    val imageUrls: List<String> = emptyList(),
    val highlights: List<CelebrationHighlight> = emptyList(),
    val badgeTitle: String? = null,
    val badgeProgress: String? = null,
    val actionLabel: String = "Continue",
)

private fun speciesIdentity(taxonId: Long?, scientificName: String, commonName: String): String =
    taxonId?.let { "taxon:$it" }
        ?: scientificName.trim().takeIf(String::isNotBlank)?.lowercase(Locale.US)?.let { "scientific:$it" }
        ?: "common:${commonName.trim().lowercase(Locale.US)}"

private fun SpeciesRecord.identity(): String = speciesIdentity(taxonId, scientificName, commonName)
private fun ReviewCandidate.identity(): String = speciesIdentity(taxonId, scientificName, commonName)

private fun parseObservedInstant(value: String?): Instant? {
    val raw = value?.trim().orEmpty()
    if (raw.isBlank()) return null
    return try {
        Instant.parse(raw)
    } catch (_: DateTimeParseException) {
        try {
            LocalDate.parse(raw.take(10)).atStartOfDay().toInstant(ZoneOffset.UTC)
        } catch (_: DateTimeParseException) {
            null
        }
    }
}

private fun lifeGroupLabel(iconicTaxonName: String): String = when (iconicTaxonName.lowercase(Locale.US)) {
    "plantae", "plant" -> "plants"
    "aves", "bird" -> "birds"
    "mammalia", "mammal" -> "mammals"
    "insecta", "insect" -> "insects"
    "fungi", "fungus" -> "fungi"
    "reptilia" -> "reptiles"
    "amphibia" -> "amphibians"
    "arachnida" -> "arachnids"
    "actinopterygii" -> "fish"
    "mollusca" -> "mollusks"
    else -> "species"
}

fun buildReviewBatchCelebration(
    status: ReviewBatchStatus,
    existingSpecies: List<SpeciesRecord>,
): FieldCelebration? {
    if (status.processedCount <= 0) return null
    val suggestions = status.items
        .mapNotNull { item -> item.candidates.firstOrNull()?.let { candidate -> item to candidate } }
        .distinctBy { (_, candidate) -> candidate.identity() }
    val known = existingSpecies.mapTo(mutableSetOf()) { it.identity() }
    val possibleNew = suggestions.filter { (_, candidate) -> candidate.identity() !in known }
    val typeCounts = possibleNew
        .groupingBy { (_, candidate) -> lifeGroupLabel(candidate.iconicTaxonName) }
        .eachCount()
        .filterKeys { it != "species" }
    val typeDetail = typeCounts.entries
        .sortedByDescending { it.value }
        .take(2)
        .joinToString(" · ") { (name, count) -> "$count $name" }
    val title = when {
        possibleNew.size == 1 -> "A possible new species"
        possibleNew.isNotEmpty() -> "${possibleNew.size} possible new species"
        suggestions.size == 1 -> "An identification is ready"
        suggestions.isNotEmpty() -> "${suggestions.size} identifications are ready"
        else -> "Identification batch complete"
    }
    val detail = buildString {
        append("Review the suggestions to add confirmed finds to your Field Guide.")
        if (typeDetail.isNotBlank()) append(" $typeDetail are new possibilities in this batch.")
        status.warnings.firstOrNull()?.let { append(" $it") }
    }
    return FieldCelebration(
        id = "batch:${status.jobId}",
        kind = CelebrationKind.Identification,
        eyebrow = "THE FIELD NOTES ARE IN",
        title = title,
        detail = detail,
        imageUrls = status.items.map { it.photo.url }.filter(String::isNotBlank).distinct().take(3),
        highlights = listOf(
            CelebrationHighlight(status.processedCount.toString(), "photos read"),
            CelebrationHighlight(suggestions.size.toString(), "unique IDs"),
            CelebrationHighlight(possibleNew.size.toString(), "possible new"),
        ),
        actionLabel = "Review discoveries",
    )
}

private fun nextFieldGuideBadge(total: Int): TrailBadgeDefinition? = TrailBadgeCatalog
    .filter { it.metric == BadgeMetric.SpeciesCount && it.target > total }
    .minByOrNull { it.target }

private fun unlockedFieldGuideBadge(before: Int, after: Int): TrailBadgeDefinition? = TrailBadgeCatalog
    .filter { it.metric == BadgeMetric.SpeciesCount && before < it.target && after >= it.target }
    .maxByOrNull { it.target }

fun buildConfirmedSpeciesCelebration(
    candidate: ReviewCandidate,
    photo: Photo,
    observedOn: String?,
    existingSpecies: List<SpeciesRecord>,
): FieldCelebration? {
    val existing = existingSpecies.firstOrNull { it.identity() == candidate.identity() }
    if (existing == null) {
        val before = existingSpecies.distinctBy { it.identity() }.size
        val after = before + 1
        val unlocked = unlockedFieldGuideBadge(before, after)
        val next = nextFieldGuideBadge(after)
        val group = lifeGroupLabel(candidate.iconicTaxonName)
        return FieldCelebration(
            id = "species:${candidate.identity()}:${photo.id}",
            kind = CelebrationKind.Discovery,
            eyebrow = "NEW TO YOUR FIELD GUIDE",
            title = candidate.commonName.ifBlank { candidate.scientificName.ifBlank { "New species" } },
            detail = "Your first confirmed $group record is now part of your living archive.",
            imageUrls = listOf(photo.url).filter(String::isNotBlank),
            highlights = listOf(
                CelebrationHighlight(after.toString(), "species logged"),
                CelebrationHighlight(group.replaceFirstChar(Char::titlecase), "life group"),
            ),
            badgeTitle = unlocked?.title,
            badgeProgress = when {
                unlocked != null -> unlocked.requirement
                next != null -> "$after / ${next.target.toInt()} · ${next.title}"
                else -> "$after species in your Field Guide"
            },
        )
    }

    val previous = parseObservedInstant(existing.latestSeen)
    val current = parseObservedInstant(observedOn ?: photo.takenAt ?: photo.createdAt)
    val days = if (previous != null && current != null && current.isAfter(previous)) {
        Duration.between(previous, current).toDays()
    } else {
        0
    }
    if (days < 60) return null
    return FieldCelebration(
        id = "return:${existing.identity()}:${photo.id}",
        kind = CelebrationKind.Rediscovery,
        eyebrow = "WELCOME BACK",
        title = existing.commonName.ifBlank { existing.scientificName },
        detail = "Your first confirmed sighting of this species in $days days.",
        imageUrls = listOf(photo.url.ifBlank { existing.coverUrl }).filter(String::isNotBlank),
        highlights = listOf(
            CelebrationHighlight(days.toString(), "days apart"),
            CelebrationHighlight((existing.encounterCount + 1).toString(), "encounters"),
        ),
    )
}

fun buildKnownSpeciesRediscoveryCelebration(
    species: SpeciesRecord,
    photo: Photo,
): FieldCelebration? = buildConfirmedSpeciesCelebration(
    candidate = ReviewCandidate(
        taxonId = species.taxonId,
        commonName = species.commonName,
        scientificName = species.scientificName,
        confidence = null,
        iconicTaxonName = species.iconicTaxonName,
    ),
    photo = photo,
    observedOn = photo.takenAt ?: photo.createdAt,
    existingSpecies = listOf(species),
)

private fun ordinal(value: Int): String {
    val suffix = if (value % 100 in 11..13) "th" else when (value % 10) {
        1 -> "st"
        2 -> "nd"
        3 -> "rd"
        else -> "th"
    }
    return "$value$suffix"
}

fun buildHikeMilestoneCelebration(
    previousHikes: List<Hike>,
    updatedHikes: List<Hike>,
    savedHike: Hike,
): FieldCelebration? {
    if (savedHike.isStandalone || previousHikes.any { it.id == savedHike.id }) return null
    val before = calculateTrailBadges(previousHikes, emptyList(), emptyList())
    val after = calculateTrailBadges(updatedHikes, emptyList(), emptyList())
    val newlyEarned = after.filter { badge ->
        badge.earned && before.firstOrNull { it.definition.id == badge.definition.id }?.earned != true
    }
    val hikeBadge = newlyEarned
        .filter { it.definition.metric == BadgeMetric.HikeCount }
        .maxByOrNull { it.definition.target }
        ?: return null
    val hikeCount = updatedHikes.count { !it.isStandalone }
    val miles = updatedHikes.filterNot { it.isStandalone }.sumOf { it.distanceMiles ?: 0.0 }
    return FieldCelebration(
        id = "hike:${savedHike.id}:$hikeCount",
        kind = CelebrationKind.Milestone,
        eyebrow = "TRAIL MILESTONE",
        title = if (hikeCount == 1) "First hike logged!" else "${ordinal(hikeCount)} hike logged!",
        detail = "${savedHike.title.ifBlank { "This outing" }} earned a new trail badge.",
        imageUrls = listOf(savedHike.coverUrl).filter(String::isNotBlank),
        highlights = listOf(
            CelebrationHighlight(hikeCount.toString(), "hikes logged"),
            CelebrationHighlight(String.format(Locale.US, "%.1f", miles), "lifetime miles"),
        ),
        badgeTitle = hikeBadge.definition.title,
        badgeProgress = hikeBadge.definition.requirement,
    )
}
