import HikeJournalDomain
import XCTest
@testable import HikeJournal

@MainActor
final class RiverGaugePreferencesStoreTests: XCTestCase {
    private var suiteName: String!
    private var defaults: UserDefaults!

    override func setUp() {
        super.setUp()
        suiteName = "HikeJournalRiverGaugeTests.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)
        defaults.removePersistentDomain(forName: suiteName)
    }

    override func tearDown() {
        defaults.removePersistentDomain(forName: suiteName)
        defaults = nil
        suiteName = nil
        super.tearDown()
    }

    func testNormalizesStationNumbersAndUSGSURLs() {
        XCTAssertEqual(
            RiverGaugePreferencesStore.normalizedSiteID("02233484"),
            "USGS-02233484"
        )
        XCTAssertEqual(
            RiverGaugePreferencesStore.normalizedSiteID(
                "https://waterdata.usgs.gov/monitoring-location/usgs-02233500/#data"
            ),
            "USGS-02233500"
        )
        XCTAssertNil(RiverGaugePreferencesStore.normalizedSiteID("bad"))
    }

    func testFollowingPersistsMetadataAndUnfollowingRemovesIt() throws {
        let gauge = RiverGauge(
            siteId: "usgs-02233484",
            name: "Econlockhatchee River",
            latitude: 28.6555,
            longitude: -81.1698
        )
        let store = RiverGaugePreferencesStore(defaults: defaults)

        store.setFollowed(gauge, isFollowed: true)

        XCTAssertEqual(store.followedIDs, ["USGS-02233484"])
        XCTAssertTrue(store.isFollowed(gauge))
        let restored = RiverGaugePreferencesStore(defaults: defaults)
        let persisted = try XCTUnwrap(restored.followedGauges.first)
        XCTAssertEqual(persisted.name, "Econlockhatchee River")
        XCTAssertEqual(persisted.latitude, 28.6555, accuracy: 0.000_001)
        XCTAssertEqual(persisted.longitude, -81.1698, accuracy: 0.000_001)

        restored.remove(siteID: "02233484")

        XCTAssertTrue(restored.followedGauges.isEmpty)
        XCTAssertTrue(RiverGaugePreferencesStore(defaults: defaults).followedGauges.isEmpty)
    }

    func testFollowingSameStationUpdatesInsteadOfDuplicating() {
        let store = RiverGaugePreferencesStore(defaults: defaults)
        store.setFollowed(
            RiverGauge(siteId: "USGS-01234567", name: "Old name", latitude: 1, longitude: 2),
            isFollowed: true
        )
        store.setFollowed(
            RiverGauge(siteId: "01234567", name: "Current name", latitude: 3, longitude: 4),
            isFollowed: true
        )

        XCTAssertEqual(store.followedGauges.count, 1)
        XCTAssertEqual(store.followedGauges.first?.name, "Current name")
        XCTAssertEqual(store.followedGauges.first?.latitude, 3)
    }
}
