import Foundation
import HikeJournalPersistence

public struct SyncIdempotencyKey: RawRepresentable, Hashable, Codable, Sendable {
  public let rawValue: String

  public init(rawValue: String) {
    self.rawValue = rawValue
  }

  /// The durable queue identifier is already unique and survives every retry.
  public init(operationID: String) {
    self.rawValue = operationID
  }
}

public struct SyncOperationAcknowledgement: Equatable, Sendable {
  public init() {}

  public static let acknowledged = SyncOperationAcknowledgement()
}

public struct SyncOperationExecutor: Sendable {
  private let body:
    @Sendable (
      _ operation: PendingOperation,
      _ idempotencyKey: SyncIdempotencyKey
    ) async throws -> SyncOperationAcknowledgement

  public init(
    _ body:
      @escaping @Sendable (
        _ operation: PendingOperation,
        _ idempotencyKey: SyncIdempotencyKey
      ) async throws -> SyncOperationAcknowledgement
  ) {
    self.body = body
  }

  public func execute(
    _ operation: PendingOperation,
    idempotencyKey: SyncIdempotencyKey
  ) async throws -> SyncOperationAcknowledgement {
    try await body(operation, idempotencyKey)
  }
}

public enum SyncConnectivityStatus: Equatable, Sendable {
  case available
  case unavailable
}

public struct SyncConnectivityProvider: Sendable {
  private let body: @Sendable () async -> SyncConnectivityStatus

  public init(_ body: @escaping @Sendable () async -> SyncConnectivityStatus) {
    self.body = body
  }

  public func status() async -> SyncConnectivityStatus {
    await body()
  }

  public static let alwaysAvailable = SyncConnectivityProvider { .available }
  public static let alwaysUnavailable = SyncConnectivityProvider { .unavailable }
}

public struct SyncClock: Sendable {
  private let body: @Sendable () -> Date

  public init(now: @escaping @Sendable () -> Date) {
    self.body = now
  }

  public func now() -> Date {
    body()
  }

  public static let system = SyncClock { Date() }

  public static func fixed(_ date: Date) -> SyncClock {
    SyncClock { date }
  }
}

public struct SyncJitter: Sendable {
  private let body: @Sendable (_ operationID: String, _ attempt: Int) -> Double

  public init(
    unitInterval: @escaping @Sendable (_ operationID: String, _ attempt: Int) -> Double
  ) {
    self.body = unitInterval
  }

  public func unitInterval(operationID: String, attempt: Int) -> Double {
    min(1, max(0, body(operationID, attempt)))
  }

  public static let none = SyncJitter { _, _ in 0 }

  /// A stable value avoids moving a persisted operation's retry deadline each
  /// time the process is relaunched while still spreading work across users.
  public static let deterministic = SyncJitter { operationID, attempt in
    var hash: UInt64 = 14_695_981_039_346_656_037
    for byte in "\(operationID):\(attempt)".utf8 {
      hash ^= UInt64(byte)
      hash &*= 1_099_511_628_211
    }
    return Double(hash % 10_001) / 10_000
  }
}

public struct SyncMediaCleanup: Sendable {
  private let body: @Sendable (PendingOperation) async throws -> Void

  public init(
    _ body: @escaping @Sendable (PendingOperation) async throws -> Void
  ) {
    self.body = body
  }

  public func removeAcknowledgedMedia(for operation: PendingOperation) async throws {
    try await body(operation)
  }

  public static let none = SyncMediaCleanup { _ in }
}

public struct SyncProgressReporter: Sendable {
  private let body: @Sendable (SyncProgressSnapshot) async -> Void

  public init(
    _ body: @escaping @Sendable (SyncProgressSnapshot) async -> Void
  ) {
    self.body = body
  }

  public func report(_ snapshot: SyncProgressSnapshot) async {
    await body(snapshot)
  }

  public static let none = SyncProgressReporter { _ in }
}

/// Closure-backed so tests and future stores can use the same sync engine. The
/// supplied operations must be durable before each closure returns.
public struct SyncOperationStore: Sendable {
  private let loadAllBody: @Sendable () async throws -> [PendingOperation]
  private let loadBody: @Sendable (_ id: String) async throws -> PendingOperation?
  private let upsertBody: @Sendable (_ operation: PendingOperation) async throws -> Void
  private let updateStateBody:
    @Sendable (
      _ id: String,
      _ state: PendingOperationState,
      _ attemptCount: Int,
      _ updatedAt: Date,
      _ lastError: String?
    ) async throws -> Void
  private let deleteBody: @Sendable (_ id: String) async throws -> Void

  public init(
    loadAll: @escaping @Sendable () async throws -> [PendingOperation],
    load: @escaping @Sendable (_ id: String) async throws -> PendingOperation?,
    upsert: @escaping @Sendable (_ operation: PendingOperation) async throws -> Void,
    updateState:
      @escaping @Sendable (
        _ id: String,
        _ state: PendingOperationState,
        _ attemptCount: Int,
        _ updatedAt: Date,
        _ lastError: String?
      ) async throws -> Void,
    delete: @escaping @Sendable (_ id: String) async throws -> Void
  ) {
    self.loadAllBody = loadAll
    self.loadBody = load
    self.upsertBody = upsert
    self.updateStateBody = updateState
    self.deleteBody = delete
  }

  public func loadAll() async throws -> [PendingOperation] {
    try await loadAllBody()
  }

  public func load(id: String) async throws -> PendingOperation? {
    try await loadBody(id)
  }

  public func upsert(_ operation: PendingOperation) async throws {
    try await upsertBody(operation)
  }

  public func updateState(
    id: String,
    state: PendingOperationState,
    attemptCount: Int,
    updatedAt: Date,
    lastError: String?
  ) async throws {
    try await updateStateBody(id, state, attemptCount, updatedAt, lastError)
  }

  public func delete(id: String) async throws {
    try await deleteBody(id)
  }

  public static func offlineDatabase(_ database: OfflineDatabase) -> SyncOperationStore {
    SyncOperationStore(
      loadAll: {
        try await database.operations()
      },
      load: { id in
        try await database.operation(id: id)
      },
      upsert: { operation in
        try await database.upsertOperation(operation)
      },
      updateState: { id, state, attemptCount, updatedAt, lastError in
        try await database.updateOperationState(
          id: id,
          state: state,
          attemptCount: attemptCount,
          updatedAt: updatedAt,
          lastError: lastError
        )
      },
      delete: { id in
        try await database.deleteOperation(id: id)
      }
    )
  }
}
