import Foundation
import CoreLocation
import HikeJournalPersistence
import HikeJournalTracking
import XCTest
@testable import HikeJournal

final class HikeRecorderTests: XCTestCase {
    func testTransientLocationAcquisitionFailureDoesNotPauseRecording() {
        XCTAssertFalse(
            RecordingLocationController.shouldReportLocationError(CLError(.locationUnknown))
        )
        XCTAssertFalse(
            RecordingLocationController.shouldReportLocationError(
                NSError(
                    domain: kCLErrorDomain,
                    code: CLError.locationUnknown.rawValue
                )
            )
        )
        XCTAssertTrue(
            RecordingLocationController.shouldReportLocationError(CLError(.denied))
        )
    }

    func testAcceptedFixesAreDurableAndFinalizationQueuesCreateBeforeRoute() async throws {
        let fixture = try RecorderFixture()
        let snapshot = try await fixture.recorder.start()
        XCTAssertEqual(snapshot.status, .recording)

        _ = try await fixture.ingestFirstPoint()
        let second = try await fixture.ingestSecondPoint()
        XCTAssertEqual(second.snapshot.pointCount, 2)
        XCTAssertGreaterThan(second.snapshot.distanceMeters, 5)

        let finished = try await fixture.recorder.finish(
            title: "Dawn ridge",
            notes: "Clear and cool"
        )
        XCTAssertEqual(finished.snapshot.status, .finished)
        XCTAssertTrue(FileManager.default.fileExists(atPath: finished.routeURL.path))

        let points = try await fixture.database.trackingPoints(sessionID: "session")
        XCTAssertEqual(points.count, 2)
        let operations = try await fixture.database.operations()
        XCTAssertEqual(operations.map(\.kind), [.createHike, .uploadRoute])
        XCTAssertEqual(operations[1].parentID, "hike")
        XCTAssertEqual(
            SyncQueuePlanner.next(from: operations)?.kind,
            .createHike
        )
        let routePayload = try XCTUnwrap(
            JSONSerialization.jsonObject(with: operations[1].payload) as? [String: Any]
        )
        XCTAssertEqual(routePayload["source_type"] as? String, "hikejournal_ios_gps")
        XCTAssertEqual(routePayload["track_point_count"] as? Int, 2)
    }

    func testInterruptedRecorderRestoresPausedFromSQLiteSnapshot() async throws {
        let fixture = try RecorderFixture()
        _ = try await fixture.recorder.start()
        _ = try await fixture.ingestFirstPoint()

        fixture.clock.set(wall: 150, monotonic: 60_000)
        let replacement = HikeRecorder(
            database: fixture.database,
            routeDirectory: fixture.routeDirectory,
            clock: fixture.clock.value,
            idGenerator: fixture.ids.value
        )
        let recoveredValue = try await replacement.restoreInterruptedRecording()
        let recovered = try XCTUnwrap(recoveredValue)
        XCTAssertEqual(recovered.status, .paused)
        XCTAssertEqual(recovered.pointCount, 1)
        XCTAssertEqual(recovered.recoveryReason, .serviceInterrupted)

        let persisted = try await fixture.database.activeTrackingSession()
        XCTAssertEqual(persisted?.status, .paused)
        XCTAssertNil(persisted?.activeSinceMonotonicMilliseconds)
    }

    func testFieldMarkUsesLastAcceptedFixAndQueuesSameCoordinates() async throws {
        let fixture = try RecorderFixture()
        _ = try await fixture.recorder.start()
        _ = try await fixture.ingestFirstPoint()
        fixture.clock.set(wall: 105, monotonic: 15_000)
        let mark = try await fixture.recorder.addFieldMark(
            type: .wildlife,
            note: "  Owl  "
        )
        XCTAssertEqual(mark.note, "Owl")
        XCTAssertEqual(mark.latitude, 42)
        XCTAssertEqual(mark.longitude, -71)

        let marks = try await fixture.database.fieldMarks(hikeID: "hike")
        let operations = try await fixture.database.operations(forHikeID: "hike")
        XCTAssertEqual(marks.count, 1)
        XCTAssertTrue(operations.contains(where: { $0.kind == .createFieldMark }))
        let markOperation = try XCTUnwrap(
            operations.first(where: { $0.kind == .createFieldMark })
        )
        let payload = try XCTUnwrap(
            JSONSerialization.jsonObject(with: markOperation.payload) as? [String: Any]
        )
        XCTAssertEqual(payload["lat"] as? Double, 42)
        XCTAssertEqual(payload["lng"] as? Double, -71)
        XCTAssertEqual(payload["wait_for_hike_create"] as? Bool, true)
    }

    func testFieldMarkBeforeFirstFixIsRejectedWithoutQueueMutation() async throws {
        let fixture = try RecorderFixture()
        _ = try await fixture.recorder.start()
        do {
            _ = try await fixture.recorder.addFieldMark(type: .note)
            XCTFail("Expected first-fix requirement")
        } catch {
            XCTAssertEqual(error as? TrackingCoreError, .fieldMarkRequiresAcceptedFix)
        }
        let operations = try await fixture.database.operations()
        XCTAssertTrue(operations.isEmpty)
    }

