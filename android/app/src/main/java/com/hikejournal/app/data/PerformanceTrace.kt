package com.hikejournal.app.data

import android.os.SystemClock
import android.util.Log
import kotlinx.coroutines.sync.Mutex

/** Lightweight release-log timings for diagnosing cold-load latency. Never log payloads or auth data. */
internal object PerformanceTrace {
    private const val Tag = "HikeJournalPerf"

    fun start(): Long = SystemClock.elapsedRealtimeNanos()

    fun elapsedMs(startedAtNanos: Long): Double =
        (SystemClock.elapsedRealtimeNanos() - startedAtNanos) / 1_000_000.0

    fun record(event: String, durationMs: Double, details: String = "") {
        val suffix = details.takeIf(String::isNotBlank)?.let { " $it" }.orEmpty()
        Log.i(Tag, "$event duration_ms=${"%.2f".format(java.util.Locale.US, durationMs)}$suffix")
    }

    fun recordSince(event: String, startedAtNanos: Long, details: String = "") =
        record(event, elapsedMs(startedAtNanos), details)
}

internal suspend fun <T> Mutex.withMeasuredLock(
    operation: String,
    block: suspend () -> T,
): T {
    val queuedAt = PerformanceTrace.start()
    lock()
    val waitMs = PerformanceTrace.elapsedMs(queuedAt)
    if (waitMs >= 5.0) PerformanceTrace.record("cache_lock_wait", waitMs, "operation=$operation")
    return try {
        block()
    } finally {
        unlock()
    }
}
