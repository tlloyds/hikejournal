import Foundation

public enum BadgeCategory: String, Codable, CaseIterable, Equatable, Sendable {
    case hiking = "Hiking"
    case distance = "Distance"
    case quests = "Quests"
    case fieldGuide = "FieldGuide"
    case specialties = "Specialties"

    public var label: String {
        switch self {
        case .hiking: "Hiking"
        case .distance: "Distance"
        case .quests: "Field quests"
        case .fieldGuide: "Field guide"
        case .specialties: "Specialties"
        }
    }

    public var description: String {
        switch self {
        case .hiking: "Milestones for showing up, season after season."
        case .distance: "Lifetime miles and the days that went farther."
        case .quests: "Completed targets and less-often-reported finds."
        case .fieldGuide: "New species added to your personal archive."
        case .specialties: "Deeper knowledge across the living world."
        }
    }
}

public enum BadgeFinish: String, Codable, CaseIterable, Equatable, Sendable {
    case bronze = "Bronze"
    case silver = "Silver"
    case gold = "Gold"
    case evergreen = "Evergreen"
}

public enum BadgeSymbol: String, Codable, CaseIterable, Equatable, Sendable {
    case boot = "Boot"
    case mountain = "Mountain"
    case route = "Route"
    case flag = "Flag"
    case rare = "Rare"
    case compass = "Compass"
    case plant = "Plant"
    case mammal = "Mammal"
    case fungi = "Fungi"
    case bird = "Bird"
    case insect = "Insect"
}

public enum BadgeMetric: String, Codable, CaseIterable, Equatable, Sendable {
    case hikeCount = "HikeCount"
    case totalMiles = "TotalMiles"
    case longestHike = "LongestHike"
    case completedQuests = "CompletedQuests"
    case rareFinds = "RareFinds"
    case speciesCount = "SpeciesCount"
    case plants = "Plants"
    case mammals = "Mammals"
    case fungi = "Fungi"
    case birds = "Birds"
    case insects = "Insects"
}

public struct TrailBadgeDefinition: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let title: String
    public let requirement: String
    public let category: BadgeCategory
    public let metric: BadgeMetric
    public let target: Double
    public let finish: BadgeFinish
    public let symbol: BadgeSymbol

    public init(
        id: String,
        title: String,
        requirement: String,
        category: BadgeCategory,
        metric: BadgeMetric,
        target: Double,
        finish: BadgeFinish,
        symbol: BadgeSymbol
    ) {
        self.id = id
        self.title = title
        self.requirement = requirement
        self.category = category
        self.metric = metric
        self.target = target
        self.finish = finish
        self.symbol = symbol
    }
}

public struct TrailBadge: Codable, Equatable, Sendable, Identifiable {
    public var id: String { definition.id }
    public let definition: TrailBadgeDefinition
    public let current: Double

    public init(definition: TrailBadgeDefinition, current: Double) {
        self.definition = definition
        self.current = current
    }

    public var earned: Bool { current >= definition.target }
    public var progress: Float {
        guard definition.target > 0 else { return earned ? 1 : 0 }
        return Float(min(1, max(0, current / definition.target)))
    }
}

public struct SpeciesTypeCounts: Codable, Equatable, Sendable {
    public let total: Int
    public let plants: Int
    public let animals: Int
    public let mammals: Int
    public let birds: Int
    public let insects: Int
    public let fungi: Int

    public init(
        total: Int,
        plants: Int,
        animals: Int,
        mammals: Int,
        birds: Int,
        insects: Int,
        fungi: Int
    ) {
        self.total = total
        self.plants = plants
        self.animals = animals
        self.mammals = mammals
        self.birds = birds
        self.insects = insects
        self.fungi = fungi
    }
}

