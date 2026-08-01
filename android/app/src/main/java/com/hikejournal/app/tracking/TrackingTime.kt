package com.hikejournal.app.tracking

internal object TrackingTimeMath {
    fun activeElapsedMs(
        accumulatedMs: Long,
        activeSinceElapsedRealtimeMs: Long?,
        status: TrackingStatus,
        sameBoot: Boolean,
        nowElapsedRealtimeMs: Long,
    ): Long {
        if (status != TrackingStatus.RECORDING || !sameBoot || activeSinceElapsedRealtimeMs == null) {
            return accumulatedMs.coerceAtLeast(0L)
        }
        return (accumulatedMs + (nowElapsedRealtimeMs - activeSinceElapsedRealtimeMs).coerceAtLeast(0L))
            .coerceAtLeast(0L)
    }
}

internal object TrackingRecoveryMath {
    fun pausedElapsedMs(checkpointedActiveElapsedMs: Long): Long =
        checkpointedActiveElapsedMs.coerceAtLeast(0L)
}
