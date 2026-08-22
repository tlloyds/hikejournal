# Manual provider, release, and physical-device setup

Everything in this file requires a human-owned provider account, production secret, signing identity, or physical device. Simulator builds and automated tests do not require these steps.

## 1. Apply production database migrations

Back up the production database and record which migrations have already run. Apply only unapplied SQL through the normal Supabase/service-role migration process. For the iOS identity, subscription, jobs, and conditions work, preserve this dependency order:

1. `sql/public_mobile_accounts_migration.sql`
2. `sql/mobile_inat_oauth_migration.sql`
3. `sql/provider_neutral_identity_migration.sql`
4. `sql/entitlements_migration.sql`
5. `sql/mobile_jobs_migration.sql`
6. `sql/outdoor_conditions_cache_migration.sql`

Also apply any earlier feature migration that the deployed database lacks; do not replace a migrated database with `schema.sql`.

After migration, verify:

- each historical Google subject has exactly one `user_identities` row and still resolves to the same `app_users.id`
- historical hikes/photos retain their existing owner subject and receive an unambiguous `owner_user_id` where possible
- Free/Plus/Lifetime policy rows exist and the entitlement/usage RPCs are executable only by the service role
- mobile job, iNaturalist credential, and outdoor-condition cache tables are inaccessible to `anon` and `authenticated`
- `GET /health`, `GET /v1/config`, and an existing Android Google account still work before enabling iOS distribution

The checked-in entitlement migration intentionally leaves existing Android mutation and advanced-feature routes in their paid-app-compatible observe-only stage. Do not globally enforce Free limits or Plus gates until verified Google Play legacy evidence has been migrated; a client platform header or Boolean is not purchase proof.

## 2. Apple Developer signing and capabilities

1. Register the explicit App ID `com.hikejournal.app`.
2. Register the widget extension ID `com.hikejournal.app.widgets`.
3. Enable Sign in with Apple for the main App ID.
4. In Xcode, select the distribution team for `HikeJournal` and `HikeJournalWidgets`; create development and distribution provisioning profiles as needed.
5. Confirm the app target retains Sign in with Apple and Background Modes for Location updates, Background fetch, and Background processing.
6. Confirm `HikeJournalWidgets.appex` is embedded and signed with the app. A separate App Group is not required by the current local Live Activity implementation.
7. Increment `CURRENT_PROJECT_VERSION` before each App Store Connect upload; do not change root `VERSION` merely to produce another build.

Configure the backend with:

```text
APPLE_SIGN_IN_CLIENT_ID=com.hikejournal.app
MOBILE_AUTH_MODE=google
MOBILE_SESSION_SECRET=<long random server-only value>
```

`APPLE_SIGN_IN_CLIENT_ID` is the expected Apple ID-token audience, not an Apple private key. Sign in with Apple uses the native app credential flow; no Apple client secret is embedded in the application.

Before release, verify a new Apple account and an existing Google account separately. The identity resolver deliberately does not merge accounts by matching email.

## 3. Google Sign-In

1. In the same Google Cloud project as the existing server/web OAuth client, create an iOS OAuth client for bundle ID `com.hikejournal.app`.
2. Keep the existing web/server client ID as the backend token audience. Do not replace it with the iOS client ID.
3. Copy `ios/Config/Secrets.example.xcconfig` to the ignored `ios/Config/Secrets.xcconfig`.
4. Set:

```text
GOOGLE_IOS_CLIENT_ID=<new iOS client ID>
GOOGLE_SERVER_CLIENT_ID=<existing web/server client ID>
GOOGLE_REVERSED_CLIENT_ID=<reversed new iOS client ID>
```

5. Set backend `GOOGLE_WEB_CLIENT_ID` to the same existing web/server client ID.
6. Build the app and inspect its installed URL types to confirm the reversed client ID is present.
7. Sign in with a historical Android account and verify its existing journals/media—not merely the profile—are returned.

The official GoogleSignIn SDK is pinned in the Xcode project. No Google client secret belongs in the app.

