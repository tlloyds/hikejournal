# HikeJournal Android and iOS release audit

**Assessed:** October 12, 2026, America/New_York. **Repository:** `main`, `41e0107`.
**Purpose:** inventory current Android behavior, identify iOS parity gaps and remaining Android work, and support a paid Plus launch on both stores during October 12–18.

The product has substantial depth on both platforms. iOS needs several concrete ports and reliability fixes; the larger launch dependency is completing the commercial system across Android, iOS, and the shared API. A successful build does not establish store readiness or physical-device behavior.

The executable work order is in [the store launch plan](roadmaps/IOS_ANDROID_STORE_LAUNCH_PLAN.md).

## 1. Baseline and evidence boundaries

| Surface | Current baseline | What is established |
| --- | --- | --- |
| Android | `versionName` **0.8.46**, `versionCode` **180**, minimum API 26, target/compile API 36 | GitHub's Latest release is `android-v0.8.46-map-refresh`, published October 7. Existing APK and AAB hashes match its release evidence. The existing APK passed the release verifier again during this audit, including signer, native alignment, and artifact checks. |
| iOS | Marketing version **0.8.46**, build **18**, minimum iOS 17 | Last functional app-source change was September 15 tracking parity (`b9cb3cf`). Subsequent marketing-version synchronization did not port Android changes. A fresh unsigned generic-device Release build passed during this audit. |
| API | Production `/health` reports **0.8.46** | Latest map-summary/viewport and narrower library/species/location reads are present. Health, privacy, support, and deletion pages responded during this audit. |
| Store setup | Corporate Apple and Google developer accounts; user confirms Play production access | HikeJournal app/product setup is unfinished. The new-personal-account closed-testing prerequisite is outside this launch's scope. Store product creation, agreements, listing, declarations, and review remain necessary. |
| Commercial scope | Paid Plus at launch on **both** platforms, with complimentary access | Confirmed by the user in this chat. Android subscriptions and shared enforcement must therefore be launch work. |

The audit inspected app source, shared services, SQL, tests, release notes/evidence, roadmaps, Git history, and ten relevant recent HikeJournal chats. The accessible `/Users/adl/.codex/memories` directory was empty; no separate persistent memory was available to corroborate. This is not a claim that every historical ChatGPT conversation was accessible.

The original [iOS parity ledger](../ios/FEATURE_PARITY.md) is a historical source inventory rooted at 0.8.6. Its statements about incremental detail rendering, durable review decisions, stable batch request IDs, and complete commercial migration need the corrections below.

### Fresh validation performed

| Check | Result and implication |
| --- | --- |
| Existing Android 0.8.46/build-180 APK verifier | **PASS**, no findings; expected permanent signer `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`. No Android build was made. |
| Existing APK/AAB SHA-256 | APK `89a0f7d2d522c856b22b50af6a8afc16c5ece5abbbd94d12a772b2dd57012af7`; AAB `f75cc7e644dc3cab6c748d58607df8041cc712cacfb13c28d76bc0a081515aea`. Both match build-180 evidence; GitHub's APK digest matches too. |
| iOS unsigned Release device build | **PASS**, Xcode 26.6, generic iOS device. This was a build, not a signed archive, upload, or device run. |
| Standard iOS Debug build/test helper | **BLOCKED at build packaging**: embedded XCTest support frameworks lack Info.plist files. Hosted tests did not run. The same condition appears in earlier release notes. It should be made reproducible and repaired, not waived indefinitely as environment noise. |
| Swift Domain | **32 passed, 1 failed out of 33**. `testBatchCelebrationUsesPhotosForPossibleNewSpecies` receives an empty image array. |
| Swift Tracking | **29 passed**. |
| Swift Persistence / Sync / Media / StoreKit | **15 / 16 / 22 / 24 passed**. |
| Swift Maps | **Test target fails to compile**: missing closing collection bracket in `MapRouteOverlapTests.swift:65`. This is a test-source error; the app Release build still succeeds. |
| Swift Live Activity on macOS | **0 tests executed**. This is not validation of ActivityKit on iPhone. |
| Targeted backend | **208 passed**, one dependency deprecation warning. Covered entitlements, App Store verification/API, mobile auth/API, and repository behavior. |
| Historical latest Android release | Build-180 evidence records **180 tests in each Debug/Release variant**, release lint, strict AAB signature verification, and emulator upgrade from 179. These were not rerun in this audit. |
| Release configuration inspection | Built iOS Info.plist has production HTTPS API/web URLs, OpenFreeMap style/attribution, and non-placeholder Google client configuration. No pairing credential is embedded. Provider login and licensed offline behavior remain unverified. |

