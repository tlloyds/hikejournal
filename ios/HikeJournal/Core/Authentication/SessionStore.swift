import Foundation
import Security

protocol SessionStoring: Sendable {
    func loadSession() async throws -> AuthSession?
    func saveSession(_ session: AuthSession) async throws
    func clearSession() async throws
    func deviceID() async throws -> String
}

enum SessionStoreError: Error, Equatable, LocalizedError {
    case keychain(OSStatus)
    case encodingFailed

    var errorDescription: String? {
        switch self {
        case let .keychain(status):
            let message = SecCopyErrorMessageString(status, nil) as String?
            return message.map { "Secure session storage failed: \($0)" }
                ?? "Secure session storage failed (\(status))."
        case .encodingFailed:
            return "HikeJournal could not securely store this session."
        }
    }
}

actor KeychainSessionStore: SessionStoring {
    private enum Account {
        static let session = "mobile-session.v1"
        static let deviceID = "device-id.v1"
    }

    private let service: String
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(service: String = "com.hikejournal.app.mobile-auth") {
        self.service = service
        encoder = JSONEncoder()
        decoder = JSONDecoder()
        encoder.dateEncodingStrategy = .millisecondsSince1970
        decoder.dateDecodingStrategy = .millisecondsSince1970
    }

    func loadSession() throws -> AuthSession? {
        guard let data = try read(account: Account.session) else { return nil }
        do {
            return try decoder.decode(AuthSession.self, from: data)
        } catch {
            try? delete(account: Account.session)
            return nil
        }
    }

    func saveSession(_ session: AuthSession) throws {
        let data: Data
        do {
            data = try encoder.encode(session)
        } catch {
            throw SessionStoreError.encodingFailed
        }
        try write(data, account: Account.session)
    }

    func clearSession() throws {
        try delete(account: Account.session)
    }

    func deviceID() throws -> String {
        if let data = try read(account: Account.deviceID),
           let existing = String(data: data, encoding: .utf8),
           existing.count >= 8 {
            return existing
        }

        let generated = UUID().uuidString.lowercased()
        guard let data = generated.data(using: .utf8) else {
            throw SessionStoreError.encodingFailed
        }
        try write(data, account: Account.deviceID)
        return generated
    }

    private func baseQuery(account: String) -> [CFString: Any] {
        [
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecAttrSynchronizable: kCFBooleanFalse as Any,
            // Match Google's secure storage configuration. This keeps the
            // app's session and device identity in the same data-protection
            // keychain used by the native sign-in provider.
            kSecUseDataProtectionKeychain: kCFBooleanTrue as Any
        ]
    }

    private func read(account: String) throws -> Data? {
        var query = baseQuery(account: account)
        query[kSecReturnData] = kCFBooleanTrue
        query[kSecMatchLimit] = kSecMatchLimitOne

        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        switch status {
        case errSecSuccess:
            guard let data = result as? Data else {
                throw SessionStoreError.encodingFailed
            }
            return data
        case errSecItemNotFound:
            return nil
        default:
            throw SessionStoreError.keychain(status)
        }
    }

    private func write(_ data: Data, account: String) throws {
        let query = baseQuery(account: account)
        let updateStatus = SecItemUpdate(
            query as CFDictionary,
            [kSecValueData: data] as CFDictionary
        )
        switch updateStatus {
        case errSecSuccess:
            return
        case errSecItemNotFound:
            var attributes = query
            attributes[kSecValueData] = data
            attributes[kSecAttrAccessible] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            let addStatus = SecItemAdd(attributes as CFDictionary, nil)
            guard addStatus == errSecSuccess else {
                throw SessionStoreError.keychain(addStatus)
            }
        default:
            throw SessionStoreError.keychain(updateStatus)
        }
    }

    private func delete(account: String) throws {
        let status = SecItemDelete(baseQuery(account: account) as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw SessionStoreError.keychain(status)
        }
    }
}

actor MemorySessionStore: SessionStoring {
    private var session: AuthSession?
    private let stableDeviceID: String

    init(session: AuthSession? = nil, deviceID: String = "00000000-0000-0000-0000-000000000001") {
        self.session = session
        stableDeviceID = deviceID
    }

    func loadSession() -> AuthSession? {
        session
    }

    func saveSession(_ session: AuthSession) {
        self.session = session
    }

    func clearSession() {
        session = nil
    }

    func deviceID() -> String {
        stableDeviceID
    }
}