## 4. Production API, web, maps, and attribution

In the ignored `ios/Config/Secrets.xcconfig`, replace the example values:

```text
HIKEJOURNAL_API_BASE_URL = https:/$()/api.your-domain.example
HIKEJOURNAL_WEB_BASE_URL = https:/$()/www.your-domain.example
HIKEJOURNAL_MAP_STYLE_URL = https:/$()/maps.provider.example/style.json
HIKEJOURNAL_MAP_ATTRIBUTION_TITLE = Provider and data contributors
HIKEJOURNAL_MAP_ATTRIBUTION_URL = https:/$()/maps.provider.example/attribution
HIKEJOURNAL_MAP_STYLE_TOKEN = <public restricted style token if required>
HIKEJOURNAL_MAP_STYLE_TOKEN_QUERY_ITEM_NAME = access_token
```

Keep the `https:/$()/` xcconfig spelling so `//` is not parsed as a comment. API/web/style/attribution URLs must be HTTPS for release. Do not include credentials, a query, or a fragment in a base URL.

Choose a MapLibre-compatible provider whose license permits the intended online and offline use. Configure a token restricted to the appropriate style/domain/bundle where supported. Confirm its attribution text/link in both map UI and offline mode. The debug demo style is not production configuration.

The 4:5 share artifact uses an iOS-native Apple Maps satellite snapshot and prints Apple Maps attribution; it does not reuse or cache the MapLibre provider's satellite tiles.

## 5. Weather, USGS, and iNaturalist providers

### Weather and river conditions

For commercial operation, review the weather provider's current license and rate limits. The server supports configurable Open-Meteo-compatible endpoints:

```text
WEATHER_ENRICHMENT_ENABLED=true
OPEN_METEO_FORECAST_URL=<licensed forecast endpoint>
OPEN_METEO_ARCHIVE_URL=<licensed archive endpoint>
OPEN_METEO_API_KEY=<server-only key when required>
WEATHER_REQUEST_TIMEOUT_SECONDS=20
OUTDOOR_FORECAST_CACHE_MINUTES=15
OUTDOOR_USGS_CACHE_MINUTES=10
USGS_WATER_API_ROOT=https://api.waterdata.usgs.gov/ogcapi/v0/collections
```

Confirm forecast and historical responses include provider attribution. USGS is configured without an app credential by default; keep the displayed USGS source/station links and recheck its production use guidance before launch.

### iNaturalist

Create an iNaturalist OAuth application and register this HTTPS redirect exactly:

```text
https://<public-api-host>/v1/inat/oauth/callback
```

Set server-only values:

```text
INAT_OAUTH_CLIENT_ID=<client ID>
INAT_OAUTH_CLIENT_SECRET=<client secret>
INAT_OAUTH_REDIRECT_URI=https://<public-api-host>/v1/inat/oauth/callback
MOBILE_INAT_OAUTH_REDIRECT_URI=https://<public-api-host>/v1/inat/oauth/callback
```

The backend redirects a completed browser session to `hikejournal://inat?status=connected`. Confirm that iNaturalist accepts the registered HTTPS callback and that the app returns from `ASWebAuthenticationSession`. The credential is encrypted using a key derived from the server-only mobile session secret; never put the iNaturalist secret/token in Xcode configuration.

Run a sandbox/staging recommendation and publication with disposable observations before production. Confirm geoprivacy, photo grouping, partial failures, retry behavior, and public observation links.

## 6. App Store Connect and StoreKit

Create one auto-renewable subscription group:

```text
HikeJournal Plus
```

Create these products exactly unless App Store Connect reports that an identifier is permanently unavailable:

```text
com.hikejournal.app.plus.monthly   $4.99/month
com.hikejournal.app.plus.annual    $49.99/year
```

If an identifier must change, update it together in `HikeJournal.storekit`, `HikeJournalProductID`, backend product allowlists/tests, App Store Connect, and this document before shipping. Both products must remain in the same group. Add localized display names/descriptions, availability, tax/category information, and review screenshots. The annual product remains the default presentation, but both choices are explicit.

