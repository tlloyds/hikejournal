import Foundation

struct MobileConfiguration: Codable, Equatable, Sendable {
    let webURL: URL
    let apiVersion: String
    let capabilities: Set<String>
    let contractVersion: String
    let compatibility: MobileCompatibility
    let authentication: MobileAuthenticationConfiguration

    enum CodingKeys: String, CodingKey {
        case webURL = "web_url"
        case apiVersion = "api_version"
        case capabilities
        case contractVersion = "contract_version"
        case compatibility
        case authentication
    }
}

struct MobileCompatibility: Codable, Equatable, Sendable {
    let minimumAndroidVersion: String?
    let recommendedAndroidVersion: String?
    let minimumIOSVersion: String?
    let recommendedIOSVersion: String?

    enum CodingKeys: String, CodingKey {
        case minimumAndroidVersion = "minimum_android_version"
        case recommendedAndroidVersion = "recommended_android_version"
        case minimumIOSVersion = "minimum_ios_version"
        case recommendedIOSVersion = "recommended_ios_version"
    }

    init(
        minimumAndroidVersion: String? = nil,
        recommendedAndroidVersion: String? = nil,
        minimumIOSVersion: String? = nil,
        recommendedIOSVersion: String? = nil
    ) {
        self.minimumAndroidVersion = minimumAndroidVersion
        self.recommendedAndroidVersion = recommendedAndroidVersion
        self.minimumIOSVersion = minimumIOSVersion
        self.recommendedIOSVersion = recommendedIOSVersion
    }
}

struct MobileAuthenticationConfiguration: Codable, Equatable, Sendable {
    let mode: String
    let googleClientID: String?

    enum CodingKeys: String, CodingKey {
        case mode
        case googleClientID = "google_client_id"
    }
}

struct AuthAccount: Codable, Equatable, Sendable {
    let subject: String
    let email: String
    let displayName: String
    let pictureURL: URL?
    let userID: String?
    let identityProvider: String?

    enum CodingKeys: String, CodingKey {
        case subject
        case email
        case displayName = "display_name"
        case pictureURL = "picture_url"
        case userID = "user_id"
        case identityProvider = "identity_provider"
    }

    init(
        subject: String,
        email: String,
        displayName: String,
        pictureURL: URL?,
        userID: String?,
        identityProvider: String?
    ) {
        self.subject = subject
        self.email = email
        self.displayName = displayName
        self.pictureURL = pictureURL
        self.userID = userID
        self.identityProvider = identityProvider
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        subject = try container.decode(String.self, forKey: .subject)
        email = try container.decode(String.self, forKey: .email)
        displayName = try container.decode(String.self, forKey: .displayName)
        userID = try container.decodeIfPresent(String.self, forKey: .userID)
        identityProvider = try container.decodeIfPresent(String.self, forKey: .identityProvider)
        let rawPictureURL = try container.decodeIfPresent(String.self, forKey: .pictureURL)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if let rawPictureURL,
           let components = URLComponents(string: rawPictureURL),
           let scheme = components.scheme?.lowercased(),
           ["http", "https"].contains(scheme),
           components.host?.isEmpty == false {
            pictureURL = components.url
        } else {
            pictureURL = nil
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(subject, forKey: .subject)
        try container.encode(email, forKey: .email)
        try container.encode(displayName, forKey: .displayName)
        try container.encode(pictureURL?.absoluteString ?? "", forKey: .pictureURL)
        try container.encodeIfPresent(userID, forKey: .userID)
        try container.encodeIfPresent(identityProvider, forKey: .identityProvider)
    }
}

struct MobileSessionPayload: Codable, Equatable, Sendable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: TimeInterval
    let tokenType: String
    let account: AuthAccount

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresIn = "expires_in"
        case tokenType = "token_type"
        case account
    }
}

struct AuthSession: Codable, Equatable, Sendable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: TimeInterval
    let tokenType: String
    let account: AuthAccount
    let obtainedAt: Date

    init(payload: MobileSessionPayload, obtainedAt: Date) {
        accessToken = payload.accessToken
        refreshToken = payload.refreshToken
        expiresIn = payload.expiresIn
        tokenType = payload.tokenType
        account = payload.account
        self.obtainedAt = obtainedAt
    }

    init(
        accessToken: String,
        refreshToken: String,
        expiresIn: TimeInterval,
        tokenType: String = "Bearer",
        account: AuthAccount,
        obtainedAt: Date
    ) {
        self.accessToken = accessToken
        self.refreshToken = refreshToken
        self.expiresIn = expiresIn
        self.tokenType = tokenType
        self.account = account
        self.obtainedAt = obtainedAt
    }

    func needsRefresh(at date: Date, leeway: TimeInterval = 60) -> Bool {
        obtainedAt.addingTimeInterval(expiresIn) <= date.addingTimeInterval(leeway)
    }
}

struct GoogleAuthenticationRequest: Codable, Equatable, Sendable {
    let credential: String
    let deviceID: String
    let nonce: String?

    enum CodingKeys: String, CodingKey {
        case credential
        case deviceID = "device_id"
        case nonce
    }
}

struct AppleAuthenticationRequest: Codable, Equatable, Sendable {
    let identityToken: String
    let deviceID: String
    let nonce: String
    let displayName: String?

    enum CodingKeys: String, CodingKey {
        case identityToken = "identity_token"
        case deviceID = "device_id"
        case nonce
        case displayName = "display_name"
    }
}

struct RefreshSessionRequest: Codable, Equatable, Sendable {
    let refreshToken: String
    let deviceID: String

