package com.hikejournal.app.tracking

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TcxDocumentTest {
    @Test
    fun `writes one track per usable segment and excludes singleton segments`() {
        val snapshot = TrackingSnapshot(
            sessionId = "session",
            hikeId = "hike",
            status = TrackingStatus.FINALIZING,
            startedAtEpochMs = 0L,
            hikeDate = "1970-01-01",
            distanceMeters = 42.5,
            activeElapsedMs = 65_500L,
            currentSegment = 2,
            routeSegments = listOf(
                listOf(point(0, 0, 0L), point(1, 0, 5_000L)),
                listOf(point(2, 1, 10_000L)),
                listOf(point(3, 2, 15_000L), point(4, 2, 20_000L)),
            ),
            lastAccuracyMeters = 3f,
            lastFixEpochMs = 20_000L,
            pointCount = 5,
            generatedTcxPath = null,
            recoveryReason = null,
            error = null,
        )

        val xml = TcxDocument.render(snapshot)

        assertEquals(2, Regex("<Track>").findAll(xml).count())
        assertEquals(4, Regex("<Trackpoint>").findAll(xml).count())
        assertTrue(xml.contains("<TotalTimeSeconds>65.500000</TotalTimeSeconds>"))
        assertTrue(xml.contains("<DistanceMeters>42.500000</DistanceMeters>"))
        assertTrue(xml.contains("1970-01-01T00:00:00Z"))
        assertFalse(xml.contains("1970-01-01T00:00:10Z"))
    }

    private fun point(sequence: Long, segment: Int, time: Long) = TrackingPoint(
        sequence = sequence,
        segment = segment,
        latitude = 40.0 + sequence / 10_000.0,
        longitude = -74.0,
        altitudeMeters = 100.0,
        accuracyMeters = 3f,
        fixEpochMs = time,
    )
}
