package com.hikejournal.app.tracking

import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

internal data class RawTrackingFix(
    val latitude: Double,
    val longitude: Double,
    val altitudeMeters: Double?,
    val accuracyMeters: Float,
    val fixEpochMs: Long,
    val fixElapsedRealtimeNanos: Long,
)

internal enum class RejectedFixReason {
    INVALID_COORDINATE,
    INVALID_ACCURACY,
    STALE,
    FUTURE,
    OUT_OF_ORDER,
    JITTER,
    IMPLAUSIBLE_SPEED,
}

internal sealed interface FilteredFix {
    data class Accepted(
        val segment: Int,
        val distanceFromPreviousMeters: Double,
        val startsSegment: Boolean,
    ) : FilteredFix

    data class Rejected(val reason: RejectedFixReason) : FilteredFix
}

internal class TrackingLocationFilter(
    private val maxAccuracyMeters: Float = 50f,
    private val maxAgeMs: Long = 30_000L,
    private val maxFutureMs: Long = 10_000L,
    private val minDistanceMeters: Double = 3.0,
    private val maxSpeedMetersPerSecond: Double = 12.0,
    private val segmentGapMs: Long = 60_000L,
) {
    fun evaluate(
        fix: RawTrackingFix,
        receivedAtEpochMs: Long,
        last: RawTrackingFix?,
        currentSegment: Int,
        segmentStartPending: Boolean,
    ): FilteredFix {
        if (!fix.latitude.isFinite() || !fix.longitude.isFinite() ||
            fix.latitude !in -90.0..90.0 || fix.longitude !in -180.0..180.0
        ) {
            return FilteredFix.Rejected(RejectedFixReason.INVALID_COORDINATE)
        }
        if (!fix.accuracyMeters.isFinite() || fix.accuracyMeters < 0f ||
            fix.accuracyMeters > maxAccuracyMeters
        ) {
            return FilteredFix.Rejected(RejectedFixReason.INVALID_ACCURACY)
        }
        val ageMs = receivedAtEpochMs - fix.fixEpochMs
        if (ageMs > maxAgeMs) return FilteredFix.Rejected(RejectedFixReason.STALE)
        if (ageMs < -maxFutureMs) return FilteredFix.Rejected(RejectedFixReason.FUTURE)
        val elapsedDeltaNanos = last?.let { previous ->
            if (fix.fixElapsedRealtimeNanos > 0L && previous.fixElapsedRealtimeNanos > 0L) {
                fix.fixElapsedRealtimeNanos - previous.fixElapsedRealtimeNanos
            } else {
                null
            }
        }
        val elapsedDeltaMs = elapsedDeltaNanos?.div(1_000_000L)
            ?: last?.let { fix.fixEpochMs - it.fixEpochMs }
        if (elapsedDeltaMs != null && elapsedDeltaMs <= 0L) {
            return FilteredFix.Rejected(RejectedFixReason.OUT_OF_ORDER)
        }

        val gapStartsSegment = last != null && elapsedDeltaMs != null && elapsedDeltaMs >= segmentGapMs
        if (last == null || segmentStartPending || gapStartsSegment) {
            return FilteredFix.Accepted(
                segment = if (gapStartsSegment && !segmentStartPending) currentSegment + 1 else currentSegment,
                distanceFromPreviousMeters = 0.0,
                startsSegment = true,
            )
        }

        val distance = haversineMeters(
            last.latitude,
            last.longitude,
            fix.latitude,
            fix.longitude,
        )
        val combinedAccuracy = sqrt(
            fix.accuracyMeters.toDouble() * fix.accuracyMeters +
                last.accuracyMeters.toDouble() * last.accuracyMeters,
        )
        val driftGateMeters = max(minDistanceMeters, combinedAccuracy * ACCURACY_DRIFT_FACTOR)
        if (distance < driftGateMeters) {
            return FilteredFix.Rejected(RejectedFixReason.JITTER)
        }
        val seconds = elapsedDeltaMs!! / 1_000.0
        if (seconds <= 0.0 || distance / seconds > maxSpeedMetersPerSecond) {
            return FilteredFix.Rejected(RejectedFixReason.IMPLAUSIBLE_SPEED)
        }
        return FilteredFix.Accepted(
            segment = currentSegment,
            distanceFromPreviousMeters = distance,
            startsSegment = false,
        )
    }

    companion object {
        private const val EARTH_RADIUS_METERS = 6_371_008.8
        private const val ACCURACY_DRIFT_FACTOR = 0.5

        fun haversineMeters(
            latitudeA: Double,
            longitudeA: Double,
            latitudeB: Double,
            longitudeB: Double,
        ): Double {
            val lat1 = Math.toRadians(latitudeA)
            val lat2 = Math.toRadians(latitudeB)
            val dLat = lat2 - lat1
            val dLon = Math.toRadians(longitudeB - longitudeA)
            val a = sin(dLat / 2) * sin(dLat / 2) +
                cos(lat1) * cos(lat2) * sin(dLon / 2) * sin(dLon / 2)
            return EARTH_RADIUS_METERS * 2 * asin(sqrt(min(1.0, max(0.0, a))))
        }
    }
}
