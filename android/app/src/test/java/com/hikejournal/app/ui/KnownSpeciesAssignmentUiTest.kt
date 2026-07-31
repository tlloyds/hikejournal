package com.hikejournal.app.ui

import com.hikejournal.app.data.SpeciesRecord
import org.junit.Assert.assertEquals
import org.junit.Test

class KnownSpeciesAssignmentUiTest {
    @Test
    fun `known species search matches common and scientific names`() {
        val species = listOf(
            species("Gopher tortoise", "Gopherus polyphemus"),
            species("Eastern bluebird", "Sialia sialis"),
        )

        assertEquals(
            listOf("Gopher tortoise"),
            filterKnownSpecies(species, "polyphemus").map { it.commonName },
        )
        assertEquals(
            listOf("Eastern bluebird"),
            filterKnownSpecies(species, "BLUEBIRD").map { it.commonName },
        )
    }

    private fun species(commonName: String, scientificName: String) = SpeciesRecord(
        key = "scientific:$scientificName",
        taxonId = null,
        commonName = commonName,
        scientificName = scientificName,
        rank = "species",
        iconicTaxonName = "Animalia",
        wikipediaUrl = "",
        wikipediaSummary = "",
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
