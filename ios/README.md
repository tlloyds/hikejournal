# HikeJournal for iOS

HikeJournal is a native SwiftUI iPhone application for the same HikeJournal account and mobile API used by Android. It targets iOS 17+, uses the canonical version in the repository root `VERSION`, and builds as `com.hikejournal.app` with the ActivityKit widget extension `com.hikejournal.app.widgets`.

The checked-in project is a functioning application, not a UI scaffold. It includes provider-neutral sign-in, server-authoritative Free/Plus/Lifetime state, StoreKit 2, durable SQLite tracking and sync, PhotoKit original-media ingestion, MapLibre maps and offline packs, the journal and field-guide workflows, Place Profiles and planning conditions, iNaturalist review/publishing, and an active-hike Live Activity.

## Requirements

- macOS with full Xcode; the current verification used Xcode 26.6
- iOS 17 or later
- an iPhone Simulator for local UI/build testing
- a configured HikeJournal API for signed-in, cloud, provider, and subscription end-to-end tests
- a physical iPhone for background GPS, locked-screen, PhotoKit GPS-integrity, voice, Live Activity, and battery validation

No beta-only API is required. The project pins GoogleSignIn-iOS 9.2.0 and MapLibre 6.28.0 through Swift Package Manager.

## Open, build, and test

Open `HikeJournal.xcodeproj`, select the shared `HikeJournal` scheme, and choose an iPhone simulator. The scheme already references `HikeJournal/Resources/HikeJournal.storekit` for local product presentation.

From the repository root:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer ./ios/build_and_test.command
```

The helper checks that the root version and iOS build configuration agree, builds the app, and runs the hosted XCTest suite. Its optional settings are:

- `DEVELOPER_DIR`: alternate full Xcode developer directory
- `HIKEJOURNAL_DERIVED_DATA_PATH`: alternate DerivedData directory
- `HIKEJOURNAL_DESTINATION`: alternate xcodebuild destination

An explicit simulator build is:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  xcodebuild \
  -project ios/HikeJournal.xcodeproj \
  -scheme HikeJournal \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  build
```

Replace `build` with `test` for the hosted XCTest suite. Each package can also be tested independently, for example:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  swift test --package-path ios/Packages/HikeJournalTracking
```

## Architecture

`HikeJournal/App` is the composition root. It creates account-scoped stores and owns lifecycle work such as interrupted-recording recovery, connectivity-driven sync, background-task registration, and URL routing.

The app target is divided into focused UI and integration modules:

- `Core/API` and `Modules/Journal/HikeJournalFeatureAPI.swift`: typed JSON, multipart requests, pagination, authentication, refresh, cancellation, safe errors, and the complete feature API
- `Core/Authentication`: Keychain sessions/device identity, GoogleSignIn, Sign in with Apple nonce/state handling, logout, and account deletion
- `Modules/Tracking`: Core Location, background updates, durable recorder orchestration, field marks, voice announcements, TCX finalization, and Live Activity updates
- `Modules/Media`: PhotoKit library browsing, limited-library handling, original-resource export, GPS validation, durable staging, and upload queue integration
- `Modules/Persistence` and `Modules/Sync`: account-isolated SQLite storage, mutation dependency planning, retry/attention state, foreground/network-triggered work, and BGTaskScheduler work
- `Modules/Maps`: MapLibre SwiftUI surface, routes and annotations, textual map alternatives, 11 National Scenic Trail overlays, and offline-region management
- `Modules/Journal`: journal library/detail/editor, media and natural-history editing, sharing, Places, forecasts/USGS, Field Briefings, comparisons, Field Guide, sightings, discovery, quests, review, publishing, medals, and celebrations
- `Modules/StoreKit`: the Plus paywall, App Store product/purchase/restore management, and reconciliation with the HikeJournal backend
- `DesignSystem`: the adaptive moss, paper, and trail palette; Cormorant Garamond and Source Sans 3; accessible motion and typography

Reusable logic is isolated in eight local Swift packages:

- `HikeJournalDomain`: resilient server models, filtering/grouping, quests, badges, and celebrations
- `HikeJournalTracking`: GPS acceptance, distance/segments/time, announcements, and TCX
- `HikeJournalPersistence`: versioned SQLite schema and durable operation/tracking records
- `HikeJournalSync`: dependency-aware sync execution and retry rules
- `HikeJournalMedia`: PhotoKit policy, GPS-safe ingestion, and protected staging
- `HikeJournalMaps`: MapLibre geometry, accessibility, trail catalog, and offline packs
- `HikeJournalStoreKit`: verified StoreKit 2 transactions and server-authoritative reconciliation
- `HikeJournalLiveActivity`: shared ActivityKit state, controller, and widget UI

## Product surface

- Four-step contextual onboarding; permissions are requested only when their feature is used
- Google and Apple account access to a provider-neutral HikeJournal identity
- Cached journal list/detail, create/edit/archive/delete, covers, captions, media deletion, TCX import, weather, comparison, natural-history history, and a 4:5 satellite-route share keepsake
- GPS recording with Android-derived fix filtering, pause/resume segments, persistent points/checkpoints, recovery, field marks, voice milestones, local TCX, sync ordering, and Live Activity
- Photo/video multi-selection through a HikeJournal PhotoKit browser; original resources and valid `PHAsset.location` are copied to protected app storage before enqueue
- MapLibre route/media/mark/sighting/place maps, current position, accessible text alternatives, scenic-trail overlays, and Plus-gated offline packs
- Saved places, photo-led Place Profiles, cached 7-day forecast, followed USGS gauges with 7/30-day history, seasonal/personal history, and Field Briefings
- Field Guide browsing/detail, Everyday Sightings, discovery areas, nearby species/sightings, five-species Field Quests, review recommendation batches, known-species assignment, grouped iNaturalist publishing, medals, and celebrations
- Free usage meters, annual-default Plus offer, verified purchase/restore/listener behavior, native subscription management, and automatic Lifetime recognition from the backend

See `FEATURE_PARITY.md` for the source-by-source Android comparison and honest platform/verification limits.

## Versioning

The plain-text root `VERSION` is canonical. `Config/Version.xcconfig` supplies `MARKETING_VERSION`, and the app build runs `Scripts/validate_version.sh`. A mismatch fails the build.

After an intentional root version change:

```sh
./ios/Scripts/sync_version.sh
```

`CURRENT_PROJECT_VERSION` is the independent iOS build number and must be incremented for each App Store Connect upload.

## Local configuration

Debug defaults to `http://127.0.0.1:8506` and the public MapLibre demo style. Release intentionally has no usable API endpoint until configured. Copy the ignored local configuration:

