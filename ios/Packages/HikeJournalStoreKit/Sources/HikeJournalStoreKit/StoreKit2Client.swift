import Foundation
import StoreKit

/// The production StoreKit 2 adapter. It is the only layer that handles
/// `VerificationResult` values; unverified payloads are discarded before they
/// enter the coordinator.
public actor StoreKit2Client: HikeJournalStoreClient {
    private var productsByID: [String: Product] = [:]
    private var transactionsByID: [UInt64: Transaction] = [:]

    public init() {}

    public func products(for identifiers: Set<String>) async throws -> [StoreProductInfo] {
        let products = try await Product.products(for: identifiers)
        for product in products {
            productsByID[product.id] = product
        }
        return products.map(Self.productInfo)
    }

    public func purchase(
        productID: String,
        appAccountToken: UUID
    ) async throws -> StorePurchaseResult {
        let product: Product
        if let cached = productsByID[productID] {
            product = cached
        } else if let loaded = try await Product.products(for: [productID]).first {
            productsByID[productID] = loaded
            product = loaded
        } else {
            throw StoreKit2ClientError.productUnavailable
        }

        let result = try await product.purchase(
            options: [.appAccountToken(appAccountToken)]
        )
        switch result {
        case let .success(verification):
            return .success(mapTransaction(verification))
        case .pending:
            return .pending
        case .userCancelled:
            return .userCancelled
        @unknown default:
            throw StoreKit2ClientError.unknownPurchaseResult
        }
    }

    public func currentEntitlements()
        -> AsyncStream<StoreVerification<StoreTransactionEvidence>>
    {
        AsyncStream { continuation in
            let task = Task { [weak self] in
                for await verification in Transaction.currentEntitlements {
                    guard !Task.isCancelled, let self else { break }
                    continuation.yield(await self.mapTransaction(verification))
                }
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    public func transactionUpdates()
        -> AsyncStream<StoreVerification<StoreTransactionEvidence>>
    {
        AsyncStream { continuation in
            let task = Task { [weak self] in
                for await verification in Transaction.updates {
                    guard !Task.isCancelled, let self else { break }
                    continuation.yield(await self.mapTransaction(verification))
                }
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    public func subscriptionStatuses(
        for identifiers: Set<String>
    ) async throws -> [StoreVerification<StoreSubscriptionStatusEvidence>] {
        var results: [StoreVerification<StoreSubscriptionStatusEvidence>] = []
        let products = try await productsForStatus(identifiers)
        for product in products {
            guard let subscription = product.subscription else { continue }
            for status in try await subscription.status {
                results.append(mapStatus(status))
            }
        }
        return results
    }

    public func synchronize() async throws {
        try await AppStore.sync()
    }

    public func finish(transactionID: UInt64) async {
        guard let transaction = transactionsByID[transactionID] else { return }
        await transaction.finish()
        transactionsByID[transactionID] = nil
    }

    private func productsForStatus(_ identifiers: Set<String>) async throws -> [Product] {
        let missing = identifiers.filter { productsByID[$0] == nil }
        if !missing.isEmpty {
            let loaded = try await Product.products(for: missing)
            for product in loaded {
                productsByID[product.id] = product
            }
        }
        return identifiers.compactMap { productsByID[$0] }
    }

    private func mapTransaction(
        _ verification: VerificationResult<Transaction>,
        signedRenewalInfo: String? = nil
    ) -> StoreVerification<StoreTransactionEvidence> {
        switch verification {
        case .unverified:
            return .unverified
        case let .verified(transaction):
            transactionsByID[transaction.id] = transaction
            return .verified(
                Self.transactionEvidence(
                    transaction,
                    signedTransaction: verification.jwsRepresentation,
                    signedRenewalInfo: signedRenewalInfo
                )
            )
        }
    }

    private func mapStatus(
        _ status: Product.SubscriptionInfo.Status
    ) -> StoreVerification<StoreSubscriptionStatusEvidence> {
        guard case let .verified(transaction) = status.transaction,
              case let .verified(renewalInfo) = status.renewalInfo,
              let state = Self.subscriptionState(status.state)
        else {
            return .unverified
        }
        let signedRenewalInfo = status.renewalInfo.jwsRepresentation
        transactionsByID[transaction.id] = transaction
        let evidence = Self.transactionEvidence(
            transaction,
            signedTransaction: status.transaction.jwsRepresentation,
            signedRenewalInfo: signedRenewalInfo
        )
        return .verified(
            StoreSubscriptionStatusEvidence(
                state: state,
                transaction: evidence,
                willAutoRenew: renewalInfo.willAutoRenew,
                gracePeriodExpirationDate: renewalInfo.gracePeriodExpirationDate,
                signedRenewalInfo: signedRenewalInfo
            )
        )
    }

    private static func transactionEvidence(
        _ transaction: Transaction,
        signedTransaction: String,
        signedRenewalInfo: String?
    ) -> StoreTransactionEvidence {
        StoreTransactionEvidence(
            transactionID: transaction.id,
            originalTransactionID: transaction.originalID,
            productID: transaction.productID,
            appAccountToken: transaction.appAccountToken,
            purchaseDate: transaction.purchaseDate,
            expirationDate: transaction.expirationDate,
            revocationDate: transaction.revocationDate,
            isUpgraded: transaction.isUpgraded,
            signedTransaction: signedTransaction,
            signedRenewalInfo: signedRenewalInfo
        )
    }

    private static func productInfo(_ product: Product) -> StoreProductInfo {
        StoreProductInfo(
            productID: product.id,
            displayName: product.displayName,
            description: product.description,
            displayPrice: product.displayPrice,
            price: product.price,
            subscriptionPeriod: product.subscription.map {
                StoreSubscriptionPeriod(
                    value: $0.subscriptionPeriod.value,
                    unit: subscriptionPeriodUnit($0.subscriptionPeriod.unit)
                )
            }
        )
    }

    private static func subscriptionPeriodUnit(
        _ unit: Product.SubscriptionPeriod.Unit
    ) -> StoreSubscriptionPeriod.Unit {
        switch unit {
        case .day: .day
        case .week: .week
        case .month: .month
        case .year: .year
        @unknown default: .month
        }
    }

    private static func subscriptionState(
        _ state: Product.SubscriptionInfo.RenewalState
    ) -> StoreSubscriptionState? {
        switch state {
        case .subscribed: .subscribed
        case .inGracePeriod: .inGracePeriod
        case .inBillingRetryPeriod: .inBillingRetryPeriod
        case .expired: .expired
        case .revoked: .revoked
        default: nil
        }
    }
}

public enum StoreKit2ClientError: Error, Equatable, LocalizedError, Sendable {
    case productUnavailable
    case unknownPurchaseResult

    public var errorDescription: String? {
        switch self {
        case .productUnavailable:
            "The selected HikeJournal Plus product is not available."
        case .unknownPurchaseResult:
            "The App Store returned an unknown purchase result."
        }
    }
}

#if canImport(UIKit)
import UIKit

public enum StoreKitSubscriptionManagementError: Error, Equatable, Sendable {
    case noActiveWindowScene
}

@MainActor
public final class StoreKitSubscriptionManagementProvider:
    SubscriptionManagementProviding
{
    public typealias SceneProvider = @MainActor @Sendable () -> UIWindowScene?

    public let fallbackURL = SubscriptionManagement.fallbackURL
    private let sceneProvider: SceneProvider

    public init(sceneProvider: @escaping SceneProvider) {
        self.sceneProvider = sceneProvider
    }

    public func showManageSubscriptions() async throws {
        guard let scene = sceneProvider() else {
            throw StoreKitSubscriptionManagementError.noActiveWindowScene
        }
        try await AppStore.showManageSubscriptions(in: scene)
    }
}
#endif
