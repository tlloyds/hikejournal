import Foundation

public enum CelebrationKind: String, Codable, CaseIterable, Equatable, Sendable {
    case identification = "Identification"
    case discovery = "Discovery"
    case rediscovery = "Rediscovery"
    case milestone = "Milestone"
}

public struct CelebrationHighlight: Codable, Equatable, Sendable {
    public let value: String
    public let label: String

    public init(value: String, label: String) {
        self.value = value
        self.label = label
    }
}

public struct FieldCelebration: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let kind: CelebrationKind
    public let eyebrow: String
    public let title: String
    public let detail: String
    public let imageUrls: [String]
    public let highlights: [CelebrationHighlight]
    public let badgeTitle: String?
    public let badgeProgress: String?
    public let actionLabel: String

    public init(
        id: String,
        kind: CelebrationKind,
        eyebrow: String,
        title: String,
        detail: String,
        imageUrls: [String] = [],
        highlights: [CelebrationHighlight] = [],
        badgeTitle: String? = nil,
        badgeProgress: String? = nil,
        actionLabel: String = "Continue"
    ) {
        self.id = id
        self.kind = kind
        self.eyebrow = eyebrow
        self.title = title
        self.detail = detail
        self.imageUrls = imageUrls
        self.highlights = highlights
        self.badgeTitle = badgeTitle
        self.badgeProgress = badgeProgress
        self.actionLabel = actionLabel
    }
}

private func speciesIdentity(
    taxonId: Int64?,
    scientificName: String,
    commonName: String
) -> String {
    if let taxonId { return "taxon:\(taxonId)" }
    if !scientificName.domainTrimmed.isEmpty {
        return "scientific:\(scientificName.domainFolded)"
    }
    return "common:\(commonName.domainFolded)"
}

private func speciesIdentity(_ species: SpeciesRecord) -> String {
    speciesIdentity(
        taxonId: species.taxonId,
        scientificName: species.scientificName,
        commonName: species.commonName
    )
}

private func speciesIdentity(_ candidate: ReviewCandidate) -> String {
    speciesIdentity(
        taxonId: candidate.taxonId,
        scientificName: candidate.scientificName,
        commonName: candidate.commonName
    )
}

private func celebrationObservedDate(_ value: String?) -> Date? {
    guard let raw = value?.domainTrimmed, !raw.isEmpty else { return nil }
    let internet = ISO8601DateFormatter()
    internet.formatOptions = [.withInternetDateTime, .withColonSeparatorInTimeZone]
    if let date = internet.date(from: raw) { return date }
    internet.formatOptions = [
        .withInternetDateTime,
        .withColonSeparatorInTimeZone,
        .withFractionalSeconds,
    ]
    if let date = internet.date(from: raw) { return date }
    guard raw.count >= 10 else { return nil }
    let formatter = DateFormatter()
    formatter.calendar = Calendar(identifier: .gregorian)
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.timeZone = TimeZone(secondsFromGMT: 0)
    formatter.dateFormat = "yyyy-MM-dd"
    formatter.isLenient = false
    return formatter.date(from: String(raw.prefix(10)))
}

private func lifeGroupLabel(_ iconicTaxonName: String) -> String {
    switch iconicTaxonName.domainFolded {
    case "plantae", "plant": "plants"
    case "aves", "bird": "birds"
    case "mammalia", "mammal": "mammals"
    case "insecta", "insect": "insects"
    case "fungi", "fungus": "fungi"
    case "reptilia": "reptiles"
    case "amphibia": "amphibians"
    case "arachnida": "arachnids"
    case "actinopterygii": "fish"
    case "mollusca": "mollusks"
    default: "species"
    }
}

