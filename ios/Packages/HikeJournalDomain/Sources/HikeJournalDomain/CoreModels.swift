import Foundation

public struct RoutePoint: Codable, Equatable, Sendable {
    public let latitude: Double
    public let longitude: Double

    public init(latitude: Double, longitude: Double) {
        self.latitude = latitude
        self.longitude = longitude
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        latitude = values.double("lat")
        longitude = values.double("lng")
    }

    public func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: DomainKey.self)
        try values.encode(latitude, forKey: DomainKey("lat"))
        try values.encode(longitude, forKey: DomainKey("lng"))
    }
}

public struct MapRoute: Codable, Equatable, Sendable {
    public let hikeId: String
    public let segments: [[RoutePoint]]

    public init(hikeId: String, segments: [[RoutePoint]]) {
        self.hikeId = hikeId
        self.segments = segments.filter { $0.count >= 2 }
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        hikeId = values.string("hikeId")
        let serverSegments = try values.array([RoutePoint].self, "routeSegments")
        let cachedSegments = serverSegments.isEmpty
            ? try values.array([RoutePoint].self, "segments")
            : serverSegments
        segments = cachedSegments.filter { $0.count >= 2 }
    }

    public func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: DomainKey.self)
        try values.encode(hikeId, forKey: DomainKey("hike_id"))
        try values.encode(segments, forKey: DomainKey("route_segments"))
    }
}

public struct WeatherSnapshot: Codable, Equatable, Sendable {
    public let provider: String
    public let providerDataset: String
    public let algorithmVersion: String
    public let intervalStartedAt: String?
    public let intervalEndedAt: String?
    public let temperatureMinC: Double?
    public let temperatureMeanC: Double?
    public let temperatureMaxC: Double?
    public let apparentTemperatureMeanC: Double?
    public let precipitationTotalMm: Double?
    public let relativeHumidityMeanPercent: Double?
    public let cloudCoverMeanPercent: Double?
    public let windSpeedMeanKph: Double?
    public let conditionLabel: String

    public init(
        provider: String = "",
        providerDataset: String = "",
        algorithmVersion: String = "",
        intervalStartedAt: String? = nil,
        intervalEndedAt: String? = nil,
        temperatureMinC: Double? = nil,
        temperatureMeanC: Double? = nil,
        temperatureMaxC: Double? = nil,
        apparentTemperatureMeanC: Double? = nil,
        precipitationTotalMm: Double? = nil,
        relativeHumidityMeanPercent: Double? = nil,
        cloudCoverMeanPercent: Double? = nil,
        windSpeedMeanKph: Double? = nil,
        conditionLabel: String = "Conditions recorded"
    ) {
        self.provider = provider
        self.providerDataset = providerDataset
        self.algorithmVersion = algorithmVersion
        self.intervalStartedAt = intervalStartedAt
        self.intervalEndedAt = intervalEndedAt
        self.temperatureMinC = temperatureMinC
        self.temperatureMeanC = temperatureMeanC
        self.temperatureMaxC = temperatureMaxC
        self.apparentTemperatureMeanC = apparentTemperatureMeanC
        self.precipitationTotalMm = precipitationTotalMm
        self.relativeHumidityMeanPercent = relativeHumidityMeanPercent
        self.cloudCoverMeanPercent = cloudCoverMeanPercent
        self.windSpeedMeanKph = windSpeedMeanKph
        self.conditionLabel = conditionLabel
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            provider: values.string("provider"),
            providerDataset: values.string("providerDataset"),
            algorithmVersion: values.string("algorithmVersion"),
            intervalStartedAt: values.optionalString("intervalStartedAt"),
            intervalEndedAt: values.optionalString("intervalEndedAt"),
            temperatureMinC: values.optionalDouble("temperatureMinC"),
            temperatureMeanC: values.optionalDouble("temperatureMeanC"),
            temperatureMaxC: values.optionalDouble("temperatureMaxC"),
            apparentTemperatureMeanC: values.optionalDouble("apparentTemperatureMeanC"),
            precipitationTotalMm: values.optionalDouble("precipitationTotalMm"),
            relativeHumidityMeanPercent: values.optionalDouble("relativeHumidityMeanPercent"),
            cloudCoverMeanPercent: values.optionalDouble("cloudCoverMeanPercent"),
            windSpeedMeanKph: values.optionalDouble("windSpeedMeanKph"),
            conditionLabel: values.string("conditionLabel", default: "Conditions recorded")
        )
    }
}