public func speciesTypeCounts(_ species: [SpeciesRecord]) -> SpeciesTypeCounts {
    let distinctSpecies = distinctSpeciesRecords(species)
    func count(_ names: Set<String>) -> Int {
        distinctSpecies.count { names.contains($0.iconicTaxonName.domainFolded) }
    }
    let animalTaxa: Set<String> = [
        "animalia", "metazoa", "mammalia", "mammal", "aves", "bird",
        "insecta", "insect", "amphibia", "reptilia", "actinopterygii",
        "arachnida", "mollusca", "crustacea", "annelida", "cnidaria",
        "echinodermata",
    ]
    return SpeciesTypeCounts(
        total: distinctSpecies.count,
        plants: count(["plantae", "plant"]),
        animals: count(animalTaxa),
        mammals: count(["mammalia", "mammal"]),
        birds: count(["aves", "bird"]),
        insects: count(["insecta", "insect"]),
        fungi: count(["fungi", "fungus"])
    )
}

private func badge(
    _ id: String,
    _ title: String,
    _ requirement: String,
    _ category: BadgeCategory,
    _ metric: BadgeMetric,
    _ target: Double,
    _ finish: BadgeFinish,
    _ symbol: BadgeSymbol
) -> TrailBadgeDefinition {
    TrailBadgeDefinition(
        id: id,
        title: title,
        requirement: requirement,
        category: category,
        metric: metric,
        target: target,
        finish: finish,
        symbol: symbol
    )
}

public let trailBadgeCatalog: [TrailBadgeDefinition] = [
    badge("hikes_1", "First Footfall", "Log your first hike.", .hiking, .hikeCount, 1, .bronze, .boot),
    badge("hikes_5", "Five Trails", "Log 5 hikes.", .hiking, .hikeCount, 5, .bronze, .boot),
    badge("hikes_10", "Trail Regular", "Log 10 hikes.", .hiking, .hikeCount, 10, .silver, .boot),
    badge("hikes_25", "Seasoned Trekker", "Log 25 hikes.", .hiking, .hikeCount, 25, .gold, .mountain),
    badge("hikes_50", "Half-Century Hiker", "Log 50 hikes.", .hiking, .hikeCount, 50, .gold, .mountain),
    badge("hikes_100", "Hundred Horizons", "Log 100 hikes.", .hiking, .hikeCount, 100, .evergreen, .mountain),

    badge("miles_25", "First 25", "Record 25 lifetime miles.", .distance, .totalMiles, 25, .bronze, .route),
    badge("miles_100", "Century Afoot", "Record 100 lifetime miles.", .distance, .totalMiles, 100, .silver, .route),
    badge("miles_250", "Long Way Home", "Record 250 lifetime miles.", .distance, .totalMiles, 250, .gold, .route),
    badge("miles_500", "Ridgeline 500", "Record 500 lifetime miles.", .distance, .totalMiles, 500, .gold, .route),
    badge("miles_1000", "Thousand-Mile Journal", "Record 1,000 lifetime miles.", .distance, .totalMiles, 1000, .evergreen, .route),
    badge("long_hike_10", "Double Digits", "Complete a hike of at least 10 miles.", .distance, .longestHike, 10, .silver, .mountain),
    badge("long_hike_20", "Endurance Day", "Complete a hike of at least 20 miles.", .distance, .longestHike, 20, .evergreen, .mountain),

    badge("quests_1", "Quest Complete", "Complete every focus find in 1 Field Quest.", .quests, .completedQuests, 1, .bronze, .flag),
    badge("quests_5", "Field Proven", "Complete 5 Field Quests.", .quests, .completedQuests, 5, .gold, .flag),
    badge("quests_10", "Quest Naturalist", "Complete 10 Field Quests.", .quests, .completedQuests, 10, .evergreen, .flag),
    badge("rare_1", "Rare Find", "Log 1 quest species marked less often reported.", .quests, .rareFinds, 1, .silver, .rare),
    badge("rare_5", "Rare Company", "Log 5 distinct less-often-reported quest species.", .quests, .rareFinds, 5, .gold, .rare),

    badge("species_1", "New Find", "Add your first species to the Field Guide.", .fieldGuide, .speciesCount, 1, .bronze, .compass),
    badge("species_25", "Curious Naturalist", "Log 25 distinct species.", .fieldGuide, .speciesCount, 25, .bronze, .compass),
    badge("species_50", "Field Naturalist", "Log 50 distinct species.", .fieldGuide, .speciesCount, 50, .silver, .compass),
    badge("species_100", "Century of Life", "Log 100 distinct species.", .fieldGuide, .speciesCount, 100, .gold, .compass),
    badge("species_250", "Living Archive", "Log 250 distinct species.", .fieldGuide, .speciesCount, 250, .evergreen, .compass),

    badge("plants_25", "Leaf Scout", "Log 25 distinct plants.", .specialties, .plants, 25, .bronze, .plant),
    badge("plants_50", "Field Botanist", "Log 50 distinct plants.", .specialties, .plants, 50, .silver, .plant),
    badge("plants_100", "Flora Authority", "Log 100 distinct plants.", .specialties, .plants, 100, .evergreen, .plant),
    badge("mammals_25", "Mammal Tracker", "Log 25 distinct mammals.", .specialties, .mammals, 25, .bronze, .mammal),
    badge("mammals_50", "Wildlife Observer", "Log 50 distinct mammals.", .specialties, .mammals, 50, .silver, .mammal),
    badge("mammals_100", "Mammal Steward", "Log 100 distinct mammals.", .specialties, .mammals, 100, .evergreen, .mammal),
    badge("fungi_25", "Mycology Scout", "Log 25 distinct fungi.", .specialties, .fungi, 25, .bronze, .fungi),
    badge("fungi_50", "Field Mycologist", "Log 50 distinct fungi.", .specialties, .fungi, 50, .silver, .fungi),
    badge("fungi_100", "Fungi Authority", "Log 100 distinct fungi.", .specialties, .fungi, 100, .evergreen, .fungi),
    badge("birds_25", "Bird Listener", "Log 25 distinct birds.", .specialties, .birds, 25, .bronze, .bird),
    badge("birds_50", "Avian Observer", "Log 50 distinct birds.", .specialties, .birds, 50, .gold, .bird),
    badge("insects_25", "Insect Eye", "Log 25 distinct insects.", .specialties, .insects, 25, .bronze, .insect),
    badge("insects_50", "Invertebrate Observer", "Log 50 distinct insects.", .specialties, .insects, 50, .gold, .insect),
]

