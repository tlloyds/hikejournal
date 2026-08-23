import Combine
import Foundation
import HikeJournalDomain
import HikeJournalPersistence

@MainActor
final class JournalStore: ObservableObject {
    @Published private(set) var hikes: [Hike] = []
    @Published private(set) var details: [String: Hike] = [:]
    @Published private(set) var species: [SpeciesRecord] = []
    @Published private(set) var sightings: [Sighting] = []
    @Published private(set) var routes: [MapRoute] = []
    @Published private(set) var locations: [HikeLocation] = []
    @Published private(set) var quests: [FieldQuest] = []
    @Published private(set) var discoveryAreas: [DiscoveryArea] = []
    @Published private(set) var nearbySpecies: NearbySpecies?
    @Published private(set) var reviewItems: [ReviewItem] = []
    @Published private(set) var publishQueue: PublishQueue?
    @Published private(set) var reviewBatchStatus: ReviewBatchStatus?
    @Published private(set) var publishBatchStatus: PublishBatchStatus?
    @Published private(set) var isReviewBatchWorking = false
    @Published private(set) var isPublishBatchWorking = false
    @Published private(set) var isRefreshingHikes = false
    @Published private(set) var isPreparingAccount = false
    @Published private(set) var activeLoads: Set<String> = []
    @Published private(set) var showingCachedData = false
    @Published private(set) var statusMessage: String?
    @Published private(set) var errorMessage: String?
    @Published private(set) var fieldGuideStatusMessage: String?
    @Published private(set) var fieldGuideErrorMessage: String?
    @Published private(set) var pendingCelebration: FieldCelebration?

    private let authentication: AuthenticationStore
    private let api: any HikeJournalFeatureAPI
    private let offlineStores: OfflineStoreCoordinator?
    private weak var sync: SyncStore?
    private var phaseObservation: AnyCancellable?
    private var accountTask: Task<Void, Never>?
    private var loadedAccountIdentity: String?
    private var started = false

    init(
        authentication: AuthenticationStore,
        api: any HikeJournalFeatureAPI,
        offlineStores: OfflineStoreCoordinator?,
        sync: SyncStore? = nil
    ) {
        self.authentication = authentication
        self.api = api
        self.offlineStores = offlineStores
        self.sync = sync
        phaseObservation = authentication.$phase
            .removeDuplicates()
            .sink { [weak self] phase in
                Task { @MainActor [weak self] in
                    guard let self, self.started else { return }
                    await self.accountChanged(phase)
                }
            }
    }

    deinit {
        accountTask?.cancel()
    }

    func start() async {
        if !started {
            started = true
            await accountChanged(authentication.phase)
        }
        await accountTask?.value
    }

    func dismissCelebration() {
        pendingCelebration = nil
    }

    func refreshHikes() async {
        guard let context = await accountContext() else {
            clearAccountData()
            return
        }
        guard !isRefreshingHikes else { return }
        isRefreshingHikes = true
        errorMessage = nil
        defer { isRefreshingHikes = false }

        let cached: [Hike]? = await cachedValue(
            [Hike].self,
            database: context.database,
            namespace: Cache.hikes,
            key: "all"
        )
        if let cached {
            hikes = await applyingPendingOperations(to: cached, database: context.database)
            showingCachedData = true
        }
        do {
            let remote = try await api.hikes()
            try await cache(
                remote,
                database: context.database,
                namespace: Cache.hikes,
                key: "all",
                lifetime: 5 * 60
            )
            hikes = await applyingPendingOperations(to: remote, database: context.database)
            showingCachedData = false
            statusMessage = nil
        } catch is CancellationError {
            return
        } catch {
            if cached != nil {
                statusMessage = "Showing the journal saved on this iPhone."
            } else {
                errorMessage = readable(error)
            }
        }
    }

    func loadHike(id: String, force: Bool = false) async {
        guard let context = await accountContext() else { return }
        let loadKey = "hike:\(id)"
        guard activeLoads.insert(loadKey).inserted else { return }
        defer { activeLoads.remove(loadKey) }
        errorMessage = nil

        let cached: Hike? = await cachedValue(
            Hike.self,
            database: context.database,
            namespace: Cache.hike,
            key: id,
            requireFresh: false
        )
        if let cached { details[id] = cached }
        if !force,
           let resource = try? await context.database.cachedResource(namespace: Cache.hike, key: id),
           resource.isFresh(at: Date()),
           cached != nil {
            return
        }

        do {
            async let headerRequest = api.hike(id: id)
            async let routeRequest = api.hikeRoute(id: id)
            let photos = try await allPhotos(hikeID: id)
            let header = try await headerRequest
            let route = try await routeRequest
            let detail = header.withDetails(
                photos: photos,
                routeSegments: route.routeSegments,
                durationSeconds: route.durationSeconds ?? header.durationSeconds,
                routeStartedAt: route.startedAt ?? header.routeStartedAt,
                distanceMiles: route.distanceMiles ?? header.distanceMiles
            )
            try await cache(
                detail,
                database: context.database,
                namespace: Cache.hike,
                key: id,
                lifetime: 10 * 60
            )
            details[id] = detail
        } catch is CancellationError {
            return
        } catch {
            if cached != nil {
                statusMessage = "This journal is offline; showing its last saved copy."
            } else {
                errorMessage = readable(error)
            }
        }
    }

    func refreshFieldGuide() async {
        guard let context = await accountContext() else { return }
        let loadKey = "field-guide"
        guard activeLoads.insert(loadKey).inserted else { return }
        defer { activeLoads.remove(loadKey) }
        fieldGuideErrorMessage = nil
        fieldGuideStatusMessage = nil
        let cachedSpecies: [SpeciesRecord]? = await cachedValue(
            [SpeciesRecord].self,
            database: context.database,
            namespace: Cache.species,
            key: "all"
        )
        let cachedSightings: [Sighting]? = await cachedValue(
            [Sighting].self,
            database: context.database,
            namespace: Cache.sightings,
            key: "all"
        )
        if let cachedSpecies { species = cachedSpecies }
        if let cachedSightings { sightings = cachedSightings }

        var speciesLoaded = false
        var sightingsLoaded = false
        do {
            let remoteSpecies = try await api.species()
            species = remoteSpecies
            speciesLoaded = true
            try await cache(
                remoteSpecies,
                database: context.database,
                namespace: Cache.species,
                key: "all",
                lifetime: 60 * 60
            )
        } catch is CancellationError {
            return
        } catch {
            fieldGuideErrorMessage = readable(error)
        }
        do {
            let remoteSightings = try await api.sightings()
            sightings = remoteSightings
            sightingsLoaded = true
            try await cache(
                remoteSightings,
                database: context.database,
                namespace: Cache.sightings,
                key: "all",
                lifetime: 10 * 60
            )
        } catch is CancellationError {
            return
        } catch {
            if fieldGuideErrorMessage == nil {
                fieldGuideErrorMessage = readable(error)
            }
        }
        if !speciesLoaded || !sightingsLoaded {
            if cachedSpecies != nil || cachedSightings != nil {
                fieldGuideStatusMessage = "Field Guide is showing its saved offline copy."
            }
        } else {
            fieldGuideStatusMessage = nil
        }
    }