public struct ForecastDay: Codable, Equatable, Sendable {
    public let date: String
    public let conditionLabel: String
    public let temperatureMaxF: Double?
    public let temperatureMinF: Double?
    public let apparentTemperatureMaxF: Double?
    public let precipitationProbabilityPercent: Double?
    public let precipitationTotalInches: Double?
    public let windSpeedMaxMph: Double?
    public let windGustMaxMph: Double?
    public let uvIndexMax: Double?
    public let sunrise: String?
    public let sunset: String?

    public init(
        date: String = "",
        conditionLabel: String = "",
        temperatureMaxF: Double? = nil,
        temperatureMinF: Double? = nil,
        apparentTemperatureMaxF: Double? = nil,
        precipitationProbabilityPercent: Double? = nil,
        precipitationTotalInches: Double? = nil,
        windSpeedMaxMph: Double? = nil,
        windGustMaxMph: Double? = nil,
        uvIndexMax: Double? = nil,
        sunrise: String? = nil,
        sunset: String? = nil
    ) {
        self.date = date
        self.conditionLabel = conditionLabel
        self.temperatureMaxF = temperatureMaxF
        self.temperatureMinF = temperatureMinF
        self.apparentTemperatureMaxF = apparentTemperatureMaxF
        self.precipitationProbabilityPercent = precipitationProbabilityPercent
        self.precipitationTotalInches = precipitationTotalInches
        self.windSpeedMaxMph = windSpeedMaxMph
        self.windGustMaxMph = windGustMaxMph
        self.uvIndexMax = uvIndexMax
        self.sunrise = sunrise
        self.sunset = sunset
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            date: values.string("date"),
            conditionLabel: values.string("conditionLabel"),
            temperatureMaxF: values.optionalDouble("temperatureMaxF"),
            temperatureMinF: values.optionalDouble("temperatureMinF"),
            apparentTemperatureMaxF: values.optionalDouble("apparentTemperatureMaxF"),
            precipitationProbabilityPercent: values.optionalDouble("precipitationProbabilityPercent"),
            precipitationTotalInches: values.optionalDouble("precipitationTotalInches"),
            windSpeedMaxMph: values.optionalDouble("windSpeedMaxMph"),
            windGustMaxMph: values.optionalDouble("windGustMaxMph"),
            uvIndexMax: values.optionalDouble("uvIndexMax"),
            sunrise: values.optionalString("sunrise"),
            sunset: values.optionalString("sunset")
        )
    }
}

public struct PlaceForecast: Codable, Equatable, Sendable {
    public let observedAt: String?
    public let timezone: String
    public let temperatureF: Double?
    public let apparentTemperatureF: Double?
    public let relativeHumidityPercent: Double?
    public let precipitationInches: Double?
    public let cloudCoverPercent: Double?
    public let windSpeedMph: Double?
    public let windGustMph: Double?
    public let conditionLabel: String
    public let days: [ForecastDay]
    public let planningNotes: [String]

