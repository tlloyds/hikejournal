import Foundation
@testable import HikeJournalDomain

func fixturePhoto(
    _ id: String,
    hikeId: String? = "hike-1",
    takenAt: String? = "2026-08-05T10:00:00Z",
    latitude: Double? = 28.6,
    longitude: Double? = -81.1,
    url: String? = nil
) -> Photo {
    Photo(
        id: id,
        hikeId: hikeId,
        url: url ?? "https://example.test/\(id).jpg",
        caption: "",
        takenAt: takenAt,
        createdAt: takenAt,
        latitude: latitude,
        longitude: longitude,
        width: nil,
        height: nil,
        contentType: "image/jpeg",
        processingStatus: "ready",
        species: []
    )
}

func fixtureHike(
    _ id: String,
    miles: Double? = 2,
    title: String? = nil,
    isStandalone: Bool = false
) -> Hike {
    Hike(
        id: id,
        title: title ?? "Trail \(id)",
        hikeDate: "2026-08-10",
        distanceMiles: miles,
        locationName: "Preserve",
        notes: "",
        isArchived: false,
        isStandalone: isStandalone,
        coverUrl: "",
        photoCount: 0,
        speciesCount: 0
    )
}

func fixtureSpecies(
    _ taxonId: Int64?,
    name: String,
    iconicTaxonName: String = "Other",
    encounterCount: Int = 1,
    latestSeen: String? = nil,
    key: String? = nil
) -> SpeciesRecord {
    SpeciesRecord(
        key: key ?? taxonId.map { "taxon:\($0)" } ?? name,
        taxonId: taxonId,
        commonName: name,
        scientificName: "Example \(name)",
        rank: "species",
        iconicTaxonName: iconicTaxonName,
        wikipediaUrl: "",
        wikipediaSummary: "",
        encounterCount: encounterCount,
        hikeCount: 1,
        hikeIds: ["hike-1"],
        hikeEncounterCounts: ["hike-1": encounterCount],
        hikeCoverUrls: [:],
        hikeLatestSeen: [:],
        latestSeen: latestSeen,
        coverUrl: ""
    )
}

func fixtureReviewItem(
    _ id: String,
    takenAt: String? = "2026-08-05T10:00:00Z",
    latitude: Double? = 28.6,
    longitude: Double? = -81.1,
    hikeId: String? = "hike-1",
    candidate: ReviewCandidate? = nil
) -> ReviewItem {
    ReviewItem(
        id: id,
        photo: fixturePhoto(
            id,
            hikeId: hikeId,
            takenAt: takenAt,
            latitude: latitude,
            longitude: longitude
        ),
        hikeId: hikeId,
        hikeTitle: "Test outing",
        hikeDate: "2026-08-05",
        locationName: "",
        state: "waiting",
        observationId: "observation-\(id)",
        candidates: candidate.map { [$0] } ?? []
    )
}

func fixturePublishItem(
    _ suffix: String,
    takenAt: String? = "2026-08-05T10:00:00Z",
    latitude: Double? = 28.6,
    longitude: Double? = -81.1,
    taxonId: Int64? = 100,
    hikeId: String? = "hike-1"
) -> PublishItem {
    PublishItem(
        id: "observation-\(suffix)",
        photo: fixturePhoto(
            "photo-\(suffix)",
            hikeId: hikeId,
            takenAt: takenAt,
            latitude: latitude,
            longitude: longitude
        ),
        hikeId: hikeId,
        hikeTitle: "Test outing",
        hikeDate: "2026-08-05",
        locationName: "",
        taxonId: taxonId,
        commonName: "Test species",
        scientificName: "Species testus",
        state: "ready",
        inatObservationId: nil,
        inatUrl: "",
        postedAt: nil,
        photoAttached: nil,
        relatedObservationIds: ["observation-\(suffix)"],
        relatedPhotoCount: 1
    )
}

func fixtureDiscoveryTaxon(
    _ id: Int64,
    focusOrder: Int? = nil,
    collected: Bool = false,
    frequencyBand: String = "Regularly reported"
) -> DiscoveryTaxon {
    DiscoveryTaxon(
        taxonId: id,
        commonName: "Species \(id)",
        scientificName: "Species \(id)",
        iconicTaxonName: "Plantae",
        observationCount: 1,
        nearbyRank: Int(id),
        frequencyBand: frequencyBand,
        referencePhoto: nil,
        collected: collected,
        collectedAt: nil,
        collectionPhotoUrl: nil,
        wikipediaUrl: "",
        wikipediaSummary: "",
        matchReason: "",
        focusOrder: focusOrder,
        pendingCredit: false
    )
}

func fixtureQuest(
    id: String = "quest-1",
    status: String = "active",
    taxa: [DiscoveryTaxon]
) -> FieldQuest {
    FieldQuest(
        id: id,
        title: "Focus quest",
        status: status,
        linkedHikeId: nil,
        areaId: "trail-1",
        areaName: "Lake Trail",
        latitude: 28.1,
        longitude: -82.1,
        radiusKm: 10,
        targetDate: "2026-08-10",
        periodLabel: "August",
        iconicTaxon: nil,
        progress: DiscoveryProgress(),
        taxa: taxa
    )
}
