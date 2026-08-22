import Foundation

public struct PlaceVisit: Codable, Equatable, Sendable {
    public let hikeId: String
    public let title: String
    public let hikeDate: String
    public let distanceMiles: Double?
    public let observationCount: Int
    public let speciesCount: Int
    public let newSpeciesCount: Int
    public let cumulativeSpeciesCount: Int
    public let coverUrl: String

    public init(
        hikeId: String,
        title: String,
        hikeDate: String,
        distanceMiles: Double?,
        observationCount: Int,
        speciesCount: Int,
        newSpeciesCount: Int,
        cumulativeSpeciesCount: Int,
        coverUrl: String
    ) {
        self.hikeId = hikeId
        self.title = title
        self.hikeDate = hikeDate
        self.distanceMiles = distanceMiles
        self.observationCount = observationCount
        self.speciesCount = speciesCount
        self.newSpeciesCount = newSpeciesCount
        self.cumulativeSpeciesCount = cumulativeSpeciesCount
        self.coverUrl = coverUrl
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            hikeId: values.string("hikeId"),
            title: values.string("title", default: "Untitled hike"),
            hikeDate: values.string("hikeDate"),
            distanceMiles: values.optionalDouble("distanceMiles"),
            observationCount: values.integer("observationCount"),
            speciesCount: values.integer("speciesCount"),
            newSpeciesCount: values.integer("newSpeciesCount"),
            cumulativeSpeciesCount: values.integer("cumulativeSpeciesCount"),
            coverUrl: values.string("coverUrl")
        )
    }
}

public struct PlaceSpecies: Codable, Equatable, Sendable {
    public let key: String
    public let taxonId: Int64?
    public let commonName: String
    public let scientificName: String
    public let iconicTaxonName: String
    public let encounterCount: Int
    public let referencePhotoUrl: String

    public init(
        key: String,
        taxonId: Int64?,
        commonName: String,
        scientificName: String,
        iconicTaxonName: String,
        encounterCount: Int,
        referencePhotoUrl: String
    ) {
        self.key = key
        self.taxonId = taxonId
        self.commonName = commonName
        self.scientificName = scientificName
        self.iconicTaxonName = iconicTaxonName
        self.encounterCount = encounterCount
        self.referencePhotoUrl = referencePhotoUrl
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            key: values.string("key"),
            taxonId: values.optionalInt64("taxonId"),
            commonName: values.string("commonName", default: "Unknown species"),
            scientificName: values.string("scientificName"),
            iconicTaxonName: values.string("iconicTaxonName", default: "Other"),
            encounterCount: values.integer("encounterCount"),
            referencePhotoUrl: values.string("referencePhotoUrl")
        )
    }
}

public struct PlaceTaxonGroup: Codable, Equatable, Sendable {
    public let name: String
    public let count: Int
    public let species: [PlaceSpecies]

    public init(name: String, count: Int, species: [PlaceSpecies]) {
        self.name = name
        self.count = count
        self.species = species
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            name: values.string("name", default: "Other"),
            count: values.integer("count"),
            species: try values.array(PlaceSpecies.self, "species")
        )
    }
}

/// Swift does not give tuples Codable/Equatable conformance, so Android's
/// `Pair<String, Int>` is represented by this named value type.
public struct TaxonCount: Codable, Equatable, Sendable {
    public let name: String
    public let count: Int

    public init(name: String, count: Int) {
        self.name = name
        self.count = count
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            name: values.string("name", default: "Other"),
            count: values.integer("count")
        )
    }
}

private struct PlaceLocationPayload: Decodable {
    let id: String
    let name: String
    let latitude: Double?
    let longitude: Double?

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        id = values.string("id")
        name = values.string("name", default: "Unknown place")
        latitude = validLatitude(values.optionalDouble("lat"))
        longitude = validLongitude(values.optionalDouble("lng"))
    }
}

private struct PlaceSummaryPayload: Decodable {
    let firstVisit: String?
    let latestVisit: String?
    let outingCount: Int
    let totalDistanceMiles: Double
    let totalDurationSeconds: Int64
    let observationCount: Int
    let speciesCount: Int

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        firstVisit = values.optionalString("firstVisit")
        latestVisit = values.optionalString("latestVisit")
        outingCount = values.integer("outingCount")
        totalDistanceMiles = values.double("totalDistanceMiles")
        totalDurationSeconds = values.int64("totalDurationSeconds")
        observationCount = values.integer("observationCount")
        speciesCount = values.integer("speciesCount")
    }
}

