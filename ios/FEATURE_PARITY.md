# HikeJournal iOS feature parity

This ledger is derived from repository code at root version 0.8.6. Android remains the behavioral reference; `mobile_api.py`, Python services, and SQL migrations are the shared data contract. A screen is marked implemented only when its underlying API, local state, and user action are wired.

Status meanings:

- **IMPLEMENTED** — source and behavior are present; credential/device-only verification may still be listed separately.
- **IMPLEMENTED WITH IOS-NATIVE DIFFERENCE** — equivalent product behavior uses an iOS lifecycle or framework that cannot exactly copy Android.
- **PLATFORM-LIMITED** — an inherent platform/store evidence boundary leaves a specifically documented release dependency.

## Verification evidence

| Check | Result |
|---|---|
| Xcode simulator build | Passed with Xcode 26.6 for an iPhone 17 Pro / iOS 26.5 simulator |
| Hosted app XCTest | 66 passed, 0 failed, 0 skipped |
| Local Swift packages | 162 passed: Domain 29, Tracking 28, Persistence 14, Sync 16, Maps 26, Media 22, StoreKit 24, Live Activity 3 |
| Python backend | 511 passed |
| Android regression | `:app:testDebugUnitTest` passed |
| Runtime smoke test | App installed and launched as `com.hikejournal.app`; signed-out branded journal rendered without app faults |
| Not claimed | No physical-iPhone run, production Google/Apple/iNaturalist flow, App Store Sandbox purchase, or licensed offline-map download |

## Application, account, and navigation

| Android capability / source | Shared API or data | iOS implementation | Verification | Status |
|---|---|---|---|---|
| Canonical release version and connection configuration — Gradle, `ConnectionPreferences`, `AppViewModel` | Root `VERSION`, `/health`, `/v1/config`, mobile contract | Root-version build validation; independent build number; Debug/Release xcconfig; validated API/web/style/OAuth configuration | Version/config tests; build passed | IMPLEMENTED |
| Getting Started and contextual permission education — `GettingStartedScreen`, preferences | Local only | Four-step SwiftUI onboarding; location and Photos explanations precede feature-time prompts | Onboarding store/tests and simulator launch | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — completion is first-install/device scoped rather than Android preference storage |
| Google account sign-in — `MainActivity`, `AuthPreferences`, repository | `POST /v1/auth/google`; existing web/server audience | Official GoogleSignIn iOS SDK with separate iOS client and existing server audience; ID token sent to backend | Auth/API tests and backend historical-Google identity tests; configured provider run remains manual | IMPLEMENTED |
| Durable session, refresh, logout, cancellation — `AuthPreferences`, `HikeJournalApi` | Refresh/logout bearer routes | This-device-only Keychain session/device ID; actor-coalesced refresh; one 401 replay; cancellation and safe errors | Hosted auth/API tests | IMPLEMENTED |
| Sign in with Apple — iOS addition required alongside Google | `POST /v1/auth/apple`; Apple JWKS/audience checks | Native button, cryptographic nonce hash, state binding, first-authorization name handling, backend-only token validation | Swift nonce/transition tests; Python Apple claim tests; signed provider run remains manual | IMPLEMENTED |
| Provider-neutral account without orphaning Google owners — ownership helpers | `app_users`, `user_identities`, provider-neutral migration and resolver | Stable canonical user UUID carried through session, cache, entitlement, StoreKit app-account token, and local account scope | Migration/identity/ownership regression tests | IMPLEMENTED |
| Auth, iNaturalist, hike, and active-recording links — manifest and `handleAppIntent` | OAuth start/callback | Strict `hikejournal://` parser plus Google reversed scheme; SwiftUI routing; one-shot recording actions | Deep-link tests; runtime launch; final provider callback manual | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — custom URL and ActivityKit links replace Android intents |
| Account profile, logout, and deletion — settings and `deleteAccount` | `DELETE /v1/account`, storage/database cleanup | Plan/account display, sign-out, destructive confirmation, cloud deletion, account-scoped local cleanup, separate subscription guidance | Hosted state tests and Python deletion/ownership tests | IMPLEMENTED |
| Primary navigation/restoration — top navigation/app state | Local | Native `TabView` and per-feature `NavigationStack`; journal, record, field guide, map, settings; restored deep-link destination | Routing tests and simulator launch | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — native iOS tab/navigation presentation |

