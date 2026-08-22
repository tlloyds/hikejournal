import Foundation
import XCTest

@testable import HikeJournalTracking

final class TrackingSessionTests: XCTestCase {
  func testInjectedClockAndIDsCreateDeterministicStartingSession() {
    let ids = LockedIDSequence(["session-id", "hike-id"])
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = TimeZone(secondsFromGMT: 0)!
    let clock = TrackingClock {
      TrackingClockReading(
        wallTime: Date(timeIntervalSince1970: 1_777_075_200),
        monotonicMilliseconds: 42,
        bootIdentifier: "boot-a"
      )
    }
    let session = TrackingSession.start(
      clock: clock,
      idGenerator: TrackingIDGenerator { ids.next() },
      calendar: calendar
    )

    XCTAssertEqual(session.sessionID, "session-id")
    XCTAssertEqual(session.hikeID, "hike-id")
    XCTAssertEqual(session.status, .starting)
    XCTAssertEqual(session.hikeDate, "2026-04-25")
    XCTAssertEqual(session.startedAtMonotonicMilliseconds, 42)
    XCTAssertTrue(session.segmentStartPending)
  }

  func testPauseResumeCreatesSegmentBoundaryWithoutBridgingDistance() throws {
    var session = makeSession()
    try session.beginRecording(at: reading(wallMilliseconds: 0, monotonicMilliseconds: 1_000))

    guard
      case .accepted(let first, let firstStartsSegment) = session.ingest(
        sample(latitude: 40, wallMilliseconds: 1_000, monotonicMilliseconds: 1_000),
        receivedAt: date(1_000)
      )
    else {
      return XCTFail("Expected first fix")
    }
    XCTAssertEqual(first.segment, 0)
    XCTAssertTrue(firstStartsSegment)

    guard
      case .accepted = session.ingest(
        sample(latitude: 40.0001, wallMilliseconds: 6_000, monotonicMilliseconds: 6_000),
        receivedAt: date(6_000)
      )
    else {
      return XCTFail("Expected walking fix")
    }
    let beforePauseDistance = session.distanceMeters
    XCTAssertGreaterThan(beforePauseDistance, 11)

    try session.pause(at: reading(wallMilliseconds: 10_000, monotonicMilliseconds: 10_000))
    XCTAssertEqual(
      session.ingest(
        sample(latitude: 41, wallMilliseconds: 12_000, monotonicMilliseconds: 12_000),
        receivedAt: date(12_000)
      ),
      .ignored(currentStatus: .paused)
    )
    try session.resume(at: reading(wallMilliseconds: 20_000, monotonicMilliseconds: 20_000))
    XCTAssertEqual(session.currentSegment, 1)
    XCTAssertTrue(session.segmentStartPending)

    guard
      case .accepted(let resumed, let startsSegment) = session.ingest(
        sample(latitude: 40.01, wallMilliseconds: 21_000, monotonicMilliseconds: 21_000),
        receivedAt: date(21_000)
      )
    else {
      return XCTFail("Expected resumed fix")
    }
    XCTAssertEqual(resumed.segment, 1)
    XCTAssertTrue(startsSegment)
    XCTAssertEqual(session.distanceMeters, beforePauseDistance, accuracy: 1e-12)
    XCTAssertEqual(session.routeSegments.map(\.count), [2, 1])
  }

  func testAcceptedFixGapOfSixtySecondsStartsNewSegment() throws {
    var session = makeSession()
    try session.beginRecording(at: reading(wallMilliseconds: 0, monotonicMilliseconds: 1_000))
    _ = session.ingest(
      sample(latitude: 40, wallMilliseconds: 1_000, monotonicMilliseconds: 1_000),
      receivedAt: date(1_000)
    )
    let result = session.ingest(
      sample(latitude: 41, wallMilliseconds: 2_000, monotonicMilliseconds: 61_000),
      receivedAt: date(2_000)
    )

    guard case .accepted(let point, let startsSegment) = result else {
      return XCTFail("Expected gap fix")
    }
    XCTAssertEqual(point.segment, 1)
    XCTAssertTrue(startsSegment)
    XCTAssertEqual(session.distanceMeters, 0)
    XCTAssertEqual(session.routeSegments.map(\.count), [1, 1])
  }