public struct PlaceProfile: Codable, Equatable, Sendable {
    public let locationId: String
    public let name: String
    public let latitude: Double?
    public let longitude: Double?
    public let firstVisit: String?
    public let latestVisit: String?
    public let outingCount: Int
    public let totalDistanceMiles: Double
    public let totalDurationSeconds: Int64
    public let observationCount: Int
    public let speciesCount: Int
    public let taxonCounts: [TaxonCount]
    public let taxonGroups: [PlaceTaxonGroup]
    public let seasonalHistory: SeasonalHistory
    public let visits: [PlaceVisit]
    public let guidance: String
    public let forecast: PlaceForecast?
    public let riverGauges: [RiverGaugeSeries]
    public let liveConditionsNotice: String?

    public init(
        locationId: String,
        name: String,
        latitude: Double?,
        longitude: Double?,
        firstVisit: String?,
        latestVisit: String?,
        outingCount: Int,
        totalDistanceMiles: Double,
        totalDurationSeconds: Int64,
        observationCount: Int,
        speciesCount: Int,
        taxonCounts: [TaxonCount],
        taxonGroups: [PlaceTaxonGroup],
        seasonalHistory: SeasonalHistory,
        visits: [PlaceVisit],
        guidance: String,
        forecast: PlaceForecast? = nil,
        riverGauges: [RiverGaugeSeries] = [],
        liveConditionsNotice: String? = nil
    ) {
        self.locationId = locationId
        self.name = name
        self.latitude = validLatitude(latitude)
        self.longitude = validLongitude(longitude)
        self.firstVisit = firstVisit
        self.latestVisit = latestVisit
        self.outingCount = outingCount
        self.totalDistanceMiles = totalDistanceMiles
        self.totalDurationSeconds = totalDurationSeconds
        self.observationCount = observationCount
        self.speciesCount = speciesCount
        self.taxonCounts = taxonCounts
        self.taxonGroups = taxonGroups
        self.seasonalHistory = seasonalHistory
        self.visits = visits
        self.guidance = guidance
        self.forecast = forecast
        self.riverGauges = riverGauges
        self.liveConditionsNotice = liveConditionsNotice
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        let location = try values.optionalValue(PlaceLocationPayload.self, "location")
        let summary = try values.optionalValue(PlaceSummaryPayload.self, "summary")
        self.init(
            locationId: location?.id ?? "",
            name: location?.name ?? "Unknown place",
            latitude: location?.latitude,
            longitude: location?.longitude,
            firstVisit: summary?.firstVisit,
            latestVisit: summary?.latestVisit,
            outingCount: summary?.outingCount ?? 0,
            totalDistanceMiles: summary?.totalDistanceMiles ?? 0,
            totalDurationSeconds: summary?.totalDurationSeconds ?? 0,
            observationCount: summary?.observationCount ?? 0,
            speciesCount: summary?.speciesCount ?? 0,
            taxonCounts: try values.array(TaxonCount.self, "taxonCounts"),
            taxonGroups: try values.array(PlaceTaxonGroup.self, "taxonGroups"),
            seasonalHistory: try values.optionalValue(SeasonalHistory.self, "seasonalHistory") ?? SeasonalHistory(),
            visits: try values.array(PlaceVisit.self, "visits"),
            guidance: values.string("guidance"),
            forecast: try values.optionalValue(PlaceForecast.self, "forecast"),
            riverGauges: try values.array(RiverGaugeSeries.self, "riverGauges"),
            liveConditionsNotice: values.optionalString("liveConditionsNotice")
        )
    }
}

public struct ComparisonSpecies: Codable, Equatable, Sendable {
    public let key: String
    public let taxonId: Int64?
    public let commonName: String
    public let scientificName: String
    public let iconicTaxonName: String
    public let referencePhotoUrl: String

