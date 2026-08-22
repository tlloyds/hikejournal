import Foundation

public enum TrackingTimeMath {
  public static func activeElapsedMilliseconds(
    checkpointedMilliseconds: Int64,
    activeSinceMonotonicMilliseconds: Int64?,
    status: TrackingStatus,
    sameBoot: Bool,
    nowMonotonicMilliseconds: Int64
  ) -> Int64 {
    let checkpoint = max(0, checkpointedMilliseconds)
    guard status == .recording,
      sameBoot,
      let activeSinceMonotonicMilliseconds
    else {
      return checkpoint
    }
    let delta = max(
      0,
      nonnegativeDifference(
        nowMonotonicMilliseconds,
        activeSinceMonotonicMilliseconds
      )
    )
    return saturatingAdd(checkpoint, delta)
  }

  /// Interrupted recovery cannot prove the recorder stayed alive after its
  /// last durable checkpoint, so uncheckpointed monotonic time is discarded.
  public static func recoveredPausedElapsedMilliseconds(
    checkpointedMilliseconds: Int64
  ) -> Int64 {
    max(0, checkpointedMilliseconds)
  }
}

public struct TrackingSession: Codable, Equatable, Sendable {
  public private(set) var sessionID: String
  public private(set) var hikeID: String
  public private(set) var status: TrackingStatus
  public private(set) var startedAt: Date
  public private(set) var startedAtMonotonicMilliseconds: Int64
  public private(set) var hikeDate: String
  public private(set) var bootIdentifier: String
  public private(set) var checkpointedActiveElapsedMilliseconds: Int64
  public private(set) var activeSinceMonotonicMilliseconds: Int64?
  public private(set) var distanceMeters: Double
  public private(set) var currentSegment: Int
  public private(set) var segmentStartPending: Bool
  public private(set) var nextPointSequence: Int64
  public private(set) var points: [TrackingPoint]
  public private(set) var generatedTCXPath: String?
  public private(set) var recoveryReason: TrackingRecoveryReason?
  public private(set) var errorMessage: String?
  public private(set) var updatedAt: Date
  public private(set) var finishedAt: Date?

  private var distanceCompensationMeters: Double

  public init(
    sessionID: String,
    hikeID: String,
    startedAt reading: TrackingClockReading,
    calendar: Calendar = .current
  ) {
    self.sessionID = sessionID
    self.hikeID = hikeID
    status = .starting
    startedAt = reading.wallTime
    startedAtMonotonicMilliseconds = reading.monotonicMilliseconds
    hikeDate = Self.hikeDateString(for: reading.wallTime, calendar: calendar)
    bootIdentifier = reading.bootIdentifier
    checkpointedActiveElapsedMilliseconds = 0
    activeSinceMonotonicMilliseconds = nil
    distanceMeters = 0
    currentSegment = 0
    segmentStartPending = true
    nextPointSequence = 0
    points = []
    generatedTCXPath = nil
    recoveryReason = nil
    errorMessage = nil
    updatedAt = reading.wallTime
    finishedAt = nil
    distanceCompensationMeters = 0
  }

  public static func start(
    clock: TrackingClock = .system,
    idGenerator: TrackingIDGenerator = .random,
    calendar: Calendar = .current
  ) -> TrackingSession {
    TrackingSession(
      sessionID: idGenerator.makeID(),
      hikeID: idGenerator.makeID(),
      startedAt: clock.read(),
      calendar: calendar
    )
  }

  public var lastAcceptedPoint: TrackingPoint? {
    points.last
  }

  public var routeSegments: [[TrackingPoint]] {
    guard !points.isEmpty else { return [] }
    var result: [[TrackingPoint]] = []
    var current: [TrackingPoint] = []
    var segment: Int?
    for point in points.sorted(by: { $0.sequence < $1.sequence }) {
      if segment != point.segment {
        if !current.isEmpty { result.append(current) }
        current = []
        segment = point.segment
      }
      current.append(point)
    }
    if !current.isEmpty { result.append(current) }
    return result
  }

  public func activeElapsedMilliseconds(at reading: TrackingClockReading) -> Int64 {
    TrackingTimeMath.activeElapsedMilliseconds(
      checkpointedMilliseconds: checkpointedActiveElapsedMilliseconds,
      activeSinceMonotonicMilliseconds: activeSinceMonotonicMilliseconds,
      status: status,
      sameBoot: bootIdentifier == reading.bootIdentifier,
      nowMonotonicMilliseconds: reading.monotonicMilliseconds
    )
  }