    public init(
        observedAt: String? = nil,
        timezone: String = "",
        temperatureF: Double? = nil,
        apparentTemperatureF: Double? = nil,
        relativeHumidityPercent: Double? = nil,
        precipitationInches: Double? = nil,
        cloudCoverPercent: Double? = nil,
        windSpeedMph: Double? = nil,
        windGustMph: Double? = nil,
        conditionLabel: String = "",
        days: [ForecastDay] = [],
        planningNotes: [String] = []
    ) {
        self.observedAt = observedAt
        self.timezone = timezone
        self.temperatureF = temperatureF
        self.apparentTemperatureF = apparentTemperatureF
        self.relativeHumidityPercent = relativeHumidityPercent
        self.precipitationInches = precipitationInches
        self.cloudCoverPercent = cloudCoverPercent
        self.windSpeedMph = windSpeedMph
        self.windGustMph = windGustMph
        self.conditionLabel = conditionLabel
        self.days = days
        self.planningNotes = planningNotes
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            observedAt: values.optionalString("observedAt"),
            timezone: values.string("timezone"),
            temperatureF: values.optionalDouble("temperatureF"),
            apparentTemperatureF: values.optionalDouble("apparentTemperatureF"),
            relativeHumidityPercent: values.optionalDouble("relativeHumidityPercent"),
            precipitationInches: values.optionalDouble("precipitationInches"),
            cloudCoverPercent: values.optionalDouble("cloudCoverPercent"),
            windSpeedMph: values.optionalDouble("windSpeedMph"),
            windGustMph: values.optionalDouble("windGustMph"),
            conditionLabel: values.string("conditionLabel"),
            days: try values.array(ForecastDay.self, "days"),
            planningNotes: try values.array(String.self, "planningNotes")
        )
    }
}

public struct RiverGauge: Codable, Equatable, Sendable {
    public let siteId: String
    public let name: String
    public let latitude: Double
    public let longitude: Double
    public let enabled: Bool
    public let suggested: Bool

    public init(
        siteId: String,
        name: String,
        latitude: Double,
        longitude: Double,
        enabled: Bool = false,
        suggested: Bool = false
    ) {
        self.siteId = siteId
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.enabled = enabled
        self.suggested = suggested
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            siteId: values.string("siteId"),
            name: values.string("name", default: "USGS water gauge"),
            latitude: values.double("lat"),
            longitude: values.double("lng"),
            enabled: values.boolean("enabled"),
            suggested: values.boolean("suggested")
        )
    }
}

public struct NearbyRiverGauge: Codable, Equatable, Sendable {
    public let gauge: RiverGauge
    public let distanceMiles: Double
    public let currentHeightFeet: Double
    public let observedAt: String
    public let provisional: Bool

    public init(
        gauge: RiverGauge,
        distanceMiles: Double,
        currentHeightFeet: Double,
        observedAt: String,
        provisional: Bool
    ) {
        self.gauge = gauge
        self.distanceMiles = distanceMiles
        self.currentHeightFeet = currentHeightFeet
        self.observedAt = observedAt
        self.provisional = provisional
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            gauge: try values.value(RiverGauge.self, "gauge"),
            distanceMiles: values.double("distanceMiles"),
            currentHeightFeet: values.double("currentHeightFeet"),
            observedAt: values.string("observedAt"),
            provisional: values.boolean("provisional")
        )
    }
}

public struct RiverGaugeReading: Codable, Equatable, Sendable {
    public let observedAt: String
    public let heightFeet: Double
    public let provisional: Bool

    public init(observedAt: String, heightFeet: Double, provisional: Bool) {
        self.observedAt = observedAt
        self.heightFeet = heightFeet
        self.provisional = provisional
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            observedAt: values.string("observedAt"),
            heightFeet: values.double("heightFeet"),
            provisional: values.boolean("provisional")
        )
    }
}

public struct RiverGaugeSeries: Codable, Equatable, Sendable {
    public let gauge: RiverGauge
    public let periodDays: Int
    public let readings: [RiverGaugeReading]
    public let distanceMiles: Double?
    public let errorMessage: String?

    public init(
        gauge: RiverGauge,
        periodDays: Int,
        readings: [RiverGaugeReading],
        distanceMiles: Double? = nil,
        errorMessage: String? = nil
    ) {
        self.gauge = gauge
        self.periodDays = periodDays
        self.readings = readings
        self.distanceMiles = distanceMiles
        self.errorMessage = errorMessage
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            gauge: try values.value(RiverGauge.self, "gauge"),
            periodDays: values.integer("periodDays"),
            readings: try values.array(RiverGaugeReading.self, "readings"),
            distanceMiles: values.optionalDouble("distanceMiles"),
            errorMessage: values.optionalString("errorMessage")
        )
    }

    public var currentHeightFeet: Double? { readings.last?.heightFeet }
    public var observedAt: String? { readings.last?.observedAt }
    public var minimumHeightFeet: Double? { readings.map(\.heightFeet).min() }
    public var maximumHeightFeet: Double? { readings.map(\.heightFeet).max() }
    public var changeFeet: Double? {
        guard let first = readings.first, let last = readings.last, readings.count >= 2 else {
            return nil
        }
        return last.heightFeet - first.heightFeet
    }
}