    public init(
        key: String,
        taxonId: Int64?,
        commonName: String,
        scientificName: String,
        iconicTaxonName: String,
        referencePhotoUrl: String
    ) {
        self.key = key
        self.taxonId = taxonId
        self.commonName = commonName
        self.scientificName = scientificName
        self.iconicTaxonName = iconicTaxonName
        self.referencePhotoUrl = referencePhotoUrl
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            key: values.string("key"),
            taxonId: values.optionalInt64("taxonId"),
            commonName: values.string("commonName", default: "Unknown species"),
            scientificName: values.string("scientificName"),
            iconicTaxonName: values.string("iconicTaxonName", default: "Other"),
            referencePhotoUrl: values.string("referencePhotoUrl")
        )
    }
}

public struct ComparisonHike: Codable, Equatable, Sendable {
    public let id: String
    public let title: String
    public let hikeDate: String
    public let locationName: String
    public let distanceMiles: Double?
    public let durationSeconds: Int64?
    public let photoCount: Int
    public let observationCount: Int
    public let speciesCount: Int

    public init(
        id: String = "",
        title: String = "Untitled hike",
        hikeDate: String = "",
        locationName: String = "",
        distanceMiles: Double? = nil,
        durationSeconds: Int64? = nil,
        photoCount: Int = 0,
        observationCount: Int = 0,
        speciesCount: Int = 0
    ) {
        self.id = id
        self.title = title
        self.hikeDate = hikeDate
        self.locationName = locationName
        self.distanceMiles = distanceMiles
        self.durationSeconds = durationSeconds
        self.photoCount = photoCount
        self.observationCount = observationCount
        self.speciesCount = speciesCount
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            id: values.string("id"),
            title: values.string("title", default: "Untitled hike"),
            hikeDate: values.string("hikeDate"),
            locationName: values.string("locationName"),
            distanceMiles: values.optionalDouble("distanceMiles"),
            durationSeconds: values.optionalInt64("durationSeconds"),
            photoCount: values.integer("photoCount"),
            observationCount: values.integer("observationCount"),
            speciesCount: values.integer("speciesCount")
        )
    }
}

private struct ComparisonSpeciesPayload: Decodable {
    let shared: [ComparisonSpecies]
    let onlyA: [ComparisonSpecies]
    let onlyB: [ComparisonSpecies]

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        shared = try values.array(ComparisonSpecies.self, "shared")
        onlyA = try values.array(ComparisonSpecies.self, "onlyA")
        onlyB = try values.array(ComparisonSpecies.self, "onlyB")
    }
}

private struct ComparisonWeatherPayload: Decodable {
    let hikeA: WeatherSnapshot?
    let hikeB: WeatherSnapshot?

    init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        hikeA = try values.optionalValue(WeatherSnapshot.self, "hikeA")
        hikeB = try values.optionalValue(WeatherSnapshot.self, "hikeB")
    }
}

public struct HikeComparison: Codable, Equatable, Sendable {
    public let hikeA: ComparisonHike
    public let hikeB: ComparisonHike
    public let shared: [ComparisonSpecies]
    public let onlyA: [ComparisonSpecies]
    public let onlyB: [ComparisonSpecies]
    public let weatherA: WeatherSnapshot?
    public let weatherB: WeatherSnapshot?
    public let guidance: String

    public init(
        hikeA: ComparisonHike,
        hikeB: ComparisonHike,
        shared: [ComparisonSpecies],
        onlyA: [ComparisonSpecies],
        onlyB: [ComparisonSpecies],
        weatherA: WeatherSnapshot?,
        weatherB: WeatherSnapshot?,
        guidance: String
    ) {
        self.hikeA = hikeA
        self.hikeB = hikeB
        self.shared = shared
        self.onlyA = onlyA
        self.onlyB = onlyB
        self.weatherA = weatherA
        self.weatherB = weatherB
        self.guidance = guidance
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        let species = try values.optionalValue(ComparisonSpeciesPayload.self, "species")
        let weather = try values.optionalValue(ComparisonWeatherPayload.self, "weather")
        self.init(
            hikeA: try values.optionalValue(ComparisonHike.self, "hikeA") ?? ComparisonHike(),
            hikeB: try values.optionalValue(ComparisonHike.self, "hikeB") ?? ComparisonHike(),
            shared: species?.shared ?? [],
            onlyA: species?.onlyA ?? [],
            onlyB: species?.onlyB ?? [],
            weatherA: weather?.hikeA,
            weatherB: weather?.hikeB,
            guidance: values.string("guidance")
        )
    }
}