  public func snapshot(at reading: TrackingClockReading) -> TrackingSnapshot {
    TrackingSnapshot(
      sessionID: sessionID,
      hikeID: hikeID,
      status: status,
      startedAt: startedAt,
      hikeDate: hikeDate,
      distanceMeters: distanceMeters,
      activeElapsedMilliseconds: activeElapsedMilliseconds(at: reading),
      currentSegment: currentSegment,
      routeSegments: routeSegments,
      lastAccuracyMeters: points.last?.accuracyMeters,
      lastFixTimestamp: points.last?.timestamp,
      pointCount: points.count,
      generatedTCXPath: generatedTCXPath,
      recoveryReason: recoveryReason,
      errorMessage: errorMessage
    )
  }

  public mutating func beginRecording(at reading: TrackingClockReading) throws {
    if status == .recording { return }
    try requireTransition(to: .recording, allowed: [.starting])
    status = .recording
    bootIdentifier = reading.bootIdentifier
    activeSinceMonotonicMilliseconds = reading.monotonicMilliseconds
    updatedAt = reading.wallTime
  }

  public mutating func checkpoint(at reading: TrackingClockReading) {
    guard status == .recording else { return }
    guard bootIdentifier == reading.bootIdentifier,
      reading.monotonicMilliseconds >= startedAtMonotonicMilliseconds
    else {
      recoverAfterInterruption(reason: .deviceRestarted, at: reading)
      return
    }
    checkpointedActiveElapsedMilliseconds = activeElapsedMilliseconds(at: reading)
    activeSinceMonotonicMilliseconds = reading.monotonicMilliseconds
    updatedAt = reading.wallTime
  }

  public mutating func pause(at reading: TrackingClockReading) throws {
    try requireTransition(to: .paused, allowed: [.recording])
    checkpointedActiveElapsedMilliseconds = activeElapsedMilliseconds(at: reading)
    activeSinceMonotonicMilliseconds = nil
    status = .paused
    updatedAt = reading.wallTime
  }

  public mutating func resume(at reading: TrackingClockReading) throws {
    try requireTransition(to: .recording, allowed: [.paused])
    status = .recording
    bootIdentifier = reading.bootIdentifier
    activeSinceMonotonicMilliseconds = reading.monotonicMilliseconds
    currentSegment = currentSegment == Int.max ? Int.max : currentSegment + 1
    segmentStartPending = true
    recoveryReason = nil
    errorMessage = nil
    updatedAt = reading.wallTime
  }

  public mutating func beginFinalization(at reading: TrackingClockReading) throws {
    try requireTransition(to: .finalizing, allowed: [.paused])
    status = .finalizing
    errorMessage = nil
    updatedAt = reading.wallTime
  }

  public mutating func failFinalization(
    message: String,
    at reading: TrackingClockReading
  ) throws {
    try requireTransition(to: .paused, allowed: [.finalizing])
    status = .paused
    recoveryReason = .finalizationFailed
    errorMessage = message
    updatedAt = reading.wallTime
  }

  public mutating func finish(
    generatedTCXPath: String? = nil,
    at reading: TrackingClockReading
  ) throws {
    try requireTransition(to: .finished, allowed: [.finalizing])
    status = .finished
    self.generatedTCXPath = generatedTCXPath ?? self.generatedTCXPath
    recoveryReason = nil
    errorMessage = nil
    updatedAt = reading.wallTime
    finishedAt = reading.wallTime
  }

  /// Restores any interrupted active/finalizing session in a safe paused
  /// state. Only durable checkpointed active time survives.
  public mutating func recoverAfterInterruption(
    reason: TrackingRecoveryReason? = nil,
    at reading: TrackingClockReading
  ) {
    switch status {
    case .starting, .recording:
      let inferredReason: TrackingRecoveryReason
      if let reason {
        inferredReason = reason
      } else if reading.bootIdentifier != bootIdentifier
        || reading.monotonicMilliseconds < startedAtMonotonicMilliseconds
      {
        inferredReason = .deviceRestarted
      } else {
        inferredReason = .serviceInterrupted
      }
      status = .paused
      checkpointedActiveElapsedMilliseconds =
        TrackingTimeMath.recoveredPausedElapsedMilliseconds(
          checkpointedMilliseconds: checkpointedActiveElapsedMilliseconds
        )
      activeSinceMonotonicMilliseconds = nil
      recoveryReason = inferredReason
      errorMessage = nil
      updatedAt = reading.wallTime
    case .finalizing:
      status = .paused
      activeSinceMonotonicMilliseconds = nil
      recoveryReason = .finalizationInterrupted
      errorMessage = "Hike finalization was interrupted"
      updatedAt = reading.wallTime
    case .paused, .finished:
      break
    }
  }

