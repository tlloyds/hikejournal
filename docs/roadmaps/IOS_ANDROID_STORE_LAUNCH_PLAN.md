# HikeJournal iOS and Android store launch plan

**Plan date:** October 12, 2026, America/New_York.
**Target window:** October 12–18, 2026.
**Scope:** iOS + Android + API/shared commercial behavior; Web changes only for shared compatibility, privacy/support/deletion/export.
**Baseline:** `main` at `41e0107`; Android 0.8.46/build 180; iOS 0.8.46/build 18.
**Status:** implementation plan; no launch approval or release completion is represented by this file.

**Implementation update (October 12):** this candidate contains a limited first implementation. The iOS batch celebration now collects photo URLs deterministically; the malformed Maps test fixture is repaired; the iOS Field Guide uses the shared parsed-date sorter and offers scientific-name order; and journal photo detail has protected-file single-photo sharing. The Domain (33 tests) and Maps (29 tests) Swift package suites pass. The iOS Debug app builds and is installed on the booted iPhone 17 Pro simulator. The signed Android build 181 passed artifact verification and upgraded from build 180 on the Android 15 emulator without a fatal runtime log; Debug and Release each passed 180 unit tests and `lintRelease` passed. Android's route replay already multiplies its duration by the remaining route fraction, so the previously suspected timer defect was removed from the work list. Play Billing, Google purchase verification, authoritative Android entitlements and quotas, Apple deletion/revocation, and most remaining iOS parity work are not implemented yet; this build is not a paid-Plus store candidate.

The [full audit](../ANDROID_IOS_RELEASE_PARITY_AUDIT_2026-10-12.md) contains the Android feature inventory, bug-fix ledger, iOS comparison, evidence and missing roadmap work. This plan turns those findings into an ordered delivery and acceptance process.

## Product decisions already made

- Publish both native apps with **paid Plus available at launch**.
- Use the existing Free/Plus model; offer complimentary Plus through trusted server grants.
- Corporate Apple and Google accounts exist; user confirms direct Play production access. Do not schedule a new-personal-account 14-day closed test.
- HikeJournal app records/subscription products/listing work is unfinished on both stores.
- `adlloyd@gmail.com` and `hikejournal.review@gmail.com` already have active, non-expiring admin Plus with every feature flag enabled.
- `adlizzle@gmail.com` must first sign in with Google, then receive the same canonical-account admin Plus grant. No account or provider identity should be created from an unverified email.
- Existing tier defaults are three cloud hikes / 50 cloud media for Free, unlimited hikes / 10,000 media for Plus. Existing Apple pricing is $4.99 monthly / $49.99 annually. Confirm these commercial settings when configuring products; do not silently change policy or price in an implementation patch.
- Preserve the GPS-safe Android original-media browser and iOS PhotoKit originals, accepted route data, offline work, private media and current accounts.

## Critical path and feasibility

The launch path is **store/product setup → verified purchase/account binding → shared entitlement enforcement → integrated clients → signed store-delivered validation → submission**. iOS parity can be developed while console work proceeds, but billing and store setup cannot be left until the final day.

This is more than an iOS cosmetic pass: Android has no Plus purchase integration, shared enforcement is dormant, and Apple deletion is incomplete. A planning estimate is **roughly 50–80 engineering hours**, plus console work and real-device/purchase testing. These are estimates, not measurements or a promise. Provider credentials, product availability, field testing or review may extend the schedule.

Aim for a **submission-ready candidate by Friday, October 16**, with Saturday/Sunday available for review responses and release. Public availability by Sunday depends on store review. If a P0 gate is still open, keep the candidate in TestFlight/Play internal distribution and report the exact remaining gate; do not quietly launch without the requested billing or data safeguards.

## Ordered implementation tickets

### L01 — Complete store and provider setup

**Priority:** P0. **Owner:** publisher, with engineering assistance. **Start:** immediately. **Depends on:** none.

Create/complete the HikeJournal app record for `com.hikejournal.app` on each store; check the widget identifier `com.hikejournal.app.widgets`, distribution profiles, Sign in with Apple and background capabilities. Complete paid-app agreements, banking/tax and required regional availability/trader information. Establish recoverable signing/upload ownership.

