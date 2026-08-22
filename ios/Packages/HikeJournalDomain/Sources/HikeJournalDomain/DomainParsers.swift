import Foundation

public func parseHikes(_ json: String) throws -> [Hike] {
    try HikeJournalDomainJSON.decode([Hike].self, from: json)
}

public func parseHike(_ json: String) throws -> Hike {
    try HikeJournalDomainJSON.decode(Hike.self, from: json)
}

public func parseHikeLocations(_ json: String) throws -> [HikeLocation] {
    try HikeJournalDomainJSON.decode([HikeLocation].self, from: json).filter {
        !$0.id.domainTrimmed.isEmpty && !$0.name.domainTrimmed.isEmpty
    }
}

public func parseHikeLocation(_ json: String) throws -> HikeLocation {
    try HikeJournalDomainJSON.decode(HikeLocation.self, from: json)
}

public func parseMapRoutes(_ json: String) throws -> [MapRoute] {
    try HikeJournalDomainJSON.decode([MapRoute].self, from: json)
}

public func parseMapRouteSegments(_ json: String) throws -> [[RoutePoint]] {
    try parseMapRoutes(json).flatMap(\.segments)
}

public func parseSpeciesList(_ json: String) throws -> [SpeciesRecord] {
    try HikeJournalDomainJSON.decode([SpeciesRecord].self, from: json)
}

public func parseSpecies(_ json: String) throws -> SpeciesRecord {
    try HikeJournalDomainJSON.decode(SpeciesRecord.self, from: json)
}

public func parseDiscoveryAreas(_ json: String) throws -> [DiscoveryArea] {
    try HikeJournalDomainJSON.decode([DiscoveryArea].self, from: json)
}

public func parseNearbySpecies(_ json: String) throws -> NearbySpecies {
    try HikeJournalDomainJSON.decode(NearbySpecies.self, from: json)
}

public func parseFieldQuest(_ json: String) throws -> FieldQuest {
    try HikeJournalDomainJSON.decode(FieldQuest.self, from: json)
}

public func parseFieldQuests(_ json: String) throws -> [FieldQuest] {
    try HikeJournalDomainJSON.decode([FieldQuest].self, from: json)
}

public func parseQuestSightingsMap(_ json: String) throws -> QuestSightingsMap {
    try HikeJournalDomainJSON.decode(QuestSightingsMap.self, from: json)
}

public func parseSightings(_ json: String) throws -> [Sighting] {
    try HikeJournalDomainJSON.decode([Sighting].self, from: json)
}

public func parseReviewQueue(_ json: String) throws -> [ReviewItem] {
    try HikeJournalDomainJSON.decode([ReviewItem].self, from: json)
}

public func parseReviewBatchResult(_ json: String) throws -> ReviewBatchResult {
    try HikeJournalDomainJSON.decode(ReviewBatchResult.self, from: json)
}

public func parseReviewBatchStatus(_ json: String) throws -> ReviewBatchStatus {
    try HikeJournalDomainJSON.decode(ReviewBatchStatus.self, from: json)
}

public func parseReviewItem(_ json: String) throws -> ReviewItem {
    try HikeJournalDomainJSON.decode(ReviewItem.self, from: json)
}

public func parsePublishQueue(_ json: String) throws -> PublishQueue {
    try HikeJournalDomainJSON.decode(PublishQueue.self, from: json)
}

public func parsePublishItem(_ json: String) throws -> PublishItem {
    try HikeJournalDomainJSON.decode(PublishItem.self, from: json)
}

public func parsePublishBatchStatus(_ json: String) throws -> PublishBatchStatus {
    try HikeJournalDomainJSON.decode(PublishBatchStatus.self, from: json)
}

public func parsePlaceProfile(_ json: String) throws -> PlaceProfile {
    try HikeJournalDomainJSON.decode(PlaceProfile.self, from: json)
}

public func parseHikeComparison(_ json: String) throws -> HikeComparison {
    try HikeJournalDomainJSON.decode(HikeComparison.self, from: json)
}

public func parseFieldBriefing(_ json: String) throws -> FieldBriefing {
    try HikeJournalDomainJSON.decode(FieldBriefing.self, from: json)
}

public func parseWeatherSnapshot(_ json: String) throws -> WeatherSnapshot? {
    let data = Data(json.utf8)
    guard !data.isEmpty, json.domainTrimmed != "null", json.domainTrimmed != "{}" else { return nil }
    return try HikeJournalDomainJSON.decode(WeatherSnapshot.self, from: data)
}

public func roundedDiscoveryCoordinate(_ value: Double) -> Double {
    (value * 100).rounded(.toNearestOrEven) / 100
}
