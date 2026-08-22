import XCTest
@testable import HikeJournal

final class DeepLinkRouterTests: XCTestCase {
    private let router = DeepLinkRouter(callbackScheme: "hikejournal")
    private let hikeID = UUID(uuidString: "00000000-0000-0000-0000-000000000123")!

    func testRoutesHikeHostLink() throws {
        let destination = router.destination(
            for: try XCTUnwrap(URL(string: "hikejournal://hike/\(hikeID.uuidString)"))
        )

        XCTAssertEqual(destination, .hike(id: hikeID))
    }

    func testRoutesPathStyleHikeLink() throws {
        let destination = router.destination(
            for: try XCTUnwrap(URL(string: "hikejournal:///hikes/\(hikeID.uuidString.lowercased())"))
        )

        XCTAssertEqual(destination, .hike(id: hikeID))
    }

    func testRoutesConnectedINaturalistCallback() throws {
        let destination = router.destination(
            for: try XCTUnwrap(URL(string: "hikejournal://inat?status=connected"))
        )

        XCTAssertEqual(destination, .inaturalist(status: .connected, message: nil))
    }

    func testRoutesINaturalistErrorWithDecodedMessage() throws {
        let destination = router.destination(
            for: try XCTUnwrap(
                URL(string: "hikejournal://inat?status=error&message=expired%20request")
            )
        )

        XCTAssertEqual(
            destination,
            .inaturalist(status: .error, message: "expired request")
        )
    }

    func testRoutesTrackingActionsWithoutStartingAnythingImplicitly() throws {
        XCTAssertEqual(
            router.destination(for: try XCTUnwrap(URL(string: "hikejournal://tracking"))),
            .tracking(action: .open)
        )
        XCTAssertEqual(
            router.destination(for: try XCTUnwrap(URL(string: "hikejournal://tracking/resume"))),
            .tracking(action: .resume)
        )
        XCTAssertEqual(
            router.destination(for: try XCTUnwrap(URL(string: "hikejournal://tracking?action=pause"))),
            .tracking(action: .pause)
        )
    }

    func testRejectsUnknownTrackingAction() throws {
        XCTAssertNil(
            router.destination(
                for: try XCTUnwrap(URL(string: "hikejournal://tracking?action=erase-everything"))
            )
        )
    }

    func testRejectsWrongSchemeMalformedHikeAndCredentials() throws {
        let urls = [
            "https://hike/\(hikeID.uuidString)",
            "hikejournal://hike/not-a-uuid",
            "hikejournal://user:password@hike/\(hikeID.uuidString)",
            "hikejournal://inat?status=unknown"
        ]

        for value in urls {
            XCTAssertNil(router.destination(for: try XCTUnwrap(URL(string: value))), value)
        }
    }
}
