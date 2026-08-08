# HikeJournal delivery roadmaps

These documents are the authoritative delivery roadmaps for hardening the
single-owner Android companion, evolving HikeJournal into a multi-user product,
and publishing it through Google Play.

They complement the older product and feature plans in the repository. When a
roadmap here conflicts with an older plan about release safety, compatibility,
security, or sequencing, this roadmap set takes precedence. Product behavior
already documented in `android/README.md` remains part of the supported product
unless a later, explicit product decision says otherwise.

## The three tracks

| Track | Outcome | May begin | Public launch dependency |
| --- | --- | --- | --- |
| [Track A: Personal release hardening](TRACK_A_PERSONAL_RELEASE.md) | A dependable, release-signed, single-owner APK and independently deployable mobile API | Active now | Required |
| [Track B: Multi-user product](TRACK_B_MULTI_USER.md) | Real user identities, tenant isolation, private per-user data, account lifecycle, and safe migration of the original owner | After Track A foundations exist; design may run in parallel | Required for a public consumer launch |
| [Track C: Google Play](TRACK_C_GOOGLE_PLAY.md) | Policy-compliant listing, testing, signing, review, rollout, and production operations | Publisher setup and policy preparation may run in parallel | Required |

The [Track A implementation status](TRACK_A_PROGRESS.md) is the current
working-tree inventory. Roadmap outcomes and checklists describe required work;
they are not evidence that a capability is deployed or verified.

The intended order is:

1. Make the current personal application safe and reliable without taking any
   feature away.
2. Reuse those reliability foundations while replacing the single shared
   identity boundary with real accounts.
3. Complete public-store review and launch only after the applicable Track A
   and Track B gates pass.

A controlled internal or closed Play test may use a hardened single-owner build
before Track B. It is not the public consumer release.

## Governing no-regression invariant

Every track is governed by this invariant:

> Existing HikeJournal functionality must not be broken, removed, silently
> degraded, or made less reliable. Work may optimize, improve, fix, secure, or
> add behavior. Any intentionally changed behavior requires a separately
> recorded product decision, a migration path, and explicit approval.

Passing compilation or unit tests alone does not prove this invariant. Each
release candidate must demonstrate parity for the supported journeys below and
must retain user data, pending operations, local media, routes, and integration
state across upgrades.

### Supported journeys that must remain intact

The detailed feature inventory lives in `android/README.md`. At minimum, the
release gate covers:

- browse and search current, archived, and everyday journal entries;
- create, edit, archive, restore, and delete hikes and sightings;
- record a hike offline, including pause/resume segments, screen-off operation,
  notification actions, recovery, finalization, and TCX synchronization;
- import photos and videos from the current album workflow while preserving
  available EXIF date, GPS, and app-owned local copies;
- view media, edit captions, select covers, send items to Species Review, and
  safely delete media;
- read cached journal, field-guide, review, publishing, and map information
  while offline;
- queue creates, edits, routes, media, captions, archive actions, deletions,
  review decisions, species assignments, cover changes, and publishing-related
  work, then synchronize them in dependency order;
- use the Field Guide, encounters, Nearby results, Field Quests, filters, maps,
  offline trail packs, and Trail Medals;
- identify photos, confirm/reject/skip suggestions, and assign known species;
- connect iNaturalist and publish grouped observations with the existing notes,
  tags, geoprivacy, and captive/cultivated settings;
- switch between a local and hosted companion configuration without rebuilding
  the app; and
- use the optional web handoff while the Streamlit application is available.

Adding a safer permission path, upload path, authentication flow, or callback
may coexist with the current behavior during migration. The old path is removed
only after supported installations have migrated and parity is proven.

## Shared compatibility rules

All three tracks must follow these rules:

1. **Expand, migrate, contract.** Database and API changes are additive first.
   Data is backfilled and both old and new readers are verified before obsolete
   fields or paths are considered for removal.
2. **Previous-client compatibility.** The production mobile API supports the
   current release and at least the immediately previous supported APK during
   rollout. A longer window may be declared per release.
3. **Stable operations.** Every retryable mutation has a stable client operation
   ID. Replaying the same operation returns the original logical outcome rather
   than duplicating data or external side effects.
