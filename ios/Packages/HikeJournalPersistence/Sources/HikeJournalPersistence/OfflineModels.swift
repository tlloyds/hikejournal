import Foundation

public enum PendingOperationKind: String, Codable, CaseIterable, Sendable {
    case createHike = "create_hike"
    case updateHike = "update_hike"
    case archiveHike = "archive_hike"
    case deleteHike = "delete_hike"
    case uploadPhoto = "upload_photo"
    case uploadRoute = "upload_route"
    case setHikeCover = "set_hike_cover"
    case updateCaption = "update_caption"
    case deletePhoto = "delete_photo"
    case queueSpeciesReview = "queue_species_review"
    case assignKnownSpecies = "assign_known_species"
    case reviewDecision = "review_decision"
    case updateSpeciesQuest = "update_species_quest"
    case createFieldMark = "create_field_mark"
    case updateNaturalHistory = "update_natural_history"

    public var targetsHikeDirectly: Bool {
        switch self {
        case .createHike, .updateHike, .archiveHike, .deleteHike, .setHikeCover:
            true
        default:
            false
        }
    }
}

public enum PendingOperationState: String, Codable, Sendable {
    case queued
    case syncing
    case needsAttention = "needs_attention"
}

public struct PendingOperation: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let kind: PendingOperationKind
    public let entityID: String
    public let parentID: String?
    public let payload: Data
    public let localFilePath: String?
    public let contentType: String?
    public let fileName: String?
    public let state: PendingOperationState
    public let attemptCount: Int
    public let createdAt: Date
    public let updatedAt: Date
    public let lastError: String?

    public init(
        id: String,
        kind: PendingOperationKind,
        entityID: String,
        parentID: String? = nil,
        payload: Data = Data("{}".utf8),
        localFilePath: String? = nil,
        contentType: String? = nil,
        fileName: String? = nil,
        state: PendingOperationState = .queued,
        attemptCount: Int = 0,
        createdAt: Date,
        updatedAt: Date,
        lastError: String? = nil
    ) {
        self.id = id
        self.kind = kind
        self.entityID = entityID
        self.parentID = parentID
        self.payload = payload
        self.localFilePath = localFilePath
        self.contentType = contentType
        self.fileName = fileName
        self.state = state
        self.attemptCount = attemptCount
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.lastError = lastError
    }

    public var targetHikeID: String? {
        parentID ?? (kind.targetsHikeDirectly ? entityID : nil)
    }
}

public enum PersistedTrackingStatus: String, Codable, Sendable {
    case starting
    case recording
    case paused
    case finalizing
    case finished
}

public struct TrackingSessionRecord: Codable, Equatable, Sendable, Identifiable {
    public var id: String { sessionID }
    public let sessionID: String
    public let hikeID: String
    public let activeSlot: Int?
    public let status: PersistedTrackingStatus
    public let startedAt: Date
    public let startedAtMonotonicMilliseconds: Int64
    public let hikeDate: String
    public let bootIdentifier: String
    public let activeElapsedMilliseconds: Int64
    public let activeSinceMonotonicMilliseconds: Int64?
    public let distanceMeters: Double
    public let currentSegment: Int
    public let segmentStartPending: Bool
    public let nextPointSequence: Int64
    public let lastFixAt: Date?
    public let lastFixMonotonicNanoseconds: Int64?
    public let lastAccuracyMeters: Double?
    public let finishedAt: Date?
    public let generatedTCXPath: String?
    public let recoveryReason: String?
    public let errorMessage: String?
    public let updatedAt: Date
    public let domainSnapshot: Data?

