import Foundation

/// Server, Android, cached standalone rows, and iOS must use this exact ID.
public let EVERYDAY_JOURNAL_ID = "everyday"
public let QUEST_FOCUS_LIMIT = 10

public func canonicalHikeScopeID(_ hikeID: String?) -> String {
    let normalized = hikeID?.domainTrimmed ?? ""
    return normalized.isEmpty ? EVERYDAY_JOURNAL_ID : normalized
}

public func isEverydayJournalID(_ hikeID: String?) -> Bool {
    hikeID?.domainTrimmed == EVERYDAY_JOURNAL_ID
}

/// Legacy standalone queue entries have no hike ID. They belong in the
/// Everyday scope alongside current rows carrying the explicit permanent ID.
public func publishItemsForHikeScope(
    _ items: [PublishItem],
    selectedHikeID: String?
) -> [PublishItem] {
    guard let selectedHikeID else { return items }
    if selectedHikeID == EVERYDAY_JOURNAL_ID {
        return items.filter {
            ($0.hikeId?.domainTrimmed.isEmpty ?? true) || $0.hikeId == EVERYDAY_JOURNAL_ID
        }
    }
    return items.filter { $0.hikeId == selectedHikeID }
}

public func toggleQuestFocus(_ current: [Int64], taxonID: Int64) -> [Int64] {
    if current.contains(taxonID) {
        return current.filter { $0 != taxonID }
    }
    guard current.count < QUEST_FOCUS_LIMIT else { return current }
    return current + [taxonID]
}

public func normalizeQuestFocusTaxonIDs(
    _ requested: [Int64],
    availableTaxa: [DiscoveryTaxon]
) -> [Int64] {
    let available = Set(availableTaxa.map(\.taxonId))
    var seen = Set<Int64>()
    var result: [Int64] = []
    for taxonID in requested where available.contains(taxonID) && seen.insert(taxonID).inserted {
        result.append(taxonID)
        if result.count == QUEST_FOCUS_LIMIT { break }
    }
    return result
}

public func focusedQuestTaxa(_ quest: FieldQuest) -> [DiscoveryTaxon] {
    quest.taxa.filter { $0.focusOrder != nil }.sorted { left, right in
        let leftOrder = left.focusOrder ?? Int.max
        let rightOrder = right.focusOrder ?? Int.max
        if leftOrder != rightOrder { return leftOrder < rightOrder }
        return left.taxonId < right.taxonId
    }
}

public func fieldQuests(_ quests: [FieldQuest], showingArchived: Bool) -> [FieldQuest] {
    quests.filter { ($0.status == "archived") == showingArchived }
}

public func isFieldQuestComplete(_ quest: FieldQuest) -> Bool {
    let focus = focusedQuestTaxa(quest)
    return !focus.isEmpty && focus.allSatisfy(\.collected)
}

public func questTargetPrompt(selectedCount: Int) -> String {
    selectedCount <= 0 ? "Pick at least 1" : "Save quest"
}

public func discoveryStatusLabel(collected: Bool, frequencyBand: String) -> String {
    let band = (frequencyBand.domainTrimmed.isEmpty ? "Nearby record" : frequencyBand)
        .uppercased(with: Locale(identifier: "en_US"))
    return collected ? "COLLECTED · \(band)" : band
}

public extension FieldQuest {
    func applyingFocusTaxonIDs(_ requested: [Int64], pending: Bool) -> FieldQuest {
        let normalized = normalizeQuestFocusTaxonIDs(requested, availableTaxa: taxa)
        let order = Dictionary(uniqueKeysWithValues: normalized.enumerated().map { index, id in
            (id, index + 1)
        })
        let updatedTaxa = taxa.map { taxon in
            DiscoveryTaxon(
                taxonId: taxon.taxonId,
                commonName: taxon.commonName,
                scientificName: taxon.scientificName,
                iconicTaxonName: taxon.iconicTaxonName,
                observationCount: taxon.observationCount,
                nearbyRank: taxon.nearbyRank,
                frequencyBand: taxon.frequencyBand,
                referencePhoto: taxon.referencePhoto,
                collected: taxon.collected,
                collectedAt: taxon.collectedAt,
                collectionPhotoUrl: taxon.collectionPhotoUrl,
                wikipediaUrl: taxon.wikipediaUrl,
                wikipediaSummary: taxon.wikipediaSummary,
                matchReason: taxon.matchReason,
                focusOrder: order[taxon.taxonId],
                pendingCredit: taxon.pendingCredit
            )
        }
        return FieldQuest(
            id: id,
            title: title,
            status: status,
            linkedHikeId: linkedHikeId,
            areaId: areaId,
            areaName: areaName,
            latitude: latitude,
            longitude: longitude,
            radiusKm: radiusKm,
            targetDate: targetDate,
            periodLabel: periodLabel,
            iconicTaxon: iconicTaxon,
            progress: progress,
            taxa: updatedTaxa,
            pendingFocusSync: pending
        )
    }
}