public struct PlaceConditions: Codable, Equatable, Sendable {
    public let forecast: PlaceForecast?
    public let riverGauges: [RiverGaugeSeries]
    public let liveConditionsNotice: String?

    public init(
        forecast: PlaceForecast? = nil,
        riverGauges: [RiverGaugeSeries] = [],
        liveConditionsNotice: String? = nil
    ) {
        self.forecast = forecast
        self.riverGauges = riverGauges
        self.liveConditionsNotice = liveConditionsNotice
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            forecast: try values.optionalValue(PlaceForecast.self, "forecast"),
            riverGauges: try values.array(RiverGaugeSeries.self, "riverGauges"),
            liveConditionsNotice: values.optionalString("liveConditionsNotice")
        )
    }
}

public struct IdentificationEvent: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let commonName: String
    public let scientificName: String
    public let source: String
    public let confidence: String
    public let actor: String
    public let note: String
    public let becameCurrent: Bool
    public let createdAt: String?

    public init(
        id: String = "",
        commonName: String = "",
        scientificName: String = "",
        source: String = "legacy_import",
        confidence: String = "tentative",
        actor: String = "",
        note: String = "",
        becameCurrent: Bool = false,
        createdAt: String? = nil
    ) {
        self.id = id
        self.commonName = commonName
        self.scientificName = scientificName
        self.source = source
        self.confidence = confidence
        self.actor = actor
        self.note = note
        self.becameCurrent = becameCurrent
        self.createdAt = createdAt
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            id: values.string("id"),
            commonName: values.string("commonName"),
            scientificName: values.string("scientificName"),
            source: values.string("source", default: "legacy_import"),
            confidence: values.string("confidence", default: "tentative"),
            actor: values.string("actor"),
            note: values.string("note"),
            becameCurrent: values.boolean("becameCurrent"),
            createdAt: values.optionalString("createdAt")
        )
    }
}

private struct PhenophaseValue: Decodable {
    let code: String

    init(from decoder: Decoder) throws {
        if let value = try? decoder.singleValueContainer().decode(String.self) {
            code = value
            return
        }
        let values = try decoder.domainContainer()
        code = values.string("code")
    }
}

public struct SpeciesLabel: Codable, Equatable, Sendable {
    public let commonName: String
    public let scientificName: String
    public let status: String
    public let isPrimary: Bool
    public let taxonId: Int64?
    public let wikipediaUrl: String
    public let wikipediaSummary: String
    public let observationId: String?
    public let confidence: String
    public let provenance: String
    public let observedOn: String?
    public let phenophases: [String]
    public let identificationHistory: [IdentificationEvent]
    public let iconicTaxonName: String