## Journal, recording, media, and offline sync

| Android capability / source | Shared API or data | iOS implementation | Verification | Status |
|---|---|---|---|---|
| Journal library, current/archive/all filters, search — `HikeJournalApp`, repository caches | `GET /v1/hikes` | Cached-first searchable/filterable library with cover, loading, empty, offline, and error states | Model/cache tests; simulator render | IMPLEMENTED |
| Create and edit journal — view model, `FieldSync` | `POST /v1/hikes`, `PUT /v1/hikes/{id}` | Native editor, client UUID, optimistic account cache, durable offline operations | Persistence/sync/adapter tests | IMPLEMENTED |
| Archive, restore, permanent delete — repository/overlay tests | Archive/delete routes | Reversible archive; explicit destructive delete; queued offline mutations and reconciliation | Ordering/retry tests; backend cleanup tests | IMPLEMENTED |
| Detail and bounded media pagination — repository/model | Hike header, route, paged photo routes | Detail incrementally merges route, photos, weather, marks, observations, cover, and cached pages | Domain/API/cache tests | IMPLEMENTED |
| Cover selection, caption edit, media delete — journal actions | Cover/caption/photo routes | Photo-only cover selection; caption sheet; confirmed delete; optimistic/durable sync | API and sync tests | IMPLEMENTED |
| TCX import/upload and route rendering — route importer/map | Route upload/parser/storage | Files importer plus native-recording TCX; segmented route rendering; failures remain visible | TCX golden/segment/escaping tests and API adapter tests | IMPLEMENTED |
| Historical weather — longitudinal screens | Weather enrichment route and immutable stored snapshot | Cached snapshot display, explicit refresh, Plus-aware action and attribution | Domain/API/backend weather tests; licensed provider run manual | IMPLEMENTED |
| Hike comparison — longitudinal screens | Comparison route | Select another outing; distance/weather/species/shared-species comparison with cached result | Domain parser/cache tests | IMPLEMENTED |
| Journal sharing — `HikeShareDialog`, map renderer | Local hike/route/media | Exact 1080×1350 branded JPEG; Apple satellite route snapshot/fallback; up to 19 protected photo attachments; native activity sheet | Rendering test verifies 4:5 offline artifact; share-sheet physical smoke remains manual | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — Apple Maps and activity sheet replace Android renderer/share intent |
| Recording prerequisites and permission escalation — tracking prerequisites/service | Local | Contextual When In Use, later Always/background request, accuracy/services/error states | Permission model tests; physical denial/escalation matrix manual | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — Core Location authorization model |
| GPS acceptance/distance — filter/repository tests | Local | Coordinate/accuracy/age/order/drift/speed gates ported; haversine distance | Tracking package edge vectors | IMPLEMENTED |
| Pause/resume, gaps, active elapsed time — state/time logic | Local | Actor state machine; paused checkpoints; new segment on resume/60-second delivery gap; monotonic active time | Tracking transition/clock tests | IMPLEMENTED |
| Durable sessions, points, checkpoints — Room database | Local SQLite | Transactional versioned SQLite records; one active slot; every accepted point and session checkpoint persisted | Persistence migrations/atomicity/recovery tests | IMPLEMENTED |
| Interrupted recording recovery — repository recovery | Local SQLite | Relaunch converts unfinished recording to explicit paused/recoverable state without inventing route data | Recorder/persistence recovery tests; process-lifecycle phone test manual | IMPLEMENTED |
| Background locked-screen recording — foreground service | Core Location background mode | Fitness activity type, background updates only while active, durable checkpoints and user-visible prerequisite state | Source/build/unit tested; physical locked-screen/battery run required | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — force-quit can stop delivery and iOS owns scheduling |
| Persistent recording surface — Android notification actions | Local ActivityKit | Lock Screen/Dynamic Island Live Activity with state, distance, elapsed time, open/pause/resume/end deep links; recording is independent of activity | Live Activity package tests and widget build; physical presentation manual | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — ActivityKit replaces foreground notification |
| Spoken progress — service announcements/settings | Local | Configurable mile announcements through `AVSpeechSynthesizer`; restore-safe next-milestone logic | Tracking announcement tests; locked-screen audio policy manual | IMPLEMENTED |
| TCX generation/finalization — `TcxWriter` | Existing parser/upload | Garmin TrainingCenterDatabase v2, `Sport=Other`, per-segment tracks, UTC, altitude, XML escaping, atomic protected file | 28-test Tracking suite includes TCX fixtures | IMPLEMENTED |
| Field marks — Room/entity/tracking UI | Field-mark route and hike payload | Coordinate/time/accuracy/type/note saved transactionally, displayed in recorder/journal/map, synced after parent hike | Persistence/order/domain/API tests | IMPLEMENTED |
| Phone-original media browser — local media picker/library | Photo upload contract | HikeJournal-owned PhotoKit browser, album/all-media view, photo/video multi-select, limited-library/add-more handling | Media package permission/selection tests; device permission matrix manual | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — PhotoKit is the GPS-safe native source rather than Android MediaStore |
| GPS-safe original retrieval — local picker/EXIF tests | Multipart `taken_at`, `lat`, `lng` | Original `PHAssetResource` export with iCloud progress; validated `PHAsset.location`; original type/name; never guesses coordinates | Located/unlocated/invalid/iCloud/failure tests; real GPS-photo check manual | IMPLEMENTED |
| App-owned durable staging — `FieldSync` local file | Upload route | Protected Application Support copy completes before enqueue; cleanup on failure/account change; no transient PhotoKit URL dependency | Media staging/relaunch/failure tests | IMPLEMENTED |
| Offline mutation queue — Room pending operations | Mutation/upload routes | Versioned SQLite operation ID/kind/entity/parent/payload/file/state/attempt/timestamps/error records | Persistence and coordinator tests | IMPLEMENTED |
| Dependency ordering, idempotency, retry/attention — sync engine | Client IDs and durable server jobs | Deterministic dependency planner; create hike before route/media/marks; bounded backoff; retry/discard; actionable failures | 16-test Sync suite plus persistence/API tests | IMPLEMENTED |
| Deferred/background sync and status — WorkManager/status strip | Shared API | Foreground drain, connectivity trigger, visible status, BG refresh/processing requests, cooperative expiration; no busy loop | Sync/scheduler adapter tests; OS-delivery timing manual | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — BGTaskScheduler timing is opportunistic |

