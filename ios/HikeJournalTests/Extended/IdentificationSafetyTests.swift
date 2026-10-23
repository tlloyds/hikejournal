import XCTest
@testable import HikeJournal

@MainActor
final class IdentificationSafetyTests: XCTestCase {
    func testFreshAndPreviouslyOnboardedUsersMustAcknowledgeTheNotice() throws {
        try withDefaults { defaults in
            XCTAssertFalse(IdentificationSafetyStore(defaults: defaults).hasAcknowledged)
            DefaultsOnboardingStore(defaults: defaults).markCompleted()
            XCTAssertFalse(IdentificationSafetyStore(defaults: defaults).hasAcknowledged)
        }
    }

    func testAcknowledgmentSurvivesStoreRecreationAndOnboardingReplay() throws {
        try withDefaults { defaults in
            IdentificationSafetyStore(defaults: defaults).acknowledge()
            DefaultsOnboardingStore(defaults: defaults).reset()
            XCTAssertTrue(IdentificationSafetyStore(defaults: defaults).hasAcknowledged)
        }
    }

    func testMaterialNoticeUpdateRequiresAcknowledgmentAgain() throws {
        try withDefaults { defaults in
            IdentificationSafetyStore(defaults: defaults).acknowledge()
            let updated = IdentificationSafetyStore(defaults: defaults, requiredNoticeVersion: 2)
            XCTAssertFalse(updated.hasAcknowledged)
            updated.acknowledge()
            XCTAssertTrue(IdentificationSafetyStore(defaults: defaults, requiredNoticeVersion: 2).hasAcknowledged)
        }
    }

    func testAcknowledgmentIsLocalToItsPreferenceDomain() throws {
        try withDefaults { firstInstall in
            IdentificationSafetyStore(defaults: firstInstall).acknowledge()
            try withDefaults { otherInstall in
                XCTAssertFalse(IdentificationSafetyStore(defaults: otherInstall).hasAcknowledged)
            }
        }
    }

    private func withDefaults(_ action: (UserDefaults) throws -> Void) throws {
        let name = "IdentificationSafetyTests.\(UUID())"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: name))
        defer { defaults.removePersistentDomain(forName: name) }
        try action(defaults)
    }
}
