import Foundation
import HikeJournalDomain

struct HikePhotoPage: Codable, Equatable, Sendable {
    let photos: [Photo]
    let nextOffset: Int?

    enum CodingKeys: String, CodingKey {
        case photos
        case nextOffset = "next_offset"
    }
}

struct HikeRoutePayload: Codable, Equatable, Sendable {
    let routeSegments: [[RoutePoint]]
    let startedAt: String?
    let durationSeconds: Int64?
    let distanceMiles: Double?
    let trackPointCount: Int

    enum CodingKeys: String, CodingKey {
        case routeSegments = "route_segments"
        case startedAt = "started_at"
        case durationSeconds = "duration_seconds"
        case distanceMiles = "distance_miles"
        case trackPointCount = "track_point_count"
    }
}

struct DeletedResourceResponse: Codable, Equatable, Sendable {
    let deleted: Bool
    let id: String?
}

struct InaturalistAuthorizationResponse: Codable, Equatable, Sendable {
    let authorizeURL: URL

    enum CodingKeys: String, CodingKey {
        case authorizeURL = "authorize_url"
    }
}

struct ReviewDecisionResponse: Codable, Equatable, Sendable {
    let ok: Bool
    let photoID: String
    let action: String

    enum CodingKeys: String, CodingKey {
        case ok
        case photoID = "photo_id"
        case action
    }
}

struct SpeciesQuestDraft: Codable, Equatable, Sendable {
    let areaID: String
    let targetDate: String
    let radiusKM: Int
    let iconicTaxon: String?
    let title: String
    let linkedHikeID: String?
    let resultLimit: Int

    enum CodingKeys: String, CodingKey {
        case areaID = "area_id"
        case targetDate = "target_date"
        case radiusKM = "radius_km"
        case iconicTaxon = "iconic_taxon"
        case title
        case linkedHikeID = "linked_hike_id"
        case resultLimit = "result_limit"
    }
}

struct SpeciesQuestUpdate: Codable, Equatable, Sendable {
    let title: String?
    let status: String?
    let linkedHikeID: String?
    let setLinkedHike: Bool
    let focusTaxonIDs: [Int64]?

    enum CodingKeys: String, CodingKey {
        case title
        case status
        case linkedHikeID = "linked_hike_id"
        case setLinkedHike = "set_linked_hike"
        case focusTaxonIDs = "focus_taxon_ids"
    }
}

protocol HikeJournalFeatureAPI: Sendable {
    func hikes() async throws -> [Hike]
    func hike(id: String) async throws -> Hike
    func hikePhotos(id: String, offset: Int, limit: Int) async throws -> HikePhotoPage
    func hikeRoute(id: String) async throws -> HikeRoutePayload
    func hikeLocations(state: String) async throws -> [HikeLocation]
    func createHikeLocation(name: String, latitude: Double?, longitude: Double?) async throws -> HikeLocation
    func placeProfile(id: String) async throws -> PlaceProfile
    func placeConditions(
        id: String,
        riverDays: Int,
        followedGaugeIDs: [String]
    ) async throws -> PlaceConditions
    func fieldBriefing(locationID: String, date: String, iconicTaxa: [String]) async throws -> FieldBriefing
    func comparison(hikeID: String, otherHikeID: String) async throws -> HikeComparison
    func enrichWeather(hikeID: String, force: Bool) async throws -> WeatherSnapshot
    func species() async throws -> [SpeciesRecord]
    func speciesDetail(key: String) async throws -> SpeciesRecord
    func sightings() async throws -> [Sighting]
    func mapRoutes() async throws -> [MapRoute]
    func discoveryAreas(query: String) async throws -> [DiscoveryArea]
    func nearbySpecies(
        areaID: String?,
        date: String,
        radiusKM: Int,
        iconicTaxa: [String],
        latitude: Double?,
        longitude: Double?,
        limit: Int
    ) async throws -> NearbySpecies
    func quests() async throws -> [FieldQuest]
    func quest(id: String) async throws -> FieldQuest
    func createQuest(_ draft: SpeciesQuestDraft) async throws -> FieldQuest
    func updateQuest(id: String, update: SpeciesQuestUpdate) async throws -> FieldQuest
    func deleteQuest(id: String) async throws
    func questSightings(questID: String, taxonID: Int64) async throws -> QuestSightingsMap
    func nearbySightings(nearby: NearbySpecies, taxonID: Int64) async throws -> QuestSightingsMap
    func reviewQueue() async throws -> [ReviewItem]
    func requestReviewRecommendation(photoID: String) async throws -> ReviewItem
    func startReviewBatch(groups: [[String]], clientRequestID: String) async throws -> ReviewBatchStatus
    func reviewBatchStatus(jobID: String) async throws -> ReviewBatchStatus
    func decideReview(
        photoID: String,
        observationID: String?,
        action: String,
        candidate: ReviewCandidate?
    ) async throws -> ReviewDecisionResponse
    func publishQueue() async throws -> PublishQueue
    func publishObservation(id: String, options: PublishOptions) async throws -> PublishItem
    func startPublishBatch(
        groups: [[String]],
        options: PublishOptions,
        clientRequestID: String
    ) async throws -> PublishBatchStatus
    func publishBatchStatus(jobID: String) async throws -> PublishBatchStatus
    func inaturalistAuthorizationURL() async throws -> URL
}