    enum CodingKeys: String, CodingKey {
        case refreshToken = "refresh_token"
        case deviceID = "device_id"
    }
}

struct LogoutRequest: Codable, Equatable, Sendable {
    let refreshToken: String

    enum CodingKeys: String, CodingKey {
        case refreshToken = "refresh_token"
    }
}

struct SignedOutResponse: Codable, Equatable, Sendable {
    let signedOut: Bool

    enum CodingKeys: String, CodingKey {
        case signedOut = "signed_out"
    }
}

struct AccountDeletionResponse: Codable, Equatable, Sendable {
    let deleted: Bool
}

struct EntitlementSnapshot: Codable, Equatable, Sendable {
    let plan: EntitlementPlan
    let source: EntitlementSource
    let billingPeriod: BillingPeriod?
    let status: EntitlementStatus
    let productID: String?
    let expiresAt: Date?
    let graceExpiresAt: Date?
    let limits: EntitlementLimits
    let usage: EntitlementUsage
    let features: [String: Bool]
    let policy: EntitlementPolicySummary

    enum CodingKeys: String, CodingKey {
        case plan
        case source
        case billingPeriod = "billing_period"
        case status
        case productID = "product_id"
        case expiresAt = "expires_at"
        case graceExpiresAt = "grace_expires_at"
        case limits
        case usage
        case features
        case policy
    }

    func allows(_ feature: String) -> Bool {
        features[feature] == true
    }

    var shouldOfferUpgrade: Bool {
        plan == .free
    }
}

enum EntitlementPlan: Equatable, Sendable {
    case free
    case plus
    case lifetime
    case unknown(String)
}

enum EntitlementSource: Equatable, Sendable {
    case free
    case appleSubscription
    case googlePlaySubscription
    case googlePlayLegacy
    case admin
    case unknown(String)
}

enum BillingPeriod: Equatable, Sendable {
    case monthly
    case annual
    case lifetime
    case unknown(String)
}

enum EntitlementStatus: Equatable, Sendable {
    case active
    case grace
    case canceled
    case canceledButUnexpired
    case expired
    case revoked
    case refunded
    case unknown(String)
}

struct EntitlementLimits: Codable, Equatable, Sendable {
    let cloudHikes: Int?
    let cloudMedia: Int?

    enum CodingKeys: String, CodingKey {
        case cloudHikes = "cloud_hikes"
        case cloudMedia = "cloud_media"
    }
}

struct EntitlementUsage: Codable, Equatable, Sendable {
    let cloudHikes: Int
    let cloudMedia: Int

    enum CodingKeys: String, CodingKey {
        case cloudHikes = "cloud_hikes"
        case cloudMedia = "cloud_media"
    }
}

struct EntitlementPolicySummary: Codable, Equatable, Sendable {
    let version: String
    let androidPaidCompatibility: String

    enum CodingKeys: String, CodingKey {
        case version
        case androidPaidCompatibility = "android_paid_compatibility"
    }
}

extension EntitlementPlan: Codable {
    init(from decoder: Decoder) throws {
        switch try decoder.singleValueContainer().decode(String.self) {
        case "free": self = .free
        case "plus": self = .plus
        case "lifetime": self = .lifetime
        case let value: self = .unknown(value)
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }

    var rawValue: String {
        switch self {
        case .free: "free"
        case .plus: "plus"
        case .lifetime: "lifetime"
        case let .unknown(value): value
        }
    }

    var displayName: String {
        switch self {
        case .free: "Free"
        case .plus: "Plus"
        case .lifetime: "Lifetime"
        case .unknown: "Account plan"
        }
    }
}

extension EntitlementSource: Codable {
    init(from decoder: Decoder) throws {
        switch try decoder.singleValueContainer().decode(String.self) {
        case "free": self = .free
        case "apple_subscription": self = .appleSubscription
        case "google_play_subscription": self = .googlePlaySubscription
        case "google_play_legacy": self = .googlePlayLegacy
        case "admin": self = .admin
        case let value: self = .unknown(value)
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }

    var rawValue: String {
        switch self {
        case .free: "free"
        case .appleSubscription: "apple_subscription"
        case .googlePlaySubscription: "google_play_subscription"
        case .googlePlayLegacy: "google_play_legacy"
        case .admin: "admin"
        case let .unknown(value): value
        }
    }
}

extension BillingPeriod: Codable {
    init(from decoder: Decoder) throws {
        switch try decoder.singleValueContainer().decode(String.self) {
        case "monthly": self = .monthly
        case "annual": self = .annual
        case "lifetime": self = .lifetime
        case let value: self = .unknown(value)
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }

    var rawValue: String {
        switch self {
        case .monthly: "monthly"
        case .annual: "annual"
        case .lifetime: "lifetime"
        case let .unknown(value): value
        }
    }
}

extension EntitlementStatus: Codable {
    init(from decoder: Decoder) throws {
        switch try decoder.singleValueContainer().decode(String.self) {
        case "active": self = .active
        case "grace": self = .grace
        case "canceled": self = .canceled
        case "canceled_but_unexpired": self = .canceledButUnexpired
        case "expired": self = .expired
        case "revoked": self = .revoked
        case "refunded": self = .refunded
        case let value: self = .unknown(value)
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }

    var rawValue: String {
        switch self {
        case .active: "active"
        case .grace: "grace"
        case .canceled: "canceled"
        case .canceledButUnexpired: "canceled_but_unexpired"
        case .expired: "expired"
        case .revoked: "revoked"
        case .refunded: "refunded"
        case let .unknown(value): value
        }
    }
}
