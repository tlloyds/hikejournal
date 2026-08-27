import Combine
import Foundation
import HikeJournalPersistence
import HikeJournalSync

@MainActor
final class SyncStore: ObservableObject {
    @Published private(set) var progress = SyncProgressSnapshot()
    @Published private(set) var schedulingHint: SyncSchedulingHint = .noWork
    @Published private(set) var isDraining = false
    @Published private(set) var statusMessage = "Sign in to sync your journal."
    @Published private(set) var errorMessage: String?

    private weak var authentication: AuthenticationStore?
    private let offlineStores: OfflineStoreCoordinator?
    private let apiClient: APIClient?
    private let connectivityMonitor: any SyncConnectivityMonitoring
    private let backgroundScheduler: any SyncBackgroundScheduling
    private let now: @Sendable () -> Date

    private var phaseObservation: AnyCancellable?
    private var phaseConfigurationTask: Task<Void, Never>?
    private var requestedPhase: AuthenticationPhase?
    private var drainTask: Task<SyncDrainResult, Error>?
    private var drainRequested = false
    private var requestedPrioritizedPhotoID: String?
    private var currentAccountID: String?
    private var accountGeneration = UUID()
    private var database: OfflineDatabase?
    private var coordinator: SyncCoordinator?
    private var apiAdapter: SyncOperationAPIAdapter?
    private var hasStarted = false

    init(
        authentication: AuthenticationStore,
        offlineStores: OfflineStoreCoordinator?,
        apiClient: APIClient?,
        connectivityMonitor: (any SyncConnectivityMonitoring)? = nil,
        backgroundScheduler: (any SyncBackgroundScheduling)? = nil,
        now: @escaping @Sendable () -> Date = { Date() }
    ) {
        self.authentication = authentication
        self.offlineStores = offlineStores
        self.apiClient = apiClient
        self.connectivityMonitor = connectivityMonitor ?? NetworkSyncConnectivityMonitor()
        self.backgroundScheduler = backgroundScheduler ?? SystemSyncBackgroundScheduler()
        self.now = now

        phaseObservation = authentication.$phase
            .removeDuplicates()
            .sink { [weak self] phase in
                Task { @MainActor [weak self] in
                    self?.queueAccountChange(phase)
                }
            }
    }

    deinit {
        phaseConfigurationTask?.cancel()
        drainTask?.cancel()
    }

    var summary: String {
        if isDraining {
            if progress.totalPhotoUploads > 0 {
                return "Uploading \(progress.completedPhotoUploads) of \(progress.totalPhotoUploads) media items"
            }
            return "Syncing journal changes"
        }
        if progress.needsAttentionCount > 0 {
            return "\(progress.needsAttentionCount) item\(progress.needsAttentionCount == 1 ? "" : "s") need attention"
        }
        if progress.queuedCount > 0 {
            return "\(progress.queuedCount) change\(progress.queuedCount == 1 ? "" : "s") waiting"
        }
        return statusMessage
    }

    var canRetry: Bool {
        currentAccountID != nil && coordinator != nil && !isDraining
    }

    func registerBackgroundTasks() {
        backgroundScheduler.register(
            refresh: { [weak self] in
                await self?.performBackgroundDrain() ?? false
            },
            processing: { [weak self] in
                await self?.performBackgroundDrain() ?? false
            }
        )
    }

    func start() async {
        guard !hasStarted else {
            await syncNow()
            return
        }
        hasStarted = true
        await connectivityMonitor.start { [weak self] in
            await self?.connectivityReturned()
        }
        if let authentication {
            await requestAccountConfiguration(authentication.phase)
        }
    }

    func applicationBecameActive() async {
        guard hasStarted else { return }
        await syncNow()
    }

    func applicationEnteredBackground() {
        follow(schedulingHint, progress: progress)
    }