## Maps, places, and outdoor conditions

| Android capability / source | Shared API or data | iOS implementation | Verification | Status |
|---|---|---|---|---|
| MapLibre base/current location/route maps — map screens | Map style config, routes | MapLibre 6.28 UIKit/SwiftUI surface, configured attribution, current location, multi-segment routes, camera fitting, load/error states | 26-test Maps suite; app build; production style render manual | IMPLEMENTED |
| Media/species/mark/sighting/discovery/place annotations — map inspectors | Hike/sightings/discovery payloads | Typed accessible symbols, selection/details, and ordered text alternative for all mapped records | Map geometry/domain/accessibility tests | IMPLEMENTED |
| National Scenic Trail overlays — display preferences/catalog | 11 production ArcGIS sources | Source-for-source 11-trail catalog, pagination/simplification, independent toggles, orange styling, attribution | Catalog parity tests | IMPLEMENTED |
| Offline map packs — offline settings/map | MapLibre offline API | Validated bounded regions, progress/failure, pause/resume, list/storage/delete, Wi-Fi policy, Plus gate | Offline-domain/store tests; licensed provider download/device offline render manual | IMPLEMENTED |
| Saved places/state library — location preferences/guessing | Hike-location routes and canonical catalog | State-scoped cached library, coordinate place creation, selection/tagging | Domain/API/cache tests | IMPLEMENTED |
| Place Profiles and personal/seasonal history — longitudinal screens | Place Profile route | Photo-led profile, metrics, visits, routes, life groups/species, seasonal history, cached/offline state and Plus gate | Domain/cache tests; simulator compile | IMPLEMENTED |
| Current conditions/7-day forecast — outdoor conditions | Shared cached conditions route | Server-routed forecast with freshness, units, daily details, planning note and cached fallback | Backend cache/provider tests and domain parsing | IMPLEMENTED |
| USGS discovery, following, and 7/30-day history — gauge preferences | Shared cached USGS OGC access | Nearby validated 00065 stations, distance/relevance selection, charts, persistent follow/unfollow, Settings management, repeated followed IDs | Backend/parser/cache tests, iOS preference/API tests | IMPLEMENTED |
| Field Briefing — “What should I look for today?” | Field Briefing and sightings routes | Sectioned targets/reasons/progress, detail/sighting map, date/place cache, Plus locked state | Domain/cache/query tests | IMPLEMENTED |

