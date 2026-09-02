package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SpeciesFiltersTest {
    private val species = listOf(
        species("Milkweed", "Plantae"),
        species("Wood stork", "Aves"),
        species("Bobcat", "Mammalia"),
        species("Monarch", "Insecta"),
        species("Slime mold", "Protozoa"),
    )

    @Test
    fun `specific filters use iconic taxonomy`() {
        assertEquals(
            listOf("Wood stork"),
            filterSpeciesByObservationType(species, ObservationTypeFilter.Birds).map { it.commonName },
        )
        assertEquals(
            listOf("Milkweed"),
            filterSpeciesByObservationType(species, ObservationTypeFilter.Plants).map { it.commonName },
        )
        assertEquals(
            listOf("Monarch"),
            filterSpeciesByObservationType(species, ObservationTypeFilter.Insects).map { it.commonName },
        )
    }

    @Test
    fun `animals includes specific animal branches and other life catches the remainder`() {
        assertEquals(
            listOf("Wood stork", "Bobcat", "Monarch"),
            filterSpeciesByObservationType(species, ObservationTypeFilter.Animals).map { it.commonName },
        )
        assertEquals(
            listOf("Slime mold"),
            filterSpeciesByObservationType(species, ObservationTypeFilter.OtherLife).map { it.commonName },
        )
        assertTrue(filterSpeciesByObservationType(species, ObservationTypeFilter.All) === species)
    }

    @Test
    fun `species search matches wikipedia descriptions`() {
        val searchable = listOf(
            species("Ghost orchid", "Plantae", wikipediaSummary = "A rare orchid found in damp forests."),
            species("Dune sunflower", "Plantae", wikipediaSummary = "A sandy coastal wildflower."),
            species("Wood stork", "Aves", wikipediaSummary = "A wading bird."),
        )

        assertEquals(
            listOf("Ghost orchid"),
            filterSpeciesBySearch(searchable, "orchid").map { it.commonName },
        )
        assertEquals(
            listOf("Dune sunflower"),
            filterSpeciesBySearch(searchable, "SANDY").map { it.commonName },
        )
        assertTrue(filterSpeciesBySearch(searchable, " ") === searchable)
    }

    private fun species(
        commonName: String,
        iconicTaxonName: String,
        wikipediaSummary: String = "",
    ) = SpeciesRecord(
        key = commonName,
        taxonId = null,
        commonName = commonName,
        scientificName = "",
        rank = "species",
        iconicTaxonName = iconicTaxonName,
        wikipediaUrl = "",
        wikipediaSummary = wikipediaSummary,
        encounterCount = 1,
        hikeCount = 1,
        hikeIds = emptyList(),
        hikeEncounterCounts = emptyMap(),
        hikeCoverUrls = emptyMap(),
        hikeLatestSeen = emptyMap(),
        latestSeen = null,
        coverUrl = "",
    )
}
