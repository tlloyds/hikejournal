import Foundation
import XCTest

@testable import HikeJournalTracking

final class LocationFilterTests: XCTestCase {
  private let filter = TrackingLocationFilter()

  func testAndroidParityConfigurationPinsAuditedThresholds() {
    let configuration = LocationFilterConfiguration.androidParity

    XCTAssertEqual(configuration.maximumAccuracyMeters, 25)
    XCTAssertEqual(configuration.maximumAgeMilliseconds, 30_000)
    XCTAssertEqual(configuration.maximumFutureMilliseconds, 10_000)
    XCTAssertEqual(configuration.minimumDistanceMeters, 1.5)
    XCTAssertEqual(configuration.accuracyDriftFactor, 0.35)
    XCTAssertEqual(configuration.maximumSpeedMetersPerSecond, 12)
    XCTAssertEqual(configuration.segmentGapMilliseconds, 60_000)
  }

  func testAcceptsWalkingMovementAndMeasuresHaversineDistance() {
    let previous = sample(
      latitude: 40, epochMilliseconds: 1_000, monotonicNanoseconds: 1_000_000_000)
    let current = sample(
      latitude: 40.0001, epochMilliseconds: 6_000, monotonicNanoseconds: 6_000_000_000)

    let result = filter.evaluate(
      current,
      receivedAt: date(milliseconds: 6_000),
      previous: previous,
      currentSegment: 0,
      segmentStartPending: false
    )

    guard case .accepted(let accepted) = result else {
      return XCTFail("Expected accepted walking point, got \(result)")
    }
    XCTAssertEqual(accepted.segment, 0)
    XCTAssertFalse(accepted.startsSegment)
    XCTAssertEqual(accepted.distanceFromPreviousMeters, 11.12, accuracy: 0.2)
  }

  func testAccuracyAdjustedGateRejectsDriftAndUsesBetterFixAccuracy() {
    let previous = sample(
      latitude: 40,
      accuracy: 20,
      epochMilliseconds: 1_000,
      monotonicNanoseconds: 1_000_000_000
    )
    let drift = sample(
      latitude: 40.00005,
      accuracy: 20,
      epochMilliseconds: 6_000,
      monotonicNanoseconds: 6_000_000_000
    )
    XCTAssertEqual(
      filter.evaluate(
        drift,
        receivedAt: date(milliseconds: 6_000),
        previous: previous,
        currentSegment: 0,
        segmentStartPending: false
      ),
      .rejected(.jitter)
    )

    let preciseCurrent = sample(
      latitude: 40.000018,
      accuracy: 3,
      epochMilliseconds: 6_000,
      monotonicNanoseconds: 6_000_000_000
    )
    guard
      case .accepted = filter.evaluate(
        preciseCurrent,
        receivedAt: date(milliseconds: 6_000),
        previous: previous,
        currentSegment: 0,
        segmentStartPending: false
      )
    else {
      return XCTFail("The 0.35× gate must use the better of the two accuracies")
    }
  }

  func testCoordinateAndAccuracyValidationRejectsEveryInvalidShape() {
    let invalidCoordinates = [
      sample(latitude: .nan, epochMilliseconds: 1_000),
      sample(latitude: .infinity, epochMilliseconds: 1_000),
      sample(latitude: 90.0001, epochMilliseconds: 1_000),
      sample(longitude: -180.0001, epochMilliseconds: 1_000),
    ]
    for value in invalidCoordinates {
      XCTAssertEqual(
        filter.evaluate(
          value,
          receivedAt: date(milliseconds: 1_000),
          previous: nil,
          currentSegment: 0,
          segmentStartPending: true
        ),
        .rejected(.invalidCoordinate)
      )
    }

    for accuracy in [Double.nan, -.infinity, -0.01, 25.01] {
      XCTAssertEqual(
        filter.evaluate(
          sample(accuracy: accuracy, epochMilliseconds: 1_000),
          receivedAt: date(milliseconds: 1_000),
          previous: nil,
          currentSegment: 0,
          segmentStartPending: true
        ),
        .rejected(.invalidAccuracy)
      )
    }
  }

  func testStaleAndFutureBoundsAreInclusiveAtAndroidThresholds() {
    let fix = sample(epochMilliseconds: 10_000)
    XCTAssertEqual(
      filter.evaluate(
        fix,
        receivedAt: date(milliseconds: 40_000),
        previous: nil,
        currentSegment: 0,
        segmentStartPending: true
      ),
      .accepted(AcceptedLocation(segment: 0, distanceFromPreviousMeters: 0, startsSegment: true))
    )
    XCTAssertEqual(
      filter.evaluate(
        fix,
        receivedAt: date(milliseconds: 40_001),
        previous: nil,
        currentSegment: 0,
        segmentStartPending: true
      ),
      .rejected(.stale)
    )
    XCTAssertEqual(
      filter.evaluate(
        fix,
        receivedAt: date(milliseconds: 0),
        previous: nil,
        currentSegment: 0,
        segmentStartPending: true
      ),
      .accepted(AcceptedLocation(segment: 0, distanceFromPreviousMeters: 0, startsSegment: true))
    )
    XCTAssertEqual(
      filter.evaluate(
        sample(epochMilliseconds: 10_001),
        receivedAt: date(milliseconds: 0),
        previous: nil,
        currentSegment: 0,
        segmentStartPending: true
      ),
      .rejected(.future)
    )
  }

