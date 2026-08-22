import Foundation
import HikeJournalSync
import Network

protocol SyncConnectivityMonitoring: Sendable {
    func status() async -> SyncConnectivityStatus
    func start(onAvailable: @escaping @Sendable () async -> Void) async
    func cancel() async
}

actor NetworkSyncConnectivityMonitor: SyncConnectivityMonitoring {
    private let monitor: NWPathMonitor
    private let queue: DispatchQueue
    private var currentStatus: SyncConnectivityStatus
    private var onAvailable: (@Sendable () async -> Void)?
    private var hasStarted = false

    init(
        monitor: NWPathMonitor = NWPathMonitor(),
        queue: DispatchQueue = DispatchQueue(
            label: "com.hikejournal.sync.connectivity",
            qos: .utility
        )
    ) {
        self.monitor = monitor
        self.queue = queue
        currentStatus = monitor.currentPath.status == .satisfied ? .available : .unavailable
    }

    func status() -> SyncConnectivityStatus {
        currentStatus
    }

    func start(onAvailable: @escaping @Sendable () async -> Void) {
        self.onAvailable = onAvailable
        guard !hasStarted else { return }
        hasStarted = true
        monitor.pathUpdateHandler = { [weak self] path in
            let isAvailable = path.status == .satisfied
            Task { await self?.receive(isAvailable: isAvailable) }
        }
        monitor.start(queue: queue)
    }

    func cancel() {
        guard hasStarted else { return }
        monitor.cancel()
        monitor.pathUpdateHandler = nil
        onAvailable = nil
        hasStarted = false
    }

    private func receive(isAvailable: Bool) async {
        let next: SyncConnectivityStatus = isAvailable ? .available : .unavailable
        let becameAvailable = currentStatus == .unavailable && next == .available
        currentStatus = next
        if becameAvailable, let onAvailable {
            await onAvailable()
        }
    }
}