public func buildReviewBatchCelebration(
    status: ReviewBatchStatus,
    existingSpecies: [SpeciesRecord]
) -> FieldCelebration? {
    guard status.processedCount > 0 else { return nil }

    var seenSuggestions = Set<String>()
    let suggestions: [(ReviewItem, ReviewCandidate)] = status.items.compactMap { item in
        guard let candidate = item.candidates.first else { return nil }
        return seenSuggestions.insert(speciesIdentity(candidate)).inserted ? (item, candidate) : nil
    }
    let known = Set(existingSpecies.map(speciesIdentity))
    let possibleNew = suggestions.filter { !known.contains(speciesIdentity($0.1)) }

    let typeCounts = Dictionary(grouping: possibleNew) { lifeGroupLabel($0.1.iconicTaxonName) }
        .mapValues(\.count)
        .filter { $0.key != "species" }
    let typeDetail = typeCounts
        .sorted {
            if $0.value != $1.value { return $0.value > $1.value }
            return $0.key < $1.key
        }
        .prefix(2)
        .map { "\($0.value) \($0.key)" }
        .joined(separator: " · ")

    let title: String
    if possibleNew.count == 1 {
        title = "A possible new species"
    } else if !possibleNew.isEmpty {
        title = "\(possibleNew.count) possible new species"
    } else if suggestions.count == 1 {
        title = "An identification is ready"
    } else if !suggestions.isEmpty {
        title = "\(suggestions.count) identifications are ready"
    } else {
        title = "Identification batch complete"
    }

    var detail = "Review the suggestions to add confirmed finds to your Field Guide."
    if !typeDetail.isEmpty {
        detail += " \(typeDetail) are new possibilities in this batch."
    }
    if let warning = status.warnings.first {
        detail += " \(warning)"
    }

    var seenImages = Set<String>()
    let images = status.items.lazy.map(\.photo.url).filter {
        !$0.isEmpty && seenImages.insert($0).inserted
    }.prefix(3)

    return FieldCelebration(
        id: "batch:\(status.jobId)",
        kind: .identification,
        eyebrow: "THE FIELD NOTES ARE IN",
        title: title,
        detail: detail,
        imageUrls: Array(images),
        highlights: [
            CelebrationHighlight(value: String(status.processedCount), label: "photos read"),
            CelebrationHighlight(value: String(suggestions.count), label: "unique IDs"),
            CelebrationHighlight(value: String(possibleNew.count), label: "possible new"),
        ],
        actionLabel: "Review discoveries"
    )
}

private func nextFieldGuideBadge(total: Int) -> TrailBadgeDefinition? {
    trailBadgeCatalog
        .filter { $0.metric == .speciesCount && $0.target > Double(total) }
        .min { $0.target < $1.target }
}

private func unlockedFieldGuideBadge(before: Int, after: Int) -> TrailBadgeDefinition? {
    trailBadgeCatalog
        .filter {
            $0.metric == .speciesCount
                && Double(before) < $0.target
                && Double(after) >= $0.target
        }
        .max { $0.target < $1.target }
}

public func buildConfirmedSpeciesCelebration(
    candidate: ReviewCandidate,
    photo: Photo,
    observedOn: String?,
    existingSpecies: [SpeciesRecord]
) -> FieldCelebration? {
    let identity = speciesIdentity(candidate)
    guard let existing = existingSpecies.first(where: { speciesIdentity($0) == identity }) else {
        let before = Set(existingSpecies.map(speciesIdentity)).count
        let after = before + 1
        let unlocked = unlockedFieldGuideBadge(before: before, after: after)
        let next = nextFieldGuideBadge(total: after)
        let group = lifeGroupLabel(candidate.iconicTaxonName)
        let title = candidate.commonName.domainTrimmed.isEmpty
            ? (candidate.scientificName.domainTrimmed.isEmpty ? "New species" : candidate.scientificName)
            : candidate.commonName
        let progress: String
        if let unlocked {
            progress = unlocked.requirement
        } else if let next {
            progress = "\(after) / \(Int(next.target)) · \(next.title)"
        } else {
            progress = "\(after) species in your Field Guide"
        }
        return FieldCelebration(
            id: "species:\(identity):\(photo.id)",
            kind: .discovery,
            eyebrow: "NEW TO YOUR FIELD GUIDE",
            title: title,
            detail: "Your first confirmed \(group) record is now part of your living archive.",
            imageUrls: photo.url.isEmpty ? [] : [photo.url],
            highlights: [
                CelebrationHighlight(value: String(after), label: "species logged"),
                CelebrationHighlight(value: group.prefix(1).uppercased() + group.dropFirst(), label: "life group"),
            ],
            badgeTitle: unlocked?.title,
            badgeProgress: progress
        )
    }

    let previous = celebrationObservedDate(existing.latestSeen)
    let current = celebrationObservedDate(observedOn ?? photo.takenAt ?? photo.createdAt)
    let days: Int
    if let previous, let current, current > previous {
        days = Int(current.timeIntervalSince(previous) / 86_400)
    } else {
        days = 0
    }
    guard days >= 60 else { return nil }
    let title = existing.commonName.domainTrimmed.isEmpty
        ? existing.scientificName
        : existing.commonName
    let image = photo.url.domainTrimmed.isEmpty ? existing.coverUrl : photo.url
    return FieldCelebration(
        id: "return:\(speciesIdentity(existing)):\(photo.id)",
        kind: .rediscovery,
        eyebrow: "WELCOME BACK",
        title: title,
        detail: "Your first confirmed sighting of this species in \(days) days.",
        imageUrls: image.isEmpty ? [] : [image],
        highlights: [
            CelebrationHighlight(value: String(days), label: "days apart"),
            CelebrationHighlight(value: String(existing.encounterCount + 1), label: "encounters"),
        ]
    )
}