struct UnavailableHikeJournalFeatureAPI: HikeJournalFeatureAPI {
    private func unavailable<Value>() throws -> Value {
        throw APIClientError.missingBaseURL
    }

    func hikes() async throws -> [Hike] { try unavailable() }
    func hike(id: String) async throws -> Hike { try unavailable() }
    func hikePhotos(id: String, offset: Int, limit: Int) async throws -> HikePhotoPage { try unavailable() }
    func hikeRoute(id: String) async throws -> HikeRoutePayload { try unavailable() }
    func hikeLocations(state: String) async throws -> [HikeLocation] { try unavailable() }
    func createHikeLocation(name: String, latitude: Double?, longitude: Double?) async throws -> HikeLocation { try unavailable() }
    func placeProfile(id: String) async throws -> PlaceProfile { try unavailable() }
    func placeConditions(id: String, riverDays: Int, followedGaugeIDs: [String]) async throws -> PlaceConditions { try unavailable() }
    func fieldBriefing(locationID: String, date: String, iconicTaxa: [String]) async throws -> FieldBriefing { try unavailable() }
    func comparison(hikeID: String, otherHikeID: String) async throws -> HikeComparison { try unavailable() }
    func enrichWeather(hikeID: String, force: Bool) async throws -> WeatherSnapshot { try unavailable() }
    func species() async throws -> [SpeciesRecord] { try unavailable() }
    func speciesDetail(key: String) async throws -> SpeciesRecord { try unavailable() }
    func sightings() async throws -> [Sighting] { try unavailable() }
    func mapRoutes() async throws -> [MapRoute] { try unavailable() }
    func discoveryAreas(query: String) async throws -> [DiscoveryArea] { try unavailable() }
    func nearbySpecies(
        areaID: String?,
        date: String,
        radiusKM: Int,
        iconicTaxa: [String],
        latitude: Double?,
        longitude: Double?,
        limit: Int
    ) async throws -> NearbySpecies { try unavailable() }
    func quests() async throws -> [FieldQuest] { try unavailable() }
    func quest(id: String) async throws -> FieldQuest { try unavailable() }
    func createQuest(_ draft: SpeciesQuestDraft) async throws -> FieldQuest { try unavailable() }
    func updateQuest(id: String, update: SpeciesQuestUpdate) async throws -> FieldQuest { try unavailable() }
    func deleteQuest(id: String) async throws { throw APIClientError.missingBaseURL }
    func questSightings(questID: String, taxonID: Int64) async throws -> QuestSightingsMap { try unavailable() }
    func nearbySightings(nearby: NearbySpecies, taxonID: Int64) async throws -> QuestSightingsMap { try unavailable() }
    func reviewQueue() async throws -> [ReviewItem] { try unavailable() }
    func requestReviewRecommendation(photoID: String) async throws -> ReviewItem { try unavailable() }
    func startReviewBatch(groups: [[String]], clientRequestID: String) async throws -> ReviewBatchStatus { try unavailable() }
    func reviewBatchStatus(jobID: String) async throws -> ReviewBatchStatus { try unavailable() }
    func decideReview(photoID: String, observationID: String?, action: String, candidate: ReviewCandidate?) async throws -> ReviewDecisionResponse { try unavailable() }
    func publishQueue() async throws -> PublishQueue { try unavailable() }
    func publishObservation(id: String, options: PublishOptions) async throws -> PublishItem { try unavailable() }
    func startPublishBatch(groups: [[String]], options: PublishOptions, clientRequestID: String) async throws -> PublishBatchStatus { try unavailable() }
    func publishBatchStatus(jobID: String) async throws -> PublishBatchStatus { try unavailable() }
    func inaturalistAuthorizationURL() async throws -> URL { try unavailable() }
}