The checked-in StoreKit configuration supports local product loading and purchase UI. Xcode LocalTesting transactions are not accepted as production server evidence. Use an App Store Sandbox account/TestFlight build for transaction-to-backend verification.

Configure the subscription backend:

```text
APPLE_APP_STORE_BUNDLE_ID=com.hikejournal.app
APPLE_APP_STORE_ENVIRONMENT=Sandbox
APPLE_APP_STORE_APP_ID=<numeric App Store Connect Apple ID; required in Production>
APPLE_APP_STORE_ROOT_CA_PATHS=<comma-separated absolute paths to current DER Apple Root CA files>
APPLE_APP_STORE_ONLINE_CHECKS=true
```

Mount current Apple Root CA DER files read-only from server secret storage. Switch `APPLE_APP_STORE_ENVIRONMENT` to `Production` only with the production numeric app ID and online certificate checks enabled.

In App Store Connect, set the App Store Server Notifications V2 production and sandbox URL to:

```text
https://<public-api-host>/v1/app-store/notifications/v2
```

This implementation verifies signed transactions, renewal information, AppTransaction evidence, and Notification V2 payloads; the client finishes a verified transaction only after server reconciliation. It does not currently make outbound App Store Server API history calls, so an App Store Connect issuer ID, key ID, and `.p8` private key are not required by the deployed code. If outbound history reconciliation is added later, those credentials must be server-only secrets.

Sandbox-check monthly and annual purchase, pending/cancel, renewal, canceled-but-active access, billing retry/grace, expiration, refund/revocation, restore on a second device, native Manage Subscription, and a backend-granted Lifetime account that sees no subscription prompt.

## 7. Legacy Google Play Lifetime migration

Do not grant Lifetime from an Android client flag, package name, email, or possession of the paid APK. The backend contains the typed `google_play_legacy` entitlement projection and rejects unverified claims, but a production migration still needs:

- a Google Play service account authorized for the app in Play Console
- the package/purchase evidence that can distinguish a historical paid purchaser
- a reviewed migration window and audit export
- server-side verification that creates an idempotent entitlement event for the canonical HikeJournal `app_users.id`

Until that evidence pipeline is configured and run, affected accounts will not automatically become Lifetime on iOS. Keep the current paid Android experience unchanged and keep global legacy-route quotas observe-only.

## 8. App privacy, legal links, and TestFlight

1. Publish the production privacy and account-deletion pages under `HIKEJOURNAL_WEB_BASE_URL` and verify their links in Settings and the paywall.
2. Review `PrivacyInfo.xcprivacy` against the deployed backend/providers. App Store Connect should account for linked app-functionality data including name/email/user ID/device ID, precise location, fitness hike records, photos/videos, free-form journal content, and purchase history. Tracking is not performed by this implementation.
3. Review the four permission purpose strings with product/legal owners.
4. Complete export-compliance, content-rights, subscription, and privacy questionnaires from the actual distribution configuration.
5. Archive with the distribution team, validate in Organizer, upload to TestFlight, and test the exact uploaded build—not only Debug.
6. Provide App Review with a usable review account or provider instructions, a background-location explanation, the recording/Live Activity path, subscription notes, and access to any server-gated Plus surface needed for review.

## 9. Required physical-iPhone checklist

No item below has been verified by the simulator/unit-test pass. Complete all applicable checks on the oldest supported iOS version and at least one current device:

