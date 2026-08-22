import Foundation
import XCTest

@testable import HikeJournalMaps

final class MapDomainTests: XCTestCase {
  func testCoordinateRejectsNonfiniteAndOutOfRangeValues() throws {
    XCTAssertThrowsError(try GeoCoordinate(latitude: .nan, longitude: 0))
    XCTAssertThrowsError(try GeoCoordinate(latitude: 91, longitude: 0))
    XCTAssertThrowsError(try GeoCoordinate(latitude: 0, longitude: -181))
    XCTAssertEqual(
      try GeoCoordinate(latitude: -90, longitude: 180),
      GeoCoordinate.unchecked(latitude: -90, longitude: 180)
    )
  }

  func testCoordinateDecodingCannotBypassValidation() throws {
    let data = Data(#"{"latitude":95,"longitude":0}"#.utf8)
    XCTAssertThrowsError(try JSONDecoder().decode(GeoCoordinate.self, from: data))
  }

  func testRouteSegmentsRequireTwoPointsIncludingWhenDecoded() throws {
    let point = try GeoCoordinate(latitude: 28, longitude: -81)
    XCTAssertThrowsError(try RecordedRouteSegment(id: "one", coordinates: [point]))
    let data = Data(
      #"{"id":"one","coordinates":[{"latitude":28,"longitude":-81}]}"#.utf8
    )
    XCTAssertThrowsError(try JSONDecoder().decode(RecordedRouteSegment.self, from: data))
  }

  func testSceneRepresentsEveryRequiredPointKind() throws {
    let coordinate = try GeoCoordinate(latitude: 28, longitude: -81)
    let points = try MapPointKind.allCases.enumerated().map { index, kind in
      try MapPoint(
        id: "point-\(index)",
        kind: kind,
        title: kind.rawValue,
        coordinate: coordinate
      )
    }
    let scene = MapScene(points: points)
    XCTAssertEqual(Set(scene.points.map(\.kind)), Set(MapPointKind.allCases))
    XCTAssertEqual(scene.points(of: .fieldMark).count, 1)
    XCTAssertEqual(scene.points(of: .sighting).count, 1)
    XCTAssertEqual(scene.points(of: .discovery).count, 1)
    XCTAssertEqual(scene.points(of: .place).count, 1)
  }

  func testStyleConfigurationResolvesCredentialWithoutPersistingIt() throws {
    let attribution = try fixtureAttribution()
    let style = try MapStyleConfiguration(
      id: "outdoors",
      styleURL: XCTUnwrap(URL(string: "https://maps.example.test/style.json?language=en")),
      attribution: attribution,
      tokenQueryItemName: "key"
    )
    XCTAssertThrowsError(try style.resolvedURL()) { error in
      XCTAssertEqual(error as? MapDomainError, .missingStyleCredential)
    }
    let credential = try MapStyleCredential("secret-value")
    let resolved = try style.resolvedURL(credential: credential)
    let items = try XCTUnwrap(
      URLComponents(url: resolved, resolvingAgainstBaseURL: false)?.queryItems)
    XCTAssertEqual(items.first { $0.name == "key" }?.value, "secret-value")
    XCTAssertFalse(try JSONEncoder().encode(style).contains(Data("secret-value".utf8)))
  }

  func testStyleValidationFailsClosed() throws {
    let attribution = try fixtureAttribution()
    XCTAssertThrowsError(
      try MapStyleConfiguration(
        id: "bad",
        styleURL: XCTUnwrap(URL(string: "http://maps.example.test/style.json")),
        attribution: attribution
      )
    )
    XCTAssertThrowsError(
      try MapStyleConfiguration(
        id: "bad",
        styleURL: XCTUnwrap(URL(string: "https://user:password@maps.example.test/style.json")),
        attribution: attribution
      )
    )
    XCTAssertThrowsError(
      try MapStyleConfiguration(
        id: "duplicate-token",
        styleURL: XCTUnwrap(URL(string: "https://maps.example.test/style.json?key=embedded")),
        attribution: attribution,
        tokenQueryItemName: "key"
      )
    )
    XCTAssertThrowsError(try MapStyleCredential("contains whitespace"))
  }

  func testCredentialIsRejectedWhenStyleDoesNotExpectOne() throws {
    let style = try fixtureStyle()
    XCTAssertThrowsError(try style.resolvedURL(credential: MapStyleCredential("token"))) { error in
      XCTAssertEqual(error as? MapDomainError, .unexpectedStyleCredential)
    }
  }

  func testAttributionRequiresSecureLinkAndNonemptyTitle() throws {
    XCTAssertThrowsError(
      try MapAttribution(
        id: "source",
        title: "",
        url: XCTUnwrap(URL(string: "https://example.test"))
      )
    )
    XCTAssertThrowsError(
      try MapAttribution(
        id: "source",
        title: "Source",
        url: XCTUnwrap(URL(string: "http://example.test"))
      )
    )
  }

  func testAccessibilitySnapshotCoversRoutesLocationAndAnnotations() throws {
    let first = try GeoCoordinate(latitude: 28, longitude: -81)
    let second = try GeoCoordinate(latitude: 28.1, longitude: -81.1)
    let segment = try RecordedRouteSegment(id: "segment", coordinates: [first, second])
    let route = try RecordedRoute(id: "route", name: "Morning hike", segments: [segment])
    let kinds: [MapPointKind] = [
      .geotaggedPhoto, .geotaggedVideo, .fieldMark, .sighting, .discovery, .place,
    ]
    let points = try kinds.enumerated().map {
      try MapPoint(id: "p\($0.offset)", kind: $0.element, title: "Sample", coordinate: first)
    }
    let location = try MapCurrentLocation(
      coordinate: second,
      horizontalAccuracyMeters: 7.6,
      recordedAt: Date(timeIntervalSince1970: 1_000)
    )
    let snapshot = MapAccessibility.snapshot(
      for: MapScene(
        routes: [route],
        currentLocation: location,
        points: points,
        selectedTrailOverlayIDs: ["florida"]
      )
    )
    XCTAssertTrue(snapshot.summary.contains("1 recorded route segment"))
    XCTAssertTrue(snapshot.summary.contains("current location shown"))
    XCTAssertTrue(snapshot.summary.contains("1 geotagged photo"))
    XCTAssertTrue(snapshot.summary.contains("1 field mark"))
    XCTAssertTrue(snapshot.summary.contains("1 discovery"))
    XCTAssertTrue(snapshot.summary.contains("trail overlays: Florida Trail"))
    XCTAssertEqual(snapshot.items.count, 8)
    XCTAssertTrue(snapshot.items.contains { $0.label == "Current location, accurate to 8 meters" })
  }

  private func fixtureAttribution() throws -> MapAttribution {
    try MapAttribution(
      id: "open-map",
      title: "Open map contributors",
      url: XCTUnwrap(URL(string: "https://example.test/attribution"))
    )
  }

  private func fixtureStyle() throws -> MapStyleConfiguration {
    try MapStyleConfiguration(
      id: "outdoors",
      styleURL: XCTUnwrap(URL(string: "https://maps.example.test/style.json")),
      attribution: fixtureAttribution()
    )
  }
}

extension GeoCoordinate {
  fileprivate static func unchecked(latitude: Double, longitude: Double) -> GeoCoordinate {
    try! GeoCoordinate(latitude: latitude, longitude: longitude)
  }
}
