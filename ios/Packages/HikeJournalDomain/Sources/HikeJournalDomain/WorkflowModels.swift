import Foundation

public struct ReviewCandidate: Codable, Equatable, Sendable {
    public let taxonId: Int64?
    public let commonName: String
    public let scientificName: String
    public let confidence: Double?
    public let iconicTaxonName: String

    public init(
        taxonId: Int64?,
        commonName: String,
        scientificName: String,
        confidence: Double?,
        iconicTaxonName: String = "Other"
    ) {
        self.taxonId = taxonId
        self.commonName = commonName
        self.scientificName = scientificName
        self.confidence = confidence.flatMap { $0.isFinite ? $0 : nil }
        self.iconicTaxonName = iconicTaxonName
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            taxonId: values.optionalInt64("taxonId"),
            commonName: values.string("commonName", default: "Unknown species"),
            scientificName: values.string("scientificName"),
            confidence: values.optionalDouble("confidence"),
            iconicTaxonName: values.string("iconicTaxonName", default: "Other")
        )
    }
}

/// iNaturalist has returned both fractions and percentage points. API decisions
/// always receive a finite fraction clamped to the closed 0...1 range.
public func normalizedReviewConfidence(_ confidence: Double?) -> Double? {
    guard let confidence, confidence.isFinite else { return nil }
    return min(1, max(0, confidence > 1 ? confidence / 100 : confidence))
}

public struct ReviewItem: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let photo: Photo
    public let hikeId: String?
    public let hikeTitle: String
    public let hikeDate: String
    public let locationName: String
    public let state: String
    public let observationId: String?
    public let candidates: [ReviewCandidate]

    public init(
        id: String,
        photo: Photo,
        hikeId: String?,
        hikeTitle: String,
        hikeDate: String,
        locationName: String,
        state: String,
        observationId: String?,
        candidates: [ReviewCandidate]
    ) {
        self.id = id
        self.photo = photo
        self.hikeId = hikeId
        self.hikeTitle = hikeTitle
        self.hikeDate = hikeDate
        self.locationName = locationName
        self.state = state
        self.observationId = observationId
        self.candidates = candidates
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            id: values.string("id"),
            photo: try values.value(Photo.self, "photo"),
            hikeId: values.optionalString("hikeId"),
            hikeTitle: values.string("hikeTitle", default: "Everyday sighting"),
            hikeDate: values.string("hikeDate"),
            locationName: values.string("locationName"),
            state: values.string("state", default: "waiting"),
            observationId: values.optionalString("observationId"),
            candidates: try values.array(ReviewCandidate.self, "candidates")
        )
    }
}

public struct ReviewBatchResult: Codable, Equatable, Sendable {
    public let items: [ReviewItem]
    public let processedPhotoIds: [String]
    public let groupedCount: Int
    public let individualCount: Int
    public let warnings: [String]

    public init(
        items: [ReviewItem],
        processedPhotoIds: [String],
        groupedCount: Int,
        individualCount: Int,
        warnings: [String]
    ) {
        self.items = items
        self.processedPhotoIds = processedPhotoIds
        self.groupedCount = groupedCount
        self.individualCount = individualCount
        self.warnings = warnings
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            items: try values.array(ReviewItem.self, "items"),
            processedPhotoIds: try values.array(String.self, "processedPhotoIds"),
            groupedCount: values.integer("groupedCount"),
            individualCount: values.integer("individualCount"),
            warnings: try values.array(String.self, "warnings")
        )
    }
}

public struct ReviewBatchStatus: Codable, Equatable, Sendable {
    public let jobId: String
    public let state: String
    public let totalPhotos: Int
    public let processedCount: Int
    public let processedPhotoIds: [String]
    public let currentPhotoNumber: Int
    public let currentPhotoId: String?
    public let totalGroups: Int
    public let currentGroup: Int
    public let groupedCount: Int
    public let individualCount: Int
    public let warnings: [String]
    public let error: String?
    public let items: [ReviewItem]