    public init(
        commonName: String = "",
        scientificName: String = "",
        status: String = "",
        isPrimary: Bool = false,
        taxonId: Int64? = nil,
        wikipediaUrl: String = "",
        wikipediaSummary: String = "",
        observationId: String? = nil,
        confidence: String = "tentative",
        provenance: String = "legacy_import",
        observedOn: String? = nil,
        phenophases: [String] = [],
        identificationHistory: [IdentificationEvent] = [],
        iconicTaxonName: String = ""
    ) {
        self.commonName = commonName
        self.scientificName = scientificName
        self.status = status
        self.isPrimary = isPrimary
        self.taxonId = taxonId
        self.wikipediaUrl = wikipediaUrl
        self.wikipediaSummary = wikipediaSummary
        self.observationId = observationId
        self.confidence = confidence
        self.provenance = provenance
        self.observedOn = observedOn
        self.phenophases = phenophases
        self.identificationHistory = identificationHistory
        self.iconicTaxonName = iconicTaxonName
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        let phenophaseValues = try values.array(PhenophaseValue.self, "phenophases")
        self.init(
            commonName: values.string("commonName"),
            scientificName: values.string("scientificName"),
            status: values.string("status"),
            isPrimary: values.boolean("isPrimary"),
            taxonId: values.optionalInt64("taxonId"),
            wikipediaUrl: values.string("wikipediaUrl"),
            wikipediaSummary: plainWikipediaSummary(values.string("wikipediaSummary")),
            observationId: values.optionalString("observationId"),
            confidence: values.string("confidence", default: "tentative"),
            provenance: values.string("provenance", default: "legacy_import"),
            observedOn: values.optionalString("observedOn"),
            phenophases: phenophaseValues.map(\.code).filter { !$0.domainTrimmed.isEmpty },
            identificationHistory: try values.array(IdentificationEvent.self, "identificationHistory"),
            iconicTaxonName: values.string("iconicTaxonName")
        )
    }
}

public struct Photo: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let hikeId: String?
    public let url: String
    public let caption: String
    public let takenAt: String?
    public let createdAt: String?
    public let latitude: Double?
    public let longitude: Double?
    public let width: Int?
    public let height: Int?
    public let contentType: String
    public let processingStatus: String
    public let syncState: String
    public let species: [SpeciesLabel]

    public init(
        id: String,
        hikeId: String?,
        url: String,
        caption: String,
        takenAt: String?,
        createdAt: String?,
        latitude: Double?,
        longitude: Double?,
        width: Int?,
        height: Int?,
        contentType: String,
        processingStatus: String,
        syncState: String = "synced",
        species: [SpeciesLabel]
    ) {
        self.id = id
        self.hikeId = hikeId
        self.url = url
        self.caption = caption
        self.takenAt = takenAt
        self.createdAt = createdAt
        self.latitude = latitude
        self.longitude = longitude
        self.width = width
        self.height = height
        self.contentType = contentType
        self.processingStatus = processingStatus
        self.syncState = syncState
        self.species = species
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            id: values.string("id"),
            hikeId: values.optionalString("hikeId"),
            url: values.string("url"),
            caption: values.string("caption"),
            takenAt: values.optionalString("takenAt"),
            createdAt: values.optionalString("createdAt"),
            latitude: values.optionalDouble("lat"),
            longitude: values.optionalDouble("lng"),
            width: values.optionalInteger("width"),
            height: values.optionalInteger("height"),
            contentType: values.string("contentType", default: "image/jpeg"),
            processingStatus: values.string("processingStatus", default: "ready"),
            syncState: values.string("syncState", default: "synced"),
            species: try values.array(SpeciesLabel.self, "species")
        )
    }

    public func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: DomainKey.self)
        try values.encode(id, forKey: DomainKey("id"))
        try values.encodeIfPresent(hikeId, forKey: DomainKey("hike_id"))
        try values.encode(url, forKey: DomainKey("url"))
        try values.encode(caption, forKey: DomainKey("caption"))
        try values.encodeIfPresent(takenAt, forKey: DomainKey("taken_at"))
        try values.encodeIfPresent(createdAt, forKey: DomainKey("created_at"))
        try values.encodeIfPresent(latitude, forKey: DomainKey("lat"))
        try values.encodeIfPresent(longitude, forKey: DomainKey("lng"))
        try values.encodeIfPresent(width, forKey: DomainKey("width"))
        try values.encodeIfPresent(height, forKey: DomainKey("height"))
        try values.encode(contentType, forKey: DomainKey("content_type"))
        try values.encode(processingStatus, forKey: DomainKey("processing_status"))
        try values.encode(syncState, forKey: DomainKey("sync_state"))
        try values.encode(species, forKey: DomainKey("species"))
    }
}