Local diagnostic logs are `/tmp/hikejournal-*-parity-audit.log`. No versions were changed, mobile release artifacts distributed, production data modified, or store submissions made by this audit.

## 2. Complete Android product inventory and iOS comparison

**Present** means source and wiring were found; it does not imply every journey was exercised on a phone. **Partial** and **Missing** identify current differences. **Native equivalent** identifies an intentional OS-specific implementation.

### Account, navigation, and journal

| Android capability | iOS assessment | Release implication |
| --- | --- | --- |
| Google sign-in against the hosted API; rotating sessions, refresh, logout, auth rejection handling | Present; actor-coalesced refresh and Keychain storage | Verify historical Google journal ownership on both actual store builds. |
| Four-step Getting Started / contextual location and media explanations | Native equivalent | Check first install, repeat launch, denied permissions, and useful signed-out state. |
| Journal/Library, Species, Record, Map, Settings navigation and contextual return | Native equivalent: TabView/NavigationStack | Verify iNaturalist and recording links preserve the originating context. |
| Account settings, public privacy/support/deletion links, in-app account deletion | Present; Apple sign-in is additionally supported | Apple credential revocation and policy updates remain launch gaps. |
| Searchable Library with current/archive/everyday scope | Present | Large libraries need runtime coverage; no blanket claim that all list paging is solved. |
| Most recent formal outing first, Everyday Sightings next | Present since 0.8.36 | Preserve this ordering. |
| Create/edit outing, date/location/notes, optimistic local drafts | Present | Preserve local work if a cloud quota is reached. |
| Archive, restore, permanent delete with confirmation | Present | Exercise offline operations and failed storage deletion. |
| Permanent Everyday Sightings workspace | Present | Keep standalone media ownership and deletion semantics distinct. |
| Journal cover, captions, species labels, media metadata | Present | Existing label/caption/weather fixes should remain regression fixtures. |
| Incremental journal photos while route/header load | **Partial**: requests are paged, but iOS fetches all pages before assigning the detail | Port progressive rendering; current behavior can recreate a long blank-detail wait. |
| TCX import and recorded-route upload | Present | Verify invalid files, segments, persisted routes, and web visibility. |
| Journal satellite route preview with offline sketch fallback | Present; Android adopted the earlier iOS pattern in 0.8.33 | No port required. |
| Branded 1080×1350 hike keepsake with selected photos and route | Native equivalent: Apple Maps snapshot and activity sheet | Verify sharing on device; this does not replace single-photo sharing. |
| Share one photo from gallery/journal/map through native share menu | **Missing** | Previously requested iOS port; add an actual image attachment, note, progress, and retry. |
| Animated route replay for native and imported tracks | **Missing** | Port the whole playback behavior, not only an animated line. |

### Recording, media, and local reliability

| Android capability | iOS assessment | Release implication |
| --- | --- | --- |
| Offline Start/Pause/Resume/End, active time and distance | Present | Real GPS and a representative long hike are required. |
| Pause confirmation from screen and notification | Present from screen and Live Activity link since 0.8.42 | Keep both paths consistent. |
| GPS filtering for age, accuracy, ordering, drift, speed; segmented gaps | Present | Check implausible fixes and paused-time exclusion. |
| Room sessions/points/checkpoints and interrupted paused recovery | Native equivalent: transactional SQLite and recorder actor | Verify relaunch and finalization under real process interruption. |
| Foreground location service and notification controls | Native equivalent: Core Location background delivery and Live Activity | Force-quit limitations are inherent; preserve collected points and report interrupted recording honestly. |
| Spoken mile progress, pause/resume, total active time and last-mile time | Present since 0.8.42 | Verify lock-screen audio, interruptions, and Bluetooth. |
| Field Marks: wildlife, plant, trail, water, campsite, hazard, note | Present | Verify coordinate/time/accuracy and parent-before-mark sync. |
| Durable TCX generation and parent hike before route/media upload | Present | Keep end-of-hike recovery independent of networking. |
| GPS-safe in-app phone-original browser, albums, multi-select | Native equivalent: PhotoKit originals and PHAsset location | Preserve Android LocalMediaPickerDialog/LocalMediaLibrary. Submit its declaration; do not replace it with a cloud-only picker. |
| Full/selected media access and limited-library recovery | Native equivalent | Test full/limited/denied/revoked/iCloud-only resources on actual devices. |
| Original photo/video GPS and date validation; missing-GPS warning | Present | Never invent coordinates or silently discard original metadata. |
| App-owned staged copies before background uploads | Present | Kill/relaunch offline and confirm staged files survive. |
| Photo viewing/swiping, video playback, caption edit, delete, cover selection | Present | Test private URL expiration and movie derivatives. |
| Edit known species, manual common/scientific names, remove primary ID | Present since 0.8.35 | Changes should remain durable offline. |
| Durable create/edit/archive/caption/delete/upload queue, retry/attention | Native equivalent: SQLite, foreground/connectivity drain, BGTaskScheduler | OS scheduling differs; do not promise Android-style continuous background execution. |
| Durable individual review decisions and multi-selection persistence | **Partial**: review membership/species tags are queued, but Review confirm/reject calls the API directly | Wire the existing `reviewDecision` operation through the UI/store before launch. |

