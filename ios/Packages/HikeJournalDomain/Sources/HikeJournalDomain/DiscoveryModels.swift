import Foundation

public let defaultReportingFrequencyBand = "Less often reported"
public let defaultReportingFrequencyGuidance =
    "Reporting frequency is not a probability of encounter."

public struct DiscoveryPhoto: Codable, Equatable, Sendable {
    public let url: String
    public let attribution: String
    public let licenseCode: String

    public init(url: String, attribution: String, licenseCode: String) {
        self.url = url
        self.attribution = attribution
        self.licenseCode = licenseCode
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            url: values.string("url"),
            attribution: values.string("attribution"),
            licenseCode: values.string("licenseCode")
        )
    }
}

public struct DiscoveryTaxon: Codable, Equatable, Sendable, Identifiable {
    public var id: Int64 { taxonId }
    public let taxonId: Int64
    public let commonName: String
    public let scientificName: String
    public let iconicTaxonName: String
    public let observationCount: Int
    public let nearbyRank: Int
    public let frequencyBand: String
    public let referencePhoto: DiscoveryPhoto?
    public let collected: Bool
    public let collectedAt: String?
    public let collectionPhotoUrl: String?
    public let wikipediaUrl: String
    public let wikipediaSummary: String
    public let matchReason: String
    public let focusOrder: Int?
    public let pendingCredit: Bool

    public init(
        taxonId: Int64,
        commonName: String,
        scientificName: String,
        iconicTaxonName: String,
        observationCount: Int,
        nearbyRank: Int,
        frequencyBand: String,
        referencePhoto: DiscoveryPhoto?,
        collected: Bool,
        collectedAt: String?,
        collectionPhotoUrl: String?,
        wikipediaUrl: String,
        wikipediaSummary: String,
        matchReason: String,
        focusOrder: Int?,
        pendingCredit: Bool
    ) {
        self.taxonId = taxonId
        self.commonName = commonName
        self.scientificName = scientificName
        self.iconicTaxonName = iconicTaxonName
        self.observationCount = observationCount
        self.nearbyRank = nearbyRank
        self.frequencyBand = frequencyBand.domainTrimmed.isEmpty
            ? defaultReportingFrequencyBand
            : frequencyBand
        self.referencePhoto = referencePhoto?.url.domainTrimmed.isEmpty == false ? referencePhoto : nil
        self.collected = collected
        self.collectedAt = collectedAt
        self.collectionPhotoUrl = collectionPhotoUrl
        self.wikipediaUrl = wikipediaUrl
        self.wikipediaSummary = wikipediaSummary
        self.matchReason = matchReason
        self.focusOrder = focusOrder
        self.pendingCredit = pendingCredit
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            taxonId: values.int64("taxonId"),
            commonName: values.string("commonName", default: "Unknown species"),
            scientificName: values.string("scientificName"),
            iconicTaxonName: values.string("iconicTaxonName", default: "Other"),
            observationCount: values.integer("observationCount"),
            nearbyRank: values.integer("nearbyRank"),
            frequencyBand: values.string("frequencyBand", default: defaultReportingFrequencyBand),
            referencePhoto: try values.optionalValue(DiscoveryPhoto.self, "referencePhoto"),
            collected: values.boolean("collected"),
            collectedAt: values.optionalString("collectedAt"),
            collectionPhotoUrl: values.optionalString("collectionPhotoUrl"),
            wikipediaUrl: values.string("wikipediaUrl"),
            wikipediaSummary: values.string("wikipediaSummary"),
            matchReason: values.string("matchReason"),
            focusOrder: values.optionalInteger("focusOrder"),
            pendingCredit: values.boolean("pendingCredit")
        )
    }
}

public struct DiscoveryProgress: Codable, Equatable, Sendable {
    public let collectedCount: Int
    public let totalCount: Int
    public let remainingCount: Int

    public init(collectedCount: Int = 0, totalCount: Int = 0, remainingCount: Int = 0) {
        self.collectedCount = collectedCount
        self.totalCount = totalCount
        self.remainingCount = remainingCount
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            collectedCount: values.integer("collectedCount"),
            totalCount: values.integer("totalCount"),
            remainingCount: values.integer("remainingCount")
        )
    }
}

public struct DiscoveryArea: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let name: String
    public let latitude: Double
    public let longitude: Double
    public let locationType: String

    public init(
        id: String,
        name: String,
        latitude: Double,
        longitude: Double,
        locationType: String
    ) {
        self.id = id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.locationType = locationType
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            id: values.string("id"),
            name: values.string("name", default: "Unnamed area"),
            latitude: values.double("lat"),
            longitude: values.double("lng"),
            locationType: values.string("locationType")
        )
    }
}