Create one Apple Plus subscription group containing `com.hikejournal.app.plus.monthly` and `com.hikejournal.app.plus.annual`, with product localization, review screenshots and availability. Define the Play product/base-plan identifiers and match the approved monthly/annual offer; publish them only after the identifiers and backend allowlist agree.

Configure App Store signed-transaction verification/Notifications V2, Play Developer API service-account access and RTDN/Pub/Sub, Google OAuth signing-certificate configuration, Apple token-revocation credentials, iNaturalist callback and licensed map/weather providers. Review the existing working iOS Release configuration; it is already populated, so do not replace it with examples.

**Acceptance:** console app/product records are usable; Sandbox/license testers can load products; notification test deliveries reach the correct environment; provider callbacks and signing ownership are recorded. First Apple IAP submission accompanies the app version. No server private credentials ship in either app.

### L02 — Make commercial access authoritative and consistent

**Priority:** P0. **Owner:** engineering. **Estimate:** 6–10 hours. **Depends on:** agreed tier policy; L03 verification contracts can be developed together.

Wire `/v1/me/entitlement` into Android using a typed account-scoped model. Make Free, store-paid Plus and admin Plus visibly consistent across clients. Audit every advertised feature gate, including maps/offline packs, Place Profiles, Field Briefing, comparison, historical weather and advanced species history/intelligence.

Wire server decisions into protected feature routes and reserve/write/release quota handling into cloud hike/media creation. Return stable actionable denial/error codes. Preserve idempotent client IDs, avoid charging usage twice, and release reservations after failed storage/database writes. Reconcile quota after deletion. Client assertions about platform/payment/email cannot authorize access.

Keep local recording, saved content, queued files and editing recoverable when a cloud limit is reached. A Free user's completed hike must not disappear because synchronization was denied. Pending creates/uploads must be reflected in local allowance displays, and entitlement changes must invalidate stale limits.

**Acceptance:** new Free accounts stop at documented limits; paid/admin accounts unlock all designated features on either platform; concurrent devices cannot exceed cloud reservations; quota errors retain local work; refunds/expiry update access; caller-supplied paid flags cannot bypass restrictions. The two existing complimentary accounts retain their access.

### L03 — Implement Play subscriptions and finish StoreKit production reconciliation

**Priority:** P0. **Owner:** engineering. **Estimate:** 12–20 hours. **Depends on:** L01 products/secrets and L02 contract.

Add a supported Play Billing Library, localized ProductDetails-based pricing, monthly/annual selection, purchase/pending/cancel/error handling, restore/query purchases and native subscription management. Bind a purchase to the signed-in canonical HikeJournal account using the appropriate obfuscated account identifier. Block accidental duplicate offers when the account already has Plus elsewhere or complimentary access.

Add the authenticated purchase-token verification endpoint and server-side Play Developer API validation, idempotent entitlement projection, acknowledgment, renewal/linked-token handling, refund/revoke/expiry/grace changes and authenticated RTDN processing. Keep raw tokens out of ordinary logs and client-derived access decisions.

Exercise the existing StoreKit path against real App Store Sandbox/TestFlight transactions and Notifications V2. Check environment handling, signed root verification, appAccountToken binding, original-transaction ownership and finishing only after server reconciliation. Add a practical missed-notification/reconciliation procedure rather than assuming all notifications arrive.

**Acceptance:** on both stores, test monthly and annual purchase, cancellation, pending, renewal, canceled-but-still-active, grace/retry, expiry, refund/revoke, restore after reinstall, second device, wrong-account restore and duplicate/out-of-order events. No paid entitlement depends solely on local purchase success. Store-funded and complimentary access coexist without repeated paywall prompts.

### L04 — Complete Apple account deletion and public account information

**Priority:** P0. **Owner:** engineering + publisher content. **Estimate:** 4–7 hours. **Depends on:** L01 Apple credentials.

Extend Apple authorization to transmit its authorization code securely to the backend, exchange/retain the required revocable credential with protected storage, and revoke it during deletion. Handle older accounts without a saved revocation credential through the documented reauthorization flow. Detect revoked credential state and clear account-scoped access. Do not confuse StoreKit private keys with Sign in with Apple token-revocation credentials.

