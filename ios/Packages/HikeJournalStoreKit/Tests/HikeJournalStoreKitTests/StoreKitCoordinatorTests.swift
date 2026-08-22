import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
import XCTest
@testable import HikeJournalStoreKit

final class StoreKitCoordinatorTests: XCTestCase {
    private let accountID = UUID(uuidString: "11111111-1111-4111-8111-111111111111")!
    private let otherAccountID = UUID(uuidString: "22222222-2222-4222-8222-222222222222")!

    func testProductIdentifiersAndServerPathsRemainStable() {
        XCTAssertEqual(
            HikeJournalProductID.plusMonthly.rawValue,
            "com.hikejournal.app.plus.monthly"
        )
        XCTAssertEqual(
            HikeJournalProductID.plusAnnual.rawValue,
            "com.hikejournal.app.plus.annual"
        )
        XCTAssertEqual(
            StoreKitServerEndpoint.transactionSyncPath,
            "/v1/storekit/transactions/sync"
        )
        XCTAssertEqual(
            StoreKitServerEndpoint.entitlementPath,
            "/v1/me/entitlement"
        )
    }

    func testProductLoadingRequestsOnlyKnownProductsAndOrdersAnnualFirst() async throws {
        let store = FakeStoreClient()
        let server = FakeEntitlementServer()
        await store.setProducts([
            product(.plusMonthly),
            StoreProductInfo(
                productID: "unexpected.product",
                displayName: "Unexpected",
                description: "",
                displayPrice: "$0",
                price: 0,
                subscriptionPeriod: nil
            ),
            product(.plusAnnual),
        ])
        let coordinator = StoreKitCoordinator(store: store, server: server)

        let loaded = try await coordinator.loadProducts()
        let requested = await store.requestedProductIDs()
        let state = await coordinator.snapshot()

        XCTAssertEqual(
            loaded.map(\.productID),
            [
                HikeJournalProductID.plusAnnual.rawValue,
                HikeJournalProductID.plusMonthly.rawValue,
            ]
        )
        XCTAssertEqual(
            requested,
            Set(HikeJournalProductID.allCases.map(\.rawValue))
        )
        XCTAssertEqual(state.catalogState, .loaded)
    }

    func testProductLoadingFailsWhenEitherConfiguredProductIsMissing() async {
        let store = FakeStoreClient()
        await store.setProducts([product(.plusMonthly)])
        let coordinator = StoreKitCoordinator(
            store: store,
            server: FakeEntitlementServer()
        )

        do {
            _ = try await coordinator.loadProducts()
            XCTFail("Expected the missing annual product to fail loading")
        } catch {
            XCTAssertEqual(
                error as? StoreKitCoordinatorError,
                .missingProducts([.plusAnnual])
            )
        }
        let state = await coordinator.snapshot()
        XCTAssertEqual(state.catalogState, .failed)
    }

    func testProductLoadingMapsStoreErrorWithoutLeakingIt() async {
        let store = FakeStoreClient()
        await store.fail(.products)
        let coordinator = StoreKitCoordinator(
            store: store,
            server: FakeEntitlementServer()
        )

        do {
            _ = try await coordinator.loadProducts()
            XCTFail("Expected product loading to fail")
        } catch {
            XCTAssertEqual(error as? StoreKitCoordinatorError, .productLoadingFailed)
        }
    }

