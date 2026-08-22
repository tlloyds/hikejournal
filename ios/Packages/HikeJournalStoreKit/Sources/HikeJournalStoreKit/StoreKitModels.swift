import Foundation

public enum HikeJournalProductID: String, Codable, CaseIterable, Sendable {
    case plusMonthly = "com.hikejournal.app.plus.monthly"
    case plusAnnual = "com.hikejournal.app.plus.annual"

    public static let subscriptionGroupName = "HikeJournal Plus"

    public var billingPeriod: String {
        switch self {
        case .plusMonthly: "monthly"
        case .plusAnnual: "annual"
        }
    }

    public var displayOrder: Int {
        switch self {
        case .plusAnnual: 0
        case .plusMonthly: 1
        }
    }
}

public struct StoreSubscriptionPeriod: Equatable, Sendable {
    public enum Unit: String, Equatable, Sendable {
        case day
        case week
        case month
        case year
    }

    public let value: Int
    public let unit: Unit

    public init(value: Int, unit: Unit) {
        self.value = value
        self.unit = unit
    }
}

public struct StoreProductInfo: Identifiable, Equatable, Sendable {
    public var id: String { productID }
    public let productID: String
    public let displayName: String
    public let description: String
    public let displayPrice: String
    public let price: Decimal
    public let subscriptionPeriod: StoreSubscriptionPeriod?

    public init(
        productID: String,
        displayName: String,
        description: String,
        displayPrice: String,
        price: Decimal,
        subscriptionPeriod: StoreSubscriptionPeriod?
    ) {
        self.productID = productID
        self.displayName = displayName
        self.description = description
        self.displayPrice = displayPrice
        self.price = price
        self.subscriptionPeriod = subscriptionPeriod
    }
}

/// A verification boundary that deliberately discards unverified StoreKit data.
/// Callers can observe that verification failed, but cannot accidentally use
/// the untrusted transaction as purchase evidence.
public enum StoreVerification<Value: Sendable>: Sendable {
    case verified(Value)
    case unverified
}

extension StoreVerification: Equatable where Value: Equatable {}

public struct StoreTransactionEvidence: Equatable, Sendable {
    public let transactionID: UInt64
    public let originalTransactionID: UInt64
    public let productID: String
    public let appAccountToken: UUID?
    public let purchaseDate: Date
    public let expirationDate: Date?
    public let revocationDate: Date?
    public let isUpgraded: Bool
    public let signedTransaction: String
    public let signedRenewalInfo: String?

    public init(
        transactionID: UInt64,
        originalTransactionID: UInt64,
        productID: String,
        appAccountToken: UUID?,
        purchaseDate: Date,
        expirationDate: Date?,
        revocationDate: Date?,
        isUpgraded: Bool,
        signedTransaction: String,
        signedRenewalInfo: String? = nil
    ) {
        self.transactionID = transactionID
        self.originalTransactionID = originalTransactionID
        self.productID = productID
        self.appAccountToken = appAccountToken
        self.purchaseDate = purchaseDate
        self.expirationDate = expirationDate
        self.revocationDate = revocationDate
        self.isUpgraded = isUpgraded
        self.signedTransaction = signedTransaction
        self.signedRenewalInfo = signedRenewalInfo
    }
}

public enum StoreSubscriptionState: String, CaseIterable, Sendable {
    case subscribed
    case inGracePeriod = "in_grace_period"
    case inBillingRetryPeriod = "in_billing_retry_period"
    case expired
    case revoked
}

public struct StoreSubscriptionStatusEvidence: Equatable, Sendable {
    public let state: StoreSubscriptionState
    public let transaction: StoreTransactionEvidence
    public let willAutoRenew: Bool
    public let gracePeriodExpirationDate: Date?
    public let signedRenewalInfo: String

    public init(
        state: StoreSubscriptionState,
        transaction: StoreTransactionEvidence,
        willAutoRenew: Bool,
        gracePeriodExpirationDate: Date?,
        signedRenewalInfo: String
    ) {
        self.state = state
        self.transaction = transaction
        self.willAutoRenew = willAutoRenew
        self.gracePeriodExpirationDate = gracePeriodExpirationDate
        self.signedRenewalInfo = signedRenewalInfo
    }
}