    public init(
        jobId: String,
        state: String,
        totalPhotos: Int,
        processedCount: Int,
        processedPhotoIds: [String],
        currentPhotoNumber: Int,
        currentPhotoId: String?,
        totalGroups: Int,
        currentGroup: Int,
        groupedCount: Int,
        individualCount: Int,
        warnings: [String],
        error: String?,
        items: [ReviewItem]
    ) {
        self.jobId = jobId
        self.state = state
        self.totalPhotos = totalPhotos
        self.processedCount = processedCount
        self.processedPhotoIds = processedPhotoIds
        self.currentPhotoNumber = currentPhotoNumber
        self.currentPhotoId = currentPhotoId
        self.totalGroups = totalGroups
        self.currentGroup = currentGroup
        self.groupedCount = groupedCount
        self.individualCount = individualCount
        self.warnings = warnings
        self.error = error
        self.items = items
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        let processedPhotoIds = try values.array(String.self, "processedPhotoIds")
        self.init(
            jobId: values.string("jobId"),
            state: values.string("state", default: "queued"),
            totalPhotos: values.integer("totalPhotos"),
            processedCount: values.integer("processedCount", default: processedPhotoIds.count),
            processedPhotoIds: processedPhotoIds,
            currentPhotoNumber: values.integer("currentPhotoNumber"),
            currentPhotoId: values.optionalString("currentPhotoId"),
            totalGroups: values.integer("totalGroups"),
            currentGroup: values.integer("currentGroup"),
            groupedCount: values.integer("groupedCount"),
            individualCount: values.integer("individualCount"),
            warnings: try values.array(String.self, "warnings"),
            error: values.optionalString("error"),
            items: try values.array(ReviewItem.self, "items")
        )
    }
}

public struct PublishItem: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let photo: Photo
    public let hikeId: String?
    public let hikeTitle: String
    public let hikeDate: String
    public let locationName: String
    public let taxonId: Int64?
    public let commonName: String
    public let scientificName: String
    public let state: String
    public let inatObservationId: Int64?
    public let inatUrl: String
    public let postedAt: String?
    public let photoAttached: Bool?
    public let relatedObservationIds: [String]
    public let relatedPhotoCount: Int

    public init(
        id: String,
        photo: Photo,
        hikeId: String?,
        hikeTitle: String,
        hikeDate: String,
        locationName: String,
        taxonId: Int64?,
        commonName: String,
        scientificName: String,
        state: String,
        inatObservationId: Int64?,
        inatUrl: String,
        postedAt: String?,
        photoAttached: Bool?,
        relatedObservationIds: [String],
        relatedPhotoCount: Int
    ) {
        self.id = id
        self.photo = photo
        self.hikeId = hikeId
        self.hikeTitle = hikeTitle
        self.hikeDate = hikeDate
        self.locationName = locationName
        self.taxonId = taxonId
        self.commonName = commonName
        self.scientificName = scientificName
        self.state = state
        self.inatObservationId = inatObservationId
        self.inatUrl = inatUrl
        self.postedAt = postedAt
        self.photoAttached = photoAttached
        self.relatedObservationIds = relatedObservationIds
        self.relatedPhotoCount = relatedPhotoCount
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            id: values.string("id"),
            photo: try values.value(Photo.self, "photo"),
            hikeId: values.optionalString("hikeId"),
            hikeTitle: values.string("hikeTitle", default: "Everyday sighting"),
            hikeDate: values.string("hikeDate"),
            locationName: values.string("locationName"),
            taxonId: values.optionalInt64("taxonId"),
            commonName: values.string("commonName", default: "Unknown species"),
            scientificName: values.string("scientificName"),
            state: values.string("state", default: "ready"),
            inatObservationId: values.optionalInt64("inatObservationId"),
            inatUrl: values.string("inatUrl"),
            postedAt: values.optionalString("postedAt"),
            photoAttached: values.optionalBoolean("photoAttached"),
            relatedObservationIds: try values.array(String.self, "relatedObservationIds"),
            relatedPhotoCount: values.integer("relatedPhotoCount", default: 1)
        )
    }
}

public struct PublishOptions: Codable, Equatable, Sendable {
    public let observationIds: [String]
    public let description: String
    public let tags: [String]
    public let geoprivacy: String
    public let captive: Bool

    public init(
        observationIds: [String],
        description: String = "",
        tags: [String] = [],
        geoprivacy: String = "open",
        captive: Bool = false
    ) {
        self.observationIds = observationIds
        self.description = description
        self.tags = tags
        self.geoprivacy = geoprivacy
        self.captive = captive
    }
}

public struct PublishBatchStatus: Codable, Equatable, Sendable {
    public let jobId: String
    public let state: String
    public let totalGroups: Int
    public let processedGroupCount: Int
    public let postedGroupCount: Int
    public let failedGroupCount: Int
    public let partialGroupCount: Int
    public let totalPhotos: Int
    public let processedPhotoCount: Int
    public let currentGroup: Int
    public let currentGroupPhotoCount: Int
    public let processedObservationIds: [String]
    public let processedPhotoIds: [String]
    public let errors: [String]
    public let error: String?