extension APIClient: HikeJournalFeatureAPI {
    func hikes() async throws -> [Hike] {
        try await send(APIRequest(path: "/v1/hikes", maximumResponseBytes: 12 * 1_024 * 1_024))
    }

    func hike(id: String) async throws -> Hike {
        return try await send(
            APIRequest(
                path: "/v1/hikes/\(try apiPathSegment(id))",
                queryItems: [
                    URLQueryItem(name: "include_photos", value: "false"),
                    URLQueryItem(name: "include_route", value: "false"),
                ]
            )
        )
    }

    func hikePhotos(id: String, offset: Int, limit: Int) async throws -> HikePhotoPage {
        try await send(
            APIRequest(
                path: "/v1/hikes/\(try apiPathSegment(id))/photos",
                queryItems: [
                    URLQueryItem(name: "offset", value: String(max(0, offset))),
                    URLQueryItem(name: "limit", value: String(min(100, max(1, limit)))),
                ],
                maximumResponseBytes: 12 * 1_024 * 1_024
            )
        )
    }

    func hikeRoute(id: String) async throws -> HikeRoutePayload {
        try await send(APIRequest(path: "/v1/hikes/\(try apiPathSegment(id))/route"))
    }

    func hikeLocations(state: String) async throws -> [HikeLocation] {
        try await send(
            APIRequest(
                path: "/v1/hike-locations",
                queryItems: [URLQueryItem(name: "state", value: state)]
            )
        )
    }

    func createHikeLocation(
        name: String,
        latitude: Double?,
        longitude: Double?
    ) async throws -> HikeLocation {
        try await send(
            APIRequest(
                method: .post,
                path: "/v1/hike-locations",
                body: try jsonBody([
                    "name": name,
                    "lat": latitude ?? NSNull(),
                    "lng": longitude ?? NSNull(),
                ])
            )
        )
    }

    func placeProfile(id: String) async throws -> PlaceProfile {
        try await send(APIRequest(path: "/v1/places/\(try apiPathSegment(id))/profile"))
    }

    func placeConditions(
        id: String,
        riverDays: Int,
        followedGaugeIDs: [String]
    ) async throws -> PlaceConditions {
        var queryItems = [
            URLQueryItem(name: "river_days", value: riverDays >= 30 ? "30" : "7")
        ]
        queryItems.append(contentsOf: followedGaugeIDs.prefix(20).map {
            URLQueryItem(name: "followed_gauge_id", value: $0)
        })
        return try await send(
            APIRequest(
                path: "/v1/places/\(try apiPathSegment(id))/conditions",
                queryItems: queryItems,
                timeoutInterval: 45,
                maximumResponseBytes: 8 * 1_024 * 1_024
            )
        )
    }

    func fieldBriefing(
        locationID: String,
        date: String,
        iconicTaxa: [String]
    ) async throws -> FieldBriefing {
        var query = [
            URLQueryItem(name: "location_id", value: locationID),
            URLQueryItem(name: "date", value: date),
        ]
        if !iconicTaxa.isEmpty {
            query.append(URLQueryItem(name: "iconic_taxon", value: iconicTaxa.joined(separator: ",")))
        }
        return try await send(APIRequest(path: "/v1/field-briefing", queryItems: query))
    }

    func comparison(hikeID: String, otherHikeID: String) async throws -> HikeComparison {
        try await send(
            APIRequest(
                path: "/v1/hikes/\(try apiPathSegment(hikeID))/comparison",
                queryItems: [URLQueryItem(name: "other_hike_id", value: otherHikeID)]
            )
        )
    }

    func enrichWeather(hikeID: String, force: Bool) async throws -> WeatherSnapshot {
        try await send(
            APIRequest(
                method: .post,
                path: "/v1/hikes/\(try apiPathSegment(hikeID))/weather",
                queryItems: [URLQueryItem(name: "force", value: force ? "true" : "false")],
                body: Data("{}".utf8),
                timeoutInterval: 60
            )
        )
    }

    func species() async throws -> [SpeciesRecord] {
        try await send(APIRequest(path: "/v1/species", maximumResponseBytes: 16 * 1_024 * 1_024))
    }

    func speciesDetail(key: String) async throws -> SpeciesRecord {
        try await send(
            APIRequest(path: "/v1/species/detail", queryItems: [URLQueryItem(name: "key", value: key)])
        )
    }

