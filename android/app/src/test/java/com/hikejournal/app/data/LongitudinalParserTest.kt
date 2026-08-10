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
              "taxon_groups":[{"name":"Plantae","count":2,"species":[{"key":"taxon:1","taxon_id":1,"common_name":"Pink sundew","scientific_name":"Drosera capillaris","iconic_taxon_name":"Plantae","encounter_count":3,"reference_photo_url":"https://example.test/sundew.jpg"}]}],
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
        assertEquals("Pink sundew", profile.taxonGroups.single().species.single().commonName)
        assertEquals("https://example.test/sundew.jpg", profile.taxonGroups.single().species.single().referencePhotoUrl)
    }

    @Test
    fun `briefing retains deterministic reasons`() {
        val briefing = parseFieldBriefing(
            """
            {
              "area":{"id":"place-1","name":"Oak Flat","lat":28.1,"lng":-82.2,"radius_km":10},
              "period":{"label":"Jul–Sep"},
              "target_date":"2026-08-09",
              "guidance":"Frequency is not probability.",
              "sections":[{"title":"Seasonal returns","items":[{"key":"taxon:1","taxon_id":1,"common_name":"Pink sundew","scientific_name":"Drosera capillaris","iconic_taxon_name":"Plantae","section":"Seasonal returns","reasons":["You recorded this around this time in 2025."],"reference_photo":{"url":"https://example.test/photo.jpg","attribution":"Jane Naturalist","license_code":"CC-BY"}}]}]
            }
            """.trimIndent(),
        )

        assertEquals("Oak Flat", briefing.areaName)
        assertEquals("place-1", briefing.areaId)
        assertEquals(28.1, briefing.latitude!!, 0.001)
        assertEquals("Jul–Sep", briefing.periodLabel)
        assertEquals("Seasonal returns", briefing.sections.single().title)
        assertTrue(briefing.sections.single().items.single().reasons.single().contains("2025"))
        assertEquals("Jane Naturalist", briefing.sections.single().items.single().referencePhotoAttribution)
    }

    @Test
    fun `hike parser includes synced field marks`() {
        val hike = parseHike(
            """
            {"id":"hike-1","title":"Marked route","field_marks":[{"id":"mark-1","hike_id":"hike-1","recording_session_id":"session-1","marked_at":"2026-08-09T12:00:00Z","lat":28.1,"lng":-82.1,"accuracy_meters":8.0,"mark_type":"wildlife","note":"Owl"}],"weather":{"provider":"open-meteo","provider_dataset":"forecast_best_match","algorithm_version":"route-centroid-interval-v1","temperature_min_c":25.0,"temperature_mean_c":27.0,"temperature_max_c":29.0,"precipitation_total_mm":0.6,"relative_humidity_mean_percent":74.0,"condition_label":"Rain"}}
            """.trimIndent(),
        )

        assertEquals("wildlife", hike.fieldMarks.single().markType)
        assertEquals("Owl", hike.fieldMarks.single().note)
        assertEquals("Rain", hike.weather?.conditionLabel)
        assertEquals(29.0, hike.weather?.temperatureMaxC!!, 0.001)
    }

    @Test
    fun `comparison keeps weather when only one hike is enriched`() {
        val comparison = parseHikeComparison(
            """
            {"hike_a":{"id":"a","hike_date":"2026-08-09"},"hike_b":{"id":"b","hike_date":"2025-08-09"},"species":{"shared":[],"only_a":[],"only_b":[]},"weather":{"hike_a":{"provider":"open-meteo","condition_label":"Overcast","temperature_mean_c":27.0},"hike_b":null}}
            """.trimIndent(),
        )

        assertEquals("Overcast", comparison.weatherA?.conditionLabel)
        assertEquals(null, comparison.weatherB)
    }
}
