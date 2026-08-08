# Track A: Personal release hardening

**Track status:** active

**Current implementation evidence:** see
[Track A implementation status](TRACK_A_PROGRESS.md). No phase is verified or
represented as deployed merely because its implementation is present in the
working tree.

**Outcome:** a reliable, performant, release-signed APK for the current owner,
backed by a durable and independently deployable mobile API, without removing or
breaking any current Android or web functionality.

Track A deliberately retains the current single-owner companion model. It
creates reliability, compatibility, observability, and production-build
foundations that Track B will later reuse.

## Scope

Track A includes:

- protection and migration of the currently installed personal application;
- durable identification and iNaturalist publishing jobs;
- API-wide idempotency and explicit retry/attention semantics;
- tombstoned deletion, cleanup reconciliation, and orphan detection;
- resumable or direct media uploads, quotas, checksums, and cleanup;
- dependency-aware health, metrics, logs, alerts, backups, and restore drills;
- formal mobile API contracts and mobile/web deployment isolation;
- production Android variants, signing, HTTPS configuration, secret handling,
  state restoration, cache isolation, performance, and device resilience;
- comprehensive no-regression, upgrade, failure-injection, and performance
  verification; and
- a functional versioned APK plus an updated API deployment.

## Non-goals

Track A does not:

- introduce registration, login, account switching, or multiple users;
- migrate Supabase to direct Android access;
- split Android and Streamlit into separate journal databases;
- redesign or remove current features;
- make journal media public as a product feature or complete the future
  multi-user privacy model;
- add subscriptions, billing, social features, or public content;
- submit the consumer application to Google Play; or
- replace the Streamlit webapp.

Security defects that can be corrected without changing the single-owner model
remain in scope. Track A must also avoid choices that would make Track B harder:
new job, idempotency, deletion, audit, and upload records carry an owner scope,
even when its value is currently the one configured personal owner.

## Required invariants

The [shared no-regression and compatibility rules](README.md) apply in full. In
addition:

- The first release-signed installation must not strand unsynchronized hikes,
  routes, media, edits, review decisions, or publishing work from the existing
  debug-signed installation.
- The release app must never contain a compiled pairing credential. Pairing is
  performed after installation and the credential is protected with an Android
  Keystore-backed mechanism.
- A mobile API restart, deploy, or scale-out event must not lose accepted work or
  cause an external observation to be published twice.
- A client timeout after a successful server mutation must be safe to retry.
- A failed storage deletion must not be reported as completed deletion.
- The webapp remains functional against every Track A schema and shared-service
  migration.
- Performance improvements must not trade correctness for speed, and no measured
  critical journey may regress beyond the performance gate below.

## Dependencies and sequencing

The mandatory sequence is:

1. `A0` inventories and protects current state.
2. `A1` establishes test, telemetry, and baseline evidence before behavior changes.
3. `A2` through `A6` harden server-side state and operations. They may overlap
   after their schema contracts are agreed.
4. `A7` establishes API/deployment compatibility around the hardened behavior.
5. `A8` productionizes Android and adopts the new capabilities using compatible
   fallbacks.
6. `A9` performs end-to-end verification, migration, and release.

Server changes deploy before an Android build that requires them. Existing
mobile endpoints stay available until `A9` proves both the current and previous
supported APKs work. Destructive cleanup is never used as a shortcut to repair
an installation.

## A0 — Current-installation safety and release decisions

### Work

- **A0.1** Record the installed package ID, versionName, versionCode, signing
  certificate, configured API endpoint, local database version, pending operation
  counts, locally owned media count, and active/interrupted recording state.
- **A0.2** Synchronize what can be synchronized and export a sanitized manifest
  of anything still local-only or awaiting attention.
- **A0.3** Take a database backup and media inventory before schema or signing
  work begins.
- **A0.4** Decide whether the personal release and future Play application share
  `com.hikejournal.app`. Record the permanent signing owner and recovery process.
- **A0.5** Generate and securely back up a permanent upload/release key without
  checking it or its passwords into the repository.
- **A0.6** Define the one-time transition from the currently debug-signed package.
  Because Android cannot update an app signed by a different certificate, use a
  final data-safe synchronization/export step before uninstall/reinstall, or an
  explicitly approved alternate package. Do not improvise during release.
