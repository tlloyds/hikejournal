package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HikeLocationGuessingTest {
    @Test
    fun `suggests the library location nearest the first recorded point`() {
        val suggestion = suggestHikeLocation(
            routeSegments = listOf(
                listOf(
                    RoutePoint(27.8608, -82.3358),
                    RoutePoint(27.9000, -82.2000),
                ),
            ),
            locations = listOf(
                HikeLocation("finish", "Near the finish", 27.9000, -82.2000),
                HikeLocation("start", "Alafia Scrub Preserve", 27.8609, -82.3359),
            ),
        )

        assertEquals("start", suggestion?.location?.id)
        assertTrue((suggestion?.distanceMeters ?: Double.MAX_VALUE) < 20.0)
    }

    @Test
    fun `does not guess when every coordinate-backed place is too far away`() {
        val suggestion = suggestHikeLocation(
            routeSegments = listOf(listOf(RoutePoint(40.0, -74.0))),
            locations = listOf(
                HikeLocation("missing", "No coordinates"),
                HikeLocation("florida", "Florida trail", 27.8609, -82.3359),
            ),
        )

        assertNull(suggestion)
    }
}
