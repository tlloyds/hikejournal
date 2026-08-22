import Foundation
import HikeJournalPersistence

public actor SyncCoordinator {
  private struct RecoveryResult: Sendable {
    let queuedOperationIDs: Set<String>
    let needsAttentionOperationIDs: [String]
  }

  private struct ExecutionResult: Sendable {
    enum Outcome: Sendable {
      case acknowledged
      case failed(SyncExecutionFailure)
      case cancelled
    }

    let operation: PendingOperation
    let attemptedCount: Int
    let outcome: Outcome
  }

  private let store: SyncOperationStore
  private let executor: SyncOperationExecutor
  private let connectivity: SyncConnectivityProvider
  private let clock: SyncClock
  private let jitter: SyncJitter
  private let mediaCleanup: SyncMediaCleanup
  private let progressReporter: SyncProgressReporter
  private let configuration: SyncCoordinatorConfiguration

  private var isDraining = false
  private var latestProgress = SyncProgressSnapshot()

  public init(
    store: SyncOperationStore,
    executor: SyncOperationExecutor,
    connectivity: SyncConnectivityProvider = .alwaysAvailable,
    clock: SyncClock = .system,
    jitter: SyncJitter = .deterministic,
    mediaCleanup: SyncMediaCleanup = .none,
    progressReporter: SyncProgressReporter = .none,
    configuration: SyncCoordinatorConfiguration = SyncCoordinatorConfiguration()
  ) {
    self.store = store
    self.executor = executor
    self.connectivity = connectivity
    self.clock = clock
    self.jitter = jitter
    self.mediaCleanup = mediaCleanup
    self.progressReporter = progressReporter
    self.configuration = configuration
  }

  public func currentProgress() -> SyncProgressSnapshot {
    latestProgress
  }

  /// Drains each currently eligible operation at most once and returns without
  /// sleeping. The app owns NWPathMonitor/BGTask integration and should follow
  /// the returned scheduling hint.
  public func drain(prioritizedPhotoID: String? = nil) async throws -> SyncDrainResult {
    guard !isDraining else {
      throw SyncCoordinatorError.drainAlreadyInProgress
    }
    isDraining = true
    defer { isDraining = false }

    var attemptedIDs: [String] = []
    var attemptedSet = Set<String>()
    var completedIDs: [String] = []
    var retryIDs: [String] = []
    var attentionIDs: [String] = []
    var cleanupFailures: [SyncCleanupFailure] = []
    var recoveredIDs = Set<String>()
    var earliestRetryDate: Date?
    var encounteredOffline = false
    var encounteredAuthentication = false
    var encounteredAttention = false
    var shouldStop = false

    let initialNow = clock.now()
    let initialOperations = try await store.loadAll()
    let recovery = try await recoverStaleOperations(
      initialOperations,
      now: initialNow
    )
    recoveredIDs = recovery.queuedOperationIDs
    attentionIDs.append(contentsOf: recovery.needsAttentionOperationIDs)
    encounteredAttention = !recovery.needsAttentionOperationIDs.isEmpty
    let afterRecovery = try await store.loadAll()
    let passOperationIDs = Set(afterRecovery.map(\.id))
    var totalPhotoUploads = afterRecovery.pendingPhotoUploadCount
    try await publishProgress(
      operations: afterRecovery,
      totalPhotoUploads: totalPhotoUploads,
      completedPhotoUploads: 0,
      completedOperations: 0,
      failedOperations: 0
    )

    while !shouldStop {
      try Task.checkCancellation()
      let now = clock.now()
      let operations = try await store.loadAll()
      totalPhotoUploads = max(
        totalPhotoUploads,
        completedIDs.photoCompletionCount(in: initialOperations + operations)
          + operations.pendingPhotoUploadCount
      )

      let plannerOperations = operations.map { operation in
        plannerProjection(
          operation,
          now: now,
          attemptedIDs: attemptedSet,
          recoveredIDs: recoveredIDs,
          allowedOperationIDs: passOperationIDs
        )
      }
      let batch = SyncQueuePlanner.nextBatch(
        from: plannerOperations,
        prioritizedPhotoID: prioritizedPhotoID,
        maximumParallelPhotoUploads: configuration.maximumParallelPhotoUploads
      )
      guard !batch.isEmpty else { break }

      guard await connectivity.status() == .available else {
        encounteredOffline = true
        break
      }

      var markedOperations: [PendingOperation] = []
      do {
        for projected in batch {
          try Task.checkCancellation()
          guard let operation = operations.first(where: { $0.id == projected.id }) else {
            throw SyncCoordinatorError.operationDisappeared(projected.id)
          }
          let attemptedCount = operation.attemptCount + 1
          markedOperations.append(operation)
          try await persistState(
            operation: operation,
            state: .syncing,
            attemptCount: attemptedCount,
            updatedAt: now,
            lastError: nil
          )
          attemptedIDs.append(operation.id)
          attemptedSet.insert(operation.id)
        }
      } catch {
        try await restoreUnexecutedOperations(markedOperations)
        if error is CancellationError {
          throw CancellationError()
        }
        throw error
      }

      try await publishProgress(
        operations: try await store.loadAll(),
        totalPhotoUploads: totalPhotoUploads,
        completedPhotoUploads: completedIDs.photoCompletionCount(
          in: initialOperations + operations),
        completedOperations: completedIDs.count,
        failedOperations: retryIDs.count + attentionIDs.count
      )

      let results = await execute(markedOperations)
      var batchWasCancelled = false
      for result in results {
        switch result.outcome {
        case .acknowledged:
          if result.operation.kind == .createHike {
            try await releaseRecordedHikeChildren(
              hikeID: result.operation.entityID,
              updatedAt: clock.now()
            )
          }
          if result.operation.kind == .deleteHike {
            cleanupFailures.append(
              contentsOf: try await discardAcknowledgedHikeChildren(result.operation)
            )
          }
          try await deleteAcknowledgedOperation(result.operation)
          completedIDs.append(result.operation.id)
          if result.operation.hasDisposableLocalMedia {
            do {
              try await mediaCleanup.removeAcknowledgedMedia(for: result.operation)
            } catch {
              cleanupFailures.append(
                SyncCleanupFailure(
                  operationID: result.operation.id,
                  message: String(describing: error)
                )
              )
            }
          }

        case .failed(let failure):
          switch failure {
          case .offline:
            try await persistState(
              operation: result.operation,
              state: .queued,
              attemptCount: result.operation.attemptCount,
              updatedAt: result.operation.updatedAt,
              lastError: failure.userFacingMessage
            )
            encounteredOffline = true
            shouldStop = true

          case .authenticationRequired:
            try await persistState(
              operation: result.operation,
              state: .needsAttention,
              attemptCount: result.attemptedCount,
              updatedAt: clock.now(),
              lastError: failure.userFacingMessage
            )
            attentionIDs.append(result.operation.id)
            encounteredAuthentication = true
            shouldStop = true

          case .quotaExceeded, .validation, .permanentServer:
            try await persistState(
              operation: result.operation,
              state: .needsAttention,
              attemptCount: result.attemptedCount,
              updatedAt: clock.now(),
              lastError: failure.userFacingMessage
            )
            attentionIDs.append(result.operation.id)
            encounteredAttention = true

          case .retryableServer(_, let retryAfter, _):
            if result.attemptedCount >= configuration.retryPolicy.maximumAttempts {
              try await persistState(
                operation: result.operation,
                state: .needsAttention,
                attemptCount: result.attemptedCount,
                updatedAt: clock.now(),
                lastError: failure.userFacingMessage
              )
              attentionIDs.append(result.operation.id)
              encounteredAttention = true
            } else {
              let failedAt = clock.now()
              try await persistState(
                operation: result.operation,
                state: .queued,
                attemptCount: result.attemptedCount,
                updatedAt: failedAt,
                lastError: failure.userFacingMessage
              )
              retryIDs.append(result.operation.id)
              let retryDate = failedAt.addingTimeInterval(
                configuration.retryPolicy.delay(
                  forAttempt: result.attemptedCount,
                  retryAfter: retryAfter,
                  jitterUnitInterval: jitter.unitInterval(
                    operationID: result.operation.id,
                    attempt: result.attemptedCount
                  )
                )
              )
              earliestRetryDate = minDate(earliestRetryDate, retryDate)
            }
          }

        case .cancelled:
          try await persistState(
            operation: result.operation,
            state: .queued,
            attemptCount: result.operation.attemptCount,
            updatedAt: result.operation.updatedAt,
            lastError: result.operation.lastError
          )
          batchWasCancelled = true
        }
      }

      let currentOperations = try await store.loadAll()
      try await publishProgress(
        operations: currentOperations,
        totalPhotoUploads: totalPhotoUploads,
        completedPhotoUploads: completedIDs.photoCompletionCount(
          in: initialOperations + currentOperations
        ),
        completedOperations: completedIDs.count,
        failedOperations: retryIDs.count + attentionIDs.count
      )
      if batchWasCancelled || Task.isCancelled {
        throw CancellationError()
      }
    }

    let finalOperations = try await store.loadAll()
    let finalNow = clock.now()
    let hint = schedulingHint(
      operations: finalOperations,
      now: finalNow,
      attemptedIDs: attemptedSet,
      earliestRetryDate: earliestRetryDate,
      encounteredOffline: encounteredOffline,
      encounteredAuthentication: encounteredAuthentication,
      encounteredAttention: encounteredAttention
    )
    try await publishProgress(
      operations: finalOperations,
      totalPhotoUploads: totalPhotoUploads,
      completedPhotoUploads: completedIDs.photoCompletionCount(
        in: initialOperations + finalOperations
      ),
      completedOperations: completedIDs.count,
      failedOperations: retryIDs.count + attentionIDs.count
    )
    return SyncDrainResult(
      attemptedOperationIDs: attemptedIDs,
      completedOperationIDs: completedIDs,
      retryScheduledOperationIDs: retryIDs,
      needsAttentionOperationIDs: attentionIDs,
      recoveredOperationIDs: recoveredIDs.sorted(),
      cleanupFailures: cleanupFailures,
      schedulingHint: hint,
      progress: latestProgress
    )
  }

  private func execute(_ operations: [PendingOperation]) async -> [ExecutionResult] {
    let executor = self.executor
    return await withTaskGroup(
      of: ExecutionResult.self,
      returning: [ExecutionResult].self
    ) { group in
      for operation in operations {
        group.addTask {
          let attemptedCount = operation.attemptCount + 1
          do {
            _ = try await executor.execute(
              operation,
              idempotencyKey: SyncIdempotencyKey(operationID: operation.id)
            )
            return ExecutionResult(
              operation: operation,
              attemptedCount: attemptedCount,
              outcome: .acknowledged
            )
          } catch is CancellationError {
            return ExecutionResult(
              operation: operation,
              attemptedCount: attemptedCount,
              outcome: .cancelled
            )
          } catch {
            if Task.isCancelled {
              return ExecutionResult(
                operation: operation,
                attemptedCount: attemptedCount,
                outcome: .cancelled
              )
            }
            return ExecutionResult(
              operation: operation,
              attemptedCount: attemptedCount,
              outcome: .failed(SyncExecutionFailure.classify(error))
            )
          }
        }
      }

      var resultByID: [String: ExecutionResult] = [:]
      for await result in group {
        resultByID[result.operation.id] = result
      }
      return operations.compactMap { resultByID[$0.id] }
    }
  }

  private func recoverStaleOperations(
    _ operations: [PendingOperation],
    now: Date
  ) async throws -> RecoveryResult {
    var recovered = Set<String>()
    var needsAttention: [String] = []
    for operation in operations where operation.state == .syncing {
      guard now.timeIntervalSince(operation.updatedAt) >= configuration.staleSyncingInterval else {
        continue
      }
      if operation.attemptCount >= configuration.retryPolicy.maximumAttempts {
        try await persistState(
          operation: operation,
          state: .needsAttention,
          attemptCount: operation.attemptCount,
          updatedAt: now,
          lastError: "An interrupted sync reached the retry limit."
        )
        needsAttention.append(operation.id)
      } else {
        try await persistState(
          operation: operation,
          state: .queued,
          attemptCount: operation.attemptCount,
          updatedAt: now,
          lastError: "Recovered an interrupted sync attempt."
        )
        recovered.insert(operation.id)
      }
    }
    return RecoveryResult(
      queuedOperationIDs: recovered,
      needsAttentionOperationIDs: needsAttention
    )
  }

  private func plannerProjection(
    _ operation: PendingOperation,
    now: Date,
    attemptedIDs: Set<String>,
    recoveredIDs: Set<String>,
    allowedOperationIDs: Set<String>? = nil
  ) -> PendingOperation {
    let unavailableInThisPass =
      allowedOperationIDs.map {
        !$0.contains(operation.id)
      } ?? false
    let unavailable: Bool
    switch operation.state {
    case .syncing, .needsAttention:
      unavailable = true
    case .queued:
      unavailable =
        unavailableInThisPass || attemptedIDs.contains(operation.id)
        || (!recoveredIDs.contains(operation.id) && retryDate(for: operation) > now)
    }
    guard unavailable else { return operation }
    return operation.copying(state: .needsAttention)
  }

  private func retryDate(for operation: PendingOperation) -> Date {
    guard operation.attemptCount > 0 else { return .distantPast }
    return operation.updatedAt.addingTimeInterval(
      configuration.retryPolicy.delay(
        forAttempt: operation.attemptCount,
        jitterUnitInterval: jitter.unitInterval(
          operationID: operation.id,
          attempt: operation.attemptCount
        )
      )
    )
  }

  private func persistState(
    operation: PendingOperation,
    state: PendingOperationState,
    attemptCount: Int,
    updatedAt: Date,
    lastError: String?
  ) async throws {
    try await store.updateState(
      id: operation.id,
      state: state,
      attemptCount: attemptCount,
      updatedAt: updatedAt,
      lastError: lastError
    )
    guard let persisted = try await store.load(id: operation.id) else {
      throw SyncCoordinatorError.operationDisappeared(operation.id)
    }
    guard persisted.state == state,
      persisted.attemptCount == attemptCount,
      persisted.updatedAt == updatedAt,
      persisted.lastError == lastError
    else {
      throw SyncCoordinatorError.stateTransitionWasNotDurable(
        operationID: operation.id,
        expected: state.rawValue
      )
    }
  }

  private func deleteAcknowledgedOperation(_ operation: PendingOperation) async throws {
    try await store.delete(id: operation.id)
    guard try await store.load(id: operation.id) == nil else {
      throw SyncCoordinatorError.queueDeletionWasNotDurable(operation.id)
    }
  }

  private func releaseRecordedHikeChildren(
    hikeID: String,
    updatedAt: Date
  ) async throws {
    let operations = try await store.loadAll()
    for operation in operations
    where
      operation.kind == .createFieldMark && operation.parentID == hikeID
    {
      guard
        var object = (try? JSONSerialization.jsonObject(with: operation.payload))
          as? [String: Any],
        object["wait_for_hike_create"] as? Bool == true
      else {
        continue
      }
      object["wait_for_hike_create"] = false
      let payload = try JSONSerialization.data(
        withJSONObject: object,
        options: [.sortedKeys]
      )
      let released = operation.copying(payload: payload, updatedAt: updatedAt)
      try await store.upsert(released)
      guard try await store.load(id: operation.id) == released else {
        throw SyncCoordinatorError.operationReplacementWasNotDurable(operation.id)
      }
    }
  }

  /// The acknowledged hike deletion supersedes every queued child mutation.
  /// Children are durably removed first, leaving the delete intent replayable
  /// if the process is interrupted anywhere in this cleanup window.
  private func discardAcknowledgedHikeChildren(
    _ deletion: PendingOperation
  ) async throws -> [SyncCleanupFailure] {
    let children = try await store.loadAll().filter {
      $0.id != deletion.id && $0.targetHikeID == deletion.entityID
    }
    var failures: [SyncCleanupFailure] = []
    for child in children {
      try await deleteAcknowledgedOperation(child)
      guard child.hasDisposableLocalMedia else { continue }
      do {
        try await mediaCleanup.removeAcknowledgedMedia(for: child)
      } catch {
        failures.append(
          SyncCleanupFailure(
            operationID: child.id,
            message: String(describing: error)
          )
        )
      }
    }
    return failures
  }

  private func restoreUnexecutedOperations(_ operations: [PendingOperation]) async throws {
    for operation in operations {
      try await persistState(
        operation: operation,
        state: .queued,
        attemptCount: operation.attemptCount,
        updatedAt: operation.updatedAt,
        lastError: operation.lastError
      )
    }
  }

  private func schedulingHint(
    operations: [PendingOperation],
    now: Date,
    attemptedIDs: Set<String>,
    earliestRetryDate: Date?,
    encounteredOffline: Bool,
    encounteredAuthentication: Bool,
    encounteredAttention: Bool
  ) -> SyncSchedulingHint {
    if encounteredAuthentication { return .requiresAuthentication }
    if encounteredOffline { return .whenConnectivityReturns }

    let projected = operations.map {
      plannerProjection(
        $0,
        now: now,
        attemptedIDs: attemptedIDs,
        recoveredIDs: []
      )
    }
    if !SyncQueuePlanner.nextBatch(
      from: projected,
      maximumParallelPhotoUploads: configuration.maximumParallelPhotoUploads
    ).isEmpty {
      return .immediate
    }

    if let earliestRetryDate { return .after(earliestRetryDate) }
    if encounteredAttention || operations.contains(where: { $0.state == .needsAttention }) {
      return .needsUserAttention
    }

    let nonStaleSyncDates = operations.compactMap { operation -> Date? in
      guard operation.state == .syncing else { return nil }
      return operation.updatedAt.addingTimeInterval(configuration.staleSyncingInterval)
    }
    if let recoveryDate = nonStaleSyncDates.min() {
      return .after(recoveryDate)
    }

    let queuedRetryDates = operations.compactMap { operation -> Date? in
      guard operation.state == .queued,
        operation.attemptCount > 0,
        !attemptedIDs.contains(operation.id)
      else { return nil }
      return retryDate(for: operation)
    }
    if let retryDate = queuedRetryDates.filter({ $0 > now }).min() {
      return .after(retryDate)
    }

    return .noWork
  }

  private func publishProgress(
    operations: [PendingOperation],
    totalPhotoUploads: Int,
    completedPhotoUploads: Int,
    completedOperations: Int,
    failedOperations: Int
  ) async throws {
    latestProgress = SyncProgressSnapshot(
      queuedCount: operations.count { $0.state == .queued },
      syncingCount: operations.count { $0.state == .syncing },
      needsAttentionCount: operations.count { $0.state == .needsAttention },
      totalPhotoUploads: totalPhotoUploads,
      completedPhotoUploads: completedPhotoUploads,
      remainingPhotoUploads: operations.pendingPhotoUploadCount,
      completedOperationCount: completedOperations,
      failedOperationCount: failedOperations,
      activeOperationIDs:
        operations
        .filter { $0.state == .syncing }
        .map(\.id)
        .sorted()
    )
    await progressReporter.report(latestProgress)
  }
}

