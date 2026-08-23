import Foundation
import XCTest
@testable import HikeJournalPersistence

final class OfflineDatabaseTests: XCTestCase {
    func testSchemaAndMutationQueueSurviveReopen() async throws {
        let fixture = try Fixture()
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let operation = makeOperation(
            id: "op-1",
            kind: .uploadPhoto,
            entityID: "photo-1",
            parentID: "hike-1",
            createdAt: now,
            localFilePath: "/durable/photo.jpg"
        )

        var database: OfflineDatabase? = try OfflineDatabase(path: fixture.databaseURL.path)
        try await database?.upsertOperation(operation)
        let schemaVersion = try await database?.schemaVersion()
        XCTAssertEqual(schemaVersion, 2)
        await database?.close()
        database = nil

        let reopened = try OfflineDatabase(path: fixture.databaseURL.path)
        let restored = try await reopened.operation(id: operation.id)
        let summary = try await reopened.queueSummary()
        XCTAssertEqual(restored, operation)
        XCTAssertEqual(
            summary,
            SyncQueueSummary(queued: 1, syncing: 0, needsAttention: 0)
        )
    }

    func testDatabaseReopensWhenAFeatureStillHoldsItsHandle() async throws {
        let fixture = try Fixture()
        let database = try OfflineDatabase(path: fixture.databaseURL.path)
        let first = makeOperation(
            id: "reopen-op",
            kind: .updateHike,
            entityID: "hike-1",
            createdAt: Date(timeIntervalSince1970: 1_700_000_000)
        )

        try await database.upsertOperation(first)
        await database.close()

        let second = makeOperation(
            id: "reopen-op-2",
            kind: .updateHike,
            entityID: "hike-2",
            createdAt: Date(timeIntervalSince1970: 1_700_000_001)
        )
        try await database.upsertOperation(second)

        let restoredFirst = try await database.operation(id: first.id)
        let restoredSecond = try await database.operation(id: second.id)
        XCTAssertEqual(restoredFirst, first)
        XCTAssertEqual(restoredSecond, second)
    }

