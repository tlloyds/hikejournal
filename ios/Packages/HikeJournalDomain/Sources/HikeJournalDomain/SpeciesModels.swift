import Foundation

public struct SeasonalMonth: Codable, Equatable, Sendable {
    public let month: Int
    public let label: String
    public let count: Int
    public let relativeIntensity: Double

    public init(month: Int, label: String, count: Int, relativeIntensity: Double) {
        self.month = month
        self.label = label
        self.count = count
        self.relativeIntensity = relativeIntensity
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            month: values.integer("month"),
            label: values.string("label"),
            count: values.integer("count"),
            relativeIntensity: values.double("relativeIntensity")
        )
    }
}

public struct SeasonalYear: Codable, Equatable, Sendable {
    public let year: Int
    public let firstObservedOn: String
    public let lastObservedOn: String
    public let observationCount: Int

    public init(
        year: Int,
        firstObservedOn: String,
        lastObservedOn: String,
        observationCount: Int
    ) {
        self.year = year
        self.firstObservedOn = firstObservedOn
        self.lastObservedOn = lastObservedOn
        self.observationCount = observationCount
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            year: values.integer("year"),
            firstObservedOn: values.string("firstObservedOn"),
            lastObservedOn: values.string("lastObservedOn"),
            observationCount: values.integer("observationCount")
        )
    }
}

public struct SeasonalHistory: Codable, Equatable, Sendable {
    public let observationCount: Int
    public let firstObservedOn: String?
    public let latestObservedOn: String?
    public let months: [SeasonalMonth]
    public let years: [SeasonalYear]
    public let guidance: String

    public init(
        observationCount: Int = 0,
        firstObservedOn: String? = nil,
        latestObservedOn: String? = nil,
        months: [SeasonalMonth] = [],
        years: [SeasonalYear] = [],
        guidance: String = ""
    ) {
        self.observationCount = observationCount
        self.firstObservedOn = firstObservedOn
        self.latestObservedOn = latestObservedOn
        self.months = months
        self.years = years
        self.guidance = guidance
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        let decodedMonths = try values.array(SeasonalMonth.self, "months")
        months = decodedMonths.enumerated().map { index, value in
            guard value.month == 0 else { return value }
            return SeasonalMonth(
                month: index + 1,
                label: value.label,
                count: value.count,
                relativeIntensity: value.relativeIntensity
            )
        }
        observationCount = values.integer("observationCount")
        firstObservedOn = values.optionalString("firstObservedOn")
        latestObservedOn = values.optionalString("latestObservedOn")
        years = try values.array(SeasonalYear.self, "years")
        guidance = values.string("guidance")
    }
}

public struct Encounter: Codable, Equatable, Sendable {
    public let photo: Photo
    public let hikeId: String?
    public let hikeTitle: String
    public let hikeDate: String
    public let locationName: String
    public let observedOn: String?

    public init(
        photo: Photo,
        hikeId: String?,
        hikeTitle: String,
        hikeDate: String,
        locationName: String,
        observedOn: String?
    ) {
        self.photo = photo
        self.hikeId = hikeId
        self.hikeTitle = hikeTitle
        self.hikeDate = hikeDate
        self.locationName = locationName
        self.observedOn = observedOn
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            photo: try values.value(Photo.self, "photo"),
            hikeId: values.optionalString("hikeId"),
            hikeTitle: values.string("hikeTitle", default: "Everyday sighting"),
            hikeDate: values.string("hikeDate"),
            locationName: values.string("locationName"),
            observedOn: values.optionalString("observedOn")
        )
    }
}

public struct SpeciesRecord: Codable, Equatable, Sendable {
    public let key: String
    public let taxonId: Int64?
    public let commonName: String
    public let scientificName: String
    public let rank: String
    public let iconicTaxonName: String
    public let wikipediaUrl: String
    public let wikipediaSummary: String
    public let encounterCount: Int
    public let hikeCount: Int
    public let hikeIds: [String]
    public let hikeEncounterCounts: [String: Int]
    public let hikeCoverUrls: [String: String]
    public let hikeLatestSeen: [String: String]
    public let latestSeen: String?
    public let coverUrl: String
    public let encounters: [Encounter]
    public let seasonalHistory: SeasonalHistory