    func testVerifiedPurchaseUsesCanonicalTokenSyncsRenewalThenFinishes() async throws {
        let log = CallLog()
        let store = FakeStoreClient(log: log)
        let server = FakeEntitlementServer(log: log)
        let authoritative = entitlement(plan: .plus, source: .appleSubscription)
        let purchaseTransaction = transaction(appAccountToken: accountID)
        let renewal = status(
            state: .subscribed,
            transaction: purchaseTransaction,
            willAutoRenew: true,
            signedRenewalInfo: "renewal.payload.signature"
        )
        await store.setProducts(allProducts())
        await store.setPurchaseResult(.success(.verified(purchaseTransaction)))
        await store.setStatuses([.verified(renewal)])
        await server.setSyncResult(.success(authoritative))
        let coordinator = StoreKitCoordinator(store: store, server: server)
        _ = try await coordinator.loadProducts()

        let result = try await coordinator.purchase(
            .plusAnnual,
            appAccountToken: accountID
        )
        let purchases = await store.purchaseRequests()
        let requests = await server.syncRequests()
        let finished = await store.finishedTransactionIDs()
        let events = await log.events()
        let state = await coordinator.snapshot()

        XCTAssertEqual(result, .synchronized(authoritative))
        XCTAssertEqual(
            purchases,
            [PurchaseRequest(productID: HikeJournalProductID.plusAnnual.rawValue, token: accountID)]
        )
        XCTAssertEqual(
            requests,
            [
                StoreKitTransactionSyncRequest(
                    signedTransaction: "transaction.payload.signature",
                    signedRenewalInfo: "renewal.payload.signature"
                ),
            ]
        )
        XCTAssertEqual(finished, [9001])
        XCTAssertEqual(events, ["server.sync", "store.finish:9001"])
        XCTAssertEqual(state.authoritativeEntitlement, authoritative)
        XCTAssertEqual(state.reconciliationState, .synchronized)
    }

    func testVerifiedPurchaseUsesServerFreeResponseInsteadOfLocallyGrantingPlus() async throws {
        let store = FakeStoreClient()
        let server = FakeEntitlementServer()
        let serverFree = entitlement(plan: .free, source: .free)
        await store.setProducts(allProducts())
        await store.setPurchaseResult(
            .success(.verified(transaction(appAccountToken: accountID)))
        )
        await server.setSyncResult(.success(serverFree))
        let coordinator = StoreKitCoordinator(store: store, server: server)
        _ = try await coordinator.loadProducts()

        let result = try await coordinator.purchase(
            .plusAnnual,
            appAccountToken: accountID
        )
        let state = await coordinator.snapshot()

        XCTAssertEqual(result, .synchronized(serverFree))
        XCTAssertEqual(state.authoritativeEntitlement?.plan, .free)
    }

    func testCancelledPendingAndUnverifiedPurchasesNeverReachServerOrFinish() async throws {
        let scenarios: [(StorePurchaseResult, StorePurchaseOutcome, Bool)] = [
            (.userCancelled, .userCancelled, false),
            (.pending, .pending, false),
            (.success(.unverified), .unverified, true),
        ]

        for (purchaseResult, expected, unverified) in scenarios {
            let store = FakeStoreClient()
            let server = FakeEntitlementServer()
            await store.setProducts(allProducts())
            await store.setPurchaseResult(purchaseResult)
            let coordinator = StoreKitCoordinator(store: store, server: server)
            _ = try await coordinator.loadProducts()

            let result = try await coordinator.purchase(
                .plusMonthly,
                appAccountToken: accountID
            )
            let requests = await server.syncRequests()
            let finished = await store.finishedTransactionIDs()
            let state = await coordinator.snapshot()

            XCTAssertEqual(result, expected)
            XCTAssertEqual(requests, [])
            XCTAssertEqual(finished, [])
            XCTAssertNil(state.authoritativeEntitlement)
            XCTAssertEqual(state.unverifiedEvidenceObserved, unverified)
        }
    }

    func testStorePurchaseErrorIsBoundedAndNeverReachesServer() async throws {
        let store = FakeStoreClient()
        let server = FakeEntitlementServer()
        await store.setProducts(allProducts())
        await store.fail(.purchase)
        let coordinator = StoreKitCoordinator(store: store, server: server)
        _ = try await coordinator.loadProducts()

        do {
            _ = try await coordinator.purchase(
                .plusMonthly,
                appAccountToken: accountID
            )
            XCTFail("Expected StoreKit purchase failure")
        } catch {
            XCTAssertEqual(error as? StoreKitCoordinatorError, .purchaseFailed)
        }

        let requests = await server.syncRequests()
        let finished = await store.finishedTransactionIDs()
        XCTAssertEqual(requests, [])
        XCTAssertEqual(finished, [])
    }

