package com.hikejournal.app.tracking

import org.junit.Assert.assertEquals
import org.junit.Test

class TrackingTimeTest {
    @Test
    fun `recording time combines checkpoint and same boot delta`() {
        assertEquals(
            25_000L,
            TrackingTimeMath.activeElapsedMs(
                accumulatedMs = 10_000L,
                activeSinceElapsedRealtimeMs = 20_000L,
                status = TrackingStatus.RECORDING,
                sameBoot = true,
                nowElapsedRealtimeMs = 35_000L,
            ),
        )
    }

    @Test
    fun `paused and rebooted time never adds monotonic delta`() {
        assertEquals(
            10_000L,
            TrackingTimeMath.activeElapsedMs(10_000L, 20_000L, TrackingStatus.PAUSED, true, 90_000L),
        )
        assertEquals(
            10_000L,
            TrackingTimeMath.activeElapsedMs(10_000L, 20_000L, TrackingStatus.RECORDING, false, 90_000L),
        )
    }

    @Test
    fun `stale service recovery preserves only durable checkpoint`() {
        assertEquals(15_000L, TrackingRecoveryMath.pausedElapsedMs(15_000L))
        assertEquals(0L, TrackingRecoveryMath.pausedElapsedMs(-1L))
    }
}
