import Foundation
import SQLite3

/// A serialized, WAL-backed store for safety-critical recording state and the
/// durable mutation queue. Each signed-in account should receive its own file.
public actor OfflineDatabase {
    public static let currentSchemaVersion = 2

    private let connection: SQLiteConnection

    public init(path: String) throws {
        connection = try SQLiteConnection(path: path)
        try Self.migrate(connection)
    }

    public static func accountDatabaseURL(
        applicationSupportDirectory: URL,
        canonicalUserID: UUID
    ) -> URL {
        applicationSupportDirectory
            .appendingPathComponent("HikeJournal", isDirectory: true)
            .appendingPathComponent("Accounts", isDirectory: true)
            .appendingPathComponent(canonicalUserID.uuidString.lowercased(), isDirectory: true)
            .appendingPathComponent("offline.sqlite", isDirectory: false)
    }

    public func close() {
        connection.close()
    }

    public func schemaVersion() throws -> Int {
        let statement = try connection.prepare("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")
        guard try statement.step() == SQLITE_ROW else { return 0 }
        return Int(statement.int64(0))
    }

    // MARK: - Mutation queue

    public func upsertOperation(_ operation: PendingOperation) throws {
        let statement = try connection.prepare(
            """
            INSERT INTO pending_operations (
                id, kind, entity_id, parent_id, payload, local_file_path,
                content_type, file_name, state, attempt_count, created_at,
                updated_at, last_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind = excluded.kind,
                entity_id = excluded.entity_id,
                parent_id = excluded.parent_id,
                payload = excluded.payload,
                local_file_path = excluded.local_file_path,
                content_type = excluded.content_type,
                file_name = excluded.file_name,
                state = excluded.state,
                attempt_count = excluded.attempt_count,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                last_error = excluded.last_error
            """
        )
        try bind(operation, to: statement)
        try statement.stepToCompletion()
    }

    public func upsertOperationsAtomically(_ operations: [PendingOperation]) throws {
        guard !operations.isEmpty else { return }
        try connection.transaction {
            for operation in operations {
                try upsertOperation(operation)
            }
        }
    }

    public func operation(id: String) throws -> PendingOperation? {
        let statement = try connection.prepare(
            "SELECT \(Self.pendingColumns) FROM pending_operations WHERE id = ? LIMIT 1"
        )
        try statement.bind(id, at: 1)
        guard try statement.step() == SQLITE_ROW else { return nil }
        return try decodeOperation(statement)
    }

    public func operations() throws -> [PendingOperation] {
        try operations(
            sql: "SELECT \(Self.pendingColumns) FROM pending_operations ORDER BY created_at, id"
        )
    }

    public func operations(forHikeID hikeID: String) throws -> [PendingOperation] {
        let statement = try connection.prepare(
            """
            SELECT \(Self.pendingColumns) FROM pending_operations
            WHERE entity_id = ? OR parent_id = ?
            ORDER BY created_at, id
            """
        )
        try statement.bind(hikeID, at: 1)
        try statement.bind(hikeID, at: 2)
        return try decodeOperations(statement)
    }

    public func operationsNeedingAttention() throws -> [PendingOperation] {
        let statement = try connection.prepare(
            """
            SELECT \(Self.pendingColumns) FROM pending_operations
            WHERE state = 'needs_attention'
            ORDER BY created_at, id
            """
        )
        return try decodeOperations(statement)
    }

    public func nextOperations(
        prioritizedPhotoID: String? = nil,
        maximumParallelPhotoUploads: Int = 2
    ) throws -> [PendingOperation] {
        SyncQueuePlanner.nextBatch(
            from: try operations(),
            prioritizedPhotoID: prioritizedPhotoID,
            maximumParallelPhotoUploads: maximumParallelPhotoUploads
        )
    }

    public func updateOperationState(
        id: String,
        state: PendingOperationState,
        attemptCount: Int,
        updatedAt: Date,
        lastError: String?
    ) throws {
        let statement = try connection.prepare(
            """
            UPDATE pending_operations
            SET state = ?, attempt_count = ?, updated_at = ?, last_error = ?
            WHERE id = ?
            """
        )
        try statement.bind(state.rawValue, at: 1)
        try statement.bind(attemptCount, at: 2)
        try statement.bind(updatedAt.timeIntervalSince1970, at: 3)
        try statement.bind(lastError, at: 4)
        try statement.bind(id, at: 5)
        try statement.stepToCompletion()
    }

    public func retryOperationsNeedingAttention(updatedAt: Date) throws {
        let statement = try connection.prepare(
            """
            UPDATE pending_operations
            SET state = 'queued', attempt_count = 0, last_error = NULL, updated_at = ?
            WHERE state = 'needs_attention'
            """
        )
        try statement.bind(updatedAt.timeIntervalSince1970, at: 1)
        try statement.stepToCompletion()
    }

    public func deleteOperation(id: String) throws {
        let statement = try connection.prepare("DELETE FROM pending_operations WHERE id = ?")
        try statement.bind(id, at: 1)
        try statement.stepToCompletion()
    }

    public func discardOperationNeedingAttention(id: String) throws {
        let statement = try connection.prepare(
            "DELETE FROM pending_operations WHERE id = ? AND state = 'needs_attention'"
        )
        try statement.bind(id, at: 1)
        try statement.stepToCompletion()
    }

    public func deleteChildOperations(kind: PendingOperationKind, hikeID: String) throws {
        let statement = try connection.prepare(
            "DELETE FROM pending_operations WHERE kind = ? AND parent_id = ?"
        )
        try statement.bind(kind.rawValue, at: 1)
        try statement.bind(hikeID, at: 2)
        try statement.stepToCompletion()
    }

    public func deleteReplaceableOperation(kind: PendingOperationKind, entityID: String) throws {
        let statement = try connection.prepare(
            """
            DELETE FROM pending_operations
            WHERE kind = ? AND entity_id = ? AND state IN ('queued', 'needs_attention')
            """
        )
        try statement.bind(kind.rawValue, at: 1)
        try statement.bind(entityID, at: 2)
        try statement.stepToCompletion()
    }

    public func queueSummary() throws -> SyncQueueSummary {
        let statement = try connection.prepare(
            "SELECT state, COUNT(*) FROM pending_operations GROUP BY state"
        )
        var queued = 0
        var syncing = 0
        var needsAttention = 0
        while try statement.step() == SQLITE_ROW {
            switch statement.string(0) {
            case PendingOperationState.queued.rawValue:
                queued = Int(statement.int64(1))
            case PendingOperationState.syncing.rawValue:
                syncing = Int(statement.int64(1))
            case PendingOperationState.needsAttention.rawValue:
                needsAttention = Int(statement.int64(1))
            default:
                break
            }
        }
        return SyncQueueSummary(
            queued: queued,
            syncing: syncing,
            needsAttention: needsAttention
        )
    }

    // MARK: - Tracking

    public func insertTrackingSession(_ session: TrackingSessionRecord) throws {
        let statement = try connection.prepare(
            """
            INSERT INTO tracking_sessions (
                session_id, hike_id, active_slot, status, started_at,
                started_at_monotonic_ms, hike_date, boot_identifier,
                active_elapsed_ms, active_since_monotonic_ms, distance_meters,
                current_segment, segment_start_pending, next_point_sequence,
                last_fix_at, last_fix_monotonic_ns, last_accuracy_meters,
                finished_at, generated_tcx_path, recovery_reason, error_message,
                updated_at, domain_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        try bind(session, to: statement)
        try statement.stepToCompletion()
    }

    public func updateTrackingSession(_ session: TrackingSessionRecord) throws {
        let statement = try connection.prepare(
            """
            UPDATE tracking_sessions SET
                hike_id = ?, active_slot = ?, status = ?, started_at = ?,
                started_at_monotonic_ms = ?, hike_date = ?, boot_identifier = ?,
                active_elapsed_ms = ?, active_since_monotonic_ms = ?,
                distance_meters = ?, current_segment = ?, segment_start_pending = ?,
                next_point_sequence = ?, last_fix_at = ?, last_fix_monotonic_ns = ?,
                last_accuracy_meters = ?, finished_at = ?, generated_tcx_path = ?,
                recovery_reason = ?, error_message = ?, updated_at = ?,
                domain_snapshot = ?
            WHERE session_id = ?
            """
        )
        try bindSessionUpdate(session, to: statement)
        try statement.stepToCompletion()
    }

    /// Commits an accepted GPS point and its derived checkpoint as one FULL
    /// synchronous SQLite transaction. A crash cannot leave their state split.
    public func recordAcceptedPoint(
        _ point: TrackingPointRecord,
        checkpoint: TrackingSessionRecord
    ) throws {
        guard point.sessionID == checkpoint.sessionID else {
            throw OfflineStoreError.invalidStoredValue(
                table: "tracking_points",
                column: "session_id",
                value: point.sessionID
            )
        }
        try connection.transaction {
            let pointStatement = try connection.prepare(
                """
                INSERT INTO tracking_points (
                    session_id, sequence, segment, latitude, longitude,
                    altitude_meters, accuracy_meters, fix_at,
                    fix_monotonic_ns, distance_from_previous_meters
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
            )
            try pointStatement.bind(point.sessionID, at: 1)
            try pointStatement.bind(point.sequence, at: 2)
            try pointStatement.bind(point.segment, at: 3)
            try pointStatement.bind(point.latitude, at: 4)
            try pointStatement.bind(point.longitude, at: 5)
            try pointStatement.bind(point.altitudeMeters, at: 6)
            try pointStatement.bind(point.accuracyMeters, at: 7)
            try pointStatement.bind(point.fixAt.timeIntervalSince1970, at: 8)
            try pointStatement.bind(point.fixMonotonicNanoseconds, at: 9)
            try pointStatement.bind(point.distanceFromPreviousMeters, at: 10)
            try pointStatement.stepToCompletion()

            let checkpointStatement = try connection.prepare(
                """
                UPDATE tracking_sessions SET
                    hike_id = ?, active_slot = ?, status = ?, started_at = ?,
                    started_at_monotonic_ms = ?, hike_date = ?, boot_identifier = ?,
                    active_elapsed_ms = ?, active_since_monotonic_ms = ?,
                    distance_meters = ?, current_segment = ?, segment_start_pending = ?,
                    next_point_sequence = ?, last_fix_at = ?, last_fix_monotonic_ns = ?,
                    last_accuracy_meters = ?, finished_at = ?, generated_tcx_path = ?,
                    recovery_reason = ?, error_message = ?, updated_at = ?,
                    domain_snapshot = ?
                WHERE session_id = ?
                """
            )
            try bindSessionUpdate(checkpoint, to: checkpointStatement)
            try checkpointStatement.stepToCompletion()
        }
    }

    public func activeTrackingSession() throws -> TrackingSessionRecord? {
        let statement = try connection.prepare(
            "SELECT \(Self.trackingSessionColumns) FROM tracking_sessions WHERE active_slot = 1 LIMIT 1"
        )
        guard try statement.step() == SQLITE_ROW else { return nil }
        return try decodeSession(statement)
    }

    public func trackingSession(id: String) throws -> TrackingSessionRecord? {
        let statement = try connection.prepare(
            "SELECT \(Self.trackingSessionColumns) FROM tracking_sessions WHERE session_id = ? LIMIT 1"
        )
        try statement.bind(id, at: 1)
        guard try statement.step() == SQLITE_ROW else { return nil }
        return try decodeSession(statement)
    }

    public func finishedTrackingSession(hikeID: String) throws -> TrackingSessionRecord? {
        let statement = try connection.prepare(
            """
            SELECT \(Self.trackingSessionColumns) FROM tracking_sessions
            WHERE hike_id = ? AND status = 'finished' LIMIT 1
            """
        )
        try statement.bind(hikeID, at: 1)
        guard try statement.step() == SQLITE_ROW else { return nil }
        return try decodeSession(statement)
    }

    public func trackingPoints(sessionID: String) throws -> [TrackingPointRecord] {
        let statement = try connection.prepare(
            """
            SELECT session_id, sequence, segment, latitude, longitude,
                   altitude_meters, accuracy_meters, fix_at, fix_monotonic_ns,
                   distance_from_previous_meters
            FROM tracking_points WHERE session_id = ? ORDER BY sequence
            """
        )
        try statement.bind(sessionID, at: 1)
        var points: [TrackingPointRecord] = []
        while try statement.step() == SQLITE_ROW {
            points.append(
                TrackingPointRecord(
                    sessionID: statement.string(0),
                    sequence: statement.int64(1),
                    segment: Int(statement.int64(2)),
                    latitude: statement.double(3),
                    longitude: statement.double(4),
                    altitudeMeters: statement.optionalDouble(5),
                    accuracyMeters: statement.double(6),
                    fixAt: Date(timeIntervalSince1970: statement.double(7)),
                    fixMonotonicNanoseconds: statement.optionalInt64(8),
                    distanceFromPreviousMeters: statement.double(9)
                )
            )
        }
        return points
    }

    public func lastTrackingPoint(sessionID: String) throws -> TrackingPointRecord? {
        let statement = try connection.prepare(
            """
            SELECT session_id, sequence, segment, latitude, longitude,
                   altitude_meters, accuracy_meters, fix_at, fix_monotonic_ns,
                   distance_from_previous_meters
            FROM tracking_points WHERE session_id = ? ORDER BY sequence DESC LIMIT 1
            """
        )
        try statement.bind(sessionID, at: 1)
        guard try statement.step() == SQLITE_ROW else { return nil }
        return TrackingPointRecord(
            sessionID: statement.string(0),
            sequence: statement.int64(1),
            segment: Int(statement.int64(2)),
            latitude: statement.double(3),
            longitude: statement.double(4),
            altitudeMeters: statement.optionalDouble(5),
            accuracyMeters: statement.double(6),
            fixAt: Date(timeIntervalSince1970: statement.double(7)),
            fixMonotonicNanoseconds: statement.optionalInt64(8),
            distanceFromPreviousMeters: statement.double(9)
        )
    }

    /// Conservatively pauses an interrupted active session. It intentionally
    /// does not add wall-clock time after the last durable checkpoint.
    @discardableResult
    public func markActiveSessionRecoverable(
        at date: Date,
        reason: String
    ) throws -> TrackingSessionRecord? {
        guard let session = try activeTrackingSession(), session.status != .finished else {
            return nil
        }
        let recovered = TrackingSessionRecord(
            sessionID: session.sessionID,
            hikeID: session.hikeID,
            activeSlot: 1,
            status: .paused,
            startedAt: session.startedAt,
            startedAtMonotonicMilliseconds: session.startedAtMonotonicMilliseconds,
            hikeDate: session.hikeDate,
            bootIdentifier: session.bootIdentifier,
            activeElapsedMilliseconds: session.activeElapsedMilliseconds,
            activeSinceMonotonicMilliseconds: nil,
            distanceMeters: session.distanceMeters,
            currentSegment: session.currentSegment,
            segmentStartPending: true,
            nextPointSequence: session.nextPointSequence,
            lastFixAt: session.lastFixAt,
            lastFixMonotonicNanoseconds: session.lastFixMonotonicNanoseconds,
            lastAccuracyMeters: session.lastAccuracyMeters,
            finishedAt: session.finishedAt,
            generatedTCXPath: session.generatedTCXPath,
            recoveryReason: reason,
            errorMessage: session.errorMessage,
            updatedAt: date,
            domainSnapshot: session.domainSnapshot
        )
        try updateTrackingSession(recovered)
        return recovered
    }

    public func clearFinishedTrackingSessions(hikeID: String? = nil) throws {
        let sql: String
        if hikeID == nil {
            sql = "DELETE FROM tracking_sessions WHERE status = 'finished'"
        } else {
            sql = "DELETE FROM tracking_sessions WHERE status = 'finished' AND hike_id = ?"
        }
        let statement = try connection.prepare(sql)
        if let hikeID {
            try statement.bind(hikeID, at: 1)
        }
        try statement.stepToCompletion()
    }

    public func discardActiveTrackingSession(id: String) throws {
        let statement = try connection.prepare(
            "DELETE FROM tracking_sessions WHERE session_id = ? AND active_slot = 1"
        )
        try statement.bind(id, at: 1)
        try statement.stepToCompletion()
    }

    public func discardActiveRecording(hikeID: String, sessionID: String) throws {
        try connection.transaction {
            let operations = try connection.prepare(
                """
                DELETE FROM pending_operations
                WHERE parent_id = ? AND kind = 'create_field_mark'
                """
            )
            try operations.bind(hikeID, at: 1)
            try operations.stepToCompletion()

            let marks = try connection.prepare("DELETE FROM field_marks WHERE hike_id = ?")
            try marks.bind(hikeID, at: 1)
            try marks.stepToCompletion()

            let session = try connection.prepare(
                """
                DELETE FROM tracking_sessions
                WHERE session_id = ? AND hike_id = ? AND active_slot = 1
                """
            )
            try session.bind(sessionID, at: 1)
            try session.bind(hikeID, at: 2)
            try session.stepToCompletion()
        }
    }

    // MARK: - Field marks

    public func upsertFieldMark(_ mark: FieldMarkRecord) throws {
        let statement = try connection.prepare(
            """
            INSERT INTO field_marks (
                id, hike_id, recording_session_id, marked_at, latitude,
                longitude, accuracy_meters, mark_type, note, sync_state,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                hike_id = excluded.hike_id,
                recording_session_id = excluded.recording_session_id,
                marked_at = excluded.marked_at,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                accuracy_meters = excluded.accuracy_meters,
                mark_type = excluded.mark_type,
                note = excluded.note,
                sync_state = excluded.sync_state,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """
        )
        try statement.bind(mark.id, at: 1)
        try statement.bind(mark.hikeID, at: 2)
        try statement.bind(mark.recordingSessionID, at: 3)
        try statement.bind(mark.markedAt.timeIntervalSince1970, at: 4)
        try statement.bind(mark.latitude, at: 5)
        try statement.bind(mark.longitude, at: 6)
        try statement.bind(mark.accuracyMeters, at: 7)
        try statement.bind(mark.markType, at: 8)
        try statement.bind(mark.note, at: 9)
        try statement.bind(mark.syncState.rawValue, at: 10)
        try statement.bind(mark.createdAt.timeIntervalSince1970, at: 11)
        try statement.bind(mark.updatedAt.timeIntervalSince1970, at: 12)
        try statement.stepToCompletion()
    }

    /// Field context and its network intent are one logical write. This avoids
    /// a crash window where a visible mark could exist without ever syncing.
    public func enqueueFieldMark(
        _ mark: FieldMarkRecord,
        operation: PendingOperation
    ) throws {
        guard operation.kind == .createFieldMark,
              operation.entityID == mark.id,
              operation.parentID == mark.hikeID else {
            throw OfflineStoreError.invalidStoredValue(
                table: "pending_operations",
                column: "field_mark_link",
                value: operation.id
            )
        }
        try connection.transaction {
            try upsertFieldMark(mark)
            try upsertOperation(operation)
        }
    }

    public func fieldMarks(hikeID: String) throws -> [FieldMarkRecord] {
        let statement = try connection.prepare(
            """
            SELECT id, hike_id, recording_session_id, marked_at, latitude,
                   longitude, accuracy_meters, mark_type, note, sync_state,
                   created_at, updated_at
            FROM field_marks WHERE hike_id = ? ORDER BY marked_at, id
            """
        )
        try statement.bind(hikeID, at: 1)
        var marks: [FieldMarkRecord] = []
        while try statement.step() == SQLITE_ROW {
            let rawState = statement.string(9)
            guard let state = FieldMarkSyncState(rawValue: rawState) else {
                throw OfflineStoreError.invalidStoredValue(
                    table: "field_marks",
                    column: "sync_state",
                    value: rawState
                )
            }
            marks.append(
                FieldMarkRecord(
                    id: statement.string(0),
                    hikeID: statement.string(1),
                    recordingSessionID: statement.optionalString(2),
                    markedAt: Date(timeIntervalSince1970: statement.double(3)),
                    latitude: statement.double(4),
                    longitude: statement.double(5),
                    accuracyMeters: statement.optionalDouble(6),
                    markType: statement.string(7),
                    note: statement.string(8),
                    syncState: state,
                    createdAt: Date(timeIntervalSince1970: statement.double(10)),
                    updatedAt: Date(timeIntervalSince1970: statement.double(11))
                )
            )
        }
        return marks
    }

    public func updateFieldMarkSyncState(
        id: String,
        state: FieldMarkSyncState,
        updatedAt: Date
    ) throws {
        let statement = try connection.prepare(
            "UPDATE field_marks SET sync_state = ?, updated_at = ? WHERE id = ?"
        )
        try statement.bind(state.rawValue, at: 1)
        try statement.bind(updatedAt.timeIntervalSince1970, at: 2)
        try statement.bind(id, at: 3)
        try statement.stepToCompletion()
    }

    public func deleteFieldMarks(hikeID: String) throws {
        let statement = try connection.prepare("DELETE FROM field_marks WHERE hike_id = ?")
        try statement.bind(hikeID, at: 1)
        try statement.stepToCompletion()
    }

    // MARK: - Cached server resources

    public func upsertCachedResource(_ resource: CachedResource) throws {
        guard !resource.namespace.isEmpty, !resource.key.isEmpty else {
            throw OfflineStoreError.invalidStoredValue(
                table: "cached_resources",
                column: resource.namespace.isEmpty ? "namespace" : "cache_key",
                value: ""
            )
        }
        let statement = try connection.prepare(
            """
            INSERT INTO cached_resources (
                namespace, cache_key, payload, etag, stored_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(namespace, cache_key) DO UPDATE SET
                payload = excluded.payload,
                etag = excluded.etag,
                stored_at = excluded.stored_at,
                expires_at = excluded.expires_at
            """
        )
        try statement.bind(resource.namespace, at: 1)
        try statement.bind(resource.key, at: 2)
        try statement.bind(resource.payload, at: 3)
        try statement.bind(resource.etag, at: 4)
        try statement.bind(resource.storedAt.timeIntervalSince1970, at: 5)
        try statement.bind(resource.expiresAt?.timeIntervalSince1970, at: 6)
        try statement.stepToCompletion()
    }

    public func cachedResource(namespace: String, key: String) throws -> CachedResource? {
        let statement = try connection.prepare(
            """
            SELECT namespace, cache_key, payload, etag, stored_at, expires_at
            FROM cached_resources
            WHERE namespace = ? AND cache_key = ?
            LIMIT 1
            """
        )
        try statement.bind(namespace, at: 1)
        try statement.bind(key, at: 2)
        guard try statement.step() == SQLITE_ROW else { return nil }
        return decodeCachedResource(statement)
    }

    public func cachedResources(namespace: String) throws -> [CachedResource] {
        let statement = try connection.prepare(
            """
            SELECT namespace, cache_key, payload, etag, stored_at, expires_at
            FROM cached_resources
            WHERE namespace = ?
            ORDER BY stored_at DESC, cache_key
            """
        )
        try statement.bind(namespace, at: 1)
        var resources: [CachedResource] = []
        while try statement.step() == SQLITE_ROW {
            resources.append(decodeCachedResource(statement))
        }
        return resources
    }

    public func deleteCachedResource(namespace: String, key: String) throws {
        let statement = try connection.prepare(
            "DELETE FROM cached_resources WHERE namespace = ? AND cache_key = ?"
        )
        try statement.bind(namespace, at: 1)
        try statement.bind(key, at: 2)
        try statement.stepToCompletion()
    }

    public func deleteCachedResources(namespace: String) throws {
        let statement = try connection.prepare(
            "DELETE FROM cached_resources WHERE namespace = ?"
        )
        try statement.bind(namespace, at: 1)
        try statement.stepToCompletion()
    }

    // MARK: - Migration

    private static func migrate(_ connection: SQLiteConnection) throws {
        try connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY NOT NULL,
                applied_at REAL NOT NULL
            )
            """
        )
        let statement = try connection.prepare(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        )
        let found = try statement.step() == SQLITE_ROW ? Int(statement.int64(0)) : 0
        guard found <= currentSchemaVersion else {
            throw OfflineStoreError.migrationTooNew(
                found: found,
                supported: currentSchemaVersion
            )
        }
        if found < 1 {
            try connection.transaction {
                try connection.execute(schemaVersionOne)
                try recordMigration(1, connection: connection)
            }
        }
        if found < 2 {
            try connection.transaction {
                try connection.execute(schemaVersionTwo)
                try recordMigration(2, connection: connection)
            }
        }
    }

    private static func recordMigration(_ version: Int, connection: SQLiteConnection) throws {
        let migration = try connection.prepare(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)"
        )
        try migration.bind(version, at: 1)
        try migration.bind(Date().timeIntervalSince1970, at: 2)
        try migration.stepToCompletion()
        try connection.execute("PRAGMA user_version = \(version)")
    }

    private static let schemaVersionOne = """
        CREATE TABLE pending_operations (
            id TEXT PRIMARY KEY NOT NULL,
            kind TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            parent_id TEXT,
            payload BLOB NOT NULL,
            local_file_path TEXT,
            content_type TEXT,
            file_name TEXT,
            state TEXT NOT NULL CHECK(state IN ('queued', 'syncing', 'needs_attention')),
            attempt_count INTEGER NOT NULL CHECK(attempt_count >= 0),
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            last_error TEXT
        );
        CREATE INDEX pending_operations_created_at_idx
            ON pending_operations(created_at, id);
        CREATE INDEX pending_operations_hike_idx
            ON pending_operations(parent_id, entity_id);
        CREATE INDEX pending_operations_state_idx
            ON pending_operations(state, created_at);

        CREATE TABLE tracking_sessions (
            session_id TEXT PRIMARY KEY NOT NULL,
            hike_id TEXT NOT NULL UNIQUE,
            active_slot INTEGER UNIQUE CHECK(active_slot IS NULL OR active_slot = 1),
            status TEXT NOT NULL CHECK(status IN ('starting', 'recording', 'paused', 'finalizing', 'finished')),
            started_at REAL NOT NULL,
            started_at_monotonic_ms INTEGER NOT NULL,
            hike_date TEXT NOT NULL,
            boot_identifier TEXT NOT NULL,
            active_elapsed_ms INTEGER NOT NULL CHECK(active_elapsed_ms >= 0),
            active_since_monotonic_ms INTEGER,
            distance_meters REAL NOT NULL CHECK(distance_meters >= 0),
            current_segment INTEGER NOT NULL CHECK(current_segment >= 0),
            segment_start_pending INTEGER NOT NULL CHECK(segment_start_pending IN (0, 1)),
            next_point_sequence INTEGER NOT NULL CHECK(next_point_sequence >= 0),
            last_fix_at REAL,
            last_fix_monotonic_ns INTEGER,
            last_accuracy_meters REAL,
            finished_at REAL,
            generated_tcx_path TEXT,
            recovery_reason TEXT,
            error_message TEXT,
            updated_at REAL NOT NULL,
            domain_snapshot BLOB
        );
        CREATE INDEX tracking_sessions_status_idx ON tracking_sessions(status);

        CREATE TABLE tracking_points (
            session_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            segment INTEGER NOT NULL CHECK(segment >= 0),
            latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),
            longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180),
            altitude_meters REAL,
            accuracy_meters REAL NOT NULL CHECK(accuracy_meters >= 0),
            fix_at REAL NOT NULL,
            fix_monotonic_ns INTEGER,
            distance_from_previous_meters REAL NOT NULL CHECK(distance_from_previous_meters >= 0),
            PRIMARY KEY(session_id, sequence),
            FOREIGN KEY(session_id) REFERENCES tracking_sessions(session_id) ON DELETE CASCADE
        );
        CREATE INDEX tracking_points_route_idx
            ON tracking_points(session_id, segment, sequence);

        CREATE TABLE field_marks (
            id TEXT PRIMARY KEY NOT NULL,
            hike_id TEXT NOT NULL,
            recording_session_id TEXT,
            marked_at REAL NOT NULL,
            latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),
            longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180),
            accuracy_meters REAL,
            mark_type TEXT NOT NULL,
            note TEXT NOT NULL,
            sync_state TEXT NOT NULL CHECK(sync_state IN ('local', 'queued', 'syncing', 'synced', 'needs_attention')),
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE INDEX field_marks_hike_idx ON field_marks(hike_id, marked_at);
        CREATE INDEX field_marks_session_idx ON field_marks(recording_session_id);
        CREATE INDEX field_marks_sync_idx ON field_marks(sync_state);
        """

    private static let schemaVersionTwo = """
        CREATE TABLE cached_resources (
            namespace TEXT NOT NULL,
            cache_key TEXT NOT NULL,
            payload BLOB NOT NULL,
            etag TEXT,
            stored_at REAL NOT NULL,
            expires_at REAL,
            PRIMARY KEY(namespace, cache_key)
        );
        CREATE INDEX cached_resources_recency_idx
            ON cached_resources(namespace, stored_at DESC);
        CREATE INDEX cached_resources_expiry_idx
            ON cached_resources(expires_at);
        """

    // MARK: - Row conversion

    private static let pendingColumns = """
        id, kind, entity_id, parent_id, payload, local_file_path, content_type,
        file_name, state, attempt_count, created_at, updated_at, last_error
        """

    private static let trackingSessionColumns = """
        session_id, hike_id, active_slot, status, started_at,
        started_at_monotonic_ms, hike_date, boot_identifier, active_elapsed_ms,
        active_since_monotonic_ms, distance_meters, current_segment,
        segment_start_pending, next_point_sequence, last_fix_at,
        last_fix_monotonic_ns, last_accuracy_meters, finished_at,
        generated_tcx_path, recovery_reason, error_message, updated_at,
        domain_snapshot
        """

    private func bind(_ operation: PendingOperation, to statement: SQLiteStatement) throws {
        try statement.bind(operation.id, at: 1)
        try statement.bind(operation.kind.rawValue, at: 2)
        try statement.bind(operation.entityID, at: 3)
        try statement.bind(operation.parentID, at: 4)
        try statement.bind(operation.payload, at: 5)
        try statement.bind(operation.localFilePath, at: 6)
        try statement.bind(operation.contentType, at: 7)
        try statement.bind(operation.fileName, at: 8)
        try statement.bind(operation.state.rawValue, at: 9)
        try statement.bind(operation.attemptCount, at: 10)
        try statement.bind(operation.createdAt.timeIntervalSince1970, at: 11)
        try statement.bind(operation.updatedAt.timeIntervalSince1970, at: 12)
        try statement.bind(operation.lastError, at: 13)
    }

    private func operations(sql: String) throws -> [PendingOperation] {
        try decodeOperations(connection.prepare(sql))
    }

    private func decodeOperations(_ statement: SQLiteStatement) throws -> [PendingOperation] {
        var result: [PendingOperation] = []
        while try statement.step() == SQLITE_ROW {
            result.append(try decodeOperation(statement))
        }
        return result
    }

    private func decodeOperation(_ statement: SQLiteStatement) throws -> PendingOperation {
        let rawKind = statement.string(1)
        let rawState = statement.string(8)
        guard let kind = PendingOperationKind(rawValue: rawKind) else {
            throw OfflineStoreError.invalidStoredValue(
                table: "pending_operations",
                column: "kind",
                value: rawKind
            )
        }
        guard let state = PendingOperationState(rawValue: rawState) else {
            throw OfflineStoreError.invalidStoredValue(
                table: "pending_operations",
                column: "state",
                value: rawState
            )
        }
        return PendingOperation(
            id: statement.string(0),
            kind: kind,
            entityID: statement.string(2),
            parentID: statement.optionalString(3),
            payload: statement.data(4),
            localFilePath: statement.optionalString(5),
            contentType: statement.optionalString(6),
            fileName: statement.optionalString(7),
            state: state,
            attemptCount: Int(statement.int64(9)),
            createdAt: Date(timeIntervalSince1970: statement.double(10)),
            updatedAt: Date(timeIntervalSince1970: statement.double(11)),
            lastError: statement.optionalString(12)
        )
    }

    private func decodeCachedResource(_ statement: SQLiteStatement) -> CachedResource {
        CachedResource(
            namespace: statement.string(0),
            key: statement.string(1),
            payload: statement.data(2),
            etag: statement.optionalString(3),
            storedAt: Date(timeIntervalSince1970: statement.double(4)),
            expiresAt: statement.optionalDouble(5).map(Date.init(timeIntervalSince1970:))
        )
    }

    private func bind(_ session: TrackingSessionRecord, to statement: SQLiteStatement) throws {
        try statement.bind(session.sessionID, at: 1)
        try statement.bind(session.hikeID, at: 2)
        try statement.bind(session.activeSlot, at: 3)
        try statement.bind(session.status.rawValue, at: 4)
        try statement.bind(session.startedAt.timeIntervalSince1970, at: 5)
        try statement.bind(session.startedAtMonotonicMilliseconds, at: 6)
        try statement.bind(session.hikeDate, at: 7)
        try statement.bind(session.bootIdentifier, at: 8)
        try statement.bind(session.activeElapsedMilliseconds, at: 9)
        try statement.bind(session.activeSinceMonotonicMilliseconds, at: 10)
        try statement.bind(session.distanceMeters, at: 11)
        try statement.bind(session.currentSegment, at: 12)
        try statement.bind(session.segmentStartPending, at: 13)
        try statement.bind(session.nextPointSequence, at: 14)
        try statement.bind(session.lastFixAt?.timeIntervalSince1970, at: 15)
        try statement.bind(session.lastFixMonotonicNanoseconds, at: 16)
        try statement.bind(session.lastAccuracyMeters, at: 17)
        try statement.bind(session.finishedAt?.timeIntervalSince1970, at: 18)
        try statement.bind(session.generatedTCXPath, at: 19)
        try statement.bind(session.recoveryReason, at: 20)
        try statement.bind(session.errorMessage, at: 21)
        try statement.bind(session.updatedAt.timeIntervalSince1970, at: 22)
        try statement.bind(session.domainSnapshot, at: 23)
    }

    private func bindSessionUpdate(
        _ session: TrackingSessionRecord,
        to statement: SQLiteStatement
    ) throws {
        try statement.bind(session.hikeID, at: 1)
        try statement.bind(session.activeSlot, at: 2)
        try statement.bind(session.status.rawValue, at: 3)
        try statement.bind(session.startedAt.timeIntervalSince1970, at: 4)
        try statement.bind(session.startedAtMonotonicMilliseconds, at: 5)
        try statement.bind(session.hikeDate, at: 6)
        try statement.bind(session.bootIdentifier, at: 7)
        try statement.bind(session.activeElapsedMilliseconds, at: 8)
        try statement.bind(session.activeSinceMonotonicMilliseconds, at: 9)
        try statement.bind(session.distanceMeters, at: 10)
        try statement.bind(session.currentSegment, at: 11)
        try statement.bind(session.segmentStartPending, at: 12)
        try statement.bind(session.nextPointSequence, at: 13)
        try statement.bind(session.lastFixAt?.timeIntervalSince1970, at: 14)
        try statement.bind(session.lastFixMonotonicNanoseconds, at: 15)
        try statement.bind(session.lastAccuracyMeters, at: 16)
        try statement.bind(session.finishedAt?.timeIntervalSince1970, at: 17)
        try statement.bind(session.generatedTCXPath, at: 18)
        try statement.bind(session.recoveryReason, at: 19)
        try statement.bind(session.errorMessage, at: 20)
        try statement.bind(session.updatedAt.timeIntervalSince1970, at: 21)
        try statement.bind(session.domainSnapshot, at: 22)
        try statement.bind(session.sessionID, at: 23)
    }

    private func decodeSession(_ statement: SQLiteStatement) throws -> TrackingSessionRecord {
        let rawStatus = statement.string(3)
        guard let status = PersistedTrackingStatus(rawValue: rawStatus) else {
            throw OfflineStoreError.invalidStoredValue(
                table: "tracking_sessions",
                column: "status",
                value: rawStatus
            )
        }
        return TrackingSessionRecord(
            sessionID: statement.string(0),
            hikeID: statement.string(1),
            activeSlot: statement.optionalInt64(2).map(Int.init),
            status: status,
            startedAt: Date(timeIntervalSince1970: statement.double(4)),
            startedAtMonotonicMilliseconds: statement.int64(5),
            hikeDate: statement.string(6),
            bootIdentifier: statement.string(7),
            activeElapsedMilliseconds: statement.int64(8),
            activeSinceMonotonicMilliseconds: statement.optionalInt64(9),
            distanceMeters: statement.double(10),
            currentSegment: Int(statement.int64(11)),
            segmentStartPending: statement.int64(12) != 0,
            nextPointSequence: statement.int64(13),
            lastFixAt: statement.optionalDouble(14).map(Date.init(timeIntervalSince1970:)),
            lastFixMonotonicNanoseconds: statement.optionalInt64(15),
            lastAccuracyMeters: statement.optionalDouble(16),
            finishedAt: statement.optionalDouble(17).map(Date.init(timeIntervalSince1970:)),
            generatedTCXPath: statement.optionalString(18),
            recoveryReason: statement.optionalString(19),
            errorMessage: statement.optionalString(20),
            updatedAt: Date(timeIntervalSince1970: statement.double(21)),
            domainSnapshot: statement.isNull(22) ? nil : statement.data(22)
        )
    }
}
