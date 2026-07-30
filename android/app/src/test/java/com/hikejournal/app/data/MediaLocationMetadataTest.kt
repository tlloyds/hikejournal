package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MediaLocationMetadataTest {
    @Test
    fun parsesIso6709VideoCoordinates() {
        val location = parseVideoLocation("+28.5693-082.4451+012.000/")

        assertEquals(28.5693, location?.first ?: 0.0, 0.000001)
        assertEquals(-82.4451, location?.second ?: 0.0, 0.000001)
    }

    @Test
    fun rejectsMissingOrOutOfRangeVideoCoordinates() {
        assertNull(parseVideoLocation(null))
        assertNull(parseVideoLocation("not-a-location"))
        assertNull(parseVideoLocation("+128.0000-082.0000/"))
    }

    @Test
    fun summarizesMissingLocationsWithoutGoingNegative() {
        val partial = MediaLocationSummary(totalCount = 5, geotaggedCount = 2)
        val complete = MediaLocationSummary(totalCount = 5, geotaggedCount = 5)
        val inconsistent = MediaLocationSummary(totalCount = 2, geotaggedCount = 3)

        assertEquals(3, partial.missingCount)
        assertFalse(partial.allGeotagged)
        assertTrue(complete.allGeotagged)
        assertEquals(0, inconsistent.missingCount)
    }
}
