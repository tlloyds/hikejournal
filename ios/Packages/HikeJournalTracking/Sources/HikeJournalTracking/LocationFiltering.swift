import Foundation

public struct LocationFilterConfiguration: Codable, Equatable, Sendable {
  public var maximumAccuracyMeters: Double
  public var maximumAgeMilliseconds: Int64
  public var maximumFutureMilliseconds: Int64
  public var minimumDistanceMeters: Double
  public var accuracyDriftFactor: Double
  public var maximumSpeedMetersPerSecond: Double
  public var segmentGapMilliseconds: Int64

  public init(
    maximumAccuracyMeters: Double = 25,
    maximumAgeMilliseconds: Int64 = 30_000,
    maximumFutureMilliseconds: Int64 = 10_000,
    minimumDistanceMeters: Double = 1.5,
    accuracyDriftFactor: Double = 0.35,
    maximumSpeedMetersPerSecond: Double = 12,
    segmentGapMilliseconds: Int64 = 60_000
  ) {
    self.maximumAccuracyMeters = maximumAccuracyMeters
    self.maximumAgeMilliseconds = maximumAgeMilliseconds
    self.maximumFutureMilliseconds = maximumFutureMilliseconds
    self.minimumDistanceMeters = minimumDistanceMeters
    self.accuracyDriftFactor = accuracyDriftFactor
    self.maximumSpeedMetersPerSecond = maximumSpeedMetersPerSecond
    self.segmentGapMilliseconds = segmentGapMilliseconds
  }

  public static let androidParity = LocationFilterConfiguration()
}

public struct TrackingLocationFilter: Sendable {
  public static let earthRadiusMeters = 6_371_008.8

  public let configuration: LocationFilterConfiguration

  public init(configuration: LocationFilterConfiguration = .androidParity) {
    self.configuration = configuration
  }

  public func evaluate(
    _ sample: LocationSample,
    receivedAt: Date,
    previous: LocationSample?,
    currentSegment: Int,
    segmentStartPending: Bool
  ) -> LocationEvaluation {
    guard sample.latitude.isFinite,
      sample.longitude.isFinite,
      (-90.0...90.0).contains(sample.latitude),
      (-180.0...180.0).contains(sample.longitude)
    else {
      return .rejected(.invalidCoordinate)
    }
    guard sample.horizontalAccuracyMeters.isFinite,
      sample.horizontalAccuracyMeters >= 0,
      sample.horizontalAccuracyMeters <= configuration.maximumAccuracyMeters
    else {
      return .rejected(.invalidAccuracy)
    }

    let receivedMilliseconds = epochMilliseconds(receivedAt)
    let fixMilliseconds = epochMilliseconds(sample.timestamp)
    let age = subtract(receivedMilliseconds, fixMilliseconds)
    if age > configuration.maximumAgeMilliseconds {
      return .rejected(.stale)
    }
    if age < -configuration.maximumFutureMilliseconds {
      return .rejected(.future)
    }

    let elapsedDeltaMilliseconds: Int64?
    if let previous {
      if let currentMonotonic = usableMonotonic(sample.monotonicTimestampNanoseconds),
        let previousMonotonic = usableMonotonic(previous.monotonicTimestampNanoseconds)
      {
        guard currentMonotonic > previousMonotonic else {
          return .rejected(.outOfOrder)
        }
        elapsedDeltaMilliseconds = (currentMonotonic - previousMonotonic) / 1_000_000
      } else {
        elapsedDeltaMilliseconds = subtract(
          fixMilliseconds,
          epochMilliseconds(previous.timestamp)
        )
      }
    } else {
      elapsedDeltaMilliseconds = nil
    }

    if let elapsedDeltaMilliseconds, elapsedDeltaMilliseconds <= 0 {
      return .rejected(.outOfOrder)
    }

    let gapStartsSegment =
      previous != nil
      && (elapsedDeltaMilliseconds ?? 0) >= configuration.segmentGapMilliseconds
    if previous == nil || segmentStartPending || gapStartsSegment {
      let nextSegment =
        currentSegment == Int.max ? Int.max : currentSegment + 1
      return .accepted(
        AcceptedLocation(
          segment: gapStartsSegment && !segmentStartPending
            ? nextSegment
            : currentSegment,
          distanceFromPreviousMeters: 0,
          startsSegment: true
        )
      )
    }

    guard let previous, let elapsedDeltaMilliseconds else {
      return .rejected(.outOfOrder)
    }
    let distance = Self.haversineMeters(
      latitudeA: previous.latitude,
      longitudeA: previous.longitude,
      latitudeB: sample.latitude,
      longitudeB: sample.longitude
    )
    let driftGate = max(
      configuration.minimumDistanceMeters,
      min(
        sample.horizontalAccuracyMeters,
        previous.horizontalAccuracyMeters
      ) * configuration.accuracyDriftFactor
    )
    if distance < driftGate {
      return .rejected(.jitter)
    }

    let elapsedSeconds = Double(elapsedDeltaMilliseconds) / 1_000
    if elapsedSeconds <= 0
      || distance / elapsedSeconds > configuration.maximumSpeedMetersPerSecond
    {
      return .rejected(.implausibleSpeed)
    }
    return .accepted(
      AcceptedLocation(
        segment: currentSegment,
        distanceFromPreviousMeters: distance,
        startsSegment: false
      )
    )
  }

  public static func haversineMeters(
    latitudeA: Double,
    longitudeA: Double,
    latitudeB: Double,
    longitudeB: Double
  ) -> Double {
    let latitude1 = latitudeA * .pi / 180
    let latitude2 = latitudeB * .pi / 180
    let latitudeDelta = latitude2 - latitude1
    let longitudeDelta = (longitudeB - longitudeA) * .pi / 180
    let haversine =
      sin(latitudeDelta / 2) * sin(latitudeDelta / 2)
      + cos(latitude1) * cos(latitude2)
      * sin(longitudeDelta / 2) * sin(longitudeDelta / 2)
    let clamped = min(1, max(0, haversine))
    return earthRadiusMeters * 2 * asin(sqrt(clamped))
  }
}

@inline(__always)
private func usableMonotonic(_ value: Int64?) -> Int64? {
  guard let value, value > 0 else { return nil }
  return value
}

@inline(__always)
internal func epochMilliseconds(_ date: Date) -> Int64 {
  let value = date.timeIntervalSince1970 * 1_000
  if value >= Double(Int64.max) { return Int64.max }
  if value <= Double(Int64.min) { return Int64.min }
  return Int64(value.rounded(.towardZero))
}

@inline(__always)
private func subtract(_ lhs: Int64, _ rhs: Int64) -> Int64 {
  let (value, overflow) = lhs.subtractingReportingOverflow(rhs)
  guard overflow else { return value }
  return lhs >= rhs ? Int64.max : Int64.min
}
