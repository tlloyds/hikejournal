import Foundation
import XCTest

@testable import HikeJournalMaps

final class OfflineMapDomainTests: XCTestCase {
  func testValidRequestProducesBoundedEstimate() throws {
    let request = try fixtureRequest()
    XCTAssertGreaterThan(request.estimate.tileCount, 0)
    XCTAssertLessThanOrEqual(request.estimate.tileCount, 50_000)
    XCTAssertGreaterThan(request.estimate.upperBoundBytes, request.estimate.lowerBoundBytes)
  }

  func testRequestRejectsZeroAreaAndOutOfMercatorBounds() throws {
    let style = try fixtureStyle()
    let zeroArea = try MapCoordinateBounds(south: 28, west: -81, north: 28, east: -81)
    XCTAssertThrowsError(
      try OfflinePackRequest(
        name: "Zero",
        style: style,
        bounds: zeroArea,
        minimumZoomLevel: 8,
        maximumZoomLevel: 10,
        networkPolicy: .wifiOnly
      )
    ) { error in
      XCTAssertEqual(error as? OfflineMapError, .invalidBounds)
    }

    let polar = try MapCoordinateBounds(south: 84, west: -81, north: 86, east: -80)
    XCTAssertThrowsError(
      try OfflinePackRequest(
        name: "Polar",
        style: style,
        bounds: polar,
        minimumZoomLevel: 8,
        maximumZoomLevel: 10,
        networkPolicy: .wifiOnly
      )
    ) { error in
      XCTAssertEqual(error as? OfflineMapError, .latitudeOutsideWebMercator)
    }
  }

  func testRequestRejectsLargeSpansAndZoomRanges() throws {
    let style = try fixtureStyle()
    let wide = try MapCoordinateBounds(south: 20, west: -100, north: 30, east: -70)
    XCTAssertThrowsError(
      try OfflinePackRequest(
        name: "Wide",
        style: style,
        bounds: wide,
        minimumZoomLevel: 1,
        maximumZoomLevel: 3,
        networkPolicy: .anyNetwork
      )
    ) { error in
      XCTAssertEqual(error as? OfflineMapError, .regionTooLarge)
    }
    let local = try MapCoordinateBounds(south: 28, west: -81, north: 28.1, east: -80.9)
    XCTAssertThrowsError(
      try OfflinePackRequest(
        name: "Too much zoom",
        style: style,
        bounds: local,
        minimumZoomLevel: 5,
        maximumZoomLevel: 19,
        networkPolicy: .anyNetwork
      )
    ) { error in
      XCTAssertEqual(error as? OfflineMapError, .invalidZoomRange)
    }
  }

  func testRequestRejectsEstimatedTileLimit() throws {
    let policy = OfflineRegionValidationPolicy(
      maximumLatitudeSpan: 20,
      maximumLongitudeSpan: 20,
      maximumZoomLevel: 18,
      maximumZoomLevels: 18,
      maximumEstimatedTiles: 10
    )
    XCTAssertThrowsError(
      try OfflinePackRequest(
        name: "Too many tiles",
        style: fixtureStyle(),
        bounds: MapCoordinateBounds(south: 28, west: -81, north: 28.1, east: -80.9),
        minimumZoomLevel: 8,
        maximumZoomLevel: 10,
        networkPolicy: .wifiOnly,
        validationPolicy: policy
      )
    ) { error in
      guard case .estimatedTileLimitExceeded(let estimated, let maximum) = error as? OfflineMapError
      else {
        return XCTFail("Unexpected error: \(error)")
      }
      XCTAssertGreaterThan(estimated, maximum)
      XCTAssertEqual(maximum, 10)
    }
  }

  func testSmallDatelineRegionIsSupported() throws {
    let request = try OfflinePackRequest(
      name: "Dateline",
      style: fixtureStyle(),
      bounds: MapCoordinateBounds(south: 10, west: 179.5, north: 10.1, east: -179.5),
      minimumZoomLevel: 5,
      maximumZoomLevel: 8,
      networkPolicy: .wifiOnly
    )
    XCTAssertTrue(request.bounds.crossesAntimeridian)
    XCTAssertEqual(request.bounds.longitudeSpan, 1, accuracy: 0.000_001)
  }

