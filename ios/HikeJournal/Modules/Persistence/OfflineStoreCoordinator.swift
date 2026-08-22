import CryptoKit
import Foundation
import HikeJournalPersistence

enum OfflineStoreCoordinatorError: Error, Equatable, LocalizedError {
    case canonicalUserIDRequired
    case applicationSupportUnavailable

    var errorDescription: String? {
        switch self {
        case .canonicalUserIDRequired:
            "Refresh this account before opening its offline journal."
        case .applicationSupportUnavailable:
            "HikeJournal could not open its private offline storage."
        }
    }
}

/// Owns exactly one account-isolated database at a time. Switching accounts
/// closes the previous SQLite connection before any other account is opened.
actor OfflineStoreCoordinator {
    private let applicationSupportDirectory: URL
    private var openUserID: UUID?
    private var openDatabase: OfflineDatabase?

    init(applicationSupportDirectory: URL? = nil) throws {
        if let applicationSupportDirectory {
            self.applicationSupportDirectory = applicationSupportDirectory
        } else if let discovered = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first {
            self.applicationSupportDirectory = discovered
        } else {
            throw OfflineStoreCoordinatorError.applicationSupportUnavailable
        }
    }

    func database(canonicalUserID rawUserID: String) async throws -> OfflineDatabase {
        let userID = try canonicalUUID(rawUserID)
        if userID == openUserID, let openDatabase {
            return openDatabase
        }

        if let openDatabase {
            await openDatabase.close()
        }

        let databaseURL = OfflineDatabase.accountDatabaseURL(
            applicationSupportDirectory: applicationSupportDirectory,
            canonicalUserID: userID
        )
        try preparePrivateDirectory(databaseURL.deletingLastPathComponent())
        let database = try OfflineDatabase(path: databaseURL.path)
        openUserID = userID
        openDatabase = database
        return database
    }

    func routesDirectory(canonicalUserID rawUserID: String) throws -> URL {
        let userID = try canonicalUUID(rawUserID)
        let databaseURL = OfflineDatabase.accountDatabaseURL(
            applicationSupportDirectory: applicationSupportDirectory,
            canonicalUserID: userID
        )
        let directory = databaseURL.deletingLastPathComponent()
            .appendingPathComponent("Routes", isDirectory: true)
        try preparePrivateDirectory(directory)
        return directory
    }

    /// The sync adapter accepts upload paths only from these account-scoped,
    /// app-owned locations. The media package hashes its account scope while
    /// recorded TCX files live beside the account database.
    func syncUploadRoots(canonicalUserID rawUserID: String) throws -> [URL] {
        let userID = try canonicalUUID(rawUserID)
        let accountDirectory = OfflineDatabase.accountDatabaseURL(
            applicationSupportDirectory: applicationSupportDirectory,
            canonicalUserID: userID
        ).deletingLastPathComponent()
        let raw = rawUserID.trimmingCharacters(in: .whitespacesAndNewlines)
        let identifiers = Set([
            raw,
            userID.uuidString.lowercased(),
            userID.uuidString.uppercased(),
        ])
        let mediaAccounts = applicationSupportDirectory
            .appendingPathComponent("HikeJournalMediaStaging", isDirectory: true)
            .appendingPathComponent("accounts", isDirectory: true)
        let mediaRoots = identifiers.map { identifier in
            mediaAccounts.appendingPathComponent(
                Self.mediaAccountScopeID(identifier),
                isDirectory: true
            )
        }
        return [accountDirectory] + mediaRoots
    }

    func close() async {
        if let openDatabase {
            await openDatabase.close()
        }
        openDatabase = nil
        openUserID = nil
    }

    private func preparePrivateDirectory(_ directory: URL) throws {
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true,
            attributes: [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication]
        )
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        var mutableDirectory = directory
        try mutableDirectory.setResourceValues(values)
    }

    private func canonicalUUID(_ rawUserID: String) throws -> UUID {
        guard let userID = UUID(uuidString: rawUserID) else {
            throw OfflineStoreCoordinatorError.canonicalUserIDRequired
        }
        return userID
    }

    private static func mediaAccountScopeID(_ accountID: String) -> String {
        let digest = SHA256.hash(data: Data(accountID.utf8))
        return "v1_" + digest.map { String(format: "%02x", $0) }.joined()
    }
}