  func testCheckpointedElapsedTimeExcludesPauseAndInterruptedGap() throws {
    var session = makeSession()
    try session.beginRecording(at: reading(wallMilliseconds: 0, monotonicMilliseconds: 1_000))
    XCTAssertEqual(
      session.activeElapsedMilliseconds(
        at: reading(wallMilliseconds: 10_000, monotonicMilliseconds: 11_000)
      ),
      10_000
    )

    session.checkpoint(at: reading(wallMilliseconds: 10_000, monotonicMilliseconds: 11_000))
    XCTAssertEqual(session.checkpointedActiveElapsedMilliseconds, 10_000)
    XCTAssertEqual(
      session.activeElapsedMilliseconds(
        at: reading(wallMilliseconds: 15_000, monotonicMilliseconds: 16_000)
      ),
      15_000
    )

    let persisted = try JSONEncoder().encode(session)
    var restored = try JSONDecoder().decode(TrackingSession.self, from: persisted)
    restored.recoverAfterInterruption(
      at: reading(wallMilliseconds: 90_000, monotonicMilliseconds: 91_000)
    )

    XCTAssertEqual(restored.status, .paused)
    XCTAssertEqual(restored.recoveryReason, .serviceInterrupted)
    XCTAssertEqual(restored.checkpointedActiveElapsedMilliseconds, 10_000)
    XCTAssertEqual(
      restored.activeElapsedMilliseconds(
        at: reading(wallMilliseconds: 500_000, monotonicMilliseconds: 501_000)
      ),
      10_000
    )
  }

  func testRecoveryAfterRebootAndFinalizationAlwaysReturnsPaused() throws {
    var recording = makeSession()
    try recording.beginRecording(at: reading(wallMilliseconds: 0, monotonicMilliseconds: 1_000))
    recording.checkpoint(at: reading(wallMilliseconds: 5_000, monotonicMilliseconds: 6_000))
    recording.recoverAfterInterruption(
      at: reading(wallMilliseconds: 50_000, monotonicMilliseconds: 10, boot: "boot-b")
    )
    XCTAssertEqual(recording.status, .paused)
    XCTAssertEqual(recording.recoveryReason, .deviceRestarted)
    XCTAssertEqual(recording.checkpointedActiveElapsedMilliseconds, 5_000)

    var finalizing = makeSession()
    try finalizing.beginRecording(at: reading(wallMilliseconds: 0, monotonicMilliseconds: 1_000))
    try finalizing.pause(at: reading(wallMilliseconds: 2_000, monotonicMilliseconds: 3_000))
    try finalizing.beginFinalization(
      at: reading(wallMilliseconds: 3_000, monotonicMilliseconds: 4_000)
    )
    finalizing.recoverAfterInterruption(
      at: reading(wallMilliseconds: 4_000, monotonicMilliseconds: 5_000)
    )
    XCTAssertEqual(finalizing.status, .paused)
    XCTAssertEqual(finalizing.recoveryReason, .finalizationInterrupted)
    XCTAssertEqual(finalizing.errorMessage, "Hike finalization was interrupted")
  }

  func testTransitionRulesRequirePausedFinalization() throws {
    var session = makeSession()
    try session.beginRecording(at: reading(wallMilliseconds: 0, monotonicMilliseconds: 1_000))
    XCTAssertThrowsError(
      try session.beginFinalization(
        at: reading(wallMilliseconds: 1_000, monotonicMilliseconds: 2_000)
      )
    ) { error in
      XCTAssertEqual(
        error as? TrackingCoreError,
        .invalidTransition(from: .recording, to: .finalizing)
      )
    }

    try session.pause(at: reading(wallMilliseconds: 2_000, monotonicMilliseconds: 3_000))
    try session.beginFinalization(
      at: reading(wallMilliseconds: 3_000, monotonicMilliseconds: 4_000)
    )
    try session.finish(
      generatedTCXPath: "/routes/session.tcx",
      at: reading(wallMilliseconds: 4_000, monotonicMilliseconds: 5_000)
    )
    XCTAssertEqual(session.status, .finished)
    XCTAssertEqual(session.generatedTCXPath, "/routes/session.tcx")
    XCTAssertEqual(session.finishedAt, date(4_000))
  }

  func testFieldMarkUsesLatestAcceptedFixAndInjectedIdentity() throws {
    var session = makeSession()
    XCTAssertThrowsError(
      try session.makeFieldMark(
        type: .hazard,
        at: reading(wallMilliseconds: 1_000, monotonicMilliseconds: 1_000),
        idGenerator: TrackingIDGenerator { "mark-before-fix" }
      )
    ) { error in
      XCTAssertEqual(error as? TrackingCoreError, .fieldMarkRequiresAcceptedFix)
    }

    try session.beginRecording(at: reading(wallMilliseconds: 0, monotonicMilliseconds: 1_000))
    _ = session.ingest(
      sample(
        latitude: 28.5,
        longitude: -81.25,
        accuracy: 4.5,
        wallMilliseconds: 2_000,
        monotonicMilliseconds: 2_000
      ),
      receivedAt: date(2_000)
    )
    let mark = try session.makeFieldMark(
      type: .trailCondition,
      note: "  washed out  \n",
      at: reading(wallMilliseconds: 3_000, monotonicMilliseconds: 3_000),
      idGenerator: TrackingIDGenerator { "mark-1" }
    )

    XCTAssertEqual(mark.id, "mark-1")
    XCTAssertEqual(mark.hikeID, "hike")
    XCTAssertEqual(mark.recordingSessionID, "session")
    XCTAssertEqual(mark.latitude, 28.5)
    XCTAssertEqual(mark.longitude, -81.25)
    XCTAssertEqual(mark.accuracyMeters, 4.5)
    XCTAssertEqual(mark.type.rawValue, "trail_condition")
    XCTAssertEqual(mark.note, "washed out")
    XCTAssertEqual(mark.syncState, .queued)
  }

