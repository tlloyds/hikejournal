import Foundation

struct AppConfiguration: Equatable {
    let apiBaseURL: URL?
    let apiKey: String?
    let webBaseURL: URL?
    let mapStyleURL: URL?
    let mapAttributionTitle: String?
    let mapAttributionURL: URL?
    let mapStyleToken: String?
    let mapStyleTokenQueryItemName: String?
    let callbackScheme: String
    let googleIOSClientID: String?
    let googleServerClientID: String?
    let googleReversedClientID: String?

    init(infoDictionary: [String: Any]) {
        apiBaseURL = Self.httpURL(infoDictionary[Key.apiBaseURL] as? String)
        apiKey = Self.providerValue(infoDictionary[Key.apiKey] as? String)
        webBaseURL = Self.httpURL(infoDictionary[Key.webBaseURL] as? String)
        mapStyleURL = Self.httpURL(infoDictionary[Key.mapStyleURL] as? String)
        mapAttributionTitle = Self.configuredString(infoDictionary[Key.mapAttributionTitle] as? String)
        mapAttributionURL = Self.httpsURL(infoDictionary[Key.mapAttributionURL] as? String)
        mapStyleToken = Self.providerValue(infoDictionary[Key.mapStyleToken] as? String)
        mapStyleTokenQueryItemName = Self.safeQueryItemName(
            infoDictionary[Key.mapStyleTokenQueryItemName] as? String
        )
        callbackScheme = Self.configuredString(infoDictionary[Key.callbackScheme] as? String) ?? "hikejournal"
        googleIOSClientID = Self.providerValue(infoDictionary[Key.googleIOSClientID] as? String)
        googleServerClientID = Self.providerValue(infoDictionary[Key.googleServerClientID] as? String)
        googleReversedClientID = Self.providerValue(infoDictionary[Key.googleReversedClientID] as? String)
    }

    var isGoogleSignInConfigured: Bool {
        googleIOSClientID?.hasSuffix(".apps.googleusercontent.com") == true &&
            googleServerClientID?.hasSuffix(".apps.googleusercontent.com") == true &&
            googleReversedClientID?.hasPrefix("com.googleusercontent.apps.") == true
    }

    private enum Key {
        static let apiBaseURL = "HikeJournalAPIBaseURL"
        static let apiKey = "HikeJournalAPIKey"
        static let webBaseURL = "HikeJournalWebBaseURL"
        static let mapStyleURL = "HikeJournalMapStyleURL"
        static let mapAttributionTitle = "HikeJournalMapAttributionTitle"
        static let mapAttributionURL = "HikeJournalMapAttributionURL"
        static let mapStyleToken = "HikeJournalMapStyleToken"
        static let mapStyleTokenQueryItemName = "HikeJournalMapStyleTokenQueryItemName"
        static let callbackScheme = "HikeJournalCallbackScheme"
        static let googleIOSClientID = "GoogleIOSClientID"
        static let googleServerClientID = "GoogleServerClientID"
        static let googleReversedClientID = "GoogleReversedClientID"
    }

    private static func configuredString(_ value: String?) -> String? {
        guard let clean = value?.trimmingCharacters(in: .whitespacesAndNewlines),
              !clean.isEmpty,
              !clean.contains("$(") else {
            return nil
        }
        return clean
    }

    private static func providerValue(_ value: String?) -> String? {
        guard let clean = configuredString(value),
              !clean.localizedCaseInsensitiveContains("configure_me"),
              !clean.localizedCaseInsensitiveContains("example") else {
            return nil
        }
        return clean
    }

    private static func httpURL(_ value: String?) -> URL? {
        guard let clean = configuredString(value),
              let components = URLComponents(string: clean),
              let scheme = components.scheme?.lowercased(),
              ["http", "https"].contains(scheme),
              components.host?.isEmpty == false,
              components.user == nil,
              components.password == nil,
              components.query == nil,
              components.fragment == nil else {
            return nil
        }
        return components.url
    }

    private static func httpsURL(_ value: String?) -> URL? {
        guard let url = httpURL(value), url.scheme?.lowercased() == "https" else { return nil }
        return url
    }

    private static func safeQueryItemName(_ value: String?) -> String? {
        guard let clean = configuredString(value), clean.count <= 64 else { return nil }
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_."))
        guard clean.unicodeScalars.allSatisfy(allowed.contains) else { return nil }
        return clean
    }
}