- **A0.7** Rotate any credential that was compiled into an earlier distributable
  APK. Coordinate this with iNaturalist token decryption/migration so a pairing
  key rotation does not silently strand the integration.

### Exit gates

- A restorable server-side backup and storage inventory exist.
- Pending/local-only state is accounted for and has an explicit migration path.
- Signing ownership and the package decision are documented.
- A credential rotation and iNaturalist reauthorization/migration plan is tested
  in a non-production environment.
- No personal data appears in committed evidence.

## A1 — Baseline, regression harness, and performance budget

### Work

- **A1.1** Turn the feature inventory in `android/README.md` and the roadmap index
  into an executable/manual release checklist.
- **A1.2** Preserve the existing Python and Android unit suites and add coverage
  where later phases modify behavior. Tests must characterize current outputs
  before refactoring shared paths.
- **A1.3** Add Android instrumentation coverage for Room migrations, cache and
  queue persistence, upgrade from the prior schema, process recreation, and the
  primary Compose journeys.
- **A1.4** Create an API integration environment with disposable database and
  storage namespaces for restart, duplicate request, failure, and migration tests.
- **A1.5** Capture performance baselines on a named reference phone/emulator and
  named backend region: cold launch, cached Library render, journal opening,
  queue processing, metadata mutations, upload throughput, identification and
  publishing job lifecycle, long-recording CPU/memory/battery, and API latency.
- **A1.6** Add artifact scanners for debug signing, debuggability, cleartext
  production networking, embedded credentials, LAN endpoints, unexpected
  exported components, native-library alignment, and release version mismatch.
- **A1.7** Add a Streamlit smoke/regression suite for shared database, repository,
  media, Species Review, publishing, and deletion paths affected by Track A.

### Performance and responsiveness gates

Unless a stricter target is recorded before implementation, each release
candidate must satisfy all of the following on the same test setup:

- no critical journey has a p95 elapsed-time regression greater than 10 percent
  from the accepted baseline;
- cached Library content becomes usable within 500 ms p95 after the application
  shell is ready, and a cached journal opens within 500 ms p95;
- ordinary authenticated metadata reads complete within 750 ms p95 and metadata
  mutation acknowledgements within 1 second p95 when client and API use the
  selected production regions and no third-party call is involved;
- tested foreground UI journeys contain no frozen frames and fewer than 5 percent
  slow frames on the reference device;
- the application produces no ANR or out-of-memory failure during the release
  media, sync, map, and recording scenarios;
- an eight-hour simulated/field recording has no accepted-point or timing loss,
  and battery/CPU/memory measurements do not regress by more than 10 percent from
  baseline without a documented correctness reason; and
- returning from a cached detail to Library does not require an unnecessary full
  network reload.

If the initial baseline proves an absolute threshold unrealistic, revise the
threshold in this document before optimizing toward it. A release may not waive
the relative no-regression requirement after results are known.

### Exit gates

- Baseline evidence is repeatable and identifies device, build, network, backend,
  sample size, p50, p95, and failure count.
- The harness can detect loss or duplication of a queued mutation.
- Shared-code changes trigger both API and webapp regression checks.
- Artifact scanning fails against the current debug artifact for the expected
  reasons and passes only a correctly configured release fixture.

## A2 — Durable identification and publishing jobs

### Work

- **A2.1** Replace process-memory job dictionaries with durable database records
  and a persistent dispatcher/worker such as Cloud Tasks or a leased
  database-backed worker.
- **A2.2** Model a job with stable ID, owner scope, type, idempotency key, input
  reference, status, attempt count, next-attempt time, lease owner/expiry,
  progress, durable result, structured error, and timestamps.
- **A2.3** Define transitions such as `queued`, `leased`, `running`, `succeeded`,
  `retry_wait`, `needs_attention`, and `cancelled`. Enforce transitions
  atomically and reclaim expired leases.
- **A2.4** Store large or sensitive job input by reference rather than duplicating
  personal content in logs or queue messages.
- **A2.5** Make iNaturalist publication side effects idempotent. Persist remote
  observation/upload identifiers at each completed step so a crash resumes rather
  than republishes.
