import Foundation

/// Coordinates StoreKit evidence with HikeJournal's server-authoritative
/// entitlement. Verified StoreKit data is never itself exposed as durable
/// access; a successful server response is required before a transaction is
/// finished and before `authoritativeEntitlement` changes.
public actor StoreKitCoordinator {
    private let store: any HikeJournalStoreClient
    private let server: any HikeJournalEntitlementServer

    private var catalogState: StoreCatalogState = .idle
    private var products: [StoreProductInfo] = []
    private var localSubscription: LocalSubscriptionInspection = .notLoaded
    private var authoritativeEntitlement: AuthoritativeEntitlementSnapshot?
    private var reconciliationState: StoreReconciliationState = .idle
    private var listenerState: TransactionListenerState = .stopped
    private var unverifiedEvidenceObserved = false

    private var listenerTask: Task<Void, Never>?
    private var listenerAccountToken: UUID?
    private var listenerGeneration = UUID()

    public init(
        store: any HikeJournalStoreClient,
        server: any HikeJournalEntitlementServer
    ) {
        self.store = store
        self.server = server
    }

    deinit {
        listenerTask?.cancel()
    }

    public func snapshot() -> StoreKitCoordinatorSnapshot {
        StoreKitCoordinatorSnapshot(
            catalogState: catalogState,
            products: products,
            localSubscription: localSubscription,
            authoritativeEntitlement: authoritativeEntitlement,
            reconciliationState: reconciliationState,
            listenerState: listenerState,
            unverifiedEvidenceObserved: unverifiedEvidenceObserved
        )
    }

    @discardableResult
    public func loadProducts() async throws -> [StoreProductInfo] {
        catalogState = .loading
        do {
            let loaded = try await store.products(
                for: Set(HikeJournalProductID.allCases.map(\.rawValue))
            )
            var unique: [HikeJournalProductID: StoreProductInfo] = [:]
            for product in loaded {
                guard let identifier = HikeJournalProductID(rawValue: product.productID) else {
                    continue
                }
                unique[identifier] = product
            }
            let missing = HikeJournalProductID.allCases.filter { unique[$0] == nil }
            guard missing.isEmpty else {
                products = unique.values.sorted(by: productOrder)
                catalogState = .failed
                throw StoreKitCoordinatorError.missingProducts(missing)
            }
            products = unique.values.sorted(by: productOrder)
            catalogState = .loaded
            return products
        } catch let error as StoreKitCoordinatorError {
            throw error
        } catch {
            catalogState = .failed
            throw StoreKitCoordinatorError.productLoadingFailed
        }
    }

    public func purchase(
        _ productID: HikeJournalProductID,
        appAccountToken: UUID
    ) async throws -> StorePurchaseOutcome {
        guard products.contains(where: { $0.productID == productID.rawValue }) else {
            throw StoreKitCoordinatorError.productNotLoaded(productID)
        }

        let result: StorePurchaseResult
        do {
            result = try await store.purchase(
                productID: productID.rawValue,
                appAccountToken: appAccountToken
            )
        } catch {
            reconciliationState = .failed
            throw StoreKitCoordinatorError.purchaseFailed
        }

        switch result {
        case .userCancelled:
            reconciliationState = .idle
            return .userCancelled
        case .pending:
            reconciliationState = .idle
            return .pending
        case .success(.unverified):
            unverifiedEvidenceObserved = true
            reconciliationState = .idle
            return .unverified
        case let .success(.verified(transaction)):
            guard transaction.productID == productID.rawValue else {
                reconciliationState = .failed
                throw StoreKitCoordinatorError.unexpectedPurchaseProduct
            }
            let entitlement = try await reconcile(
                transaction,
                appAccountToken: appAccountToken
            )
            await refreshSubscriptionStatusBestEffort()
            return .synchronized(entitlement)
        }
    }

    /// Replays every currently verified HikeJournal subscription through the
    /// backend and then refreshes backend state. A Google legacy Lifetime plan
    /// therefore remains authoritative even when StoreKit has no transaction.
    @discardableResult
    public func refreshEntitlements(
        appAccountToken: UUID
    ) async throws -> AuthoritativeEntitlementSnapshot {
        reconciliationState = .synchronizing
        let stream = await store.currentEntitlements()
        var transactions: [StoreTransactionEvidence] = []
        for await result in stream {
            if Task.isCancelled { break }
            switch result {
            case let .verified(transaction):
                transactions.append(transaction)
            case .unverified:
                unverifiedEvidenceObserved = true
            }
        }

        transactions.sort { lhs, rhs in
            if lhs.purchaseDate != rhs.purchaseDate {
                return lhs.purchaseDate < rhs.purchaseDate
            }
            return lhs.transactionID < rhs.transactionID
        }

        var latestSnapshot: AuthoritativeEntitlementSnapshot?
        for transaction in transactions {
            guard isEligibleForAccount(
                transaction,
                appAccountToken: appAccountToken
            ) else {
                continue
            }
            latestSnapshot = try await reconcile(
                transaction,
                appAccountToken: appAccountToken
            )
        }

        if latestSnapshot == nil {
            do {
                latestSnapshot = try await server.fetchEntitlement()
                authoritativeEntitlement = latestSnapshot
                reconciliationState = .synchronized
            } catch {
                reconciliationState = .failed
                throw StoreKitCoordinatorError.entitlementRefreshFailed
            }
        }

        await refreshSubscriptionStatusBestEffort()
        guard let latestSnapshot else {
            reconciliationState = .failed
            throw StoreKitCoordinatorError.entitlementRefreshFailed
        }
        return latestSnapshot
    }

    @discardableResult
    public func restorePurchases(
        appAccountToken: UUID
    ) async throws -> AuthoritativeEntitlementSnapshot {
        do {
            try await store.synchronize()
        } catch {
            reconciliationState = .failed
            throw StoreKitCoordinatorError.restoreFailed
        }
        return try await refreshEntitlements(appAccountToken: appAccountToken)
    }

    @discardableResult
    public func refreshSubscriptionStatus() async throws -> LocalSubscriptionSummary? {
        let results: [StoreVerification<StoreSubscriptionStatusEvidence>]
        do {
            results = try await store.subscriptionStatuses(
                for: Set(HikeJournalProductID.allCases.map(\.rawValue))
            )
        } catch {
            localSubscription = .failed
            throw StoreKitCoordinatorError.subscriptionStatusFailed
        }

        var verified: [StoreSubscriptionStatusEvidence] = []
        for result in results {
            switch result {
            case let .verified(status):
                guard HikeJournalProductID(rawValue: status.transaction.productID) != nil else {
                    continue
                }
                verified.append(status)
            case .unverified:
                unverifiedEvidenceObserved = true
            }
        }

        let summary = verified.max(by: statusOrder).flatMap(localSummary)
        localSubscription = .available(summary)
        return summary
    }

    /// Starts one listener per signed-in canonical account. Starting again for
    /// the same UUID is idempotent; changing accounts cancels the old listener.
    public func startTransactionListener(appAccountToken: UUID) async {
        if listenerTask != nil, listenerAccountToken == appAccountToken {
            return
        }
        stopTransactionListener()

        let stream = await store.transactionUpdates()
        let generation = UUID()
        listenerGeneration = generation
        listenerAccountToken = appAccountToken
        listenerState = .running
        listenerTask = Task { [weak self] in
            for await update in stream {
                if Task.isCancelled { break }
                await self?.consumeTransactionUpdate(
                    update,
                    appAccountToken: appAccountToken
                )
            }
            await self?.listenerDidFinish(generation: generation)
        }
    }

    public func stopTransactionListener() {
        listenerGeneration = UUID()
        listenerTask?.cancel()
        listenerTask = nil
        listenerAccountToken = nil
        listenerState = .stopped
    }

    private func consumeTransactionUpdate(
        _ update: StoreVerification<StoreTransactionEvidence>,
        appAccountToken: UUID
    ) async {
        switch update {
        case .unverified:
            unverifiedEvidenceObserved = true
        case let .verified(transaction):
            guard isEligibleForAccount(
                transaction,
                appAccountToken: appAccountToken
            ) else {
                return
            }
            do {
                _ = try await reconcile(
                    transaction,
                    appAccountToken: appAccountToken
                )
                await refreshSubscriptionStatusBestEffort()
            } catch {
                // Keep listening so StoreKit can redeliver later. The verified
                // transaction remains unfinished until backend sync succeeds.
                reconciliationState = .failed
            }
        }
    }

    private func listenerDidFinish(generation: UUID) {
        guard listenerGeneration == generation else { return }
        listenerTask = nil
        listenerAccountToken = nil
        listenerState = .stopped
    }

    private func reconcile(
        _ transaction: StoreTransactionEvidence,
        appAccountToken: UUID
    ) async throws -> AuthoritativeEntitlementSnapshot {
        guard HikeJournalProductID(rawValue: transaction.productID) != nil else {
            reconciliationState = .failed
            throw StoreKitCoordinatorError.unexpectedPurchaseProduct
        }
        guard !transaction.isUpgraded else {
            reconciliationState = .failed
            throw StoreKitCoordinatorError.unexpectedPurchaseProduct
        }
        guard transaction.appAccountToken == appAccountToken else {
            reconciliationState = .failed
            throw StoreKitCoordinatorError.accountTokenMismatch
        }
        let signedTransaction = transaction.signedTransaction
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !signedTransaction.isEmpty else {
            reconciliationState = .failed
            throw StoreKitCoordinatorError.missingSignedTransaction
        }

        reconciliationState = .synchronizing
        let signedRenewalInfo = await renewalInfo(for: transaction)
        let request = StoreKitTransactionSyncRequest(
            signedTransaction: signedTransaction,
            signedRenewalInfo: signedRenewalInfo
        )
        let snapshot: AuthoritativeEntitlementSnapshot
        do {
            snapshot = try await server.sync(request)
        } catch {
            reconciliationState = .failed
            throw StoreKitCoordinatorError.serverSynchronizationFailed
        }

        authoritativeEntitlement = snapshot
        reconciliationState = .synchronized
        await store.finish(transactionID: transaction.transactionID)
        return snapshot
    }

    private func renewalInfo(
        for transaction: StoreTransactionEvidence
    ) async -> String? {
        if let signedRenewalInfo = normalized(transaction.signedRenewalInfo) {
            return signedRenewalInfo
        }
        guard let results = try? await store.subscriptionStatuses(
            for: [transaction.productID]
        ) else {
            return nil
        }
        for result in results {
            switch result {
            case let .verified(status)
                where status.transaction.originalTransactionID
                    == transaction.originalTransactionID:
                return normalized(status.signedRenewalInfo)
            case .unverified:
                unverifiedEvidenceObserved = true
            case .verified:
                continue
            }
        }
        return nil
    }

    private func isEligibleForAccount(
        _ transaction: StoreTransactionEvidence,
        appAccountToken: UUID
    ) -> Bool {
        HikeJournalProductID(rawValue: transaction.productID) != nil
            && !transaction.isUpgraded
            && transaction.appAccountToken == appAccountToken
            && normalized(transaction.signedTransaction) != nil
    }

    private func refreshSubscriptionStatusBestEffort() async {
        _ = try? await refreshSubscriptionStatus()
    }
}