Update privacy/provider/purchase/retention explanations; add a private support contact; make the public deletion request path usable for Apple-only accounts. Explain that deleting HikeJournal does not automatically cancel an Apple/Google subscription or delete observations on iNaturalist. Verify saved journals/media/credentials/local queue cleanup and retry when a provider fails.

Implement a minimally complete account export or documented supported export path required by Track B: journal metadata, routes, media inventory/download access, observations/history, review/publishing references, quests and relevant settings. A hike share card is not an account export.

**Acceptance:** Google and Apple accounts can delete through their supported paths; Apple revocation is demonstrated; deletion errors are recoverable; private media cannot be reached after cleanup; export reconciles with a seeded account. Live public pages, store disclosures and app links match actual behavior.

### L05 — Restore trustworthy iOS verification

**Priority:** P0 verification / P1 bug repair. **Owner:** engineering. **Estimate:** 1–3 hours. **Depends on:** none.

Repair the unmatched dictionary/array bracket in the Maps test fixture. Replace the stateful lazy-filter image collection in the batch celebration with deterministic collection. Resolve/reproduce the Debug helper's XCTest framework packaging failure using isolated build outputs; do not claim hosted-test success from a Release compile. Investigate the historically timing-sensitive recorder test if it still fails rather than relying on isolated reruns as the permanent gate.

**Acceptance:** Maps tests compile; all 33 current Domain tests pass; the hosted app suite runs and passes; the Release app and widget build succeed. New failures are triaged as source, test, toolchain or runtime evidence, with no blanket “environment” waiver.

### L06 — Port complete viewport maps and finish initial camera focus

**Priority:** P1. **Owner:** engineering. **Estimate:** 4–7 hours. **Depends on:** L05; current production viewport API already exists.

Add Swift map summary/viewport models and capability-aware API calls. Connect MapLibre camera-idle changes to debounced, cancellable viewport loads; preserve bounded cached features and exclude stale responses after account/bounds changes. Implement overview clusters and zoom-to-cluster behavior, selected-point detail and accessibility text. Preserve Photos/Routes toggles, route visibility and field marks.

Apply the initial-loading/late-summary fit fix, and separately implement useful dominant-photo-region framing in the shared summary/camera behavior. Current SQL still fits the union of photos and routes. Retain an explicit fit-all option so outlying records remain discoverable. Do not download the complete media collection to calculate the camera on the phone.

Close the iOS trail/satellite and confirmed-species control differences. Keep online imagery and offline-pack provider configuration consistent with the actual licenses.

**Acceptance:** test >100 photos, >100 hikes, empty/no-GPS collection, photo-heavy Florida with remote route/outlier, broad/dense views, zoom/pan, antimeridian/invalid bounds, late cache/summary, fast camera changes, offline fallback and account switching. Every geotagged photo is discoverable; no stale result resets the camera; viewport payloads remain bounded. Compare Android and iOS with the same seeded collection.

### L07 — Make iOS journal/species performance match the product promise

**Priority:** P1. **Owner:** engineering. **Estimate:** 3–5 hours. **Depends on:** L05.

Split hike header, route and photo-page completion. Render cached data/header/first photos promptly; append pages without waiting for all pages. Load further media by deliberate demand/prefetch with deduplication. Preserve offline cache and partial-failure states. Do not silently cap content at the current 10,000-photo loop.

Separate Collection from sightings fetches; load Quests/Discover/Review only when used. Move large model encoding/decoding off MainActor. Apply explicit index/detail freshness, account scoping and mutation/sync invalidation. Refresh sensitive expired media URLs without unnecessarily refetching the whole account.

Add payload-free timing for cache/read/parse/first usable content/HTTP response size and correlation. Use shared API summaries/scoped place/route reads already deployed rather than rebuilding those optimizations.

**Acceptance:** warm saved library/species show usable content within a proposed one-second budget on representative devices, without waiting for network completion; a large hike shows its first content before all photo pages finish; repeated navigation/replay/scientific sort does not trigger account-wide downloads. Measure the proposed budgets, report actual numbers and confirm egress after representative traffic.