    func testPurchaseRejectsMissingOrDifferentAppAccountToken() async throws {
        for token in [nil, otherAccountID] as [UUID?] {
            let store = FakeStoreClient()
            let server = FakeEntitlementServer()
            await store.setProducts(allProducts())
            await store.setPurchaseResult(
                .success(.verified(transaction(appAccountToken: token)))
            )
            let coordinator = StoreKitCoordinator(store: store, server: server)
            _ = try await coordinator.loadProducts()

            do {
                _ = try await coordinator.purchase(
                    .plusAnnual,
                    appAccountToken: accountID
                )
                XCTFail("Expected appAccountToken mismatch")
            } catch {
                XCTAssertEqual(
                    error as? StoreKitCoordinatorError,
                    .accountTokenMismatch
                )
            }
            let requests = await server.syncRequests()
            let finished = await store.finishedTransactionIDs()
            XCTAssertEqual(requests, [])
            XCTAssertEqual(finished, [])
        }
    }

    func testServerFailureLeavesVerifiedTransactionUnfinishedForRetry() async throws {
        let store = FakeStoreClient()
        let server = FakeEntitlementServer()
        await store.setProducts(allProducts())
        await store.setPurchaseResult(
            .success(.verified(transaction(appAccountToken: accountID)))
        )
        await server.setSyncResult(.failure(.failed))
        let coordinator = StoreKitCoordinator(store: store, server: server)
        _ = try await coordinator.loadProducts()

        do {
            _ = try await coordinator.purchase(
                .plusAnnual,
                appAccountToken: accountID
            )
            XCTFail("Expected server synchronization to fail")
        } catch {
            XCTAssertEqual(
                error as? StoreKitCoordinatorError,
                .serverSynchronizationFailed
            )
        }

        let finished = await store.finishedTransactionIDs()
        let state = await coordinator.snapshot()
        XCTAssertEqual(finished, [])
        XCTAssertNil(state.authoritativeEntitlement)
        XCTAssertEqual(state.reconciliationState, .failed)
    }

    func testCurrentEntitlementsRefreshIgnoresUnverifiedAndWrongAccountEvidence() async throws {
        let store = FakeStoreClient()
        let server = FakeEntitlementServer()
        let matching = transaction(
            transactionID: 9003,
            appAccountToken: accountID,
            signedRenewalInfo: "renewal.current.signature"
        )
        await store.setCurrentEntitlements([
            .unverified,
            .verified(transaction(transactionID: 9002, appAccountToken: otherAccountID)),
            .verified(matching),
        ])
        await server.setSyncResult(
            .success(entitlement(plan: .plus, source: .appleSubscription))
        )
        let coordinator = StoreKitCoordinator(store: store, server: server)

        let result = try await coordinator.refreshEntitlements(
            appAccountToken: accountID
        )
        let requestCount = await server.syncRequests().count
        let finished = await store.finishedTransactionIDs()
        let state = await coordinator.snapshot()

        XCTAssertEqual(result.plan, .plus)
        XCTAssertEqual(requestCount, 1)
        XCTAssertEqual(finished, [9003])
        XCTAssertTrue(state.unverifiedEvidenceObserved)
    }

    func testRefreshWithoutStoreKitPurchaseLoadsServerLifetime() async throws {
        let store = FakeStoreClient()
        let server = FakeEntitlementServer()
        let lifetime = entitlement(plan: .lifetime, source: .googlePlayLegacy)
        await store.setCurrentEntitlements([])
        await server.setFetchResult(.success(lifetime))
        let coordinator = StoreKitCoordinator(store: store, server: server)

        let result = try await coordinator.refreshEntitlements(
            appAccountToken: accountID
        )
        let requests = await server.syncRequests()
        let fetchCount = await server.fetchCount()
        let state = await coordinator.snapshot()

        XCTAssertEqual(result, lifetime)
        XCTAssertEqual(requests, [])
        XCTAssertEqual(fetchCount, 1)
        XCTAssertEqual(state.authoritativeEntitlement?.source, .googlePlayLegacy)
    }

