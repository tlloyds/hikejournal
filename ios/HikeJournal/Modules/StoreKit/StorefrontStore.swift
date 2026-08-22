import Combine
import Foundation
import HikeJournalStoreKit
import UIKit

enum StorefrontPresentationError: Error, LocalizedError {
    case signedInAccountRequired
    case canonicalAccountIDRequired
    case unavailable

    var errorDescription: String? {
        switch self {
        case .signedInAccountRequired:
            "Sign in to buy or restore HikeJournal Plus."
        case .canonicalAccountIDRequired:
            "This account needs to be refreshed before it can use the App Store."
        case .unavailable:
            "The App Store is unavailable in this build."
        }
    }
}

@MainActor
final class StorefrontStore: ObservableObject {
    @Published private(set) var products: [StoreProductInfo] = []
    @Published private(set) var coordinatorSnapshot: StoreKitCoordinatorSnapshot?
    @Published private(set) var isLoading = false
    @Published private(set) var purchasingProductID: String?
    @Published private(set) var notice: String?
    @Published private(set) var errorMessage: String?
    @Published var selectedProductID: HikeJournalProductID = .plusAnnual

    private let authentication: AuthenticationStore
    private let coordinator: StoreKitCoordinator?
    private let subscriptionManagement: StoreKitSubscriptionManagementProvider

    init(
        authentication: AuthenticationStore,
        coordinator: StoreKitCoordinator?
    ) {
        self.authentication = authentication
        self.coordinator = coordinator
        subscriptionManagement = StoreKitSubscriptionManagementProvider {
            UIApplication.shared.connectedScenes
                .compactMap { $0 as? UIWindowScene }
                .first { $0.activationState == .foregroundActive }
        }
    }

    var managementFallbackURL: URL {
        subscriptionManagement.fallbackURL
    }

    func configureForCurrentAccount() async {
        guard let coordinator else { return }
        guard let accountToken = currentAccountToken() else {
            await coordinator.stopTransactionListener()
            coordinatorSnapshot = await coordinator.snapshot()
            products = []
            return
        }

        // A server-granted Lifetime account should never be prompted to buy an
        // Apple subscription and has no transaction listener to reconcile.
        if authentication.entitlement?.plan == .lifetime {
            await coordinator.stopTransactionListener()
            coordinatorSnapshot = await coordinator.snapshot()
            products = []
            return
        }

        await coordinator.startTransactionListener(appAccountToken: accountToken)
        isLoading = true
        defer { isLoading = false }
        do {
            products = try await coordinator.loadProducts()
            _ = try await coordinator.refreshEntitlements(appAccountToken: accountToken)
            await authentication.loadEntitlement(showErrors: false)
            coordinatorSnapshot = await coordinator.snapshot()
        } catch is CancellationError {
            return
        } catch {
            coordinatorSnapshot = await coordinator.snapshot()
            errorMessage = readable(error)
        }
    }

    func purchase(_ productID: HikeJournalProductID) async {
        guard purchasingProductID == nil else { return }
        notice = nil
        errorMessage = nil
        do {
            let coordinator = try availableCoordinator()
            let accountToken = try requiredAccountToken()
            purchasingProductID = productID.rawValue
            defer { purchasingProductID = nil }
            let outcome = try await coordinator.purchase(
                productID,
                appAccountToken: accountToken
            )
            switch outcome {
            case .synchronized:
                await authentication.loadEntitlement(showErrors: false)
                notice = "HikeJournal Plus is ready."
            case .pending:
                notice = "Your purchase is pending approval. HikeJournal will update when the App Store completes it."
            case .userCancelled:
                break
            case .unverified:
                errorMessage = "The App Store purchase could not be verified, so no plan change was applied."
            }
            coordinatorSnapshot = await coordinator.snapshot()
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readable(error)
        }
    }

    func restorePurchases() async {
        guard !isLoading else { return }
        notice = nil
        errorMessage = nil
        isLoading = true
        defer { isLoading = false }
        do {
            let coordinator = try availableCoordinator()
            let accountToken = try requiredAccountToken()
            _ = try await coordinator.restorePurchases(appAccountToken: accountToken)
            await authentication.loadEntitlement(showErrors: false)
            coordinatorSnapshot = await coordinator.snapshot()
            notice = "Purchases restored and checked with HikeJournal."
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readable(error)
        }
    }

    func showManageSubscriptions() async {
        errorMessage = nil
        do {
            try await subscriptionManagement.showManageSubscriptions()
        } catch {
            errorMessage = "Open the App Store subscription page to manage your plan."
        }
    }

    func clearMessages() {
        notice = nil
        errorMessage = nil
    }

    private func availableCoordinator() throws -> StoreKitCoordinator {
        guard let coordinator else { throw StorefrontPresentationError.unavailable }
        return coordinator
    }

    private func currentAccountToken() -> UUID? {
        guard case let .signedIn(account) = authentication.phase,
              let userID = account.userID else {
            return nil
        }
        return UUID(uuidString: userID)
    }

    private func requiredAccountToken() throws -> UUID {
        guard case let .signedIn(account) = authentication.phase else {
            throw StorefrontPresentationError.signedInAccountRequired
        }
        guard let userID = account.userID,
              let token = UUID(uuidString: userID) else {
            throw StorefrontPresentationError.canonicalAccountIDRequired
        }
        return token
    }

    private func readable(_ error: Error) -> String {
        if let localized = error as? LocalizedError,
           let description = localized.errorDescription,
           !description.isEmpty {
            return description
        }
        return "HikeJournal couldn't reach the App Store. Please try again."
    }
}
