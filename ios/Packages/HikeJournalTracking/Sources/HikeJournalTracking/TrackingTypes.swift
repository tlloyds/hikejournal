import Dispatch
import Foundation

public enum TrackingStatus: String, Codable, CaseIterable, Sendable {
  case starting
  case recording
  case paused
  case finalizing
  case finished
}

public enum TrackingRecoveryReason: String, Codable, Sendable {
  case finalizationInterrupted = "finalization_interrupted"
  case deviceRestarted = "device_restarted"
  case permissionRevoked = "permission_revoked"
  case notificationPermissionRevoked = "notification_permission_revoked"
  case locationDisabled = "location_disabled"
  case serviceInterrupted = "service_interrupted"
  case serviceStartFailed = "service_start_failed"
  case finalizationFailed = "finalization_failed"
}

public enum TrackingCoreError: Error, Equatable, Sendable {
  case invalidTransition(from: TrackingStatus, to: TrackingStatus)
  case locationRequiresRecording(current: TrackingStatus)
  case fieldMarkRequiresAcceptedFix
  case unsafeSessionIdentifier
}

extension TrackingCoreError: LocalizedError {
  public var errorDescription: String? {
    switch self {
    case .invalidTransition(let from, let to):
      return "Cannot transition from \(from.rawValue) to \(to.rawValue)."
    case .locationRequiresRecording(let current):
      return "A location cannot be recorded while tracking is \(current.rawValue)."
    case .fieldMarkRequiresAcceptedFix:
      return "Wait for the first accepted GPS fix before adding a Field Mark."
    case .unsafeSessionIdentifier:
      return "The tracking session identifier is not safe for a route filename."
    }
  }
}

/// A typed, platform-neutral location fix. Monotonic time is preferred for
/// ordering, speed, and segment gaps; wall time remains the persisted fallback.
public struct LocationSample: Codable, Equatable, Sendable {
  public var latitude: Double
  public var longitude: Double
  public var altitudeMeters: Double?
  public var horizontalAccuracyMeters: Double
  public var timestamp: Date
  public var monotonicTimestampNanoseconds: Int64?

  public init(
    latitude: Double,
    longitude: Double,
    altitudeMeters: Double? = nil,
    horizontalAccuracyMeters: Double,
    timestamp: Date,
    monotonicTimestampNanoseconds: Int64? = nil
  ) {
    self.latitude = latitude
    self.longitude = longitude
    self.altitudeMeters = altitudeMeters
    self.horizontalAccuracyMeters = horizontalAccuracyMeters
    self.timestamp = timestamp
    self.monotonicTimestampNanoseconds = monotonicTimestampNanoseconds
  }
}

public enum LocationRejectionReason: String, Codable, Equatable, Sendable {
  case invalidCoordinate = "invalid_coordinate"
  case invalidAccuracy = "invalid_accuracy"
  case stale
  case future
  case outOfOrder = "out_of_order"
  case jitter
  case implausibleSpeed = "implausible_speed"
}

public struct AcceptedLocation: Equatable, Sendable {
  public let segment: Int
  public let distanceFromPreviousMeters: Double
  public let startsSegment: Bool

  public init(
    segment: Int,
    distanceFromPreviousMeters: Double,
    startsSegment: Bool
  ) {
    self.segment = segment
    self.distanceFromPreviousMeters = distanceFromPreviousMeters
    self.startsSegment = startsSegment
  }
}

public enum LocationEvaluation: Equatable, Sendable {
  case accepted(AcceptedLocation)
  case rejected(LocationRejectionReason)
}

public struct TrackingPoint: Codable, Equatable, Sendable {
  public let sequence: Int64
  public let segment: Int
  public let latitude: Double
  public let longitude: Double
  public let altitudeMeters: Double?
  public let accuracyMeters: Double
  public let timestamp: Date
  public let monotonicTimestampNanoseconds: Int64?
  public let distanceFromPreviousMeters: Double

  public init(
    sequence: Int64,
    segment: Int,
    latitude: Double,
    longitude: Double,
    altitudeMeters: Double?,
    accuracyMeters: Double,
    timestamp: Date,
    monotonicTimestampNanoseconds: Int64?,
    distanceFromPreviousMeters: Double
  ) {
    self.sequence = sequence
    self.segment = segment
    self.latitude = latitude
    self.longitude = longitude
    self.altitudeMeters = altitudeMeters
    self.accuracyMeters = accuracyMeters
    self.timestamp = timestamp
    self.monotonicTimestampNanoseconds = monotonicTimestampNanoseconds
    self.distanceFromPreviousMeters = distanceFromPreviousMeters
  }

  public var locationSample: LocationSample {
    LocationSample(
      latitude: latitude,
      longitude: longitude,
      altitudeMeters: altitudeMeters,
      horizontalAccuracyMeters: accuracyMeters,
      timestamp: timestamp,
      monotonicTimestampNanoseconds: monotonicTimestampNanoseconds
    )
  }
}

