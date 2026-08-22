import Foundation

public enum ObservationTypeFilter: String, Codable, CaseIterable, Equatable, Sendable {
    case all = "All"
    case plants = "Plants"
    case animals = "Animals"
    case birds = "Birds"
    case mammals = "Mammals"
    case insects = "Insects"
    case reptiles = "Reptiles"
    case amphibians = "Amphibians"
    case arachnids = "Arachnids"
    case fungi = "Fungi"
    case fish = "Fish"
    case mollusks = "Mollusks"
    case otherLife = "OtherLife"

    public var label: String {
        switch self {
        case .all: "All types"
        case .plants: "Plants"
        case .animals: "Animals"
        case .birds: "Birds"
        case .mammals: "Mammals"
        case .insects: "Insects"
        case .reptiles: "Reptiles"
        case .amphibians: "Amphibians"
        case .arachnids: "Arachnids"
        case .fungi: "Fungi"
        case .fish: "Fish"
        case .mollusks: "Mollusks"
        case .otherLife: "Other life"
        }
    }
}

private let animalIconicTaxa: Set<String> = [
    "animalia", "aves", "mammalia", "insecta", "reptilia", "amphibia",
    "arachnida", "actinopterygii", "mollusca",
]

private let knownIconicTaxa = animalIconicTaxa.union(["plantae", "fungi"])

public func iconicTaxonMatchesObservationType(
    _ iconicTaxonName: String,
    filter: ObservationTypeFilter
) -> Bool {
    let iconicTaxon = iconicTaxonName.domainFolded
    switch filter {
    case .all: return true
    case .plants: return iconicTaxon == "plantae"
    case .animals: return animalIconicTaxa.contains(iconicTaxon)
    case .birds: return iconicTaxon == "aves"
    case .mammals: return iconicTaxon == "mammalia"
    case .insects: return iconicTaxon == "insecta"
    case .reptiles: return iconicTaxon == "reptilia"
    case .amphibians: return iconicTaxon == "amphibia"
    case .arachnids: return iconicTaxon == "arachnida"
    case .fungi: return iconicTaxon == "fungi"
    case .fish: return iconicTaxon == "actinopterygii"
    case .mollusks: return iconicTaxon == "mollusca"
    case .otherLife: return !knownIconicTaxa.contains(iconicTaxon)
    }
}

public extension SpeciesRecord {
    func matchesObservationType(_ filter: ObservationTypeFilter) -> Bool {
        iconicTaxonMatchesObservationType(iconicTaxonName, filter: filter)
    }
}

public func filterSpeciesByObservationType(
    _ species: [SpeciesRecord],
    filter: ObservationTypeFilter
) -> [SpeciesRecord] {
    filter == .all ? species : species.filter { $0.matchesObservationType(filter) }
}

public enum SpeciesSort: String, Codable, CaseIterable, Equatable, Sendable {
    case alphabetical = "Alphabetical"
    case mostEncountered = "MostEncountered"
    case mostRecent = "MostRecent"

    public var label: String {
        switch self {
        case .alphabetical: "Alphabetical"
        case .mostEncountered: "Most encountered"
        case .mostRecent: "Most recent"
        }
    }
}

func observedDate(_ value: String?) -> Date? {
    guard let raw = value?.domainTrimmed, !raw.isEmpty else { return nil }

    let internet = ISO8601DateFormatter()
    internet.formatOptions = [.withInternetDateTime, .withColonSeparatorInTimeZone]
    if let value = internet.date(from: raw) { return value }
    internet.formatOptions = [
        .withInternetDateTime,
        .withColonSeparatorInTimeZone,
        .withFractionalSeconds,
    ]
    if let value = internet.date(from: raw) { return value }

    if raw.contains("T") {
        internet.formatOptions = [.withInternetDateTime]
        if let value = internet.date(from: raw + "Z") { return value }
        internet.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let value = internet.date(from: raw + "Z") { return value }
    }

    guard raw.count == 10 else { return nil }
    let formatter = DateFormatter()
    formatter.calendar = Calendar(identifier: .gregorian)
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.timeZone = TimeZone(secondsFromGMT: 0)
    formatter.dateFormat = "yyyy-MM-dd"
    formatter.isLenient = false
    return formatter.date(from: raw)
}

public func latestObservedValue<Values: Sequence>(_ values: Values) -> String?
where Values.Element == String {
    var best: (value: String, date: Date?)?
    for value in values {
        let date = observedDate(value)
        guard let current = best else {
            best = (value, date)
            continue
        }
        switch (date, current.date) {
        case let (candidate?, existing?) where candidate > existing:
            best = (value, date)
        case (_?, nil):
            best = (value, date)
        default:
            break
        }
    }
    return best?.value
}

private func alphabeticalSpeciesOrder(_ left: SpeciesRecord, _ right: SpeciesRecord) -> Bool {
    let leftValues = [left.commonName.domainFolded, left.scientificName.domainFolded, left.key.domainFolded]
    let rightValues = [right.commonName.domainFolded, right.scientificName.domainFolded, right.key.domainFolded]
    for (leftValue, rightValue) in zip(leftValues, rightValues) where leftValue != rightValue {
        return leftValue < rightValue
    }
    return false
}

public func sortSpeciesRecords(_ species: [SpeciesRecord], by sort: SpeciesSort) -> [SpeciesRecord] {
    species.sorted { left, right in
        switch sort {
        case .alphabetical:
            return alphabeticalSpeciesOrder(left, right)
        case .mostEncountered:
            if left.encounterCount != right.encounterCount {
                return left.encounterCount > right.encounterCount
            }
            return alphabeticalSpeciesOrder(left, right)
        case .mostRecent:
            let leftDate = observedDate(left.latestSeen)
            let rightDate = observedDate(right.latestSeen)
            switch (leftDate, rightDate) {
            case let (leftDate?, rightDate?) where leftDate != rightDate:
                return leftDate > rightDate
            case (_?, nil):
                return true
            case (nil, _?):
                return false
            default:
                return alphabeticalSpeciesOrder(left, right)
            }
        }
    }
}

public func filterHikesForSelection(_ hikes: [Hike], query: String) -> [Hike] {
    let query = query.domainTrimmed
    return hikes.filter { hike in
        query.isEmpty
            || hike.title.range(of: query, options: [.caseInsensitive, .diacriticInsensitive]) != nil
            || hike.locationName.range(of: query, options: [.caseInsensitive, .diacriticInsensitive]) != nil
            || hike.hikeDate.range(of: query, options: [.caseInsensitive]) != nil
    }.sorted { left, right in
        if left.hikeDate != right.hikeDate { return left.hikeDate > right.hikeDate }
        return left.title.domainFolded < right.title.domainFolded
    }
}

public func formatHikeFilterDate(_ raw: String) -> String {
    guard raw.count >= 10, let date = observedDate(String(raw.prefix(10))) else { return raw }
    let formatter = DateFormatter()
    formatter.calendar = Calendar(identifier: .gregorian)
    formatter.locale = Locale(identifier: "en_US")
    formatter.timeZone = TimeZone(secondsFromGMT: 0)
    formatter.dateFormat = "MMM d, yyyy"
    return formatter.string(from: date)
}