    func testRestoreCallsAppStoreSyncThenReconcilesServerState() async throws {
        let log = CallLog()
        let store = FakeStoreClient(log: log)
        let server = FakeEntitlementServer(log: log)
        let lifetime = entitlement(plan: .lifetime, source: .admin)
        await store.setCurrentEntitlements([])
        await server.setFetchResult(.success(lifetime))
        let coordinator = StoreKitCoordinator(store: store, server: server)

        let result = try await coordinator.restorePurchases(
            appAccountToken: accountID
        )
        let synchronizeCount = await store.synchronizeCount()
        let events = await log.events()

        XCTAssertEqual(result, lifetime)
        XCTAssertEqual(synchronizeCount, 1)
        XCTAssertEqual(events, ["store.synchronize", "server.fetch"])
    }

    func testRestoreFailureDoesNotFetchOrChangeEntitlement() async {
        let store = FakeStoreClient()
        let server = FakeEntitlementServer()
        await store.fail(.synchronize)
        let coordinator = StoreKitCoordinator(store: store, server: server)

        do {
            _ = try await coordinator.restorePurchases(
                appAccountToken: accountID
            )
            XCTFail("Expected restore to fail")
        } catch {
            XCTAssertEqual(error as? StoreKitCoordinatorError, .restoreFailed)
        }
        let fetchCount = await server.fetchCount()
        let state = await coordinator.snapshot()
        XCTAssertEqual(fetchCount, 0)
        XCTAssertNil(state.authoritativeEntitlement)
    }

    func testSubscriptionStatusCoversActiveGraceRetryExpiredAndRevoked() async throws {
        let mappings: [(StoreSubscriptionState, LocalSubscriptionState)] = [
            (.subscribed, .active),
            (.inGracePeriod, .gracePeriod),
            (.inBillingRetryPeriod, .billingRetry),
            (.expired, .expired),
            (.revoked, .revoked),
        ]

        for (storeState, localState) in mappings {
            let store = FakeStoreClient()
            let coordinator = StoreKitCoordinator(
                store: store,
                server: FakeEntitlementServer()
            )
            let graceDate = storeState == .inGracePeriod
                ? Date(timeIntervalSince1970: 1_800_000_000)
                : nil
            await store.setStatuses([
                .verified(
                    status(
                        state: storeState,
                        transaction: transaction(appAccountToken: accountID),
                        willAutoRenew: true,
                        gracePeriodExpirationDate: graceDate
                    )
                ),
            ])

            let summary = try await coordinator.refreshSubscriptionStatus()

            XCTAssertEqual(summary?.state, localState)
            XCTAssertEqual(summary?.gracePeriodExpirationDate, graceDate)
        }
    }

    func testCanceledButUnexpiredSubscriptionRemainsLocallyActiveWithAutoRenewOff() async throws {
        let store = FakeStoreClient()
        let coordinator = StoreKitCoordinator(
            store: store,
            server: FakeEntitlementServer()
        )
        await store.setStatuses([
            .verified(
                status(
                    state: .subscribed,
                    transaction: transaction(appAccountToken: accountID),
                    willAutoRenew: false
                )
            ),
        ])

        let summary = try await coordinator.refreshSubscriptionStatus()
        let state = await coordinator.snapshot()

        XCTAssertEqual(summary?.state, .active)
        XCTAssertEqual(summary?.willAutoRenew, false)
        XCTAssertNil(state.authoritativeEntitlement)
    }

    func testUnverifiedSubscriptionStatusIsNeverPresentedAsLocalAccess() async throws {
        let store = FakeStoreClient()
        await store.setStatuses([.unverified])
        let coordinator = StoreKitCoordinator(
            store: store,
            server: FakeEntitlementServer()
        )

        let summary = try await coordinator.refreshSubscriptionStatus()
        let state = await coordinator.snapshot()

        XCTAssertNil(summary)
        XCTAssertEqual(state.localSubscription, .available(nil))
        XCTAssertTrue(state.unverifiedEvidenceObserved)
        XCTAssertNil(state.authoritativeEntitlement)
    }