## Field Guide, discovery, review, and publishing

| Android capability / source | Shared API or data | iOS implementation | Verification | Status |
|---|---|---|---|---|
| Field Guide browse/search/filter/sort/detail — species screens | Species list/detail | Lazy searchable guide, observation-type filters, latest/encounter/name sorts, scientific metadata, imagery, encounter history | Domain filter/sort/model tests | IMPLEMENTED |
| Phenology, phenophases, provenance, confidence, identification history — longitudinal/detail UI | Observation natural-history route and history payload | Evidence labels, normalized confidence, history timeline, editable phenophases and reversible state; no local scientific inference | Domain round-trip/normalization/API tests | IMPLEMENTED |
| Everyday Sightings permanent journal — app/sightings map | `everyday` pseudo-journal and sightings route | Permanent sightings workspace/list/map/detail; standalone media semantics; pseudo-journal cannot be deleted | Domain/API/ownership tests | IMPLEMENTED |
| Discovery areas, nearby species and sightings — discovery screens | Areas/nearby/sightings with server cache | Search/select area, radius/date/taxon controls, ranked frequency language, collected/pending state, map sources | Discovery/grouping/model/cache tests | IMPLEMENTED |
| Field Quests and five-species focus — quest screens | Quest CRUD and sightings | Create/rename/link/archive/restore/delete, stable candidate pool, focused targets, progress/detail and sightings map | Quest lifecycle/focus/domain/API tests | IMPLEMENTED |
| Trail medals/badges/celebrations — badge screens/dialog | Actual Android/Python badge definitions | Exact catalog/progress/earned evidence; restrained hike/discovery/rediscovery/batch celebrations; Reduce Motion | Badge/domain/celebration tests and app build | IMPLEMENTED |
| Species review queue and individual recommendations/decisions — review screen | Review routes | Queue with image/provenance/confidence, opt-in recommendation, confirm/choose/reject/remove-from-review, retry/error state | Domain/API tests; Android/iOS review surfaces | IMPLEMENTED |
| Smart review grouping and durable batch jobs — batch work | Review job start/status | Android-derived time/distance/hike grouping, ≤8 photos/group, stable client request ID, foreground polling, cached recovery/progress and completion celebration | Grouping, API body, backend lease/idempotency tests | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — app resumes server job polling instead of Android WorkManager |
| Known-species assignment and review state — journal review controls | Species/review routes | Search/assign known species, preserve observation semantics, revert queue state, rediscovery celebration | Domain/API/store tests | IMPLEMENTED |
| iNaturalist connection — publishing OAuth | OAuth start/callback and encrypted server token | `ASWebAuthenticationSession`, state-bound server callback, app link routing, no provider secret/token in app | Router/API/backend OAuth tests; configured end-to-end flow manual | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — native web authentication session |
| iNaturalist queue, options, single/group publish, status/retry — publishing screen/work | Publish/job routes | Ready/attention/posted queue, geoprivacy, explicit public acknowledgement, related-photo grouping, individual and ≤8-photo batch publish, status/progress/recovery and links | Grouping/API body/backend durable-job tests; live disposable publish manual | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — foreground resumable polling replaces Android worker UI |

## Settings, subscriptions, backend compatibility, and quality

