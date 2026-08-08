# Track A implementation status

**Snapshot date:** 2026-08-07

**Scope:** current repository working tree, not a production deployment or a
release certification

This matrix distinguishes code that is present or in progress from the exit
evidence required by [Track A](TRACK_A_PERSONAL_RELEASE.md). No Track A phase is
`verified` yet. In particular, this snapshot does not prove that a database
migration was applied, an API revision was deployed, alerts were connected, a
backup was restored, or a permanently signed APK was installed on the personal
device. Those facts require release-specific evidence.

## Boundary represented by the current work

The mobile API has a separate dependency file and container entry point and can
run without the Streamlit runtime. That is process and deployment packaging
independence, not total product independence: Android and Streamlit still share
the journal database, object storage, schema, models, repositories, and several
domain/service modules. A mobile-only API deploy can leave the web UI untouched,
but shared-code or schema changes still require webapp regression evidence.

Reliability work stays in Track A even though only one person uses the app:
durable external work, safe retries/deletes/uploads, single-owner resource
limits, dependency health, monitoring, backups, contracts, and Android release
engineering. Track B begins when the trust boundary changes: registration and
sessions, immutable user identities, per-resource authorization/RLS, private
per-user media, account-scoped device state, account lifecycle, per-user
iNaturalist credentials, tenant quotas/fairness, and cross-tenant testing.

## Status matrix

| Area | Present or in progress in the working tree | Still required before the phase can be verified | Status |
| --- | --- | --- | --- |
| A0 — current installation safety | Release configuration can omit the pairing key and accept external signing inputs. | Inventory and back up the installed app's local-only state; capture server/database and media backups; perform a restore; choose the permanent package/signing owner; create and protect the permanent key; rehearse the debug-signature transition and credential rotation. | Blocked on owner decisions and operational evidence |
| A1 — baseline and regression harness | Python/Android tests and an APK safety verifier cover part of the changed surface. | Device/emulator feature matrix, Room/Keystore migration instrumentation, disposable migrated integration environment, measured performance baseline, clean-build evidence, and a signed release fixture that passes inspection. | Active, partial |
| A2 — durable jobs | When the Supabase migration is applied and the durable store is required, identification and grouped-publishing jobs have persistent IDs, owner scope, request fingerprints, attempt/retry state, durable results, fenced lease updates, atomic expired-lease attention transitions, and failure-isolated periodic/status-poll recovery. | Apply and verify the migration in the target environment; add an external durable dispatcher/worker and independent lease heartbeat; prove multi-instance/revision recovery; add explicit needs-attention/cancelled transitions, operator cancellation/retry, wall-clock bounds, and retention/pruning for request/result payloads; cover remaining synchronous publication paths; and safely resolve ambiguous iNaturalist creates. A remote create and its local checkpoint cannot currently be committed atomically, so an interrupted create may require attention and **exactly-once publication is not yet proven**. | Active, partial |
| A3 — API-wide idempotency | Durable job request IDs reject a changed payload and replay the recorded job result. | Inventory and ledger every retryable mutation, add revision/conflict/error contracts, define and execute retained-ledger cleanup, and run dropped-response/concurrent-replay tests across all mutation routes. Job idempotency alone is not API-wide idempotency. | Active, narrow slice |
| A4 — deletion and reconciliation | Photo deletion is storage-first, treats an already-missing object as clean, and does not remove the database row when storage reports a failure. | Transactional tombstones, durable cleanup jobs, per-object attempt evidence, scheduled reconciliation, orphan/missing-object repair, and failure-injection tests for every deletion class. The current cross-provider delete is not atomic. | Active, narrow slice |
| A5 — uploads and personal safeguards | Existing compatible multipart uploads remain available. | Direct/resumable sessions, checksums, finalization ledger, abandonment cleanup, byte progress, device free-space checks, and configurable single-owner limits. Track A limits protect the one personal deployment from accidental exhaustion; Track B later adds tenant accounting, fairness, and abuse controls. | Planned |
| A6 — operations and recovery | Liveness, readiness, authenticated dependency/queue health, request snapshots, and correlation headers exist in the working tree. Readiness probes are concurrent, timeout-bounded, and briefly cached. Hosted mode rejects weak/missing pairing credentials and missing owner identity; container access logs are disabled to avoid OAuth/query leakage. | Deploy and exercise them; prove pairing-key generation/rotation, add failed-auth monitoring/throttling or an equivalent edge control, verify platform request-log query redaction and restricted retention, and add durable cross-instance metrics, dashboards, routed/tested alerts, cleanup/upload metrics, synthetic checks, privacy-reviewed Android crash/ANR reporting, automated backup retention/object recovery, and a completed isolated restore drill. Cached readiness is diagnostic behavior, not monitoring or deployment evidence. | Active, partial |
| A7 — contract/deployment boundary | The API has an API-only dependency set, additive contract/config fields, a checked route-presence manifest, and a normalized OpenAPI fingerprint over every protected operation plus modeled schemas. Android now parses the contract and compatibility window additively. | Human-reviewable schema snapshots/diffs, typed response/error models and Android consumer fixtures for all shapes, a required CI breaking-change gate, capability-driven behavior, support-window policy, schema capability checks, and path-filtered deployment triggers. The fingerprint detects drift but does not prove compatibility by itself. | Active, partial |
| A8 — Android productionization | The working tree targets API 36, separates debug/personal-release networking and filenames, requires HTTPS API and trail-style URLs for personal release, omits compiled release pairing credentials, accepts external signing configuration, requires the expected signer digest and affirmative modern APK/strict AAB signature evidence before staged promotion, uses a Keystore-backed preference path, excludes sensitive connection preferences from transfer backup, and includes APK inspection/state/performance work. | Permanent key and recorded signer identity; a signed APK/AAB and provenance evidence; debug-to-release user-data backup/transition; Keystore/legacy-fallback migration instrumentation and main-thread performance work; owner approval of both the production trail provider and hardcoded Esri satellite service including quota, attribution, privacy, commercial/permitted-use, and offline rights; supported-device/API testing; and complete accessibility/resilience checks. | Active, partial; signed release blocked |
| A9 — integrated personal release | Roadmap, runbook, and verification tooling exist. | Complete every required matrix, deploy the compatible API/schema, run webapp regression against the migrated environment, perform rollback/restore drills, install and upgrade the signed personal APK, and archive checksums, signer fingerprint, test results, runtime smoke evidence, and known limitations. | Not started as a release gate |

