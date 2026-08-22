import XCTest

@testable import HikeJournalMaps

final class MapGeometryTests: XCTestCase {
  func testOrdinaryBoundsFitCoordinates() throws {
    let fit = try XCTUnwrap(
      MapCameraFitter.fit(coordinates: [
        GeoCoordinate(latitude: 28, longitude: -82),
        GeoCoordinate(latitude: 30, longitude: -80),
      ])
    )
    XCTAssertEqual(fit.bounds.south, 28)
    XCTAssertEqual(fit.bounds.north, 30)
    XCTAssertEqual(fit.bounds.west, -82)
    XCTAssertEqual(fit.bounds.east, -80)
    XCTAssertEqual(fit.center.latitude, 29)
    XCTAssertEqual(fit.center.longitude, -81)
  }

  func testDatelineFitUsesSmallestLongitudeArc() throws {
    let fit = try XCTUnwrap(
      MapCameraFitter.fit(coordinates: [
        GeoCoordinate(latitude: 10, longitude: 179),
        GeoCoordinate(latitude: 12, longitude: -179),
        GeoCoordinate(latitude: 11, longitude: 178),
      ])
    )
    XCTAssertTrue(fit.bounds.crossesAntimeridian)
    XCTAssertEqual(fit.bounds.west, 178, accuracy: 0.000_001)
    XCTAssertEqual(fit.bounds.east, -179, accuracy: 0.000_001)
    XCTAssertEqual(fit.longitudeSpan, 3, accuracy: 0.000_001)
    XCTAssertEqual(abs(fit.center.longitude), 179.5, accuracy: 0.000_001)
  }

  func testSingleCoordinateGetsSafeMinimumCameraSpan() throws {
    let fit = try XCTUnwrap(
      MapCameraFitter.fit(
        coordinates: [GeoCoordinate(latitude: 28, longitude: -81)],
        minimumSpanDegrees: 0.01
      )
    )
    XCTAssertEqual(fit.center.latitude, 28)
    XCTAssertEqual(fit.center.longitude, -81)
    XCTAssertEqual(fit.latitudeSpan, 0.01)
    XCTAssertEqual(fit.longitudeSpan, 0.01)
  }

  func testEmptyCoordinatesHaveNoCameraFit() {
    XCTAssertNil(MapCameraFitter.fit(coordinates: []))
  }
}
