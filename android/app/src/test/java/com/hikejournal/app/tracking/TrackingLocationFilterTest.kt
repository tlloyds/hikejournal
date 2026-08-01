package com.hikejournal.app.tracking

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TrackingLocationFilterTest {
    private val filter = TrackingLocationFilter()

    @Test
    fun `accepts walking movement and measures haversine distance`() {
        val previous = fix(latitude = 40.0, epochMs = 1_000L, elapsedNanos = 1_000_000_000L)
        val current = fix(latitude = 40.0001, epochMs = 6_000L, elapsedNanos = 6_000_000_000L)

        val result = filter.evaluate(current, 6_000L, previous, 0, false)

        assertTrue(result is FilteredFix.Accepted)
        result as FilteredFix.Accepted
        assertEquals(0, result.segment)
        assertEquals(11.12, result.distanceFromPreviousMeters, 0.2)
    }

    @Test
    fun `combined accuracy rejects drift even when it exceeds three meters`() {
        val previous = fix(
            latitude = 40.0,
            accuracy = 20f,
            epochMs = 1_000L,
            elapsedNanos = 1_000_000_000L,
        )
        val current = fix(
            latitude = 40.00007,
            accuracy = 20f,
            epochMs = 6_000L,
            elapsedNanos = 6_000_000_000L,
        )

        val result = filter.evaluate(current, 6_000L, previous, 0, false)

        assertEquals(
            FilteredFix.Rejected(RejectedFixReason.JITTER),
            result,
        )
    }

    @Test
    fun `elapsed realtime controls ordering and speed when wall timestamps match`() {
        val previous = fix(latitude = 40.0, epochMs = 6_000L, elapsedNanos = 1_000_000_000L)
        val current = fix(latitude = 40.0001, epochMs = 6_000L, elapsedNanos = 6_000_000_000L)

        val result = filter.evaluate(current, 6_000L, previous, 0, false)

        assertTrue(result is FilteredFix.Accepted)
    }

    @Test
    fun `elapsed realtime gap starts a segment without bridging distance`() {
        val previous = fix(latitude = 40.0, epochMs = 1_000L, elapsedNanos = 1_000_000_000L)
        val current = fix(latitude = 40.001, epochMs = 6_000L, elapsedNanos = 61_000_000_000L)

        val result = filter.evaluate(current, 6_000L, previous, 2, false)

        assertEquals(FilteredFix.Accepted(3, 0.0, true), result)
    }

    @Test
    fun `resume starts a segment without bridging distance`() {
        val previous = fix(latitude = 40.0, epochMs = 1_000L, elapsedNanos = 1_000_000_000L)
        val current = fix(latitude = 40.001, epochMs = 6_000L, elapsedNanos = 6_000_000_000L)

        val result = filter.evaluate(current, 6_000L, previous, 4, true)

        assertEquals(FilteredFix.Accepted(4, 0.0, true), result)
    }

    @Test
    fun `rejects stale inaccurate out of order and implausibly fast fixes`() {
        val previous = fix(latitude = 40.0, epochMs = 10_000L, elapsedNanos = 10_000_000_000L)

        assertEquals(
            RejectedFixReason.STALE,
            rejected(fix(epochMs = 10_000L), receivedAt = 40_001L),
        )
        assertEquals(
            RejectedFixReason.INVALID_ACCURACY,
            rejected(fix(epochMs = 10_000L, accuracy = 51f), receivedAt = 10_000L),
        )
        assertEquals(
            RejectedFixReason.OUT_OF_ORDER,
            rejected(
                fix(epochMs = 11_000L, elapsedNanos = 9_000_000_000L),
                receivedAt = 11_000L,
                previous = previous,
            ),
        )
        assertEquals(
            RejectedFixReason.IMPLAUSIBLE_SPEED,
            rejected(
                fix(latitude = 40.001, epochMs = 11_000L, elapsedNanos = 11_000_000_000L),
                receivedAt = 11_000L,
                previous = previous,
            ),
        )
    }

    private fun rejected(
        current: RawTrackingFix,
        receivedAt: Long,
        previous: RawTrackingFix? = null,
    ): RejectedFixReason =
        (filter.evaluate(current, receivedAt, previous, 0, false) as FilteredFix.Rejected).reason

    private fun fix(
        latitude: Double = 40.0,
        longitude: Double = -74.0,
        accuracy: Float = 3f,
        epochMs: Long,
        elapsedNanos: Long = epochMs * 1_000_000L,
    ) = RawTrackingFix(
        latitude = latitude,
        longitude = longitude,
        altitudeMeters = 100.0,
        accuracyMeters = accuracy,
        fixEpochMs = epochMs,
        fixElapsedRealtimeNanos = elapsedNanos,
    )
}