    public init(
        key: String,
        taxonId: Int64?,
        commonName: String,
        scientificName: String,
        rank: String,
        iconicTaxonName: String,
        wikipediaUrl: String,
        wikipediaSummary: String,
        encounterCount: Int,
        hikeCount: Int,
        hikeIds: [String],
        hikeEncounterCounts: [String: Int],
        hikeCoverUrls: [String: String],
        hikeLatestSeen: [String: String],
        latestSeen: String?,
        coverUrl: String,
        encounters: [Encounter] = [],
        seasonalHistory: SeasonalHistory = SeasonalHistory()
    ) {
        self.key = key
        self.taxonId = taxonId
        self.commonName = commonName
        self.scientificName = scientificName
        self.rank = rank
        self.iconicTaxonName = iconicTaxonName
        self.wikipediaUrl = wikipediaUrl
        self.wikipediaSummary = wikipediaSummary
        self.encounterCount = encounterCount
        self.hikeCount = hikeCount
        self.hikeIds = hikeIds
        self.hikeEncounterCounts = hikeEncounterCounts
        self.hikeCoverUrls = hikeCoverUrls
        self.hikeLatestSeen = hikeLatestSeen
        self.latestSeen = latestSeen
        self.coverUrl = coverUrl
        self.encounters = encounters
        self.seasonalHistory = seasonalHistory
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            key: values.string("key"),
            taxonId: values.optionalInt64("taxonId"),
            commonName: values.string("commonName", default: "Unknown species"),
            scientificName: values.string("scientificName"),
            rank: values.string("rank"),
            iconicTaxonName: values.string("iconicTaxonName", default: "Other"),
            wikipediaUrl: values.string("wikipediaUrl"),
            wikipediaSummary: plainWikipediaSummary(values.string("wikipediaSummary")),
            encounterCount: values.integer("encounterCount"),
            hikeCount: values.integer("hikeCount"),
            hikeIds: try values.array(String.self, "hikeIds"),
            hikeEncounterCounts: try values.dictionary(Int.self, "hikeEncounterCounts"),
            hikeCoverUrls: try values.dictionary(String.self, "hikeCoverUrls"),
            hikeLatestSeen: try values.dictionary(String.self, "hikeLatestSeen"),
            latestSeen: values.optionalString("latestSeen"),
            coverUrl: values.string("coverUrl"),
            encounters: try values.array(Encounter.self, "encounters"),
            seasonalHistory: try values.optionalValue(SeasonalHistory.self, "seasonalHistory") ?? SeasonalHistory()
        )
    }
}

public struct Sighting: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let hikeId: String?
    public let hikeTitle: String
    public let hikeDate: String
    public let locationName: String
    public let url: String
    public let caption: String
    public let takenAt: String?
    public let latitude: Double
    public let longitude: Double
    public let speciesName: String
    public let scientificName: String
    public let confirmed: Bool

    public init(
        id: String,
        hikeId: String?,
        hikeTitle: String,
        hikeDate: String,
        locationName: String,
        url: String,
        caption: String,
        takenAt: String?,
        latitude: Double,
        longitude: Double,
        speciesName: String,
        scientificName: String,
        confirmed: Bool
    ) {
        self.id = id
        self.hikeId = hikeId
        self.hikeTitle = hikeTitle
        self.hikeDate = hikeDate
        self.locationName = locationName
        self.url = url
        self.caption = caption
        self.takenAt = takenAt
        self.latitude = latitude
        self.longitude = longitude
        self.speciesName = speciesName
        self.scientificName = scientificName
        self.confirmed = confirmed
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            id: values.string("id"),
            hikeId: values.optionalString("hikeId"),
            hikeTitle: values.string("hikeTitle", default: "Everyday sighting"),
            hikeDate: values.string("hikeDate"),
            locationName: values.string("locationName"),
            url: values.string("url"),
            caption: values.string("caption"),
            takenAt: values.optionalString("takenAt"),
            latitude: values.double("lat"),
            longitude: values.double("lng"),
            speciesName: values.string("speciesName"),
            scientificName: values.string("scientificName"),
            confirmed: values.boolean("confirmed")
        )
    }
}

public func plainWikipediaSummary(_ value: String) -> String {
    var result = value.replacingOccurrences(
        of: "<[^>]*>",
        with: " ",
        options: .regularExpression
    )
    let replacements = [
        "&nbsp;": " ",
        "&amp;": "&",
        "&quot;": "\"",
        "&#39;": "'",
    ]
    for (source, replacement) in replacements {
        result = result.replacingOccurrences(of: source, with: replacement)
    }
    return result
        .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
        .domainTrimmed
}
