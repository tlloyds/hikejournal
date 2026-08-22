import Foundation
import HikeJournalPersistence
import XCTest
@testable import HikeJournal

final class OfflineStoreCoordinatorTests: XCTestCase {
    func testRejectsProviderSubjectInPlaceOfCanonicalUUID() async throws {
        let fixture = try TemporaryDirectory()
        let coordinator = try OfflineStoreCoordinator(
            applicationSupportDirectory: fixture.url
        )
        do {
            _ = try await coordinator.database(canonicalUserID: "apple:subject")
            XCTFail("Provider subjects must never identify local account stores")
        } catch {
            XCTAssertEqual(error as? OfflineStoreCoordinatorError, .canonicalUserIDRequired)
        }
    }

    func testSwitchingAccountsKeepsQueuesPhysicallySeparated() async throws {
        let fixture = try TemporaryDirectory()
        let coordinator = try OfflineStoreCoordinator(
            applicationSupportDirectory: fixture.url
        )
        let firstID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
        let secondID = "11111111-2222-3333-4444-555555555555"
        let timestamp = Date(timeIntervalSince1970: 100)

        let first = try await coordinator.database(canonicalUserID: firstID)
        try await first.upsertOperation(
            PendingOperation(
                id: "first-only",
                kind: .createHike,
                entityID: "hike",
                createdAt: timestamp,
                updatedAt: timestamp
            )
        )

        let second = try await coordinator.database(canonicalUserID: secondID)
        let secondOperations = try await second.operations()
        XCTAssertTrue(secondOperations.isEmpty)

        let reopenedFirst = try await coordinator.database(canonicalUserID: firstID)
        let firstOperations = try await reopenedFirst.operations()
        XCTAssertEqual(firstOperations.map(\.id), ["first-only"])
    }
}

private final class TemporaryDirectory {
    let url: URL

    init() throws {
        url = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(
            at: url,
            withIntermediateDirectories: true
        )
    }

    deinit {
        try? FileManager.default.removeItem(at: url)
    }
}