### Maps, places, and conditions

| Android capability | iOS assessment | Release implication |
| --- | --- | --- |
| MapLibre map, current location, route segments/start/end, photos, marks, selection | Present | Test photo taps, journal handoff, and textual alternatives. |
| Main map covers all owner-visible geotagged photos with summary + viewport requests | **Missing**: iOS still reads `/v1/sightings` | Port `/v1/map/summary` and `/v1/map/viewport`, clustering and camera callbacks. |
| Debounced camera updates, stale-request cancellation, overview clusters and cluster zoom | **Missing** | Bounds must follow settled camera changes; show more than the old row-cap snapshot. |
| Late-arriving summary bounds can override the initial cached fit | **Missing** | Apply the Android build-180 ordering fix during the port. |
| Independent Photos/Routes display controls | Present since 0.8.39 | Preserve both controls. |
| Trail/satellite choice and confirmed-species filtering | **Partial**: iOS adds a hardcoded Esri satellite layer; comparable workspace selectors were not found | Add equivalent controls or explicitly document a launch difference. Review imagery/offline rights separately from OpenFreeMap. |
| All 11 National Scenic Trail overlays | Present | Check representative provider failures and attribution. |
| Stricter scenic-trail overlap highlighting | Present since 0.8.39 | Repair the broken Maps test fixture. This is overlay highlighting, not place-to-place geospatial overlap scoring. |
| Offline trail packs, storage/progress/delete; licensed satellite packs when configured | Native equivalent; iOS Plus gate | Actual licensed-provider downloads/offline render remain a device and provider gate. |
| Nationwide state-scoped place catalog and user-created coordinates | Present; iOS state selection defaults to FL | Android has current-state discovery/preferences; assess equivalent initial selection as lower-priority polish. |
| Place Profiles with visits, covers, mileage, species/life groups, seasonal history | Present | Keep account-scoped caching and verify Plus access. |
| Satellite route maps containing all saved routes at a place | Present since 0.8.41 | Test multiple routes and no-route fallback. |
| Current conditions, seven-day forecast, local update time/attribution | Present | Commercial Open-Meteo configuration is a shared launch dependency. |
| Nearby USGS gauges, follow/unfollow, 7/30-day history and relevance | Present | Verify station selection/settings and provider errors. |
| Field Briefing: expected finds, reason/evidence, photos, sightings maps | Present | Verify current-location and saved-place entry and cached/offline response. |
| Historical route-interval weather and retry/refresh | Present | Shared server improvements already benefit both platforms. |
| Hike Comparison and shared/unique species | Present | Compare client and server Plus gates and selected-hike requests. |

### Field Guide, review, publishing, and progress