public struct FieldMark: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let hikeId: String
    public let recordingSessionId: String?
    public let markedAt: String
    public let latitude: Double
    public let longitude: Double
    public let accuracyMeters: Double?
    public let markType: String
    public let note: String
    public let syncState: String

    public init(
        id: String,
        hikeId: String,
        recordingSessionId: String?,
        markedAt: String,
        latitude: Double,
        longitude: Double,
        accuracyMeters: Double?,
        markType: String,
        note: String,
        syncState: String = "synced"
    ) {
        self.id = id
        self.hikeId = hikeId
        self.recordingSessionId = recordingSessionId
        self.markedAt = markedAt
        self.latitude = latitude
        self.longitude = longitude
        self.accuracyMeters = accuracyMeters
        self.markType = markType
        self.note = note
        self.syncState = syncState
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            id: values.string("id"),
            hikeId: values.string("hikeId"),
            recordingSessionId: values.optionalString("recordingSessionId"),
            markedAt: values.string("markedAt"),
            latitude: values.double("lat"),
            longitude: values.double("lng"),
            accuracyMeters: values.optionalDouble("accuracyMeters"),
            markType: values.string("markType", default: "note"),
            note: values.string("note"),
            syncState: values.string("syncState", default: "synced")
        )
    }
}

public struct Hike: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let title: String
    public let hikeDate: String
    public let distanceMiles: Double?
    public let durationSeconds: Int64?
    public let routeStartedAt: String?
    public let locationName: String
    public let notes: String
    public let isArchived: Bool
    public let isStandalone: Bool
    public let coverUrl: String
    public let coverPhotoId: String?
    public let photoCount: Int
    public let speciesCount: Int
    public let syncState: String
    public let photos: [Photo]
    public let routeSegments: [[RoutePoint]]
    public let primaryLocationId: String?
    public let primaryLocationName: String
    public let fieldMarks: [FieldMark]
    public let weather: WeatherSnapshot?

    public init(
        id: String,
        title: String,
        hikeDate: String,
        distanceMiles: Double?,
        durationSeconds: Int64? = nil,
        routeStartedAt: String? = nil,
        locationName: String,
        notes: String,
        isArchived: Bool,
        isStandalone: Bool = false,
        coverUrl: String,
        coverPhotoId: String? = nil,
        photoCount: Int,
        speciesCount: Int,
        syncState: String = "synced",
        photos: [Photo] = [],
        routeSegments: [[RoutePoint]] = [],
        primaryLocationId: String? = nil,
        primaryLocationName: String = "",
        fieldMarks: [FieldMark] = [],
        weather: WeatherSnapshot? = nil
    ) {
        self.id = id
        self.title = title
        self.hikeDate = hikeDate
        self.distanceMiles = distanceMiles
        self.durationSeconds = durationSeconds
        self.routeStartedAt = routeStartedAt
        self.locationName = locationName
        self.notes = notes
        self.isArchived = isArchived
        self.isStandalone = isStandalone
        self.coverUrl = coverUrl
        self.coverPhotoId = coverPhotoId
        self.photoCount = photoCount
        self.speciesCount = speciesCount
        self.syncState = syncState
        self.photos = photos
        self.routeSegments = routeSegments.filter { $0.count >= 2 }
        self.primaryLocationId = primaryLocationId
        self.primaryLocationName = primaryLocationName
        self.fieldMarks = fieldMarks
        self.weather = weather
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            id: values.string("id"),
            title: values.string("title", default: "Untitled hike"),
            hikeDate: values.string("hikeDate"),
            distanceMiles: values.optionalDouble("distanceMiles"),
            durationSeconds: values.optionalInt64("durationSeconds"),
            routeStartedAt: values.optionalString("routeStartedAt") ?? values.optionalString("startedAt"),
            locationName: values.string("locationName"),
            notes: values.string("notes"),
            isArchived: values.boolean("isArchived"),
            isStandalone: values.boolean("isStandalone"),
            coverUrl: values.string("coverUrl"),
            coverPhotoId: values.optionalString("coverPhotoId"),
            photoCount: values.integer("photoCount"),
            speciesCount: values.integer("speciesCount"),
            syncState: values.string("syncState", default: "synced"),
            photos: try values.array(Photo.self, "photos"),
            routeSegments: try values.array([RoutePoint].self, "routeSegments"),
            primaryLocationId: values.optionalString("primaryLocationId"),
            primaryLocationName: values.string("primaryLocationName"),
            fieldMarks: try values.array(FieldMark.self, "fieldMarks"),
            weather: try values.optionalValue(WeatherSnapshot.self, "weather")
        )
    }
}