- **A2.6** Preserve current polling response shapes while adding durable status.
  New capability fields are additive.
- **A2.7** Add cancellation and an operator-safe retry path for jobs that need
  attention.
- **A2.8** Bound attempts and wall-clock duration. Third-party timeouts become
  explicit retryable or terminal errors rather than indefinitely running work.

### Failure tests

- Restart the API before dispatch, during execution, after an external side
  effect, and before the client receives completion.
- Route consecutive polls to different API instances.
- Expire a worker lease and prove exactly one logical completion.
- Simulate iNaturalist timeout, rate limit, partial media upload, and duplicated
  callback.
- Deploy a new API revision while jobs are queued and running.

### Exit gates

- No accepted job disappears or returns an unexplained not-found after restart,
  deployment, or multi-instance polling.
- Replaying a completed job returns its durable result and produces no duplicate
  iNaturalist observation.
- Queue depth, oldest-job age, retry count, and needs-attention count are visible
  to monitoring.
- Existing Android identification and publishing screens require no feature loss
  and correctly render every durable terminal state.

## A3 — API-wide idempotency and synchronization semantics

### Work

- **A3.1** Inventory every mobile mutation and its current client operation ID,
  dependency, retry classification, and resulting server records.
- **A3.2** Require a stable operation ID and owner scope for every retryable
  mutation. Persist a server operation ledger with request fingerprint, status,
  result reference, and retention period.
- **A3.3** Atomically claim operations. The same ID and same fingerprint returns
  the original logical response; the same ID with different input is rejected.
- **A3.4** Define a versioned structured error envelope with stable codes for
  retryable, authentication, validation, conflict, dependency, quota, and
  needs-attention outcomes.
- **A3.5** Add revision/precondition fields for edits vulnerable to lost updates.
  Preserve the current last-write behavior where needed until Android presents a
  compatible conflict path.
- **A3.6** Ensure dependency ordering remains durable across app and API restarts:
  parent hike, route, media, caption/review/species/cover operations must reconcile
  to stable server IDs.
- **A3.7** Define operation-ledger retention longer than the maximum offline retry
  horizon, with archival/cleanup that cannot re-enable duplicates.
- **A3.8** Optimize queue dispatch and refresh invalidation to avoid redundant
  full-list requests while retaining immediate local overlays.

### Exit gates

- Dropping every mutation response after server commit and replaying the request
  produces one logical result.
- Parallel duplicate submissions and out-of-order dependent submissions are safe.
- Android correctly distinguishes retry, attention, conflict, quota, and terminal
  validation states without discarding the local operation.
- Reconnect processing preserves dependency order and meets the accepted sync
  responsiveness budget.

## A4 — Tombstoned deletion and cleanup reconciliation

### Work

- **A4.1** Define deletion states and retention: requested/tombstoned, cleaning,
  complete, recoverable where applicable, and needs attention.
- **A4.2** Atomically tombstone the logical record and enqueue cleanup. Normal
  reads hide it immediately while audit/repair tools can still find it.
- **A4.3** Delete dependent database records and storage objects idempotently.
  Missing objects count as already clean; unexpected access/provider errors do not.
- **A4.4** Persist per-object cleanup results, attempts, and error codes. Do not
  swallow a storage failure or report completed deletion early.
- **A4.5** Add a periodic reconciler for stuck tombstones, orphaned objects,
  missing objects, and records whose media manifest disagrees with storage.
- **A4.6** Cover hikes, everyday sightings, routes, photos/videos, generated
  derivatives, covers, review items, quest relationships, and publishing records
  according to their existing semantics.
- **A4.7** Preserve offline deletion overlays and allow safe client replay.
- **A4.8** Define restore behavior during any recovery window without resurrecting
  partially cleaned data.

### Exit gates

- Injected database and storage failures at every cleanup step eventually
  converge or visibly remain in `needs_attention`; none are silently lost.
- Replaying a deletion is safe and does not affect unrelated records.
- The reconciler detects seeded orphan and missing-object cases.
- Webapp and Android hide the same tombstoned records and retain their current
  delete/archive distinctions.

## A5 — Resumable/direct uploads and quotas