    /// Call after a durable enqueue. A prioritized photo is attempted before
    /// other eligible photo uploads without bypassing hike dependencies.
    func workWasQueued(prioritizedPhotoID: String? = nil) async {
        await drain(prioritizedPhotoID: prioritizedPhotoID)
    }

    func syncNow(prioritizedPhotoID: String? = nil) async {
        await drain(prioritizedPhotoID: prioritizedPhotoID)
    }

    func retryNeedsAttention() async {
        guard let database else { return }
        errorMessage = nil
        do {
            try await database.retryOperationsNeedingAttention(updatedAt: now())
            await drain(prioritizedPhotoID: nil)
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readable(error)
        }
    }

    private func queueAccountChange(_ phase: AuthenticationPhase) {
        Task { @MainActor [weak self] in
            await self?.requestAccountConfiguration(phase)
        }
    }

    private func requestAccountConfiguration(_ phase: AuthenticationPhase) async {
        requestedPhase = phase
        if phaseConfigurationTask == nil {
            phaseConfigurationTask = Task { @MainActor [weak self] in
                guard let self else { return }
                while let phase = self.requestedPhase {
                    self.requestedPhase = nil
                    await self.configure(for: phase)
                }
                self.phaseConfigurationTask = nil
            }
        }
        await phaseConfigurationTask?.value
    }

    private func configure(for phase: AuthenticationPhase) async {
        switch phase {
        case .restoring:
            statusMessage = "Checking your sync account…"

        case .signedOut:
            await clearAccount()
            statusMessage = "Sign in to sync your journal."

        case let .signedIn(account):
            guard let canonicalUserID = account.userID?.trimmingCharacters(
                in: .whitespacesAndNewlines
            ), !canonicalUserID.isEmpty else {
                await clearAccount()
                errorMessage = "Refresh this account before syncing its offline journal."
                statusMessage = "Sync needs an updated account identity."
                return
            }
            if canonicalUserID == currentAccountID, coordinator != nil {
                await drain(prioritizedPhotoID: nil)
                return
            }
            await clearAccount()
            guard !Task.isCancelled else { return }
            guard let offlineStores, let apiClient else {
                errorMessage = "HikeJournal sync is unavailable because local storage or the server is not configured."
                statusMessage = "Sync is unavailable."
                return
            }
            do {
                let openedDatabase = try await offlineStores.database(
                    canonicalUserID: canonicalUserID
                )
                let roots = try await offlineStores.syncUploadRoots(
                    canonicalUserID: canonicalUserID
                )
                guard !Task.isCancelled else { return }

                let generation = UUID()
                accountGeneration = generation
                currentAccountID = canonicalUserID
                database = openedDatabase
                let fileStore = AccountSyncFileStore(allowedRoots: roots)
                let connectivityProvider = SyncConnectivityProvider {
                    [connectivityMonitor] in
                    await connectivityMonitor.status()
                }
                let adapter = SyncOperationAPIAdapter(
                    apiClient: apiClient,
                    fileStore: fileStore,
                    connectivity: connectivityProvider
                )
                apiAdapter = adapter
                coordinator = SyncCoordinator(
                    store: .offlineDatabase(openedDatabase),
                    executor: adapter.executor(),
                    connectivity: connectivityProvider,
                    clock: SyncClock(now: now),
                    jitter: .deterministic,
                    mediaCleanup: SyncMediaCleanup { operation in
                        try fileStore.removeAcknowledgedFile(for: operation)
                    },
                    progressReporter: SyncProgressReporter { [weak self] snapshot in
                        await self?.receive(snapshot, generation: generation)
                    }
                )
                errorMessage = nil
                statusMessage = "Ready to sync."
                await drain(prioritizedPhotoID: nil)
            } catch is CancellationError {
                return
            } catch {
                currentAccountID = nil
                database = nil
                coordinator = nil
                apiAdapter = nil
                errorMessage = readable(error)
                statusMessage = "Sync could not open this account."
            }
        }
    }

