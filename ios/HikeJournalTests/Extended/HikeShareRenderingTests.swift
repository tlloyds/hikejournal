import HikeJournalDomain
import SwiftUI
import XCTest
@testable import HikeJournal

@MainActor
final class HikeShareRenderingTests: XCTestCase {
    func testTrailKeepsakeRendersAtFourByFiveExportSizeWithoutNetworkMap() throws {
        let hike = Hike(
            id: "outing-1",
            title: "Morning among the scrub oaks",
            hikeDate: "2026-08-22",
            distanceMiles: 4.25,
            durationSeconds: 5_410,
            locationName: "Oak Flat Preserve",
            notes: "",
            isArchived: false,
            coverUrl: "",
            photoCount: 0,
            speciesCount: 0,
            routeSegments: [[
                RoutePoint(latitude: 28.60, longitude: -81.20),
                RoutePoint(latitude: 28.61, longitude: -81.19),
                RoutePoint(latitude: 28.605, longitude: -81.18),
            ]]
        )
        let renderer = ImageRenderer(
            content: HikeShareCard(hike: hike, satelliteMap: nil)
                .frame(width: 1_080, height: 1_350)
                .environment(\.colorScheme, .dark)
        )
        renderer.scale = 1

        let image = try XCTUnwrap(renderer.uiImage)

        XCTAssertEqual(image.size.width, 1_080)
        XCTAssertEqual(image.size.height, 1_350)
        XCTAssertNotNil(image.jpegData(compressionQuality: 0.94))
    }
}
