package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class MobileMapParserTest {
    @Test
    fun summaryParsesTotalCountAndExpandsSinglePointBounds() {
        val summary = parseMobileMapSummary(
            """{"photo_count":127,"bounds":[-82.1,28.2,-82.1,28.2]}""",
        )

        assertEquals(127, summary.photoCount)
        assertEquals(-82.11, summary.bounds?.west ?: 0.0, 0.000001)
        assertEquals(-82.09, summary.bounds?.east ?: 0.0, 0.000001)
        assertNotNull(summary.bounds)
    }

    @Test
    fun viewportParsesIndividualPhotosAndClusterMarkers() {
        val sightings = parseMobileMapViewport(
            """{"features":[{"kind":"photo","id":"photo-1","lat":28.2,"lng":-82.1,"hike_id":"hike-1","caption":"Egret","url":"photo-url","thumbnail_url":"thumb-url"},{"kind":"cluster","id":"cluster:1:2","lat":28.3,"lng":-82.0,"cluster_count":37,"title":"37 photos"}]}""",
        )

        assertEquals(2, sightings.size)
        assertEquals("photo-1", sightings[0].id)
        assertEquals(0, sightings[0].clusterCount)
        assertEquals("photo-url", sightings[0].url)
        assertEquals(0, sightings[0].latitude.compareTo(28.2))
        assertEquals("cluster:1:2", sightings[1].id)
        assertEquals(37, sightings[1].clusterCount)
        assertEquals("37 photos", sightings[1].hikeTitle)
        assertNull(sightings[1].hikeId)
    }
}
