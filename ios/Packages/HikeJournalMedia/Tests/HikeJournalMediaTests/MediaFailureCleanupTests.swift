import Foundation
import XCTest
@testable import HikeJournalMedia

final class MediaFailureCleanupTests: XCTestCase {
    private var baseDirectory: URL!

    override func setUpWithError() throws {
        baseDirectory = FileManager.default.temporaryDirectory.appendingPathComponent(
            "HikeJournalMediaFailureTests-\(UUID().uuidString)",
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

    func testOverLimitResourceHasTypedErrorAndLeavesNoQueuedOrPartialFile() async throws {
        let asset = makeImageAsset(id: "oversized")
        let oversized = Data(
            repeating: 0x7f,
            count: Int(hikeJournalMaximumQueuedMediaBytes + 1)
        )
        let library = MockMediaLibrary(
            assets: [asset],
            behaviors: [asset.resources[0].libraryResourceID: .data(oversized)]
        )
        let store = makeStore()
        let service = MediaIngestionService(library: library, stagingStore: store)

        do {
            _ = try await service.ingest(
                assetIdentifiers: [asset.localIdentifier],
                accountID: "account-limit"
            )
            XCTFail("Expected the 30 MiB ceiling")
        } catch let error as MediaIngestionError {
            XCTAssertEqual(
                error,
                .fileTooLarge(
                    assetIdentifier: asset.localIdentifier,
                    originalFilename: "IMG_0001.HEIC",
                    actualBytes: hikeJournalMaximumQueuedMediaBytes + 1,
                    maximumBytes: hikeJournalMaximumQueuedMediaBytes
                )
            )
        }

        let queued = try await store.queuedItems(accountID: "account-limit")
        XCTAssertTrue(queued.isEmpty)
        XCTAssertTrue(try regularFiles().isEmpty)
    }

    func testLivePhotoSecondResourceFailureCleansSuccessfulFirstResource() async throws {
        let asset = makeLivePhotoAsset(id: "live-failure")
        let still = asset.resources.first { $0.kind == .photo }!
        let motion = asset.resources.first { $0.kind == .pairedVideo }!
        let failure = MediaIngestionError.libraryFailure(
            assetIdentifier: asset.localIdentifier,
            message: "iCloud download failed."
        )
        let library = MockMediaLibrary(
            assets: [asset],
            behaviors: [
                still.libraryResourceID: .data(Data("still".utf8)),
                motion.libraryResourceID: .failure(failure),
            ]
        )
        let store = makeStore()
        let service = MediaIngestionService(library: library, stagingStore: store)

        do {
            _ = try await service.ingest(
                assetIdentifiers: [asset.localIdentifier],
                accountID: "account-live",
                representation: .originalsOnly
            )
            XCTFail("Expected the motion resource failure")
        } catch let error as MediaIngestionError {
            XCTAssertEqual(error, failure)
        }

        let queued = try await store.queuedItems(accountID: "account-live")
        XCTAssertTrue(queued.isEmpty)
        XCTAssertTrue(try regularFiles().isEmpty)
    }

    func testTaskCancellationReachesLibraryAndCleansPartialDownload() async throws {
        let asset = makeImageAsset(id: "cancelled")
        let library = MockMediaLibrary(
            assets: [asset],
            behaviors: [
                asset.resources[0].libraryResourceID: .waitForTaskCancellation(
                    Data("partial-download".utf8)
                )
            ]
        )
        let store = makeStore()
        let service = MediaIngestionService(library: library, stagingStore: store)
        let task = Task {
            try await service.ingest(
                assetIdentifiers: [asset.localIdentifier],
                accountID: "account-cancel"
            )
        }

        await library.waitUntilExportStarts()
        task.cancel()
        do {
            _ = try await task.value
            XCTFail("Expected cancellation")
        } catch is CancellationError {
            // Cancellation remains distinguishable from an import failure.
        }

        let queued = try await store.queuedItems(accountID: "account-cancel")
        XCTAssertTrue(queued.isEmpty)
        XCTAssertTrue(try regularFiles().isEmpty)
    }

    func testBatchFailureRollsBackEarlierAssetsThatWereNeverReturned() async throws {
        let first = makeImageAsset(id: "first-good")
        let second = makeImageAsset(id: "second-bad")
        let failure = MediaIngestionError.libraryFailure(
            assetIdentifier: second.localIdentifier,
            message: "Cloud provider unavailable."
        )
        let library = MockMediaLibrary(
            assets: [first, second],
            behaviors: [
                first.resources[0].libraryResourceID: .data(Data("first".utf8)),
                second.resources[0].libraryResourceID: .failure(failure),
            ]
        )
        let store = makeStore()
        let service = MediaIngestionService(library: library, stagingStore: store)

        do {
            _ = try await service.ingest(
                assetIdentifiers: [first.localIdentifier, second.localIdentifier],
                accountID: "account-batch"
            )
            XCTFail("Expected batch failure")
        } catch let error as MediaIngestionError {
            XCTAssertEqual(error, failure)
        }

        let queued = try await store.queuedItems(accountID: "account-batch")
        XCTAssertTrue(queued.isEmpty)
        XCTAssertTrue(try regularFiles().isEmpty)
    }

    func testImmediateCancellationAlsoCleansPartialOutput() async throws {
        let asset = makeImageAsset(id: "immediate-cancel")
        let library = MockMediaLibrary(
            assets: [asset],
            behaviors: [
                asset.resources[0].libraryResourceID: .immediateCancellation(
                    Data("partial".utf8)
                )
            ]
        )
        let store = makeStore()
        let service = MediaIngestionService(library: library, stagingStore: store)

        do {
            _ = try await service.ingest(
                assetIdentifiers: [asset.localIdentifier],
                accountID: "account-immediate"
            )
            XCTFail("Expected cancellation")
        } catch is CancellationError {
            // Expected.
        }

        let queued = try await store.queuedItems(accountID: "account-immediate")
        XCTAssertTrue(queued.isEmpty)
        XCTAssertTrue(try regularFiles().isEmpty)
    }

    private func makeStore() -> MediaStagingStore {
        let root = baseDirectory!
        return MediaStagingStore(baseDirectory: root)
    }

    private func regularFiles() throws -> [URL] {
        guard let enumerator = FileManager.default.enumerator(
            at: baseDirectory,
            includingPropertiesForKeys: [.isRegularFileKey]
        ) else { return [] }
        return try enumerator.compactMap { element in
            guard let url = element as? URL else { return nil }
            return try url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true
                ? url
                : nil
        }
    }
}
