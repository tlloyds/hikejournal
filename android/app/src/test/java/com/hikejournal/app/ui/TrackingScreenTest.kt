package com.hikejournal.app.ui

import com.hikejournal.app.tracking.TrackingPoint
import com.hikejournal.app.tracking.TrackingSnapshot
import com.hikejournal.app.tracking.TrackingStatus
import org.junit.Assert.assertEquals
import org.junit.Test

class TrackingScreenTest {
    @Test
    fun `live tracking map defaults to satellite`() {
        assertEquals(MapLayerMode.Satellite, DEFAULT_TRACKING_MAP_LAYER)
    }

    @Test
    fun `active duration uses clock notation`() {
        assertEquals("00:00", formatTrackingDuration(0))
        assertEquals("08:05", formatTrackingDuration(485))
        assertEquals("2:03:04", formatTrackingDuration(7_384))
    }

    @Test
    fun `distance uses two decimals for live feedback`() {
        assertEquals("0.00 mi", formatTrackingDistance(0.0))
        assertEquals("3.28 mi", formatTrackingDistance(3.276))
    }

    @Test
    fun `invalid display values are made safe`() {
        assertEquals("00:00", formatTrackingDuration(-12))
        assertEquals("0.00 mi", formatTrackingDistance(Double.NaN))
        assertEquals("0.00 mi", formatTrackingDistance(-1.2))
    }

    @Test
    fun `snapshot maps metric storage to live miles and seconds`() {
        val model = snapshot().toTrackingUiModel(nowEpochMs = 100_000L)

        assertEquals(1.0, model.distanceMiles, 0.000001)
        assertEquals(125L, model.elapsedSeconds)
        assertEquals(TrackingGpsUiStatus.Strong, model.gpsStatus)
        assertEquals(28.2, model.currentPoint?.latitude ?: 0.0, 0.000001)
    }

    @Test
    fun `stale fix returns to searching status`() {
        val model = snapshot(lastFixEpochMs = 20_000L).toTrackingUiModel(nowEpochMs = 100_001L)

        assertEquals(TrackingGpsUiStatus.Searching, model.gpsStatus)
    }

    private fun snapshot(lastFixEpochMs: Long = 99_000L) = TrackingSnapshot(
        sessionId = "session-1",
        hikeId = "hike-1",
        status = TrackingStatus.RECORDING,
        startedAtEpochMs = 1_000L,
        hikeDate = "2026-08-01",
        distanceMeters = 1_609.344,
        activeElapsedMs = 125_999L,
        currentSegment = 0,
        routeSegments = listOf(
            listOf(
                point(0, 28.1, -82.1),
                point(1, 28.2, -82.2),
            ),
        ),
        lastAccuracyMeters = 8f,
        lastFixEpochMs = lastFixEpochMs,
        pointCount = 2,
        generatedTcxPath = null,
        recoveryReason = null,
        error = null,
    )

    private fun point(sequence: Long, latitude: Double, longitude: Double) = TrackingPoint(
        sequence = sequence,
        segment = 0,
        latitude = latitude,
        longitude = longitude,
        altitudeMeters = null,
        accuracyMeters = 8f,
        fixEpochMs = 99_000L + sequence,
    )
}
