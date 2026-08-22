import Foundation

/// Android and iOS intentionally share this queued-file ceiling.
public let hikeJournalMaximumQueuedMediaBytes: Int64 = 30 * 1024 * 1024
public let hikeJournalMaximumMediaSelection = 500

public enum MediaLibraryAuthorization: String, Codable, Equatable, Sendable {
    case authorized
    case limited
    case denied
    case restricted
    case notDetermined

    public var permitsRead: Bool {
        self == .authorized || self == .limited
    }
}

public enum MediaAssetKind: String, Codable, Equatable, Sendable {
    case image
    case video
    case livePhoto
    case unsupported
}

public enum MediaResourceKind: String, Codable, Equatable, Sendable {
    case photo
    case fullSizePhoto
    case video
    case fullSizeVideo
    case pairedVideo
    case fullSizePairedVideo
    case alternatePhoto
    case adjustmentData
    case adjustmentBasePhoto
    case adjustmentBasePairedVideo
    case audio
    case unknown
}

public struct MediaSourceLocation: Equatable, Sendable {
    public let latitude: Double
    public let longitude: Double

    public init(latitude: Double, longitude: Double) {
        self.latitude = latitude
        self.longitude = longitude
    }
}

public struct MediaCoordinate: Codable, Equatable, Sendable {
    public let latitude: Double
    public let longitude: Double

    private enum CodingKeys: String, CodingKey {
        case latitude
        case longitude
    }

    /// Validation is deliberately strict: invalid, incomplete, or non-finite
    /// PhotoKit coordinates become `nil`; they are never clamped or guessed.
    public init?(validating source: MediaSourceLocation?) {
        guard let source,
              source.latitude.isFinite,
              source.longitude.isFinite,
              (-90.0...90.0).contains(source.latitude),
              (-180.0...180.0).contains(source.longitude) else {
            return nil
        }
        latitude = source.latitude
        longitude = source.longitude
    }

    public init(from decoder: any Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let source = MediaSourceLocation(
            latitude: try container.decode(Double.self, forKey: .latitude),
            longitude: try container.decode(Double.self, forKey: .longitude)
        )
        guard let validated = MediaCoordinate(validating: source) else {
            throw DecodingError.dataCorruptedError(
                forKey: .latitude,
                in: container,
                debugDescription: "Media coordinates must be finite and within latitude/longitude bounds."
            )
        }
        self = validated
    }

    public func encode(to encoder: any Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(latitude, forKey: .latitude)
        try container.encode(longitude, forKey: .longitude)
    }
}

public struct MediaResourceDescriptor: Codable, Equatable, Sendable {
    public let libraryResourceID: String
    public let assetIdentifier: String
    public let sourceIndex: Int
    public let kind: MediaResourceKind
    public let originalFilename: String
    public let uniformTypeIdentifier: String

    public init(
        libraryResourceID: String,
        assetIdentifier: String,
        sourceIndex: Int,
        kind: MediaResourceKind,
        originalFilename: String,
        uniformTypeIdentifier: String
    ) {
        self.libraryResourceID = libraryResourceID
        self.assetIdentifier = assetIdentifier
        self.sourceIndex = sourceIndex
        self.kind = kind
        self.originalFilename = originalFilename
        self.uniformTypeIdentifier = uniformTypeIdentifier
    }
}

public struct MediaAssetSnapshot: Equatable, Sendable {
    public let localIdentifier: String
    public let kind: MediaAssetKind
    public let creationDate: Date?
    public let sourceLocation: MediaSourceLocation?
    public let pixelWidth: Int
    public let pixelHeight: Int
    public let duration: TimeInterval?
    public let resources: [MediaResourceDescriptor]

    public init(
        localIdentifier: String,
        kind: MediaAssetKind,
        creationDate: Date?,
        sourceLocation: MediaSourceLocation?,
        pixelWidth: Int,
        pixelHeight: Int,
        duration: TimeInterval?,
        resources: [MediaResourceDescriptor]
    ) {
        self.localIdentifier = localIdentifier
        self.kind = kind
        self.creationDate = creationDate
        self.sourceLocation = sourceLocation
        self.pixelWidth = max(0, pixelWidth)
        self.pixelHeight = max(0, pixelHeight)
        self.duration = duration.flatMap { $0.isFinite && $0 >= 0 ? $0 : nil }
        self.resources = resources
    }
}

/// Photos edits are non-destructive and appear as separate resources. Journal
/// imports default to the current full-size edit because it matches what the
/// person selected in Photos. `.originalsOnly` instead chooses the original
/// photo/video resources. Adjustment data and adjustment-base resources are
/// never uploaded. GPS never comes from either file representation; only the
/// validated `PHAsset.location` snapshot is authoritative.
public enum MediaRepresentationPolicy: String, Codable, Equatable, Sendable {
    case currentEditsWhenAvailable
    case originalsOnly
}

public enum StagedMediaRole: String, Codable, Equatable, Sendable {
    case primary
    case livePhotoMotion
}

public struct SelectedMediaResource: Equatable, Sendable {
    public let role: StagedMediaRole
    public let resource: MediaResourceDescriptor

    public init(role: StagedMediaRole, resource: MediaResourceDescriptor) {
        self.role = role
        self.resource = resource
    }
}

public struct QueuedMediaComponent: Codable, Equatable, Sendable {
    public let id: String
    public let role: StagedMediaRole
    public let stagedFilename: String
    public let originalFilename: String
    public let uniformTypeIdentifier: String
    public let contentType: String
    public let byteCount: Int64

    public init(
        id: String,
        role: StagedMediaRole,
        stagedFilename: String,
        originalFilename: String,
        uniformTypeIdentifier: String,
        contentType: String,
        byteCount: Int64
    ) {
        self.id = id
        self.role = role
        self.stagedFilename = stagedFilename
        self.originalFilename = originalFilename
        self.uniformTypeIdentifier = uniformTypeIdentifier
        self.contentType = contentType
        self.byteCount = byteCount
    }
}