  func testMonotonicTimeControlsOrderingAndSpeedWithMatchingWallTimestamps() {
    let previous = sample(
      latitude: 40, epochMilliseconds: 6_000, monotonicNanoseconds: 1_000_000_000)
    let current = sample(
      latitude: 40.0001, epochMilliseconds: 6_000, monotonicNanoseconds: 6_000_000_000)

    guard
      case .accepted = filter.evaluate(
        current,
        receivedAt: date(milliseconds: 6_000),
        previous: previous,
        currentSegment: 0,
        segmentStartPending: false
      )
    else {
      return XCTFail("Monotonic time should supersede the matching wall timestamp")
    }

    XCTAssertEqual(
      filter.evaluate(
        sample(
          latitude: 40.0002,
          epochMilliseconds: 7_000,
          monotonicNanoseconds: 999_999_999
        ),
        receivedAt: date(milliseconds: 7_000),
        previous: previous,
        currentSegment: 0,
        segmentStartPending: false
      ),
      .rejected(.outOfOrder)
    )
  }

  func testWallClockFallbackRejectsOutOfOrderAndImplausiblyFastFixes() {
    let previous = sample(latitude: 40, epochMilliseconds: 10_000, monotonicNanoseconds: nil)
    XCTAssertEqual(
      filter.evaluate(
        sample(latitude: 40.0001, epochMilliseconds: 10_000, monotonicNanoseconds: nil),
        receivedAt: date(milliseconds: 10_000),
        previous: previous,
        currentSegment: 0,
        segmentStartPending: false
      ),
      .rejected(.outOfOrder)
    )
    XCTAssertEqual(
      filter.evaluate(
        sample(latitude: 40.001, epochMilliseconds: 11_000, monotonicNanoseconds: nil),
        receivedAt: date(milliseconds: 11_000),
        previous: previous,
        currentSegment: 0,
        segmentStartPending: false
      ),
      .rejected(.implausibleSpeed)
    )
  }

  func testTwelveMetersPerSecondIsTheInclusiveSpeedCeiling() {
    let previous = sample(
      latitude: 0,
      longitude: 0,
      epochMilliseconds: 1_000,
      monotonicNanoseconds: 1_000_000_000
    )
    func longitude(for meters: Double) -> Double {
      meters / TrackingLocationFilter.earthRadiusMeters * 180 / .pi
    }

    guard
      case .accepted = filter.evaluate(
        sample(
          latitude: 0,
          longitude: longitude(for: 11.999),
          epochMilliseconds: 2_000,
          monotonicNanoseconds: 2_000_000_000
        ),
        receivedAt: date(milliseconds: 2_000),
        previous: previous,
        currentSegment: 0,
        segmentStartPending: false
      )
    else {
      return XCTFail("Movement below 12 m/s should be accepted")
    }
    XCTAssertEqual(
      filter.evaluate(
        sample(
          latitude: 0,
          longitude: longitude(for: 12.001),
          epochMilliseconds: 2_000,
          monotonicNanoseconds: 2_000_000_000
        ),
        receivedAt: date(milliseconds: 2_000),
        previous: previous,
        currentSegment: 0,
        segmentStartPending: false
      ),
      .rejected(.implausibleSpeed)
    )
  }

  func testExactSixtySecondGapAndResumeStartSegmentsWithoutBridgeDistance() {
    let previous = sample(
      latitude: 40, epochMilliseconds: 1_000, monotonicNanoseconds: 1_000_000_000)
    let gap = sample(
      latitude: 40.001, epochMilliseconds: 6_000, monotonicNanoseconds: 61_000_000_000)
    XCTAssertEqual(
      filter.evaluate(
        gap,
        receivedAt: date(milliseconds: 6_000),
        previous: previous,
        currentSegment: 2,
        segmentStartPending: false
      ),
      .accepted(AcceptedLocation(segment: 3, distanceFromPreviousMeters: 0, startsSegment: true))
    )

    let resumed = sample(
      latitude: 40.001, epochMilliseconds: 6_000, monotonicNanoseconds: 6_000_000_000)
    XCTAssertEqual(
      filter.evaluate(
        resumed,
        receivedAt: date(milliseconds: 6_000),
        previous: previous,
        currentSegment: 4,
        segmentStartPending: true
      ),
      .accepted(AcceptedLocation(segment: 4, distanceFromPreviousMeters: 0, startsSegment: true))
    )
  }

  func testHaversineIsStableAtAntipodesAndCoincidentPoints() {
    XCTAssertEqual(
      TrackingLocationFilter.haversineMeters(
        latitudeA: 28,
        longitudeA: -82,
        latitudeB: 28,
        longitudeB: -82
      ),
      0
    )
    XCTAssertEqual(
      TrackingLocationFilter.haversineMeters(
        latitudeA: 0,
        longitudeA: 0,
        latitudeB: 0,
        longitudeB: 180
      ),
      .pi * TrackingLocationFilter.earthRadiusMeters,
      accuracy: 0.001
    )
  }

  private func sample(
    latitude: Double = 40,
    longitude: Double = -74,
    altitude: Double? = 100,
    accuracy: Double = 3,
    epochMilliseconds: Int64,
    monotonicNanoseconds: Int64? = nil
  ) -> LocationSample {
    LocationSample(
      latitude: latitude,
      longitude: longitude,
      altitudeMeters: altitude,
      horizontalAccuracyMeters: accuracy,
      timestamp: date(milliseconds: epochMilliseconds),
      monotonicTimestampNanoseconds: monotonicNanoseconds
    )
  }

  private func date(milliseconds: Int64) -> Date {
    Date(timeIntervalSince1970: Double(milliseconds) / 1_000)
  }
}