| Android capability / source | Shared API or data | iOS implementation | Verification | Status |
|---|---|---|---|---|
| Settings surface — account/connection/tracking/map/sync/provider/support | Config/auth/entitlement/OAuth/public pages | Account and plan, quota meters, purchase/restore/manage, voice, background location, map/offline storage, trail toggles, gauges, sync retry/attention, iNaturalist, privacy/support/version, deletion | Hosted state tests and simulator build | IMPLEMENTED |
| HikeJournal visual identity, light/dark, Dynamic Type, VoiceOver | Android theme/fonts/product UI | Moss/paper/orange visual system, bundled Cormorant/Source Sans, photo-led moments, native layouts, accessible labels/text map alternative, Reduce Motion | Build/unit tests and simulator smoke; full device accessibility audit manual | IMPLEMENTED WITH IOS-NATIVE DIFFERENCE — native iOS controls and navigation |
| Free/Plus/Lifetime authoritative snapshot | Entitlement service/migration and `/v1/me/entitlement` | Typed account snapshot drives plan, feature locks, quotas, paywall, and Lifetime no-nag behavior | Python free/monthly/annual/lifetime/expired/grace/revoked tests; 24 StoreKit tests | IMPLEMENTED |
| Free quota and Plus server enforcement | Policy/usage/reservation/feature-decision service | Non-destructive 3-hike/50-media meters, client create/media/feature gates, local recording availability, and deletion-refreshed usage | Policy/concurrency/deletion/feature tests and iOS state tests | PLATFORM-LIMITED — hard quotas and Plus gates on existing legacy routes remain intentionally staged until paid Android purchasers have verifiable entitlement evidence; direct legacy API bypass is therefore not claimed |
| Plus paywall and plan presentation | Product IDs and entitlement | Annual-default $49.99/year, monthly $4.99/month, Restore, Terms, Privacy, native Manage Subscription, pending/error states; hidden for Lifetime | StoreKit package/UI build tests; live Sandbox manual | IMPLEMENTED |
| StoreKit 2 load/purchase/listener/restore/status | Transaction-sync route | Verified-only transactions, `appAccountToken`, current entitlements/status, listener, restore, graceful canceled/pending/unverified/error behavior; finish only after server handoff | 24 StoreKit tests; local config present; Sandbox transaction manual | IMPLEMENTED |
| App Store signed transaction and Notifications V2 | Transaction/app-transaction/notification routes | Apple root-chain verification, bundle/environment/product/account checks, durable original-transaction link, idempotent/out-of-order renewal/expiry/retry/refund/revocation projection | Python signed fixture/config/API/replay tests | IMPLEMENTED |
| Legacy Google Play paid purchaser to Lifetime | Verified legacy projection/schema | iOS honors any server-authoritative non-expiring `google_play_legacy` Lifetime and never trusts a client flag | Forged/wrong-package rejection and typed verified-projection tests | PLATFORM-LIMITED — production Google Play evidence/service-account migration is a human-controlled prerequisite and has not been run |
| Privacy, purpose strings, provider attribution, no tracking | Public pages/provider metadata | iOS privacy manifest covers account/device ID, location, fitness, photos/video, journal content, purchase history; MapLibre/Apple/USGS/weather attribution paths; no tracking SDK | Plist/build validation; App Store questionnaire/legal review manual | IMPLEMENTED |
| Backend/Android regression protection | Existing Android API, 59-operation protected manifest | Additive routes/keys/migrations; Google subject compatibility; Android commercial gates unchanged; OpenAPI fingerprint intentionally updated | Python 511 passed; Android debug unit tests passed | IMPLEMENTED |

## Platform and release boundaries

- Core Location background delivery is appropriate for active recording, but a deliberate user force-quit can stop delivery. HikeJournal preserves all accepted data and recovers the session paused; it never fabricates the missing path.
- iOS determines BGTaskScheduler timing. Immediate foreground and connectivity-triggered sync remain the primary path; deferred work is opportunistic.
- PhotoKit original-resource and `PHAsset.location` behavior is source- and unit-tested, but the GPS integrity guarantee still requires the physical-photo matrix in `MANUAL_SETUP.md`.
- MapLibre's tile/style license, App Store products, Apple/Google/iNaturalist credentials, and production weather contract belong to the operator. The app rejects absent production configuration rather than embedding secrets.
- The only incomplete commercial migration is intentionally explicit: existing paid Android customers cannot safely be assigned Lifetime or subjected to Free server gates until Google Play supplies verifiable historical purchase evidence. Current Android behavior is unchanged.