    func sightings() async throws -> [Sighting] {
        try await send(APIRequest(path: "/v1/sightings", maximumResponseBytes: 12 * 1_024 * 1_024))
    }

    func mapRoutes() async throws -> [MapRoute] {
        try await send(APIRequest(path: "/v1/routes", maximumResponseBytes: 12 * 1_024 * 1_024))
    }

    func discoveryAreas(query: String) async throws -> [DiscoveryArea] {
        try await send(
            APIRequest(path: "/v1/discovery/areas", queryItems: [URLQueryItem(name: "q", value: query)])
        )
    }

    func nearbySpecies(
        areaID: String?,
        date: String,
        radiusKM: Int,
        iconicTaxa: [String],
        latitude: Double?,
        longitude: Double?,
        limit: Int
    ) async throws -> NearbySpecies {
        var query = [
            URLQueryItem(name: "date", value: date),
            URLQueryItem(name: "radius_km", value: String(radiusKM)),
            URLQueryItem(name: "limit", value: String(limit)),
        ]
        if let areaID, !areaID.isEmpty {
            query.append(URLQueryItem(name: "area_id", value: areaID))
        } else if let latitude, let longitude {
            query += [
                URLQueryItem(name: "lat", value: String(roundedDiscoveryCoordinate(latitude))),
                URLQueryItem(name: "lng", value: String(roundedDiscoveryCoordinate(longitude))),
                URLQueryItem(name: "area_name", value: "Current area"),
            ]
        }
        if !iconicTaxa.isEmpty {
            query.append(URLQueryItem(name: "iconic_taxon", value: iconicTaxa.joined(separator: ",")))
        }
        return try await send(APIRequest(path: "/v1/discovery/nearby", queryItems: query))
    }

    func quests() async throws -> [FieldQuest] {
        try await send(APIRequest(path: "/v1/discovery/quests"))
    }

    func quest(id: String) async throws -> FieldQuest {
        try await send(APIRequest(path: "/v1/discovery/quests/\(try apiPathSegment(id))"))
    }

    func createQuest(_ draft: SpeciesQuestDraft) async throws -> FieldQuest {
        try await send(
            APIRequest(
                method: .post,
                path: "/v1/discovery/quests",
                body: try JSONEncoder.hikeJournal.encode(draft),
                timeoutInterval: 60
            )
        )
    }

    func updateQuest(id: String, update: SpeciesQuestUpdate) async throws -> FieldQuest {
        try await send(
            APIRequest(
                method: .patch,
                path: "/v1/discovery/quests/\(try apiPathSegment(id))",
                body: try JSONEncoder.hikeJournal.encode(update)
            )
        )
    }

    func deleteQuest(id: String) async throws {
        let response: DeletedResourceResponse = try await send(
            APIRequest(method: .delete, path: "/v1/discovery/quests/\(try apiPathSegment(id))")
        )
        guard response.deleted else { throw APIClientError.responseDecodingFailed }
    }

    func questSightings(questID: String, taxonID: Int64) async throws -> QuestSightingsMap {
        try await send(
            APIRequest(
                path: "/v1/discovery/quests/\(try apiPathSegment(questID))/sightings",
                queryItems: [URLQueryItem(name: "taxon_id", value: String(taxonID))]
            )
        )
    }

    func nearbySightings(nearby: NearbySpecies, taxonID: Int64) async throws -> QuestSightingsMap {
        var query = [
            URLQueryItem(name: "taxon_id", value: String(taxonID)),
            URLQueryItem(name: "date", value: nearby.targetDate),
            URLQueryItem(name: "radius_km", value: String(nearby.radiusKm)),
        ]
        if !nearby.areaId.isEmpty {
            query.append(URLQueryItem(name: "area_id", value: nearby.areaId))
        } else if let latitude = nearby.latitude, let longitude = nearby.longitude {
            query += [
                URLQueryItem(name: "lat", value: String(roundedDiscoveryCoordinate(latitude))),
                URLQueryItem(name: "lng", value: String(roundedDiscoveryCoordinate(longitude))),
                URLQueryItem(name: "area_name", value: nearby.areaName),
            ]
        }
        return try await send(APIRequest(path: "/v1/discovery/nearby/sightings", queryItems: query))
    }

    func reviewQueue() async throws -> [ReviewItem] {
        try await send(APIRequest(path: "/v1/species/review"))
    }

