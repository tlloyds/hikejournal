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
#if targetEnvironment(simulator)
        guard let data = UserDefaults.standard.data(forKey: simulatorKey(account: Account.session)) else {
            return nil
        }
        do {
            return try decoder.decode(AuthSession.self, from: data)
        } catch {
            UserDefaults.standard.removeObject(forKey: simulatorKey(account: Account.session))
            return nil
        }
#else
        guard let data = try read(account: Account.session) else { return nil }
        do {
            return try decoder.decode(AuthSession.self, from: data)
        } catch {
            try? delete(account: Account.session)
            return nil
        }
#endif
    }

    func saveSession(_ session: AuthSession) throws {
        let data: Data
        do {
            data = try encoder.encode(session)
        } catch {
            throw SessionStoreError.encodingFailed
        }
#if targetEnvironment(simulator)
        UserDefaults.standard.set(data, forKey: simulatorKey(account: Account.session))
#else
        try write(data, account: Account.session)
#endif
    }

    func clearSession() throws {
#if targetEnvironment(simulator)
        UserDefaults.standard.removeObject(forKey: simulatorKey(account: Account.session))
#else
        try delete(account: Account.session)
#endif
    }

    func deviceID() throws -> String {
#if targetEnvironment(simulator)
        if let data = UserDefaults.standard.data(forKey: simulatorKey(account: Account.deviceID)),
           let existing = String(data: data, encoding: .utf8),
           existing.count >= 8 {
            return existing
        }

        let generated = UUID().uuidString.lowercased()
        guard let data = generated.data(using: .utf8) else {
            throw SessionStoreError.encodingFailed
        }
        UserDefaults.standard.set(data, forKey: simulatorKey(account: Account.deviceID))
        return generated
#else
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
#endif
    }

#if targetEnvironment(simulator)
    private func simulatorKey(account: String) -> String {
        "HikeJournal.KeychainSessionStore.\(service).\(account)"
    }
#endif

    private func baseQuery(account: String) -> [CFString: Any] {
        [
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecAttrSynchronizable: kCFBooleanFalse as Any
        ]
    }

    private func keychainQueries(account: String) -> [[CFString: Any]] {
        let legacy = baseQuery(account: account)
        var dataProtection = legacy
        dataProtection[kSecUseDataProtectionKeychain] = kCFBooleanTrue as Any
        // A simulator build cannot carry the data-protection entitlement. Keep
        // the data-protection query first for signed device builds, then fall
        // back to the ordinary app keychain when the entitlement is absent.
        return [dataProtection, legacy]
    }

    private func read(account: String) throws -> Data? {
        for baseQuery in keychainQueries(account: account) {
            var query = baseQuery
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
            case errSecItemNotFound, errSecMissingEntitlement:
                continue
            default:
                throw SessionStoreError.keychain(status)
            }
        }
        return nil
    }

    private func write(_ data: Data, account: String) throws {
        for query in keychainQueries(account: account) {
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
                switch addStatus {
                case errSecSuccess:
                    return
                case errSecMissingEntitlement:
                    continue
                default:
                    throw SessionStoreError.keychain(addStatus)
                }
            case errSecMissingEntitlement:
                continue
            default:
                throw SessionStoreError.keychain(updateStatus)
            }
        }
        throw SessionStoreError.keychain(errSecMissingEntitlement)
    }

    private func delete(account: String) throws {
        for query in keychainQueries(account: account) {
            let status = SecItemDelete(query as CFDictionary)
            guard status == errSecSuccess || status == errSecItemNotFound || status == errSecMissingEntitlement else {
                throw SessionStoreError.keychain(status)
            }
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