    public init(
        sessionID: String,
        hikeID: String,
        activeSlot: Int? = 1,
        status: PersistedTrackingStatus,
        startedAt: Date,
        startedAtMonotonicMilliseconds: Int64,
        hikeDate: String,
        bootIdentifier: String,
        activeElapsedMilliseconds: Int64 = 0,
        activeSinceMonotonicMilliseconds: Int64? = nil,
        distanceMeters: Double = 0,
        currentSegment: Int = 0,
        segmentStartPending: Bool = true,
        nextPointSequence: Int64 = 0,
        lastFixAt: Date? = nil,
        lastFixMonotonicNanoseconds: Int64? = nil,
        lastAccuracyMeters: Double? = nil,
        finishedAt: Date? = nil,
        generatedTCXPath: String? = nil,
        recoveryReason: String? = nil,
        errorMessage: String? = nil,
        updatedAt: Date,
        domainSnapshot: Data? = nil
    ) {
        self.sessionID = sessionID
        self.hikeID = hikeID
        self.activeSlot = activeSlot
        self.status = status
        self.startedAt = startedAt
        self.startedAtMonotonicMilliseconds = startedAtMonotonicMilliseconds
        self.hikeDate = hikeDate
        self.bootIdentifier = bootIdentifier
        self.activeElapsedMilliseconds = activeElapsedMilliseconds
        self.activeSinceMonotonicMilliseconds = activeSinceMonotonicMilliseconds
        self.distanceMeters = distanceMeters
        self.currentSegment = currentSegment
        self.segmentStartPending = segmentStartPending
        self.nextPointSequence = nextPointSequence
        self.lastFixAt = lastFixAt
        self.lastFixMonotonicNanoseconds = lastFixMonotonicNanoseconds
        self.lastAccuracyMeters = lastAccuracyMeters
        self.finishedAt = finishedAt
        self.generatedTCXPath = generatedTCXPath
        self.recoveryReason = recoveryReason
        self.errorMessage = errorMessage
        self.updatedAt = updatedAt
        self.domainSnapshot = domainSnapshot
    }
}

public struct TrackingPointRecord: Codable, Equatable, Sendable {
    public let sessionID: String
    public let sequence: Int64
    public let segment: Int
    public let latitude: Double
    public let longitude: Double
    public let altitudeMeters: Double?
    public let accuracyMeters: Double
    public let fixAt: Date
    public let fixMonotonicNanoseconds: Int64?
    public let distanceFromPreviousMeters: Double

    public init(
        sessionID: String,
        sequence: Int64,
        segment: Int,
        latitude: Double,
        longitude: Double,
        altitudeMeters: Double? = nil,
        accuracyMeters: Double,
        fixAt: Date,
        fixMonotonicNanoseconds: Int64? = nil,
        distanceFromPreviousMeters: Double
    ) {
        self.sessionID = sessionID
        self.sequence = sequence
        self.segment = segment
        self.latitude = latitude
        self.longitude = longitude
        self.altitudeMeters = altitudeMeters
        self.accuracyMeters = accuracyMeters
        self.fixAt = fixAt
        self.fixMonotonicNanoseconds = fixMonotonicNanoseconds
        self.distanceFromPreviousMeters = distanceFromPreviousMeters
    }
}

public enum FieldMarkSyncState: String, Codable, Sendable {
    case local
    case queued
    case syncing
    case synced
    case needsAttention = "needs_attention"
}

public struct FieldMarkRecord: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let hikeID: String
    public let recordingSessionID: String?
    public let markedAt: Date
    public let latitude: Double
    public let longitude: Double
    public let accuracyMeters: Double?
    public let markType: String
    public let note: String
    public let syncState: FieldMarkSyncState
    public let createdAt: Date
    public let updatedAt: Date

    public init(
        id: String,
        hikeID: String,
        recordingSessionID: String? = nil,
        markedAt: Date,
        latitude: Double,
        longitude: Double,
        accuracyMeters: Double? = nil,
        markType: String,
        note: String = "",
        syncState: FieldMarkSyncState = .local,
        createdAt: Date,
        updatedAt: Date
    ) {
        self.id = id
        self.hikeID = hikeID
        self.recordingSessionID = recordingSessionID
        self.markedAt = markedAt
        self.latitude = latitude
        self.longitude = longitude
        self.accuracyMeters = accuracyMeters
        self.markType = markType
        self.note = note
        self.syncState = syncState
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

public struct SyncQueueSummary: Equatable, Sendable {
    public let queued: Int
    public let syncing: Int
    public let needsAttention: Int

    public init(queued: Int, syncing: Int, needsAttention: Int) {
        self.queued = queued
        self.syncing = syncing
        self.needsAttention = needsAttention
    }
}

/// Account-scoped server material retained for cached-first screens. The
/// payload is the exact response body, so a newer app can decode it with the
/// same tolerant models it uses for the network response. Expiry controls
/// refresh policy; expired values remain readable for honest offline fallback.
public struct CachedResource: Equatable, Sendable {
    public let namespace: String
    public let key: String
    public let payload: Data
    public let etag: String?
    public let storedAt: Date
    public let expiresAt: Date?

    public init(
        namespace: String,
        key: String,
        payload: Data,
        etag: String? = nil,
        storedAt: Date,
        expiresAt: Date? = nil
    ) {
        self.namespace = namespace
        self.key = key
        self.payload = payload
        self.etag = etag
        self.storedAt = storedAt
        self.expiresAt = expiresAt
    }

    public func isFresh(at date: Date) -> Bool {
        expiresAt.map { $0 > date } ?? true
    }
}