### L08 — Finish iOS durable Review, batch submissions and reconnect

**Priority:** P1. **Owner:** engineering. **Estimate:** 4–7 hours. **Depends on:** L05 and L02 error contracts.

Wire Review decisions to the existing SQLite `.reviewDecision` and sync adapter. Persist multi-select operations in one durable transaction before scheduling work, apply immediate overlays, preserve reject/requeue semantics and invalidate affected species/journal/review caches.

Persist batch request UUID, payload/options and state before submitting the start call. Reuse it after a lost response; save server job ID once known. Permit only one active poller per job, bounded/backoff retries, cancellation and restart/reconnect recovery.

Refresh visible Review/Publish after connectivity becomes usable and sync acknowledges relevant changes. Keep cached readability distinct from API/auth/connectivity failure. Show OAuth URL-request progress/error at the connecting button, and preserve originating journal/review/tracking context after callbacks.

**Acceptance:** decide offline → kill/relaunch → reconnect results in one durable decision; multi-selection survives immediate backgrounding; reconnect on the same Wi-Fi resumes decisions without a restart; lost batch-start response reuses the same request; the published external observation is not blindly duplicated on ambiguous failure. Cancel/expiry and concurrent sync/OAuth are covered.

### L09 — Port corrected route replay and photo sharing

**Priority:** P1. **Owner:** engineering. **Estimate:** 4–7 hours. **Depends on:** L05/L06.

Android's remaining-duration expression already includes the remaining route fraction and speed; a source check confirms it is correct. Implement iOS distance-weighted segmented replay with moving point, local route reveal, play/pause/restart/scrub, 0.5×/1×/2×, elapsed/total miles, numbered mile markers, and camera insets that leave the full route above/below controls. Preserve segments; do not draw or measure gaps. Replaying never mutates the saved route or fetches data on each frame.

Add single-photo sharing to the shared iOS photo detail view from hike/gallery/map entry. Reuse the existing activity-sheet bridge, stage a protected file, show preparation/failure, include its note if useful, and reject video from this photo-only action. Do not substitute a URL-only share or the hike keepsake.

**Acceptance:** native/imported/no-route/short/long/multi-segment tracks, pause at 50%, scrub while paused/playing, mid-play speed change and rotation work predictably; at 50% and 1× a 24-second route takes approximately 12 more seconds. A received share attachment is the selected image; cancellation and expired-link retries remain recoverable. Verify Reduce Motion and VoiceOver.

### L10 — Bring Field Guide and queue controls into parity

**Priority:** P1. **Owner:** engineering. **Estimate:** 2–4 hours. **Depends on:** L05/L07.

Add Common name and Scientific name sort choices with deterministic fallback/tie behavior; use parsed-date recent ordering. Add outing scope and consistent life-group filters. Implement a tap/drag alphabet or position navigator for at least 30 visible species with accessible jump actions and room beside rows. Add the useful outing/stage controls missing from the iOS publishing workspace without redesigning the whole inbox.

**Acceptance:** all control combinations operate on one state source; filtering changes jump targets; empty names/mixed dates/diacritics/large collections do not yield invalid ordering or index targets; VoiceOver has an equivalent navigation path. Existing description search and region/confidence labels remain intact.

### L11 — Finish complimentary grants and cross-platform plan presentation

**Priority:** P0 access requirement. **Owner:** engineering/operator. **Estimate:** 1–2 hours plus recipient's first sign-in. **Depends on:** L02.

Preserve the two existing admin grants. After `adlizzle@gmail.com` signs in, resolve its verified Google provider identity to the canonical UUID and use `apply_app_entitlement_event` with source `admin`, plan `plus`, active state, a stable operator event/entitlement ID, reason/actor metadata and no expiry unless the user requests one. Verify the returned snapshot and all flags.

Provide a small audited operator grant/revoke procedure for future complimentary users. Add “Complimentary Plus” presentation and prevent unnecessary purchase prompts on either platform. Keep an ordinary Free test account as well as the Plus review account, so full-access review does not conceal broken quota/paywall flows.

