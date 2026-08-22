import Foundation
import HikeJournalStoreKit

extension APIClient: HikeJournalEntitlementServer {
    func sync(
        _ request: StoreKitTransactionSyncRequest
    ) async throws -> AuthoritativeEntitlementSnapshot {
        let body: Data
        do {
            body = try JSONEncoder().encode(request)
        } catch {
            throw APIClientError.requestEncodingFailed
        }
        return try await send(
            APIRequest(
                method: .post,
                path: StoreKitServerEndpoint.transactionSyncPath,
                body: body
            )
        )
    }

    func fetchEntitlement() async throws -> AuthoritativeEntitlementSnapshot {
        try await send(APIRequest(path: StoreKitServerEndpoint.entitlementPath))
    }
}
