package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class SpeciesSortingTest {
    @Test
    fun `alphabetical sort ignores case`() {
        val records = listOf(
            species("zebra longwing"),
            species("Apple snail"),
            species("anhinga"),
        )

        assertEquals(
            listOf("anhinga", "Apple snail", "zebra longwing"),
            sortSpeciesRecords(records, SpeciesSort.Alphabetical).map { it.commonName },
        )
    }

    @Test
    fun `most encountered uses alphabetical tie break`() {
        val records = listOf(
            species("Zebra longwing", encounterCount = 2),
            species("Anhinga", encounterCount = 5),
            species("Apple snail", encounterCount = 5),
        )

        assertEquals(
            listOf("Anhinga", "Apple snail", "Zebra longwing"),
            sortSpeciesRecords(records, SpeciesSort.MostEncountered).map { it.commonName },
        )
    }

    @Test
    fun `newest uses latest seen with missing dates last and alphabetical tie breaks`() {
        val records = listOf(
            species("Zebra longwing", latestSeen = "2026-07-28T12:00:00Z"),
            species("Anhinga", latestSeen = "2026-07-30"),
            species("Apple snail", latestSeen = "2026-07-28T12:00:00Z"),
            species("Blank date", latestSeen = "  "),
            species("Missing date", latestSeen = null),
        )

        assertEquals(
            listOf("Anhinga", "Apple snail", "Zebra longwing", "Blank date", "Missing date"),
            sortSpeciesRecords(records, SpeciesSort.MostRecent).map { it.commonName },
        )
    }

    @Test
    fun `newest compares instants across timezone offsets`() {
        val records = listOf(
            species("Local next day", latestSeen = "2026-07-30T00:30:00+02:00"),
            species("Later UTC instant", latestSeen = "2026-07-29T23:00:00Z"),
        )

        assertEquals(
            listOf("Later UTC instant", "Local next day"),
            sortSpeciesRecords(records, SpeciesSort.MostRecent).map { it.commonName },
        )
    }

    private fun species(
        commonName: String,
        encounterCount: Int = 1,
        latestSeen: String? = null,
    ) = SpeciesRecord(
        key = commonName,
        taxonId = null,
        commonName = commonName,
        scientificName = commonName,
        rank = "species",
        iconicTaxonName = "Other",
        wikipediaUrl = "",
        wikipediaSummary = "",
        encounterCount = encounterCount,
        hikeCount = 1,
        hikeIds = emptyList(),
        hikeEncounterCounts = emptyMap(),
        hikeCoverUrls = emptyMap(),
        hikeLatestSeen = emptyMap(),
        latestSeen = latestSeen,
        coverUrl = "",
    )
}
