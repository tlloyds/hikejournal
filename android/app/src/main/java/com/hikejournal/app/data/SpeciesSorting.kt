package com.hikejournal.app.data

import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.util.Locale

enum class SpeciesSort(val label: String) {
    Alphabetical("Alphabetical"),
    MostEncountered("Most encountered"),
    MostRecent("Most recent"),
}

private val alphabeticalSpeciesComparator = compareBy<SpeciesRecord>(
    { it.commonName.lowercase(Locale.ROOT) },
    { it.scientificName.lowercase(Locale.ROOT) },
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