| Android capability | iOS assessment | Release implication |
| --- | --- | --- |
| Search common name, scientific name, stored Wikipedia description | Present since 0.8.34 | SwiftUI already owns one search state; Android's Compose-specific stale-state fix is not a literal port. |
| Observation-type filters, including aggregate Animals and outing scope | **Partial**: iOS offers available iconic taxa; no equivalent outing filter was found | Bring collection filter behavior into parity and test combinations. |
| Common-name and scientific-name A–Z sorts plus recent/encounter sorts | **Partial**: iOS has one common-name sort; its view also sorts recent dates as strings | Add scientific-name sort and use the tested date/tie-break helpers. |
| Tap/drag quick-jump rail for ≥30 visible species | **Missing** | Add an accessible iOS equivalent for large collections. |
| Species detail imagery, encounters, journal/map/reference links | Present | Exercise large histories and private-photo loading. |
| Personal 12-month seasonality, confidence, provenance, phenophases, ID history | Present; some Plus presentation exists | Confirm the advertised Plus features are enforced consistently. |
| Regional Native/Non-native/Invasive/Unknown labels and legibility | Present since 0.8.38/0.8.40 | Keep ecological status separate from confidence; USDA fallback is region-specific. |
| Discovery by saved/current area, date, radius, taxa; sightings maps | Present | Verify failed-location cancellation and request limits. |
| Field Quest create/focus/rename/link/archive/restore/delete/progress | Present; explicit targets and current-location quest fixes shipped in iOS 0.8.30/31 | Preserve the actual configured target limits; avoid confusing nearby frequency with probability. |
| Photo-first Review, candidates/confidence, confirm/reject/skip/remove | Present, but decisions have durability gap above | Reject keeps the photo queued for another suggestion. |
| Smart same-encounter grouping, split groups, server recommendation jobs | Present, with iOS foreground polling | Verify grouped/individual results, restart recovery and expiration. |
| Durable stable batch submission identity | **Partial**: iOS generates a UUID for each start and persists only after the initial response | Persist the request ID/payload before submission and reuse it after a dropped response. |
| Review automatically recovers after connectivity returns | **Partial**: iOS's network callback drains sync, without an equivalent visible Review refresh hook | Add screen-aware refresh/resume; do not introduce Android's previous sticky-offline guard. |
| iNaturalist connect while field sync is running | iOS avoids the Android sync-connected guard, but lacks a clearly observed URL-request progress state | Verify and add local progress/error visibility; preserve context on callback. |
| Publish confirmed observations, grouping, notes/tags/geoprivacy/cultivated choice and explicit confirmation | Present | Test individual and grouped publication with disposable staging observations. |
| Publish queue filters and high-throughput bulk ergonomics | **Partial**: iOS has search and batch controls; no matching outing/stage selector was found in its workspace | Finish the most useful filtering; keep bulk selection and error handling predictable. |
| Background/resumable publishing with partial failures and observation links | Native equivalent, with batch-start persistence gap above | Test dropped responses and ambiguous external creates; exactly-once is not proven by local job IDs. |
| Trail Medals: hike/miles/long outing/quests/rare finds/species/taxon specialties | Present | Derived from journal data; archived hikes count toward lifetime progress. |
| Discovery/rediscovery/milestone/batch celebrations and reduced motion | Present, **batch image bug reproduced** | Fix before calling the iOS visual polish complete. |

Primary implementation sources: [Android UI](../android/app/src/main/java/com/hikejournal/app/ui/), [Android repository](../android/app/src/main/java/com/hikejournal/app/data/HikeJournalRepository.kt), [iOS journal store](../ios/HikeJournal/Modules/Journal/JournalStore.swift), [iOS journal views](../ios/HikeJournal/Modules/Journal/JournalViews.swift), [iOS Field Guide](../ios/HikeJournal/Modules/Journal/FieldGuideViews.swift), [iOS maps](../ios/HikeJournal/Modules/Maps/JournalMapViews.swift), and [shared API](../mobile_api.py).

## 3. Recent feature and bug-fix ledger

This ledger covers the current mobile change sequence, including fixes important to earlier iOS stability. The Android inventory above also includes older functionality retained in 0.8.46.