**Acceptance:** all three registered requested accounts have full Plus feature access on iOS and Android; revoke/expiry behavior is deliberate; purchases cannot overwrite or remove an independent admin grant; account switching cannot leak another person's plan. No hardcoded email allowlist in mobile code.

### L12 — Complete release operations and store-review package

**Priority:** P0 public release. **Owner:** engineering + publisher. **Estimate:** 5–9 hours plus field/purchase runs. **Depends on:** L01–L11 integration.

Exercise two-user authorization/private-media isolation, database migration/rollback, recoverable database/object backups and an isolated restore. Define alerts and measured limits for auth failures, API latency, oldest sync/job age, upload/deletion failures, crash/ANR and database/media egress. Document an operator response to abandoned jobs/ambiguous publications. Validate shared Web journeys after schema/service changes.

Prepare real screenshots and sanitized seed content, icon/Play feature graphic, descriptions/subscription explanation, privacy/support/deletion links, App Privacy/Data Safety, age/content/target-audience and export-compliance answers, Android photo/video/foreground-service/health declarations as applicable, and reviewer instructions. The GPS-original permission review uses the existing justification and a demonstration video. Reviewers use the isolated Plus account; do not expose the owner's journals or credentials in documentation.

**Acceptance:** exact uploaded TestFlight and Play-delivered builds pass the matrix below, public links are reachable, products are loaded from the stores, reviewer instructions work without developer assistance, and the publisher has a concrete submission packet.

## Proposed calendar

| Date | Engineering outcome | Publisher/device work | Exit decision |
| --- | --- | --- | --- |
| Mon Oct 12 | Audit and plan complete; confirm existing grants and baseline | Begin L01 app records, agreements, products and provider credentials; sign in the third requested account | Required external inputs and owners identified. |
| Tue Oct 13 | Repair iOS test baseline; design/implement shared entitlement and Play verification contracts; start viewport/progressive-loading work | Finish store product/notification/signing setup and sanitized reviewer data | Products and staging verification are usable. |
| Wed Oct 14 | Integrate Android purchase/entitlement UI; finish iOS maps/loading/durable Review; begin replay/share/sorts | Sandbox/license-tester purchase cycles and initial device tracking/Photos tests | No unresolved purchase-account binding or data-loss issue. |
| Thu Oct 15 | Complete corrected replay, sharing, filters, Apple deletion, commercial gates and privacy/export path; run integration regressions | Validate purchase lifecycle, notifications, denied permissions, original GPS media and account switching | Freeze a candidate only when P0 code is complete. |
| Fri Oct 16 | Run signed archive/AAB and exact store-build checks; fix findings and collect evidence | Representative locked-screen/background hike, low-network upload/reconnect, listing/declarations/reviewer walkthrough | Submission-ready go/no-go based on evidence. |
| Sat Oct 17 | Submit compliant candidates; respond to review findings through normal checks | Monitor both consoles and backend | Keep launch target conditional on review; no critical-gate waiver. |
| Sun Oct 18 | Release approved builds under measured rollout policy, or record the precise remaining blocker | Verify public listing/install/purchase and backend health | Public availability only if approval and gates permit. |

Independent console/content work can proceed during engineering. These dates are an aggressive work sequence, not evidence that work is done. If L01/L03 are unusable by Wednesday, move the public launch date rather than shrinking commercial verification to a button-click smoke test.

## Release-candidate acceptance matrix

