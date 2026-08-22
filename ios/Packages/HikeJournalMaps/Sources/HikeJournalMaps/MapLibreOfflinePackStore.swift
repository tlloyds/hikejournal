#if os(iOS) && canImport(MapLibre) && canImport(UIKit)
  import Foundation
  @preconcurrency import MapLibre
  import UIKit

  /// Configures the URL session MapLibre creates for maps and offline packs.
  /// Call this before constructing any `MLNMapView` or accessing offline storage.
  @MainActor
  public enum MapLibreNetworkPolicyController {
    public static func configure(_ policy: OfflineNetworkPolicy) {
      let configuration = URLSessionConfiguration.default
      configuration.waitsForConnectivity = true
      switch policy {
      case .anyNetwork:
        configuration.allowsCellularAccess = true
        configuration.allowsExpensiveNetworkAccess = true
        configuration.allowsConstrainedNetworkAccess = true
      case .wifiOnly:
        configuration.allowsCellularAccess = false
        configuration.allowsExpensiveNetworkAccess = false
        configuration.allowsConstrainedNetworkAccess = false
      }
      MLNNetworkConfiguration.sharedManager.sessionConfiguration = configuration
    }
  }

  /// Serialized production owner for `MLNOfflineStorage` and tile-pyramid packs.
  /// Entitlement checks intentionally remain app-owned and must happen before calls
  /// to `create`; this actor has no client-controlled paid-state input.
  public actor MapLibreOfflinePackStore {
    private let driver: MapLibreOfflineDriver
    private let networkPolicy: OfflineNetworkPolicy
    private var reservedRegionKeys: Set<String> = []

    public init(
      networkPolicy: OfflineNetworkPolicy,
      maximumAllowedTiles: UInt64 = 50_000
    ) async {
      self.networkPolicy = networkPolicy
      driver = await MapLibreOfflineDriver(
        networkPolicy: networkPolicy,
        maximumAllowedTiles: maximumAllowedTiles
      )
    }

    public func create(
      _ request: OfflinePackRequest,
      automaticallyResume: Bool = true
    ) async throws -> OfflinePackSnapshot {
      guard request.networkPolicy == networkPolicy else {
        throw OfflineMapError.networkPolicyMismatch
      }
      guard !reservedRegionKeys.contains(request.regionKey) else {
        throw OfflineMapError.duplicatePack
      }
      reservedRegionKeys.insert(request.regionKey)
      defer { reservedRegionKeys.remove(request.regionKey) }
      return try await driver.create(request, automaticallyResume: automaticallyResume)
    }

    public func list() async throws -> [OfflinePackSnapshot] {
      try await driver.list()
    }

    public func status(id: UUID) async throws -> OfflinePackSnapshot {
      try await driver.status(id: id)
    }

    @discardableResult
    public func resume(id: UUID) async throws -> OfflinePackSnapshot {
      try await driver.resume(id: id)
    }

    @discardableResult
    public func suspend(id: UUID) async throws -> OfflinePackSnapshot {
      try await driver.suspend(id: id)
    }

    public func delete(id: UUID) async throws {
      try await driver.delete(id: id)
    }

    public func updates(id: UUID) async throws -> AsyncStream<OfflinePackSnapshot> {
      try await driver.updates(id: id)
    }

    public func totalStorageBytes() async -> UInt64 {
      await driver.totalStorageBytes()
    }
  }

  @MainActor
  private final class MapLibreOfflineDriver: NSObject {
    private let storage: MLNOfflineStorage
    private var failures: [UUID: OfflinePackFailure] = [:]
    private var watchers: [UUID: [UUID: AsyncStream<OfflinePackSnapshot>.Continuation]] = [:]

    init(networkPolicy: OfflineNetworkPolicy, maximumAllowedTiles: UInt64) {
      MapLibreNetworkPolicyController.configure(networkPolicy)
      storage = MLNOfflineStorage.shared
      super.init()
      storage.setMaximumAllowedMapboxTiles(maximumAllowedTiles)
      let center = NotificationCenter.default
      center.addObserver(
        self,
        selector: #selector(progressChanged(_:)),
        name: .MLNOfflinePackProgressChanged,
        object: nil
      )
      center.addObserver(
        self,
        selector: #selector(downloadFailed(_:)),
        name: .MLNOfflinePackError,
        object: nil
      )
      center.addObserver(
        self,
        selector: #selector(tileLimitReached(_:)),
        name: .MLNOfflinePackMaximumMapboxTilesReached,
        object: nil
      )
    }

    deinit {
      NotificationCenter.default.removeObserver(self)
    }

    func create(
      _ request: OfflinePackRequest,
      automaticallyResume: Bool
    ) async throws -> OfflinePackSnapshot {
      let existing = try await indexedPacks()
      guard existing[request.id] == nil,
        !existing.values.contains(where: { $0.context.regionKey == request.regionKey })
      else {
        throw OfflineMapError.duplicatePack
      }
      let context = OfflinePackContext(request: request)
      let contextData = try OfflinePackContextCodec.encode(context)
      let styleURL = try request.style.resolvedURL(credential: request.styleCredential)
      let region = MLNTilePyramidOfflineRegion(
        styleURL: styleURL,
        bounds: Self.sdkBounds(request.bounds),
        fromZoomLevel: request.minimumZoomLevel,
        toZoomLevel: request.maximumZoomLevel
      )
      let pack: MLNOfflinePack = try await withCheckedThrowingContinuation { continuation in
        storage.addPack(for: region, withContext: contextData) { pack, error in
          if let pack {
            continuation.resume(returning: pack)
          } else {
            continuation.resume(
              throwing: OfflineMapError.sdkFailure(
                error?.localizedDescription ?? "MapLibre did not create the offline pack."
              )
            )
          }
        }
      }
      if automaticallyResume {
        pack.resume()
      }
      return snapshot(pack: pack, context: context)
    }

    func list() async throws -> [OfflinePackSnapshot] {
      let packs = try await indexedPacks()
      return packs.values
        .map { snapshot(pack: $0.pack, context: $0.context) }
        .sorted { $0.context.createdAt < $1.context.createdAt }
    }

    func status(id: UUID) async throws -> OfflinePackSnapshot {
      let item = try await pack(id: id)
      if item.pack.state == .unknown {
        item.pack.requestProgress()
      }
      return snapshot(pack: item.pack, context: item.context)
    }

    func resume(id: UUID) async throws -> OfflinePackSnapshot {
      let item = try await pack(id: id)
      failures.removeValue(forKey: id)
      item.pack.resume()
      return snapshot(pack: item.pack, context: item.context)
    }

    func suspend(id: UUID) async throws -> OfflinePackSnapshot {
      let item = try await pack(id: id)
      item.pack.suspend()
      return snapshot(pack: item.pack, context: item.context)
    }

    func delete(id: UUID) async throws {
      let item = try await pack(id: id)
      try await withCheckedThrowingContinuation {
        (continuation: CheckedContinuation<Void, Error>) in
        storage.removePack(item.pack) { error in
          if let error {
            continuation.resume(throwing: OfflineMapError.sdkFailure(error.localizedDescription))
          } else {
            continuation.resume(returning: ())
          }
        }
      }
      failures.removeValue(forKey: id)
      if let continuations = watchers.removeValue(forKey: id)?.values {
        for continuation in continuations {
          continuation.finish()
        }
      }
    }

    func updates(id: UUID) async throws -> AsyncStream<OfflinePackSnapshot> {
      let item = try await pack(id: id)
      let watcherID = UUID()
      let initial = snapshot(pack: item.pack, context: item.context)
      item.pack.requestProgress()
      return AsyncStream(bufferingPolicy: .bufferingNewest(20)) { continuation in
        watchers[id, default: [:]][watcherID] = continuation
        continuation.yield(initial)
        continuation.onTermination = { [weak self] _ in
          Task { @MainActor in
            self?.removeWatcher(packID: id, watcherID: watcherID)
          }
        }
      }
    }

    func totalStorageBytes() -> UInt64 {
      storage.countOfBytesCompleted
    }

    private func removeWatcher(packID: UUID, watcherID: UUID) {
      watchers[packID]?.removeValue(forKey: watcherID)
      if watchers[packID]?.isEmpty == true {
        watchers.removeValue(forKey: packID)
      }
    }

    private func ensureStorageReady() async throws {
      for _ in 0..<200 {
        if storage.packs != nil { return }
        try await Task.sleep(for: .milliseconds(25))
      }
      throw OfflineMapError.storageUnavailable
    }

    private struct IndexedPack {
      let pack: MLNOfflinePack
      let context: OfflinePackContext
    }

    private func indexedPacks() async throws -> [UUID: IndexedPack] {
      try await ensureStorageReady()
      var result: [UUID: IndexedPack] = [:]
      for pack in storage.packs ?? [] {
        guard let context = try? OfflinePackContextCodec.decode(pack.context) else {
          continue
        }
        result[context.id] = IndexedPack(pack: pack, context: context)
      }
      return result
    }

    private func pack(id: UUID) async throws -> IndexedPack {
      guard let pack = try await indexedPacks()[id] else {
        throw OfflineMapError.packNotFound
      }
      return pack
    }

    private func snapshot(
      pack: MLNOfflinePack,
      context: OfflinePackContext
    ) -> OfflinePackSnapshot {
      let sdkProgress = pack.progress
      let progress = OfflinePackProgress(
        resourcesCompleted: sdkProgress.countOfResourcesCompleted,
        resourcesExpected: sdkProgress.countOfResourcesExpected,
        maximumResourcesExpected: sdkProgress.maximumResourcesExpected == UInt64.max
          ? nil
          : sdkProgress.maximumResourcesExpected,
        tilesCompleted: sdkProgress.countOfTilesCompleted,
        bytesCompleted: sdkProgress.countOfBytesCompleted,
        tileBytesCompleted: sdkProgress.countOfTileBytesCompleted
      )
      let failure = failures[context.id]
      let state: OfflinePackState
      if failure != nil {
        state = .failed
      } else {
        switch pack.state {
        case .unknown: state = .unknown
        case .inactive: state = .inactive
        case .active: state = .downloading
        case .complete: state = .complete
        case .invalid: state = .invalid
        @unknown default: state = .unknown
        }
      }
      return OfflinePackSnapshot(
        context: context,
        state: state,
        progress: progress,
        failure: failure,
        totalMapStorageBytes: storage.countOfBytesCompleted
      )
    }

    @objc private func progressChanged(_ notification: Notification) {
      guard let pack = notification.object as? MLNOfflinePack,
        let context = try? OfflinePackContextCodec.decode(pack.context)
      else {
        return
      }
      if pack.state == .complete {
        failures.removeValue(forKey: context.id)
      }
      publish(snapshot(pack: pack, context: context))
    }

    @objc private func downloadFailed(_ notification: Notification) {
      guard let pack = notification.object as? MLNOfflinePack,
        let context = try? OfflinePackContextCodec.decode(pack.context)
      else {
        return
      }
      let error = notification.userInfo?[MLNOfflinePackUserInfoKey.error] as? NSError
      failures[context.id] = OfflinePackFailure(
        code: error?.code,
        message: error?.localizedDescription ?? "MapLibre reported an offline download error.",
        isRecoverable: true
      )
      publish(snapshot(pack: pack, context: context))
    }

    @objc private func tileLimitReached(_ notification: Notification) {
      guard let pack = notification.object as? MLNOfflinePack,
        let context = try? OfflinePackContextCodec.decode(pack.context)
      else {
        return
      }
      let maximum = notification.userInfo?[MLNOfflinePackUserInfoKey.maximumCount] as? NSNumber
      failures[context.id] = OfflinePackFailure(
        code: nil,
        message: "The device offline tile limit was reached"
          + (maximum.map { " (\($0.uint64Value) tiles)." } ?? "."),
        isRecoverable: false
      )
      pack.suspend()
      publish(snapshot(pack: pack, context: context))
    }

    private func publish(_ snapshot: OfflinePackSnapshot) {
      if let continuations = watchers[snapshot.id]?.values {
        for continuation in continuations {
          continuation.yield(snapshot)
        }
      }
    }

    private static func sdkBounds(_ bounds: MapCoordinateBounds) -> MLNCoordinateBounds {
      let east = bounds.crossesAntimeridian ? bounds.east + 360 : bounds.east
      return MLNCoordinateBounds(
        sw: CLLocationCoordinate2D(latitude: bounds.south, longitude: bounds.west),
        ne: CLLocationCoordinate2D(latitude: bounds.north, longitude: east)
      )
    }
  }
#endif