    func testInvalidFixIsNotPersisted() async throws {
        let fixture = try RecorderFixture()
        _ = try await fixture.recorder.start()
        let update = try await fixture.recorder.ingest(
            LocationSample(
                latitude: 42,
                longitude: -71,
                horizontalAccuracyMeters: 40,
                timestamp: Date(timeIntervalSince1970: 100),
                monotonicTimestampNanoseconds: 10_000_000_000
            )
        )
        XCTAssertEqual(update.ingestResult, .rejected(.invalidAccuracy))
        let points = try await fixture.database.trackingPoints(sessionID: "session")
        XCTAssertTrue(points.isEmpty)
    }

    func testConcurrentAcceptedFixesAreSerializedBeforeSQLiteCommit() async throws {
        let fixture = try RecorderFixture()
        _ = try await fixture.recorder.start()

        let firstTask = Task {
            try await fixture.recorder.ingest(
                LocationSample(
                    latitude: 42,
                    longitude: -71,
                    altitudeMeters: 100,
                    horizontalAccuracyMeters: 5,
                    timestamp: Date(timeIntervalSince1970: 100),
                    monotonicTimestampNanoseconds: 10_000_000_000
                )
            )
        }
        await Task.yield()
        let secondTask = Task {
            try await fixture.recorder.ingest(
                LocationSample(
                    latitude: 42.0001,
                    longitude: -71,
                    altitudeMeters: 101,
                    horizontalAccuracyMeters: 5,
                    timestamp: Date(timeIntervalSince1970: 105),
                    monotonicTimestampNanoseconds: 15_000_000_000
                )
            )
        }

        let first = try await firstTask.value
        let second = try await secondTask.value
        let points = try await fixture.database.trackingPoints(sessionID: "session")
        XCTAssertEqual(first.snapshot.pointCount, 1)
        XCTAssertEqual(second.snapshot.pointCount, 2)
        XCTAssertEqual(points.map(\.sequence), [0, 1])
    }
}

private final class RecorderFixture {
    let directory: URL
    let routeDirectory: URL
    let database: OfflineDatabase
    let clock = ManualTrackingClock()
    let ids = DeterministicIDs([
        "session", "hike", "mark", "mark-operation", "create-operation", "route-operation",
    ])
    let recorder: HikeRecorder

    init() throws {
        directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        routeDirectory = directory.appendingPathComponent("routes", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        database = try OfflineDatabase(
            path: directory.appendingPathComponent("offline.sqlite").path
        )
        recorder = HikeRecorder(
            database: database,
            routeDirectory: routeDirectory,
            clock: clock.value,
            idGenerator: ids.value
        )
    }

    deinit {
        try? FileManager.default.removeItem(at: directory)
    }

    func ingestFirstPoint() async throws -> RecorderUpdate {
        clock.set(wall: 100, monotonic: 10_000)
        return try await recorder.ingest(
            LocationSample(
                latitude: 42,
                longitude: -71,
                altitudeMeters: 100,
                horizontalAccuracyMeters: 5,
                timestamp: Date(timeIntervalSince1970: 100),
                monotonicTimestampNanoseconds: 10_000_000_000
            )
        )
    }

    func ingestSecondPoint() async throws -> RecorderUpdate {
        clock.set(wall: 105, monotonic: 15_000)
        return try await recorder.ingest(
            LocationSample(
                latitude: 42.0001,
                longitude: -71,
                altitudeMeters: 101,
                horizontalAccuracyMeters: 5,
                timestamp: Date(timeIntervalSince1970: 105),
                monotonicTimestampNanoseconds: 15_000_000_000
            )
        )
    }
}

private final class ManualTrackingClock: @unchecked Sendable {
    private let lock = NSLock()
    private var reading = TrackingClockReading(
        wallTime: Date(timeIntervalSince1970: 100),
        monotonicMilliseconds: 10_000,
        bootIdentifier: "boot"
    )

    var value: TrackingClock {
        TrackingClock { [weak self] in
            guard let self else {
                return TrackingClockReading(
                    wallTime: .distantPast,
                    monotonicMilliseconds: 0,
                    bootIdentifier: "missing"
                )
            }
            lock.lock()
            defer { lock.unlock() }
            return reading
        }
    }

    func set(wall: TimeInterval, monotonic: Int64) {
        lock.lock()
        reading = TrackingClockReading(
            wallTime: Date(timeIntervalSince1970: wall),
            monotonicMilliseconds: monotonic,
            bootIdentifier: "boot"
        )
        lock.unlock()
    }
}

private final class DeterministicIDs: @unchecked Sendable {
    private let lock = NSLock()
    private var values: [String]

    init(_ values: [String]) {
        self.values = values
    }

    var value: TrackingIDGenerator {
        TrackingIDGenerator { [weak self] in
            guard let self else { return "missing" }
            lock.lock()
            defer { lock.unlock() }
            return values.isEmpty ? "fallback" : values.removeFirst()
        }
    }
}