    private func clearAccount() async {
        accountGeneration = UUID()
        currentAccountID = nil
        coordinator = nil
        apiAdapter = nil
        database = nil
        let activeDrain = drainTask
        drainTask = nil
        drainRequested = false
        requestedPrioritizedPhotoID = nil
        activeDrain?.cancel()
        _ = await activeDrain?.result
        await offlineStores?.close()
        progress = SyncProgressSnapshot()
        schedulingHint = .noWork
        isDraining = false
        errorMessage = nil
        backgroundScheduler.cancelPendingTasks()
    }

    @discardableResult
    private func drain(prioritizedPhotoID: String?) async -> Bool {
        guard let coordinator, currentAccountID != nil else { return false }
        drainRequested = true
        if let prioritizedPhotoID {
            requestedPrioritizedPhotoID = prioritizedPhotoID
        }
        if drainTask != nil { return true }

        let generation = accountGeneration
        isDraining = true
        errorMessage = nil
        var succeeded = true
        while drainRequested, generation == accountGeneration {
            drainRequested = false
            let nextPrioritizedPhotoID = requestedPrioritizedPhotoID
            requestedPrioritizedPhotoID = nil
            succeeded = await drainOnce(
                coordinator: coordinator,
                generation: generation,
                prioritizedPhotoID: nextPrioritizedPhotoID
            )
            if !succeeded { break }
        }
        return succeeded
    }

    private func drainOnce(
        coordinator: SyncCoordinator,
        generation: UUID,
        prioritizedPhotoID: String?
    ) async -> Bool {
        statusMessage = "Syncing journal changes…"
        let task = Task {
            try await coordinator.drain(prioritizedPhotoID: prioritizedPhotoID)
        }
        drainTask = task
        do {
            let result = try await task.value
            guard generation == accountGeneration else { return false }
            drainTask = nil
            isDraining = drainRequested
            progress = result.progress
            schedulingHint = result.schedulingHint
            statusMessage = message(for: result.schedulingHint)
            if let cleanup = result.cleanupFailures.first {
                errorMessage = "A synced file still needs local cleanup: \(cleanup.message)"
            }
            follow(result.schedulingHint, progress: result.progress)
            return true
        } catch is CancellationError {
            if generation == accountGeneration {
                drainTask = nil
                isDraining = false
            }
            return false
        } catch {
            guard generation == accountGeneration else { return false }
            drainTask = nil
            isDraining = false
            errorMessage = readable(error)
            statusMessage = "Sync paused."
            return false
        }
    }

    private func performBackgroundDrain() async -> Bool {
        await drain(prioritizedPhotoID: nil)
    }

    private func connectivityReturned() async {
        guard schedulingHint == .whenConnectivityReturns || progress.queuedCount > 0 else {
            return
        }
        await drain(prioritizedPhotoID: nil)
    }

    private func receive(_ snapshot: SyncProgressSnapshot, generation: UUID) {
        guard generation == accountGeneration else { return }
        progress = snapshot
    }

    private func follow(_ hint: SyncSchedulingHint, progress: SyncProgressSnapshot) {
        do {
            try backgroundScheduler.schedule(for: hint, progress: progress)
        } catch {
            errorMessage = "iOS could not schedule the next sync yet. Your queued changes are still safe."
        }
    }

    private func message(for hint: SyncSchedulingHint) -> String {
        switch hint {
        case .noWork:
            return "Up to date."
        case .immediate:
            return "More changes are ready to sync."
        case .whenConnectivityReturns:
            return "Waiting for a connection."
        case .after:
            return "A retry is scheduled."
        case .requiresAuthentication:
            return "Sign in again, then retry sync."
        case .needsUserAttention:
            return "Some changes need attention."
        }
    }

    private func readable(_ error: Error) -> String {
        if let localized = error as? LocalizedError,
           let message = localized.errorDescription,
           !message.isEmpty {
            return message
        }
        return "HikeJournal couldn't complete sync. Your queued changes are still safe."
    }
}
