package com.hikejournal.app

import com.hikejournal.app.data.PlaceProfile
import com.hikejournal.app.data.SeasonalHistory
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Test

class LongitudinalNavigationTest {
    @Test
    fun `top-level navigation clears a loaded place profile and pending planning work`() {
        val state = AppState(
            placeProfile = PlaceProfile(
                locationId = "place-1",
                name = "Oak Flat",
                latitude = 28.1,
                longitude = -81.2,
                firstVisit = null,
                latestVisit = null,
                outingCount = 0,
                totalDistanceMiles = 0.0,
                totalDurationSeconds = 0,
                observationCount = 0,
                speciesCount = 0,
                taxonCounts = emptyList(),
                taxonGroups = emptyList(),
                seasonalHistory = SeasonalHistory(),
                visits = emptyList(),
                guidance = "",
            ),
            isLongitudinalLoading = true,
            longitudinalDestination = LongitudinalDestination.FieldBriefing,
            isRiverGaugeLoading = true,
        )

        val cleared = state.withoutLongitudinalScreens()

        assertNull(cleared.placeProfile)
        assertNull(cleared.fieldBriefing)
        assertNull(cleared.hikeComparison)
        assertNull(cleared.longitudinalDestination)
        assertFalse(cleared.isLongitudinalLoading)
        assertFalse(cleared.isRiverGaugeLoading)
    }
}