public func filterDiscoveryAreas(
    _ areas: [DiscoveryArea],
    query: String,
    limit: Int = 6
) -> [DiscoveryArea] {
    guard limit > 0 else { return [] }
    let normalized = query.domainTrimmed
    return Array(
        areas.lazy.filter {
            normalized.isEmpty
                || $0.name.range(of: normalized, options: [.caseInsensitive, .diacriticInsensitive]) != nil
        }.prefix(limit)
    )
}

private struct DiscoveryAreaPayload: Decodable {
    let id: String
    let name: String
    let latitude: Double?
    let longitude: Double?
    let radiusKm: Int

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        id = values.string("id")
        name = values.string("name", default: "Selected area")
        latitude = values.optionalDouble("lat")
        longitude = values.optionalDouble("lng")
        radiusKm = values.integer("radiusKm", default: 10)
    }
}

private struct DiscoveryPeriodPayload: Decodable {
    let targetDate: String
    let label: String

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        targetDate = values.string("targetDate")
        label = values.string("label")
    }
}

private struct DiscoveryFiltersPayload: Decodable {
    let iconicTaxon: String?
    let resultLimit: Int

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        iconicTaxon = values.optionalString("iconicTaxon")
        resultLimit = values.integer("resultLimit", default: 50)
    }
}

private struct DiscoveryDensityPayload: Decodable {
    let level: String
    let message: String

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        level = values.string("level", default: "normal")
        message = values.string("message")
    }
}

private struct DiscoverySourcePayload: Decodable {
    let guidance: String
    let fromCache: Bool

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        guidance = values.string("guidance", default: defaultReportingFrequencyGuidance)
        fromCache = values.boolean("fromCache")
    }
}

private struct QuestSourcePayload: Decodable {
    let guidance: String
    let fromCache: Bool

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        guidance = values.string(
            "guidance",
            default: "Markers use locations iNaturalist makes public."
        )
        fromCache = values.boolean("fromCache")
    }
}

public struct NearbySpecies: Codable, Equatable, Sendable {
    public let areaId: String
    public let areaName: String
    public let latitude: Double?
    public let longitude: Double?
    public let radiusKm: Int
    public let targetDate: String
    public let periodLabel: String
    public let iconicTaxon: String?
    public let resultLimit: Int
    public let dataDensity: String
    public let dataDensityMessage: String
    public let sourceGuidance: String
    public let fromCache: Bool
    public let progress: DiscoveryProgress
    public let taxa: [DiscoveryTaxon]

    public init(
        areaId: String,
        areaName: String,
        latitude: Double?,
        longitude: Double?,
        radiusKm: Int,
        targetDate: String,
        periodLabel: String,
        iconicTaxon: String?,
        resultLimit: Int,
        dataDensity: String,
        dataDensityMessage: String,
        sourceGuidance: String,
        fromCache: Bool,
        progress: DiscoveryProgress,
        taxa: [DiscoveryTaxon]
    ) {
        self.areaId = areaId
        self.areaName = areaName
        self.latitude = latitude
        self.longitude = longitude
        self.radiusKm = radiusKm
        self.targetDate = targetDate
        self.periodLabel = periodLabel
        self.iconicTaxon = iconicTaxon
        self.resultLimit = resultLimit
        self.dataDensity = dataDensity
        self.dataDensityMessage = dataDensityMessage
        self.sourceGuidance = sourceGuidance.domainTrimmed.isEmpty
            ? defaultReportingFrequencyGuidance
            : sourceGuidance
        self.fromCache = fromCache
        self.progress = progress
        self.taxa = taxa
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        let area = try values.optionalValue(DiscoveryAreaPayload.self, "area")
        let period = try values.optionalValue(DiscoveryPeriodPayload.self, "period")
        let filters = try values.optionalValue(DiscoveryFiltersPayload.self, "filters")
        let density = try values.optionalValue(DiscoveryDensityPayload.self, "dataDensity")
        let source = try values.optionalValue(DiscoverySourcePayload.self, "source")
        self.init(
            areaId: area?.id ?? "",
            areaName: area?.name ?? "Selected area",
            latitude: area?.latitude,
            longitude: area?.longitude,
            radiusKm: area?.radiusKm ?? 10,
            targetDate: period?.targetDate ?? "",
            periodLabel: period?.label ?? "",
            iconicTaxon: filters?.iconicTaxon,
            resultLimit: filters?.resultLimit ?? 50,
            dataDensity: density?.level ?? "normal",
            dataDensityMessage: density?.message ?? "",
            sourceGuidance: source?.guidance ?? defaultReportingFrequencyGuidance,
            fromCache: source?.fromCache ?? false,
            progress: try values.optionalValue(DiscoveryProgress.self, "progress") ?? DiscoveryProgress(),
            taxa: try values.array(DiscoveryTaxon.self, "taxa")
        )
    }
}