Track A quotas are safeguards for one configured owner and one personal service:
they bound accidental file, batch, transfer, and storage consumption without
introducing tenant identity or fairness. Per-user accounting, tenant isolation,
abuse prevention, and shared-capacity policy belong to Track B.

### Work

- **A5.1** Establish a server-created upload session with owner scope, operation
  ID, expected content type, byte limit, checksum, expiration, and target object
  key.
- **A5.2** Prefer provider-supported signed direct or resumable transfer so large
  media is not buffered through FastAPI memory. Retain the existing multipart
  endpoint for previous supported clients during migration.
- **A5.3** Finalize uploads only after verifying actual size, allowed media type,
  checksum, ownership, and expected object key. Metadata creation and operation
  completion must be idempotent.
- **A5.4** Support cancellation, interrupted resume, expired-session recovery, and
  cleanup of abandoned multipart objects.
- **A5.5** Add configurable per-file, per-batch, per-day, concurrent-transfer, and
  total-storage limits. Personal defaults must be generous enough to preserve the
  current workflow, including large album selections, while preventing accidental
  unbounded transfer.
- **A5.6** Before app-owned copying, estimate selected bytes and check device free
  space. Preserve the current 500-item selection capability; if the batch cannot
  fit, explain why and allow a smaller selection rather than losing the feature.
- **A5.7** Persist byte-level progress and actionable errors, limit concurrent
  transfers, and avoid recomputing metadata or thumbnails unnecessarily.
- **A5.8** Preserve original EXIF/GPS/taken-time behavior, supported image/video
  types, local preview behavior, review defaults, and post-upload URL reconciliation.

### Exit gates

- A transfer interrupted at multiple offsets resumes or safely restarts without a
  duplicate database row or abandoned finalized object.
- Finalized objects match declared size and checksum; corrupt or oversized content
  is rejected before journal metadata claims success.
- Quota and low-storage failures leave the original selection/local copy safe and
  show a recoverable action.
- API peak memory does not scale with the full uploaded file size for the new path.
- Previous supported APK uploads continue through the compatibility endpoint.

## A6 — Health, telemetry, alerts, backup, and recovery

### Work

- **A6.1** Separate process liveness from traffic readiness. Readiness verifies
  required database, storage, and durable-job dependencies with bounded timeouts.
- **A6.2** Add dependency status and a scheduled, harmless authenticated synthetic
  read without exposing secrets or private records.
- **A6.3** Emit structured logs and correlation IDs connecting an Android operation,
  API request, durable job, storage action, and external publish attempt.
- **A6.4** Measure request volume/latency/status, authentication failures, queue
  depth/age/retries, job failures, upload bytes/duration, cleanup backlog, storage
  growth, and dependency health.
- **A6.5** Alert on elevated 5xx/error rate, readiness failure, stuck/old jobs,
  cleanup backlog, repeated auth failures, unusual storage growth, and failed or
  stale backups. Alerts must route to a monitored destination and have runbooks.
- **A6.6** Add privacy-conscious Android crash/ANR telemetry. Exclude coordinates,
  route points, captions, media, tokens, signed URLs, and other journal content.
- **A6.7** Configure automated database backup retention and object recovery or
  versioning appropriate to the selected providers. Encrypt and restrict backups.
- **A6.8** Maintain a manifest/reconciliation report connecting media records to
  object keys and derivatives.
- **A6.9** Write and perform a restore drill into an isolated environment. Verify a
  sampled hike's metadata, route, media, review state, durable operations, and
  publishing state without altering production.
- **A6.10** Record recovery point and recovery time measurements and compare them
  with the agreed objectives.

### Exit gates

- Liveness stays healthy during a simulated dependency outage while readiness
  correctly fails and recovers.
- Each alert has been triggered in a controlled test and reaches its destination.
- A sanitized trace follows one operation across phone, API, worker, and storage.
- A backup has been restored successfully; merely enabling backups does not pass.
- Monitoring and crash reports contain none of the prohibited personal fields.

## A7 — Contract and deployment independence

### Work

- **A7.1** Generate and version an OpenAPI contract for `/v1`; check a normalized
  snapshot into source control and detect breaking changes in CI.
- **A7.2** Add consumer-driven contract tests between Android serialization/models
  and representative API responses, including unknown additive fields and every
  structured error state.