public enum LocationIngestResult: Equatable, Sendable {
  case accepted(point: TrackingPoint, startsSegment: Bool)
  case rejected(LocationRejectionReason)
  case ignored(currentStatus: TrackingStatus)
}

public struct TrackingSnapshot: Codable, Equatable, Sendable {
  public let sessionID: String
  public let hikeID: String
  public let status: TrackingStatus
  public let startedAt: Date
  public let hikeDate: String
  public let distanceMeters: Double
  public let activeElapsedMilliseconds: Int64
  public let currentSegment: Int
  public let routeSegments: [[TrackingPoint]]
  public let lastAccuracyMeters: Double?
  public let lastFixTimestamp: Date?
  public let pointCount: Int
  public let generatedTCXPath: String?
  public let recoveryReason: TrackingRecoveryReason?
  public let errorMessage: String?

  public init(
    sessionID: String,
    hikeID: String,
    status: TrackingStatus,
    startedAt: Date,
    hikeDate: String,
    distanceMeters: Double,
    activeElapsedMilliseconds: Int64,
    currentSegment: Int,
    routeSegments: [[TrackingPoint]],
    lastAccuracyMeters: Double?,
    lastFixTimestamp: Date?,
    pointCount: Int,
    generatedTCXPath: String?,
    recoveryReason: TrackingRecoveryReason?,
    errorMessage: String?
  ) {
    self.sessionID = sessionID
    self.hikeID = hikeID
    self.status = status
    self.startedAt = startedAt
    self.hikeDate = hikeDate
    self.distanceMeters = distanceMeters
    self.activeElapsedMilliseconds = activeElapsedMilliseconds
    self.currentSegment = currentSegment
    self.routeSegments = routeSegments
    self.lastAccuracyMeters = lastAccuracyMeters
    self.lastFixTimestamp = lastFixTimestamp
    self.pointCount = pointCount
    self.generatedTCXPath = generatedTCXPath
    self.recoveryReason = recoveryReason
    self.errorMessage = errorMessage
  }
}

public struct TrackingClockReading: Codable, Equatable, Sendable {
  public let wallTime: Date
  public let monotonicMilliseconds: Int64
  public let bootIdentifier: String

  public init(
    wallTime: Date,
    monotonicMilliseconds: Int64,
    bootIdentifier: String
  ) {
    self.wallTime = wallTime
    self.monotonicMilliseconds = monotonicMilliseconds
    self.bootIdentifier = bootIdentifier
  }
}

public struct TrackingClock: Sendable {
  private let readValue: @Sendable () -> TrackingClockReading

  public init(read: @escaping @Sendable () -> TrackingClockReading) {
    readValue = read
  }

  public func read() -> TrackingClockReading {
    readValue()
  }

  public static let system = TrackingClock {
    let wallTime = Date()
    let monotonicMilliseconds = Int64(
      min(DispatchTime.now().uptimeNanoseconds / 1_000_000, UInt64(Int64.max))
    )
    let wallMilliseconds = Int64(
      (wallTime.timeIntervalSince1970 * 1_000).rounded(.towardZero)
    )
    let bootMarker = (wallMilliseconds - monotonicMilliseconds) / (5 * 60_000)
    return TrackingClockReading(
      wallTime: wallTime,
      monotonicMilliseconds: monotonicMilliseconds,
      bootIdentifier: String(bootMarker)
    )
  }
}

public struct TrackingIDGenerator: Sendable {
  private let makeValue: @Sendable () -> String

  public init(make: @escaping @Sendable () -> String) {
    makeValue = make
  }

  public func makeID() -> String {
    makeValue()
  }

  public static let random = TrackingIDGenerator {
    UUID().uuidString.lowercased()
  }
}

public enum FieldMarkType: String, Codable, CaseIterable, Sendable {
  case wildlife
  case plant
  case trailCondition = "trail_condition"
  case bridge
  case boardwalk
  case water
  case campsite
  case hazard
  case note
}

public enum FieldMarkSyncState: String, Codable, Sendable {
  case queued
  case synced
}

public struct FieldMark: Codable, Equatable, Sendable, Identifiable {
  public let id: String
  public let hikeID: String
  public let recordingSessionID: String?
  public let markedAt: Date
  public let latitude: Double
  public let longitude: Double
  public let accuracyMeters: Double?
  public let type: FieldMarkType
  public let note: String
  public let syncState: FieldMarkSyncState

  public init(
    id: String,
    hikeID: String,
    recordingSessionID: String?,
    markedAt: Date,
    latitude: Double,
    longitude: Double,
    accuracyMeters: Double?,
    type: FieldMarkType,
    note: String,
    syncState: FieldMarkSyncState = .queued
  ) {
    self.id = id
    self.hikeID = hikeID
    self.recordingSessionID = recordingSessionID
    self.markedAt = markedAt
    self.latitude = latitude
    self.longitude = longitude
    self.accuracyMeters = accuracyMeters
    self.type = type
    self.note = note.trimmingCharacters(in: .whitespacesAndNewlines)
    self.syncState = syncState
  }
}
