import Combine
import Foundation
import HikeJournalMedia
import HikeJournalPersistence

@MainActor
final class MediaAttachmentStore: ObservableObject {
    @Published private(set) var isImporting = false
    @Published private(set) var progress: Double = 0
    @Published private(set) var importedCount = 0
    @Published private(set) var unavailableCount = 0
    @Published private(set) var errorMessage: String?

    private let authentication: AuthenticationStore
    private let offlineStores: OfflineStoreCoordinator?
    private let stagingStore: MediaStagingStore
    private let ingestion: MediaIngestionService
    private let now: @Sendable () -> Date
    private let onQueued: @Sendable () async -> Void
    private var task: Task<Void, Never>?

    init(
        authentication: AuthenticationStore,
        offlineStores: OfflineStoreCoordinator?,
        library: any MediaLibraryAccessing = PhotoKitMediaLibrary(),
        stagingStore: MediaStagingStore = MediaStagingStore(),
        now: @escaping @Sendable () -> Date = { Date() },
        onQueued: @escaping @Sendable () async -> Void = {}
    ) {
        self.authentication = authentication
        self.offlineStores = offlineStores
        self.stagingStore = stagingStore
        ingestion = MediaIngestionService(library: library, stagingStore: stagingStore)
        self.now = now
        self.onQueued = onQueued
    }

    deinit {
        task?.cancel()
    }

    func importAssets(
        _ identifiers: [String],
        into hikeID: String,
        caption: String = "",
        queueForReview: Bool = false,
        representation: MediaRepresentationPolicy = .currentEditsWhenAvailable
    ) async {
        guard !isImporting else { return }
        errorMessage = nil
        importedCount = 0
        unavailableCount = 0
        progress = 0

        guard case .signedIn(let account) = authentication.phase,
              let canonicalUserID = account.userID,
              let offlineStores else {
            errorMessage = "Sign in before adding photos or videos."
            return
        }
        let cleanHikeID = hikeID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanHikeID.isEmpty else {
            errorMessage = "Choose a journal before adding media."
            return
        }

        isImporting = true
        defer { isImporting = false }
        do {
            let batch = try await ingestion.ingest(
                assetIdentifiers: identifiers,
                accountID: canonicalUserID,
                representation: representation,
                progress: { [weak self] update in
                    Task { @MainActor [weak self] in
                        self?.progress = update.overallFraction
                    }
                }
            )
            let database = try await offlineStores.database(canonicalUserID: canonicalUserID)
            let operations = try makeOperations(
                batch: batch,
                hikeID: cleanHikeID,
                caption: caption,
                queueForReview: queueForReview
            )
            do {
                try await database.upsertOperationsAtomically(operations)
            } catch {
                for item in batch.items {
                    _ = try? await stagingStore.acknowledge(
                        manifestID: item.manifest.id,
                        accountID: canonicalUserID
                    )
                }
                throw error
            }
            importedCount = batch.items.count
            unavailableCount = batch.unavailableAssetIdentifiers.count
            progress = 1
            await onQueued()
        } catch is CancellationError {
            errorMessage = nil
        } catch {
            errorMessage = readable(error)
        }
    }

    func cancel() {
        task?.cancel()
        task = nil
    }

    func clearError() {
        errorMessage = nil
    }

    private func makeOperations(
        batch: MediaIngestionBatch,
        hikeID: String,
        caption: String,
        queueForReview: Bool
    ) throws -> [PendingOperation] {
        var operations: [PendingOperation] = []
        var timestamp = now()
        for item in batch.items {
            for file in item.files {
                let entityID = UUID().uuidString.lowercased()
                var payload: [String: Any] = [
                    "caption": caption,
                    "queue_for_review": queueForReview,
                    "manifest_id": item.manifest.id,
                    "component_role": file.component.role.rawValue,
                ]
                if let capturedAt = item.manifest.capturedAt {
                    payload["taken_at"] = Self.apiDateFormatter.string(from: capturedAt)
                }
                if let coordinate = item.manifest.coordinate {
                    payload["lat"] = coordinate.latitude
                    payload["lng"] = coordinate.longitude
                }
                let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
                operations.append(
                    PendingOperation(
                        id: UUID().uuidString.lowercased(),
                        kind: .uploadPhoto,
                        entityID: entityID,
                        parentID: hikeID,
                        payload: data,
                        localFilePath: file.fileURL.path,
                        contentType: file.component.contentType,
                        fileName: file.component.originalFilename,
                        createdAt: timestamp,
                        updatedAt: timestamp
                    )
                )
                timestamp = timestamp.addingTimeInterval(0.000_001)
            }
        }
        return operations
    }

    private func readable(_ error: Error) -> String {
        if let localized = error as? LocalizedError,
           let description = localized.errorDescription,
           !description.isEmpty {
            return description
        }
        return "HikeJournal couldn't secure the selected media. Nothing was queued."
    }

    private static let apiDateFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()
}