    func testSubscriptionStatusFailureIsExplicitAndDoesNotChangeAuthority() async {
        let store = FakeStoreClient()
        await store.fail(.statuses)
        let coordinator = StoreKitCoordinator(
            store: store,
            server: FakeEntitlementServer()
        )

        do {
            _ = try await coordinator.refreshSubscriptionStatus()
            XCTFail("Expected subscription status failure")
        } catch {
            XCTAssertEqual(
                error as? StoreKitCoordinatorError,
                .subscriptionStatusFailed
            )
        }

        let state = await coordinator.snapshot()
        XCTAssertEqual(state.localSubscription, .failed)
        XCTAssertNil(state.authoritativeEntitlement)
    }

    func testTransactionListenerIsIdempotentAndSynchronizesVerifiedUpdates() async throws {
        let store = FakeStoreClient()
        let server = FakeEntitlementServer()
        let authoritative = entitlement(plan: .plus, source: .appleSubscription)
        await server.setSyncResult(.success(authoritative))
        let coordinator = StoreKitCoordinator(store: store, server: server)

        await coordinator.startTransactionListener(appAccountToken: accountID)
        await coordinator.startTransactionListener(appAccountToken: accountID)
        let streamCount = await store.transactionUpdateStreamCount()
        let runningState = await coordinator.snapshot()
        XCTAssertEqual(streamCount, 1)
        XCTAssertEqual(runningState.listenerState, .running)

        await store.sendUpdate(
            .verified(transaction(transactionID: 9010, appAccountToken: accountID))
        )
        let synchronized = await eventually {
            let requests = await server.syncRequests()
            let finished = await store.finishedTransactionIDs()
            return requests.count == 1 && finished == [9010]
        }
        XCTAssertTrue(synchronized)
        let synchronizedState = await coordinator.snapshot()
        XCTAssertEqual(synchronizedState.authoritativeEntitlement, authoritative)

        await coordinator.stopTransactionListener()
        let stoppedState = await coordinator.snapshot()
        XCTAssertEqual(stoppedState.listenerState, .stopped)
        await store.finishUpdateStreams()
    }

    func testListenerDropsUnverifiedUpdateAndKeepsVerifiedServerFailureUnfinished() async {
        let store = FakeStoreClient()
        let server = FakeEntitlementServer()
        await server.setSyncResult(.failure(.failed))
        let coordinator = StoreKitCoordinator(store: store, server: server)
        await coordinator.startTransactionListener(appAccountToken: accountID)

        await store.sendUpdate(.unverified)
        await store.sendUpdate(
            .verified(transaction(transactionID: 9011, appAccountToken: accountID))
        )
        let attempted = await eventually {
            let requests = await server.syncRequests()
            return requests.count == 1
        }

        let finished = await store.finishedTransactionIDs()
        let state = await coordinator.snapshot()
        XCTAssertTrue(attempted)
        XCTAssertEqual(finished, [])
        XCTAssertTrue(state.unverifiedEvidenceObserved)
        XCTAssertEqual(state.reconciliationState, .failed)
        XCTAssertEqual(state.listenerState, .running)
        await coordinator.stopTransactionListener()
        await store.finishUpdateStreams()
    }

