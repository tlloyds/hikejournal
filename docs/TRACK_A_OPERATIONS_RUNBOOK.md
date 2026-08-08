# Track A operations runbook

This runbook defines repeatable deployment and recovery gates for the current
personal-release work. It applies to the single-owner APK and mobile API. It
does not prove that the working-tree changes have been deployed or verified,
and it does not authorize multi-user distribution. See the
[Track A implementation status](roadmaps/TRACK_A_PROGRESS.md) for the current
evidence boundary.

## Current working-tree coverage and limits

Present in the working tree:

- the mobile container has an API-only dependency set and can be built and run
  separately from Streamlit, while still sharing data and service code;
- the existing `/health` contract remains unchanged, with separate liveness,
  bounded/cached dependency readiness, authenticated health, and authenticated
  in-process metrics;
- when `sql/mobile_jobs_migration.sql` is applied and the durable job store is
  required, identification and grouped-publishing requests have persistent
  owner-scoped records, request fingerprints, attempt state, fenced leases,
  retry timing, periodic/status-poll recovery, and durable results;
- safe identification work can be reclaimed after a stopped worker; an
  ambiguous stopped iNaturalist create enters attention state instead of being
  blindly repeated, but its remote outcome is not known atomically;
- photo deletion removes storage before its database row and reports a storage
  failure without deleting the row; this is safer but not a transactional
  tombstone workflow;
- Android personal-release configuration requires HTTPS API and map-style URLs,
  omits the compiled pairing credential, accepts external signing inputs, uses
  a Keystore-backed preference path (with a legacy compatibility fallback still
  requiring migration tests), and has an APK safety scanner; and
- API responses expose additive compatibility fields; Android parses the
  contract/compatibility window; and tests guard route presence plus a
  normalized OpenAPI fingerprint. Most response bodies remain loosely typed,
  so a full human-reviewable schema diff and Android consumer-fixture gate is
  not implemented.

These are implementation statements only. Hosted job durability is conditional
on the migration and configuration succeeding. Local development may fall back
to process memory, which is not restart-durable. No production migration,
deployment, monitor, signed artifact, device transition, or restore result is
established by this document.

Not complete yet:

- an external durable dispatcher/dedicated worker and independent lease
  heartbeats (recovery currently runs inside an API process);
- explicit operator cancellation/retry, attention/cancelled transitions,
  wall-clock limits, and retention/pruning for durable job/idempotency payloads;
- exactly-once handling of the ambiguous iNaturalist create boundary and
  durable coverage for every publication path;
- an idempotency ledger for every non-job mutation;
- tombstones and a scheduled cleanup/orphan reconciler;
- direct/resumable multipart uploads, per-class quotas, and checksum repair;
- globally aggregated request percentiles and automated alert policies;
- exercised pairing-key rotation plus failed-auth throttling/edge protection and
  verified platform-log redaction for sensitive query strings;
- an automated backup/export pipeline and completed production restore drill;
- the data-safe debug-signature to permanent-signature device migration and a
  usable backup/export of local-only personal state;
- a permanent signing key, signed release evidence, and signer-transition test;
  and
- production trail and Esri satellite provider decisions with quota,
  attribution, privacy, commercial/permitted-use, and offline-storage rights
  resolved.

These remain Track A work, not multi-user prerequisites to be deferred to Track
B.

## Safe deployment order

1. Record the current API revision and verify the existing `/health` response.
2. Capture a Supabase backup using the project's provider-supported backup or
   logical export facility. Record its immutable identifier and retention date.
3. Export a storage inventory containing object key, byte size, last-modified
   time, and checksum/ETag when reliable. Store evidence outside the repository;
   it contains private journal metadata.
4. Apply `sql/mobile_jobs_migration.sql`. Confirm the table and all three RPCs
   (`update_mobile_api_job`, `claim_mobile_api_job`, and
   `fail_expired_mobile_api_job`) are visible to the service role and unavailable
   to `anon`/`authenticated`.
   Configure `MOBILE_OWNER_SUBJECT` once with an immutable personal-owner value;
   changing it later changes the durable-job owner namespace. Require the store
   with `MOBILE_JOB_STORE_REQUIRED=true` on any hosted target.
5. Deploy the mobile API. Do not deploy an APK that depends on a capability
   until the API capability is visible in authenticated `/v1/config`.
6. Verify `/health/live` is HTTP 200 and `/health/ready` is HTTP 200 with all
   dependencies `ok`.
7. With the pairing key supplied only as a request secret, verify
   `/v1/operations/health`, `/v1/operations/metrics`, `/v1/config`, Library,
   journal details, one harmless metadata edit/reversal, and one test upload.
