import Foundation
import XCTest
@testable import HikeJournalMedia

final class MediaIngestionTests: XCTestCase {
    private var baseDirectory: URL!

    override func setUpWithError() throws {
        baseDirectory = FileManager.default.temporaryDirectory.appendingPathComponent(
            "HikeJournalMediaTests-\(UUID().uuidString)",
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

    func testMultipleSelectionPreservesRequestOrderAndReportsLimitedLibraryOmissions() async throws {
        let imageID = "image-requested-first"
        let imageResource = makeResource(
            assetID: imageID,
            index: 0,
            kind: .photo,
            filename: #"folder\trip\IMG_4321.HEIC"#,
            uniformTypeIdentifier: "public.heic"
        )
        let image = makeImageAsset(id: imageID, resources: [imageResource])
        let video = makeVideoAsset(id: "video-requested-second")
        let imageBytes = Data("full-resolution-image".utf8)
        let videoBytes = Data("original-video".utf8)
        let library = MockMediaLibrary(
            status: .limited,
            // PhotoKit fetch ordering is not contractual; deliberately reverse it.
            assets: [video, image],
            behaviors: [
                imageResource.libraryResourceID: .data(imageBytes),
                video.resources[0].libraryResourceID: .data(videoBytes),
            ]
        )
        let firstID = UUID(uuidString: "00000000-0000-0000-0000-000000000101")!
        let secondID = UUID(uuidString: "00000000-0000-0000-0000-000000000102")!
        let generator = LockedUUIDGenerator([firstID, secondID])
        let store = makeStore(generator: generator)
        let progress = ProgressRecorder()
        let service = MediaIngestionService(library: library, stagingStore: store)

        let batch = try await service.ingest(
            assetIdentifiers: [imageID, "not-visible-in-limited-library", video.localIdentifier, imageID],
            accountID: "account-1",
            representation: .originalsOnly,
            progress: { value in progress.record(value) }
        )

        XCTAssertEqual(batch.authorization, .limited)
        XCTAssertEqual(
            batch.items.map(\.manifest.sourceAssetIdentifier),
            [imageID, video.localIdentifier]
        )
        XCTAssertEqual(batch.unavailableAssetIdentifiers, ["not-visible-in-limited-library"])
        XCTAssertEqual(batch.items.map(\.manifest.id), [
            firstID.uuidString.lowercased(),
            secondID.uuidString.lowercased(),
        ])
        let imageItem = batch.items[0]
        XCTAssertEqual(imageItem.manifest.coordinate?.latitude, 44.31)
        XCTAssertEqual(imageItem.manifest.coordinate?.longitude, -68.21)
        XCTAssertEqual(imageItem.manifest.pixelWidth, 4_032)
        XCTAssertEqual(imageItem.files[0].component.originalFilename, "IMG_4321.HEIC")
        XCTAssertEqual(imageItem.files[0].component.uniformTypeIdentifier, "public.heic")
        XCTAssertEqual(imageItem.files[0].component.contentType, "image/heic")
        XCTAssertEqual(try Data(contentsOf: imageItem.files[0].fileURL), imageBytes)
        XCTAssertNil(batch.items[1].manifest.coordinate)
        XCTAssertEqual(batch.items[1].files[0].component.contentType, "video/quicktime")
        XCTAssertEqual(try Data(contentsOf: batch.items[1].files[0].fileURL), videoBytes)
        let exportedIDs = await library.exportedIDs()
        XCTAssertEqual(
            exportedIDs,
            [imageResource.libraryResourceID, video.resources[0].libraryResourceID]
        )

        let progressValues = progress.values()
        XCTAssertFalse(progressValues.isEmpty)
        XCTAssertEqual(progressValues.last?.overallFraction, 1)
        XCTAssertTrue(progressValues.allSatisfy { (0...1).contains($0.overallFraction) })
        for item in batch.items {
            XCTAssertEqual(
                try item.directoryURL.resourceValues(forKeys: [.isExcludedFromBackupKey]).isExcludedFromBackup,
                true
            )
            for file in item.files {
                XCTAssertEqual(
                    try file.fileURL.resourceValues(forKeys: [.isExcludedFromBackupKey]).isExcludedFromBackup,
                    true
                )
            }
        }
    }

    func testInvalidPhotoKitCoordinatesBecomeNilEvenWhenFilePayloadContainsGPSLikeText() async throws {
        let resource = makeResource(
            assetID: "invalid-gps",
            index: 0,
            kind: .photo,
            filename: "IMG_9999.JPG",
            uniformTypeIdentifier: "public.jpeg"
        )
        let asset = makeImageAsset(
            id: "invalid-gps",
            location: MediaSourceLocation(latitude: .nan, longitude: 12),
            resources: [resource]
        )
        let library = MockMediaLibrary(
            assets: [asset],
            behaviors: [resource.libraryResourceID: .data(Data("GPS=1,2".utf8))]
        )
        let service = MediaIngestionService(
            library: library,
            stagingStore: makeStore()
        )

        let batch = try await service.ingest(
            assetIdentifiers: [asset.localIdentifier],
            accountID: "account-gps"
        )

        XCTAssertNil(batch.items[0].manifest.coordinate)
    }

    func testLimitedLibraryCanReturnOnlyUnavailableIdentifiersWithoutFailing() async throws {
        let service = MediaIngestionService(
            library: MockMediaLibrary(status: .limited, assets: []),
            stagingStore: makeStore()
        )

        let batch = try await service.ingest(
            assetIdentifiers: ["hidden-1", "hidden-2"],
            accountID: "limited-account"
        )

        XCTAssertEqual(batch.authorization, .limited)
        XCTAssertTrue(batch.items.isEmpty)
        XCTAssertEqual(batch.unavailableAssetIdentifiers, ["hidden-1", "hidden-2"])
    }

    func testDeniedLibraryAccessFailsBeforeReadingAssets() async throws {
        let service = MediaIngestionService(
            library: MockMediaLibrary(status: .denied, assets: [makeImageAsset()]),
            stagingStore: makeStore()
        )

        do {
            _ = try await service.ingest(
                assetIdentifiers: ["image-1"],
                accountID: "account"
            )
            XCTFail("Expected denied access")
        } catch let error as MediaIngestionError {
            XCTAssertEqual(error, .libraryAccessRequired(.denied))
        }
    }

    func testSelectionValidationIsDeterministic() async throws {
        let service = MediaIngestionService(
            library: MockMediaLibrary(assets: []),
            stagingStore: makeStore()
        )

        do {
            _ = try await service.ingest(
                assetIdentifiers: ["", "  "],
                accountID: "account"
            )
            XCTFail("Expected an empty selection error")
        } catch let error as MediaIngestionError {
            XCTAssertEqual(error, .emptySelection)
        }

        do {
            _ = try await service.ingest(
                assetIdentifiers: (0...hikeJournalMaximumMediaSelection).map { "asset-\($0)" },
                accountID: "account"
            )
            XCTFail("Expected a selection limit error")
        } catch let error as MediaIngestionError {
            XCTAssertEqual(
                error,
                .tooManyAssets(maximum: hikeJournalMaximumMediaSelection)
            )
        }
    }

    private func makeStore(generator: LockedUUIDGenerator? = nil) -> MediaStagingStore {
        let fixedDate = Date(timeIntervalSince1970: 1_800_000_000)
        let root = baseDirectory!
        return MediaStagingStore(
            baseDirectory: root,
            idGenerator: { generator?.next() ?? UUID() },
            now: { fixedDate }
        )
    }
}

private final class ProgressRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var recorded: [MediaIngestionProgress] = []

    func record(_ value: MediaIngestionProgress) {
        lock.lock()
        recorded.append(value)
        lock.unlock()
    }

    func values() -> [MediaIngestionProgress] {
        lock.lock()
        defer { lock.unlock() }
        return recorded
    }
}
