import XCTest
@testable import HikeJournal

final class AppVersionTests: XCTestCase {
    func testCanonicalVersionShape() {
        XCTAssertTrue(AppVersion.isSemanticRelease("0.8.6"))
        XCTAssertTrue(AppVersion.isSemanticRelease("12.34.567"))
    }

    func testRejectsNonCanonicalVersions() {
        XCTAssertFalse(AppVersion.isSemanticRelease("v0.8.6"))
        XCTAssertFalse(AppVersion.isSemanticRelease("0.8"))
        XCTAssertFalse(AppVersion.isSemanticRelease("0.8.6-beta"))
    }

    func testDisplayIncludesIndependentBuildNumber() {
        let version = AppVersion(marketingVersion: "0.8.6", buildNumber: "1")
        XCTAssertEqual(version.displayName, "Version 0.8.6 (1)")
    }
}