| Journey | Required evidence |
| --- | --- |
| Historical data | Google sign-in on both uploaded builds shows existing owner's hikes/media/species/places with reconciled counts. |
| Account isolation | A/B switch during slow request/upload/poll; no old journal, image, map, job, entitlement or staged-file access appears in the new account. |
| Free/paid/complimentary | Free limits and feature gates; purchase/restore/refund/lifecycle; three requested complimentary identities once registered; no client-spoof bypass. |
| GPS recording | Outdoor session, lock/background, pause confirmation, resume segments, marks, voice, process interruption, finish/TCX/upload; older supported and current OS. |
| Photos | Original GPS and capture time verified server-side; no-GPS/limited/denied/revoked/iCloud/video; offline staging survives relaunch. |
| Sync/Review | Offline create/edit/archive/caption/delete/decision; multi-select durability; reconnect without restart; attention/retry; lost responses and batch recovery. |
| Maps | >100 geotagged photos and >100 hikes; dense clusters, pan/zoom rescope, useful initial region, toggles, route/mark detail, offline pack and attribution. |
| Field Guide | Search/sorts/filters/quick navigation/encounters/ecology/history/discovery/quests/medals/celebrations; no repeated broad fetch per scroll. |
| Publishing | Disposable staging individual/grouped posts, geoprivacy, partial failures, cancellation, OAuth during sync and duplicate-avoidance operator handling. |
| Performance/cost | Warm cached content before network; progressive large-hike content; response/first-content timings; repeated navigation/replay workload with recorded database egress. |
| Account lifecycle | Google/Apple deletion, Apple revocation, export, failed storage cleanup retry, subscription guidance and live public URLs. |
| Accessibility | VoiceOver/TalkBack, largest text, contrast/non-color cues, Reduce Motion, landscape/insets; routes remain visible under playback controls. |
| Distribution | Play signing/generated splits/16 KB runtime, upgrade from installed build 180; signed app/widget TestFlight build; final screenshots match binaries. |
| Operations | Backup + isolated restore, rollback against current schema/previous client, alert exercise, shared Web regression and owner/operator runbook. |

Do not count a macOS Live Activity test run with zero tests as device evidence. Do not count successful unsigned Release compilation as a signed archive/upload. Record exact device/OS/source revision/build/product/environment for each result.

## Versioning and release procedure

1. Declare the concrete affected scope before each release. This integrated commercial candidate affects both clients and API/shared code; isolated interim fixes can remain platform-only.
2. Choose the semantic version for the final scope; do not bump `VERSION` merely to force an iOS build. Sync iOS marketing metadata from it.
3. Android distributed/uploaded builds must exceed both local build **180** and any higher Console build. iOS uploads must exceed both local build **18** and any higher App Store Connect build. Preserve independent counters.
4. Deploy backward-compatible API/schema before the clients, with migration checks and rollback evidence; keep supported old clients functioning during review.
5. Run relevant Python, Android Debug/Release/lint and iOS package/hosted/build checks. Build Android through `./build_android.command personal`; require APK verifier, strict AAB signer and lineage evidence. Create and validate the signed iOS archive including the widget.
6. Commit/push the actual release to `main` following AGENTS.md. Use `v<VERSION>` for a new canonical version and unique platform-qualified tags when it is unchanged. Attach only affected verified artifacts, never debug/unsigned files; retain exact hashes/source/evidence. GitHub APK distribution does not prove Play delivery.
7. Release notes explicitly cover Android, iOS, API/shared and Web, including “No functional changes” where appropriate, independent build metadata, test results and log triage.
8. Submit with products, declarations and reviewer access, then observe measured rollout gates. Pause rollout for data loss, cross-account access, broken recording, duplicate publication, signing failure or failed account deletion.

## Work kept after the launch scope

Voice notes/private audio; comparative geospatial route-overlap scoring; persistent first-medal-unlock history/social badges; broad Streamlit visual/controller redesign; direct/resumable upload architecture unless current bounded uploads fail; richer review-card visual presentation; automatic place-state selection polish. Schedule deeper independent job dispatch/heartbeat and cleanup reconciliation improvements after the initial operational failure/recovery gates are proven.

These are explicit product/architecture extensions. They must not obscure current public-release requirements such as quotas, account isolation, commercial provider use, backup/restore, export/deletion and store billing.

## Current execution status

- [x] Audited Android 0.8.46/build 180 and latest GitHub release.
- [x] Assessed current iOS source and recent Android-only changes.
- [x] Ran fresh APK verification, unsigned iOS Release build, focused backend and Swift package checks; recorded failures honestly.
- [x] Verified two existing complimentary Plus accounts against production.
- [ ] Register/sign in `adlizzle@gmail.com`, then apply and verify its canonical-account grant.
- [ ] L01–L12 implementation/console/device/release acceptance complete.
- [ ] Store submissions accepted and public rollout verified.

Implementation has not started as part of the audit request. The existing two Plus grants required no changes; the third awaits a real sign-in. The plan is ready to execute in the order above.