  func testContextRoundTripIsDeterministicAndCredentialFree() throws {
    let credential = try MapStyleCredential("super-secret")
    let style = try MapStyleConfiguration(
      id: "secure",
      styleURL: XCTUnwrap(URL(string: "https://maps.example.test/style.json")),
      attribution: fixtureAttribution(),
      tokenQueryItemName: "key"
    )
    let request = try fixtureRequest(style: style, credential: credential)
    let date = Date(timeIntervalSince1970: 1234)
    let context = OfflinePackContext(request: request, createdAt: date)
    let first = try OfflinePackContextCodec.encode(context)
    let second = try OfflinePackContextCodec.encode(context)
    XCTAssertEqual(first, second)
    XCTAssertFalse(String(decoding: first, as: UTF8.self).contains("super-secret"))
    XCTAssertEqual(try OfflinePackContextCodec.decode(first), context)
  }

  func testContextRejectsTamperedFingerprintAndOversizedData() throws {
    let context = OfflinePackContext(request: try fixtureRequest())
    let encoded = try OfflinePackContextCodec.encode(context)
    var object = try XCTUnwrap(
      JSONSerialization.jsonObject(with: encoded) as? [String: Any]
    )
    object["regionKey"] = "tampered"
    let tampered = try JSONSerialization.data(withJSONObject: object)
    XCTAssertThrowsError(try OfflinePackContextCodec.decode(tampered)) { error in
      XCTAssertEqual(error as? OfflineMapError, .corruptContext)
    }
    XCTAssertThrowsError(
      try OfflinePackContextCodec.decode(
        Data(repeating: 0, count: OfflinePackContextCodec.maximumBytes + 1))
    ) { error in
      XCTAssertEqual(error as? OfflineMapError, .contextTooLarge)
    }
  }

  func testRegionKeySeparatesDifferentStylesAndBounds() throws {
    let first = try fixtureRequest()
    let second = try fixtureRequest(
      bounds: MapCoordinateBounds(south: 28.1, west: -81, north: 28.2, east: -80.9)
    )
    XCTAssertNotEqual(first.regionKey, second.regionKey)
    XCTAssertEqual(first.regionKey, OfflinePackContext(request: first).regionKey)
  }

  func testProgressFractionAndSnapshotCompletion() throws {
    let progress = OfflinePackProgress(resourcesCompleted: 7, resourcesExpected: 10)
    XCTAssertEqual(try XCTUnwrap(progress.fractionCompleted), 0.7, accuracy: 0.000_001)
    XCTAssertNil(OfflinePackProgress().fractionCompleted)
    let snapshot = OfflinePackSnapshot(
      context: OfflinePackContext(request: try fixtureRequest()),
      state: .complete,
      progress: progress,
      totalMapStorageBytes: 123_456
    )
    XCTAssertTrue(snapshot.isComplete)
    XCTAssertEqual(snapshot.totalMapStorageBytes, 123_456)
    XCTAssertGreaterThan(snapshot.estimate.tileCount, 0)
  }

  private func fixtureRequest(
    style: MapStyleConfiguration? = nil,
    credential: MapStyleCredential? = nil,
    bounds: MapCoordinateBounds? = nil
  ) throws -> OfflinePackRequest {
    try OfflinePackRequest(
      id: UUID(uuidString: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")!,
      name: "Ocala hike",
      style: style ?? fixtureStyle(),
      styleCredential: credential,
      bounds: bounds ?? MapCoordinateBounds(south: 28, west: -81, north: 28.1, east: -80.9),
      minimumZoomLevel: 8,
      maximumZoomLevel: 12,
      networkPolicy: .wifiOnly
    )
  }

  private func fixtureStyle() throws -> MapStyleConfiguration {
    try MapStyleConfiguration(
      id: "outdoors",
      styleURL: XCTUnwrap(URL(string: "https://maps.example.test/style.json")),
      attribution: fixtureAttribution()
    )
  }

  private func fixtureAttribution() throws -> MapAttribution {
    try MapAttribution(
      id: "open-map",
      title: "Open map contributors",
      url: XCTUnwrap(URL(string: "https://example.test/attribution"))
    )
  }
}