    func testTransactionSyncRequestUsesExactCamelCasePayloadAndHTTPSPath() throws {
        let client = try URLSessionEntitlementServerClient(
            baseURL: URL(string: "https://api.example.test/mobile")!,
            accessToken: { "unused" }
        )
        let payload = StoreKitTransactionSyncRequest(
            signedTransaction: "transaction.payload.signature",
            signedRenewalInfo: "renewal.payload.signature"
        )

        let request = try client.makeTransactionSyncURLRequest(
            payload,
            accessToken: "access-token"
        )
        let object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: try XCTUnwrap(request.httpBody))
                as? [String: String]
        )

        XCTAssertEqual(
            request.url?.absoluteString,
            "https://api.example.test/mobile/v1/storekit/transactions/sync"
        )
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(
            request.value(forHTTPHeaderField: "Authorization"),
            "Bearer access-token"
        )
        XCTAssertEqual(
            object,
            [
                "signedTransaction": "transaction.payload.signature",
                "signedRenewalInfo": "renewal.payload.signature",
            ]
        )
        XCTAssertNil(object["isLifetimeOwner"])
        XCTAssertNil(object["appAccountToken"])
    }

    func testServerClientDecodesAuthoritativeSnapshotAndNeverInfersItLocally() async throws {
        URLProtocolStub.handler = { request in
            XCTAssertEqual(
                request.url?.path,
                "/v1/storekit/transactions/sync"
            )
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 200,
                httpVersion: "HTTP/1.1",
                headerFields: ["Content-Type": "application/json"]
            )!
            return (response, Data(Self.serverLifetimeJSON.utf8))
        }
        defer { URLProtocolStub.handler = nil }
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [URLProtocolStub.self]
        let session = URLSession(configuration: configuration)
        let client = try URLSessionEntitlementServerClient(
            baseURL: URL(string: "https://api.example.test")!,
            session: session,
            accessToken: { "access-token" }
        )

        let snapshot = try await client.sync(
            StoreKitTransactionSyncRequest(
                signedTransaction: "transaction.payload.signature"
            )
        )

        XCTAssertEqual(snapshot.plan, .lifetime)
        XCTAssertEqual(snapshot.source, .googlePlayLegacy)
        XCTAssertEqual(snapshot.status, .active)
        XCTAssertEqual(snapshot.limits.cloudMedia, 10_000)
        XCTAssertEqual(snapshot.features["field_briefing"], true)
    }

    func testServerClientRejectsInsecureURLAndInvalidBearerToken() throws {
        XCTAssertThrowsError(
            try URLSessionEntitlementServerClient(
                baseURL: URL(string: "http://api.example.test")!,
                accessToken: { "token" }
            )
        ) { error in
            XCTAssertEqual(error as? EntitlementServerClientError, .insecureBaseURL)
        }

        let client = try URLSessionEntitlementServerClient(
            baseURL: URL(string: "https://api.example.test")!,
            accessToken: { "unused" }
        )
        XCTAssertThrowsError(
            try client.makeTransactionSyncURLRequest(
                StoreKitTransactionSyncRequest(
                    signedTransaction: "transaction.payload.signature"
                ),
                accessToken: "token with spaces"
            )
        ) { error in
            XCTAssertEqual(error as? EntitlementServerClientError, .invalidAccessToken)
        }
    }

    func testManageSubscriptionsHasOfficialFallbackURL() {
        XCTAssertEqual(
            SubscriptionManagement.fallbackURL.absoluteString,
            "https://apps.apple.com/account/subscriptions"
        )
    }

    private static let serverLifetimeJSON = """
    {
      "plan": "lifetime",
      "source": "google_play_legacy",
      "billing_period": "lifetime",
      "status": "active",
      "product_id": "com.hikejournal.android.paid",
      "expires_at": null,
      "grace_expires_at": null,
      "limits": {"cloud_hikes": null, "cloud_media": 10000},
      "usage": {"cloud_hikes": 7, "cloud_media": 12},
      "features": {"field_briefing": true},
      "policy": {"version": "2026-08-21", "android_paid_compatibility": "observe_only"}
    }
    """
}

private enum FakeFailure: Error {
    case failed
}

private enum FakeStoreOperation: Hashable {
    case products
    case purchase
    case statuses
    case synchronize
}

private struct PurchaseRequest: Equatable, Sendable {
    let productID: String
    let token: UUID
}

private actor CallLog {
    private var values: [String] = []

    func record(_ value: String) {
        values.append(value)
    }

    func events() -> [String] {
        values
    }
}

