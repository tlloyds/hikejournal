#if canImport(Photos)
import Foundation
import Photos

public final class PhotoKitMediaLibrary: MediaLibraryAccessing, @unchecked Sendable {
    private let resourceManager: PHAssetResourceManager

    public init(resourceManager: PHAssetResourceManager = .default()) {
        self.resourceManager = resourceManager
    }

    public func authorizationStatus() async -> MediaLibraryAuthorization {
        Self.authorization(PHPhotoLibrary.authorizationStatus(for: .readWrite))
    }

    /// Call this only after an in-context explanation in the app UI.
    public func requestAuthorization() async -> MediaLibraryAuthorization {
        await withCheckedContinuation { continuation in
            PHPhotoLibrary.requestAuthorization(for: .readWrite) { status in
                continuation.resume(returning: Self.authorization(status))
            }
        }
    }

    public func assets(forLocalIdentifiers identifiers: [String]) async throws -> [MediaAssetSnapshot] {
        try Task.checkCancellation()
        let result = PHAsset.fetchAssets(
            withLocalIdentifiers: identifiers,
            options: nil
        )
        var snapshots: [MediaAssetSnapshot] = []
        snapshots.reserveCapacity(result.count)
        result.enumerateObjects { asset, _, _ in
            let resources = PHAssetResource.assetResources(for: asset)
            let descriptors = resources.enumerated().map { index, resource in
                Self.descriptor(
                    assetIdentifier: asset.localIdentifier,
                    index: index,
                    resource: resource
                )
            }
            let kind: MediaAssetKind
            switch asset.mediaType {
            case .image where asset.mediaSubtypes.contains(.photoLive):
                kind = .livePhoto
            case .image:
                kind = .image
            case .video:
                kind = .video
            default:
                kind = .unsupported
            }
            let coordinate = asset.location?.coordinate
            snapshots.append(
                MediaAssetSnapshot(
                    localIdentifier: asset.localIdentifier,
                    kind: kind,
                    creationDate: asset.creationDate,
                    sourceLocation: coordinate.map {
                        MediaSourceLocation(
                            latitude: $0.latitude,
                            longitude: $0.longitude
                        )
                    },
                    pixelWidth: asset.pixelWidth,
                    pixelHeight: asset.pixelHeight,
                    duration: asset.mediaType == .video ? asset.duration : nil,
                    resources: descriptors
                )
            )
        }
        try Task.checkCancellation()
        return snapshots
    }

    public func exportResource(
        _ descriptor: MediaResourceDescriptor,
        to destinationURL: URL,
        maximumBytes: Int64,
        progress: @escaping MediaResourceProgressHandler
    ) async throws {
        try Task.checkCancellation()
        let result = PHAsset.fetchAssets(
            withLocalIdentifiers: [descriptor.assetIdentifier],
            options: nil
        )
        guard let asset = result.firstObject else {
            throw MediaIngestionError.resourceChanged(
                assetIdentifier: descriptor.assetIdentifier
            )
        }
        let resources = PHAssetResource.assetResources(for: asset)
        let resource = Self.matchingResource(
            descriptor,
            assetIdentifier: asset.localIdentifier,
            resources: resources
        )
        guard let resource else {
            throw MediaIngestionError.resourceChanged(
                assetIdentifier: descriptor.assetIdentifier
            )
        }
        let operation = PhotoKitResourceExportOperation(
            manager: resourceManager,
            resource: resource,
            descriptor: descriptor,
            destinationURL: destinationURL,
            maximumBytes: maximumBytes,
            progress: progress
        )
        try await operation.run()
    }

    private static func authorization(_ status: PHAuthorizationStatus) -> MediaLibraryAuthorization {
        switch status {
        case .authorized: .authorized
        case .limited: .limited
        case .denied: .denied
        case .restricted: .restricted
        case .notDetermined: .notDetermined
        @unknown default: .restricted
        }
    }

    private static func descriptor(
        assetIdentifier: String,
        index: Int,
        resource: PHAssetResource
    ) -> MediaResourceDescriptor {
        MediaResourceDescriptor(
            libraryResourceID: "\(assetIdentifier)#\(index)",
            assetIdentifier: assetIdentifier,
            sourceIndex: index,
            kind: kind(resource.type),
            originalFilename: resource.originalFilename,
            uniformTypeIdentifier: resource.uniformTypeIdentifier
        )
    }

    private static func matchingResource(
        _ descriptor: MediaResourceDescriptor,
        assetIdentifier: String,
        resources: [PHAssetResource]
    ) -> PHAssetResource? {
        if resources.indices.contains(descriptor.sourceIndex) {
            let candidate = resources[descriptor.sourceIndex]
            if matches(candidate, descriptor: descriptor) {
                return candidate
            }
        }
        let candidates = resources.filter { Self.matches($0, descriptor: descriptor) }
        return candidates.count == 1 ? candidates[0] : nil
    }

    private static func matches(
        _ resource: PHAssetResource,
        descriptor: MediaResourceDescriptor
    ) -> Bool {
        kind(resource.type) == descriptor.kind
            && resource.originalFilename == descriptor.originalFilename
            && resource.uniformTypeIdentifier == descriptor.uniformTypeIdentifier
    }