public struct MediaLocationSummary: Codable, Equatable, Sendable {
    public let totalCount: Int
    public let geotaggedCount: Int

    public init(totalCount: Int, geotaggedCount: Int) {
        self.totalCount = totalCount
        self.geotaggedCount = geotaggedCount
    }

    public var missingCount: Int { max(0, totalCount - geotaggedCount) }
    public var allGeotagged: Bool { totalCount > 0 && missingCount == 0 }
}

public struct HikeDraft: Codable, Equatable, Sendable {
    public let title: String
    public let hikeDate: String
    public let distanceMiles: Double?
    public let locationName: String
    public let notes: String
    public let locationId: String?

    public init(
        title: String,
        hikeDate: String,
        distanceMiles: Double?,
        locationName: String,
        notes: String,
        locationId: String? = nil
    ) {
        self.title = title
        self.hikeDate = hikeDate
        self.distanceMiles = distanceMiles
        self.locationName = locationName
        self.notes = notes
        self.locationId = locationId
    }
}

public struct USState: Codable, Equatable, Sendable {
    public let code: String
    public let name: String

    public init(code: String, name: String) {
        self.code = code
        self.name = name
    }
}

public let unitedStates: [USState] = [
    ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"),
    ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"),
    ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"), ("ID", "Idaho"),
    ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"), ("KS", "Kansas"),
    ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"), ("MD", "Maryland"),
    ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"), ("MS", "Mississippi"),
    ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"), ("NV", "Nevada"),
    ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"), ("NY", "New York"),
    ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"), ("OK", "Oklahoma"),
    ("OR", "Oregon"), ("PA", "Pennsylvania"), ("RI", "Rhode Island"), ("SC", "South Carolina"),
    ("SD", "South Dakota"), ("TN", "Tennessee"), ("TX", "Texas"), ("UT", "Utah"),
    ("VT", "Vermont"), ("VA", "Virginia"), ("WA", "Washington"), ("WV", "West Virginia"),
    ("WI", "Wisconsin"), ("WY", "Wyoming"),
].map { USState(code: $0.0, name: $0.1) }

public func normalizeUSStateCode(_ value: String?) -> String? {
    let normalized = value?.domainTrimmed.uppercased(with: Locale(identifier: "en_US_POSIX")) ?? ""
    return unitedStates.contains { $0.code == normalized } ? normalized : nil
}

public func usStateCode(forName value: String?) -> String? {
    let normalized = value?.domainTrimmed ?? ""
    return unitedStates.first {
        $0.code.caseInsensitiveCompare(normalized) == .orderedSame
            || $0.name.caseInsensitiveCompare(normalized) == .orderedSame
    }?.code
}

public struct HikeLocation: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let name: String
    public let latitude: Double?
    public let longitude: Double?
    public let isUserPlace: Bool
    public let stateCode: String?

    public init(
        id: String,
        name: String,
        latitude: Double? = nil,
        longitude: Double? = nil,
        isUserPlace: Bool = false,
        stateCode: String? = nil
    ) {
        self.id = id
        self.name = name
        self.latitude = validLatitude(latitude)
        self.longitude = validLongitude(longitude)
        self.isUserPlace = isUserPlace
        self.stateCode = normalizeUSStateCode(stateCode)
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.domainContainer()
        self.init(
            id: values.string("id"),
            name: values.string("name"),
            latitude: values.optionalDouble("lat"),
            longitude: values.optionalDouble("lng"),
            isUserPlace: values.boolean("isUserPlace"),
            stateCode: values.optionalString("state")
        )
    }
}