| Release/change | Result now in Android | iOS treatment |
| --- | --- | --- |
| 0.8.0–0.8.3 | Hosted Google accounts, private expiring media links, privacy/support/deletion pages, safe signing lineage, nationwide places | Shared API applies; native auth/local implementation still needs store-build validation. |
| 0.8.7–0.8.31 iOS stabilization | Android remains the behavior reference | iOS already received API snake-case decoding; auth/Keychain/Google entry fixes; imagery/map/trail-toggle fixes; scrolling; captions/species labels; journal creation; recorded-route point race/persistence; photo paging/swiping; reject/remove behavior; location cancellation; quest target/current-area and place-loading fixes. Do not undo them during parity work. |
| 0.8.32 | Transport failures preserve auth; actual rejection signs out; cache does not disguise auth failures as offline; review/publish freshness separated; paused auth operations requeued selectively | iOS auth actor already addresses much of this, but review reconnect/durability needs verification. |
| 0.8.33 | Journal route preview with offline fallback and route accessibility | Already present in iOS. |
| 0.8.34 and photo-picker follow-ups | Wikipedia-description search; restored GPS-bearing original-browser path after cloud-picker regression | Description search and PhotoKit original retrieval present. Never repeat the Android picker regression. |
| 0.8.35 | Known/manual species edit and primary-ID removal, durable offline | Ported to iOS. |
| 0.8.36 | Latest hike, then Everyday Sightings ordering | Ported to iOS. |
| 0.8.38/40 | Regional ecology data, USDA Florida fallback, retry unknown snapshots, stronger labels/counts | Shared data and native presentation ported. |
| 0.8.39 | Photos/Routes toggles and stricter scenic-trail geometry/direction matching | Ported; iOS Maps test fixture is broken. |
| Android 0.8.40/build 164 | Serial refresh-token rotation across UI/workers; singleTask OAuth return preserves context | iOS actor refresh is equivalent; browser return still needs real-device regression. |
| 0.8.41 | Place-scoped multi-route maps, offline sketch | Ported to iOS. |
| 0.8.42 | Pause confirmation; spoken pause/resume, total time and last-mile time | Last functional iOS change, build 18. |
| 0.8.43/build 167 | Immediate Field Guide search/filter/sort updates; transactionally persist multi-review choices before worker starts | SwiftUI search does not share Compose's state ownership bug. iOS multi-decision durability remains incomplete. |
| 0.8.43/build 168 | Species disk cache rendered first; network outside global cache lock; background JSON parsing; lazy Nearby/Quests; safe timings; scoped API reads | Shared backend applies. iOS has cache-first list/species behavior, but MainActor parsing, redundant sightings reads, eager hike pagination, and refresh policies remain. |
| 0.8.43/build 169 | Single-photo native sharing | iOS port explicitly requested in the “Add Android photo sharing” chat; still missing. |
| 0.8.43/builds 170–172 | Local fast replay, play/pause/restart/scrub, safe route framing, 0.5×/1×/2× | Missing on iOS. A later source check confirmed Android scales its remaining duration correctly; no Android timing defect is recorded. |
| 0.8.44/build 173 | Replay elapsed/total miles and numbered mile markers that activate as playback advances | Missing on iOS. These are replay markers; live-recording markers were not part of that release. |
| 0.8.44/build 174 | Validated-network reconnect refreshes Review so decisions resume | iOS needs equivalent refresh/resume, without assuming NWPath status proves API reachability. |
| 0.8.44/build 175 | iNaturalist OAuth no longer blocked by sync connectivity; visible connecting/error UI | iOS lacks that blocking guard; progress/context regression still needed. |
| 0.8.45/build 176 | 30-second hike and one-minute species reuse; compact summaries; bounded Everyday paging; narrow projections | Shared SQL/API already applies. iOS request/cache/rendering behavior needs alignment. |
| API 0.8.45 map/location releases | Scope photo/route reads to visible data; omit duplicate geometry; resolve tags/places by requested IDs/state; remove invalid species column | Benefits both clients automatically. No literal client port required. |
| 0.8.45/build 177 | Separate scientific-name/common-name sorts | Missing scientific sort on iOS. |
| 0.8.45/build 178 | Large-collection quick-jump rail | Missing on iOS. |
| 0.8.46/build 179 | All-photo summary + bounded viewport/clusters, direct SQL ownership without hike/photo row-cap truncation | Missing on iOS. |
| 0.8.46/build 180 | Set loading before cache hydration; apply late summary bounds even after earlier fit | Missing on iOS. Dominant-region framing remains a separate unfinished requirement. |

Release-specific validation is in [release notes](release-notes/) and [release evidence](release-evidence/). In particular, some photo-sharing/name-sort releases did not run unit tests; a subsequent full suite is useful evidence, not proof of every interactive flow.

## 4. Confirmed defects and implementation gaps

P0 blocks the requested paid public launch. P1 is required for reliable final polish/parity. P2 can follow launch when disclosed accurately.