extension PendingOperation {
  fileprivate var hasDisposableLocalMedia: Bool {
    localFilePath != nil && (kind == .uploadPhoto || kind == .uploadRoute)
  }

  fileprivate func copying(state: PendingOperationState) -> PendingOperation {
    PendingOperation(
      id: id,
      kind: kind,
      entityID: entityID,
      parentID: parentID,
      payload: payload,
      localFilePath: localFilePath,
      contentType: contentType,
      fileName: fileName,
      state: state,
      attemptCount: attemptCount,
      createdAt: createdAt,
      updatedAt: updatedAt,
      lastError: lastError
    )
  }

  fileprivate func copying(payload: Data, updatedAt: Date) -> PendingOperation {
    PendingOperation(
      id: id,
      kind: kind,
      entityID: entityID,
      parentID: parentID,
      payload: payload,
      localFilePath: localFilePath,
      contentType: contentType,
      fileName: fileName,
      state: state,
      attemptCount: attemptCount,
      createdAt: createdAt,
      updatedAt: updatedAt,
      lastError: lastError
    )
  }
}

extension Array where Element == PendingOperation {
  fileprivate var pendingPhotoUploadCount: Int {
    count {
      $0.kind == .uploadPhoto && ($0.state == .queued || $0.state == .syncing)
    }
  }
}

extension Array where Element == String {
  fileprivate func photoCompletionCount(in operations: [PendingOperation]) -> Int {
    let photoOperationIDs = Set(
      operations.filter { $0.kind == .uploadPhoto }.map(\.id)
    )
    return count { photoOperationIDs.contains($0) }
  }
}

private func minDate(_ left: Date?, _ right: Date) -> Date {
  guard let left else { return right }
  return min(left, right)
}
