package com.hikejournal.app.tracking

import android.content.Context
import android.location.Location
import android.os.SystemClock
import android.provider.Settings
import androidx.room.withTransaction
import com.hikejournal.app.data.local.OfflineDatabase
import com.hikejournal.app.data.local.TrackingPointEntity
import com.hikejournal.app.data.local.TrackingSessionEntity
import java.io.File
import java.time.Instant
import java.time.ZoneId
import java.util.UUID
import kotlinx.coroutines.delay
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn

@OptIn(ExperimentalCoroutinesApi::class)
class TrackingRepository private constructor(
    private val appContext: Context,
) {
    private val database = OfflineDatabase.get(appContext)
    private val dao = database.tracking()
    private val clock = AndroidTrackingClock(appContext)
    private val locationFilter = TrackingLocationFilter()
    private val tcxWriter = TcxWriter(File(appContext.filesDir, "tracking/routes"))
    private val repositoryScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /**
     * The current non-finished recording. While recording, elapsed time updates once a second
     * without writing to the database; durable time checkpoints are handled by the service.
     */
    val snapshots: Flow<TrackingSnapshot?> = dao.observeActiveSession()
        .flatMapLatest { session ->
            if (session == null) {
                flowOf(null)
            } else {
                dao.observePoints(session.sessionId).flatMapLatest { points ->
                    val routeSegments = groupPoints(points)
                    if (parseStatus(session.status) == TrackingStatus.RECORDING) {
                        flow {
                            while (true) {
                                emit(toSnapshot(session, routeSegments, points.size))
                                delay(SNAPSHOT_TICK_MS)
                            }
                        }
                    } else {
                        flowOf(toSnapshot(session, routeSegments, points.size))
                    }
                }
            }
        }
        .distinctUntilChanged()
        .stateIn(
            scope = repositoryScope,
            started = SharingStarted.WhileSubscribed(stopTimeoutMillis = 5_000L),
            initialValue = null,
        )

    suspend fun start(): TrackingSnapshot {
        val prerequisites = TrackingPrerequisites.check(appContext)
        if (!prerequisites.allSatisfied) throw TrackingPrerequisiteException(prerequisites)

        val nowEpochMs = clock.epochMillis()
        val nowElapsedMs = clock.elapsedRealtimeMillis()
        val session = database.withTransaction {
            if (dao.activeSession() != null) {
                throw TrackingStateException("A hike is already in progress")
            }
            val created = TrackingSessionEntity(
                sessionId = UUID.randomUUID().toString(),
                hikeId = UUID.randomUUID().toString(),
                activeSlot = ACTIVE_SLOT,
                status = TrackingStatus.STARTING.name,
                startedAtEpochMs = nowEpochMs,
                startedAtElapsedRealtimeMs = nowElapsedMs,
                hikeDate = Instant.ofEpochMilli(nowEpochMs)
                    .atZone(ZoneId.systemDefault())
                    .toLocalDate()
                    .toString(),
                bootCount = clock.bootCount(),
                activeElapsedMs = 0L,
                activeSinceElapsedRealtimeMs = null,
                distanceMeters = 0.0,
                currentSegment = 0,
                segmentStartPending = true,
                nextPointSequence = 0L,
                lastFixEpochMs = null,
                lastFixElapsedRealtimeNanos = null,
                lastAccuracyMeters = null,
                finishedAtEpochMs = null,
                generatedTcxPath = null,
                recoveryReason = null,
                error = null,
                updatedAtEpochMs = nowEpochMs,
            )
            dao.insertSession(created)
            created
        }
        try {
            HikeTrackingService.start(appContext)
        } catch (error: RuntimeException) {
            database.withTransaction {
                dao.activeSession()?.takeIf { it.sessionId == session.sessionId }?.let { current ->
                    dao.updateSession(
                        current.copy(
                            status = TrackingStatus.PAUSED.name,
                            error = error.message ?: "Unable to start foreground recording",
                            recoveryReason = "service_start_failed",
                            updatedAtEpochMs = clock.epochMillis(),
                        ),
                    )
                }
            }
            throw TrackingStateException(error.message ?: "Unable to start foreground recording")
        }
        return snapshotFor(session)
    }

    suspend fun pause(): TrackingSnapshot = transition(
        target = TrackingStatus.PAUSED,
        allowed = setOf(TrackingStatus.RECORDING),
    ) { current, nowEpochMs, nowElapsedMs ->
        current.copy(
            status = TrackingStatus.PAUSED.name,
            activeElapsedMs = activeElapsedAt(current, nowElapsedMs),
            activeSinceElapsedRealtimeMs = null,
            updatedAtEpochMs = nowEpochMs,
        )
    }

    suspend fun resume(): TrackingSnapshot {
        val prerequisites = TrackingPrerequisites.check(appContext)
        if (!prerequisites.allSatisfied) throw TrackingPrerequisiteException(prerequisites)
        HikeTrackingService.start(appContext)
        return resumeTransition()
    }

    internal suspend fun resumeFromService(): TrackingSnapshot {
        val prerequisites = TrackingPrerequisites.check(appContext)
        if (!prerequisites.allSatisfied) throw TrackingPrerequisiteException(prerequisites)
        return resumeTransition()
    }

    private suspend fun resumeTransition(): TrackingSnapshot = transition(
            target = TrackingStatus.RECORDING,
            allowed = setOf(TrackingStatus.PAUSED),
        ) { current, nowEpochMs, nowElapsedMs ->
            current.copy(
                status = TrackingStatus.RECORDING.name,
                bootCount = clock.bootCount(),
                activeSinceElapsedRealtimeMs = nowElapsedMs,
                currentSegment = current.currentSegment + 1,
                segmentStartPending = true,
                recoveryReason = null,
                error = null,
                updatedAtEpochMs = nowEpochMs,
            )
        }

    suspend fun markFinalizing(): TrackingSnapshot = transition(
        target = TrackingStatus.FINALIZING,
        allowed = setOf(TrackingStatus.PAUSED),
    ) { current, nowEpochMs, _ ->
        current.copy(
            status = TrackingStatus.FINALIZING.name,
            error = null,
            updatedAtEpochMs = nowEpochMs,
        )
    }

    suspend fun failFinalization(message: String): TrackingSnapshot = transition(
        target = TrackingStatus.PAUSED,
        allowed = setOf(TrackingStatus.FINALIZING),
    ) { current, nowEpochMs, _ ->
        current.copy(
            status = TrackingStatus.PAUSED.name,
            recoveryReason = "finalization_failed",
            error = message,
            updatedAtEpochMs = nowEpochMs,
        )
    }

    suspend fun markFinished(generatedTcxPath: String? = null): TrackingSnapshot {
        val snapshot = transition(
            target = TrackingStatus.FINISHED,
            allowed = setOf(TrackingStatus.FINALIZING),
        ) { current, nowEpochMs, _ ->
            current.copy(
                activeSlot = null,
                status = TrackingStatus.FINISHED.name,
                finishedAtEpochMs = nowEpochMs,
                generatedTcxPath = generatedTcxPath ?: current.generatedTcxPath,
                recoveryReason = null,
                error = null,
                updatedAtEpochMs = nowEpochMs,
            )
        }
        HikeTrackingService.stopAfterFinished(appContext)
        return snapshot
    }

    /** Permanently removes an in-progress recording and its route points. */
    suspend fun discard() {
        val discarded = database.withTransaction {
            val current = dao.activeSession() ?: throw TrackingStateException("There is no hike in progress")
            dao.discardActive(current.sessionId)
        }
        if (discarded == 0) throw TrackingStateException("The hike could not be discarded")
        HikeTrackingService.stopAfterDiscard(appContext)
    }

    suspend fun recover(): TrackingSnapshot? {
        val nowEpochMs = clock.epochMillis()
        val nowElapsedMs = clock.elapsedRealtimeMillis()
        val prerequisites = TrackingPrerequisites.check(appContext)
        val recovered = database.withTransaction {
            val current = dao.activeSession() ?: return@withTransaction null
            val status = parseStatus(current.status)
            val updated = when {
                status == TrackingStatus.FINALIZING -> current.copy(
                    status = TrackingStatus.PAUSED.name,
                    recoveryReason = "finalization_interrupted",
                    error = "Hike finalization was interrupted",
                    updatedAtEpochMs = nowEpochMs,
                )
                status != TrackingStatus.RECORDING && status != TrackingStatus.STARTING -> current
                current.bootCount != clock.bootCount() ||
                    nowElapsedMs < current.startedAtElapsedRealtimeMs -> current.copy(
                    status = TrackingStatus.PAUSED.name,
                    activeSinceElapsedRealtimeMs = null,
                    recoveryReason = "device_restarted",
                    error = null,
                    updatedAtEpochMs = nowEpochMs,
                )
                !prerequisites.fineLocationGranted -> pauseRecovered(
                    current,
                    nowEpochMs,
                    "permission_revoked",
                )
                !prerequisites.notificationsGranted -> pauseRecovered(
                    current,
                    nowEpochMs,
                    "notification_permission_revoked",
                )
                !prerequisites.locationEnabled -> pauseRecovered(
                    current,
                    nowEpochMs,
                    "location_disabled",
                )
                nowEpochMs - current.updatedAtEpochMs > MAX_RECOVERY_GAP_MS -> pauseRecovered(
                    current,
                    nowEpochMs,
                    "service_interrupted",
                )
                else -> current
            }
            if (updated != current) dao.updateSession(updated)
            updated
        }
        return if (recovered == null) null else snapshotFor(recovered)
    }

    internal suspend fun pauseAfterServiceFailure(message: String): TrackingSnapshot? {
        val paused = database.withTransaction {
            val current = dao.activeSession() ?: return@withTransaction null
            val status = parseStatus(current.status)
            if (status !in setOf(TrackingStatus.STARTING, TrackingStatus.RECORDING)) {
                return@withTransaction current
            }
            current.copy(
                status = TrackingStatus.PAUSED.name,
                activeElapsedMs = TrackingRecoveryMath.pausedElapsedMs(current.activeElapsedMs),
                activeSinceElapsedRealtimeMs = null,
                recoveryReason = "service_start_failed",
                error = message,
                updatedAtEpochMs = clock.epochMillis(),
            ).also { dao.updateSession(it) }
        }
        return paused?.let { snapshotFor(it) }
    }

    suspend fun current(): TrackingSnapshot? {
        val session = dao.activeSession() ?: return null
        return snapshotFor(session)
    }

    suspend fun finished(hikeId: String): TrackingSnapshot? {
        val session = dao.finishedSession(hikeId) ?: return null
        return snapshotFor(session)
    }

    fun observeRouteByHikeId(hikeId: String): Flow<List<List<TrackingPoint>>> = flow {
        val session = dao.finishedSession(hikeId)
        if (session == null) {
            emit(emptyList())
        } else {
            emitAllPoints(session.sessionId)
        }
    }

    suspend fun routeByHikeId(hikeId: String): List<List<TrackingPoint>> {
        val session = dao.finishedSession(hikeId) ?: return emptyList()
        return groupPoints(dao.points(session.sessionId))
    }

    suspend fun allFinishedRoutes(): List<List<TrackingPoint>> =
        dao.finishedSessions(null).flatMap { session -> groupPoints(dao.points(session.sessionId)) }

    suspend fun allFinishedRoutesByHikeId(): Map<String, List<List<TrackingPoint>>> =
        dao.finishedSessions(null).associate { session ->
            session.hikeId to groupPoints(dao.points(session.sessionId))
        }

    fun routeSegments(sessionId: String): Flow<List<List<TrackingPoint>>> =
        dao.observePoints(sessionId).map(::groupPoints)

    suspend fun generateTcx(sessionId: String): File? {
        val session = dao.session(sessionId)
            ?: throw TrackingStateException("Unknown tracking session $sessionId")
        val snapshot = snapshotFor(session)
        if (snapshot.routeSegments.none { it.size >= 2 }) return null
        return tcxWriter.write(snapshot)
    }

    suspend fun clearFinished(hikeId: String? = null) {
        val generatedFiles = database.withTransaction {
            val files = dao.finishedSessions(hikeId).mapNotNull { it.generatedTcxPath }
            dao.clearFinished(hikeId)
            files
        }
        generatedFiles.forEach { path ->
            val file = File(path)
            val routeDirectory = File(appContext.filesDir, "tracking/routes")
            if (file.parentFile?.canonicalFile == routeDirectory.canonicalFile) file.delete()
        }
    }

    internal suspend fun beginRecording(): TrackingSnapshot {
        val current = dao.activeSession()
            ?: throw TrackingStateException("There is no hike to start")
        if (parseStatus(current.status) == TrackingStatus.RECORDING) return snapshotFor(current)
        return transition(
            target = TrackingStatus.RECORDING,
            allowed = setOf(TrackingStatus.STARTING),
        ) { entity, nowEpochMs, nowElapsedMs ->
            entity.copy(
                status = TrackingStatus.RECORDING.name,
                activeSinceElapsedRealtimeMs = nowElapsedMs,
                bootCount = clock.bootCount(),
                updatedAtEpochMs = nowEpochMs,
            )
        }
    }

    internal suspend fun checkpoint(): TrackingSnapshot? {
        val current = dao.activeSession() ?: return null
        if (parseStatus(current.status) != TrackingStatus.RECORDING) return snapshotFor(current)
        if (current.bootCount != clock.bootCount()) return recover()
        return transition(
            target = TrackingStatus.RECORDING,
            allowed = setOf(TrackingStatus.RECORDING),
        ) { entity, nowEpochMs, nowElapsedMs ->
            entity.copy(
                activeElapsedMs = activeElapsedAt(entity, nowElapsedMs),
                activeSinceElapsedRealtimeMs = nowElapsedMs,
                updatedAtEpochMs = nowEpochMs,
            )
        }
    }

    internal suspend fun acceptLocation(location: Location): Boolean {
        val fix = RawTrackingFix(
            latitude = location.latitude,
            longitude = location.longitude,
            altitudeMeters = location.altitude.takeIf { location.hasAltitude() && it.isFinite() },
            accuracyMeters = location.accuracy.takeIf { location.hasAccuracy() } ?: Float.POSITIVE_INFINITY,
            fixEpochMs = location.time,
            fixElapsedRealtimeNanos = location.elapsedRealtimeNanos,
        )
        return database.withTransaction {
            val session = dao.activeSession() ?: return@withTransaction false
            if (parseStatus(session.status) != TrackingStatus.RECORDING) return@withTransaction false
            val lastEntity = dao.lastPoint(session.sessionId)
            val filtered = locationFilter.evaluate(
                fix = fix,
                receivedAtEpochMs = clock.epochMillis(),
                last = lastEntity?.toRawFix(),
                currentSegment = session.currentSegment,
                segmentStartPending = session.segmentStartPending,
            )
            if (filtered !is FilteredFix.Accepted) return@withTransaction false
            val point = TrackingPointEntity(
                sessionId = session.sessionId,
                sequence = session.nextPointSequence,
                segment = filtered.segment,
                latitude = fix.latitude,
                longitude = fix.longitude,
                altitudeMeters = fix.altitudeMeters,
                accuracyMeters = fix.accuracyMeters,
                fixEpochMs = fix.fixEpochMs,
                fixElapsedRealtimeNanos = fix.fixElapsedRealtimeNanos,
                distanceFromPreviousMeters = filtered.distanceFromPreviousMeters,
            )
            dao.insertPoint(point)
            dao.updateSession(
                session.copy(
                    distanceMeters = session.distanceMeters + filtered.distanceFromPreviousMeters,
                    currentSegment = filtered.segment,
                    segmentStartPending = false,
                    nextPointSequence = session.nextPointSequence + 1,
                    lastFixEpochMs = fix.fixEpochMs,
                    lastFixElapsedRealtimeNanos = fix.fixElapsedRealtimeNanos,
                    lastAccuracyMeters = fix.accuracyMeters,
                    updatedAtEpochMs = clock.epochMillis(),
                ),
            )
            true
        }
    }

    private suspend fun transition(
        target: TrackingStatus,
        allowed: Set<TrackingStatus>,
        update: (TrackingSessionEntity, Long, Long) -> TrackingSessionEntity,
    ): TrackingSnapshot {
        val entity = database.withTransaction {
            val current = dao.activeSession()
                ?: throw TrackingStateException("There is no hike in progress")
            val status = parseStatus(current.status)
            TrackingTransitions.require(status, target, *allowed.toTypedArray())
            update(current, clock.epochMillis(), clock.elapsedRealtimeMillis())
                .also { dao.updateSession(it) }
        }
        return snapshotFor(entity)
    }

    private fun pauseRecovered(
        current: TrackingSessionEntity,
        nowEpochMs: Long,
        reason: String,
    ): TrackingSessionEntity = current.copy(
        status = TrackingStatus.PAUSED.name,
        // Recovery cannot prove the service was alive after its last durable checkpoint. Preserve
        // only checkpointed active time so a force-stop gap is never counted as hiking time.
        activeElapsedMs = TrackingRecoveryMath.pausedElapsedMs(current.activeElapsedMs),
        activeSinceElapsedRealtimeMs = null,
        recoveryReason = reason,
        error = null,
        updatedAtEpochMs = nowEpochMs,
    )

    private suspend fun snapshotFor(session: TrackingSessionEntity): TrackingSnapshot =
        toSnapshot(session, dao.points(session.sessionId))

    private fun toSnapshot(
        session: TrackingSessionEntity,
        points: List<TrackingPointEntity>,
    ): TrackingSnapshot = toSnapshot(session, groupPoints(points), points.size)

    private fun toSnapshot(
        session: TrackingSessionEntity,
        routeSegments: List<List<TrackingPoint>>,
        pointCount: Int,
    ): TrackingSnapshot = TrackingSnapshot(
        sessionId = session.sessionId,
        hikeId = session.hikeId,
        status = parseStatus(session.status),
        startedAtEpochMs = session.startedAtEpochMs,
        hikeDate = session.hikeDate,
        distanceMeters = session.distanceMeters,
        activeElapsedMs = activeElapsedAt(session, clock.elapsedRealtimeMillis()),
        currentSegment = session.currentSegment,
        routeSegments = routeSegments,
        lastAccuracyMeters = session.lastAccuracyMeters,
        lastFixEpochMs = session.lastFixEpochMs,
        pointCount = pointCount,
        generatedTcxPath = session.generatedTcxPath,
        recoveryReason = session.recoveryReason,
        error = session.error,
    )

    private fun activeElapsedAt(session: TrackingSessionEntity, nowElapsedMs: Long): Long =
        TrackingTimeMath.activeElapsedMs(
            accumulatedMs = session.activeElapsedMs,
            activeSinceElapsedRealtimeMs = session.activeSinceElapsedRealtimeMs,
            status = parseStatus(session.status),
            sameBoot = session.bootCount == clock.bootCount(),
            nowElapsedRealtimeMs = nowElapsedMs,
        )

    private fun groupPoints(points: List<TrackingPointEntity>): List<List<TrackingPoint>> = points
        .groupBy { it.segment }
        .toSortedMap()
        .values
        .map { segment -> segment.sortedBy { it.sequence }.map(TrackingPointEntity::toPublicPoint) }

    private suspend fun kotlinx.coroutines.flow.FlowCollector<List<List<TrackingPoint>>>.emitAllPoints(
        sessionId: String,
    ) {
        dao.observePoints(sessionId).map(::groupPoints).collect(::emit)
    }

    private fun parseStatus(value: String): TrackingStatus = try {
        TrackingStatus.valueOf(value)
    } catch (_: IllegalArgumentException) {
        throw TrackingStateException("Unknown persisted tracking state: $value")
    }

    companion object {
        private const val ACTIVE_SLOT = 1
        private const val SNAPSHOT_TICK_MS = 1_000L
        private const val MAX_RECOVERY_GAP_MS = 45_000L

        @Volatile private var instance: TrackingRepository? = null

        fun get(context: Context): TrackingRepository = instance ?: synchronized(this) {
            instance ?: TrackingRepository(context.applicationContext).also { instance = it }
        }
    }
}

private fun TrackingPointEntity.toRawFix() = RawTrackingFix(
    latitude = latitude,
    longitude = longitude,
    altitudeMeters = altitudeMeters,
    accuracyMeters = accuracyMeters,
    fixEpochMs = fixEpochMs,
    fixElapsedRealtimeNanos = fixElapsedRealtimeNanos,
)

private fun TrackingPointEntity.toPublicPoint() = TrackingPoint(
    sequence = sequence,
    segment = segment,
    latitude = latitude,
    longitude = longitude,
    altitudeMeters = altitudeMeters,
    accuracyMeters = accuracyMeters,
    fixEpochMs = fixEpochMs,
)

private class AndroidTrackingClock(context: Context) {
    private val contentResolver = context.contentResolver

    fun epochMillis(): Long = System.currentTimeMillis()

    fun elapsedRealtimeMillis(): Long = SystemClock.elapsedRealtime()

    fun bootCount(): Int = Settings.Global.getInt(
        contentResolver,
        Settings.Global.BOOT_COUNT,
        fallbackBootMarker(),
    )

    private fun fallbackBootMarker(): Int =
        ((epochMillis() - elapsedRealtimeMillis()) / (5 * 60_000L)).toInt()
}