public struct FieldQuest: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let title: String
    public let status: String
    public let linkedHikeId: String?
    public let areaId: String
    public let areaName: String
    public let latitude: Double?
    public let longitude: Double?
    public let radiusKm: Int
    public let targetDate: String
    public let periodLabel: String
    public let iconicTaxon: String?
    public let progress: DiscoveryProgress
    public let taxa: [DiscoveryTaxon]
    public let pendingFocusSync: Bool

    public init(
        id: String,
        title: String,
        status: String,
        linkedHikeId: String?,
        areaId: String,
        areaName: String,
        latitude: Double?,
        longitude: Double?,
        radiusKm: Int,
        targetDate: String,
        periodLabel: String,
        iconicTaxon: String?,
        progress: DiscoveryProgress,
        taxa: [DiscoveryTaxon],
        pendingFocusSync: Bool = false
    ) {
        self.id = id
        self.title = title
        self.status = status
        self.linkedHikeId = linkedHikeId
        self.areaId = areaId
        self.areaName = areaName
        self.latitude = latitude
        self.longitude = longitude
        self.radiusKm = radiusKm
        self.targetDate = targetDate
        self.periodLabel = periodLabel
        self.iconicTaxon = iconicTaxon
        self.progress = progress
        self.taxa = taxa
        self.pendingFocusSync = pendingFocusSync
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        let area = try values.optionalValue(DiscoveryAreaPayload.self, "area")
        let period = try values.optionalValue(DiscoveryPeriodPayload.self, "period")
        let filters = try values.optionalValue(DiscoveryFiltersPayload.self, "filters")
        self.init(
            id: values.string("id"),
            title: values.string("title", default: "Field Quest"),
            status: values.string("status", default: "active"),
            linkedHikeId: values.optionalString("linkedHikeId"),
            areaId: area?.id ?? "",
            areaName: area?.name ?? "Selected area",
            latitude: area?.latitude,
            longitude: area?.longitude,
            radiusKm: area?.radiusKm ?? 10,
            targetDate: period?.targetDate ?? "",
            periodLabel: period?.label ?? "",
            iconicTaxon: filters?.iconicTaxon,
            progress: try values.optionalValue(DiscoveryProgress.self, "progress") ?? DiscoveryProgress(),
            taxa: try values.array(DiscoveryTaxon.self, "taxa"),
            pendingFocusSync: values.boolean("pendingFocusSync")
        )
    }
}

public struct QuestSighting: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let latitude: Double
    public let longitude: Double
    public let observedOn: String
    public let placeGuess: String
    public let observer: String
    public let uri: String
    public let photoUrl: String
    public let photoAttribution: String
    public let photoLicenseCode: String
    public let positionalAccuracyMeters: Int?
    public let obscured: Bool

    public init(
        id: String,
        latitude: Double,
        longitude: Double,
        observedOn: String,
        placeGuess: String,
        observer: String,
        uri: String,
        photoUrl: String,
        photoAttribution: String,
        photoLicenseCode: String,
        positionalAccuracyMeters: Int?,
        obscured: Bool
    ) {
        self.id = id
        self.latitude = latitude
        self.longitude = longitude
        self.observedOn = observedOn
        self.placeGuess = placeGuess
        self.observer = observer
        self.uri = uri
        self.photoUrl = photoUrl
        self.photoAttribution = photoAttribution
        self.photoLicenseCode = photoLicenseCode
        self.positionalAccuracyMeters = positionalAccuracyMeters
        self.obscured = obscured
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            id: values.string("id"),
            latitude: values.double("lat"),
            longitude: values.double("lng"),
            observedOn: values.string("observedOn"),
            placeGuess: values.string("placeGuess"),
            observer: values.string("observer"),
            uri: values.string("uri"),
            photoUrl: values.string("photoUrl"),
            photoAttribution: values.string("photoAttribution"),
            photoLicenseCode: values.string("photoLicenseCode"),
            positionalAccuracyMeters: values.optionalInteger("positionalAccuracyM"),
            obscured: values.boolean("obscured")
        )
    }
}