    private static func kind(_ type: PHAssetResourceType) -> MediaResourceKind {
        switch type {
        case .photo: .photo
        case .fullSizePhoto: .fullSizePhoto
        case .video: .video
        case .fullSizeVideo: .fullSizeVideo
        case .pairedVideo: .pairedVideo
        case .fullSizePairedVideo: .fullSizePairedVideo
        case .alternatePhoto: .alternatePhoto
        case .adjustmentData: .adjustmentData
        case .adjustmentBasePhoto: .adjustmentBasePhoto
        case .adjustmentBasePairedVideo: .adjustmentBasePairedVideo
        case .adjustmentBaseVideo, .photoProxy: .unknown
        case .audio: .audio
        @unknown default: .unknown
        }
    }
}

private final class PhotoKitResourceExportOperation: @unchecked Sendable {
    private let manager: PHAssetResourceManager
    private let resource: PHAssetResource
    private let descriptor: MediaResourceDescriptor
    private let destinationURL: URL
    private let maximumBytes: Int64
    private let progress: MediaResourceProgressHandler
    private let lock = NSLock()

    private var requestID: PHAssetResourceDataRequestID?
    private var continuation: CheckedContinuation<Void, Error>?
    private var fileHandle: FileHandle?
    private var byteCount: Int64 = 0
    private var finished = false

    init(
        manager: PHAssetResourceManager,
        resource: PHAssetResource,
        descriptor: MediaResourceDescriptor,
        destinationURL: URL,
        maximumBytes: Int64,
        progress: @escaping MediaResourceProgressHandler
    ) {
        self.manager = manager
        self.resource = resource
        self.descriptor = descriptor
        self.destinationURL = destinationURL
        self.maximumBytes = maximumBytes
        self.progress = progress
    }

    func run() async throws {
        guard maximumBytes > 0 else {
            throw MediaIngestionError.fileTooLarge(
                assetIdentifier: descriptor.assetIdentifier,
                originalFilename: descriptor.originalFilename,
                actualBytes: 0,
                maximumBytes: maximumBytes
            )
        }
        guard FileManager.default.createFile(atPath: destinationURL.path, contents: nil) else {
            throw MediaIngestionError.storageFailure(
                "HikeJournal could not create secure temporary media storage."
            )
        }
        do {
            fileHandle = try FileHandle(forWritingTo: destinationURL)
        } catch {
            try? FileManager.default.removeItem(at: destinationURL)
            throw MediaIngestionError.storageFailure(
                "HikeJournal could not open secure temporary media storage."
            )
        }

        try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation {
                (continuation: CheckedContinuation<Void, Error>) in
                lock.lock()
                if finished {
                    lock.unlock()
                    continuation.resume(throwing: CancellationError())
                    return
                }
                self.continuation = continuation
                lock.unlock()

                let options = PHAssetResourceRequestOptions()
                options.isNetworkAccessAllowed = true
                options.progressHandler = { [weak self] fraction in
                    guard let self else { return }
                    self.progress(min(1, max(0, fraction.isFinite ? fraction : 0)))
                }
                let requestID = manager.requestData(
                    for: resource,
                    options: options,
                    dataReceivedHandler: { [weak self] data in
                        self?.receive(data)
                    },
                    completionHandler: { [weak self] error in
                        self?.complete(error)
                    }
                )
                lock.lock()
                self.requestID = requestID
                let alreadyFinished = finished
                lock.unlock()
                if alreadyFinished {
                    manager.cancelDataRequest(requestID)
                }
            }
        } onCancel: { [weak self] in
            self?.cancel()
        }
    }

    private func receive(_ data: Data) {
        var failure: Error?
        lock.lock()
        if !finished {
            let nextCount = byteCount + Int64(data.count)
            if nextCount > maximumBytes {
                failure = MediaIngestionError.fileTooLarge(
                    assetIdentifier: descriptor.assetIdentifier,
                    originalFilename: descriptor.originalFilename,
                    actualBytes: nextCount,
                    maximumBytes: maximumBytes
                )
            } else {
                do {
                    guard let fileHandle else {
                        throw CocoaError(.fileWriteUnknown)
                    }
                    try fileHandle.write(contentsOf: data)
                    byteCount = nextCount
                } catch {
                    failure = MediaIngestionError.storageFailure(
                        "HikeJournal could not write secure temporary media storage."
                    )
                }
            }
        }
        lock.unlock()
        if let failure {
            finish(.failure(failure), cancelRequest: true)
        }
    }

    private func complete(_ error: Error?) {
        if let error {
            finish(
                .failure(
                    MediaIngestionError.libraryFailure(
                        assetIdentifier: descriptor.assetIdentifier,
                        message: "Photos could not download \(descriptor.originalFilename): \(error.localizedDescription)"
                    )
                ),
                cancelRequest: false
            )
        } else {
            finish(.success(()), cancelRequest: false)
        }
    }

    private func cancel() {
        finish(.failure(CancellationError()), cancelRequest: true)
    }

    private func finish(_ result: Result<Void, Error>, cancelRequest: Bool) {
        lock.lock()
        guard !finished else {
            lock.unlock()
            return
        }
        finished = true
        let requestID = self.requestID
        let continuation = self.continuation
        let fileHandle = self.fileHandle
        self.continuation = nil
        self.fileHandle = nil
        lock.unlock()

        if cancelRequest, let requestID {
            manager.cancelDataRequest(requestID)
        }
        try? fileHandle?.synchronize()
        try? fileHandle?.close()
        if case .failure = result {
            try? FileManager.default.removeItem(at: destinationURL)
        }
        continuation?.resume(with: result)
    }
}
#endif
