package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LongitudinalParserTest {
    @Test
    fun `place profile keeps seasonal months and visit progression`() {
        val profile = parsePlaceProfile(
            """
            {
              "location":{"id":"place-1","name":"Oak Flat"},
              "summary":{"first_visit":"2024-02-01","latest_visit":"2026-02-01","outing_count":2,"total_distance_miles":5.5,"total_duration_seconds":7200,"observation_count":4,"species_count":3},
              "taxon_counts":[{"name":"Plantae","count":2}],
              "seasonal_history":{"observation_count":4,"months":[{"month":2,"label":"Feb","count":4,"relative_intensity":1.0}],"years":[],"guidance":"Your observations."},
              "visits":[{"hike_id":"hike-2","title":"Return","hike_date":"2026-02-01","distance_miles":3.0,"observation_count":2,"species_count":2,"new_species_count":1,"cumulative_species_count":3,"cover_url":""}],
              "guidance":"Your records."
            }
            """.trimIndent(),
        )

        assertEquals("Oak Flat", profile.name)
        assertEquals(3, profile.speciesCount)
        assertEquals(4, profile.seasonalHistory.months.single().count)
        assertEquals(3, profile.visits.single().cumulativeSpeciesCount)
    }

    @Test
    fun `briefing retains deterministic reasons`() {
        val briefing = parseFieldBriefing(
            """
            {
              "area":{"name":"Oak Flat"},
              "target_date":"2026-08-09",
              "guidance":"Frequency is not probability.",
              "sections":[{"title":"Seasonal returns","items":[{"key":"taxon:1","taxon_id":1,"common_name":"Pink sundew","scientific_name":"Drosera capillaris","iconic_taxon_name":"Plantae","section":"Seasonal returns","reasons":["You recorded this around this time in 2025."],"reference_photo":{"url":"https://example.test/photo.jpg"}}]}]
            }
            """.trimIndent(),
        )

        assertEquals("Oak Flat", briefing.areaName)
        assertEquals("Seasonal returns", briefing.sections.single().title)
        assertTrue(briefing.sections.single().items.single().reasons.single().contains("2025"))
    }

    @Test
    fun `hike parser includes synced field marks`() {
        val hike = parseHike(
            """
            {"id":"hike-1","title":"Marked route","field_marks":[{"id":"mark-1","hike_id":"hike-1","recording_session_id":"session-1","marked_at":"2026-08-09T12:00:00Z","lat":28.1,"lng":-82.1,"accuracy_meters":8.0,"mark_type":"wildlife","note":"Owl"}]}
            """.trimIndent(),
        )

        assertEquals("wildlife", hike.fieldMarks.single().markType)
        assertEquals("Owl", hike.fieldMarks.single().note)
    }
}