/// Android compatibility spelling for call sites that mirror the source name.
public let TrailBadgeCatalog = trailBadgeCatalog

public func calculateTrailBadges(
    hikes: [Hike],
    species: [SpeciesRecord],
    quests: [FieldQuest]
) -> [TrailBadge] {
    let outings = hikes.filter { !$0.isStandalone }
    let distinctSpecies = distinctSpeciesRecords(species)
    let completedQuests = quests.filter(isFieldQuestComplete).count

    var rareTaxa = Set<Int64?>()
    for quest in quests {
        for taxon in quest.taxa where taxon.collected
            && taxon.frequencyBand.range(of: "less often", options: .caseInsensitive) != nil {
            rareTaxa.insert(taxon.taxonId)
        }
    }

    func iconicCount(_ names: Set<String>) -> Double {
        Double(distinctSpecies.count { names.contains($0.iconicTaxonName.domainFolded) })
    }

    let distances = outings.map { hike -> Double in
        guard let value = hike.distanceMiles, value.isFinite else { return 0 }
        return max(0, value)
    }
    let metrics: [BadgeMetric: Double] = [
        .hikeCount: Double(outings.count),
        .totalMiles: distances.reduce(0, +),
        .longestHike: distances.max() ?? 0,
        .completedQuests: Double(completedQuests),
        .rareFinds: Double(rareTaxa.count),
        .speciesCount: Double(distinctSpecies.count),
        .plants: iconicCount(["plantae", "plant"]),
        .mammals: iconicCount(["mammalia", "mammal"]),
        .fungi: iconicCount(["fungi", "fungus"]),
        .birds: iconicCount(["aves", "bird"]),
        .insects: iconicCount(["insecta", "insect"]),
    ]
    return trailBadgeCatalog.map {
        TrailBadge(definition: $0, current: metrics[$0.metric] ?? 0)
    }
}

func distinctSpeciesRecords(_ species: [SpeciesRecord]) -> [SpeciesRecord] {
    var seen = Set<String>()
    return species.filter { record in
        let identity = record.taxonId.map(String.init) ?? record.key
        return seen.insert(identity).inserted
    }
}
