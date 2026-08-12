package com.hikejournal.app.ui

import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.HikeLocation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PlaceProfileNavigationTest {
    @Test
    fun `place targets use the latest visit and exclude standalone entries`() {
        val targets = placeProfileTargets(
            listOf(
                hike("a-old", "2026-07-01", "place-a", "Oak Flat", "old.jpg"),
                hike("b", "2026-08-05", "place-b", "Pine Loop", "pine.jpg"),
                hike("a-new", "2026-08-10", "place-a", "Oak Flat", "new.jpg"),
                hike("everyday", "2026-08-11", "place-c", "Various", "everyday.jpg", standalone = true),
                hike("unlinked", "2026-08-12", null, "Unlinked", "unlinked.jpg"),
            ),
        )

        assertEquals(listOf("place-a", "place-b"), targets.map { it.id })
        assertEquals("new.jpg", targets.first().coverUrl)
        assertEquals("2026-08-10", targets.first().latestHikeDate)
    }

    @Test
    fun `adjacent place targets wrap in both directions`() {
        val targets = listOf(
            PlaceProfileTarget("place-a", "Oak Flat", "a.jpg", "2026-08-10"),
            PlaceProfileTarget("place-b", "Pine Loop", "b.jpg", "2026-08-05"),
            PlaceProfileTarget("place-c", "Marsh Edge", "c.jpg", "2026-07-30"),
        )

        assertEquals("place-b", adjacentPlaceProfileTarget(targets, "place-a", 1)?.id)
        assertEquals("place-c", adjacentPlaceProfileTarget(targets, "place-a", -1)?.id)
        assertEquals("place-a", adjacentPlaceProfileTarget(targets, "place-c", 1)?.id)
        assertNull(adjacentPlaceProfileTarget(targets, "missing", 1))
        assertNull(adjacentPlaceProfileTarget(emptyList(), "place-a", 1))
    }

    @Test
    fun `place targets append unvisited saved places for planning`() {
        val targets = placeProfileTargets(
            hikes = listOf(hike("visited", "2026-08-10", "place-a", "Oak Flat", "oak.jpg")),
            locations = listOf(
                HikeLocation("place-b", "Zigzag Marsh", 28.0, -81.0),
                HikeLocation("place-a", "Oak Flat", 28.1, -81.1),
                HikeLocation("place-c", "Cypress Loop", 28.2, -81.2),
            ),
        )

        assertEquals(listOf("place-a", "place-c", "place-b"), targets.map { it.id })
        assertEquals("", targets[1].latestHikeDate)
        assertEquals(true, targets[1].hasCoordinates)
    }

    @Test
    fun `river trend describes net change over the selected period`() {
        assertEquals("Up +1.25 ft over 7 days", riverPeriodTrendLabel(1.25, 7))
        assertEquals("Down -0.75 ft over 30 days", riverPeriodTrendLabel(-0.75, 30))
        assertEquals("Little net change over 7 days", riverPeriodTrendLabel(0.01, 7))
        assertEquals("Net change over 30 days unavailable", riverPeriodTrendLabel(null, 30))
    }

    private fun hike(
        id: String,
        date: String,
        locationId: String?,
        locationName: String,
        coverUrl: String,
        standalone: Boolean = false,
    ) = Hike(
        id = id,
        title = id,
        hikeDate = date,
        distanceMiles = null,
        locationName = locationName,
        notes = "",
        isArchived = true,
        isStandalone = standalone,
        coverUrl = coverUrl,
        photoCount = 0,
        speciesCount = 0,
        primaryLocationId = locationId,
        primaryLocationName = locationName,
    )
}
