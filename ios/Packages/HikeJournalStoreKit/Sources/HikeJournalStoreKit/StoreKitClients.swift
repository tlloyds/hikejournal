import Foundation

public protocol HikeJournalStoreClient: Sendable {
    func products(for identifiers: Set<String>) async throws -> [StoreProductInfo]
    func purchase(
        productID: String,
        appAccountToken: UUID
    ) async throws -> StorePurchaseResult
    func currentEntitlements() async -> AsyncStream<StoreVerification<StoreTransactionEvidence>>
    func transactionUpdates() async -> AsyncStream<StoreVerification<StoreTransactionEvidence>>
    func subscriptionStatuses(
        for identifiers: Set<String>
    ) async throws -> [StoreVerification<StoreSubscriptionStatusEvidence>]
    func synchronize() async throws
    func finish(transactionID: UInt64) async
}

public protocol HikeJournalEntitlementServer: Sendable {
    func sync(
        _ request: StoreKitTransactionSyncRequest
    ) async throws -> AuthoritativeEntitlementSnapshot
    func fetchEntitlement() async throws -> AuthoritativeEntitlementSnapshot
}

@MainActor
public protocol SubscriptionManagementProviding: AnyObject {
    var fallbackURL: URL { get }
    func showManageSubscriptions() async throws
}
