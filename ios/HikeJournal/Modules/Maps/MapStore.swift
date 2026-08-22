import Combine
import Foundation
import HikeJournalMaps

enum JournalMapError: Error, LocalizedError, Equatable {
    case providerConfigurationMissing
    case providerCredentialIncomplete
    case offlineStoreUnavailable
    case plusRequired
    case routeRequired

    var errorDescription: String? {
        switch self {
        case .providerConfigurationMissing:
            "A secure map style and its attribution must be configured before the map can open."
        case .providerCredentialIncomplete:
            "The map provider token and token query name must either both be configured or both be omitted."
        case .offlineStoreUnavailable:
            "Offline map storage is still preparing. Please try again in a moment."
        case .plusRequired:
            "Offline map regions are included with HikeJournal Plus."
        case .routeRequired:
            "Choose a recorded route with at least two GPS points."
        }
    }
}

@MainActor
final class MapStore: ObservableObject {
    @Published private(set) var style: MapStyleConfiguration?
    @Published private(set) var styleCredential: MapStyleCredential?
    @Published private(set) var offlinePacks: [OfflinePackSnapshot] = []
    @Published private(set) var totalStorageBytes: UInt64 = 0
    @Published private(set) var isStarting = false
    @Published private(set) var isManagingOfflinePacks = false
    @Published private(set) var statusMessage: String?
    @Published private(set) var errorMessage: String?
    @Published var selectedTrailOverlayIDs: Set<String> {
        didSet {
            selectedTrailOverlayIDs = selectedTrailOverlayIDs.intersection(Self.validTrailIDs)
            defaults.set(Array(selectedTrailOverlayIDs).sorted(), forKey: Self.trailPreferenceKey)
        }
    }

    let activeNetworkPolicy: OfflineNetworkPolicy

    private static let trailPreferenceKey = "maps.nationalScenicTrails.selected"
    private static let wifiPreferenceKey = "maps.offline.wifiOnly"
    private static let validTrailIDs = Set(NationalScenicTrailCatalog.all.map(\.id))

    private let configuration: AppConfiguration
    private let authentication: AuthenticationStore
    private let defaults: UserDefaults
    private var offlineStore: MapLibreOfflinePackStore?
    private var updateTasks: [UUID: Task<Void, Never>] = [:]

    init(
        configuration: AppConfiguration,
        authentication: AuthenticationStore,
        defaults: UserDefaults = .standard
    ) {
        self.configuration = configuration
        self.authentication = authentication
        self.defaults = defaults
        let savedTrails = Set(defaults.stringArray(forKey: Self.trailPreferenceKey) ?? [])
        selectedTrailOverlayIDs = savedTrails.intersection(Self.validTrailIDs)
        let wifiOnly = defaults.object(forKey: Self.wifiPreferenceKey) == nil
            ? true
            : defaults.bool(forKey: Self.wifiPreferenceKey)
        activeNetworkPolicy = wifiOnly ? .wifiOnly : .anyNetwork
    }

    func start() async {
        guard style == nil, !isStarting else { return }
        isStarting = true
        errorMessage = nil
        defer { isStarting = false }

        do {
            guard let styleURL = configuration.mapStyleURL,
                  let attributionTitle = configuration.mapAttributionTitle,
                  let attributionURL = configuration.mapAttributionURL else {
                throw JournalMapError.providerConfigurationMissing
            }
            let hasToken = configuration.mapStyleToken != nil
            let hasTokenName = configuration.mapStyleTokenQueryItemName != nil
            guard hasToken == hasTokenName else {
                throw JournalMapError.providerCredentialIncomplete
            }
            let attribution = try MapAttribution(
                id: "base-map",
                title: attributionTitle,
                url: attributionURL
            )
            let proposedStyle = try MapStyleConfiguration(
                id: "journal-map",
                styleURL: styleURL,
                attribution: attribution,
                tokenQueryItemName: configuration.mapStyleTokenQueryItemName
            )
            let proposedCredential = try configuration.mapStyleToken.map(MapStyleCredential.init)
            _ = try proposedStyle.resolvedURL(credential: proposedCredential)

            // MapLibre's URL-session policy is global. Constructing this owner first
            // guarantees it is set before SwiftUI can instantiate an MLNMapView.
            let store = await MapLibreOfflinePackStore(
                networkPolicy: activeNetworkPolicy,
                maximumAllowedTiles: 50_000
            )
            offlineStore = store
            styleCredential = proposedCredential
            style = proposedStyle
            await refreshOfflinePacks()
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readable(error)
        }
    }

    func refreshOfflinePacks() async {
        guard let offlineStore else { return }
        do {
            let values = try await offlineStore.list()
            offlinePacks = values.sorted { $0.context.createdAt > $1.context.createdAt }
            totalStorageBytes = await offlineStore.totalStorageBytes()
            reconcileObservers()
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readable(error)
        }
    }

