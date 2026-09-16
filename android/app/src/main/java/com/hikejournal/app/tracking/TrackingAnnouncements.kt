package com.hikejournal.app.tracking

import java.util.Locale
import kotlin.math.floor

internal data class TrackingMileAnnouncement(
    val completedMiles: Int,
    val totalElapsedMs: Long,
    val lastMileElapsedMs: Long,
) {
    val message: String
        get() {
            val mileLabel = if (completedMiles == 1) "mile" else "miles"
            return "Total distance $completedMiles $mileLabel. " +
                "Total time ${formatSpeechElapsed(totalElapsedMs)}. " +
                "Last mile time ${formatSpeechElapsed(lastMileElapsedMs)}."
        }
}

/**
 * Pure scheduling state for whole-mile speech. The service persists the three
 * fields that make this scheduler resumable when Android recreates it.
 */
internal class TrackingMileAnnouncementScheduler(
    private var sessionId: String? = null,
    private var lastAnnouncedMile: Int = 0,
    private var lastAnnouncedElapsedMs: Long = 0L,
) {
    fun update(snapshot: TrackingSnapshot): TrackingMileAnnouncement? {
        val completedMiles = completedMiles(snapshot.distanceMeters)
        val elapsedMs = snapshot.activeElapsedMs.coerceAtLeast(0L)
        if (sessionId != snapshot.sessionId) {
            sessionId = snapshot.sessionId
            lastAnnouncedMile = completedMiles
            // A restored session may already be past one or more milestones.
            // Baseline it without retroactive speech; future splits are measured
            // from the first milestone observed by this installation.
            lastAnnouncedElapsedMs = if (completedMiles > 0) elapsedMs else 0L
            return null
        }
        if (completedMiles <= lastAnnouncedMile) return null

        val lastMileElapsedMs = (elapsedMs - lastAnnouncedElapsedMs).coerceAtLeast(0L)
        lastAnnouncedMile = completedMiles
        lastAnnouncedElapsedMs = elapsedMs
        return TrackingMileAnnouncement(
            completedMiles = completedMiles,
            totalElapsedMs = elapsedMs,
            lastMileElapsedMs = lastMileElapsedMs,
        )
    }

    fun sessionId(): String? = sessionId
    fun lastAnnouncedMile(): Int = lastAnnouncedMile
    fun lastAnnouncedElapsedMs(): Long = lastAnnouncedElapsedMs

    private fun completedMiles(distanceMeters: Double): Int {
        if (!distanceMeters.isFinite() || distanceMeters <= 0.0) return 0
        val value = floor(distanceMeters / METERS_PER_MILE)
        return if (value >= Int.MAX_VALUE) Int.MAX_VALUE else value.toInt().coerceAtLeast(0)
    }
}

internal fun formatSpeechElapsed(elapsedMs: Long): String {
    val totalSeconds = elapsedMs.coerceAtLeast(0L) / 1_000L
    val hours = totalSeconds / 3_600L
    val minutes = (totalSeconds % 3_600L) / 60L
    val seconds = totalSeconds % 60L
    val parts = buildList {
        if (hours > 0L) add("$hours ${if (hours == 1L) "hour" else "hours"}")
        if (minutes > 0L) add("$minutes ${if (minutes == 1L) "minute" else "minutes"}")
        if (hours == 0L && minutes == 0L) {
            add("$seconds ${if (seconds == 1L) "second" else "seconds"}")
        }
    }
    return parts.joinToString(" ").ifBlank { String.format(Locale.US, "0 seconds") }
}

private const val METERS_PER_MILE = 1_609.344