private func productOrder(_ lhs: StoreProductInfo, _ rhs: StoreProductInfo) -> Bool {
    let left = HikeJournalProductID(rawValue: lhs.productID)?.displayOrder ?? Int.max
    let right = HikeJournalProductID(rawValue: rhs.productID)?.displayOrder ?? Int.max
    if left != right { return left < right }
    return lhs.productID < rhs.productID
}

private func statusOrder(
    _ lhs: StoreSubscriptionStatusEvidence,
    _ rhs: StoreSubscriptionStatusEvidence
) -> Bool {
    let leftDate = lhs.transaction.expirationDate ?? lhs.transaction.purchaseDate
    let rightDate = rhs.transaction.expirationDate ?? rhs.transaction.purchaseDate
    if leftDate != rightDate { return leftDate < rightDate }
    return statusRank(lhs.state) < statusRank(rhs.state)
}

private func statusRank(_ state: StoreSubscriptionState) -> Int {
    switch state {
    case .expired: 0
    case .revoked: 1
    case .inBillingRetryPeriod: 2
    case .inGracePeriod: 3
    case .subscribed: 4
    }
}

private func localSummary(
    _ status: StoreSubscriptionStatusEvidence
) -> LocalSubscriptionSummary? {
    guard let productID = HikeJournalProductID(
        rawValue: status.transaction.productID
    ) else {
        return nil
    }
    let state: LocalSubscriptionState = switch status.state {
    case .subscribed: .active
    case .inGracePeriod: .gracePeriod
    case .inBillingRetryPeriod: .billingRetry
    case .expired: .expired
    case .revoked: .revoked
    }
    return LocalSubscriptionSummary(
        state: state,
        productID: productID,
        expirationDate: status.transaction.expirationDate,
        gracePeriodExpirationDate: status.gracePeriodExpirationDate,
        willAutoRenew: status.willAutoRenew
    )
}

private func normalized(_ value: String?) -> String? {
    let normalized = value?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    return normalized.isEmpty ? nil : normalized
}
