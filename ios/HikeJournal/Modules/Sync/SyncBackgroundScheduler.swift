import BackgroundTasks
import Foundation
import HikeJournalSync

enum SyncBackgroundTaskIdentifier {
    static let refresh = "com.hikejournal.app.sync.refresh"
    static let processing = "com.hikejournal.app.sync.processing"
}

@MainActor
protocol SyncBackgroundScheduling: AnyObject {
    func register(
        refresh: @escaping @Sendable () async -> Bool,
        processing: @escaping @Sendable () async -> Bool
    )
    func schedule(for hint: SyncSchedulingHint, progress: SyncProgressSnapshot) throws
    func cancelPendingTasks()
}

@MainActor
final class SystemSyncBackgroundScheduler: SyncBackgroundScheduling {
    private let scheduler: BGTaskScheduler
    private var hasRegistered = false

    init(scheduler: BGTaskScheduler = .shared) {
        self.scheduler = scheduler
    }

    func register(
        refresh: @escaping @Sendable () async -> Bool,
        processing: @escaping @Sendable () async -> Bool
    ) {
        guard !hasRegistered else { return }
        hasRegistered = true
        scheduler.register(
            forTaskWithIdentifier: SyncBackgroundTaskIdentifier.refresh,
            using: nil
        ) { [weak self] task in
            Task { @MainActor [weak self] in
                self?.run(task: task, operation: refresh)
            }
        }
        scheduler.register(
            forTaskWithIdentifier: SyncBackgroundTaskIdentifier.processing,
            using: nil
        ) { [weak self] task in
            Task { @MainActor [weak self] in
                self?.run(task: task, operation: processing)
            }
        }
    }

    func schedule(for hint: SyncSchedulingHint, progress: SyncProgressSnapshot) throws {
        switch hint {
        case .noWork, .whenConnectivityReturns, .requiresAuthentication, .needsUserAttention:
            cancelPendingTasks()

        case .immediate:
            try submit(
                earliestBeginDate: nil,
                needsProcessing: progress.remainingPhotoUploads > 0
            )

        case let .after(date):
            try submit(
                earliestBeginDate: date,
                needsProcessing: progress.remainingPhotoUploads > 0
            )
        }
    }

    func cancelPendingTasks() {
        scheduler.cancel(taskRequestWithIdentifier: SyncBackgroundTaskIdentifier.refresh)
        scheduler.cancel(taskRequestWithIdentifier: SyncBackgroundTaskIdentifier.processing)
    }

    private func submit(earliestBeginDate: Date?, needsProcessing: Bool) throws {
        if needsProcessing {
            scheduler.cancel(taskRequestWithIdentifier: SyncBackgroundTaskIdentifier.refresh)
            scheduler.cancel(taskRequestWithIdentifier: SyncBackgroundTaskIdentifier.processing)
            let request = BGProcessingTaskRequest(
                identifier: SyncBackgroundTaskIdentifier.processing
            )
            request.requiresNetworkConnectivity = true
            request.requiresExternalPower = false
            request.earliestBeginDate = earliestBeginDate
            try scheduler.submit(request)
        } else {
            scheduler.cancel(taskRequestWithIdentifier: SyncBackgroundTaskIdentifier.processing)
            scheduler.cancel(taskRequestWithIdentifier: SyncBackgroundTaskIdentifier.refresh)
            let request = BGAppRefreshTaskRequest(
                identifier: SyncBackgroundTaskIdentifier.refresh
            )
            request.earliestBeginDate = earliestBeginDate
            try scheduler.submit(request)
        }
    }

    private func run(
        task: BGTask,
        operation: @escaping @Sendable () async -> Bool
    ) {
        let worker = Task {
            let succeeded = await operation()
            task.setTaskCompleted(success: succeeded && !Task.isCancelled)
        }
        task.expirationHandler = {
            worker.cancel()
        }
    }
}