private actor FakeStoreClient: HikeJournalStoreClient {
    private var configuredProducts: [StoreProductInfo] = []
    private var productIdentifiers: Set<String> = []
    private var configuredPurchaseResult: StorePurchaseResult = .userCancelled
    private var purchases: [PurchaseRequest] = []
    private var currentResults: [StoreVerification<StoreTransactionEvidence>] = []
    private var configuredStatuses: [StoreVerification<StoreSubscriptionStatusEvidence>] = []
    private var failures: Set<FakeStoreOperation> = []
    private var finishedIDs: [UInt64] = []
    private var synchronizeCalls = 0
    private var updateStreamCalls = 0
    private var updateContinuations: [
        AsyncStream<StoreVerification<StoreTransactionEvidence>>.Continuation
    ] = []
    private let log: CallLog?

    init(log: CallLog? = nil) {
        self.log = log
    }

    func setProducts(_ products: [StoreProductInfo]) {
        configuredProducts = products
    }

    func setPurchaseResult(_ result: StorePurchaseResult) {
        configuredPurchaseResult = result
    }

    func setCurrentEntitlements(
        _ results: [StoreVerification<StoreTransactionEvidence>]
    ) {
        currentResults = results
    }

    func setStatuses(
        _ statuses: [StoreVerification<StoreSubscriptionStatusEvidence>]
    ) {
        configuredStatuses = statuses
    }

    func fail(_ operation: FakeStoreOperation) {
        failures.insert(operation)
    }

    func products(for identifiers: Set<String>) async throws -> [StoreProductInfo] {
        productIdentifiers = identifiers
        if failures.contains(.products) { throw FakeFailure.failed }
        return configuredProducts
    }

    func purchase(
        productID: String,
        appAccountToken: UUID
    ) async throws -> StorePurchaseResult {
        purchases.append(PurchaseRequest(productID: productID, token: appAccountToken))
        if failures.contains(.purchase) { throw FakeFailure.failed }
        return configuredPurchaseResult
    }

    func currentEntitlements()
        async -> AsyncStream<StoreVerification<StoreTransactionEvidence>>
    {
        let results = currentResults
        return AsyncStream { continuation in
            for result in results { continuation.yield(result) }
            continuation.finish()
        }
    }

    func transactionUpdates()
        async -> AsyncStream<StoreVerification<StoreTransactionEvidence>>
    {
        updateStreamCalls += 1
        let pair = AsyncStream.makeStream(
            of: StoreVerification<StoreTransactionEvidence>.self
        )
        updateContinuations.append(pair.continuation)
        return pair.stream
    }

    func subscriptionStatuses(
        for _: Set<String>
    ) async throws -> [StoreVerification<StoreSubscriptionStatusEvidence>] {
        if failures.contains(.statuses) { throw FakeFailure.failed }
        return configuredStatuses
    }

    func synchronize() async throws {
        synchronizeCalls += 1
        await log?.record("store.synchronize")
        if failures.contains(.synchronize) { throw FakeFailure.failed }
    }

    func finish(transactionID: UInt64) async {
        finishedIDs.append(transactionID)
        await log?.record("store.finish:\(transactionID)")
    }

    func sendUpdate(_ update: StoreVerification<StoreTransactionEvidence>) {
        for continuation in updateContinuations {
            continuation.yield(update)
        }
    }

    func finishUpdateStreams() {
        for continuation in updateContinuations { continuation.finish() }
        updateContinuations = []
    }

    func requestedProductIDs() -> Set<String> { productIdentifiers }
    func purchaseRequests() -> [PurchaseRequest] { purchases }
    func finishedTransactionIDs() -> [UInt64] { finishedIDs }
    func synchronizeCount() -> Int { synchronizeCalls }
    func transactionUpdateStreamCount() -> Int { updateStreamCalls }
}

private actor FakeEntitlementServer: HikeJournalEntitlementServer {
    private var configuredSyncResult: Result<AuthoritativeEntitlementSnapshot, FakeFailure>
    private var configuredFetchResult: Result<AuthoritativeEntitlementSnapshot, FakeFailure>
    private var requests: [StoreKitTransactionSyncRequest] = []
    private var fetchCalls = 0
    private let log: CallLog?

    init(log: CallLog? = nil) {
        self.log = log
        configuredSyncResult = .success(
            entitlement(plan: .plus, source: .appleSubscription)
        )
        configuredFetchResult = .success(entitlement(plan: .free, source: .free))
    }

    func setSyncResult(
        _ result: Result<AuthoritativeEntitlementSnapshot, FakeFailure>
    ) {
        configuredSyncResult = result
    }

    func setFetchResult(
        _ result: Result<AuthoritativeEntitlementSnapshot, FakeFailure>
    ) {
        configuredFetchResult = result
    }

    func sync(
        _ request: StoreKitTransactionSyncRequest
    ) async throws -> AuthoritativeEntitlementSnapshot {
        requests.append(request)
        await log?.record("server.sync")
        return try configuredSyncResult.get()
    }

    func fetchEntitlement() async throws -> AuthoritativeEntitlementSnapshot {
        fetchCalls += 1
        await log?.record("server.fetch")
        return try configuredFetchResult.get()
    }

    func syncRequests() -> [StoreKitTransactionSyncRequest] { requests }
    func fetchCount() -> Int { fetchCalls }
}

