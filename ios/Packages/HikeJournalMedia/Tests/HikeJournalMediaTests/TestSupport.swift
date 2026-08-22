import Foundation
@testable import HikeJournalMedia

enum MockExportBehavior: Sendable {
    case data(Data)
    case failure(MediaIngestionError)
    case immediateCancellation(Data)
    case waitForTaskCancellation(Data)
}

actor MockMediaLibrary: MediaLibraryAccessing {
    private let status: MediaLibraryAuthorization
    private let configuredAssets: [MediaAssetSnapshot]
    private var behaviors: [String: MockExportBehavior]
    private var exportedResourceIDs: [String] = []
    private var exportStartCount = 0
    private var startWaiters: [CheckedContinuation<Void, Never>] = []

    init(
        status: MediaLibraryAuthorization = .authorized,
        assets: [MediaAssetSnapshot],
        behaviors: [String: MockExportBehavior] = [:]
    ) {
        self.status = status
        configuredAssets = assets
        self.behaviors = behaviors
    }

    func authorizationStatus() -> MediaLibraryAuthorization {
        status
    }

    func assets(forLocalIdentifiers identifiers: [String]) -> [MediaAssetSnapshot] {
        let requested = Set(identifiers)
        return configuredAssets.filter { requested.contains($0.localIdentifier) }
    }

    func exportResource(
        _ resource: MediaResourceDescriptor,
        to destinationURL: URL,
        maximumBytes: Int64,
        progress: @escaping MediaResourceProgressHandler
    ) async throws {
        exportedResourceIDs.append(resource.libraryResourceID)
        exportStartCount += 1
        let waiters = startWaiters
        startWaiters.removeAll()
        waiters.forEach { $0.resume() }
        progress(0)
        let behavior = behaviors[resource.libraryResourceID] ?? .data(Data("media".utf8))
        switch behavior {
        case let .data(data):
            try data.write(to: destinationURL)
            progress(0.5)
            progress(1)
        case let .failure(error):
            throw error
        case let .immediateCancellation(partial):
            try partial.write(to: destinationURL)
            throw CancellationError()
        case let .waitForTaskCancellation(partial):
            try partial.write(to: destinationURL)
            try await Task.sleep(for: .seconds(30))
            throw MediaIngestionError.libraryFailure(
                assetIdentifier: resource.assetIdentifier,
                message: "Cancellation did not reach the mock library."
            )
        }
    }

    func exportedIDs() -> [String] {
        exportedResourceIDs
    }

    func waitUntilExportStarts() async {
        if exportStartCount > 0 { return }
        await withCheckedContinuation { continuation in
            startWaiters.append(continuation)
        }
    }
}

final class LockedUUIDGenerator: @unchecked Sendable {
    private let lock = NSLock()
    private var values: [UUID]

    init(_ values: [UUID]) {
        self.values = values
    }

    func next() -> UUID {
        lock.lock()
        defer { lock.unlock() }
        if values.count > 1 {
            return values.removeFirst()
        }
        return values.first ?? UUID()
    }
}

func makeResource(
    assetID: String,
    index: Int,
    kind: MediaResourceKind,
    filename: String,
    uniformTypeIdentifier: String
) -> MediaResourceDescriptor {
    MediaResourceDescriptor(
        libraryResourceID: "\(assetID)#\(index)",
        assetIdentifier: assetID,
        sourceIndex: index,
        kind: kind,
        originalFilename: filename,
        uniformTypeIdentifier: uniformTypeIdentifier
    )
}

func makeImageAsset(
    id: String = "image-1",
    location: MediaSourceLocation? = MediaSourceLocation(latitude: 44.31, longitude: -68.21),
    resources: [MediaResourceDescriptor]? = nil
) -> MediaAssetSnapshot {
    MediaAssetSnapshot(
        localIdentifier: id,
        kind: .image,
        creationDate: Date(timeIntervalSince1970: 1_700_000_000),
        sourceLocation: location,
        pixelWidth: 4_032,
        pixelHeight: 3_024,
        duration: nil,
        resources: resources ?? [
            makeResource(
                assetID: id,
                index: 0,
                kind: .photo,
                filename: "IMG_0001.HEIC",
                uniformTypeIdentifier: "public.heic"
            )
        ]
    )
}

func makeVideoAsset(id: String = "video-1") -> MediaAssetSnapshot {
    MediaAssetSnapshot(
        localIdentifier: id,
        kind: .video,
        creationDate: Date(timeIntervalSince1970: 1_700_000_100),
        sourceLocation: nil,
        pixelWidth: 1_920,
        pixelHeight: 1_080,
        duration: 12.5,
        resources: [
            makeResource(
                assetID: id,
                index: 0,
                kind: .video,
                filename: "IMG_0002.MOV",
                uniformTypeIdentifier: "com.apple.quicktime-movie"
            )
        ]
    )
}

func makeLivePhotoAsset(id: String = "live-1") -> MediaAssetSnapshot {
    MediaAssetSnapshot(
        localIdentifier: id,
        kind: .livePhoto,
        creationDate: Date(timeIntervalSince1970: 1_700_000_200),
        sourceLocation: MediaSourceLocation(latitude: 35.6, longitude: -83.5),
        pixelWidth: 4_032,
        pixelHeight: 3_024,
        duration: nil,
        resources: [
            makeResource(
                assetID: id,
                index: 0,
                kind: .photo,
                filename: "IMG_0003.HEIC",
                uniformTypeIdentifier: "public.heic"
            ),
            makeResource(
                assetID: id,
                index: 1,
                kind: .pairedVideo,
                filename: "IMG_0003.MOV",
                uniformTypeIdentifier: "com.apple.quicktime-movie"
            ),
            makeResource(
                assetID: id,
                index: 2,
                kind: .fullSizePhoto,
                filename: "IMG_E0003.JPG",
                uniformTypeIdentifier: "public.jpeg"
            ),
            makeResource(
                assetID: id,
                index: 3,
                kind: .fullSizePairedVideo,
                filename: "IMG_E0003.MOV",
                uniformTypeIdentifier: "com.apple.quicktime-movie"
            ),
        ]
    )
}
