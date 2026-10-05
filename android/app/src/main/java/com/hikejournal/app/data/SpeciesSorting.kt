package com.hikejournal.app.data

import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.util.Locale

enum class SpeciesSort(val label: String) {
    Alphabetical("Common name"),
    ScientificName("Scientific name"),
    MostEncountered("Most encountered"),
    MostRecent("Most recent"),
}

data class SpeciesJumpTarget(val label: String, val speciesIndex: Int)

private const val QuickJumpMinimumSpecies = 30

fun speciesJumpTargets(species: List<SpeciesRecord>, sort: SpeciesSort): List<SpeciesJumpTarget> {
    if (species.size < QuickJumpMinimumSpecies) return emptyList()
    return when (sort) {
        SpeciesSort.Alphabetical, SpeciesSort.ScientificName -> {
            val seen = mutableSetOf<String>()
            species.mapIndexedNotNull { index, record ->
                val name = if (sort == SpeciesSort.ScientificName) record.scientificName else record.commonName
                val initial = name.trim().firstOrNull()?.uppercaseChar()?.toString() ?: "#"
                if (seen.add(initial)) SpeciesJumpTarget(initial, index) else null
            }
        }
        SpeciesSort.MostEncountered, SpeciesSort.MostRecent ->
            (0..4).map { step ->
                val index = (species.lastIndex * step + 2) / 4
                SpeciesJumpTarget("${index + 1}", index)
            }
    }
}

private val alphabeticalSpeciesComparator = compareBy<SpeciesRecord>(
    { it.commonName.lowercase(Locale.ROOT) },
    { it.scientificName.lowercase(Locale.ROOT) },
    { it.key.lowercase(Locale.ROOT) },
)

private val scientificNameSpeciesComparator = compareBy<SpeciesRecord>(
    { it.scientificName.lowercase(Locale.ROOT) },
    { it.commonName.lowercase(Locale.ROOT) },
    { it.key.lowercase(Locale.ROOT) },
)

internal fun observedInstant(value: String?): Instant? {
    val raw = value?.trim().orEmpty()
    if (raw.isEmpty()) return null
    return runCatching { Instant.parse(raw) }.getOrNull()
        ?: runCatching { OffsetDateTime.parse(raw).toInstant() }.getOrNull()
        ?: runCatching { LocalDateTime.parse(raw).toInstant(ZoneOffset.UTC) }.getOrNull()
        ?: runCatching { LocalDate.parse(raw).atStartOfDay().toInstant(ZoneOffset.UTC) }.getOrNull()
}

internal fun latestObservedValue(values: Iterable<String>): String? =
    values.maxByOrNull { observedInstant(it) ?: Instant.MIN }

fun sortSpeciesRecords(
    species: List<SpeciesRecord>,
    sort: SpeciesSort,
): List<SpeciesRecord> = when (sort) {
    SpeciesSort.Alphabetical -> species.sortedWith(alphabeticalSpeciesComparator)
    SpeciesSort.ScientificName -> species.sortedWith(scientificNameSpeciesComparator)
    SpeciesSort.MostEncountered -> species.sortedWith(
        compareByDescending<SpeciesRecord> { it.encounterCount }
            .then(alphabeticalSpeciesComparator),
    )
    SpeciesSort.MostRecent -> species.sortedWith(
        compareBy<SpeciesRecord> { observedInstant(it.latestSeen) == null }
            .thenByDescending { observedInstant(it.latestSeen) }
            .then(alphabeticalSpeciesComparator),
    )
}
