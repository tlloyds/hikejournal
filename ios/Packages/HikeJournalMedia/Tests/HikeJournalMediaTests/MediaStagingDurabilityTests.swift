import Foundation
import XCTest
@testable import HikeJournalMedia

final class MediaStagingDurabilityTests: XCTestCase {
    private var baseDirectory: URL!

    override func setUpWithError() throws {
        baseDirectory = FileManager.default.temporaryDirectory.appendingPathComponent(
            "HikeJournalMediaDurabilityTests-\(UUID().uuidString)",
            isDirectory: true
        )
        try FileManager.default.createDirectory(
            at: baseDirectory,
            withIntermediateDirectories: true
        )
    }

    override func tearDownWithError() throws {
        if let baseDirectory {
            try? FileManager.default.removeItem(at: baseDirectory)
        }
        baseDirectory = nil
    }

    func testDurableReopenDoesNotCleanFilesUntilExplicitAcknowledgement() async throws {
        let expectedID = UUID(uuidString: "00000000-0000-0000-0000-000000000201")!
        let firstStore = makeStore(generator: LockedUUIDGenerator([expectedID]))
        let staged = try await ingestOne(accountID: "durable-account", store: firstStore)
        let stagedFile = try XCTUnwrap(staged.files.first?.fileURL)

        let reopenedStore = makeStore()
        let reopened = try await reopenedStore.queuedItems(accountID: "durable-account")

        XCTAssertEqual(reopened.count, 1)
        XCTAssertEqual(reopened[0].manifest, staged.manifest)
        XCTAssertEqual(reopened[0].manifest.id, expectedID.uuidString.lowercased())
        XCTAssertTrue(FileManager.default.fileExists(atPath: stagedFile.path))

        let acknowledged = try await reopenedStore.acknowledge(
            manifestID: staged.manifest.id,
            accountID: "durable-account"
        )
        let acknowledgedAgain = try await reopenedStore.acknowledge(
            manifestID: staged.manifest.id,
            accountID: "durable-account"
        )
        XCTAssertTrue(acknowledged)
        XCTAssertFalse(acknowledgedAgain)
        XCTAssertFalse(FileManager.default.fileExists(atPath: stagedFile.path))
    }

    func testWrongAccountAndMalformedIDCannotDeleteQueuedMedia() async throws {
        let store = makeStore()
        let staged = try await ingestOne(accountID: "owner-account", store: store)

        let wrongAccountResult = try await store.acknowledge(
            manifestID: staged.manifest.id,
            accountID: "different-account"
        )
        XCTAssertFalse(wrongAccountResult)
        XCTAssertTrue(FileManager.default.fileExists(atPath: staged.directoryURL.path))

        do {
            _ = try await store.acknowledge(
                manifestID: "../../owner-account",
                accountID: "owner-account"
            )
            XCTFail("Expected the unsafe identifier to be rejected")
        } catch let error as MediaIngestionError {
            XCTAssertEqual(
                error,
                .invalidManifest("The staged media identifier is invalid.")
            )
        }
        XCTAssertTrue(FileManager.default.fileExists(atPath: staged.directoryURL.path))
    }

    func testCorruptManifestBlocksAcknowledgementInsteadOfDeletingDirectory() async throws {
        let store = makeStore()
        let staged = try await ingestOne(accountID: "corrupt-account", store: store)
        let manifestURL = staged.directoryURL.appendingPathComponent("manifest.json")
        try Data("not-json".utf8).write(to: manifestURL)

        do {
            _ = try await store.acknowledge(
                manifestID: staged.manifest.id,
                accountID: "corrupt-account"
            )
            XCTFail("Expected corrupt manifest validation")
        } catch let error as MediaIngestionError {
            XCTAssertEqual(
                error,
                .invalidManifest("HikeJournal could not reopen a staged media manifest.")
            )
        }
        XCTAssertTrue(FileManager.default.fileExists(atPath: staged.directoryURL.path))
    }

    func testTamperedFileFailsReopenWithoutAutomaticDeletion() async throws {
        let store = makeStore()
        let staged = try await ingestOne(accountID: "tamper-account", store: store)
        let fileURL = try XCTUnwrap(staged.files.first?.fileURL)
        try Data("changed-after-queue".utf8).write(to: fileURL)

        do {
            _ = try await store.queuedItems(accountID: "tamper-account")
            XCTFail("Expected durable byte-count validation")
        } catch let error as MediaIngestionError {
            XCTAssertEqual(
                error,
                .invalidManifest("A staged media file no longer matches its durable manifest.")
            )
        }
        XCTAssertTrue(FileManager.default.fileExists(atPath: staged.directoryURL.path))
    }

    func testManifestIDCollisionAllocatesANewStableDirectory() async throws {
        let firstID = UUID(uuidString: "00000000-0000-0000-0000-000000000301")!
        let secondID = UUID(uuidString: "00000000-0000-0000-0000-000000000302")!
        let generator = LockedUUIDGenerator([firstID, firstID, secondID])
        let store = makeStore(generator: generator)

        let first = try await ingestOne(
            asset: makeImageAsset(id: "collision-first"),
            accountID: "collision-account",
            store: store
        )
        let second = try await ingestOne(
            asset: makeImageAsset(id: "collision-second"),
            accountID: "collision-account",
            store: store
        )

        XCTAssertEqual(first.manifest.id, firstID.uuidString.lowercased())
        XCTAssertEqual(second.manifest.id, secondID.uuidString.lowercased())
        XCTAssertNotEqual(first.directoryURL, second.directoryURL)
        let reopened = try await store.queuedItems(accountID: "collision-account")
        XCTAssertEqual(Set(reopened.map(\.manifest.id)), Set([first.manifest.id, second.manifest.id]))
    }

    func testAccountScopesAreOpaqueAndCannotCollideAcrossAccounts() async throws {
        let store = makeStore()
        let first = try await ingestOne(accountID: "user@example.com", store: store)
        let second = try await ingestOne(accountID: "another@example.com", store: store)

        XCTAssertNotEqual(first.manifest.accountScopeID, second.manifest.accountScopeID)
        XCTAssertFalse(first.directoryURL.path.contains("user@example.com"))
        XCTAssertFalse(second.directoryURL.path.contains("another@example.com"))
        XCTAssertTrue(FileManager.default.fileExists(atPath: first.directoryURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: second.directoryURL.path))
    }

    private func ingestOne(
        asset: MediaAssetSnapshot = makeImageAsset(),
        accountID: String,
        store: MediaStagingStore
    ) async throws -> StagedMediaItem {
        let library = MockMediaLibrary(
            assets: [asset],
            behaviors: [
                asset.resources[0].libraryResourceID: .data(Data("durable-media".utf8))
            ]
        )
        let service = MediaIngestionService(library: library, stagingStore: store)
        let batch = try await service.ingest(
            assetIdentifiers: [asset.localIdentifier],
            accountID: accountID,
            representation: .originalsOnly
        )
        return try XCTUnwrap(batch.items.first)
    }

    private func makeStore(generator: LockedUUIDGenerator? = nil) -> MediaStagingStore {
        let root = baseDirectory!
        let fixedDate = Date(timeIntervalSince1970: 1_850_000_000)
        return MediaStagingStore(
            baseDirectory: root,
            idGenerator: { generator?.next() ?? UUID() },
            now: { fixedDate }
        )
    }
}