  func testLongSessionDistanceAndSequenceRemainNumericallyStable() throws {
    var session = makeSession()
    try session.beginRecording(at: reading(wallMilliseconds: 0, monotonicMilliseconds: 1_000))
    let pointCount = 50_000
    let longitudeStep = 0.00002
    for index in 0..<pointCount {
      let longitude = Double(index) * longitudeStep
      let milliseconds = Int64(index + 1) * 1_000
      let result = session.ingest(
        sample(
          latitude: 0,
          longitude: longitude,
          accuracy: 1,
          wallMilliseconds: milliseconds,
          monotonicMilliseconds: milliseconds
        ),
        receivedAt: date(milliseconds)
      )
      guard case .accepted = result else {
        return XCTFail("Point \(index) was unexpectedly rejected: \(result)")
      }
    }
    // On the equator, the exact path is one great-circle arc. This closed
    // form avoids using the same repeated floating-point summation as the
    // implementation and catches long-session drift.
    let expectedDistance =
      TrackingLocationFilter.earthRadiusMeters
      * (Double(pointCount - 1) * longitudeStep * .pi / 180)

    XCTAssertEqual(session.points.count, pointCount)
    XCTAssertEqual(session.points.last?.sequence, Int64(pointCount - 1))
    XCTAssertEqual(session.distanceMeters, expectedDistance, accuracy: 1e-9)
    XCTAssertTrue(session.distanceMeters.isFinite)
  }

  func testElapsedTimeMathSaturatesAndNeverUsesAnotherBoot() {
    XCTAssertEqual(
      TrackingTimeMath.activeElapsedMilliseconds(
        checkpointedMilliseconds: 10_000,
        activeSinceMonotonicMilliseconds: 20_000,
        status: .recording,
        sameBoot: false,
        nowMonotonicMilliseconds: 90_000
      ),
      10_000
    )
    XCTAssertEqual(
      TrackingTimeMath.activeElapsedMilliseconds(
        checkpointedMilliseconds: Int64.max - 5,
        activeSinceMonotonicMilliseconds: 1,
        status: .recording,
        sameBoot: true,
        nowMonotonicMilliseconds: 100
      ),
      Int64.max
    )
    XCTAssertEqual(
      TrackingTimeMath.recoveredPausedElapsedMilliseconds(
        checkpointedMilliseconds: -1
      ),
      0
    )
  }

  func testPublicDomainAndDependencyTypesAreSendable() {
    requireSendable(TrackingSession.self)
    requireSendable(TrackingSnapshot.self)
    requireSendable(LocationSample.self)
    requireSendable(TrackingLocationFilter.self)
    requireSendable(WholeMileAnnouncementScheduler.self)
    requireSendable(TCXWriter.self)
    requireSendable(TrackingClock.self)
    requireSendable(TrackingIDGenerator.self)
  }

  private func makeSession() -> TrackingSession {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = TimeZone(secondsFromGMT: 0)!
    return TrackingSession(
      sessionID: "session",
      hikeID: "hike",
      startedAt: reading(wallMilliseconds: 0, monotonicMilliseconds: 1_000),
      calendar: calendar
    )
  }

  private func sample(
    latitude: Double,
    longitude: Double = -74,
    altitude: Double? = 100,
    accuracy: Double = 3,
    wallMilliseconds: Int64,
    monotonicMilliseconds: Int64
  ) -> LocationSample {
    LocationSample(
      latitude: latitude,
      longitude: longitude,
      altitudeMeters: altitude,
      horizontalAccuracyMeters: accuracy,
      timestamp: date(wallMilliseconds),
      monotonicTimestampNanoseconds: monotonicMilliseconds * 1_000_000
    )
  }

  private func reading(
    wallMilliseconds: Int64,
    monotonicMilliseconds: Int64,
    boot: String = "boot-a"
  ) -> TrackingClockReading {
    TrackingClockReading(
      wallTime: date(wallMilliseconds),
      monotonicMilliseconds: monotonicMilliseconds,
      bootIdentifier: boot
    )
  }

  private func date(_ milliseconds: Int64) -> Date {
    Date(timeIntervalSince1970: Double(milliseconds) / 1_000)
  }
}

private func requireSendable<T: Sendable>(_: T.Type) {}

private final class LockedIDSequence: @unchecked Sendable {
  private let lock = NSLock()
  private var values: [String]

  init(_ values: [String]) {
    self.values = values
  }

  func next() -> String {
    lock.lock()
    defer { lock.unlock() }
    return values.removeFirst()
  }
}