    func testCachedResponsesSurviveReopenAndRemainAvailableAfterExpiry() async throws {
        let fixture = try Fixture()
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let resource = CachedResource(
            namespace: "place-profile",
            key: "location-1",
            payload: Data(#"{"name":"Mt. Washington"}"#.utf8),
            etag: #"W/"profile-1""#,
            storedAt: now,
            expiresAt: now.addingTimeInterval(300)
        )

        var database: OfflineDatabase? = try OfflineDatabase(path: fixture.databaseURL.path)
        try await database?.upsertCachedResource(resource)
        await database?.close()
        database = nil

        let reopened = try OfflineDatabase(path: fixture.databaseURL.path)
        let restored = try await reopened.cachedResource(
            namespace: resource.namespace,
            key: resource.key
        )
        XCTAssertEqual(restored, resource)
        XCTAssertTrue(try XCTUnwrap(restored).isFresh(at: now.addingTimeInterval(299)))
        XCTAssertFalse(try XCTUnwrap(restored).isFresh(at: now.addingTimeInterval(301)))
    }

    func testCachedResourceNamespacesDoNotCollide() async throws {
        let fixture = try Fixture()
        let database = try OfflineDatabase(path: fixture.databaseURL.path)
        let now = Date(timeIntervalSince1970: 100)
        try await database.upsertCachedResource(
            CachedResource(namespace: "hike", key: "same", payload: Data("hike".utf8), storedAt: now)
        )
        try await database.upsertCachedResource(
            CachedResource(namespace: "species", key: "same", payload: Data("species".utf8), storedAt: now)
        )

        let hike = try await database.cachedResource(namespace: "hike", key: "same")
        let species = try await database.cachedResource(namespace: "species", key: "same")
        XCTAssertEqual(hike?.payload, Data("hike".utf8))
        XCTAssertEqual(species?.payload, Data("species".utf8))

        try await database.deleteCachedResources(namespace: "hike")
        let deletedHike = try await database.cachedResource(namespace: "hike", key: "same")
        let remainingSpecies = try await database.cachedResource(namespace: "species", key: "same")
        XCTAssertNil(deletedHike)
        XCTAssertNotNil(remainingSpecies)
    }

    func testQueueStateCanBeRetriedAndDiscarded() async throws {
        let fixture = try Fixture()
        let database = try OfflineDatabase(path: fixture.databaseURL.path)
        let now = Date(timeIntervalSince1970: 100)
        try await database.upsertOperation(
            makeOperation(id: "a", kind: .updateHike, entityID: "hike", createdAt: now)
        )
        try await database.updateOperationState(
            id: "a",
            state: .needsAttention,
            attemptCount: 5,
            updatedAt: now.addingTimeInterval(5),
            lastError: "server rejected it"
        )
        let attentionIDs = try await database.operationsNeedingAttention().map(\.id)
        XCTAssertEqual(attentionIDs, ["a"])

        try await database.retryOperationsNeedingAttention(updatedAt: now.addingTimeInterval(10))
        let retriedValue = try await database.operation(id: "a")
        let retried = try XCTUnwrap(retriedValue)
        XCTAssertEqual(retried.state, .queued)
        XCTAssertEqual(retried.attemptCount, 0)
        XCTAssertNil(retried.lastError)

        try await database.updateOperationState(
            id: "a",
            state: .needsAttention,
            attemptCount: 1,
            updatedAt: now,
            lastError: "again"
        )
        try await database.discardOperationNeedingAttention(id: "a")
        let discarded = try await database.operation(id: "a")
        XCTAssertNil(discarded)
    }

    func testSyncPlannerPreservesCreateAndDeleteDependencies() {
        let start = Date(timeIntervalSince1970: 100)
        let update = makeOperation(
            id: "update",
            kind: .updateHike,
            entityID: "hike",
            createdAt: start
        )
        let create = makeOperation(
            id: "create",
            kind: .createHike,
            entityID: "hike",
            createdAt: start.addingTimeInterval(1)
        )
        XCTAssertEqual(SyncQueuePlanner.next(from: [update, create])?.id, "create")

        let deletion = makeOperation(
            id: "delete",
            kind: .deleteHike,
            entityID: "hike",
            createdAt: start.addingTimeInterval(2)
        )
        XCTAssertEqual(SyncQueuePlanner.next(from: [update, deletion])?.id, "delete")
    }

    func testSyncPlannerUploadsSelectedCoverBeforeOtherMedia() {
        let start = Date(timeIntervalSince1970: 100)
        let regular = makeOperation(
            id: "regular",
            kind: .uploadPhoto,
            entityID: "photo-a",
            parentID: "hike",
            createdAt: start
        )
        let coverUpload = makeOperation(
            id: "cover-upload",
            kind: .uploadPhoto,
            entityID: "photo-b",
            parentID: "hike",
            createdAt: start.addingTimeInterval(1)
        )
        let cover = makeOperation(
            id: "cover",
            kind: .setHikeCover,
            entityID: "hike",
            payload: Data(#"{"photo_id":"photo-b"}"#.utf8),
            createdAt: start.addingTimeInterval(2)
        )
        XCTAssertEqual(
            SyncQueuePlanner.next(from: [regular, coverUpload, cover])?.id,
            "cover-upload"
        )
        XCTAssertEqual(
            SyncQueuePlanner.nextBatch(from: [regular, coverUpload, cover]).map(\.id),
            ["cover-upload"]
        )
    }

    func testPhotoBatchIsBoundedAndSkipsAttention() {
        let start = Date(timeIntervalSince1970: 100)
        let operations = (0..<5).map { index in
            makeOperation(
                id: "photo-\(index)",
                kind: .uploadPhoto,
                entityID: "photo-\(index)",
                parentID: "hike",
                state: index == 1 ? .needsAttention : .queued,
                createdAt: start.addingTimeInterval(Double(index))
            )
        }
        XCTAssertEqual(
            SyncQueuePlanner.nextBatch(
                from: operations,
                maximumParallelPhotoUploads: 2
            ).map(\.id),
            ["photo-0", "photo-2"]
        )
    }

    func testAcceptedPointAndCheckpointCommitTogether() async throws {
        let fixture = try Fixture()
        let database = try OfflineDatabase(path: fixture.databaseURL.path)
        let initial = makeSession()
        try await database.insertTrackingSession(initial)

        let fixDate = initial.startedAt.addingTimeInterval(5)
        let point = TrackingPointRecord(
            sessionID: initial.sessionID,
            sequence: 0,
            segment: 0,
            latitude: 42.3601,
            longitude: -71.0589,
            altitudeMeters: 14,
            accuracyMeters: 5,
            fixAt: fixDate,
            fixMonotonicNanoseconds: 15_000_000_000,
            distanceFromPreviousMeters: 0
        )
        let checkpoint = makeSession(
            status: .recording,
            distanceMeters: 0,
            nextSequence: 1,
            lastFixAt: fixDate,
            lastFixMonotonicNanoseconds: 15_000_000_000,
            lastAccuracy: 5
        )
        try await database.recordAcceptedPoint(point, checkpoint: checkpoint)

        let points = try await database.trackingPoints(sessionID: initial.sessionID)
        let active = try await database.activeTrackingSession()
        XCTAssertEqual(points, [point])
        XCTAssertEqual(active, checkpoint)
    }

    func testFailedPointDoesNotAdvanceCheckpoint() async throws {
        let fixture = try Fixture()
        let database = try OfflineDatabase(path: fixture.databaseURL.path)
        let initial = makeSession()
        try await database.insertTrackingSession(initial)
        let invalid = TrackingPointRecord(
            sessionID: initial.sessionID,
            sequence: 0,
            segment: 0,
            latitude: 120,
            longitude: 0,
            accuracyMeters: 5,
            fixAt: initial.startedAt,
            distanceFromPreviousMeters: 0
        )
        let advanced = makeSession(nextSequence: 1)

        do {
            try await database.recordAcceptedPoint(invalid, checkpoint: advanced)
            XCTFail("Expected the coordinate check to reject the point")
        } catch {
            XCTAssertNotNil(error as? OfflineStoreError)
        }
        let points = try await database.trackingPoints(sessionID: initial.sessionID)
        let active = try await database.activeTrackingSession()
        XCTAssertEqual(points, [])
        XCTAssertEqual(active, initial)
    }

    func testOnlyOneActiveSessionCanExist() async throws {
        let fixture = try Fixture()
        let database = try OfflineDatabase(path: fixture.databaseURL.path)
        try await database.insertTrackingSession(makeSession())
        let second = TrackingSessionRecord(
            sessionID: "session-2",
            hikeID: "hike-2",
            status: .recording,
            startedAt: Date(timeIntervalSince1970: 200),
            startedAtMonotonicMilliseconds: 200,
            hikeDate: "2023-11-15",
            bootIdentifier: "boot",
            updatedAt: Date(timeIntervalSince1970: 200)
        )
        do {
            try await database.insertTrackingSession(second)
            XCTFail("Expected unique active session protection")
        } catch {
            XCTAssertNotNil(error as? OfflineStoreError)
        }
    }

    func testInterruptedRecordingRecoversPausedWithoutInventingElapsedTime() async throws {
        let fixture = try Fixture()
        let database = try OfflineDatabase(path: fixture.databaseURL.path)
        let active = makeSession(status: .recording, activeElapsed: 12_000)
        try await database.insertTrackingSession(active)

        let recoveredValue = try await database.markActiveSessionRecoverable(
            at: active.updatedAt.addingTimeInterval(100),
            reason: "service_interrupted"
        )
        let recovered = try XCTUnwrap(recoveredValue)
        XCTAssertEqual(recovered.status, .paused)
        XCTAssertEqual(recovered.activeElapsedMilliseconds, 12_000)
        XCTAssertNil(recovered.activeSinceMonotonicMilliseconds)
        XCTAssertTrue(recovered.segmentStartPending)
        XCTAssertEqual(recovered.recoveryReason, "service_interrupted")
    }

    func testFieldMarksPersistInChronologicalOrderAndUpdateSyncState() async throws {
        let fixture = try Fixture()
        let database = try OfflineDatabase(path: fixture.databaseURL.path)
        let now = Date(timeIntervalSince1970: 100)
        let later = FieldMarkRecord(
            id: "later",
            hikeID: "hike",
            markedAt: now.addingTimeInterval(5),
            latitude: 44,
            longitude: -72,
            accuracyMeters: 7,
            markType: "view",
            note: "ridge",
            syncState: .queued,
            createdAt: now,
            updatedAt: now
        )
        let earlier = FieldMarkRecord(
            id: "earlier",
            hikeID: "hike",
            markedAt: now,
            latitude: 43,
            longitude: -71,
            markType: "wildlife",
            createdAt: now,
            updatedAt: now
        )
        try await database.upsertFieldMark(later)
        try await database.upsertFieldMark(earlier)
        let orderedIDs = try await database.fieldMarks(hikeID: "hike").map(\.id)
        XCTAssertEqual(orderedIDs, ["earlier", "later"])

        try await database.updateFieldMarkSyncState(id: "later", state: .synced, updatedAt: now)
        let updatedState = try await database.fieldMarks(hikeID: "hike").last?.syncState
        XCTAssertEqual(updatedState, .synced)
        try await database.deleteFieldMarks(hikeID: "hike")
        let remainingMarks = try await database.fieldMarks(hikeID: "hike")
        XCTAssertEqual(remainingMarks, [])
    }

    func testFieldMarkAndSyncIntentCommitTogether() async throws {
        let fixture = try Fixture()
        let database = try OfflineDatabase(path: fixture.databaseURL.path)
        let now = Date(timeIntervalSince1970: 100)
        let mark = FieldMarkRecord(
            id: "mark",
            hikeID: "hike",
            markedAt: now,
            latitude: 43,
            longitude: -71,
            markType: "wildlife",
            syncState: .queued,
            createdAt: now,
            updatedAt: now
        )
        let operation = makeOperation(
            id: "mark-op",
            kind: .createFieldMark,
            entityID: mark.id,
            parentID: mark.hikeID,
            createdAt: now
        )
        try await database.enqueueFieldMark(mark, operation: operation)
        let restoredMarks = try await database.fieldMarks(hikeID: mark.hikeID)
        let restoredOperation = try await database.operation(id: operation.id)
        XCTAssertEqual(restoredMarks, [mark])
        XCTAssertEqual(restoredOperation, operation)

        do {
            try await database.enqueueFieldMark(
                mark,
                operation: makeOperation(
                    id: "wrong",
                    kind: .updateCaption,
                    entityID: mark.id,
                    parentID: mark.hikeID,
                    createdAt: now
                )
            )
            XCTFail("Expected link validation")
        } catch {
            XCTAssertNotNil(error as? OfflineStoreError)
        }
    }

    func testAccountPathUsesCanonicalUUIDWithoutIdentityProviderData() {
        let root = URL(fileURLWithPath: "/tmp/app-support", isDirectory: true)
        let id = UUID(uuidString: "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE")!
        let url = OfflineDatabase.accountDatabaseURL(
            applicationSupportDirectory: root,
            canonicalUserID: id
        )
        XCTAssertEqual(
            url.path,
            "/tmp/app-support/HikeJournal/Accounts/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/offline.sqlite"
        )
    }

    private func makeOperation(
        id: String,
        kind: PendingOperationKind,
        entityID: String,
        parentID: String? = nil,
        payload: Data = Data("{}".utf8),
        state: PendingOperationState = .queued,
        createdAt: Date,
        localFilePath: String? = nil
    ) -> PendingOperation {
        PendingOperation(
            id: id,
            kind: kind,
            entityID: entityID,
            parentID: parentID,
            payload: payload,
            localFilePath: localFilePath,
            contentType: localFilePath == nil ? nil : "image/jpeg",
            fileName: localFilePath == nil ? nil : "photo.jpg",
            state: state,
            createdAt: createdAt,
            updatedAt: createdAt
        )
    }

    private func makeSession(
        status: PersistedTrackingStatus = .starting,
        activeElapsed: Int64 = 0,
        distanceMeters: Double = 0,
        nextSequence: Int64 = 0,
        lastFixAt: Date? = nil,
        lastFixMonotonicNanoseconds: Int64? = nil,
        lastAccuracy: Double? = nil
    ) -> TrackingSessionRecord {
        let now = Date(timeIntervalSince1970: 100)
        return TrackingSessionRecord(
            sessionID: "session",
            hikeID: "hike",
            status: status,
            startedAt: now,
            startedAtMonotonicMilliseconds: 10_000,
            hikeDate: "1970-01-01",
            bootIdentifier: "boot",
            activeElapsedMilliseconds: activeElapsed,
            activeSinceMonotonicMilliseconds: status == .recording ? 10_000 : nil,
            distanceMeters: distanceMeters,
            nextPointSequence: nextSequence,
            lastFixAt: lastFixAt,
            lastFixMonotonicNanoseconds: lastFixMonotonicNanoseconds,
            lastAccuracyMeters: lastAccuracy,
            updatedAt: now
        )
    }
}

private final class Fixture {
    let directory: URL
    let databaseURL: URL

    init() throws {
        directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )
        databaseURL = directory.appendingPathComponent("offline.sqlite")
    }

    deinit {
        try? FileManager.default.removeItem(at: directory)
    }
}
