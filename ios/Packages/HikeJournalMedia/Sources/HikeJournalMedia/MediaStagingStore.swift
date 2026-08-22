import CryptoKit
import Foundation

public typealias MediaManifestIDGenerator = @Sendable () -> UUID

public actor MediaStagingStore {
    private enum Layout {
        static let root = "HikeJournalMediaStaging"
        static let accounts = "accounts"
        static let incoming = ".incoming"
        static let queued = "queued"
        static let manifest = "manifest.json"
    }

    private let rootDirectory: URL
    private let fileManager: FileManager
    private let idGenerator: MediaManifestIDGenerator
    private let now: @Sendable () -> Date
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    public init(
        baseDirectory: URL? = nil,
        fileManager: FileManager = .default,
        idGenerator: @escaping MediaManifestIDGenerator = { UUID() },
        now: @escaping @Sendable () -> Date = { Date() }
    ) {
        let base = baseDirectory ?? Self.defaultApplicationSupportDirectory(fileManager: fileManager)
        rootDirectory = base.appendingPathComponent(Layout.root, isDirectory: true)
        self.fileManager = fileManager
        self.idGenerator = idGenerator
        self.now = now
        encoder = JSONEncoder()
        decoder = JSONDecoder()
        encoder.dateEncodingStrategy = .millisecondsSince1970
        encoder.outputFormatting = [.sortedKeys]
        decoder.dateDecodingStrategy = .millisecondsSince1970
    }

    public func queuedItems(accountID: String) throws -> [StagedMediaItem] {
        let account = try prepareAccount(accountID)
        let children = try fileManager.contentsOfDirectory(
            at: account.queued,
            includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles]
        )
        return try children.compactMap { directory in
            let values = try directory.resourceValues(forKeys: [.isDirectoryKey])
            guard values.isDirectory == true else { return nil }
            return try loadItem(
                directory: directory,
                expectedAccountScopeID: account.scopeID
            )
        }
        .sorted {
            if $0.manifest.stagedAt != $1.manifest.stagedAt {
                return $0.manifest.stagedAt < $1.manifest.stagedAt
            }
            return $0.manifest.id < $1.manifest.id
        }
    }

    /// Queued media is durable until its consumer explicitly acknowledges the
    /// exact manifest. Missing acknowledgements are harmless and do not delete
    /// any neighboring manifests.
    @discardableResult
    public func acknowledge(manifestID: String, accountID: String) throws -> Bool {
        let safeID = try normalizedManifestID(manifestID)
        let account = try prepareAccount(accountID)
        let directory = account.queued.appendingPathComponent(safeID, isDirectory: true)
        guard fileManager.fileExists(atPath: directory.path) else { return false }
        _ = try loadItem(
            directory: directory,
            expectedAccountScopeID: account.scopeID
        )
        do {
            try fileManager.removeItem(at: directory)
            return true
        } catch {
            throw MediaIngestionError.storageFailure(
                "HikeJournal could not remove acknowledged staged media."
            )
        }
    }

    func stage(
        asset: MediaAssetSnapshot,
        selectedResources: [SelectedMediaResource],
        accountID: String,
        representation: MediaRepresentationPolicy,
        library: any MediaLibraryAccessing,
        componentProgress: @escaping @Sendable (
            _ componentIndex: Int,
            _ componentCount: Int,
            _ role: StagedMediaRole,
            _ fraction: Double
        ) -> Void
    ) async throws -> StagedMediaItem {
        let account = try prepareAccount(accountID)
        let manifestID = try allocateManifestID(in: account.queued)
        let temporaryDirectory = try makeTemporaryDirectory(in: account.incoming)
        var committed = false
        defer {
            if !committed {
                try? fileManager.removeItem(at: temporaryDirectory)
            }
        }

        var components: [QueuedMediaComponent] = []
        do {
            for (index, selection) in selectedResources.enumerated() {
                try Task.checkCancellation()
                let metadata = MediaTypeResolver.metadata(
                    for: selection.resource,
                    role: selection.role,
                    assetKind: asset.kind
                )
                let destination = temporaryDirectory.appendingPathComponent(
                    metadata.stagedFilename,
                    isDirectory: false
                )
                do {
                    try await library.exportResource(
                        selection.resource,
                        to: destination,
                        maximumBytes: hikeJournalMaximumQueuedMediaBytes,
                        progress: { fraction in
                            componentProgress(
                                index,
                                selectedResources.count,
                                selection.role,
                                fraction
                            )
                        }
                    )
                } catch is CancellationError {
                    throw CancellationError()
                } catch let error as MediaIngestionError {
                    throw error
                } catch {
                    throw MediaIngestionError.libraryFailure(
                        assetIdentifier: asset.localIdentifier,
                        message: "HikeJournal could not download \(metadata.originalFilename) from Photos."
                    )
                }
                try Task.checkCancellation()

                let byteCount = try regularFileSize(at: destination)
                guard byteCount > 0 else {
                    throw MediaIngestionError.emptyResource(
                        assetIdentifier: asset.localIdentifier,
                        originalFilename: metadata.originalFilename
                    )
                }
                guard byteCount <= hikeJournalMaximumQueuedMediaBytes else {
                    throw MediaIngestionError.fileTooLarge(
                        assetIdentifier: asset.localIdentifier,
                        originalFilename: metadata.originalFilename,
                        actualBytes: byteCount,
                        maximumBytes: hikeJournalMaximumQueuedMediaBytes
                    )
                }
                try secureFile(at: destination)
                components.append(
                    QueuedMediaComponent(
                        id: "\(manifestID).\(selection.role.rawValue)",
                        role: selection.role,
                        stagedFilename: metadata.stagedFilename,
                        originalFilename: metadata.originalFilename,
                        uniformTypeIdentifier: selection.resource.uniformTypeIdentifier,
                        contentType: metadata.contentType,
                        byteCount: byteCount
                    )
                )
                componentProgress(
                    index,
                    selectedResources.count,
                    selection.role,
                    1
                )
            }

            let manifest = QueuedMediaManifest(
                id: manifestID,
                accountScopeID: account.scopeID,
                sourceAssetIdentifier: asset.localIdentifier,
                assetKind: asset.kind,
                representationPolicy: representation,
                capturedAt: asset.creationDate,
                coordinate: MediaCoordinate(validating: asset.sourceLocation),
                pixelWidth: asset.pixelWidth,
                pixelHeight: asset.pixelHeight,
                duration: asset.duration,
                stagedAt: now(),
                components: components
            )
            let manifestURL = temporaryDirectory.appendingPathComponent(Layout.manifest)
            try encoder.encode(manifest).write(to: manifestURL, options: [.atomic])
            try secureFile(at: manifestURL)
            try excludeFromBackup(temporaryDirectory)

            let finalDirectory = account.queued.appendingPathComponent(
                manifestID,
                isDirectory: true
            )
            guard !fileManager.fileExists(atPath: finalDirectory.path) else {
                throw MediaIngestionError.storageFailure(
                    "HikeJournal could not allocate collision-safe media staging."
                )
            }
            try fileManager.moveItem(at: temporaryDirectory, to: finalDirectory)
            committed = true
            return try loadItem(
                directory: finalDirectory,
                expectedAccountScopeID: account.scopeID
            )
        } catch is CancellationError {
            throw CancellationError()
        } catch let error as MediaIngestionError {
            throw error
        } catch {
            throw MediaIngestionError.storageFailure(
                "HikeJournal could not secure the selected media in durable staging."
            )
        }
    }

    func discardUnreturned(manifestIDs: [String], accountID: String) {
        guard let account = try? prepareAccount(accountID) else { return }
        for manifestID in manifestIDs {
            guard let safeID = try? normalizedManifestID(manifestID) else { continue }
            let directory = account.queued.appendingPathComponent(safeID, isDirectory: true)
            try? fileManager.removeItem(at: directory)
        }
    }

    private func prepareAccount(_ accountID: String) throws -> (
        scopeID: String,
        incoming: URL,
        queued: URL
    ) {
        let clean = accountID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { throw MediaIngestionError.invalidAccountID }
        let scopeID = Self.accountScopeID(clean)
        let accounts = rootDirectory.appendingPathComponent(Layout.accounts, isDirectory: true)
        let account = accounts.appendingPathComponent(scopeID, isDirectory: true)
        let incoming = account.appendingPathComponent(Layout.incoming, isDirectory: true)
        let queued = account.appendingPathComponent(Layout.queued, isDirectory: true)
        do {
            for directory in [rootDirectory, accounts, account, incoming, queued] {
                try fileManager.createDirectory(
                    at: directory,
                    withIntermediateDirectories: true
                )
                try excludeFromBackup(directory)
                try applyFileProtection(to: directory)
            }
        } catch let error as MediaIngestionError {
            throw error
        } catch {
            throw MediaIngestionError.storageFailure(
                "HikeJournal could not open durable media staging."
            )
        }
        return (scopeID, incoming, queued)
    }

    private func allocateManifestID(in queuedDirectory: URL) throws -> String {
        for _ in 0..<32 {
            let candidate = idGenerator().uuidString.lowercased()
            let path = queuedDirectory.appendingPathComponent(candidate, isDirectory: true)
            if !fileManager.fileExists(atPath: path.path) {
                return candidate
            }
        }
        throw MediaIngestionError.storageFailure(
            "HikeJournal could not allocate collision-safe media staging."
        )
    }

    private func makeTemporaryDirectory(in incoming: URL) throws -> URL {
        for _ in 0..<32 {
            let directory = incoming.appendingPathComponent(
                UUID().uuidString.lowercased(),
                isDirectory: true
            )
            if !fileManager.fileExists(atPath: directory.path) {
                try fileManager.createDirectory(at: directory, withIntermediateDirectories: false)
                try excludeFromBackup(directory)
                try applyFileProtection(to: directory)
                return directory
            }
        }
        throw MediaIngestionError.storageFailure(
            "HikeJournal could not create temporary media staging."
        )
    }

    private func loadItem(
        directory: URL,
        expectedAccountScopeID: String
    ) throws -> StagedMediaItem {
        do {
            let manifestURL = directory.appendingPathComponent(Layout.manifest)
            let manifest = try decoder.decode(
                QueuedMediaManifest.self,
                from: Data(contentsOf: manifestURL)
            )
            guard manifest.schemaVersion == 1,
                  manifest.accountScopeID == expectedAccountScopeID,
                  manifest.id == directory.lastPathComponent,
                  UUID(uuidString: manifest.id) != nil,
                  !manifest.components.isEmpty,
                  Set(manifest.components.map(\.id)).count == manifest.components.count else {
                throw MediaIngestionError.invalidManifest(
                    "A staged media manifest failed ownership or schema validation."
                )
            }
            let files = try manifest.components.map { component -> StagedMediaFile in
                guard isSafeRelativeFilename(component.stagedFilename),
                      component.byteCount > 0,
                      component.byteCount <= hikeJournalMaximumQueuedMediaBytes else {
                    throw MediaIngestionError.invalidManifest(
                        "A staged media manifest contains an unsafe file reference."
                    )
                }
                let fileURL = directory.appendingPathComponent(component.stagedFilename)
                let actualSize = try regularFileSize(at: fileURL)
                guard actualSize == component.byteCount else {
                    throw MediaIngestionError.invalidManifest(
                        "A staged media file no longer matches its durable manifest."
                    )
                }
                return StagedMediaFile(component: component, fileURL: fileURL)
            }
            return StagedMediaItem(
                manifest: manifest,
                directoryURL: directory,
                files: files
            )
        } catch let error as MediaIngestionError {
            throw error
        } catch {
            throw MediaIngestionError.invalidManifest(
                "HikeJournal could not reopen a staged media manifest."
            )
        }
    }

    private func regularFileSize(at url: URL) throws -> Int64 {
        let values = try url.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
        guard values.isRegularFile == true, let size = values.fileSize else {
            throw MediaIngestionError.invalidManifest(
                "Staged media is missing or is not a regular file."
            )
        }
        return Int64(size)
    }

    private func secureFile(at url: URL) throws {
        try excludeFromBackup(url)
        try applyFileProtection(to: url)
    }

    private func excludeFromBackup(_ url: URL) throws {
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        var mutableURL = url
        try mutableURL.setResourceValues(values)
    }

    private func applyFileProtection(to url: URL) throws {
        #if os(iOS) || os(tvOS) || os(watchOS)
        try fileManager.setAttributes(
            [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication],
            ofItemAtPath: url.path
        )
        #endif
    }

    private func normalizedManifestID(_ value: String) throws -> String {
        guard let id = UUID(uuidString: value) else {
            throw MediaIngestionError.invalidManifest(
                "The staged media identifier is invalid."
            )
        }
        return id.uuidString.lowercased()
    }

    private func isSafeRelativeFilename(_ value: String) -> Bool {
        !value.isEmpty
            && value != Layout.manifest
            && value == (value as NSString).lastPathComponent
            && !value.contains("\\")
            && value != "."
            && value != ".."
    }

    private static func accountScopeID(_ accountID: String) -> String {
        let digest = SHA256.hash(data: Data(accountID.utf8))
        return "v1_" + digest.map { String(format: "%02x", $0) }.joined()
    }

    private static func defaultApplicationSupportDirectory(fileManager: FileManager) -> URL {
        fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? fileManager.temporaryDirectory.appendingPathComponent(
                "HikeJournalApplicationSupport",
                isDirectory: true
            )
    }
}
