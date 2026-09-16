package com.hikejournal.app.tracking

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TrackingAnnouncementsTest {
    @Test
    fun `mile announcement includes total and last mile time`() {
        val scheduler = TrackingMileAnnouncementScheduler()
        scheduler.update(snapshot(distanceMeters = 0.0, activeElapsedMs = 0L))

        val first = scheduler.update(
            snapshot(
                distanceMeters = 1_609.344,
                activeElapsedMs = 20 * 60 * 1_000L,
            ),
        )
        assertEquals(
            "Total distance 1 mile. Total time 20 minutes. Last mile time 20 minutes.",
            first?.message,
        )

        val second = scheduler.update(
            snapshot(
                distanceMeters = 2 * 1_609.344,
                activeElapsedMs = 40 * 60 * 1_000L,
            ),
        )
        assertEquals(
            "Total distance 2 miles. Total time 40 minutes. Last mile time 20 minutes.",
            second?.message,
        )
    }

    @Test
    fun `mile announcement is emitted once per completed mile`() {
        val scheduler = TrackingMileAnnouncementScheduler()
        scheduler.update(snapshot(distanceMeters = 0.0, activeElapsedMs = 0L))

        assertEquals(
            1,
            scheduler.update(snapshot(distanceMeters = 1_700.0, activeElapsedMs = 90_000L))?.completedMiles,
        )
        assertNull(scheduler.update(snapshot(distanceMeters = 1_800.0, activeElapsedMs = 100_000L)))
    }

    @Test
    fun `speech duration uses natural units`() {
        assertEquals("0 seconds", formatSpeechElapsed(0L))
        assertEquals("1 minute", formatSpeechElapsed(60_000L))
        assertEquals("1 hour 2 minutes", formatSpeechElapsed(3_725_000L))
    }

    private fun snapshot(distanceMeters: Double, activeElapsedMs: Long) = TrackingSnapshot(
        sessionId = "session-1",
        hikeId = "hike-1",
        status = TrackingStatus.RECORDING,
        startedAtEpochMs = 0L,
        hikeDate = "2026-09-15",
        distanceMeters = distanceMeters,
        activeElapsedMs = activeElapsedMs,
        currentSegment = 0,
        routeSegments = emptyList(),
        lastAccuracyMeters = null,
        lastFixEpochMs = null,
        pointCount = 0,
        generatedTcxPath = null,
        recoveryReason = null,
        error = null,
    )
}