public enum StorePurchaseResult: Equatable, Sendable {
    case success(StoreVerification<StoreTransactionEvidence>)
    case pending
    case userCancelled
}

public struct StoreKitTransactionSyncRequest: Codable, Equatable, Sendable {
    public let signedTransaction: String
    public let signedRenewalInfo: String?

    public init(signedTransaction: String, signedRenewalInfo: String? = nil) {
        self.signedTransaction = signedTransaction
        self.signedRenewalInfo = signedRenewalInfo
    }
}

public enum AuthoritativePlan: String, Codable, CaseIterable, Sendable {
    case free
    case plus
    case lifetime
}

public enum AuthoritativeEntitlementSource: String, Codable, CaseIterable, Sendable {
    case free
    case appleSubscription = "apple_subscription"
    case googlePlaySubscription = "google_play_subscription"
    case googlePlayLegacy = "google_play_legacy"
    case admin
}

public enum AuthoritativeEntitlementStatus: String, Codable, CaseIterable, Sendable {
    case active
    case grace
    case canceled
    case canceledButUnexpired = "canceled_but_unexpired"
    case expired
    case revoked
    case refunded
}

public struct AuthoritativeEntitlementLimits: Codable, Equatable, Sendable {
    public let cloudHikes: Int?
    public let cloudMedia: Int?

    public init(cloudHikes: Int?, cloudMedia: Int?) {
        self.cloudHikes = cloudHikes
        self.cloudMedia = cloudMedia
    }

    enum CodingKeys: String, CodingKey {
        case cloudHikes = "cloud_hikes"
        case cloudMedia = "cloud_media"
    }
}

public struct AuthoritativeEntitlementUsage: Codable, Equatable, Sendable {
    public let cloudHikes: Int
    public let cloudMedia: Int

    public init(cloudHikes: Int, cloudMedia: Int) {
        self.cloudHikes = cloudHikes
        self.cloudMedia = cloudMedia
    }

    enum CodingKeys: String, CodingKey {
        case cloudHikes = "cloud_hikes"
        case cloudMedia = "cloud_media"
    }
}

public struct AuthoritativeEntitlementPolicy: Codable, Equatable, Sendable {
    public let version: String
    public let androidPaidCompatibility: String

    public init(version: String, androidPaidCompatibility: String) {
        self.version = version
        self.androidPaidCompatibility = androidPaidCompatibility
    }

    enum CodingKeys: String, CodingKey {
        case version
        case androidPaidCompatibility = "android_paid_compatibility"
    }
}

/// This is the only state in this package that may drive durable HikeJournal
/// access. Local StoreKit status remains presentation/reconciliation evidence.
public struct AuthoritativeEntitlementSnapshot: Codable, Equatable, Sendable {
    public let plan: AuthoritativePlan
    public let source: AuthoritativeEntitlementSource
    public let billingPeriod: String?
    public let status: AuthoritativeEntitlementStatus
    public let productID: String?
    public let expiresAt: Date?
    public let graceExpiresAt: Date?
    public let limits: AuthoritativeEntitlementLimits
    public let usage: AuthoritativeEntitlementUsage
    public let features: [String: Bool]
    public let policy: AuthoritativeEntitlementPolicy

    public init(
        plan: AuthoritativePlan,
        source: AuthoritativeEntitlementSource,
        billingPeriod: String?,
        status: AuthoritativeEntitlementStatus,
        productID: String?,
        expiresAt: Date?,
        graceExpiresAt: Date?,
        limits: AuthoritativeEntitlementLimits,
        usage: AuthoritativeEntitlementUsage,
        features: [String: Bool],
        policy: AuthoritativeEntitlementPolicy
    ) {
        self.plan = plan
        self.source = source
        self.billingPeriod = billingPeriod
        self.status = status
        self.productID = productID
        self.expiresAt = expiresAt
        self.graceExpiresAt = graceExpiresAt
        self.limits = limits
        self.usage = usage
        self.features = features
        self.policy = policy
    }

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
}

public enum LocalSubscriptionState: String, Equatable, Sendable {
    case active
    case gracePeriod = "grace_period"
    case billingRetry = "billing_retry"
    case expired
    case revoked
}