private struct QuestMapQuestPayload: Decodable {
    let id: String
    let title: String
    let areaName: String
    let latitude: Double
    let longitude: Double
    let radiusKm: Int
    let periodLabel: String

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        id = values.string("id")
        title = values.string("title", default: "Field Quest")
        areaName = values.string("areaName", default: "Selected area")
        latitude = values.double("lat")
        longitude = values.double("lng")
        radiusKm = values.integer("radiusKm", default: 10)
        periodLabel = values.string("periodLabel")
    }
}

private struct QuestMapTaxonPayload: Decodable {
    let taxonId: Int64
    let commonName: String
    let scientificName: String

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        taxonId = values.int64("taxonId")
        commonName = values.string("commonName", default: "Unknown species")
        scientificName = values.string("scientificName")
    }
}

public struct QuestSightingsMap: Codable, Equatable, Sendable {
    public let questId: String
    public let questTitle: String
    public let areaName: String
    public let latitude: Double
    public let longitude: Double
    public let radiusKm: Int
    public let periodLabel: String
    public let taxonId: Int64
    public let commonName: String
    public let scientificName: String
    public let totalResults: Int
    public let mappedCount: Int
    public let limited: Bool
    public let sourceGuidance: String
    public let sightings: [QuestSighting]

    public init(
        questId: String,
        questTitle: String,
        areaName: String,
        latitude: Double,
        longitude: Double,
        radiusKm: Int,
        periodLabel: String,
        taxonId: Int64,
        commonName: String,
        scientificName: String,
        totalResults: Int,
        mappedCount: Int,
        limited: Bool,
        sourceGuidance: String,
        sightings: [QuestSighting]
    ) {
        self.questId = questId
        self.questTitle = questTitle
        self.areaName = areaName
        self.latitude = latitude
        self.longitude = longitude
        self.radiusKm = radiusKm
        self.periodLabel = periodLabel
        self.taxonId = taxonId
        self.commonName = commonName
        self.scientificName = scientificName
        self.totalResults = totalResults
        self.mappedCount = mappedCount
        self.limited = limited
        self.sourceGuidance = sourceGuidance
        self.sightings = sightings
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        let quest = try values.optionalValue(QuestMapQuestPayload.self, "quest")
        let taxon = try values.optionalValue(QuestMapTaxonPayload.self, "taxon")
        let source = try values.optionalValue(QuestSourcePayload.self, "source")
        self.init(
            questId: quest?.id ?? "",
            questTitle: quest?.title ?? "Field Quest",
            areaName: quest?.areaName ?? "Selected area",
            latitude: quest?.latitude ?? 0,
            longitude: quest?.longitude ?? 0,
            radiusKm: quest?.radiusKm ?? 10,
            periodLabel: quest?.periodLabel ?? "",
            taxonId: taxon?.taxonId ?? 0,
            commonName: taxon?.commonName ?? "Unknown species",
            scientificName: taxon?.scientificName ?? "",
            totalResults: values.integer("totalResults"),
            mappedCount: values.integer("mappedCount"),
            limited: values.boolean("limited"),
            sourceGuidance: source?.guidance ?? "Markers use locations iNaturalist makes public.",
            sightings: try values.array(QuestSighting.self, "sightings")
        )
    }
}

public struct BriefingItem: Codable, Equatable, Sendable, Identifiable {
    public var id: String { key }
    public let key: String
    public let taxonId: Int64?
    public let commonName: String
    public let scientificName: String
    public let iconicTaxonName: String
    public let section: String
    public let reasons: [String]
    public let referencePhotoUrl: String
    public let referencePhotoAttribution: String
    public let referencePhotoLicenseCode: String
    public let observationCount: Int
    public let nearbyRank: Int
    public let frequencyBand: String
    public let collected: Bool
    public let collectedAt: String?
    public let collectionPhotoUrl: String?
    public let wikipediaUrl: String
    public let wikipediaSummary: String
    public let pendingCredit: Bool