4. **Durable local state.** Android database migrations preserve cached records,
   recording sessions, accepted GPS points, operation queues, app-owned media,
   and attention states. Destructive fallback migrations are prohibited for
   release builds.
5. **Safe rollout order.** Backward-compatible server and schema changes deploy
   before a client that depends on them. Cleanup waits until the supported
   client window has closed.
6. **Shared-system compatibility.** Track A does not fork the journal database
   or storage. The Streamlit webapp and Android remain clients of the same
   records, and shared service changes must pass both clients' regression suites.
7. **One release version.** The plain-text `VERSION` value remains canonical for
   Android `versionName`, mobile API version responses, and artifact naming.
   Android `versionCode` increases for every distributed Android build.
8. **No secrets in artifacts.** APKs, AABs, images, logs, test evidence, and
   repository history must not contain pairing keys, Supabase service keys,
   storage credentials, iNaturalist secrets, or private user content.

## Evidence, status, and completion

Each roadmap item has an identifier such as `A2.3`, `B3.1`, or `C4.2`. Delivery
work should reference these identifiers in commits, pull requests, or release
notes. Status values are:

- `planned`: accepted scope, not started;
- `active`: implementation or verification is underway;
- `blocked`: an external decision or dependency prevents progress;
- `verified`: implementation exists and all listed evidence has been inspected;
- `deferred`: explicitly moved with a written reason and destination.

An item is not `verified` merely because code exists. Evidence must include the
applicable tests, runtime exercise, migration result, artifact inspection, and
operations proof named in the track. Store evidence under a release-specific
location such as `docs/release-evidence/<VERSION>/` or attach equivalent CI and
deployment links to the release record. Evidence may contain sanitized command
output, reports, screenshots, metric queries, backup/restore records, and signed
artifact metadata; it must not contain secrets or personal trail/media data.

At every release gate, record:

- source revision and canonical version;
- schema and API migration versions;
- APK/AAB checksums and signing-certificate fingerprint;
- automated test and lint reports;
- feature-regression checklist results;
- upgrade test result from the previously installed release;
- offline/retry/restart/failure-injection results;
- performance comparison against the accepted baseline;
- webapp regression result when shared code, schema, or storage changed; and
- rollback and restore readiness.

## Webapp impact summary

| Track | Are webapp changes required? | Boundary |
| --- | --- | --- |
| Track A | **No intentional web UI or feature changes are required.** Compatibility fixes may be required when shared repository, storage, domain, or schema code is hardened. | Keep existing Streamlit journeys and public behavior. Additive schema migrations and shared-service refactors must be verified against both clients. Mobile API packaging/deployment may be separated without changing the webapp. |
| Track B | **Yes.** | The webapp must recognize the same stable user identity, query through owner-scoped authorization, respect account deletion/export, and preserve collaboration semantics. |
| Track C | **Usually not for core journal behavior.** | Public privacy, support, and account-deletion pages are required. They may be separate web pages. If the webapp supplies them or reviewer access, those specific changes are part of Track C. |

Track A implementers must not make opportunistic Streamlit UI changes. If a
shared-backend change reveals a necessary web compatibility fix, keep it minimal,
test it, and identify the affected Track A requirement in the change record.

## Cross-track decisions

The following decisions affect more than one roadmap and should be made once:

- the permanent Android application ID and signing ownership;
- whether the personal release and future Play build share the same package;
- the stable user/owner identifier used in new durable tables during Track A;
- the future identity provider and token format;
- media privacy and authorized delivery design;
- mobile API compatibility window and deprecation policy;
- publisher account type and whether Google Play classifies the product in a
  health/activity category;
- production map and tile providers, including commercial and offline rights;
- privacy-conscious telemetry providers and data-retention periods; and
- backup recovery-point and recovery-time objectives.

Track A may use a constant single-owner identifier internally, but new tables
and operations must carry an owner field so Track B can migrate rather than
replace them.

## Related repository documents

- `android/README.md`: current Android capability inventory and local usage.
- `ANDROID_OFFLINE_PLAN.md`: delivered offline architecture and historical plan.
- `AGENTS.md`: canonical versioning and release workflow rules.
- `deploy/mobile/README.md`: current single-owner deployment boundary.
- `ROADMAP.md`: older web product/refactor roadmap; it remains relevant to web
  product work but does not replace these delivery roadmaps.
