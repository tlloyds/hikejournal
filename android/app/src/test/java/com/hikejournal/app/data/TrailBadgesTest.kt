package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TrailBadgesTest {
    @Test
    fun `hike count distance and longest day unlock independently`() {
        val hikes = List(10) { index ->
            hike(
                id = "hike-$index",
                miles = if (index == 0) 12.0 else 10.0,
            )
        }
        val badges = calculateTrailBadges(hikes, emptyList(), emptyList())

        assertTrue(badges.named("Trail Regular").earned)
        assertTrue(badges.named("Century Afoot").earned)
        assertTrue(badges.named("Double Digits").earned)
        assertFalse(badges.named("Seasoned Trekker").earned)
        assertFalse(badges.named("Endurance Day").earned)
    }

    @Test
    fun `field guide and specialty medals use distinct species`() {
        val plants = List(25) { index -> species(index.toLong(), "Plantae") }
        val duplicate = plants.first().copy(key = "duplicate-key")
        val badges = calculateTrailBadges(emptyList(), plants + duplicate, emptyList())

        assertEquals(25.0, badges.named("Curious Naturalist").current, 0.0)
        assertTrue(badges.named("Leaf Scout").earned)
        assertFalse(badges.named("Field Botanist").earned)
    }

    @Test
    fun `everyday sightings do not count as a hike milestone`() {
        val everyday = hike(id = "everyday", miles = 0.0).copy(isStandalone = true)

        val badges = calculateTrailBadges(listOf(everyday), emptyList(), emptyList())

        assertEquals(0.0, badges.named("First Footfall").current, 0.0)
        assertFalse(badges.named("First Footfall").earned)
    }

    @Test
    fun `quest requires every selected focus target and deduplicates rare finds`() {
        val completeQuest = parseFieldQuest(questJson("one", firstCollected = true, secondCollected = true))
        val incompleteQuest = parseFieldQuest(questJson("two", firstCollected = true, secondCollected = false))
        val badges = calculateTrailBadges(emptyList(), emptyList(), listOf(completeQuest, incompleteQuest))

        assertEquals(1.0, badges.named("Quest Complete").current, 0.0)
        assertTrue(badges.named("Quest Complete").earned)
        assertEquals(1.0, badges.named("Rare Find").current, 0.0)
        assertFalse(badges.named("Rare Company").earned)
    }

    private fun List<TrailBadge>.named(title: String): TrailBadge =
        single { it.definition.title == title }

    private fun hike(id: String, miles: Double) = Hike(
        id = id,
        title = "Trail $id",
        hikeDate = "2026-07-27",
        distanceMiles = miles,
        locationName = "State Park",
        notes = "",
        isArchived = false,
        coverUrl = "",
        photoCount = 0,
        speciesCount = 0,
    )

    private fun species(taxonId: Long, iconicTaxonName: String) = SpeciesRecord(
        key = "taxon-$taxonId",
        taxonId = taxonId,
        commonName = "Species $taxonId",
        scientificName = "Species $taxonId",
        rank = "species",
        iconicTaxonName = iconicTaxonName,
        wikipediaUrl = "",
        wikipediaSummary = "",
        encounterCount = 1,
        hikeCount = 1,
        hikeIds = listOf("hike-1"),
        hikeEncounterCounts = mapOf("hike-1" to 1),
        hikeCoverUrls = emptyMap(),
        latestSeen = "2026-07-27",
        coverUrl = "",
    )

    private fun questJson(
        id: String,
        firstCollected: Boolean,
        secondCollected: Boolean,
    ): String =
        """
        {
          "id":"$id",
          "title":"Focus quest",
          "status":"active",
          "area":{"id":"trail-1","name":"Lake Trail","radius_km":10},
          "period":{"target_date":"2026-07-27","label":"Jul"},
          "progress":{"collected_count":0,"total_count":2,"remaining_count":2},
          "taxa":[
            {
              "taxon_id":101,
              "common_name":"Rare fern",
              "scientific_name":"Rare fern",
              "iconic_taxon_name":"Plantae",
              "frequency_band":"Less often reported",
              "focus_order":1,
              "collected":$firstCollected
            },
            {
              "taxon_id":202,
              "common_name":"Common bird",
              "scientific_name":"Common bird",
              "iconic_taxon_name":"Aves",
              "frequency_band":"Regularly reported",
              "focus_order":2,
              "collected":$secondCollected
            }
          ]
        }
        """.trimIndent()
}