public func buildKnownSpeciesRediscoveryCelebration(
    species: SpeciesRecord,
    photo: Photo
) -> FieldCelebration? {
    buildConfirmedSpeciesCelebration(
        candidate: ReviewCandidate(
            taxonId: species.taxonId,
            commonName: species.commonName,
            scientificName: species.scientificName,
            confidence: nil,
            iconicTaxonName: species.iconicTaxonName
        ),
        photo: photo,
        observedOn: photo.takenAt ?? photo.createdAt,
        existingSpecies: [species]
    )
}

private func ordinal(_ value: Int) -> String {
    let suffix: String
    if (11...13).contains(value % 100) {
        suffix = "th"
    } else {
        switch value % 10 {
        case 1: suffix = "st"
        case 2: suffix = "nd"
        case 3: suffix = "rd"
        default: suffix = "th"
        }
    }
    return "\(value)\(suffix)"
}

public func buildHikeMilestoneCelebration(
    previousHikes: [Hike],
    updatedHikes: [Hike],
    savedHike: Hike
) -> FieldCelebration? {
    guard !savedHike.isStandalone,
          !previousHikes.contains(where: { $0.id == savedHike.id }) else { return nil }
    let before = calculateTrailBadges(hikes: previousHikes, species: [], quests: [])
    let after = calculateTrailBadges(hikes: updatedHikes, species: [], quests: [])
    let earnedBefore = Set(before.filter(\.earned).map(\.id))
    let newlyEarnedHikeBadges = after.filter {
        $0.earned && !earnedBefore.contains($0.id) && $0.definition.metric == .hikeCount
    }
    guard let hikeBadge = newlyEarnedHikeBadges.max(by: {
        $0.definition.target < $1.definition.target
    }) else { return nil }

    let outings = updatedHikes.filter { !$0.isStandalone }
    let hikeCount = outings.count
    let miles = outings.reduce(0) { result, hike in
        guard let distance = hike.distanceMiles, distance.isFinite else { return result }
        return result + distance
    }
    let title = hikeCount == 1 ? "First hike logged!" : "\(ordinal(hikeCount)) hike logged!"
    let hikeTitle = savedHike.title.domainTrimmed.isEmpty ? "This outing" : savedHike.title
    return FieldCelebration(
        id: "hike:\(savedHike.id):\(hikeCount)",
        kind: .milestone,
        eyebrow: "TRAIL MILESTONE",
        title: title,
        detail: "\(hikeTitle) earned a new trail badge.",
        imageUrls: savedHike.coverUrl.isEmpty ? [] : [savedHike.coverUrl],
        highlights: [
            CelebrationHighlight(value: String(hikeCount), label: "hikes logged"),
            CelebrationHighlight(
                value: String(format: "%.1f", locale: Locale(identifier: "en_US"), miles),
                label: "lifetime miles"
            ),
        ],
        badgeTitle: hikeBadge.definition.title,
        badgeProgress: hikeBadge.definition.requirement
    )
}