    func refreshMap() async {
        guard let context = await accountContext() else { return }
        let loadKey = "map"
        guard activeLoads.insert(loadKey).inserted else { return }
        defer { activeLoads.remove(loadKey) }
        let cachedRoutes: [MapRoute]? = await cachedValue(
            [MapRoute].self,
            database: context.database,
            namespace: Cache.routes,
            key: "all"
        )
        let cachedSightings: [Sighting]? = await cachedValue(
            [Sighting].self,
            database: context.database,
            namespace: Cache.sightings,
            key: "all"
        )
        if let cachedRoutes { routes = cachedRoutes }
        if let cachedSightings { sightings = cachedSightings }
        do {
            async let routeRequest = api.mapRoutes()
            async let sightingRequest = api.sightings()
            let (remoteRoutes, remoteSightings) = try await (routeRequest, sightingRequest)
            routes = remoteRoutes
            sightings = remoteSightings
            try await cache(remoteRoutes, database: context.database, namespace: Cache.routes, key: "all", lifetime: 10 * 60)
            try await cache(remoteSightings, database: context.database, namespace: Cache.sightings, key: "all", lifetime: 10 * 60)
        } catch is CancellationError {
            return
        } catch {
            if cachedRoutes == nil && cachedSightings == nil { errorMessage = readable(error) }
            else { statusMessage = "Map points and routes are from the saved offline copy." }
        }
    }

    func loadLocations(state: String, force: Bool = false) async {
        guard let context = await accountContext() else { return }
        let normalized = normalizeUSStateCode(state) ?? "FL"
        let cacheKey = normalized.lowercased()
        let cached: [HikeLocation]? = await cachedValue(
            [HikeLocation].self,
            database: context.database,
            namespace: Cache.locations,
            key: cacheKey
        )
        if let cached { locations = cached }
        if !force,
           let resource = try? await context.database.cachedResource(namespace: Cache.locations, key: cacheKey),
           resource.isFresh(at: Date()), cached != nil { return }
        do {
            let remote = try await api.hikeLocations(state: normalized)
            locations = remote
            try await cache(remote, database: context.database, namespace: Cache.locations, key: cacheKey, lifetime: 24 * 60 * 60)
        } catch {
            if cached == nil { errorMessage = readable(error) }
        }
    }

    @discardableResult
    func createLocation(
        name: String,
        latitude: Double,
        longitude: Double
    ) async -> HikeLocation? {
        let cleanName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanName.isEmpty,
              (-90...90).contains(latitude),
              (-180...180).contains(longitude) else {
            errorMessage = "Enter a place name and valid decimal coordinates."
            return nil
        }
        do {
            let location = try await api.createHikeLocation(
                name: cleanName,
                latitude: latitude,
                longitude: longitude
            )
            locations.removeAll { $0.id == location.id }
            locations.insert(location, at: 0)
            statusMessage = "“\(location.name)” is ready for place planning."
            return location
        } catch is CancellationError {
            return nil
        } catch {
            errorMessage = readable(error)
            return nil
        }
    }

    func loadQuests() async {
        guard let context = await accountContext() else { return }
        let cached: [FieldQuest]? = await cachedValue(
            [FieldQuest].self,
            database: context.database,
            namespace: Cache.quests,
            key: "all"
        )
        if let cached { quests = cached }
        do {
            let remote = try await api.quests()
            quests = remote
            try await cache(remote, database: context.database, namespace: Cache.quests, key: "all", lifetime: 5 * 60)
        } catch {
            if cached == nil { errorMessage = readable(error) }
        }
    }

    func searchDiscoveryAreas(_ query: String) async {
        let clean = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard clean.count >= 2 else {
            discoveryAreas = []
            return
        }
        do {
            discoveryAreas = try await api.discoveryAreas(query: clean)
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readable(error)
        }
    }

    func discoverNearbySpecies(
        areaID: String?,
        date: String,
        radiusKM: Int,
        iconicTaxa: [String],
        latitude: Double? = nil,
        longitude: Double? = nil,
        limit: Int = 50
    ) async {
        do {
            nearbySpecies = try await api.nearbySpecies(
                areaID: areaID,
                date: date,
                radiusKM: radiusKM,
                iconicTaxa: iconicTaxa,
                latitude: latitude,
                longitude: longitude,
                limit: limit
            )
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readable(error)
        }
    }

    @discardableResult
    func createQuest(_ draft: SpeciesQuestDraft) async -> FieldQuest? {
        do {
            let created = try await api.createQuest(draft)
            quests.removeAll { $0.id == created.id }
            quests.insert(created, at: 0)
            await cacheVisibleQuests()
            return created
        } catch {
            errorMessage = readable(error)
            return nil
        }
    }

    @discardableResult
    func updateQuest(id: String, update: SpeciesQuestUpdate) async -> FieldQuest? {
        do {
            let value = try await api.updateQuest(id: id, update: update)
            quests = quests.map { $0.id == id ? value : $0 }
            await cacheVisibleQuests()
            return value
        } catch {
            errorMessage = readable(error)
            return nil
        }
    }

