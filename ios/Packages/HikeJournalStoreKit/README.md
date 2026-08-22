# HikeJournalStoreKit

An isolated iOS 17 StoreKit 2 and entitlement-reconciliation package for
HikeJournal. It is intentionally not coupled to the app target, authentication
store, or Xcode project.

## Integration contract

Create one `StoreKit2Client`, one `URLSessionEntitlementServerClient`, and one
`StoreKitCoordinator` for the signed-in account. Pass the canonical
`app_users.id` UUID to every coordinator purchase, refresh, restore, and
listener call:

```swift
let store = StoreKit2Client()
let server = try URLSessionEntitlementServerClient(
    baseURL: apiBaseURL,
    accessToken: { try await sessionStore.validAccessToken() }
)
let coordinator = StoreKitCoordinator(store: store, server: server)

try await coordinator.loadProducts()
await coordinator.startTransactionListener(appAccountToken: accountUserID)
let entitlement = try await coordinator.refreshEntitlements(
    appAccountToken: accountUserID
)
```

Stop the listener before replacing or signing out the account. Starting it
again for the same UUID is idempotent; starting it for another UUID replaces
the prior listener.

Purchases use StoreKit's `.appAccountToken(accountUserID)` option. Only
verified transactions enter reconciliation. The package posts exactly
`signedTransaction` and optional `signedRenewalInfo` to
`POST /v1/storekit/transactions/sync`, and finishes a transaction only after
the backend returns a fresh authoritative entitlement snapshot. Pending,
cancelled, unverified, mismatched-account, and failed-server cases never finish
or grant durable access.

`StoreKitCoordinatorSnapshot.localSubscription` is display/recovery evidence
for active, canceled-but-unexpired, grace, billing-retry, expired, and revoked
states. Only `authoritativeEntitlement` may drive HikeJournal feature or quota
access, including cross-platform Google legacy Lifetime access.

Use `StoreKitSubscriptionManagementProvider` on iOS to show Apple's native
manage-subscriptions sheet. `SubscriptionManagement.fallbackURL` provides the
official web fallback.

Apple's official server verifier intentionally does not cryptographically
accept Xcode/LocalTesting JWS. Use injected fakes for local package/UI tests and
App Store Sandbox transactions for end-to-end backend synchronization.

## Verification

From this directory:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test
```

The tests use injected StoreKit and server actors; they require no App Store
account, certificate, network request, or real purchase.