## Important conditional behavior

- Hosted configuration requires the Supabase mobile-job store. The durability
  statements above apply only after `sql/mobile_jobs_migration.sql` is applied
  successfully and `MOBILE_JOB_STORE_REQUIRED=true` (or hosted-policy detection)
  prevents the local fallback. Local development may use an in-memory store;
  those jobs do not survive process restart.
- Lease fencing prevents an old worker from persisting over a newer claimant,
  and persisted progress extends a lease. There is no independent heartbeat or
  external durable dispatch service yet; recovery still depends on an API
  process receiving CPU and running its periodic scan or handling a poll.
- Ambiguous iNaturalist create failures are surfaced for manual attention instead
  of being blindly replayed. This reduces duplicate risk but cannot establish
  whether the remote observation was created before the response was lost.
- Request metrics are process-local and reset with an instance. No production
  dashboard, alert policy, backup schedule, or restore result is represented by
  the repository alone.

## Current release blockers

The personal production release remains blocked until, at minimum:

1. current server media/data and local device-only state are inventoried and
   recoverably backed up, and a restore/transition rehearsal succeeds;
2. the mobile-job migration and target deployment are verified, including
   restart and multi-instance behavior;
3. the iNaturalist ambiguous-create and remaining non-durable publication paths
   meet the A2 idempotency exit gate;
4. permanent signing ownership/key custody and the debug-to-release migration
   are approved and exercised;
5. the owner supplies `MOBILE_TRAIL_MAP_STYLE_URL` from a production map/style
   provider and approves the separate Esri World Imagery satellite dependency;
   attribution, quota, privacy, commercial/permitted-use, and offline-storage
   terms must be accepted for both;
6. alerts, backup retention, restore drill, rollback, contract checks, and webapp
   regression evidence are complete; and
7. a clean, versioned, permanently signed APK/AAB passes artifact, upgrade,
   device, feature, failure, and performance gates.

Update this file when evidence changes; do not infer completion from roadmap
scope or from a passing unit-test subset.

Latest local candidate evidence: [0.6.29](../release-evidence/0.6.29/README.md).