| ID | Priority/platform | Finding and evidence | Required outcome |
| --- | --- | --- | --- |
| COM-01 | P0 Android/API | No BillingClient dependency, purchase/restore UI, subscription verification route, or RTDN handler was found. `google_play_subscription` is a data-source enum, not an integration. | Native Play purchase lifecycle, verified backend projection, restore/manage, account binding and RTDN. |
| COM-02 | P0 shared | `EXISTING_MOBILE_ENTITLEMENT_ENFORCEMENT_ENABLED = False` at `mobile_api.py:161`; the helpers are not wired into existing mutations/features. Android does not consume the entitlement snapshot. iOS client gates vary and permit some unknown-entitlement states. | Consistent Free/Plus/admin access with server feature decisions and atomic cloud-quota reservation/write/release. Preserve saved/offline work and authorized complimentary accounts. |
| COM-03 | P0 stores/iOS | Store products are not configured. Apple code and 24 package tests exist, but no real Sandbox/TestFlight end-to-end purchase evidence was found. | Configure both stores and server notification credentials; prove purchases, renewal, canceled-active, grace, expiry, refund, restore, and cross-device/account behavior. |
| ACC-01 | P0 iOS/API | Apple payload carries identity token/nonce/name, without authorization code. No Apple token exchange/revocation flow was found in account deletion. | Implement the Apple authorization-code/token lifecycle and revoke on deletion; secure retry for failures and clear old-account state. [Apple's account-deletion guidance](https://developer.apple.com/documentation/technotes/tn3194-handling-account-deletions-and-revoking-tokens-for-sign-in-with-apple). |
| ACC-02 | P0 shared/Web | Live privacy page mentions Google, omits Apple and purchases; public deletion page accepts Google only. Support is a public GitHub issue tracker. | Update data/provider/retention/purchase disclosures and contact path; support Apple-only deletion requests as well as in-app deletion; verify actual shipped links. |
| MAP-01 | P1 iOS | `JournalStore.refreshMap` at line 268 calls `api.sightings()`; feature API at line 346 uses the old route; no map summary/viewport client was found. | Port viewport contracts/camera lifecycle, bounded cache and clusters; cover >100 photos and >100 hikes. |
| MAP-02 | P1 Android/API, then iOS | `mobile_map_summary` still unions all photos and route geometries in its extent. Build 180 fixes timing, not a robust dominant-photo-region camera. | Satisfy the recent Orlando/bulk-of-photos request with a deterministic useful initial region, while retaining an explicit fit-all action. |
| REP-01 | P1 iOS | No replay UI/domain implementation found. Android `RoutePlaybackDialog.kt:72–79` computes both remaining duration and progress delta from the remaining fraction; source review confirms the 50%-at-1× timing is 12 seconds as intended. | Port Android's clock behavior and controls to iOS, preserving distance-weighted segments and accessibility. |
| REP-02 | P1 iOS | No replay UI/domain implementation found. | All controls, distance-weighted segmented path, speeds, markers, framing and accessibility, with entirely local playback. |
| MED-01 | P1 iOS | Viewer actions at `JournalViews.swift:1507` have edit/cover/delete but no single-photo share. | Protected attachment staging and native activity sheet from every photo entry point. |
| PERF-01 | P1 iOS | `loadHike` at line 157 calls `allPhotos`; line 1547 loops through up to 10,000 photos before the detail is assigned. | Render header and first page promptly, then append pages; update route independently; retain explicit refresh and accurate paging. |
| PERF-02 | P1 iOS | `refreshFieldGuide` fetches species then sightings even in Collection; refresh does not honor index freshness; JSON encode/decode helpers are MainActor methods. Species detail can remain fresh for 24 hours. | Separate screen data needs, offload large parsing, use bounded freshness/invalidation, and retain stale readable data without mislabeling every error offline. |
| REV-01 | P1 iOS | `decideReview` at line 796 calls the API directly; `.reviewDecision` exists in Persistence and the sync adapter but was not found in the store enqueue path. | Save decisions transactionally before returning success; immediate overlays, retries, app restart and multi-select safety. |
| REV-02 | P1 iOS | Batch starts at lines 555/623 generate a new request UUID; persistence follows the server response. | Save submission request/payload first; retry the same operation after response loss; resume one job after reconnect. |
| REV-03 | P1 iOS | Connectivity callback drives sync; visible Review/Publish refresh and polling resumption do not have Android-equivalent reconnect wiring. | Offline/online recovery while the user stays on the screen; visible request progress and errors. |
| SPEC-01 | P1 iOS | Local FieldGuideViews sort enum has latest/encounters/name only; view uses string date ordering. No quick-jump rail or outing-scope selector was found. | Scientific/common sorts, parsed-date ordering, combined filters, accessible quick navigation. |
| QA-01 | P1 iOS | Celebration image test fails; the image builder uses a stateful Set insertion inside a lazy filter/prefix at `Celebrations.swift:171`. Re-evaluation can consume all URLs. | Use deterministic image collection; rerun existing regression and inspect the celebration. |
| QA-02 | P0 verification | Maps test fixture has an unmatched collection bracket at line 65; Debug helper fails framework packaging before hosted tests run. | Restore reliable package/hosted tests; keep successful Release evidence separate. |

## 5. Complimentary Plus access

Production checks used canonical server account IDs resolved from existing Google identities. No account was merged or created from an email, and no client-side email bypass was added.

| Requested account | Verified current state | Remaining action |
| --- | --- | --- |
| `adlloyd@gmail.com` | Existing **Plus / admin / active**, no expiry, every feature flag true | Preserve the grant while enabling commercial enforcement. |
| `hikejournal.review@gmail.com` | Existing **Plus / admin / active**, no expiry, every feature flag true | Use for full-access review/demo journeys; keep isolated from personal data. |
| `adlizzle@gmail.com` | No matching registered HikeJournal account found | Sign in once with Google, then resolve its provider identity to the canonical UUID and apply an audited admin Plus grant. Do not fabricate an identity row. |

Current Plus policy has unlimited cloud hikes and a **10,000-media allowance**. “Full access” currently means all Plus features, with that published tier allowance. An unlimited-media operator exception would require an explicit per-account policy design; this audit did not change everyone's limits.

Two grants already existed, so this audit did not modify them. For future complimentary access, use a server/operator grant with reason, actor, event ID, canonical user UUID, optional expiry, and revoke support. The recipient should see “Complimentary Plus” and the granting store should not be misrepresented. Email can help an operator find an already verified identity; it must not grant access merely because a client supplies it.

Since the user reports no successful HikeJournal store launch, the roadmap's assumed legacy paid-Android purchaser migration is **conditional**, not automatically a blocker for this first launch. Confirm whether any actual purchasers exist; preserve verified admin grants regardless. Possession of a sideloaded APK is not purchase evidence.

## 6. Android/shared work still missing from roadmaps

| Roadmap requirement | Reconciled current assessment | Launch treatment |
| --- | --- | --- |
| Track A permanent signing/artifact safety | Substantially completed in later releases; August status text is stale. Latest existing APK was reverified. | Preserve key custody and upgrade lineage; validate Play-delivered signing/splits after enrollment. |
| Track B stable identity/private media/account deletion | Much is now implemented, unlike early architecture plans. Expiring signed media and canonical identities are present. | Test two-account isolation, expired links, logout/switch/queued data and actual deployed RLS. Do not redo a nonexistent public-media migration blindly. |
| Track B complete account export | No complete account export API/UI was found | Plan a minimally complete downloadable export or documented supported export path before claiming the Track B public-release gate is complete. It must include routes/media references/review/quests, not just a share card. |
| Track A durable external jobs | Durable job store/leases/results exist; independent dispatch/heartbeat and multi-instance recovery still need evidence | Rehearse restart/dropped-response/ambiguous-create handling. Operator attention is safer than blind external retry. Track A does not establish exactly-once publication. |
| Track A deletion/reconciliation | Storage-first delete and retries exist; comprehensive tombstones/cleanup reconciliation are unfinished | Run failure injection for photo/hike/account deletion; retain actionable failures and a recovery procedure. Schedule durable reconciliation beyond the initial launch. |
| Track A direct/resumable uploads | Current multipart, 30 MB, staged retry path exists; direct/resumable sessions/checksum/finalization work remains | Preserve and verify current bounded behavior. Resumable/direct uploads are post-launch unless current large-file tests fail. |
| Track A operations/backups | Health/readiness and correlation exist; dashboard alerts, backup retention and restore proof are not established by source | Production gate: recoverable database/object backup, isolated restore, rollback and actionable monitoring. Recent chat noted Supabase Free had no scheduled backup/PITR evidence. |
| Track B quotas/cost/abuse | Commercial cloud quota enforcement is dormant; general rate-limit/fairness evidence is incomplete | P0 for a paid public service: quotas and bounded expensive work, tenant-safe monitoring, a tested mitigation path. |
| Track C Play console/declarations/assets | Corporate account access exists; HikeJournal app, products and submission work remain | Complete app signing, listing, SDK/native checks, Data Safety, photo/video/FGS declarations, contact/deletion/reviewer instructions. |
| Commercial provider use | Esri imagery is hardcoded on both clients; free-weather and offline rights cannot be inferred from a working URL | Configure/confirm commercial weather and licensed maps, attribution, quotas and offline terms. |
| ROADMAP Review Inbox/Field Guide polish | Some bullets contradict themselves or refer to old Streamlit layouts; native mobile features are materially ahead | Preserve useful UI; improve mobile filters, large-queue selection and ranked suggestions. Do not start a global controller rewrite this week. |
| Longitudinal voice notes | Not shipped on either platform | Post-launch; private audio, recording permissions, interruptions and sync are real new work. |
| Geospatial route-overlap scoring for comparisons | Not shipped; separate from already implemented scenic-trail highlighting | Post-launch; requires documented spatial algorithm and evidence. |
| BADGES_PLAN persistent first-unlock events/social badges | Derived medals and current celebrations exist | Optional extension, not required to ship current badge catalog. |
| ANDROID_APP_PLAN Supabase Auth/direct-client/Edge Functions architecture | Design proposal superseded in practice by hosted FastAPI + verified mobile sessions | Do not replace the backend during polish. Keep data-contract and ownership tests. |

## 7. Store requirements checked against official sources

The checked-in Android target is already **API 36**, matching the current general new-app/update requirement. Use a supported **Play Billing Library 8+** for the new integration; version 7's ordinary submission deadline has passed. [Target SDK requirement](https://developer.android.com/google/play/requirements/target-sdk), [Billing deprecation schedule](https://developer.android.com/google/play/billing/deprecation-faq).

The local APK verifier already checks 16 KB ZIP and native ELF alignment. Still verify Play-generated splits and an applicable runtime device/emulator. [Android page-size guidance](https://developer.android.com/guide/practices/page-sizes).

The Android custom original-media browser needs a substantive restricted-permissions declaration. A custom picker alone does not qualify. Use the existing GPS-integrity justification and a review video; preserve the path required by AGENTS.md. [Google photo/video policy](https://support.google.com/googleplay/android-developer/answer/16935362?hl=en), [project justification](play/PHOTO_VIDEO_PERMISSION_JUSTIFICATION.md).

Apple currently requires Xcode 26+ with the iOS 26 SDK for uploads; the available Xcode 26.6 satisfies the toolchain baseline, while iOS 17 remains the app's supported deployment minimum. Configure and submit the first in-app purchases with the new app version. [Apple requirements](https://developer.apple.com/news/upcoming-requirements/), [first IAP submission](https://developer.apple.com/help/app-store-connect/manage-submissions-to-app-review/submit-an-in-app-purchase/).

Privacy, subscription disclosure, account deletion and review access must agree with the actual production behavior. Apple sign-in revocation is distinct from deleting HikeJournal rows. [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/), [Apple revocation](https://developer.apple.com/documentation/signinwithapplerestapi/revoke-tokens), [Play purchase integration](https://developer.android.com/google/play/billing/integrate).

The 12-testers/14-days requirement applies to qualifying new personal developer accounts. The user confirmed corporate accounts and direct Play production access, so it is not scheduled here. Technical device/purchase validation and store review still apply. [Google testing eligibility](https://support.google.com/googleplay/android-developer/answer/14151465).

## 8. Chat-history requirements preserved

Relevant retrieved chats included “Fix map photo coverage”, “Add species page scroll controls”, “Fix Android Supabase egress”, “Add species name sorting”, “Investigate Supabase egress spike”, “Fix iNaturalist sync connection”, “Assess animated hike routes”, “Add Android photo sharing”, “Review Android app performance”, and the September Species Review reconnection conversation.

The plan preserves their practical intent:

- Show the full geotagged collection as users pan/zoom; a total count label is not sufficient.
- Make the initial camera useful for the main photo region, including the Orlando-heavy collection.
- Reduce database egress without removing photos, compressing away useful product detail, or making replay dependent on repeated network calls.
- Render cached content promptly; the reported 29-second repeat-load experience is a regression target, not an accepted baseline.
- Keep original GPS-bearing media ingestion and its Play declaration.
- Make Review reconnect without requiring a restart, and make iNaturalist connect while sync runs.
- Keep replay controls clear of the route, support speed changes, and show elapsed miles/numbered replay markers.
- Port the explicitly requested single-photo sharing feature to iOS.
- Keep platform-specific build numbers, publish only affected verified artifacts, and attach signed APKs to GitHub releases when a release is requested.

Final publication during October 12–18 remains a target conditional on finishing the P0 work, physical-device checks, product setup and store review. The plan schedules a submission-ready candidate first and does not promise approval on a specific day.
