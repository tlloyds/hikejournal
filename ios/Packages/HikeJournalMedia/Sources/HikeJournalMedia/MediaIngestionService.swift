import Foundation

public protocol MediaLibraryAccessing: Sendable {
    func authorizationStatus() async -> MediaLibraryAuthorization

    /// Returned snapshots may be in any order and may omit identifiers that a
    /// limited library grant does not expose.
    func assets(forLocalIdentifiers identifiers: [String]) async throws -> [MediaAssetSnapshot]

    /// Implementations must permit iCloud download, report progress, cooperate
    /// with task cancellation, and stop once `maximumBytes` would be exceeded.
    func exportResource(
        _ resource: MediaResourceDescriptor,
        to destinationURL: URL,
        maximumBytes: Int64,
        progress: @escaping MediaResourceProgressHandler
    ) async throws
}

public actor MediaIngestionService {
    private let library: any MediaLibraryAccessing
    private let stagingStore: MediaStagingStore
    private let selectionPolicy: MediaResourceSelectionPolicy

    public init(
        library: any MediaLibraryAccessing,
        stagingStore: MediaStagingStore,
        selectionPolicy: MediaResourceSelectionPolicy = MediaResourceSelectionPolicy()
    ) {
        self.library = library
        self.stagingStore = stagingStore
        self.selectionPolicy = selectionPolicy
    }

    public func ingest(
        assetIdentifiers: [String],
        accountID: String,
        representation: MediaRepresentationPolicy = .currentEditsWhenAvailable,
        progress: MediaProgressHandler? = nil
    ) async throws -> MediaIngestionBatch {
        guard !accountID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw MediaIngestionError.invalidAccountID
        }
        let identifiers = orderedUniqueIdentifiers(assetIdentifiers)
        guard !identifiers.isEmpty else {
            throw MediaIngestionError.emptySelection
        }
        guard identifiers.count <= hikeJournalMaximumMediaSelection else {
            throw MediaIngestionError.tooManyAssets(maximum: hikeJournalMaximumMediaSelection)
        }

        let authorization = await library.authorizationStatus()
        guard authorization.permitsRead else {
            throw MediaIngestionError.libraryAccessRequired(authorization)
        }

        let snapshots: [MediaAssetSnapshot]
        do {
            snapshots = try await library.assets(forLocalIdentifiers: identifiers)
        } catch is CancellationError {
            throw CancellationError()
        } catch let error as MediaIngestionError {
            throw error
        } catch {
            throw MediaIngestionError.libraryFailure(
                assetIdentifier: "",
                message: "HikeJournal could not read the selected Photos items."
            )
        }
        try Task.checkCancellation()

        let snapshotsByID = Dictionary(
            snapshots.map { ($0.localIdentifier, $0) },
            uniquingKeysWith: { first, _ in first }
        )
        let available = identifiers.compactMap { snapshotsByID[$0] }
        let unavailable = identifiers.filter { snapshotsByID[$0] == nil }
        var staged: [StagedMediaItem] = []

        do {
            for (assetIndex, asset) in available.enumerated() {
                try Task.checkCancellation()
                let selected = try selectionPolicy.selectResources(
                    for: asset,
                    representation: representation
                )
                let item = try await stagingStore.stage(
                    asset: asset,
                    selectedResources: selected,
                    accountID: accountID,
                    representation: representation,
                    library: library,
                    componentProgress: { componentIndex, componentCount, role, fraction in
                        let safeFraction = min(1, max(0, fraction.isFinite ? fraction : 0))
                        let assetFraction = (
                            Double(componentIndex) + safeFraction
                        ) / Double(max(1, componentCount))
                        let overall = (
                            Double(assetIndex) + assetFraction
                        ) / Double(max(1, available.count))
                        progress?(
                            MediaIngestionProgress(
                                assetIdentifier: asset.localIdentifier,
                                assetIndex: assetIndex,
                                assetCount: available.count,
                                role: role,
                                resourceFraction: safeFraction,
                                overallFraction: min(1, max(0, overall))
                            )
                        )
                    }
                )
                staged.append(item)
            }
        } catch {
            await stagingStore.discardUnreturned(
                manifestIDs: staged.map(\.manifest.id),
                accountID: accountID
            )
            if error is CancellationError {
                throw CancellationError()
            }
            throw error
        }

        return MediaIngestionBatch(
            authorization: authorization,
            items: staged,
            unavailableAssetIdentifiers: unavailable
        )
    }

    private func orderedUniqueIdentifiers(_ values: [String]) -> [String] {
        var seen = Set<String>()
        return values.compactMap { value in
            let clean = value.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !clean.isEmpty, seen.insert(clean).inserted else { return nil }
            return clean
        }
    }
}