    public init(
        key: String,
        taxonId: Int64?,
        commonName: String,
        scientificName: String,
        iconicTaxonName: String,
        section: String,
        reasons: [String],
        referencePhotoUrl: String,
        referencePhotoAttribution: String,
        referencePhotoLicenseCode: String,
        observationCount: Int,
        nearbyRank: Int,
        frequencyBand: String,
        collected: Bool,
        collectedAt: String?,
        collectionPhotoUrl: String?,
        wikipediaUrl: String,
        wikipediaSummary: String,
        pendingCredit: Bool
    ) {
        self.key = key
        self.taxonId = taxonId
        self.commonName = commonName
        self.scientificName = scientificName
        self.iconicTaxonName = iconicTaxonName
        self.section = section
        self.reasons = reasons
        self.referencePhotoUrl = referencePhotoUrl
        self.referencePhotoAttribution = referencePhotoAttribution
        self.referencePhotoLicenseCode = referencePhotoLicenseCode
        self.observationCount = observationCount
        self.nearbyRank = nearbyRank
        self.frequencyBand = frequencyBand
        self.collected = collected
        self.collectedAt = collectedAt
        self.collectionPhotoUrl = collectionPhotoUrl
        self.wikipediaUrl = wikipediaUrl
        self.wikipediaSummary = wikipediaSummary
        self.pendingCredit = pendingCredit
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        let photo = try values.optionalValue(DiscoveryPhoto.self, "referencePhoto")
        let photoURL = photo?.url ?? values.string("referencePhotoUrl")
        let photoAttribution = photo?.attribution ?? values.string("referencePhotoAttribution")
        let photoLicenseCode = photo?.licenseCode ?? values.string("referencePhotoLicenseCode")
        self.init(
            key: values.string("key"),
            taxonId: values.optionalInt64("taxonId"),
            commonName: values.string("commonName", default: "Unknown species"),
            scientificName: values.string("scientificName"),
            iconicTaxonName: values.string("iconicTaxonName", default: "Other"),
            section: values.string("section"),
            reasons: try values.array(String.self, "reasons"),
            referencePhotoUrl: photoURL,
            referencePhotoAttribution: photoAttribution,
            referencePhotoLicenseCode: photoLicenseCode,
            observationCount: values.integer("observationCount"),
            nearbyRank: values.integer("nearbyRank"),
            frequencyBand: values.string("frequencyBand", default: "Nearby record"),
            collected: values.boolean("collected"),
            collectedAt: values.optionalString("collectedAt"),
            collectionPhotoUrl: values.optionalString("collectionPhotoUrl"),
            wikipediaUrl: values.string("wikipediaUrl"),
            wikipediaSummary: values.string("wikipediaSummary"),
            pendingCredit: values.boolean("pendingCredit")
        )
    }

    public func toDiscoveryTaxon() -> DiscoveryTaxon {
        DiscoveryTaxon(
            taxonId: taxonId ?? 0,
            commonName: commonName,
            scientificName: scientificName,
            iconicTaxonName: iconicTaxonName,
            observationCount: observationCount,
            nearbyRank: nearbyRank,
            frequencyBand: frequencyBand,
            referencePhoto: referencePhotoUrl.domainTrimmed.isEmpty ? nil : DiscoveryPhoto(
                url: referencePhotoUrl,
                attribution: referencePhotoAttribution,
                licenseCode: referencePhotoLicenseCode
            ),
            collected: collected,
            collectedAt: collectedAt,
            collectionPhotoUrl: collectionPhotoUrl,
            wikipediaUrl: wikipediaUrl,
            wikipediaSummary: wikipediaSummary,
            matchReason: reasons.joined(separator: "\n\n"),
            focusOrder: nil,
            pendingCredit: pendingCredit
        )
    }
}

public struct BriefingSection: Codable, Equatable, Sendable {
    public let title: String
    public let items: [BriefingItem]

    public init(title: String, items: [BriefingItem]) {
        self.title = title
        self.items = items
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            title: values.string("title"),
            items: try values.array(BriefingItem.self, "items")
        )
    }
}

public struct FieldBriefing: Codable, Equatable, Sendable {
    public let areaId: String
    public let areaName: String
    public let latitude: Double?
    public let longitude: Double?
    public let radiusKm: Int
    public let targetDate: String
    public let periodLabel: String
    public let sections: [BriefingSection]
    public let guidance: String

    public init(
        areaId: String,
        areaName: String,
        latitude: Double?,
        longitude: Double?,
        radiusKm: Int,
        targetDate: String,
        periodLabel: String,
        sections: [BriefingSection],
        guidance: String
    ) {
        self.areaId = areaId
        self.areaName = areaName
        self.latitude = latitude
        self.longitude = longitude
        self.radiusKm = radiusKm
        self.targetDate = targetDate
        self.periodLabel = periodLabel
        self.sections = sections
        self.guidance = guidance
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        let area = try values.optionalValue(DiscoveryAreaPayload.self, "area")
        let period = try values.optionalValue(DiscoveryPeriodPayload.self, "period")
        self.init(
            areaId: area?.id ?? "",
            areaName: area?.name ?? "Selected place",
            latitude: area?.latitude,
            longitude: area?.longitude,
            radiusKm: area?.radiusKm ?? 10,
            targetDate: values.string("targetDate"),
            periodLabel: period?.label ?? "",
            sections: try values.array(BriefingSection.self, "sections"),
            guidance: values.string("guidance")
        )
    }
}