- **A7.3** Make Android consume `/v1/config` capabilities, minimum-supported app
  version, recommended version, API contract revision, limits, and feature flags.
- **A7.4** Define and document the support window, deprecation headers/telemetry,
  server-first rollout, and emergency feature-disable behavior.
- **A7.5** Separate mobile API build inputs/dependencies from Streamlit dependencies.
  The API must boot and pass integration tests with no web process or Streamlit
  runtime installed.
- **A7.6** Narrow deployment triggers so a web-only change does not redeploy the
  mobile API. Shared module/schema changes deliberately trigger both applicable
  test/deploy pipelines.
- **A7.7** Pin and scan runtime/build dependencies, verify base images and Gradle
  wrapper integrity, and produce a dependency/SBOM record for releases.
- **A7.8** Make schema compatibility explicit with expand/backfill/contract
  migrations and readiness checks for required capabilities.
- **A7.9** Retain the optional web handoff and shared journal semantics; deployment
  independence is not data separation.

### Exit gates

- The previous supported APK passes its contract and end-to-end smoke suite
  against the new API.
- A deliberately breaking API change is rejected by CI.
- The mobile API builds, deploys, starts, and serves its smoke test without the
  Streamlit application or its unused dependencies.
- A web-only change does not invoke mobile API deployment.
- Stopping the web service does not affect Android/API journeys other than the
  optional handoff.
- A mobile API rollback can run safely against the expanded schema.

## A8 — Android productionization and responsiveness

### Work

- **A8.1** Create explicit development/staging/personal-release configuration.
  Production builds require an HTTPS API endpoint and fail closed when signing or
  endpoint configuration is absent. LAN and cleartext behavior remain development-only.
- **A8.2** Replace the debug artifact workflow with a minified, non-debuggable,
  permanently signed release APK. Also produce a valid AAB-ready variant without
  changing current personal APK distribution until approved.
- **A8.3** Remove compiled pairing defaults. Pair after installation, store the
  credential through Android Keystore-backed encryption, mask it in UI/logs, and
  preserve an intentional repair/rotation flow.
- **A8.4** Upgrade compile/target SDK and Android Gradle tooling to the current
  supported production requirement while retaining minSdk 26 and verifying all
  behavior changes on API 26 through the target version.
- **A8.5** Namespace Room cache, queues, app-owned media, map packs, and integration
  state by server/environment now. A connection change must not display or send
  the previous environment's state without an explicit migration/confirmation.
- **A8.6** Restore navigation, editors, selections, scroll positions where useful,
  map context, settings, and unfinished non-destructive work across rotation and
  normal process recreation.
- **A8.7** Optimize cache invalidation, parsing, image loading, database queries,
  Compose recomposition, and request batching based on `A1` traces. Do not replace
  cache-first immediate feedback with network blocking.
- **A8.8** Improve validated-internet detection, cancellation, WorkManager
  constraints, bounded retries, and foreground/background transition behavior.
- **A8.9** Make lockscreen recording detail and spoken mile announcements
  configurable without changing their current default until a product decision.
- **A8.10** Use a verified HTTPS App Link for OAuth where provider constraints
  permit; retain a safe compatibility callback until connected installations migrate.
- **A8.11** Decide the broad MediaStore access versus system Photo Picker strategy.
  Preserve full current import capability while adding the policy-compliant path;
  no permission is removed before parity and migration are proven.
- **A8.12** Configure production map/style providers, quotas, attribution, privacy,
  and commercial/offline rights. Preserve trail/satellite switching and offline
  trail packs.
- **A8.13** Add tablet/foldable/landscape/multi-window resilience and accessibility
  checks for TalkBack, switch access, touch targets, contrast, and large fonts
  without a visual redesign of unrelated screens.
- **A8.14** Automate version consistency: `VERSION`, Android `versionName`, mobile
  API version, APK filename, monotonically increasing versionCode, checksums,
  signing fingerprint, R8 mapping, and release notes.

### Exit gates

- Artifact inspection finds no debug signing, debuggability, LAN endpoint,
  cleartext production permission, compiled token, service credential, or
  unexpected exported component.
- The signed APK installs and every subsequent Track A release upgrades in place.
- The one-time debug-to-release transition preserves all accounted personal data
  through the approved synchronization/export path.
