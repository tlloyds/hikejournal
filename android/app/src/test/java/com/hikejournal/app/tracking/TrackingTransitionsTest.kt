package com.hikejournal.app.tracking

import org.junit.Assert.assertThrows
import org.junit.Test

class TrackingTransitionsTest {
    @Test
    fun `allows recording pause resume and paused finalization`() {
        TrackingTransitions.require(TrackingStatus.RECORDING, TrackingStatus.PAUSED, TrackingStatus.RECORDING)
        TrackingTransitions.require(TrackingStatus.PAUSED, TrackingStatus.RECORDING, TrackingStatus.PAUSED)
        TrackingTransitions.require(TrackingStatus.PAUSED, TrackingStatus.FINALIZING, TrackingStatus.PAUSED)
        TrackingTransitions.require(TrackingStatus.FINALIZING, TrackingStatus.FINISHED, TrackingStatus.FINALIZING)
    }

    @Test
    fun `end cannot begin while recording`() {
        assertThrows(TrackingStateException::class.java) {
            TrackingTransitions.require(
                TrackingStatus.RECORDING,
                TrackingStatus.FINALIZING,
                TrackingStatus.PAUSED,
            )
        }
    }
}