  public mutating func pauseAfterServiceFailure(
    message: String,
    at reading: TrackingClockReading
  ) {
    guard status == .starting || status == .recording else { return }
    status = .paused
    checkpointedActiveElapsedMilliseconds =
      TrackingTimeMath.recoveredPausedElapsedMilliseconds(
        checkpointedMilliseconds: checkpointedActiveElapsedMilliseconds
      )
    activeSinceMonotonicMilliseconds = nil
    recoveryReason = .serviceStartFailed
    errorMessage = message
    updatedAt = reading.wallTime
  }

  @discardableResult
  public mutating func ingest(
    _ sample: LocationSample,
    receivedAt: Date,
    filter: TrackingLocationFilter = TrackingLocationFilter()
  ) -> LocationIngestResult {
    guard status == .recording else {
      return .ignored(currentStatus: status)
    }
    let evaluation = filter.evaluate(
      sample,
      receivedAt: receivedAt,
      previous: points.last?.locationSample,
      currentSegment: currentSegment,
      segmentStartPending: segmentStartPending
    )
    switch evaluation {
    case .rejected(let reason):
      return .rejected(reason)
    case .accepted(let accepted):
      let altitude = sample.altitudeMeters.flatMap { $0.isFinite ? $0 : nil }
      let point = TrackingPoint(
        sequence: nextPointSequence,
        segment: accepted.segment,
        latitude: sample.latitude,
        longitude: sample.longitude,
        altitudeMeters: altitude,
        accuracyMeters: sample.horizontalAccuracyMeters,
        timestamp: sample.timestamp,
        monotonicTimestampNanoseconds: sample.monotonicTimestampNanoseconds,
        distanceFromPreviousMeters: accepted.distanceFromPreviousMeters
      )
      points.append(point)
      addDistance(accepted.distanceFromPreviousMeters)
      currentSegment = accepted.segment
      segmentStartPending = false
      if nextPointSequence < Int64.max { nextPointSequence += 1 }
      updatedAt = receivedAt
      return .accepted(point: point, startsSegment: accepted.startsSegment)
    }
  }

  public func makeFieldMark(
    type: FieldMarkType,
    note: String = "",
    at reading: TrackingClockReading,
    idGenerator: TrackingIDGenerator = .random
  ) throws -> FieldMark {
    guard let point = points.last else {
      throw TrackingCoreError.fieldMarkRequiresAcceptedFix
    }
    return FieldMark(
      id: idGenerator.makeID(),
      hikeID: hikeID,
      recordingSessionID: sessionID,
      markedAt: reading.wallTime,
      latitude: point.latitude,
      longitude: point.longitude,
      accuracyMeters: point.accuracyMeters,
      type: type,
      note: note,
      syncState: .queued
    )
  }

  private mutating func addDistance(_ value: Double) {
    guard value.isFinite, value >= 0 else { return }
    let corrected = value - distanceCompensationMeters
    let next = distanceMeters + corrected
    distanceCompensationMeters = (next - distanceMeters) - corrected
    distanceMeters = next
  }

  private func requireTransition(
    to target: TrackingStatus,
    allowed: Set<TrackingStatus>
  ) throws {
    guard allowed.contains(status) else {
      throw TrackingCoreError.invalidTransition(from: status, to: target)
    }
  }

  private static func hikeDateString(for date: Date, calendar: Calendar) -> String {
    let components = calendar.dateComponents([.year, .month, .day], from: date)
    return String(
      format: "%04d-%02d-%02d",
      locale: Locale(identifier: "en_US_POSIX"),
      components.year ?? 0,
      components.month ?? 0,
      components.day ?? 0
    )
  }
}

@inline(__always)
private func nonnegativeDifference(_ lhs: Int64, _ rhs: Int64) -> Int64 {
  guard lhs > rhs else { return 0 }
  let (difference, overflow) = lhs.subtractingReportingOverflow(rhs)
  return overflow ? Int64.max : difference
}

@inline(__always)
private func saturatingAdd(_ lhs: Int64, _ rhs: Int64) -> Int64 {
  let (sum, overflow) = lhs.addingReportingOverflow(rhs)
  return overflow ? Int64.max : max(0, sum)
}