    func requestReviewRecommendation(photoID: String) async throws -> ReviewItem {
        try await send(
            APIRequest(
                method: .post,
                path: "/v1/species/review/\(try apiPathSegment(photoID))/recommendation",
                body: Data("{}".utf8),
                timeoutInterval: 60
            )
        )
    }

    func startReviewBatch(
        groups: [[String]],
        clientRequestID: String
    ) async throws -> ReviewBatchStatus {
        try await send(
            APIRequest(
                method: .post,
                path: "/v1/species/review/batch-recommendation/start",
                body: try jsonBody([
                    "groups": groups.map { ["photo_ids": $0] },
                    "client_request_id": clientRequestID,
                ])
            )
        )
    }

    func reviewBatchStatus(jobID: String) async throws -> ReviewBatchStatus {
        try await send(
            APIRequest(
                path: "/v1/species/review/batch-recommendation/\(try apiPathSegment(jobID))"
            )
        )
    }

    func decideReview(
        photoID: String,
        observationID: String?,
        action: String,
        candidate: ReviewCandidate?
    ) async throws -> ReviewDecisionResponse {
        var payload: [String: Any] = [
            "action": action,
            "observation_id": observationID ?? NSNull(),
        ]
        if let candidate {
            let candidatePayload: [String: Any] = [
                "taxon_id": candidate.taxonId.map { $0 as Any } ?? NSNull(),
                "common_name": candidate.commonName,
                "scientific_name": candidate.scientificName,
                "confidence": normalizedReviewConfidence(candidate.confidence).map { $0 as Any } ?? NSNull(),
            ]
            payload["candidate"] = candidatePayload
        }
        return try await send(
            APIRequest(
                method: .post,
                path: "/v1/species/review/\(try apiPathSegment(photoID))/decision",
                body: try jsonBody(payload),
                timeoutInterval: 60
            )
        )
    }

    func publishQueue() async throws -> PublishQueue {
        try await send(APIRequest(path: "/v1/species/publish"))
    }

    func publishObservation(id: String, options: PublishOptions) async throws -> PublishItem {
        var payload = try jsonObject(options)
        payload["acknowledged_public"] = true
        return try await send(
            APIRequest(
                method: .post,
                path: "/v1/species/publish/\(try apiPathSegment(id))",
                body: try jsonBody(payload),
                timeoutInterval: 90
            )
        )
    }

    func startPublishBatch(
        groups: [[String]],
        options: PublishOptions,
        clientRequestID: String
    ) async throws -> PublishBatchStatus {
        try await send(
            APIRequest(
                method: .post,
                path: "/v1/species/publish/batch/start",
                body: try jsonBody([
                    "acknowledged_public": true,
                    "groups": groups.map { ["observation_ids": $0] },
                    "client_request_id": clientRequestID,
                    "description": options.description,
                    "tags": options.tags,
                    "geoprivacy": options.geoprivacy,
                    "captive": options.captive,
                ])
            )
        )
    }

    func publishBatchStatus(jobID: String) async throws -> PublishBatchStatus {
        try await send(
            APIRequest(path: "/v1/species/publish/batch/\(try apiPathSegment(jobID))")
        )
    }

    func inaturalistAuthorizationURL() async throws -> URL {
        let response: InaturalistAuthorizationResponse = try await send(
            APIRequest(path: "/v1/inat/oauth/start")
        )
        return response.authorizeURL
    }

    private func apiPathSegment(_ value: String) throws -> String {
        let clean = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty, clean.utf8.count <= 256 else {
            throw APIClientError.invalidRequestPath
        }
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-._~"))
        guard let encoded = clean.addingPercentEncoding(withAllowedCharacters: allowed) else {
            throw APIClientError.invalidRequestPath
        }
        return encoded
    }

    private func jsonBody(_ value: [String: Any]) throws -> Data {
        guard JSONSerialization.isValidJSONObject(value) else {
            throw APIClientError.requestEncodingFailed
        }
        do {
            return try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
        } catch {
            throw APIClientError.requestEncodingFailed
        }
    }

    private func jsonObject<Value: Encodable>(_ value: Value) throws -> [String: Any] {
        do {
            let data = try JSONEncoder.hikeJournal.encode(value)
            guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw APIClientError.requestEncodingFailed
            }
            return object
        } catch let error as APIClientError {
            throw error
        } catch {
            throw APIClientError.requestEncodingFailed
        }
    }
}

private extension JSONEncoder {
    static var hikeJournal: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }
}