    public init(
        jobId: String,
        state: String,
        totalGroups: Int,
        processedGroupCount: Int,
        postedGroupCount: Int,
        failedGroupCount: Int,
        partialGroupCount: Int,
        totalPhotos: Int,
        processedPhotoCount: Int,
        currentGroup: Int,
        currentGroupPhotoCount: Int,
        processedObservationIds: [String],
        processedPhotoIds: [String],
        errors: [String],
        error: String?
    ) {
        self.jobId = jobId
        self.state = state
        self.totalGroups = totalGroups
        self.processedGroupCount = processedGroupCount
        self.postedGroupCount = postedGroupCount
        self.failedGroupCount = failedGroupCount
        self.partialGroupCount = partialGroupCount
        self.totalPhotos = totalPhotos
        self.processedPhotoCount = processedPhotoCount
        self.currentGroup = currentGroup
        self.currentGroupPhotoCount = currentGroupPhotoCount
        self.processedObservationIds = processedObservationIds
        self.processedPhotoIds = processedPhotoIds
        self.errors = errors
        self.error = error
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            jobId: values.string("jobId"),
            state: values.string("state", default: "queued"),
            totalGroups: values.integer("totalGroups"),
            processedGroupCount: values.integer("processedGroupCount"),
            postedGroupCount: values.integer("postedGroupCount"),
            failedGroupCount: values.integer("failedGroupCount"),
            partialGroupCount: values.integer("partialGroupCount"),
            totalPhotos: values.integer("totalPhotos"),
            processedPhotoCount: values.integer("processedPhotoCount"),
            currentGroup: values.integer("currentGroup"),
            currentGroupPhotoCount: values.integer("currentGroupPhotoCount"),
            processedObservationIds: try values.array(String.self, "processedObservationIds"),
            processedPhotoIds: try values.array(String.self, "processedPhotoIds"),
            errors: try values.array(String.self, "errors"),
            error: values.optionalString("error")
        )
    }
}

public struct SyncAttention: Codable, Equatable, Sendable {
    public let kind: String
    public let detail: String
    public let error: String

    public init(kind: String, detail: String, error: String) {
        self.kind = kind
        self.detail = detail
        self.error = error
    }
}

public struct SyncStatus: Codable, Equatable, Sendable {
    public let pendingCount: Int
    public let syncingCount: Int
    public let needsAttentionCount: Int
    public let connected: Bool
    public let lastSyncedAt: Int64?
    public let attentionItems: [SyncAttention]
    public let pendingCreateHikeIds: Set<String>
    public let coverSyncHikeIds: Set<String>
    public let pendingPhotoCount: Int
    public let syncingPhotoCount: Int

    public init(
        pendingCount: Int = 0,
        syncingCount: Int = 0,
        needsAttentionCount: Int = 0,
        connected: Bool = true,
        lastSyncedAt: Int64? = nil,
        attentionItems: [SyncAttention] = [],
        pendingCreateHikeIds: Set<String> = [],
        coverSyncHikeIds: Set<String> = [],
        pendingPhotoCount: Int = 0,
        syncingPhotoCount: Int = 0
    ) {
        self.pendingCount = pendingCount
        self.syncingCount = syncingCount
        self.needsAttentionCount = needsAttentionCount
        self.connected = connected
        self.lastSyncedAt = lastSyncedAt
        self.attentionItems = attentionItems
        self.pendingCreateHikeIds = pendingCreateHikeIds
        self.coverSyncHikeIds = coverSyncHikeIds
        self.pendingPhotoCount = pendingPhotoCount
        self.syncingPhotoCount = syncingPhotoCount
    }
}

private struct PublishCountsPayload: Decodable {
    let ready: Int
    let needsAttention: Int
    let posted: Int

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        ready = values.integer("ready")
        needsAttention = values.integer("needsAttention")
        posted = values.integer("posted")
    }
}

public struct PublishQueue: Codable, Equatable, Sendable {
    public let connected: Bool
    public let readyCount: Int
    public let needsAttentionCount: Int
    public let postedCount: Int
    public let items: [PublishItem]

    public init(
        connected: Bool,
        readyCount: Int,
        needsAttentionCount: Int,
        postedCount: Int,
        items: [PublishItem]
    ) {
        self.connected = connected
        self.readyCount = readyCount
        self.needsAttentionCount = needsAttentionCount
        self.postedCount = postedCount
        self.items = items
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        let counts = try values.optionalValue(PublishCountsPayload.self, "counts")
        self.init(
            connected: values.boolean("connected"),
            readyCount: counts?.ready ?? 0,
            needsAttentionCount: counts?.needsAttention ?? 0,
            postedCount: counts?.posted ?? 0,
            items: try values.array(PublishItem.self, "items")
        )
    }
}

public struct LoadResult<Value: Codable & Equatable & Sendable>: Codable, Equatable, Sendable {
    public let value: Value
    public let fromCache: Bool

    public init(value: Value, fromCache: Bool) {
        self.value = value
        self.fromCache = fromCache
    }
}