public struct QueuedMediaManifest: Codable, Equatable, Sendable {
    public let schemaVersion: Int
    public let id: String
    public let accountScopeID: String
    public let sourceAssetIdentifier: String
    public let assetKind: MediaAssetKind
    public let representationPolicy: MediaRepresentationPolicy
    public let capturedAt: Date?
    public let coordinate: MediaCoordinate?
    public let pixelWidth: Int
    public let pixelHeight: Int
    public let duration: TimeInterval?
    public let stagedAt: Date
    public let components: [QueuedMediaComponent]

    public init(
        schemaVersion: Int = 1,
        id: String,
        accountScopeID: String,
        sourceAssetIdentifier: String,
        assetKind: MediaAssetKind,
        representationPolicy: MediaRepresentationPolicy,
        capturedAt: Date?,
        coordinate: MediaCoordinate?,
        pixelWidth: Int,
        pixelHeight: Int,
        duration: TimeInterval?,
        stagedAt: Date,
        components: [QueuedMediaComponent]
    ) {
        self.schemaVersion = schemaVersion
        self.id = id
        self.accountScopeID = accountScopeID
        self.sourceAssetIdentifier = sourceAssetIdentifier
        self.assetKind = assetKind
        self.representationPolicy = representationPolicy
        self.capturedAt = capturedAt
        self.coordinate = coordinate
        self.pixelWidth = pixelWidth
        self.pixelHeight = pixelHeight
        self.duration = duration
        self.stagedAt = stagedAt
        self.components = components
    }
}

public struct StagedMediaFile: Equatable, Sendable {
    public let component: QueuedMediaComponent
    public let fileURL: URL

    public init(component: QueuedMediaComponent, fileURL: URL) {
        self.component = component
        self.fileURL = fileURL
    }
}

public struct StagedMediaItem: Equatable, Sendable {
    public let manifest: QueuedMediaManifest
    public let directoryURL: URL
    public let files: [StagedMediaFile]

    public init(
        manifest: QueuedMediaManifest,
        directoryURL: URL,
        files: [StagedMediaFile]
    ) {
        self.manifest = manifest
        self.directoryURL = directoryURL
        self.files = files
    }
}

public struct MediaIngestionBatch: Equatable, Sendable {
    public let authorization: MediaLibraryAuthorization
    public let items: [StagedMediaItem]
    public let unavailableAssetIdentifiers: [String]

    public init(
        authorization: MediaLibraryAuthorization,
        items: [StagedMediaItem],
        unavailableAssetIdentifiers: [String]
    ) {
        self.authorization = authorization
        self.items = items
        self.unavailableAssetIdentifiers = unavailableAssetIdentifiers
    }
}

public struct MediaIngestionProgress: Equatable, Sendable {
    public let assetIdentifier: String
    public let assetIndex: Int
    public let assetCount: Int
    public let role: StagedMediaRole
    public let resourceFraction: Double
    public let overallFraction: Double

    public init(
        assetIdentifier: String,
        assetIndex: Int,
        assetCount: Int,
        role: StagedMediaRole,
        resourceFraction: Double,
        overallFraction: Double
    ) {
        self.assetIdentifier = assetIdentifier
        self.assetIndex = assetIndex
        self.assetCount = assetCount
        self.role = role
        self.resourceFraction = resourceFraction
        self.overallFraction = overallFraction
    }
}

public typealias MediaProgressHandler = @Sendable (MediaIngestionProgress) -> Void
public typealias MediaResourceProgressHandler = @Sendable (Double) -> Void

public enum MediaIngestionError: Error, Equatable, LocalizedError, Sendable {
    case invalidAccountID
    case emptySelection
    case tooManyAssets(maximum: Int)
    case libraryAccessRequired(MediaLibraryAuthorization)
    case unsupportedAsset(String)
    case requiredResourceMissing(assetIdentifier: String, role: StagedMediaRole)
    case resourceChanged(assetIdentifier: String)
    case emptyResource(assetIdentifier: String, originalFilename: String)
    case fileTooLarge(
        assetIdentifier: String,
        originalFilename: String,
        actualBytes: Int64,
        maximumBytes: Int64
    )
    case libraryFailure(assetIdentifier: String, message: String)
    case storageFailure(String)
    case invalidManifest(String)

    public var errorDescription: String? {
        switch self {
        case .invalidAccountID:
            return "A signed-in account is required before media can be queued."
        case .emptySelection:
            return "Choose at least one photo or video."
        case let .tooManyAssets(maximum):
            return "Choose no more than \(maximum) photos and videos at a time."
        case .libraryAccessRequired(.limited):
            return "Choose media that HikeJournal is allowed to see."
        case .libraryAccessRequired:
            return "Allow photo-library access to add original media."
        case let .unsupportedAsset(identifier):
            return "The selected Photos item is not a supported image or video (\(identifier))."
        case let .requiredResourceMissing(_, role):
            return role == .livePhotoMotion
                ? "The selected Live Photo's motion resource is unavailable."
                : "The selected photo or video resource is unavailable."
        case let .resourceChanged(identifier):
            return "The selected Photos resource changed before it could be copied (\(identifier))."
        case let .emptyResource(_, filename):
            return "\(filename) did not contain any media data."
        case let .fileTooLarge(_, filename, _, maximum):
            return "\(filename) is larger than the \(maximum / 1024 / 1024) MiB queue limit."
        case let .libraryFailure(_, message):
            return message
        case let .storageFailure(message):
            return message
        case let .invalidManifest(message):
            return message
        }
    }
}
