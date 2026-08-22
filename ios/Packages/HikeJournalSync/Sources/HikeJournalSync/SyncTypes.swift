import Foundation

public enum SyncExecutionFailure: Error, Equatable, Sendable {
  case offline(message: String? = nil)
  case authenticationRequired(message: String? = nil)
  case quotaExceeded(resource: String? = nil, message: String? = nil)
  case validation(message: String)
  case retryableServer(
    statusCode: Int? = nil, retryAfter: TimeInterval? = nil, message: String? = nil)
  case permanentServer(statusCode: Int? = nil, message: String? = nil)

  public static func classify(_ error: any Error) -> SyncExecutionFailure {
    if let classified = error as? SyncExecutionFailure {
      return classified
    }
    if let urlError = error as? URLError {
      switch urlError.code {
      case .notConnectedToInternet, .networkConnectionLost, .dataNotAllowed,
        .internationalRoamingOff, .callIsActive:
        return .offline(message: urlError.localizedDescription)
      default:
        return .retryableServer(message: urlError.localizedDescription)
      }
    }
    return .retryableServer(message: String(describing: error))
  }

  public var userFacingMessage: String {
    switch self {
    case .offline(let message):
      return message ?? "HikeJournal is offline."
    case .authenticationRequired(let message):
      return message ?? "Sign in again to continue syncing."
    case .quotaExceeded(let resource, let message):
      if let message { return message }
      if let resource { return "The \(resource) cloud limit has been reached." }
      return "The cloud storage limit has been reached."
    case .validation(let message):
      return message
    case .retryableServer(let statusCode, _, let message):
      if let message { return message }
      if let statusCode { return "The server returned HTTP \(statusCode)." }
      return "The server could not complete this sync yet."
    case .permanentServer(let statusCode, let message):
      if let message { return message }
      if let statusCode { return "The server rejected this change (HTTP \(statusCode))." }
      return "The server rejected this change."
    }
  }
}

public struct SyncRetryPolicy: Equatable, Sendable {
  public let maximumAttempts: Int
  public let baseDelay: TimeInterval
  public let maximumDelay: TimeInterval
  public let maximumJitterFraction: Double

  public init(
    maximumAttempts: Int = 5,
    baseDelay: TimeInterval = 2,
    maximumDelay: TimeInterval = 5 * 60,
    maximumJitterFraction: Double = 0.25
  ) {
    self.maximumAttempts = max(1, maximumAttempts)
    self.baseDelay = max(0, baseDelay)
    self.maximumDelay = max(0, maximumDelay)
    self.maximumJitterFraction = min(1, max(0, maximumJitterFraction))
  }

  public func delay(
    forAttempt attempt: Int,
    retryAfter: TimeInterval? = nil,
    jitterUnitInterval: Double = 0
  ) -> TimeInterval {
    let exponent = max(0, min(attempt - 1, 30))
    let exponential = baseDelay * pow(2, Double(exponent))
    let jittered = exponential * (1 + min(1, max(0, jitterUnitInterval)) * maximumJitterFraction)
    return min(maximumDelay, max(jittered, retryAfter ?? 0))
  }
}

public struct SyncCoordinatorConfiguration: Equatable, Sendable {
  public let maximumParallelPhotoUploads: Int
  public let staleSyncingInterval: TimeInterval
  public let retryPolicy: SyncRetryPolicy

  public init(
    maximumParallelPhotoUploads: Int = 2,
    staleSyncingInterval: TimeInterval = 15 * 60,
    retryPolicy: SyncRetryPolicy = SyncRetryPolicy()
  ) {
    self.maximumParallelPhotoUploads = min(2, max(1, maximumParallelPhotoUploads))
    self.staleSyncingInterval = max(0, staleSyncingInterval)
    self.retryPolicy = retryPolicy
  }
}

public enum SyncSchedulingHint: Equatable, Sendable {
  /// Nothing is immediately schedulable. The app adapter need not create work.
  case noWork
  /// New eligible work appeared during the pass; ask the adapter to drain again.
  case immediate
  /// Observe connectivity and call `drain` once it becomes available.
  case whenConnectivityReturns
  /// Earliest useful time for a foreground or BGTask adapter to call `drain`.
  case after(Date)
  /// Token refresh or an interactive sign-in is required before another drain.
  case requiresAuthentication
  /// One or more durable operations require a user decision or quota change.
  case needsUserAttention
}

public struct SyncProgressSnapshot: Equatable, Sendable {
  public let queuedCount: Int
  public let syncingCount: Int
  public let needsAttentionCount: Int
  public let totalPhotoUploads: Int
  public let completedPhotoUploads: Int
  public let remainingPhotoUploads: Int
  public let completedOperationCount: Int
  public let failedOperationCount: Int
  public let activeOperationIDs: [String]

  public init(
    queuedCount: Int = 0,
    syncingCount: Int = 0,
    needsAttentionCount: Int = 0,
    totalPhotoUploads: Int = 0,
    completedPhotoUploads: Int = 0,
    remainingPhotoUploads: Int = 0,
    completedOperationCount: Int = 0,
    failedOperationCount: Int = 0,
    activeOperationIDs: [String] = []
  ) {
    self.queuedCount = queuedCount
    self.syncingCount = syncingCount
    self.needsAttentionCount = needsAttentionCount
    self.totalPhotoUploads = totalPhotoUploads
    self.completedPhotoUploads = completedPhotoUploads
    self.remainingPhotoUploads = remainingPhotoUploads
    self.completedOperationCount = completedOperationCount
    self.failedOperationCount = failedOperationCount
    self.activeOperationIDs = activeOperationIDs
  }
}

public struct SyncCleanupFailure: Equatable, Sendable {
  public let operationID: String
  public let message: String

  public init(operationID: String, message: String) {
    self.operationID = operationID
    self.message = message
  }
}

public struct SyncDrainResult: Equatable, Sendable {
  public let attemptedOperationIDs: [String]
  public let completedOperationIDs: [String]
  public let retryScheduledOperationIDs: [String]
  public let needsAttentionOperationIDs: [String]
  public let recoveredOperationIDs: [String]
  public let cleanupFailures: [SyncCleanupFailure]
  public let schedulingHint: SyncSchedulingHint
  public let progress: SyncProgressSnapshot

  public init(
    attemptedOperationIDs: [String],
    completedOperationIDs: [String],
    retryScheduledOperationIDs: [String],
    needsAttentionOperationIDs: [String],
    recoveredOperationIDs: [String],
    cleanupFailures: [SyncCleanupFailure],
    schedulingHint: SyncSchedulingHint,
    progress: SyncProgressSnapshot
  ) {
    self.attemptedOperationIDs = attemptedOperationIDs
    self.completedOperationIDs = completedOperationIDs
    self.retryScheduledOperationIDs = retryScheduledOperationIDs
    self.needsAttentionOperationIDs = needsAttentionOperationIDs
    self.recoveredOperationIDs = recoveredOperationIDs
    self.cleanupFailures = cleanupFailures
    self.schedulingHint = schedulingHint
    self.progress = progress
  }
}

public enum SyncCoordinatorError: Error, Equatable, Sendable {
  case drainAlreadyInProgress
  case operationDisappeared(String)
  case stateTransitionWasNotDurable(operationID: String, expected: String)
  case operationReplacementWasNotDurable(String)
  case queueDeletionWasNotDurable(String)
}