private final class URLProtocolStub: URLProtocol {
    nonisolated(unsafe) static var handler: (
        (URLRequest) throws -> (HTTPURLResponse, Data)
    )?

    override class func canInit(with _: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = Self.handler else {
            client?.urlProtocol(self, didFailWithError: FakeFailure.failed)
            return
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}

private func allProducts() -> [StoreProductInfo] {
    HikeJournalProductID.allCases.map(product)
}

private func product(_ id: HikeJournalProductID) -> StoreProductInfo {
    let annual = id == .plusAnnual
    return StoreProductInfo(
        productID: id.rawValue,
        displayName: annual ? "HikeJournal Plus Annual" : "HikeJournal Plus Monthly",
        description: "HikeJournal Plus",
        displayPrice: annual ? "$49.99" : "$4.99",
        price: Decimal(string: annual ? "49.99" : "4.99")!,
        subscriptionPeriod: StoreSubscriptionPeriod(
            value: 1,
            unit: annual ? .year : .month
        )
    )
}

private func transaction(
    transactionID: UInt64 = 9001,
    productID: HikeJournalProductID = .plusAnnual,
    appAccountToken: UUID?,
    signedRenewalInfo: String? = nil
) -> StoreTransactionEvidence {
    StoreTransactionEvidence(
        transactionID: transactionID,
        originalTransactionID: 8001,
        productID: productID.rawValue,
        appAccountToken: appAccountToken,
        purchaseDate: Date(timeIntervalSince1970: 1_700_000_000),
        expirationDate: Date(timeIntervalSince1970: 1_800_000_000),
        revocationDate: nil,
        isUpgraded: false,
        signedTransaction: "transaction.payload.signature",
        signedRenewalInfo: signedRenewalInfo
    )
}

private func status(
    state: StoreSubscriptionState,
    transaction: StoreTransactionEvidence,
    willAutoRenew: Bool,
    gracePeriodExpirationDate: Date? = nil,
    signedRenewalInfo: String = "renewal.payload.signature"
) -> StoreSubscriptionStatusEvidence {
    StoreSubscriptionStatusEvidence(
        state: state,
        transaction: transaction,
        willAutoRenew: willAutoRenew,
        gracePeriodExpirationDate: gracePeriodExpirationDate,
        signedRenewalInfo: signedRenewalInfo
    )
}

private func entitlement(
    plan: AuthoritativePlan,
    source: AuthoritativeEntitlementSource
) -> AuthoritativeEntitlementSnapshot {
    AuthoritativeEntitlementSnapshot(
        plan: plan,
        source: source,
        billingPeriod: plan == .plus ? "annual" : (plan == .lifetime ? "lifetime" : nil),
        status: .active,
        productID: plan == .plus ? HikeJournalProductID.plusAnnual.rawValue : nil,
        expiresAt: plan == .plus ? Date(timeIntervalSince1970: 1_800_000_000) : nil,
        graceExpiresAt: nil,
        limits: AuthoritativeEntitlementLimits(
            cloudHikes: plan == .free ? 3 : nil,
            cloudMedia: plan == .free ? 50 : 10_000
        ),
        usage: AuthoritativeEntitlementUsage(cloudHikes: 1, cloudMedia: 2),
        features: ["field_briefing": plan != .free],
        policy: AuthoritativeEntitlementPolicy(
            version: "2026-08-21",
            androidPaidCompatibility: "observe_only"
        )
    )
}

private func eventually(
    attempts: Int = 100,
    condition: @escaping () async -> Bool
) async -> Bool {
    for _ in 0 ..< attempts {
        if await condition() { return true }
        try? await Task.sleep(nanoseconds: 5_000_000)
    }
    return false
}