public struct LocalSubscriptionSummary: Equatable, Sendable {
    public let state: LocalSubscriptionState
    public let productID: HikeJournalProductID
    public let expirationDate: Date?
    public let gracePeriodExpirationDate: Date?
    public let willAutoRenew: Bool

    public init(
        state: LocalSubscriptionState,
        productID: HikeJournalProductID,
        expirationDate: Date?,
        gracePeriodExpirationDate: Date?,
        willAutoRenew: Bool
    ) {
        self.state = state
        self.productID = productID
        self.expirationDate = expirationDate
        self.gracePeriodExpirationDate = gracePeriodExpirationDate
        self.willAutoRenew = willAutoRenew
    }
}

public enum LocalSubscriptionInspection: Equatable, Sendable {
    case notLoaded
    case available(LocalSubscriptionSummary?)
    case failed
}

public enum StoreCatalogState: Equatable, Sendable {
    case idle
    case loading
    case loaded
    case failed
}

public enum StoreReconciliationState: Equatable, Sendable {
    case idle
    case synchronizing
    case synchronized
    case failed
}

public enum TransactionListenerState: Equatable, Sendable {
    case stopped
    case running
}

public struct StoreKitCoordinatorSnapshot: Equatable, Sendable {
    public let catalogState: StoreCatalogState
    public let products: [StoreProductInfo]
    public let localSubscription: LocalSubscriptionInspection
    public let authoritativeEntitlement: AuthoritativeEntitlementSnapshot?
    public let reconciliationState: StoreReconciliationState
    public let listenerState: TransactionListenerState
    public let unverifiedEvidenceObserved: Bool

    public init(
        catalogState: StoreCatalogState,
        products: [StoreProductInfo],
        localSubscription: LocalSubscriptionInspection,
        authoritativeEntitlement: AuthoritativeEntitlementSnapshot?,
        reconciliationState: StoreReconciliationState,
        listenerState: TransactionListenerState,
        unverifiedEvidenceObserved: Bool
    ) {
        self.catalogState = catalogState
        self.products = products
        self.localSubscription = localSubscription
        self.authoritativeEntitlement = authoritativeEntitlement
        self.reconciliationState = reconciliationState
        self.listenerState = listenerState
        self.unverifiedEvidenceObserved = unverifiedEvidenceObserved
    }
}

public enum StorePurchaseOutcome: Equatable, Sendable {
    case synchronized(AuthoritativeEntitlementSnapshot)
    case pending
    case userCancelled
    case unverified
}

public enum StoreKitCoordinatorError: Error, Equatable, LocalizedError, Sendable {
    case productLoadingFailed
    case missingProducts([HikeJournalProductID])
    case productNotLoaded(HikeJournalProductID)
    case purchaseFailed
    case unexpectedPurchaseProduct
    case accountTokenMismatch
    case missingSignedTransaction
    case serverSynchronizationFailed
    case entitlementRefreshFailed
    case subscriptionStatusFailed
    case restoreFailed

    public var errorDescription: String? {
        switch self {
        case .productLoadingFailed:
            "HikeJournal could not load App Store products."
        case let .missingProducts(products):
            "The App Store did not return: \(products.map(\.rawValue).joined(separator: ", "))."
        case .productNotLoaded:
            "Load HikeJournal Plus products before purchasing."
        case .purchaseFailed:
            "The App Store purchase did not complete."
        case .unexpectedPurchaseProduct:
            "The verified purchase was for an unexpected product."
        case .accountTokenMismatch:
            "The verified purchase belongs to a different HikeJournal account."
        case .missingSignedTransaction:
            "The verified purchase did not include signed transaction evidence."
        case .serverSynchronizationFailed:
            "HikeJournal could not confirm this purchase with the server."
        case .entitlementRefreshFailed:
            "HikeJournal could not refresh the server entitlement."
        case .subscriptionStatusFailed:
            "HikeJournal could not refresh App Store subscription status."
        case .restoreFailed:
            "The App Store could not restore purchases."
        }
    }
}

public enum StoreKitServerEndpoint {
    public static let transactionSyncPath = "/v1/storekit/transactions/sync"
    public static let entitlementPath = "/v1/me/entitlement"
}

public enum SubscriptionManagement {
    public static let fallbackURL = URL(
        string: "https://apps.apple.com/account/subscriptions"
    )!
}
