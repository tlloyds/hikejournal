import CoreLocation
import XCTest
@testable import HikeJournal

final class OnboardingStoreTests: XCTestCase {
    private var suiteName: String!
    private var defaults: UserDefaults!

    override func setUp() {
        super.setUp()
        suiteName = "HikeJournalTests.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)
        defaults.removePersistentDomain(forName: suiteName)
    }

    override func tearDown() {
        defaults.removePersistentDomain(forName: suiteName)
        defaults = nil
        suiteName = nil
        super.tearDown()
    }

    func testCompletionRoundTripAndReset() {
        let store = DefaultsOnboardingStore(defaults: defaults)
        XCTAssertFalse(store.hasCompleted)

        store.markCompleted()
        XCTAssertTrue(store.hasCompleted)

        store.reset()
        XCTAssertFalse(store.hasCompleted)
    }
}

@MainActor
final class AppModelTests: XCTestCase {
    func testFreshInstallStartsInOnboardingThenOpensRecording() {
        let store = MemoryOnboardingStore(hasCompleted: false)
        let location = FakeLocationPermissionClient(status: .notDetermined)
        let model = AppModel(environment: makeEnvironment(store: store, location: location))

        XCTAssertEqual(model.phase, .onboarding)

        model.completeOnboarding(openRecording: true)

        XCTAssertTrue(store.hasCompleted)
        XCTAssertEqual(model.phase, .journal)
        XCTAssertEqual(model.selectedTab, .record)
    }

    func testReturningInstallStartsAtJournal() {
        let store = MemoryOnboardingStore(hasCompleted: true)
        let model = AppModel(
            environment: makeEnvironment(
                store: store,
                location: FakeLocationPermissionClient(status: .authorizedWhenInUse)
            )
        )

        XCTAssertEqual(model.phase, .journal)
        XCTAssertEqual(model.locationAuthorization, .authorizedWhenInUse)
    }

    func testLocationChangesFlowThroughInjectedClient() {
        let location = FakeLocationPermissionClient(status: .notDetermined)
        let model = AppModel(
            environment: makeEnvironment(
                store: MemoryOnboardingStore(hasCompleted: true),
                location: location
            )
        )

        model.requestWhenInUseLocation()
        XCTAssertEqual(location.requestCount, 1)

        location.send(.denied)
        XCTAssertEqual(model.locationAuthorization, .denied)
    }

    private func makeEnvironment(
        store: OnboardingStoring,
        location: LocationPermissionClient
    ) -> AppEnvironment {
        AppEnvironment(
            configuration: AppConfiguration(infoDictionary: [:]),
            version: AppVersion(marketingVersion: "0.8.6", buildNumber: "1"),
            onboardingStore: store,
            locationPermission: location,
            now: { Date(timeIntervalSince1970: 0) }
        )
    }
}

private final class MemoryOnboardingStore: OnboardingStoring {
    var hasCompleted: Bool

    init(hasCompleted: Bool) {
        self.hasCompleted = hasCompleted
    }

    func markCompleted() {
        hasCompleted = true
    }

    func reset() {
        hasCompleted = false
    }
}

@MainActor
private final class FakeLocationPermissionClient: LocationPermissionClient {
    private(set) var authorizationStatus: CLAuthorizationStatus
    var authorizationDidChange: ((CLAuthorizationStatus) -> Void)?
    private(set) var requestCount = 0

    init(status: CLAuthorizationStatus) {
        authorizationStatus = status
    }

    func requestWhenInUse() {
        requestCount += 1
    }

    func send(_ status: CLAuthorizationStatus) {
        authorizationStatus = status
        authorizationDidChange?(status)
    }
}
