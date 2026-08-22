import Foundation
import HikeJournalPersistence
import XCTest

@testable import HikeJournalSync

final class SyncCoordinatorTests: XCTestCase {
  func testDependencyOrderingAndPhotoConcurrencyFollowPlanner() async throws {
    let start = Date(timeIntervalSince1970: 100)
    let operations = [
      operation(
        id: "route",
        kind: .uploadRoute,
        entityID: "route",
        parentID: "hike",
        createdAt: start
      ),
      operation(
        id: "field-mark",
        kind: .createFieldMark,
        entityID: "mark",
        parentID: "hike",
        payload: Data(#"{"wait_for_hike_create":true}"#.utf8),
        createdAt: start.addingTimeInterval(0.5)
      ),
      operation(
        id: "photo-1",
        kind: .uploadPhoto,
        entityID: "photo-1",
        parentID: "hike",
        createdAt: start.addingTimeInterval(1)
      ),
      operation(
        id: "photo-2",
        kind: .uploadPhoto,
        entityID: "photo-2",
        parentID: "hike",
        createdAt: start.addingTimeInterval(2)
      ),
      operation(
        id: "create",
        kind: .createHike,
        entityID: "hike",
        createdAt: start.addingTimeInterval(3)
      ),
    ]
    let store = MemoryOperationStore(operations)
    let probe = ExecutorProbe(delayNanoseconds: 30_000_000)
    let coordinator = coordinator(store: store, probe: probe, now: start.addingTimeInterval(10))

    let result = try await coordinator.drain()

    let starts = await probe.startedOperationIDs()
    let maximumPhotos = await probe.maximumConcurrentPhotos()
    XCTAssertEqual(Array(starts.prefix(3)), ["create", "route", "field-mark"])
    XCTAssertEqual(Set(starts.suffix(2)), Set(["photo-1", "photo-2"]))
    XCTAssertEqual(maximumPhotos, 2)
    XCTAssertEqual(
      result.completedOperationIDs,
      ["create", "route", "field-mark", "photo-1", "photo-2"]
    )
    XCTAssertEqual(result.schedulingHint, .noWork)
    let remaining = await store.all()
    XCTAssertTrue(remaining.isEmpty)
  }

  func testAtMostTwoPhotosRunAndProgressExposesActiveBatch() async throws {
    let start = Date(timeIntervalSince1970: 200)
    let operations = (0..<5).map { index in
      operation(
        id: "photo-\(index)",
        kind: .uploadPhoto,
        entityID: "photo-\(index)",
        parentID: "hike",
        createdAt: start.addingTimeInterval(Double(index))
      )
    }
    let store = MemoryOperationStore(operations)
    let probe = ExecutorProbe(delayNanoseconds: 25_000_000)
    let progress = ProgressProbe()
    let coordinator = SyncCoordinator(
      store: store.adapter(),
      executor: probe.executor(),
      clock: .fixed(start.addingTimeInterval(10)),
      jitter: .none,
      progressReporter: progress.reporter()
    )

    let result = try await coordinator.drain()

    let maximumPhotos = await probe.maximumConcurrentPhotos()
    let snapshots = await progress.all()
    XCTAssertEqual(maximumPhotos, 2)
    XCTAssertTrue(snapshots.contains { $0.syncingCount == 2 })
    XCTAssertFalse(snapshots.contains { $0.syncingCount > 2 })
    XCTAssertEqual(result.progress.totalPhotoUploads, 5)
    XCTAssertEqual(result.progress.completedPhotoUploads, 5)
    XCTAssertEqual(result.progress.remainingPhotoUploads, 0)
    XCTAssertEqual(result.progress.completedOperationCount, 5)
  }

  func testAcknowledgedHikeDeletionDiscardsBlockedChildrenBeforeIntent() async throws {
    let now = Date(timeIntervalSince1970: 250)
    let store = MemoryOperationStore([
      operation(id: "update", kind: .updateHike, entityID: "hike", createdAt: now),
      operation(
        id: "photo",
        kind: .uploadPhoto,
        entityID: "photo",
        parentID: "hike",
        localFilePath: "/durable/photo.jpg",
        createdAt: now.addingTimeInterval(1)
      ),
      operation(
        id: "delete",
        kind: .deleteHike,
        entityID: "hike",
        createdAt: now.addingTimeInterval(2)
      ),
    ])
    let probe = ExecutorProbe()
    let cleanup = CleanupProbe()
    let coordinator = SyncCoordinator(
      store: store.adapter(),
      executor: probe.executor(),
      clock: .fixed(now.addingTimeInterval(3)),
      jitter: .none,
      mediaCleanup: cleanup.cleanup()
    )

    let result = try await coordinator.drain()

    let starts = await probe.startedOperationIDs()
    let cleaned = await cleanup.operationIDs()
    let remaining = await store.all()
    XCTAssertEqual(starts, ["delete"])
    XCTAssertEqual(result.completedOperationIDs, ["delete"])
    XCTAssertEqual(cleaned, ["photo"])
    XCTAssertTrue(remaining.isEmpty)
  }

  func testStaleSyncingOperationRecoversAfterDatabaseRestart() async throws {
    let directory = FileManager.default.temporaryDirectory
      .appendingPathComponent(UUID().uuidString, isDirectory: true)
    try FileManager.default.createDirectory(
      at: directory,
      withIntermediateDirectories: true
    )
    defer { try? FileManager.default.removeItem(at: directory) }
    let databaseURL = directory.appendingPathComponent("offline.sqlite")
    let staleDate = Date(timeIntervalSince1970: 100)
    var database: OfflineDatabase? = try OfflineDatabase(path: databaseURL.path)
    try await database?.upsertOperation(
      operation(
        id: "crashed",
        kind: .updateHike,
        entityID: "hike",
        state: .syncing,
        attemptCount: 1,
        createdAt: staleDate,
        updatedAt: staleDate
      )
    )
    await database?.close()
    database = nil

    let reopened = try OfflineDatabase(path: databaseURL.path)
    let probe = ExecutorProbe()
    let coordinator = SyncCoordinator(
      store: .offlineDatabase(reopened),
      executor: probe.executor(),
      clock: .fixed(staleDate.addingTimeInterval(100)),
      jitter: .none,
      configuration: SyncCoordinatorConfiguration(staleSyncingInterval: 10)
    )

    let result = try await coordinator.drain()
    XCTAssertEqual(result.recoveredOperationIDs, ["crashed"])
    XCTAssertEqual(result.completedOperationIDs, ["crashed"])
    await reopened.close()

    let verified = try OfflineDatabase(path: databaseURL.path)
    let persisted = try await verified.operation(id: "crashed")
    XCTAssertNil(persisted)
    await verified.close()
  }

  func testPartialPhotoFailureKeepsOnlyFailedRowAndCleansOnlySuccess() async throws {
    let now = Date(timeIntervalSince1970: 300)
    let first = operation(
      id: "good",
      kind: .uploadPhoto,
      entityID: "good",
      parentID: "hike",
      localFilePath: "/durable/good.jpg",
      createdAt: now
    )
    let second = operation(
      id: "retry",
      kind: .uploadPhoto,
      entityID: "retry",
      parentID: "hike",
      localFilePath: "/durable/retry.jpg",
      createdAt: now.addingTimeInterval(1)
    )
    let store = MemoryOperationStore([first, second])
    let probe = ExecutorProbe(
      scriptedFailures: [
        "retry": [.retryableServer(statusCode: 503, message: "maintenance")]
      ]
    )
    let cleanup = CleanupProbe()
    let coordinator = SyncCoordinator(
      store: store.adapter(),
      executor: probe.executor(),
      clock: .fixed(now),
      jitter: .none,
      mediaCleanup: cleanup.cleanup(),
      configuration: SyncCoordinatorConfiguration(
        retryPolicy: SyncRetryPolicy(baseDelay: 2)
      )
    )

    let result = try await coordinator.drain()

    XCTAssertEqual(result.completedOperationIDs, ["good"])
    XCTAssertEqual(result.retryScheduledOperationIDs, ["retry"])
    XCTAssertEqual(result.schedulingHint, .after(now.addingTimeInterval(2)))
    let goodRow = await store.value(id: "good")
    let retryRow = await store.value(id: "retry")
    let cleaned = await cleanup.operationIDs()
    XCTAssertNil(goodRow)
    XCTAssertEqual(retryRow?.state, .queued)
    XCTAssertEqual(retryRow?.attemptCount, 1)
    XCTAssertEqual(cleaned, ["good"])
  }

  func testAuthenticationAndQuotaFailuresNeedAttentionWithoutRetrying() async throws {
    let now = Date(timeIntervalSince1970: 400)
    let authStore = MemoryOperationStore([
      operation(id: "auth", kind: .updateHike, entityID: "hike", createdAt: now)
    ])
    let authProbe = ExecutorProbe(
      scriptedFailures: ["auth": [.authenticationRequired()]]
    )
    let authCoordinator = coordinator(store: authStore, probe: authProbe, now: now)

    let authResult = try await authCoordinator.drain()
    let authRow = await authStore.value(id: "auth")
    XCTAssertEqual(authResult.schedulingHint, .requiresAuthentication)
    XCTAssertEqual(authResult.needsAttentionOperationIDs, ["auth"])
    XCTAssertEqual(authRow?.state, .needsAttention)

    let quotaStore = MemoryOperationStore([
      operation(
        id: "quota",
        kind: .uploadPhoto,
        entityID: "photo",
        parentID: "hike",
        createdAt: now
      )
    ])
    let quotaProbe = ExecutorProbe(
      scriptedFailures: ["quota": [.quotaExceeded(resource: "media")]]
    )
    let quotaCoordinator = coordinator(store: quotaStore, probe: quotaProbe, now: now)

    let quotaResult = try await quotaCoordinator.drain()
    let quotaRow = await quotaStore.value(id: "quota")
    XCTAssertEqual(quotaResult.schedulingHint, .needsUserAttention)
    XCTAssertEqual(quotaResult.needsAttentionOperationIDs, ["quota"])
    XCTAssertEqual(quotaRow?.state, .needsAttention)
  }

  func testIdempotencyKeySurvivesRetryAndRetryLimitIsBounded() async throws {
    let firstNow = Date(timeIntervalSince1970: 500)
    let store = MemoryOperationStore([
      operation(id: "stable-id", kind: .updateHike, entityID: "hike", createdAt: firstNow)
    ])
    let probe = ExecutorProbe(
      scriptedFailures: [
        "stable-id": [
          .retryableServer(statusCode: 503),
          .retryableServer(statusCode: 503),
        ]
      ]
    )
    let configuration = SyncCoordinatorConfiguration(
      retryPolicy: SyncRetryPolicy(
        maximumAttempts: 2,
        baseDelay: 2,
        maximumDelay: 10,
        maximumJitterFraction: 0
      )
    )
    let firstCoordinator = SyncCoordinator(
      store: store.adapter(),
      executor: probe.executor(),
      clock: .fixed(firstNow),
      jitter: .none,
      configuration: configuration
    )
    let firstResult = try await firstCoordinator.drain()
    XCTAssertEqual(firstResult.schedulingHint, .after(firstNow.addingTimeInterval(2)))

    let secondCoordinator = SyncCoordinator(
      store: store.adapter(),
      executor: probe.executor(),
      clock: .fixed(firstNow.addingTimeInterval(2)),
      jitter: .none,
      configuration: configuration
    )
    let secondResult = try await secondCoordinator.drain()

    let keys = await probe.idempotencyKeys()
    let row = await store.value(id: "stable-id")
    XCTAssertEqual(keys, ["stable-id", "stable-id"])
    XCTAssertEqual(secondResult.schedulingHint, .needsUserAttention)
    XCTAssertEqual(row?.state, .needsAttention)
    XCTAssertEqual(row?.attemptCount, 2)
  }

  func testCancellationRestoresQueuedStateAndNeverCleansMedia() async throws {
    let now = Date(timeIntervalSince1970: 600)
    let queued = operation(
      id: "cancel",
      kind: .uploadPhoto,
      entityID: "photo",
      parentID: "hike",
      localFilePath: "/durable/photo.jpg",
      createdAt: now
    )
    let store = MemoryOperationStore([queued])
    let executor = CancellableExecutorProbe()
    let cleanup = CleanupProbe()
    let coordinator = SyncCoordinator(
      store: store.adapter(),
      executor: executor.executor(),
      clock: .fixed(now),
      jitter: .none,
      mediaCleanup: cleanup.cleanup()
    )
    let task = Task { try await coordinator.drain() }
    await executor.waitUntilStarted()
    task.cancel()

    do {
      _ = try await task.value
      XCTFail("Expected cancellation")
    } catch is CancellationError {
      // Expected.
    }

    let row = await store.value(id: "cancel")
    let cleaned = await cleanup.operationIDs()
    XCTAssertEqual(row?.state, .queued)
    XCTAssertEqual(row?.attemptCount, 0)
    XCTAssertEqual(row?.updatedAt, now)
    XCTAssertTrue(cleaned.isEmpty)
  }

  func testCleanupWaitsForVerifiedDurableQueueDeletion() async throws {
    let now = Date(timeIntervalSince1970: 700)
    let queued = operation(
      id: "undeleted",
      kind: .uploadPhoto,
      entityID: "photo",
      parentID: "hike",
      localFilePath: "/durable/photo.jpg",
      createdAt: now
    )
    let store = MemoryOperationStore([queued], deleteBehavior: .ignore)
    let probe = ExecutorProbe()
    let cleanup = CleanupProbe()
    let coordinator = SyncCoordinator(
      store: store.adapter(),
      executor: probe.executor(),
      clock: .fixed(now),
      jitter: .none,
      mediaCleanup: cleanup.cleanup()
    )

    do {
      _ = try await coordinator.drain()
      XCTFail("Expected durable deletion verification to fail")
    } catch let error as SyncCoordinatorError {
      XCTAssertEqual(error, .queueDeletionWasNotDurable("undeleted"))
    }

    let row = await store.value(id: "undeleted")
    let cleaned = await cleanup.operationIDs()
    XCTAssertEqual(row?.state, .syncing)
    XCTAssertTrue(cleaned.isEmpty)
  }

  func testPrioritizedPhotoDrainsBeforeOlderPhoto() async throws {
    let now = Date(timeIntervalSince1970: 800)
    let store = MemoryOperationStore([
      operation(
        id: "older",
        kind: .uploadPhoto,
        entityID: "older-photo",
        parentID: "hike",
        createdAt: now
      ),
      operation(
        id: "priority",
        kind: .uploadPhoto,
        entityID: "priority-photo",
        parentID: "hike",
        createdAt: now.addingTimeInterval(1)
      ),
    ])
    let probe = ExecutorProbe()
    let coordinator = SyncCoordinator(
      store: store.adapter(),
      executor: probe.executor(),
      clock: .fixed(now.addingTimeInterval(2)),
      jitter: .none,
      configuration: SyncCoordinatorConfiguration(maximumParallelPhotoUploads: 1)
    )

    _ = try await coordinator.drain(prioritizedPhotoID: "priority-photo")

    let starts = await probe.startedOperationIDs()
    XCTAssertEqual(starts, ["priority", "older"])
  }

  func testOfflineDrainDoesNotTouchQueueOrExecutor() async throws {
    let now = Date(timeIntervalSince1970: 900)
    let queued = operation(
      id: "offline",
      kind: .updateHike,
      entityID: "hike",
      createdAt: now
    )
    let store = MemoryOperationStore([queued])
    let probe = ExecutorProbe()
    let coordinator = SyncCoordinator(
      store: store.adapter(),
      executor: probe.executor(),
      connectivity: .alwaysUnavailable,
      clock: .fixed(now),
      jitter: .none
    )

    let result = try await coordinator.drain()

    let row = await store.value(id: "offline")
    let starts = await probe.startedOperationIDs()
    XCTAssertEqual(result.schedulingHint, .whenConnectivityReturns)
    XCTAssertTrue(result.attemptedOperationIDs.isEmpty)
    XCTAssertEqual(row, queued)
    XCTAssertTrue(starts.isEmpty)
  }

  func testOfflineFailureDuringExecutionRestoresOriginalAttemptBudget() async throws {
    let now = Date(timeIntervalSince1970: 950)
    let queued = operation(
      id: "lost-network",
      kind: .updateHike,
      entityID: "hike",
      createdAt: now
    )
    let store = MemoryOperationStore([queued])
    let probe = ExecutorProbe(
      scriptedFailures: ["lost-network": [.offline(message: "connection lost")]]
    )
    let coordinator = coordinator(store: store, probe: probe, now: now)

    let result = try await coordinator.drain()

    let row = await store.value(id: "lost-network")
    XCTAssertEqual(result.schedulingHint, .whenConnectivityReturns)
    XCTAssertEqual(row?.state, .queued)
    XCTAssertEqual(row?.attemptCount, 0)
    XCTAssertEqual(row?.updatedAt, now)
    XCTAssertEqual(row?.lastError, "connection lost")
  }

  func testValidationFailureMovesDirectlyToNeedsAttention() async throws {
    let now = Date(timeIntervalSince1970: 975)
    let store = MemoryOperationStore([
      operation(id: "invalid", kind: .updateHike, entityID: "hike", createdAt: now)
    ])
    let probe = ExecutorProbe(
      scriptedFailures: ["invalid": [.validation(message: "Title is required.")]]
    )
    let coordinator = coordinator(store: store, probe: probe, now: now)

    let result = try await coordinator.drain()

    let row = await store.value(id: "invalid")
    XCTAssertEqual(result.schedulingHint, .needsUserAttention)
    XCTAssertEqual(row?.state, .needsAttention)
    XCTAssertEqual(row?.lastError, "Title is required.")
  }

  func testOperationsEnqueuedDuringDrainWaitForImmediateNextPass() async throws {
    let now = Date(timeIntervalSince1970: 990)
    let first = operation(
      id: "first-pass",
      kind: .updateHike,
      entityID: "first-hike",
      createdAt: now
    )
    let followup = operation(
      id: "next-pass",
      kind: .updateHike,
      entityID: "second-hike",
      createdAt: now.addingTimeInterval(1)
    )
    let store = MemoryOperationStore([first])
    let firstExecutor = SyncOperationExecutor { operation, _ in
      if operation.id == first.id {
        await store.insert(followup)
      }
      return .acknowledged
    }
    let firstCoordinator = SyncCoordinator(
      store: store.adapter(),
      executor: firstExecutor,
      clock: .fixed(now.addingTimeInterval(2)),
      jitter: .none
    )

    let firstResult = try await firstCoordinator.drain()
    XCTAssertEqual(firstResult.completedOperationIDs, ["first-pass"])
    XCTAssertEqual(firstResult.schedulingHint, .immediate)
    let retained = await store.value(id: "next-pass")
    XCTAssertNotNil(retained)

    let secondProbe = ExecutorProbe()
    let secondCoordinator = coordinator(
      store: store,
      probe: secondProbe,
      now: now.addingTimeInterval(2)
    )
    let secondResult = try await secondCoordinator.drain()
    XCTAssertEqual(secondResult.completedOperationIDs, ["next-pass"])
    XCTAssertEqual(secondResult.schedulingHint, .noWork)
  }

  func testRecentSyncingRowReturnsRecoverySchedulingHintWithoutReplay() async throws {
    let now = Date(timeIntervalSince1970: 1_000)
    let syncing = operation(
      id: "active",
      kind: .updateHike,
      entityID: "hike",
      state: .syncing,
      attemptCount: 1,
      createdAt: now.addingTimeInterval(-20),
      updatedAt: now.addingTimeInterval(-5)
    )
    let store = MemoryOperationStore([syncing])
    let probe = ExecutorProbe()
    let coordinator = SyncCoordinator(
      store: store.adapter(),
      executor: probe.executor(),
      clock: .fixed(now),
      jitter: .none,
      configuration: SyncCoordinatorConfiguration(staleSyncingInterval: 10)
    )

    let result = try await coordinator.drain()

    let starts = await probe.startedOperationIDs()
    XCTAssertEqual(result.schedulingHint, .after(now.addingTimeInterval(5)))
    XCTAssertTrue(starts.isEmpty)
  }

  func testFailureClassificationAndRetryDelayAreTypedAndBounded() {
    XCTAssertEqual(
      SyncExecutionFailure.classify(URLError(.notConnectedToInternet)),
      .offline(message: URLError(.notConnectedToInternet).localizedDescription)
    )
    let policy = SyncRetryPolicy(
      maximumAttempts: 5,
      baseDelay: 2,
      maximumDelay: 20,
      maximumJitterFraction: 0.5
    )
    XCTAssertEqual(policy.delay(forAttempt: 1, jitterUnitInterval: 0), 2)
    XCTAssertEqual(policy.delay(forAttempt: 2, jitterUnitInterval: 1), 6)
    XCTAssertEqual(policy.delay(forAttempt: 10, retryAfter: 100, jitterUnitInterval: 1), 20)
  }
}

private enum DeleteBehavior: Sendable {
  case normal
  case ignore
}

private actor MemoryOperationStore {
  private var values: [String: PendingOperation]
  private let deleteBehavior: DeleteBehavior

  init(
    _ operations: [PendingOperation],
    deleteBehavior: DeleteBehavior = .normal
  ) {
    self.values = Dictionary(uniqueKeysWithValues: operations.map { ($0.id, $0) })
    self.deleteBehavior = deleteBehavior
  }

  nonisolated func adapter() -> SyncOperationStore {
    SyncOperationStore(
      loadAll: { try await self.loadAll() },
      load: { id in try await self.load(id: id) },
      upsert: { operation in await self.insert(operation) },
      updateState: { id, state, attemptCount, updatedAt, lastError in
        try await self.update(
          id: id,
          state: state,
          attemptCount: attemptCount,
          updatedAt: updatedAt,
          lastError: lastError
        )
      },
      delete: { id in try await self.delete(id: id) }
    )
  }

  func all() -> [PendingOperation] {
    values.values.sorted {
      if $0.createdAt != $1.createdAt { return $0.createdAt < $1.createdAt }
      return $0.id < $1.id
    }
  }

  func value(id: String) -> PendingOperation? {
    values[id]
  }

  func insert(_ operation: PendingOperation) {
    values[operation.id] = operation
  }

  private func loadAll() throws -> [PendingOperation] {
    all()
  }

  private func load(id: String) throws -> PendingOperation? {
    values[id]
  }

  private func update(
    id: String,
    state: PendingOperationState,
    attemptCount: Int,
    updatedAt: Date,
    lastError: String?
  ) throws {
    guard let operation = values[id] else { return }
    values[id] = PendingOperation(
      id: operation.id,
      kind: operation.kind,
      entityID: operation.entityID,
      parentID: operation.parentID,
      payload: operation.payload,
      localFilePath: operation.localFilePath,
      contentType: operation.contentType,
      fileName: operation.fileName,
      state: state,
      attemptCount: attemptCount,
      createdAt: operation.createdAt,
      updatedAt: updatedAt,
      lastError: lastError
    )
  }

  private func delete(id: String) throws {
    guard deleteBehavior == .normal else { return }
    values[id] = nil
  }
}

private actor ExecutorProbe {
  private var failures: [String: [SyncExecutionFailure]]
  private let delayNanoseconds: UInt64
  private var starts: [String] = []
  private var keys: [String] = []
  private var activePhotos = 0
  private var maximumPhotos = 0

  init(
    scriptedFailures: [String: [SyncExecutionFailure]] = [:],
    delayNanoseconds: UInt64 = 0
  ) {
    self.failures = scriptedFailures
    self.delayNanoseconds = delayNanoseconds
  }

  nonisolated func executor() -> SyncOperationExecutor {
    SyncOperationExecutor { operation, key in
      try await self.execute(operation, key: key)
    }
  }

  func startedOperationIDs() -> [String] { starts }
  func idempotencyKeys() -> [String] { keys }
  func maximumConcurrentPhotos() -> Int { maximumPhotos }

  private func execute(
    _ operation: PendingOperation,
    key: SyncIdempotencyKey
  ) async throws -> SyncOperationAcknowledgement {
    starts.append(operation.id)
    keys.append(key.rawValue)
    if operation.kind == .uploadPhoto {
      activePhotos += 1
      maximumPhotos = max(maximumPhotos, activePhotos)
    }
    defer {
      if operation.kind == .uploadPhoto {
        activePhotos -= 1
      }
    }
    if delayNanoseconds > 0 {
      try await Task<Never, Never>.sleep(nanoseconds: delayNanoseconds)
    }
    if var operationFailures = failures[operation.id], !operationFailures.isEmpty {
      let failure = operationFailures.removeFirst()
      failures[operation.id] = operationFailures
      throw failure
    }
    return .acknowledged
  }
}

private actor CancellableExecutorProbe {
  private var started = false
  private var waiters: [CheckedContinuation<Void, Never>] = []

  nonisolated func executor() -> SyncOperationExecutor {
    SyncOperationExecutor { operation, _ in
      try await self.execute(operation)
    }
  }

  func waitUntilStarted() async {
    guard !started else { return }
    await withCheckedContinuation { continuation in
      waiters.append(continuation)
    }
  }

  private func execute(
    _ operation: PendingOperation
  ) async throws -> SyncOperationAcknowledgement {
    _ = operation
    started = true
    let continuations = waiters
    waiters.removeAll()
    for continuation in continuations {
      continuation.resume()
    }
    do {
      try await Task<Never, Never>.sleep(nanoseconds: 30_000_000_000)
    } catch {
      // URLSession commonly reports task cancellation as URLError.cancelled.
      throw URLError(.cancelled)
    }
    return .acknowledged
  }
}

private actor CleanupProbe {
  private var ids: [String] = []

  nonisolated func cleanup() -> SyncMediaCleanup {
    SyncMediaCleanup { operation in
      await self.record(operation.id)
    }
  }

  func operationIDs() -> [String] { ids }

  private func record(_ id: String) {
    ids.append(id)
  }
}

private actor ProgressProbe {
  private var snapshots: [SyncProgressSnapshot] = []

  nonisolated func reporter() -> SyncProgressReporter {
    SyncProgressReporter { snapshot in
      await self.record(snapshot)
    }
  }

  func all() -> [SyncProgressSnapshot] { snapshots }

  private func record(_ snapshot: SyncProgressSnapshot) {
    snapshots.append(snapshot)
  }
}

private func coordinator(
  store: MemoryOperationStore,
  probe: ExecutorProbe,
  now: Date
) -> SyncCoordinator {
  SyncCoordinator(
    store: store.adapter(),
    executor: probe.executor(),
    clock: .fixed(now),
    jitter: .none
  )
}

private func operation(
  id: String,
  kind: PendingOperationKind,
  entityID: String,
  parentID: String? = nil,
  payload: Data = Data("{}".utf8),
  localFilePath: String? = nil,
  state: PendingOperationState = .queued,
  attemptCount: Int = 0,
  createdAt: Date,
  updatedAt: Date? = nil,
  lastError: String? = nil
) -> PendingOperation {
  PendingOperation(
    id: id,
    kind: kind,
    entityID: entityID,
    parentID: parentID,
    payload: payload,
    localFilePath: localFilePath,
    contentType: localFilePath == nil ? nil : "image/jpeg",
    fileName: localFilePath == nil ? nil : "media.jpg",
    state: state,
    attemptCount: attemptCount,
    createdAt: createdAt,
    updatedAt: updatedAt ?? createdAt,
    lastError: lastError
  )
}
