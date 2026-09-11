import Foundation
import XCTest

@testable import HikeJournalMaps

final class MapRouteOverlapTests: XCTestCase {
  func testParallelNearbyRouteIsShared() throws {
    let trail = try lineFeature(
      [[-81.82, 29.0], [-81.80, 29.0]]
    )
    let route = try recordedRoute(
      [[-81.82, 29.00005], [-81.80, 29.00005]]
    )

    let classified = MapRouteOverlapClassifier.classify(
      routes: [route],
      trailGeoJSON: [trail]
    )

    XCTAssertFalse(classified.isEmpty)
    XCTAssertTrue(classified.allSatisfy { $0.overlapsTrail })
  }

  func testNearbyParallelPathOutsideCenterlineToleranceIsPersonal() throws {
    let trail = try lineFeature(
      [[-81.82, 29.0], [-81.80, 29.0]]
    )
    let route = try recordedRoute(
      [[-81.82, 29.0003], [-81.80, 29.0003]]
    )

    let classified = MapRouteOverlapClassifier.classify(
      routes: [route],
      trailGeoJSON: [trail]
    )

    XCTAssertFalse(classified.isEmpty)
    XCTAssertTrue(classified.allSatisfy { !$0.overlapsTrail })
  }

  func testPerpendicularCrossingIsPersonal() throws {
    let trail = try lineFeature(
      [[-81.82, 29.0], [-81.80, 29.0]]
    )
    let route = try recordedRoute(
      [[-81.81, 28.999], [-81.81, 29.001]]
    )

    let classified = MapRouteOverlapClassifier.classify(
      routes: [route],
      trailGeoJSON: [trail]
    )

    XCTAssertTrue(classified.allSatisfy { !$0.overlapsTrail })
  }

  private func lineFeature(_ coordinates: [[Double]]) throws -> Data {
    try JSONSerialization.data(withJSONObject: [
      "type": "FeatureCollection",
      "features": [[
        "type": "Feature",
        "geometry": ["type": "LineString", "coordinates": coordinates],
        "properties": [:],
      ]
    ])
  }

  private func recordedRoute(_ coordinates: [[Double]]) throws -> RecordedRoute {
    let values = try coordinates.map {
      try GeoCoordinate(latitude: $0[1], longitude: $0[0])
    }
    return try RecordedRoute(
      id: "route",
      name: "Route",
      segments: [try RecordedRouteSegment(id: "segment", coordinates: values)]
    )
  }
}