    func deleteQuest(id: String) async -> Bool {
        do {
            try await api.deleteQuest(id: id)
            quests.removeAll { $0.id == id }
            await cacheVisibleQuests()
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    func loadReviewAndPublishing() async {
        guard let context = await accountContext() else { return }
        let cachedReview: [ReviewItem]? = await cachedValue(
            [ReviewItem].self,
            database: context.database,
            namespace: Cache.review,
            key: "all"
        )
        let cachedPublishing: PublishQueue? = await cachedValue(
            PublishQueue.self,
            database: context.database,
            namespace: Cache.publishing,
            key: "all"
        )
        let cachedReviewBatch: ReviewBatchStatus? = await cachedValue(
            ReviewBatchStatus.self,
            database: context.database,
            namespace: Cache.reviewBatch,
            key: "active"
        )
        let cachedPublishBatch: PublishBatchStatus? = await cachedValue(
            PublishBatchStatus.self,
            database: context.database,
            namespace: Cache.publishBatch,
            key: "active"
        )
        if let cachedReview { reviewItems = cachedReview }
        if let cachedPublishing { publishQueue = cachedPublishing }
        if let cachedReviewBatch { reviewBatchStatus = cachedReviewBatch }
        if let cachedPublishBatch { publishBatchStatus = cachedPublishBatch }
        do {
            async let reviewRequest = api.reviewQueue()
            async let publishingRequest = api.publishQueue()
            let (review, publishing) = try await (reviewRequest, publishingRequest)
            reviewItems = review
            publishQueue = publishing
            try await cache(review, database: context.database, namespace: Cache.review, key: "all", lifetime: 2 * 60)
            try await cache(publishing, database: context.database, namespace: Cache.publishing, key: "all", lifetime: 2 * 60)
        } catch {
            if cachedReview == nil && cachedPublishing == nil { errorMessage = readable(error) }
        }
        if let cachedReviewBatch, !Self.batchFinished(cachedReviewBatch.state) {
            Task { @MainActor [weak self] in await self?.resumeReviewBatch(cachedReviewBatch) }
        }
        if let cachedPublishBatch, !Self.batchFinished(cachedPublishBatch.state) {
            Task { @MainActor [weak self] in await self?.resumePublishBatch(cachedPublishBatch) }
        }
    }

    @discardableResult
    func startReviewBatchRecommendations() async -> Bool {
        guard !isReviewBatchWorking else { return false }
        let waiting = reviewItems.filter { $0.candidates.isEmpty }
        let groups = buildReviewPhotoGroups(waiting).map(\.photoIds)
        guard !groups.isEmpty else {
            errorMessage = "Every photo in this review queue already has a suggestion."
            return false
        }
        guard groups.count <= REVIEW_BATCH_MAX_GROUPS_PER_JOB else {
            errorMessage = "Choose fewer than \(REVIEW_BATCH_MAX_GROUPS_PER_JOB) identification groups at a time."
            return false
        }
        isReviewBatchWorking = true
        errorMessage = nil
        let existingSpecies = species
        defer { isReviewBatchWorking = false }
        do {
            let initial = try await api.startReviewBatch(
                groups: groups,
                clientRequestID: UUID().uuidString.lowercased()
            )
            reviewBatchStatus = initial
            await persistReviewBatch(initial)
            let completed = try await pollReviewBatch(initial)
            reviewBatchStatus = completed
            await persistReviewBatch(completed)
            guard completed.state == "completed" else {
                throw JournalStoreError.invalidResponse(
                    completed.error ?? "Species recommendations could not complete."
                )
            }
            pendingCelebration = buildReviewBatchCelebration(
                status: completed,
                existingSpecies: existingSpecies
            )
            await refreshReviewQueue()
            return true
        } catch is CancellationError {
            return false
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    @discardableResult
    func startPublishBatch(options: PublishOptions) async -> Bool {
        guard !isPublishBatchWorking else { return false }
        guard publishQueue?.connected == true else {
            errorMessage = "Connect iNaturalist before publishing."
            return false
        }
        let ready = publishQueue?.items.filter { $0.state == "ready" } ?? []
        let groups = buildPublishObservationGroups(ready).flatMap { group in
            stride(from: 0, to: group.observationIds.count, by: GROUPED_PUBLISH_MAX_PHOTOS).map { start in
                Array(group.observationIds[start..<min(start + GROUPED_PUBLISH_MAX_PHOTOS, group.observationIds.count)])
            }
        }
        guard !groups.isEmpty else {
            errorMessage = "There are no confirmed observations waiting to publish."
            return false
        }
        guard groups.count <= 50 else {
            errorMessage = "Choose fewer than 50 publishing groups at a time."
            return false
        }
        isPublishBatchWorking = true
        errorMessage = nil
        defer { isPublishBatchWorking = false }
        do {
            let initial = try await api.startPublishBatch(
                groups: groups,
                options: options,
                clientRequestID: UUID().uuidString.lowercased()
            )
            publishBatchStatus = initial
            await persistPublishBatch(initial)
            let completed = try await pollPublishBatch(initial)
            publishBatchStatus = completed
            await persistPublishBatch(completed)
            guard completed.state == "completed" else {
                throw JournalStoreError.invalidResponse(
                    completed.error ?? completed.errors.first ?? "iNaturalist publishing could not complete."
                )
            }
            await refreshPublishQueue()
            return true
        } catch is CancellationError {
            return false
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    private func resumeReviewBatch(_ saved: ReviewBatchStatus) async {
        guard !isReviewBatchWorking else { return }
        isReviewBatchWorking = true
        defer { isReviewBatchWorking = false }
        do {
            let completed = try await pollReviewBatch(saved)
            reviewBatchStatus = completed
            await persistReviewBatch(completed)
            if completed.state == "completed" {
                pendingCelebration = buildReviewBatchCelebration(
                    status: completed,
                    existingSpecies: species
                )
                await refreshReviewQueue()
            } else {
                errorMessage = completed.error ?? "Species recommendations need attention."
            }
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readable(error)
        }
    }

    private func resumePublishBatch(_ saved: PublishBatchStatus) async {
        guard !isPublishBatchWorking else { return }
        isPublishBatchWorking = true
        defer { isPublishBatchWorking = false }
        do {
            let completed = try await pollPublishBatch(saved)
            publishBatchStatus = completed
            await persistPublishBatch(completed)
            if completed.state == "completed" {
                await refreshPublishQueue()
            } else {
                errorMessage = completed.error ?? completed.errors.first ?? "Publishing needs attention."
            }
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readable(error)
        }
    }

    private func pollReviewBatch(_ initial: ReviewBatchStatus) async throws -> ReviewBatchStatus {
        var status = initial
        for _ in 0..<600 {
            if Self.batchFinished(status.state) { return status }
            try await Task.sleep(for: .milliseconds(1_500))
            status = try await api.reviewBatchStatus(jobID: status.jobId)
            reviewBatchStatus = status
            await persistReviewBatch(status)
        }
        throw JournalStoreError.invalidResponse("Species identification is still running. Return to Review to resume its status check.")
    }

    private func pollPublishBatch(_ initial: PublishBatchStatus) async throws -> PublishBatchStatus {
        var status = initial
        for _ in 0..<600 {
            if Self.batchFinished(status.state) { return status }
            try await Task.sleep(for: .milliseconds(1_500))
            status = try await api.publishBatchStatus(jobID: status.jobId)
            publishBatchStatus = status
            await persistPublishBatch(status)
        }
        throw JournalStoreError.invalidResponse("Publishing is still running. Return to iNaturalist to resume its status check.")
    }

    private func refreshReviewQueue() async {
        guard let context = await accountContext() else { return }
        do {
            let value = try await api.reviewQueue()
            reviewItems = value
            try await cache(value, database: context.database, namespace: Cache.review, key: "all", lifetime: 2 * 60)
        } catch {
            errorMessage = readable(error)
        }
    }

    private func refreshPublishQueue() async {
        guard let context = await accountContext() else { return }
        do {
            let value = try await api.publishQueue()
            publishQueue = value
            try await cache(value, database: context.database, namespace: Cache.publishing, key: "all", lifetime: 2 * 60)
        } catch {
            errorMessage = readable(error)
        }
    }

    private func persistReviewBatch(_ status: ReviewBatchStatus) async {
        guard let context = await accountContext() else { return }
        try? await cache(status, database: context.database, namespace: Cache.reviewBatch, key: "active", lifetime: 7 * 24 * 60 * 60)
    }

    private func persistPublishBatch(_ status: PublishBatchStatus) async {
        guard let context = await accountContext() else { return }
        try? await cache(status, database: context.database, namespace: Cache.publishBatch, key: "active", lifetime: 7 * 24 * 60 * 60)
    }

    private static func batchFinished(_ state: String) -> Bool {
        ["completed", "failed", "cancelled"].contains(state.lowercased())
    }

    @discardableResult
    func requestReviewRecommendation(photoID: String) async -> ReviewItem? {
        do {
            let item = try await api.requestReviewRecommendation(photoID: photoID)
            if let index = reviewItems.firstIndex(where: { $0.id == item.id || $0.photo.id == photoID }) {
                reviewItems[index] = item
            } else {
                reviewItems.insert(item, at: 0)
            }
            return item
        } catch {
            errorMessage = readable(error)
            return nil
        }
    }

    @discardableResult
    func identifyPhotoWithINaturalist(photoID: String, hikeID: String) async -> ReviewItem? {
        let queued = details[hikeID]?.photos.first { $0.id == photoID }?.processingStatus == "in_review"
        if !queued {
            guard await queueSpeciesReview(photoID: photoID, hikeID: hikeID, queued: true) else {
                return nil
            }
        }
        return await requestReviewRecommendation(photoID: photoID)
    }

    @discardableResult
    func decideReview(
        photoID: String,
        observationID: String?,
        action: String,
        candidate: ReviewCandidate? = nil
    ) async -> Bool {
        let reviewedItem = reviewItems.first { $0.photo.id == photoID || $0.id == photoID }
        let existingSpecies = species
        do {
            let response = try await api.decideReview(
                photoID: photoID,
                observationID: observationID,
                action: action,
                candidate: candidate
            )
            guard response.ok else { return false }
            reviewItems.removeAll { $0.photo.id == photoID || $0.id == photoID }
            if action == "confirm", let candidate, let reviewedItem {
                pendingCelebration = buildConfirmedSpeciesCelebration(
                    candidate: candidate,
                    photo: reviewedItem.photo,
                    observedOn: reviewedItem.photo.takenAt ?? reviewedItem.photo.createdAt,
                    existingSpecies: existingSpecies
                )
            }
            await refreshFieldGuide()
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    @discardableResult
    func publishObservation(id: String, options: PublishOptions) async -> PublishItem? {
        do {
            let item = try await api.publishObservation(id: id, options: options)
            if var queue = publishQueue {
                let items = queue.items.map { $0.id == item.id ? item : $0 }
                queue = PublishQueue(
                    connected: queue.connected,
                    readyCount: max(0, queue.readyCount - (item.state == "posted" ? 1 : 0)),
                    needsAttentionCount: queue.needsAttentionCount,
                    postedCount: queue.postedCount + (item.state == "posted" ? 1 : 0),
                    items: items
                )
                publishQueue = queue
            }
            return item
        } catch {
            errorMessage = readable(error)
            return nil
        }
    }

    func inaturalistAuthorizationURL() async throws -> URL {
        try await api.inaturalistAuthorizationURL()
    }

    func speciesDetail(key: String) async throws -> SpeciesRecord {
        guard let context = await accountContext() else { throw APIClientError.sessionRequired }
        if let cached: SpeciesRecord = await cachedValue(
            SpeciesRecord.self,
            database: context.database,
            namespace: Cache.speciesDetail,
            key: key
        ), let resource = try? await context.database.cachedResource(
            namespace: Cache.speciesDetail,
            key: key
        ), resource.isFresh(at: Date()) {
            return cached
        }
        do {
            let value = try await api.speciesDetail(key: key)
            try await cache(value, database: context.database, namespace: Cache.speciesDetail, key: key, lifetime: 24 * 60 * 60)
            return value
        } catch {
            if let cached: SpeciesRecord = await cachedValue(
                SpeciesRecord.self,
                database: context.database,
                namespace: Cache.speciesDetail,
                key: key
            ) { return cached }
            throw error
        }
    }

    func placeProfile(
        id: String,
        riverDays: Int = 7,
        followedGaugeIDs: [String] = [],
        force: Bool = false
    ) async throws -> LoadResult<PlaceProfile> {
        guard authentication.entitlement?.allows("place_profiles") != false else {
            throw JournalStoreError.plusRequired("Place Profiles")
        }
        guard let context = await accountContext() else { throw APIClientError.sessionRequired }
        let normalizedRiverDays = riverDays >= 30 ? 30 : 7
        let normalizedGaugeIDs = Array(
            Set(followedGaugeIDs.map { $0.trimmingCharacters(in: .whitespacesAndNewlines).uppercased() })
        ).filter { !$0.isEmpty }.sorted()
        let cacheKey = "\(id)|\(normalizedRiverDays)|\(normalizedGaugeIDs.joined(separator: ","))"
        let cached: PlaceProfile? = await cachedValue(
            PlaceProfile.self,
            database: context.database,
            namespace: Cache.placeProfile,
            key: cacheKey
        )
        if !force,
           let cached,
           let resource = try? await context.database.cachedResource(namespace: Cache.placeProfile, key: cacheKey),
           resource.isFresh(at: Date()) {
            return LoadResult(value: cached, fromCache: true)
        }
        do {
            async let profileRequest = api.placeProfile(id: id)
            async let conditionsRequest = try? api.placeConditions(
                id: id,
                riverDays: normalizedRiverDays,
                followedGaugeIDs: normalizedGaugeIDs
            )
            let base = try await profileRequest
            let conditions = await conditionsRequest
            let value = conditions.map(base.withConditions) ?? base
            try await cache(value, database: context.database, namespace: Cache.placeProfile, key: cacheKey, lifetime: 30 * 60)
            return LoadResult(value: value, fromCache: false)
        } catch {
            if let cached { return LoadResult(value: cached, fromCache: true) }
            throw error
        }
    }

    func fieldBriefing(
        locationID: String,
        date: String,
        iconicTaxa: [String],
        force: Bool = false
    ) async throws -> LoadResult<FieldBriefing> {
        guard authentication.entitlement?.allows("field_briefing") != false else {
            throw JournalStoreError.plusRequired("Field Briefing")
        }
        guard let context = await accountContext() else { throw APIClientError.sessionRequired }
        let key = [locationID, date, iconicTaxa.sorted().joined(separator: ",")].joined(separator: "|")
        let cached: FieldBriefing? = await cachedValue(
            FieldBriefing.self,
            database: context.database,
            namespace: Cache.briefing,
            key: key
        )
        if !force,
           let cached,
           let resource = try? await context.database.cachedResource(namespace: Cache.briefing, key: key),
           resource.isFresh(at: Date()) {
            return LoadResult(value: cached, fromCache: true)
        }
        do {
            let value = try await api.fieldBriefing(locationID: locationID, date: date, iconicTaxa: iconicTaxa)
            try await cache(value, database: context.database, namespace: Cache.briefing, key: key, lifetime: 6 * 60 * 60)
            return LoadResult(value: value, fromCache: false)
        } catch {
            if let cached { return LoadResult(value: cached, fromCache: true) }
            throw error
        }
    }

    func briefingSightings(
        briefing: FieldBriefing,
        item: BriefingItem
    ) async throws -> QuestSightingsMap {
        guard let taxonID = item.taxonId else {
            throw JournalStoreError.invalidResponse("This field note has no mapped taxon.")
        }
        let allItems = briefing.sections.flatMap(\.items)
        let nearby = NearbySpecies(
            areaId: briefing.areaId,
            areaName: briefing.areaName,
            latitude: briefing.latitude,
            longitude: briefing.longitude,
            radiusKm: briefing.radiusKm,
            targetDate: briefing.targetDate,
            periodLabel: briefing.periodLabel,
            iconicTaxon: nil,
            resultLimit: max(1, allItems.count),
            dataDensity: "normal",
            dataDensityMessage: "",
            sourceGuidance: defaultReportingFrequencyGuidance,
            fromCache: false,
            progress: DiscoveryProgress(),
            taxa: allItems.map { $0.toDiscoveryTaxon() }
        )
        return try await api.nearbySightings(nearby: nearby, taxonID: taxonID)
    }

    func comparison(hikeID: String, otherHikeID: String) async throws -> LoadResult<HikeComparison> {
        guard let context = await accountContext() else { throw APIClientError.sessionRequired }
        let key = [hikeID, otherHikeID].sorted().joined(separator: "|")
        let cached: HikeComparison? = await cachedValue(
            HikeComparison.self,
            database: context.database,
            namespace: Cache.comparison,
            key: key
        )
        do {
            let value = try await api.comparison(hikeID: hikeID, otherHikeID: otherHikeID)
            try await cache(value, database: context.database, namespace: Cache.comparison, key: key, lifetime: 24 * 60 * 60)
            return LoadResult(value: value, fromCache: false)
        } catch {
            if let cached { return LoadResult(value: cached, fromCache: true) }
            throw error
        }
    }

    @discardableResult
    func createHike(_ draft: HikeDraft) async -> String? {
        guard quotaAllowsNewHike else {
            errorMessage = "Your Free cloud journal is full. Delete a cloud hike or choose Plus to add another."
            return nil
        }
        guard let context = await accountContext() else { return nil }
        let hikeID = UUID().uuidString.lowercased()
        let previousHikes = hikes
        do {
            let data = try HikeJournalDomainJSON.encode(draft)
            let timestamp = Date()
            try await context.database.upsertOperation(
                PendingOperation(
                    id: UUID().uuidString.lowercased(),
                    kind: .createHike,
                    entityID: hikeID,
                    payload: data,
                    createdAt: timestamp,
                    updatedAt: timestamp
                )
            )
            let local = Hike.localDraft(id: hikeID, draft: draft)
            hikes.removeAll { $0.id == hikeID }
            hikes.insert(local, at: 0)
            details[hikeID] = local
            pendingCelebration = buildHikeMilestoneCelebration(
                previousHikes: previousHikes,
                updatedHikes: hikes,
                savedHike: local
            )
            await persistVisibleHikes(database: context.database)
            await sync?.workWasQueued()
            return hikeID
        } catch {
            errorMessage = readable(error)
            return nil
        }
    }

    func updateHike(id: String, draft: HikeDraft) async -> Bool {
        guard let context = await accountContext() else { return false }
        do {
            let data = try HikeJournalDomainJSON.encode(draft)
            let timestamp = Date()
            try await context.database.upsertOperation(
                PendingOperation(
                    id: UUID().uuidString.lowercased(),
                    kind: .updateHike,
                    entityID: id,
                    payload: data,
                    createdAt: timestamp,
                    updatedAt: timestamp
                )
            )
            hikes = hikes.map { $0.id == id ? $0.withDraft(draft) : $0 }
            if let detail = details[id] { details[id] = detail.withDraft(draft) }
            await persistVisibleHikes(database: context.database)
            await sync?.workWasQueued()
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    func setArchived(id: String, archived: Bool) async -> Bool {
        guard let context = await accountContext() else { return false }
        do {
            let payload = try JSONSerialization.data(
                withJSONObject: ["is_archived": archived],
                options: [.sortedKeys]
            )
            let timestamp = Date()
            try await context.database.deleteReplaceableOperation(kind: .archiveHike, entityID: id)
            try await context.database.upsertOperation(
                PendingOperation(
                    id: UUID().uuidString.lowercased(),
                    kind: .archiveHike,
                    entityID: id,
                    payload: payload,
                    createdAt: timestamp,
                    updatedAt: timestamp
                )
            )
            hikes = hikes.map { $0.id == id ? $0.withArchived(archived) : $0 }
            if let detail = details[id] { details[id] = detail.withArchived(archived) }
            await persistVisibleHikes(database: context.database)
            await sync?.workWasQueued()
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    func deleteHike(id: String) async -> Bool {
        guard let context = await accountContext() else { return false }
        do {
            let timestamp = Date()
            try await context.database.upsertOperation(
                PendingOperation(
                    id: UUID().uuidString.lowercased(),
                    kind: .deleteHike,
                    entityID: id,
                    createdAt: timestamp,
                    updatedAt: timestamp
                )
            )
            hikes.removeAll { $0.id == id }
            details[id] = nil
            await persistVisibleHikes(database: context.database)
            await sync?.workWasQueued()
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    func queuePhotoAction(
        kind: PendingOperationKind,
        photoID: String,
        hikeID: String,
        payload: [String: Any] = [:]
    ) async -> Bool {
        guard let context = await accountContext() else { return false }
        do {
            let body = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
            let timestamp = Date()
            try await context.database.upsertOperation(
                PendingOperation(
                    id: UUID().uuidString.lowercased(),
                    kind: kind,
                    entityID: kind == .setHikeCover ? hikeID : photoID,
                    parentID: kind == .setHikeCover ? nil : hikeID,
                    payload: body,
                    createdAt: timestamp,
                    updatedAt: timestamp
                )
            )
            if kind == .updateCaption, let caption = payload["caption"] as? String,
               let detail = details[hikeID] {
                details[hikeID] = detail.withPhotoCaption(photoID: photoID, caption: caption)
            } else if kind == .deletePhoto, let detail = details[hikeID] {
                details[hikeID] = detail.withoutPhoto(id: photoID)
            } else if kind == .setHikeCover {
                let selected = payload["photo_id"] as? String
                if let detail = details[hikeID] { details[hikeID] = detail.withCoverPhoto(id: selected) }
            }
            await sync?.workWasQueued(prioritizedPhotoID: photoID)
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    func queueRouteImport(fileURL: URL, hikeID: String) async -> Bool {
        guard let context = await accountContext(), let offlineStores else { return false }
        let accessed = fileURL.startAccessingSecurityScopedResource()
        defer { if accessed { fileURL.stopAccessingSecurityScopedResource() } }

        var destination: URL?
        do {
            let values = try fileURL.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
            guard values.isRegularFile == true else {
                throw JournalStoreError.invalidResponse("Choose a TCX route file.")
            }
            let size = values.fileSize ?? 0
            guard size > 0, size <= 30 * 1_024 * 1_024 else {
                throw JournalStoreError.invalidResponse("TCX files must be between 1 byte and 30 MB.")
            }
            let lowerName = fileURL.lastPathComponent.lowercased()
            guard lowerName.hasSuffix(".tcx") || lowerName.hasSuffix(".tcx.txt") || lowerName.hasSuffix(".xml") else {
                throw JournalStoreError.invalidResponse("Choose a .tcx or .xml route file.")
            }

            let routeDirectory = try await offlineStores.routesDirectory(canonicalUserID: context.userID)
            let suffix = fileURL.pathExtension.lowercased() == "xml" ? "xml" : "tcx"
            let ownedURL = routeDirectory.appendingPathComponent(
                "import-\(UUID().uuidString.lowercased()).\(suffix)",
                isDirectory: false
            )
            try FileManager.default.copyItem(at: fileURL, to: ownedURL)
            destination = ownedURL
            try FileManager.default.setAttributes(
                [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication],
                ofItemAtPath: ownedURL.path
            )
            var resourceValues = URLResourceValues()
            resourceValues.isExcludedFromBackup = true
            var mutableURL = ownedURL
            try mutableURL.setResourceValues(resourceValues)

            let timestamp = Date()
            let entityID = "route-import:\(hikeID)"
            try await context.database.deleteReplaceableOperation(kind: .uploadRoute, entityID: entityID)
            try await context.database.upsertOperation(
                PendingOperation(
                    id: UUID().uuidString.lowercased(),
                    kind: .uploadRoute,
                    entityID: entityID,
                    parentID: hikeID,
                    payload: try JSONSerialization.data(
                        withJSONObject: ["source_type": "hikejournal_ios_gps"],
                        options: [.sortedKeys]
                    ),
                    localFilePath: ownedURL.path,
                    contentType: "application/vnd.garmin.tcx+xml",
                    fileName: fileURL.lastPathComponent,
                    createdAt: timestamp,
                    updatedAt: timestamp
                )
            )
            await sync?.workWasQueued()
            return true
        } catch {
            if let destination { try? FileManager.default.removeItem(at: destination) }
            errorMessage = readable(error)
            return false
        }
    }

    func queueSpeciesReview(photoID: String, hikeID: String, queued: Bool) async -> Bool {
        guard let context = await accountContext() else { return false }
        do {
            let timestamp = Date()
            try await context.database.deleteReplaceableOperation(kind: .queueSpeciesReview, entityID: photoID)
            try await context.database.upsertOperation(
                PendingOperation(
                    id: UUID().uuidString.lowercased(),
                    kind: .queueSpeciesReview,
                    entityID: photoID,
                    parentID: hikeID,
                    payload: try JSONSerialization.data(
                        withJSONObject: ["queued": queued],
                        options: [.sortedKeys]
                    ),
                    createdAt: timestamp,
                    updatedAt: timestamp
                )
            )
            if let detail = details[hikeID] {
                details[hikeID] = detail.withPhotoProcessingStatus(
                    photoID: photoID,
                    status: queued ? "in_review" : "ready"
                )
            }
            await sync?.workWasQueued(prioritizedPhotoID: photoID)
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    func assignKnownSpecies(photoID: String, hikeID: String, species record: SpeciesRecord) async -> Bool {
        guard let context = await accountContext() else { return false }
        let rediscovery = details[hikeID]?.photos
            .first(where: { $0.id == photoID })
            .flatMap { buildKnownSpeciesRediscoveryCelebration(species: record, photo: $0) }
        do {
            let timestamp = Date()
            let payload: [String: Any] = [
                "taxon_id": record.taxonId ?? NSNull(),
                "common_name": record.commonName,
                "scientific_name": record.scientificName,
            ]
            try await context.database.upsertOperation(
                PendingOperation(
                    id: UUID().uuidString.lowercased(),
                    kind: .assignKnownSpecies,
                    entityID: photoID,
                    parentID: hikeID,
                    payload: try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]),
                    createdAt: timestamp,
                    updatedAt: timestamp
                )
            )
            if let detail = details[hikeID] {
                details[hikeID] = detail.withKnownSpecies(photoID: photoID, record: record)
            }
            pendingCelebration = rediscovery
            await sync?.workWasQueued(prioritizedPhotoID: photoID)
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    func updateNaturalHistory(
        observationID: String,
        hikeID: String,
        confidence: String,
        phenophases: [String]
    ) async -> Bool {
        guard let context = await accountContext() else { return false }
        do {
            let timestamp = Date()
            try await context.database.deleteReplaceableOperation(
                kind: .updateNaturalHistory,
                entityID: observationID
            )
            try await context.database.upsertOperation(
                PendingOperation(
                    id: UUID().uuidString.lowercased(),
                    kind: .updateNaturalHistory,
                    entityID: observationID,
                    parentID: hikeID,
                    payload: try JSONSerialization.data(
                        withJSONObject: [
                            "confidence": confidence,
                            "provenance": "user",
                            "phenophases": phenophases,
                        ],
                        options: [.sortedKeys]
                    ),
                    createdAt: timestamp,
                    updatedAt: timestamp
                )
            )
            if let detail = details[hikeID] {
                details[hikeID] = detail.withNaturalHistory(
                    observationID: observationID,
                    confidence: confidence,
                    phenophases: phenophases
                )
            }
            await sync?.workWasQueued()
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    func enrichWeather(hikeID: String, force: Bool = false) async -> Bool {
        guard authentication.entitlement?.allows("historical_weather") != false else {
            errorMessage = "Historical weather is included with Plus."
            return false
        }
        do {
            let weather = try await api.enrichWeather(hikeID: hikeID, force: force)
            if let detail = details[hikeID] { details[hikeID] = detail.withWeather(weather) }
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    func clearError() { errorMessage = nil }

    func clearFieldGuideError() { fieldGuideErrorMessage = nil }

    var quotaAllowsNewHike: Bool {
        guard let entitlement = authentication.entitlement,
              let limit = entitlement.limits.cloudHikes else { return true }
        return entitlement.usage.cloudHikes < limit
    }

    var remainingMediaAllowance: Int {
        guard let entitlement = authentication.entitlement,
              let limit = entitlement.limits.cloudMedia else { return 500 }
        return max(0, min(500, limit - entitlement.usage.cloudMedia))
    }

    private func accountChanged(_ phase: AuthenticationPhase) async {
        switch phase {
        case .restoring:
            return
        case .signedOut:
            accountTask?.cancel()
            accountTask = nil
            isPreparingAccount = false
            loadedAccountIdentity = nil
            clearAccountData()
        case let .signedIn(account):
            let identity = account.userID ?? account.subject
            // Authentication restore and startJournal can both observe the
            // same signed-in phase. Do not cancel the first network refresh
            // and then let the second call return on isRefreshingHikes.
            guard loadedAccountIdentity != identity || accountTask == nil else { return }
            accountTask?.cancel()
            loadedAccountIdentity = identity
            isPreparingAccount = true
            accountTask = Task { @MainActor [weak self] in
                await self?.refreshHikes()
                self?.isPreparingAccount = false
            }
        }
    }

    private func accountContext() async -> (userID: String, database: OfflineDatabase)? {
        guard case .signedIn(let account) = authentication.phase,
              let userID = account.userID,
              let offlineStores else { return nil }
        do {
            return (userID, try await offlineStores.database(canonicalUserID: userID))
        } catch {
            errorMessage = readable(error)
            return nil
        }
    }

    private func clearAccountData() {
        hikes = []
        details = [:]
        species = []
        sightings = []
        routes = []
        locations = []
        quests = []
        discoveryAreas = []
        nearbySpecies = nil
        reviewItems = []
        publishQueue = nil
        reviewBatchStatus = nil
        publishBatchStatus = nil
        isReviewBatchWorking = false
        isPublishBatchWorking = false
        showingCachedData = false
        statusMessage = nil
        errorMessage = nil
        fieldGuideStatusMessage = nil
        fieldGuideErrorMessage = nil
        pendingCelebration = nil
    }

    private func allPhotos(hikeID: String) async throws -> [Photo] {
        var result: [Photo] = []
        var offset = 0
        var seenOffsets = Set<Int>()
        while seenOffsets.insert(offset).inserted, result.count < 10_000 {
            try Task.checkCancellation()
            let page = try await api.hikePhotos(id: hikeID, offset: offset, limit: 100)
            result.append(contentsOf: page.photos)
            guard let next = page.nextOffset, next > offset else { break }
            offset = next
        }
        return result
    }

    private func cachedValue<Value: Codable & Sendable>(
        _ type: Value.Type,
        database: OfflineDatabase,
        namespace: String,
        key: String,
        requireFresh: Bool = false
    ) async -> Value? {
        guard let resource = try? await database.cachedResource(namespace: namespace, key: key),
              !requireFresh || resource.isFresh(at: Date()) else { return nil }
        return try? HikeJournalDomainJSON.decode(type, from: resource.payload)
    }

    private func cache<Value: Codable & Sendable>(
        _ value: Value,
        database: OfflineDatabase,
        namespace: String,
        key: String,
        lifetime: TimeInterval
    ) async throws {
        let now = Date()
        try await database.upsertCachedResource(
            CachedResource(
                namespace: namespace,
                key: key,
                payload: try HikeJournalDomainJSON.encode(value),
                storedAt: now,
                expiresAt: now.addingTimeInterval(lifetime)
            )
        )
    }

    private func persistVisibleHikes(database: OfflineDatabase) async {
        try? await cache(hikes, database: database, namespace: Cache.hikes, key: "all", lifetime: 5 * 60)
    }

    private func cacheVisibleQuests() async {
        guard let context = await accountContext() else { return }
        try? await cache(
            quests,
            database: context.database,
            namespace: Cache.quests,
            key: "all",
            lifetime: 5 * 60
        )
    }

    private func applyingPendingOperations(
        to remote: [Hike],
        database: OfflineDatabase
    ) async -> [Hike] {
        guard let operations = try? await database.operations() else { return remote }
        var result = remote
        for operation in operations.sorted(by: { $0.createdAt < $1.createdAt }) {
            switch operation.kind {
            case .createHike:
                if let draft = try? HikeJournalDomainJSON.decode(HikeDraft.self, from: operation.payload),
                   !result.contains(where: { $0.id == operation.entityID }) {
                    result.insert(.localDraft(id: operation.entityID, draft: draft), at: 0)
                }
            case .updateHike:
                if let draft = try? HikeJournalDomainJSON.decode(HikeDraft.self, from: operation.payload) {
                    result = result.map { $0.id == operation.entityID ? $0.withDraft(draft) : $0 }
                }
            case .archiveHike:
                if let object = try? JSONSerialization.jsonObject(with: operation.payload) as? [String: Any],
                   let archived = object["is_archived"] as? Bool {
                    result = result.map { $0.id == operation.entityID ? $0.withArchived(archived) : $0 }
                }
            case .deleteHike:
                result.removeAll { $0.id == operation.entityID }
            default:
                break
            }
        }
        return result.sorted { lhs, rhs in
            if lhs.hikeDate != rhs.hikeDate { return lhs.hikeDate > rhs.hikeDate }
            return lhs.title.localizedCaseInsensitiveCompare(rhs.title) == .orderedAscending
        }
    }

    private func readable(_ error: Error) -> String {
        if let localized = error as? LocalizedError,
           let message = localized.errorDescription,
           !message.isEmpty { return message }
        return "HikeJournal couldn't load that field page. Its saved data remains on this iPhone."
    }

    private enum Cache {
        static let hikes = "hikes"
        static let hike = "hike-detail"
        static let species = "species-v2"
        static let speciesDetail = "species-detail-v2"
        static let sightings = "sightings-v2"
        static let routes = "routes"
        static let locations = "locations"
        static let placeProfile = "place-profile"
        static let briefing = "field-briefing"
        static let comparison = "hike-comparison"
        static let quests = "quests"
        static let review = "review"
        static let publishing = "publishing"
        static let reviewBatch = "review-batch"
        static let publishBatch = "publish-batch"
    }
}

enum JournalStoreError: Error, LocalizedError, Equatable {
    case plusRequired(String)
    case invalidResponse(String)

    var errorDescription: String? {
        switch self {
        case .plusRequired(let feature): "\(feature) is included with HikeJournal Plus."
        case .invalidResponse(let message): message
        }
    }
}

private extension Hike {
    static func localDraft(id: String, draft: HikeDraft) -> Hike {
        Hike(
            id: id,
            title: draft.title,
            hikeDate: draft.hikeDate,
            distanceMiles: draft.distanceMiles,
            locationName: draft.locationName,
            notes: draft.notes,
            isArchived: false,
            coverUrl: "",
            photoCount: 0,
            speciesCount: 0,
            syncState: "queued",
            primaryLocationId: draft.locationId,
            primaryLocationName: draft.locationName
        )
    }

    func withDetails(
        photos: [Photo],
        routeSegments: [[RoutePoint]],
        durationSeconds: Int64?,
        routeStartedAt: String?,
        distanceMiles: Double?
    ) -> Hike {
        Hike(
            id: id,
            title: title,
            hikeDate: hikeDate,
            distanceMiles: distanceMiles,
            durationSeconds: durationSeconds,
            routeStartedAt: routeStartedAt,
            locationName: locationName,
            notes: notes,
            isArchived: isArchived,
            isStandalone: isStandalone,
            coverUrl: coverUrl,
            coverPhotoId: coverPhotoId,
            photoCount: photos.count,
            speciesCount: speciesCount,
            syncState: syncState,
            photos: photos,
            routeSegments: routeSegments,
            primaryLocationId: primaryLocationId,
            primaryLocationName: primaryLocationName,
            fieldMarks: fieldMarks,
            weather: weather
        )
    }

    func withDraft(_ draft: HikeDraft) -> Hike {
        Hike(
            id: id,
            title: draft.title,
            hikeDate: draft.hikeDate,
            distanceMiles: draft.distanceMiles,
            durationSeconds: durationSeconds,
            routeStartedAt: routeStartedAt,
            locationName: draft.locationName,
            notes: draft.notes,
            isArchived: isArchived,
            isStandalone: isStandalone,
            coverUrl: coverUrl,
            coverPhotoId: coverPhotoId,
            photoCount: photoCount,
            speciesCount: speciesCount,
            syncState: "queued",
            photos: photos,
            routeSegments: routeSegments,
            primaryLocationId: draft.locationId,
            primaryLocationName: draft.locationName,
            fieldMarks: fieldMarks,
            weather: weather
        )
    }

    func withArchived(_ value: Bool) -> Hike {
        Hike(
            id: id, title: title, hikeDate: hikeDate, distanceMiles: distanceMiles,
            durationSeconds: durationSeconds, routeStartedAt: routeStartedAt,
            locationName: locationName, notes: notes, isArchived: value,
            isStandalone: isStandalone, coverUrl: coverUrl, coverPhotoId: coverPhotoId,
            photoCount: photoCount, speciesCount: speciesCount, syncState: "queued",
            photos: photos, routeSegments: routeSegments, primaryLocationId: primaryLocationId,
            primaryLocationName: primaryLocationName, fieldMarks: fieldMarks, weather: weather
        )
    }

    func withWeather(_ value: WeatherSnapshot) -> Hike {
        Hike(
            id: id, title: title, hikeDate: hikeDate, distanceMiles: distanceMiles,
            durationSeconds: durationSeconds, routeStartedAt: routeStartedAt,
            locationName: locationName, notes: notes, isArchived: isArchived,
            isStandalone: isStandalone, coverUrl: coverUrl, coverPhotoId: coverPhotoId,
            photoCount: photoCount, speciesCount: speciesCount, syncState: syncState,
            photos: photos, routeSegments: routeSegments, primaryLocationId: primaryLocationId,
            primaryLocationName: primaryLocationName, fieldMarks: fieldMarks, weather: value
        )
    }

    func withPhotoCaption(photoID: String, caption: String) -> Hike {
        withPhotos(photos.map { $0.id == photoID ? $0.withCaption(caption) : $0 })
    }

    func withPhotoProcessingStatus(photoID: String, status: String) -> Hike {
        withPhotos(photos.map { $0.id == photoID ? $0.withProcessingStatus(status) : $0 })
    }

    func withKnownSpecies(photoID: String, record: SpeciesRecord) -> Hike {
        withPhotos(photos.map { $0.id == photoID ? $0.withKnownSpecies(record) : $0 })
    }

    func withNaturalHistory(
        observationID: String,
        confidence: String,
        phenophases: [String]
    ) -> Hike {
        withPhotos(photos.map {
            $0.withNaturalHistory(
                observationID: observationID,
                confidence: confidence,
                phenophases: phenophases
            )
        })
    }

    func withoutPhoto(id photoID: String) -> Hike {
        withPhotos(photos.filter { $0.id != photoID })
    }

    func withCoverPhoto(id photoID: String?) -> Hike {
        let selected = photos.first { $0.id == photoID }
        return Hike(
            id: id, title: title, hikeDate: hikeDate, distanceMiles: distanceMiles,
            durationSeconds: durationSeconds, routeStartedAt: routeStartedAt,
            locationName: locationName, notes: notes, isArchived: isArchived,
            isStandalone: isStandalone, coverUrl: selected?.url ?? coverUrl,
            coverPhotoId: photoID, photoCount: photoCount, speciesCount: speciesCount,
            syncState: "queued", photos: photos, routeSegments: routeSegments,
            primaryLocationId: primaryLocationId, primaryLocationName: primaryLocationName,
            fieldMarks: fieldMarks, weather: weather
        )
    }

    private func withPhotos(_ value: [Photo]) -> Hike {
        Hike(
            id: id, title: title, hikeDate: hikeDate, distanceMiles: distanceMiles,
            durationSeconds: durationSeconds, routeStartedAt: routeStartedAt,
            locationName: locationName, notes: notes, isArchived: isArchived,
            isStandalone: isStandalone, coverUrl: coverUrl, coverPhotoId: coverPhotoId,
            photoCount: value.count, speciesCount: speciesCount, syncState: "queued",
            photos: value, routeSegments: routeSegments, primaryLocationId: primaryLocationId,
            primaryLocationName: primaryLocationName, fieldMarks: fieldMarks, weather: weather
        )
    }
}

private extension Photo {
    func withCaption(_ value: String) -> Photo {
        Photo(
            id: id,
            hikeId: hikeId,
            url: url,
            caption: value,
            takenAt: takenAt,
            createdAt: createdAt,
            latitude: latitude,
            longitude: longitude,
            width: width,
            height: height,
            contentType: contentType,
            processingStatus: processingStatus,
            syncState: "queued",
            species: species
        )
    }

    func withProcessingStatus(_ value: String) -> Photo {
        Photo(
            id: id, hikeId: hikeId, url: url, caption: caption,
            takenAt: takenAt, createdAt: createdAt, latitude: latitude, longitude: longitude,
            width: width, height: height, contentType: contentType,
            processingStatus: value, syncState: "queued", species: species
        )
    }

    func withKnownSpecies(_ record: SpeciesRecord) -> Photo {
        let label = SpeciesLabel(
            commonName: record.commonName,
            scientificName: record.scientificName,
            status: "confirmed",
            isPrimary: true,
            taxonId: record.taxonId,
            wikipediaUrl: record.wikipediaUrl,
            wikipediaSummary: record.wikipediaSummary,
            confidence: "confident",
            provenance: "known_species",
            observedOn: takenAt,
            iconicTaxonName: record.iconicTaxonName
        )
        return Photo(
            id: id, hikeId: hikeId, url: url, caption: caption,
            takenAt: takenAt, createdAt: createdAt, latitude: latitude, longitude: longitude,
            width: width, height: height, contentType: contentType,
            processingStatus: "ready", syncState: "queued", species: [label] + species.filter { !$0.isPrimary }
        )
    }

    func withNaturalHistory(
        observationID: String,
        confidence: String,
        phenophases: [String]
    ) -> Photo {
        let labels = species.map { label in
            label.observationId == observationID
                ? label.withNaturalHistory(confidence: confidence, phenophases: phenophases)
                : label
        }
        return Photo(
            id: id, hikeId: hikeId, url: url, caption: caption,
            takenAt: takenAt, createdAt: createdAt, latitude: latitude, longitude: longitude,
            width: width, height: height, contentType: contentType,
            processingStatus: processingStatus, syncState: "queued", species: labels
        )
    }
}

private extension SpeciesLabel {
    func withNaturalHistory(confidence: String, phenophases: [String]) -> SpeciesLabel {
        SpeciesLabel(
            commonName: commonName,
            scientificName: scientificName,
            status: status,
            isPrimary: isPrimary,
            taxonId: taxonId,
            wikipediaUrl: wikipediaUrl,
            wikipediaSummary: wikipediaSummary,
            observationId: observationId,
            confidence: confidence,
            provenance: "user",
            observedOn: observedOn,
            phenophases: phenophases,
            identificationHistory: identificationHistory,
            iconicTaxonName: iconicTaxonName
        )
    }
}

private extension PlaceProfile {
    func withConditions(_ conditions: PlaceConditions) -> PlaceProfile {
        PlaceProfile(
            locationId: locationId,
            name: name,
            latitude: latitude,
            longitude: longitude,
            firstVisit: firstVisit,
            latestVisit: latestVisit,
            outingCount: outingCount,
            totalDistanceMiles: totalDistanceMiles,
            totalDurationSeconds: totalDurationSeconds,
            observationCount: observationCount,
            speciesCount: speciesCount,
            taxonCounts: taxonCounts,
            taxonGroups: taxonGroups,
            seasonalHistory: seasonalHistory,
            visits: visits,
            guidance: guidance,
            forecast: conditions.forecast,
            riverGauges: conditions.riverGauges,
            liveConditionsNotice: conditions.liveConditionsNotice
        )
    }
}