8. Restart or replace the API while a disposable identification job is queued.
   Prove the same job ID completes once and remains visible from another
   instance. Do not use a public iNaturalist publish for this drill: the remote
   create/checkpoint ambiguity is still a Track A blocker, not a safe
   failure-injection target.
9. Run the full Python suite, Android debug/release unit tests, both lint modes,
   debug build, personal unsigned/signed build as applicable, and the artifact
   scanner. Record exact commands, versions, and outcomes.

Rollback the API revision if readiness or existing APK flows fail. The database
migration is additive and may remain installed during an application rollback.
Do not drop the job table while any accepted job or retained idempotency record
exists.

## Alerts and dashboards

Create host-native metrics from access logs; the built-in request snapshot is
diagnostic and instance-local. Initial personal-use alert thresholds:

- readiness is non-200 for two consecutive checks or five minutes;
- database, storage, or job-store dependency status is not `ok`;
- API 5xx exceeds 1% over 10 minutes with at least five requests, or any critical
  mutation has three consecutive 5xx responses;
- ordinary metadata read p95 exceeds 750 ms or metadata mutation p95 exceeds
  one second for 15 minutes in the production region;
- any job needs attention, oldest active job exceeds 15 minutes, retry-wait jobs
  increase across three samples, or metrics report truncation;
- container memory exceeds 80%, a revision restarts unexpectedly, or the API
  reaches its configured concurrency/instance ceiling; and
- backup age or the last successful restore-drill age exceeds the chosen policy.

Alerts must include revision, route template or dependency, status class,
request ID, and UTC time. Never log pairing keys, authorization headers, request
bodies, photo URLs, owner email, EXIF, captions, or job request/result payloads.
Container Uvicorn access logs are disabled because raw OAuth/discovery query
strings are sensitive. Before launch, verify the hosting platform's own request
logs redact or exclude query strings and restrict their access and retention.

These are target thresholds, not a claim that alerts or dashboards are deployed.
Readiness currently bounds and caches its dependency probes; it does not page an
operator, retain history, or aggregate across instances.

## Backup and restore drill

At least quarterly and before destructive schema/storage work:

1. Provision an isolated Supabase project/database and isolated storage prefix.
2. Restore the selected database backup and copy only the matching storage
   inventory into the isolated prefix.
3. Point a disposable API revision at the isolated resources. Never point the
   production APK at the drill environment.
4. Verify row counts and owner scopes for hikes, photos, observations, routes,
   OAuth records, publishing records, and mobile jobs. Reconcile database object
   references against the inventory in both directions.
5. Exercise read-only Library/journal/species/map flows, then perform disposable
   create/edit/upload/delete and job-restart tests.
6. Record recovery-point age, elapsed restore time, missing/orphan counts,
   integrity failures, API/version/schema identifiers, and remediation owners.
7. Destroy the isolated drill resources only after evidence has been reviewed;
   follow the provider's recoverable deletion process.

A backup is not accepted merely because it exists. Track A's gate is a completed
restore with database/storage reconciliation and usable application reads.
No completed production restore drill is recorded by this runbook.

## Personal APK transition gate

The permanent signing decision, production map provider, and local-data
transition require the owner. No permanently signed personal release is
represented here. Before replacing the current debug-signed installation:

- capture package, versionCode/versionName, signing certificate, Room schema,
  pending mutation counts, pending media, interrupted recording state, and API
  endpoint;
- finish or export every local-only operation and rotate any credential embedded
  in an older debug artifact;
- back up the permanent keystore and recovery information in two controlled
  locations;
- build with the canonical `VERSION`, incremented `versionCode`, production
  HTTPS API URL, owner-selected production `MOBILE_TRAIL_MAP_STYLE_URL`, and all
  four signing inputs;
- set `ANDROID_EXPECTED_SIGNER_SHA256` to the recorded public certificate
  digest and require the release artifact verifier to pass before canonical APK
  promotion; and
- only then uninstall the debug package, install the signed APK, re-pair, and
  repeat the smoke checklist.

## Webapp boundary

No Streamlit UI change is required for the current working-tree slice. The job
migration is additive and mobile-only, and mobile health/metrics/config routes
live only in FastAPI. The webapp still shares the database, storage, models,
repositories, and several service modules, so a migrated integration smoke test
and full Python/web regression tests remain release gates for every shared-code
or schema change. The current packaging improves process independence; full
contract and deployment-trigger independence remains incomplete. Track B
introduces user identity, owner-scoped RLS, private media authorization, account
lifecycle, and other multi-user behavior.