- [ ] Install the signed TestFlight/release candidate on a physical iPhone.
- [ ] Complete first launch without an immediate permission barrage; repeat with onboarding already completed.
- [ ] Sign in with Google and verify historical Android-created journals, media, observations, and places.
- [ ] Sign in with Apple on a fresh account; sign out/in again after Apple stops returning name/email.
- [ ] Exercise account switching and confirm no cached journal, map, image, job, or entitlement crosses accounts.
- [ ] Verify When In Use explanation/request, then the later Always/background escalation; test denied, restricted, reduced accuracy, and Location Services disabled.
- [ ] Record a short hike outdoors with good GPS and verify accepted-point filtering, distance, elapsed time, and route shape.
- [ ] Lock the screen and walk with the phone locked; reopen and verify continuity without an invented gap.
- [ ] Background/foreground the app repeatedly; test an incoming call/audio interruption if practical.
- [ ] Pause, wait, resume, and verify a new route segment and active-time accounting.
- [ ] Add each field-mark type and a note; verify coordinate/time/accuracy in the final journal and map.
- [ ] Terminate the process normally during a hike and verify safe paused recovery on relaunch.
- [ ] Deliberately force-quit during a test hike, then confirm the next launch reports a recoverable gap rather than claiming uninterrupted tracking.
- [ ] Verify mile voice announcements enabled/disabled, with screen locked and other audio active.
- [ ] Verify the Live Activity in Lock Screen/Dynamic Island, including recording/paused state, distance, elapsed time, deep links, and end cleanup.
- [ ] Finish the hike; verify local TCX generation, queued journal creation, route upload order, and server route rendering.
- [ ] Import a valid and invalid TCX from Files and verify error handling/segment rendering.
- [ ] Select a GPS-tagged phone-original photo through the HikeJournal browser; verify its server/map location matches `PHAsset.location`.
- [ ] Select photos with no GPS, invalid GPS, edited resources, an iCloud-only resource, and a video; verify no location is invented and failures remain actionable.
- [ ] Test full, limited, add-more, denied, and later-revoked Photos permission.
- [ ] Select multiple media, kill/relaunch offline, then reconnect and verify uploads use app-owned staged files.
- [ ] Create/edit/archive/restore/delete a journal offline; reconnect and inspect sync ordering, retry, and quota updates.
- [ ] Exercise the Free 3-journal/50-media UX; verify deletion frees displayed capacity and never deletes data automatically.
- [ ] Render routes, media, field marks, sightings, discoveries, and places on the configured MapLibre style; verify all attribution links and the text alternative.
- [ ] Toggle all 11 National Scenic Trail overlays and verify provider failures do not remove the base map.
- [ ] Download, pause/resume, use offline, inspect storage, and delete an offline pack under the provider's licensed production style.
- [ ] Load a Place Profile, cached/offline profile, 7-day forecast, 7/30-day USGS history, follow/unfollow gauges, Field Briefing, historical weather, and hike comparison.
- [ ] Browse/search/filter/sort the Field Guide; exercise Everyday Sightings, discovery, quest lifecycle, known-species assignment, recommendation batches, decisions, medals, and celebrations.
- [ ] Connect iNaturalist, cancel/expire the browser flow, reconnect, publish individually and in a grouped batch, choose each geoprivacy level, and recover a partial failure.
- [ ] Test local StoreKit product UI, then App Store Sandbox monthly and annual purchases, cancellation/pending, restore, expiry/grace/refund, second-device reconciliation, and native subscription management.
- [ ] Verify a server-granted Lifetime account unlocks Plus surfaces and is never prompted to subscribe.
- [ ] Exercise account deletion with queued local data and an active Apple subscription; confirm the UI explains that subscription management is separate.
- [ ] Test VoiceOver reading/order/action labels, map text alternatives, and non-color status cues.
- [ ] Test the largest accessibility Dynamic Type sizes, Reduce Motion, light/dark appearance, increased contrast, landscape, and text truncation.
- [ ] Measure battery/thermal behavior during a representative multi-hour background hike and document the device/iOS/settings used.

## Known iOS constraints to validate, not “fix” with claims

- iOS controls BGTaskScheduler timing; deferred sync is opportunistic, while foreground/connectivity work is immediate.
- A deliberate force-quit can stop background Core Location delivery. The app persists accepted data and recovers the unfinished session safely, but it cannot reconstruct a route the OS did not deliver.
- Simulator success does not validate real GPS filtering, background/lock continuity, original PhotoKit GPS, speech policy, Live Activity presentation, offline provider licensing, or battery behavior.