- Android API 26 through the current target API pass smoke and permission tests;
  relevant release artifacts pass 16 KB native-page alignment verification.
- Rotation, process recreation, reboot, Doze, permission denial/revocation,
  offline/poor network, low storage, long recording, large media selection, map
  pack, and OAuth scenarios meet their stated expectations.
- Performance gates from `A1` pass with no critical-journey regression.

## A9 — Integrated verification and personal release

### Required release matrix

Verify at least:

| Dimension | Cases |
| --- | --- |
| Installation | clean install; approved debug-to-release transition; upgrade from previous release-signed APK |
| API compatibility | new APK/new API; previous APK/new API; new APK during API rollback where supported |
| Network | offline start; loss during read/write/upload/job; captive/unvalidated network; reconnect; Wi-Fi/cellular transition |
| Process | Android process death; task swipe; API restart; worker restart; rolling deploy; two API instances |
| Data | empty journal; established journal; large archive; queued dependencies; attention items; migration from prior Room/schema versions |
| Media | image/video; EXIF/GPS present/missing; large selection; low disk; cancelled/interrupted/resumed upload; corrupt input |
| Recording | permission denied/revoked; screen off; pause/resume; reboot/recovery; zero/one/many accepted points; long session |
| External services | database/storage outage; map outage; iNaturalist timeout/rate limit/partial publication |
| Clients | Android journey parity; Streamlit smoke suite; optional web handoff |

### Release evidence

- **A9.1** All Python, Android unit, Android instrumentation, lint, contract, and
  artifact checks pass from a clean checkout/build environment.
- **A9.2** The feature checklist in the roadmap index passes on the signed APK.
- **A9.3** Failure-injection reports demonstrate durable jobs, idempotency,
  deletion convergence, upload recovery, and client compatibility.
- **A9.4** Performance results satisfy `A1` gates and include before/after traces.
- **A9.5** A backup restore drill and deployment rollback have succeeded.
- **A9.6** The API deployment exposes the expected version/readiness, and dashboards
  and alerts are active.
- **A9.7** The APK is named `dist/HikeJournal-v<VERSION>.apk`, signed by the recorded
  certificate, checksummed, scanned, installed on the personal device, and smoke-tested.
- **A9.8** Release notes identify compatible API/schema versions, migrations,
  performance improvements, known limitations, and rollback instructions.

### Track A definition of done

Track A is complete only when all of the following are proven:

- The current feature inventory works on the signed personal APK and the webapp
  retains its current shared-data behavior.
- Accepted work survives phone/API/worker restarts and rolling deployment.
- Retried operations and publications do not duplicate logical outcomes.
- Deletion and upload failures converge or remain visibly actionable.
- Monitoring detects dependency, queue, cleanup, and backup failures.
- A real restore and a deployment rollback have succeeded.
- API releases are contract-checked and independently deployable from the web UI.
- The signed APK contains no embedded credential or development endpoint and can
  receive in-place upgrades.
- The performance/responsiveness budget passes.
- All evidence has been inspected, not merely planned.

## Webapp changes required by Track A

No intentional webapp feature or user-interface change is required.

Some Track A implementation touches shared repository, storage, domain, and
schema code. Those changes may require narrow compatibility updates in the
webapp, but they must preserve its existing Library, Journal, map, Species
Review, publishing, media, archive, and deletion behavior. The default approach
is additive schema evolution and shared-service backward compatibility, not a
webapp rewrite.

Specific boundaries:

- Durable mobile jobs may live behind mobile API routes without changing web UI.
  If the webapp uses the same publishing service, it should adopt or remain
  compatible with the durable implementation rather than maintain conflicting
  state semantics.
- Tombstones affect shared reads; repository methods used by both clients must
  consistently hide normal tombstoned records while retaining repair access.
- New upload sessions may be Android-specific initially. Existing web uploads and
  the previous Android multipart endpoint remain available until separately
  migrated.
- Separating API dependencies/deployment should not require a Streamlit behavior
  change. Shared source can remain shared behind explicit packages and tests.
- Monitoring, backups, indexes, and additive database migrations need no visible
  web changes but do require web regression evidence.