    @discardableResult
    func createOfflinePack(
        name: String,
        coordinates: [GeoCoordinate],
        minimumZoomLevel: Double = 8,
        maximumZoomLevel: Double = 14
    ) async -> Bool {
        guard authentication.entitlement?.allows("offline_maps") == true else {
            errorMessage = JournalMapError.plusRequired.localizedDescription
            return false
        }
        guard let offlineStore, let style else {
            errorMessage = JournalMapError.offlineStoreUnavailable.localizedDescription
            return false
        }
        guard let bounds = Self.downloadBounds(for: coordinates) else {
            errorMessage = JournalMapError.routeRequired.localizedDescription
            return false
        }

        isManagingOfflinePacks = true
        errorMessage = nil
        statusMessage = nil
        defer { isManagingOfflinePacks = false }
        do {
            let request = try OfflinePackRequest(
                name: name,
                style: style,
                styleCredential: styleCredential,
                bounds: bounds,
                minimumZoomLevel: minimumZoomLevel,
                maximumZoomLevel: maximumZoomLevel,
                networkPolicy: activeNetworkPolicy
            )
            let snapshot = try await offlineStore.create(request)
            merge(snapshot)
            observe(packID: snapshot.id)
            statusMessage = "Downloading “\(snapshot.context.name)” for offline use."
            return true
        } catch is CancellationError {
            return false
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    func resume(packID: UUID) async {
        await manage(packID: packID) { store in
            try await store.resume(id: packID)
        }
    }

    func suspend(packID: UUID) async {
        await manage(packID: packID) { store in
            try await store.suspend(id: packID)
        }
    }

    func delete(packID: UUID) async {
        guard let offlineStore else { return }
        isManagingOfflinePacks = true
        errorMessage = nil
        defer { isManagingOfflinePacks = false }
        do {
            try await offlineStore.delete(id: packID)
            updateTasks.removeValue(forKey: packID)?.cancel()
            offlinePacks.removeAll { $0.id == packID }
            totalStorageBytes = await offlineStore.totalStorageBytes()
            statusMessage = "Offline region removed."
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readable(error)
        }
    }

    func clearMessages() {
        statusMessage = nil
        errorMessage = nil
    }

    static func downloadBounds(for coordinates: [GeoCoordinate]) -> MapCoordinateBounds? {
        guard coordinates.count >= 2,
              let fit = MapCameraFitter.fit(coordinates: coordinates),
              !fit.bounds.crossesAntimeridian else { return nil }
        let latitudePadding = max(0.015, fit.bounds.latitudeSpan * 0.15)
        let longitudePadding = max(0.015, fit.bounds.longitudeSpan * 0.15)
        let latitudeLimit = OfflineRegionValidationPolicy.webMercatorLatitudeLimit
        return try? MapCoordinateBounds(
            south: max(-latitudeLimit, fit.bounds.south - latitudePadding),
            west: max(-180, fit.bounds.west - longitudePadding),
            north: min(latitudeLimit, fit.bounds.north + latitudePadding),
            east: min(180, fit.bounds.east + longitudePadding)
        )
    }

    private func manage(
        packID: UUID,
        operation: (MapLibreOfflinePackStore) async throws -> OfflinePackSnapshot
    ) async {
        guard let offlineStore else { return }
        isManagingOfflinePacks = true
        errorMessage = nil
        defer { isManagingOfflinePacks = false }
        do {
            let snapshot = try await operation(offlineStore)
            merge(snapshot)
            observe(packID: snapshot.id)
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readable(error)
        }
    }

    private func reconcileObservers() {
        let liveIDs = Set(offlinePacks.map(\.id))
        for (id, task) in updateTasks where !liveIDs.contains(id) {
            task.cancel()
            updateTasks.removeValue(forKey: id)
        }
        for snapshot in offlinePacks where !snapshot.isComplete {
            observe(packID: snapshot.id)
        }
    }

    private func observe(packID: UUID) {
        guard updateTasks[packID] == nil, let offlineStore else { return }
        updateTasks[packID] = Task { [weak self] in
            do {
                let stream = try await offlineStore.updates(id: packID)
                for await snapshot in stream {
                    guard !Task.isCancelled else { return }
                    self?.merge(snapshot)
                    if snapshot.isComplete {
                        self?.statusMessage = "“\(snapshot.context.name)” is ready offline."
                    }
                }
            } catch is CancellationError {
                return
            } catch let error as OfflineMapError where error == .packNotFound {
                return
            } catch {
                self?.errorMessage = self?.readable(error)
            }
        }
    }

    private func merge(_ snapshot: OfflinePackSnapshot) {
        offlinePacks.removeAll { $0.id == snapshot.id }
        offlinePacks.append(snapshot)
        offlinePacks.sort { $0.context.createdAt > $1.context.createdAt }
        totalStorageBytes = max(snapshot.totalMapStorageBytes, totalStorageBytes)
    }

    private func readable(_ error: Error) -> String {
        if let localized = error as? LocalizedError,
           let description = localized.errorDescription,
           !description.isEmpty {
            return description
        }
        return "HikeJournal couldn't prepare the map. Please try again."
    }
}