```sh
cp ios/Config/Secrets.example.xcconfig ios/Config/Secrets.xcconfig
```

Configure only public client values:

- `HIKEJOURNAL_API_BASE_URL` and `HIKEJOURNAL_WEB_BASE_URL`
- `HIKEJOURNAL_MAP_STYLE_URL`, attribution title/URL, optional public style token, and its query-item name
- `GOOGLE_IOS_CLIENT_ID`, the existing `GOOGLE_SERVER_CLIENT_ID`, and `GOOGLE_REVERSED_CLIENT_ID`
- optional legacy pairing `HIKEJOURNAL_API_KEY` only when that deployment still uses it

Production API, web, style, and attribution URLs must be HTTPS. `AppConfiguration` rejects URL credentials, query strings, fragments, placeholder provider values, and unsafe token query names. A style token embedded in a shipped app is public configuration, not a secret; use a provider-scoped/restricted token.

Never place refresh tokens, Apple private keys, App Store server credentials, Google client secrets, Supabase service-role keys, storage credentials, or iNaturalist secrets in an xcconfig or app resource. These belong on the server. Exact provider and production steps are in `MANUAL_SETUP.md`.

## Permissions, callbacks, and privacy

The app declares When In Use and Always/background location descriptions, original Photo Library access, Photo Library add access for exports, background location/fetch/processing modes, permitted sync task identifiers, Live Activities, and Sign in with Apple.

Registered URL schemes are:

- `hikejournal://` for iNaturalist and recording routes
- the configured Google reversed client ID for GoogleSignIn

`PrivacyInfo.xcprivacy` declares UserDefaults access and the linked app-functionality data the implementation can send or retain: account details, app/device identity, precise route/media location, hike fitness records, photos/videos, field-note content, and purchase history. Tracking is false. App Store Connect answers still require a human review against the deployed backend and provider configuration.

## Verification boundary

At version 0.8.6, the local automated evidence includes a successful simulator build, 66 passing hosted Xcode tests, 162 passing package tests, 511 passing Python tests, and the Android debug unit suite. The app was installed and launched successfully on an iPhone 17 Pro simulator.

Those results do not prove a production provider login, App Store Sandbox purchase, iNaturalist publication, licensed offline-map download, or physical-device background route. None of those credential/device-dependent checks has been claimed. Follow `MANUAL_SETUP.md` before TestFlight or App Store submission.
