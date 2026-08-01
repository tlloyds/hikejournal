package com.hikejournal.app.tracking

enum class TrackingStatus {
    STARTING,
    RECORDING,
    PAUSED,
    FINALIZING,
    FINISHED,
}
data class TrackingPoint(
    val sequence: Long,
    val segment: Int,
    val latitude: Double,
    val longitude: Double,
    val altitudeMeters: Double?,
    val accuracyMeters: Float,
    val fixEpochMs: Long,
)

data class TrackingSnapshot(
    val sessionId: String,
    val hikeId: String,
    val status: TrackingStatus,
    val startedAtEpochMs: Long,
    val hikeDate: String,
    val distanceMeters: Double,
    val activeElapsedMs: Long,
    val currentSegment: Int,
    val routeSegments: List<List<TrackingPoint>>,
    val lastAccuracyMeters: Float?,
    val lastFixEpochMs: Long?,
    val pointCount: Int,
    val generatedTcxPath: String?,
    val recoveryReason: String?,
    val error: String?,
)

data class TrackingPrerequisiteState(
    val fineLocationGranted: Boolean,
    val notificationsGranted: Boolean,
    val locationEnabled: Boolean,
) {
    val allSatisfied: Boolean
        get() = fineLocationGranted && notificationsGranted && locationEnabled
}

class TrackingPrerequisiteException(
    val prerequisites: TrackingPrerequisiteState,
) : IllegalStateException("Location, notification, and GPS prerequisites must be satisfied")

class TrackingStateException(message: String) : IllegalStateException(message)

internal object TrackingTransitions {
    fun require(status: TrackingStatus, target: TrackingStatus, vararg allowed: TrackingStatus) {
        if (status !in allowed) {
            throw TrackingStateException("Cannot transition from $status to $target")
        }
    }
}
