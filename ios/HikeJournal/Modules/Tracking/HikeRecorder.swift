import Foundation
import HikeJournalPersistence
import HikeJournalTracking

enum HikeRecorderError: Error, Equatable, LocalizedError {
    case recordingAlreadyActive
    case noActiveRecording
    case corruptedRecoveryState

    var errorDescription: String? {
        switch self {
        case .recordingAlreadyActive:
            "Finish or discard the current outing before starting another."
        case .noActiveRecording:
            "There is no active outing to update."
        case .corruptedRecoveryState:
            "The saved outing could not be restored safely. Its GPS points remain on this iPhone."
        }
    }
}

struct RecorderUpdate: Equatable, Sendable {
    let snapshot: TrackingSnapshot
    let ingestResult: LocationIngestResult?
    let announcement: MileAnnouncement?
}

struct FinishedRecording: Equatable, Sendable {
    let snapshot: TrackingSnapshot
    let routeURL: URL
}

/// Platform-neutral orchestration between the tracking domain and durable
/// SQLite. Core Location and SwiftUI are adapters around this actor.
actor HikeRecorder {
    private let database: OfflineDatabase
    private let routeDirectory: URL
    private let clock: TrackingClock
    private let idGenerator: TrackingIDGenerator
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder
    private var session: TrackingSession?
    private var announcements = WholeMileAnnouncementScheduler()
    private var mutationInProgress = false
    private var mutationWaiters: [CheckedContinuation<Void, Never>] = []

    init(
        database: OfflineDatabase,
        routeDirectory: URL,
        clock: TrackingClock = .system,
        idGenerator: TrackingIDGenerator = .random
    ) {
        self.database = database
        self.routeDirectory = routeDirectory
        self.clock = clock
        self.idGenerator = idGenerator
        self.encoder = JSONEncoder()
        self.decoder = JSONDecoder()
    }

    func restoreInterruptedRecording() async throws -> TrackingSnapshot? {
        await acquireMutationLock()
        defer { releaseMutationLock() }

        guard let record = try await database.activeTrackingSession() else {
            session = nil
            return nil
        }
        guard let snapshotData = record.domainSnapshot,
              var restored = try? decoder.decode(TrackingSession.self, from: snapshotData),
              restored.sessionID == record.sessionID,
              restored.hikeID == record.hikeID else {
            throw HikeRecorderError.corruptedRecoveryState
        }
        let reading = clock.read()
        restored.recoverAfterInterruption(at: reading)
        session = restored
        announcements = WholeMileAnnouncementScheduler(
            sessionID: restored.sessionID,
            lastAnnouncedMile: completedMiles(restored.distanceMeters)
        )
        try await database.updateTrackingSession(try persistenceRecord(restored))
        return restored.snapshot(at: reading)
    }

    func start() async throws -> TrackingSnapshot {
        await acquireMutationLock()
        defer { releaseMutationLock() }

        guard try await database.activeTrackingSession() == nil, session == nil else {
            throw HikeRecorderError.recordingAlreadyActive
        }
        var started = TrackingSession.start(clock: clock, idGenerator: idGenerator)
        let reading = clock.read()
        try started.beginRecording(at: reading)
        try await database.insertTrackingSession(try persistenceRecord(started))
        session = started
        announcements = WholeMileAnnouncementScheduler(
            sessionID: started.sessionID,
            lastAnnouncedMile: 0
        )
        return started.snapshot(at: reading)
    }

    func currentSnapshot() throws -> TrackingSnapshot? {
        session?.snapshot(at: clock.read())
    }

    func ingest(
        _ sample: LocationSample,
        receivedAt: Date? = nil
    ) async throws -> RecorderUpdate {
        await acquireMutationLock()
        defer { releaseMutationLock() }

        guard var current = session else { throw HikeRecorderError.noActiveRecording }
        let reading = clock.read()
        let result = current.ingest(
            sample,
            receivedAt: receivedAt ?? reading.wallTime
        )

        switch result {
        case .accepted(let point, _):
            current.checkpoint(at: reading)
            let checkpoint = try persistenceRecord(current)
            try await database.recordAcceptedPoint(
                TrackingPointRecord(
                    sessionID: current.sessionID,
                    sequence: point.sequence,
                    segment: point.segment,
                    latitude: point.latitude,
                    longitude: point.longitude,
                    altitudeMeters: point.altitudeMeters,
                    accuracyMeters: point.accuracyMeters,
                    fixAt: point.timestamp,
                    fixMonotonicNanoseconds: point.monotonicTimestampNanoseconds,
                    distanceFromPreviousMeters: point.distanceFromPreviousMeters
                ),
                checkpoint: checkpoint
            )
            session = current
        case .rejected, .ignored:
            break
        }

        let snapshot = current.snapshot(at: reading)
        let announcement = announcements.update(
            sessionID: current.sessionID,
            distanceMeters: snapshot.distanceMeters,
            activeElapsedMilliseconds: snapshot.activeElapsedMilliseconds
        )
        return RecorderUpdate(
            snapshot: snapshot,
            ingestResult: result,
            announcement: announcement
        )
    }

    func pause() async throws -> TrackingSnapshot {
        await acquireMutationLock()
        defer { releaseMutationLock() }

        guard var current = session else { throw HikeRecorderError.noActiveRecording }
        let reading = clock.read()
        try current.pause(at: reading)
        try await database.updateTrackingSession(try persistenceRecord(current))
        session = current
        return current.snapshot(at: reading)
    }

    func resume() async throws -> TrackingSnapshot {
        await acquireMutationLock()
        defer { releaseMutationLock() }

        guard var current = session else { throw HikeRecorderError.noActiveRecording }
        let reading = clock.read()
        try current.resume(at: reading)
        try await database.updateTrackingSession(try persistenceRecord(current))
        session = current
        return current.snapshot(at: reading)
    }

    func addFieldMark(
        type: FieldMarkType,
        note: String = ""
    ) async throws -> FieldMark {
        await acquireMutationLock()
        defer { releaseMutationLock() }

        guard let current = session else { throw HikeRecorderError.noActiveRecording }
        let reading = clock.read()
        let mark = try current.makeFieldMark(
            type: type,
            note: note,
            at: reading,
            idGenerator: idGenerator
        )
        let payload = try JSONSerialization.data(
            withJSONObject: [
                "id": mark.id,
                "recording_session_id": mark.recordingSessionID as Any? ?? NSNull(),
                "marked_at": iso8601(mark.markedAt),
                "lat": mark.latitude,
                "lng": mark.longitude,
                "accuracy_meters": mark.accuracyMeters as Any? ?? NSNull(),
                "mark_type": mark.type.rawValue,
                "note": mark.note,
                "wait_for_hike_create": true,
            ],
            options: [.sortedKeys]
        )
        let record = FieldMarkRecord(
            id: mark.id,
            hikeID: mark.hikeID,
            recordingSessionID: mark.recordingSessionID,
            markedAt: mark.markedAt,
            latitude: mark.latitude,
            longitude: mark.longitude,
            accuracyMeters: mark.accuracyMeters,
            markType: mark.type.rawValue,
            note: mark.note,
            syncState: .queued,
            createdAt: reading.wallTime,
            updatedAt: reading.wallTime
        )
        let operation = PendingOperation(
            id: idGenerator.makeID(),
            kind: .createFieldMark,
            entityID: mark.id,
            parentID: mark.hikeID,
            payload: payload,
            createdAt: reading.wallTime,
            updatedAt: reading.wallTime
        )
        try await database.enqueueFieldMark(record, operation: operation)
        return mark
    }

    func finish(title: String, notes: String = "") async throws -> FinishedRecording {
        await acquireMutationLock()
        defer { releaseMutationLock() }

        guard var current = session else { throw HikeRecorderError.noActiveRecording }
        var reading = clock.read()
        if current.status == .recording {
            try current.pause(at: reading)
        }
        try current.beginFinalization(at: reading)
        try await database.updateTrackingSession(try persistenceRecord(current))

        do {
            let finalizingSnapshot = current.snapshot(at: reading)
            let routeURL = try TCXWriter(directoryURL: routeDirectory).write(
                snapshot: finalizingSnapshot,
                notes: notes.nilIfBlank
            )
            reading = clock.read()
            try current.finish(generatedTCXPath: routeURL.path, at: reading)
            let finishedSnapshot = current.snapshot(at: reading)
            try await database.updateTrackingSession(try persistenceRecord(current))
            try await database.upsertOperationsAtomically(
                try finalizationOperations(
                    session: current,
                    snapshot: finishedSnapshot,
                    title: title,
                    notes: notes,
                    routeURL: routeURL,
                    createdAt: reading.wallTime
                )
            )
            session = nil
            return FinishedRecording(snapshot: finishedSnapshot, routeURL: routeURL)
        } catch {
            reading = clock.read()
            try? current.failFinalization(message: error.localizedDescription, at: reading)
            try? await database.updateTrackingSession(try persistenceRecord(current))
            session = current
            throw error
        }
    }

    func discard() async throws {
        await acquireMutationLock()
        defer { releaseMutationLock() }

        guard let current = session else { throw HikeRecorderError.noActiveRecording }
        try await database.discardActiveRecording(
            hikeID: current.hikeID,
            sessionID: current.sessionID
        )
        session = nil
    }

    /// Swift actors are re-entrant while awaiting another actor. A location
    /// callback can therefore enter while the previous callback is committing
    /// its point to SQLite, before `session` has been advanced. Serialize all
    /// mutations that depend on the in-memory session so each durable point
    /// gets exactly one sequence number and Save cannot overtake a GPS write.
    private func acquireMutationLock() async {
        guard mutationInProgress else {
            mutationInProgress = true
            return
        }
        await withCheckedContinuation { continuation in
            mutationWaiters.append(continuation)
        }
    }

    private func releaseMutationLock() {
        guard !mutationWaiters.isEmpty else {
            mutationInProgress = false
            return
        }
        mutationWaiters.removeFirst().resume()
    }

    private func persistenceRecord(_ session: TrackingSession) throws -> TrackingSessionRecord {
        let status = PersistedTrackingStatus(rawValue: session.status.rawValue) ?? .paused
        return TrackingSessionRecord(
            sessionID: session.sessionID,
            hikeID: session.hikeID,
            activeSlot: session.status == .finished ? nil : 1,
            status: status,
            startedAt: session.startedAt,
            startedAtMonotonicMilliseconds: session.startedAtMonotonicMilliseconds,
            hikeDate: session.hikeDate,
            bootIdentifier: session.bootIdentifier,
            activeElapsedMilliseconds: session.checkpointedActiveElapsedMilliseconds,
            activeSinceMonotonicMilliseconds: session.activeSinceMonotonicMilliseconds,
            distanceMeters: session.distanceMeters,
            currentSegment: session.currentSegment,
            segmentStartPending: session.segmentStartPending,
            nextPointSequence: session.nextPointSequence,
            lastFixAt: session.lastAcceptedPoint?.timestamp,
            lastFixMonotonicNanoseconds: session.lastAcceptedPoint?.monotonicTimestampNanoseconds,
            lastAccuracyMeters: session.lastAcceptedPoint?.accuracyMeters,
            finishedAt: session.finishedAt,
            generatedTCXPath: session.generatedTCXPath,
            recoveryReason: session.recoveryReason?.rawValue,
            errorMessage: session.errorMessage,
            updatedAt: session.updatedAt,
            domainSnapshot: try encoder.encode(session)
        )
    }

    private func finalizationOperations(
        session: TrackingSession,
        snapshot: TrackingSnapshot,
        title: String,
        notes: String,
        routeURL: URL,
        createdAt: Date
    ) throws -> [PendingOperation] {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let createPayload = try JSONSerialization.data(
            withJSONObject: [
                "title": trimmedTitle.isEmpty ? "Recorded outing" : trimmedTitle,
                "hike_date": session.hikeDate,
                "distance_miles": snapshot.distanceMeters / WholeMileAnnouncementScheduler.metersPerMile,
                "location_name": "",
                "notes": notes.trimmingCharacters(in: .whitespacesAndNewlines),
                "location_id": NSNull(),
            ],
            options: [.sortedKeys]
        )
        let routePayload = try JSONSerialization.data(
            withJSONObject: [
                "source_type": "hikejournal_ios_gps",
                "started_at": iso8601(snapshot.startedAt),
                "duration_seconds": snapshot.activeElapsedMilliseconds / 1_000,
                "distance_miles": snapshot.distanceMeters / WholeMileAnnouncementScheduler.metersPerMile,
                "track_point_count": snapshot.pointCount,
                "route_segments": snapshot.routeSegments.map { segment in
                    segment.map { point in
                        var value: [String: Any] = [
                            "lat": point.latitude,
                            "lng": point.longitude,
                            "timestamp": iso8601(point.timestamp),
                        ]
                        if let altitude = point.altitudeMeters {
                            value["altitude_meters"] = altitude
                        }
                        return value
                    }
                },
            ],
            options: [.sortedKeys]
        )
        return [
            PendingOperation(
                id: idGenerator.makeID(),
                kind: .createHike,
                entityID: session.hikeID,
                payload: createPayload,
                createdAt: createdAt,
                updatedAt: createdAt
            ),
            PendingOperation(
                id: idGenerator.makeID(),
                kind: .uploadRoute,
                entityID: "recorded-route:\(session.hikeID)",
                parentID: session.hikeID,
                payload: routePayload,
                localFilePath: routeURL.path,
                contentType: "application/vnd.garmin.tcx+xml",
                fileName: "hikejournal-recording.tcx",
                createdAt: createdAt.addingTimeInterval(0.001),
                updatedAt: createdAt.addingTimeInterval(0.001)
            ),
        ]
    }

    private func completedMiles(_ meters: Double) -> Int {
        guard meters.isFinite, meters > 0 else { return 0 }
        return Int(floor(meters / WholeMileAnnouncementScheduler.metersPerMile))
    }

    private func iso8601(_ date: Date) -> String {
        ISO8601DateFormatter().string(from: date)
    }
}

private extension String {
    var nilIfBlank: String? {
        let value = trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? nil : value
    }
}
