package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SpeciesDiscoveryParserTest {
    private val discoveryAreas = listOf(
        DiscoveryArea("1", "Alafia River State Park", 27.8, -82.1, "saved_location"),
        DiscoveryArea("2", "Lettuce Lake Trail", 28.1, -82.4, "saved_location"),
        DiscoveryArea("3", "Florida Trail", 28.2, -81.7, "saved_location"),
    )

    @Test
    fun `saved trail search populates before typing and filters by name`() {
        assertEquals(discoveryAreas, filterDiscoveryAreas(discoveryAreas, ""))
        assertEquals(
            listOf(discoveryAreas[1]),
            filterDiscoveryAreas(discoveryAreas, "lettuce"),
        )
        assertTrue(filterDiscoveryAreas(discoveryAreas, "missing").isEmpty())
    }

    @Test
    fun `foreground coordinates are rounded before discovery requests`() {
        assertEquals(28.54, roundedDiscoveryCoordinate(28.53831), 0.000001)
        assertEquals(-81.38, roundedDiscoveryCoordinate(-81.37924), 0.000001)
    }

    @Test
    fun `nearby response preserves frequency attribution and personal progress`() {
        val nearby = parseNearbySpecies(
            """
            {
              "area":{"id":"trail-1","name":"Florida Trail","lat":28.1,"lng":-81.5,"radius_km":10},
              "period":{"target_date":"2026-07-26","label":"Jun · Jul · Aug"},
              "filters":{"iconic_taxon":"Aves"},
              "source":{"from_cache":true,"guidance":"Reporting frequency is not a probability of encounter."},
              "data_density":{"level":"normal","message":""},
              "progress":{"collected_count":1,"total_count":2,"remaining_count":1},
              "taxa":[{
                "taxon_id":123,
                "common_name":"Florida Scrub-Jay",
                "scientific_name":"Aphelocoma coerulescens",
                "iconic_taxon_name":"Aves",
                "observation_count":42,
                "nearby_rank":1,
                "frequency_band":"Often reported",
                "reference_photo":{"url":"https://example.test/jay.jpg","attribution":"© Naturalist","license_code":"cc-by"},
                "collected":false,
                "pending_credit":true
              }]
            }
            """.trimIndent(),
        )

        assertEquals("Florida Trail", nearby.areaName)
        assertEquals(1, nearby.progress.collectedCount)
        assertTrue(nearby.fromCache)
        assertEquals("Often reported", nearby.taxa.single().frequencyBand)
        assertEquals("cc-by", nearby.taxa.single().referencePhoto?.licenseCode)
        assertTrue(nearby.taxa.single().pendingCredit)
        assertFalse(nearby.taxa.single().collected)
    }

    @Test
    fun `quest response preserves frozen checklist and focus order`() {
        val quest = parseFieldQuest(
            """
            {
              "id":"quest-1",
              "title":"Wetland birds",
              "status":"active",
              "linked_hike_id":"hike-1",
              "area":{"id":"trail-1","name":"Lake Trail","radius_km":25},
              "period":{"target_date":"2026-07-26","label":"Jun · Jul · Aug"},
              "filters":{"iconic_taxon":"Aves"},
              "progress":{"collected_count":0,"total_count":1,"remaining_count":1},
              "taxa":[{
                "taxon_id":456,
                "common_name":"Limpkin",
                "scientific_name":"Aramus guarauna",
                "nearby_rank":3,
                "frequency_band":"Regularly reported",
                "focus_order":1,
                "collected":false,
                "pending_credit":false
              }]
            }
            """.trimIndent(),
        )

        assertEquals("quest-1", quest.id)
        assertEquals("hike-1", quest.linkedHikeId)
        assertEquals(1, quest.progress.totalCount)
        assertEquals(1, quest.taxa.single().focusOrder)
    }
}
