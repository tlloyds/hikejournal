# Track B: Multi-user product

**Track status:** planned

**Outcome:** HikeJournal supports multiple real users with verified identities,
per-user authorization and storage, isolated Android state, safe account
lifecycle, and a migration path for the original personal owner—without losing
the functionality hardened in Track A.

Track B changes the security and ownership model. It is intentionally separate
from Track A so daily personal reliability can improve before this larger
migration is complete.

Track A may impose generous limits on the one configured personal owner to
prevent accidental resource exhaustion. Track B turns those service safeguards
into per-user accounting, fair tenant quotas, and abuse controls; it must not
treat the Track A owner key or global limit as a tenant boundary.

## Scope

Track B includes:

- user registration/sign-in, verified JWT sessions, recovery, logout, device
  session management, and optional multi-factor authentication;
- stable tenant/user identifiers and owner-scoped authorization at API,
  repository, database, job, object-storage, and cache boundaries;
- private per-user media delivery and quotas;
- account-scoped Android database/files/queues with safe switching and wiping;
- per-user iNaturalist credentials and publishing state;
- profile, export, deletion, retention, and support/recovery workflows;
- rate limiting, abuse protection, audited administrative access, and scalable
  capacity controls;
- preservation or explicit migration of current hike collaboration semantics;
- migration of the current single owner and their journal without duplication or
  loss; and
- multi-client isolation, migration, security, and load verification.

## Non-goals

Unless separately approved, Track B does not:

- add a social feed, public profiles, messaging, follower graphs, or public media;
- introduce subscriptions or billing;
- redesign unrelated Android or Streamlit product surfaces;
- replace all shared Python/domain code;
- fork journal data into separate Android and web databases;
- remove offline functionality or require connectivity to record a hike; or
- complete Google Play listing/review work, which belongs to Track C.

Existing collaboration metadata and behavior must be preserved. Expanding it
into invitations, roles, or shared editing requires its own product and security
specification rather than being inferred from “multi-user.”

## Track A dependencies

Track B depends on these Track A foundations:

- durable jobs include owner scope and do not rely on a global process dictionary;
- mutation idempotency keys and operation ledgers are owner-scoped;
- deletion and upload sessions carry stable owners;
- API contracts and compatibility negotiation are versioned;
- backups and restore drills work before ownership data is migrated;
- Android cache/queues/files are already namespaced by server/environment;
- release signing and upgrade paths are stable; and
- monitoring can identify per-tenant failures without logging private content.

Identity design may begin in parallel with late Track A, but production tenant
migration cannot begin until backups, compatibility, and isolation tests exist.

## Compatibility requirements

- The original single-owner journal becomes one real account with stable ownership;
  it is not copied into a new empty product or left under a synthetic global user.
- Existing record IDs, media object identity, routes, observations, review state,
  quests, badges, and iNaturalist publication references remain valid.
- The mobile API may temporarily accept the legacy single-owner pairing flow only
  for a bounded migration window. It must not become an alternate path around
  per-user authorization.
- Offline operations created before authentication migration retain their owner
  mapping and synchronize once the user completes the migration.
- Logout and account switching never upload one account's queued operations into
  another account.
- Database changes use expand/backfill/verify/contract sequencing. Service-role
  access is limited to narrowly defined server operations, never used as a reason
  to skip resource authorization.
- Streamlit and Android use the same stable subject mapping and authorization
  semantics, even if their interactive login mechanisms differ.
- Current functional journeys remain available to every appropriately authorized
  user unless an explicit product decision says otherwise.

## B0 — Identity, tenancy, and migration design

### Work

- **B0.1** Select the identity provider and supported login methods. Define issuer,
  audience, stable subject, email-change behavior, refresh-token lifetime,
  revocation, recovery, and optional MFA.
- **B0.2** Define the canonical internal user ID independently of mutable email.
  Map the current `MOBILE_OWNER_EMAIL`/subject and Streamlit OIDC identity to it.
- **B0.3** Produce a resource ownership matrix for hikes, collaborators, photos,
  routes, observations, reviews, species preferences, quests, medals, jobs,
  operation ledgers, upload sessions, integration credentials, and audit records.
- **B0.4** Define roles and collaboration semantics separately from ownership.
  Specify read/write/delete/publish/reshare rights for owner and collaborator.
- **B0.5** Threat-model broken object-level authorization, token theft, refresh
  replay, account enumeration, signed-URL leakage, cross-account caches, support
  impersonation, and deletion/export abuse.
- **B0.6** Plan migration cohorts, compatibility window, rollback, and reconciliation
  for the original owner and later beta users.
- **B0.7** Define privacy, retention, export, deletion, support, and audit requirements
  before schemas are finalized.

### Exit gates

- Identity and resource-authorization specifications are reviewed and approved.
- Every owned resource has an unambiguous subject, role, and authorization rule.
- The original owner maps deterministically to one future account.
- Threat-model findings have owners and acceptance tests.
- Migration can roll back without losing new writes or reassigning ownership.

## B1 — Authentication and device sessions

### Work

- **B1.1** Implement login/registration according to the approved product model,
  using system browser or provider-recommended secure flows and verified redirects.
- **B1.2** Validate JWT signature, issuer, audience, expiry, subject, and token type
  at the API. Never trust email or owner IDs supplied as ordinary request fields.
- **B1.3** Implement secure refresh-token rotation, replay detection, revocation,
  logout, and per-device session inventory.
- **B1.4** Store Android tokens using Keystore-backed protection; redact headers,
  redirects, errors, analytics, and crash reports.
- **B1.5** Implement recovery and provider-linking/unlinking without account takeover
  or accidental duplicate accounts.
- **B1.6** Preserve a clearly labeled local-development authentication mechanism.
  It must be disabled in public production.
- **B1.7** Remove the global pairing key as public-production authorization after
  the migration window and verify it cannot access user routes.

### Exit gates

- Expired, wrong-audience, wrong-issuer, revoked, replayed, and altered tokens fail.
- Revoking one device does not revoke unrelated devices unless requested.
- Android login/logout/restart/token-refresh flows pass on supported API levels.
- Secrets/tokens do not appear in logs, backups, screenshots, crash reports, APK,
  AAB, or repository artifacts.
- The legacy pairing route is unreachable in the public production configuration.

## B2 — Owner-scoped data authorization and RLS

### Work

- **B2.1** Add immutable owner IDs and appropriate collaborator/role relationships
  to all resource tables, including Track A operational tables.
- **B2.2** Backfill ownership in repeatable batches with counts, checksums, exception
  reports, and rollback markers.
- **B2.3** Implement owner/collaborator-scoped database RLS or an equivalently
  rigorous API authorization layer. Prefer database enforcement as defense in depth.
- **B2.4** Replace service-role fetch-all/application-filter patterns with scoped
  queries. Every resource-by-ID operation checks access, not only list endpoints.
- **B2.5** Propagate user context through repository, job, storage, discovery,
  publishing, deletion, idempotency, and audit services.
- **B2.6** Ensure missing and forbidden resources do not leak another account's
  existence or metadata through timing/error differences beyond accepted limits.
- **B2.7** Define secure administrative access as separate audited roles, never a
  hidden normal-user flag.

### Exit gates

- A generated cross-tenant test matrix attempts every list/read/create/update/
  archive/delete/upload/publish/job/status route with another user's IDs and fails.
- Database policy tests prove direct unauthorized access fails even when an API
  handler accidentally omits a filter.
- Backfill counts reconcile with the pre-migration inventory and no resource has a
  null, ambiguous, or unexpected owner.
- Existing owner/collaborator workflows pass on Android and web.

## B3 — Account-scoped Android state

### Work

- **B3.1** Extend server/environment namespaces from Track A to stable account IDs
  for Room records, operation queues, app-owned media, thumbnails, OAuth state,
  map metadata where private context applies, and preferences.
- **B3.2** Require an explicit active account for remote reads/writes. Background
  workers bind to the account/session that created each operation.
- **B3.3** Prevent account switch when unsafe local-only state is unresolved, or
  preserve it in its original account namespace with a clear return path.
- **B3.4** Implement logout choices and policy: revoke session; cancel account-bound
  work; remove decrypted tokens; and wipe or retain offline content as explicitly
  selected/allowed.
- **B3.5** Provide secure account switching without cross-account flashes in UI,
  image cache, notifications, widgets, or background work.
- **B3.6** Migrate the personal owner's existing unscoped local state into their
  authenticated namespace exactly once with a durable migration marker.
- **B3.7** Preserve offline hike recording. A signed-in user can record without
  connectivity, and the resulting data remains bound to that account.

### Exit gates

- Automated tests seed two accounts with colliding local/server IDs and prove no
  read, preview, notification, queue item, or upload crosses accounts.
- Logout removes all credentials and applies the documented local-data policy.
- Switching accounts during queued, retrying, and attention-state operations is safe.
- The original owner's local migration is idempotent and preserves record/media/
  queue counts.

## B4 — Private per-user media and quotas

### Work

- **B4.1** Move new media to owner-scoped private object keys and authorized access.
  Store object identity rather than permanent public delivery URLs where possible.
- **B4.2** Issue short-lived read/upload permissions after resource authorization.
  Bind permissions to user, object, operation, method, size, and expiration.
- **B4.3** Migrate existing public objects in controlled batches while both old and
  new clients can display them. Revoke public delivery only after compatibility passes.
- **B4.4** Prevent signed URLs and CDN caches from becoming long-lived public links;
  define cache headers and revocation expectations.
- **B4.5** Add per-user usage accounting and enforce transparent quotas through the
  durable upload system.
- **B4.6** Ensure deletions, exports, backups, derivatives, and orphan reconciliation
  cover each user's media without crossing tenants.

### Exit gates

- An authenticated user cannot fetch another user's object by guessing its key,
  reusing an upload session, or modifying a signed request.
- Expired/revoked media authorization fails, while offline app-owned copies behave
  according to policy.
- Public access to migrated production objects is disabled after supported clients
  pass the private-delivery flow.
- Usage totals reconcile with provider inventory and deletion cleanup.

## B5 — Per-user iNaturalist and external integrations

### Work

- **B5.1** Bind OAuth attempts, credentials, scopes, publishing jobs, remote IDs,
  rate limits, and disconnect state to the authenticated user.
- **B5.2** Encrypt integration credentials with a KMS/secret-management design that
  supports key versioning and rotation; do not derive encryption solely from a
  global API pairing key.
- **B5.3** Migrate or require a clear one-time reauthorization for the original
  owner without losing existing remote observation links.
- **B5.4** Ensure callbacks bind to the initiating account/device/session and are
  single-use, time-bounded, and safe against login CSRF/account swapping.
- **B5.5** Implement disconnect/revocation and account-deletion cleanup while
  retaining the minimum remote identifiers required for idempotency/audit under
  the published retention policy.

### Exit gates

- Two simultaneous users can authorize and publish without credential or result
  crossover.
- Credential key rotation preserves access or deliberately drives reauthorization
  with no silent failure.
- Callback replay, state substitution, session switching, and wrong-user polling fail.
- External publication remains exactly-once at the logical operation level.

## B6 — Account lifecycle, export, and deletion

### Work

- **B6.1** Add account/profile settings, support contact, device/session management,
  and a clear explanation of synchronized versus local data.
- **B6.2** Create a machine-readable and human-usable export covering journal
  metadata, routes, media, observations, review/publishing state, quests, and
  relevant account settings.
- **B6.3** Provide authenticated in-app deletion and a public web request path,
  identity confirmation, status tracking, cancellation window if offered, and
  completion notice.
- **B6.4** Drive deletion through durable Track A tombstones/jobs across database,
  media, credentials, caches, derived data, and processors. Apply documented legal
  backup retention separately.
- **B6.5** Document retention for operational logs, idempotency/audit records,
  backups, support data, deleted content, and external publication references.
- **B6.6** Handle account recovery, email/provider change, inaccessible provider,
  and duplicate-account resolution with audited support tooling.

### Exit gates

- Export completeness reconciles against seeded account inventory and opens with
  documented tools.
- Account deletion removes or tombstones all in-scope data, revokes sessions and
  integrations, and completes after injected failures through durable retry.
- The public deletion request path and in-app flow are reachable and tested.
- Recovery/support actions require appropriate proof and create an audit record.

## B7 — Abuse protection, scale, and operations

### Work

- **B7.1** Add per-user, per-device, per-IP, endpoint, upload, discovery, and
  publishing limits with clear user-visible quota responses.
- **B7.2** Protect registration, recovery, OAuth, uploads, expensive identification,
  and object delivery from enumeration and automation abuse.
- **B7.3** Build capacity and cost models for database, object storage/egress,
  identification, maps, jobs, logs, and third-party APIs.
- **B7.4** Extend monitoring with tenant-safe aggregate metrics and high-cardinality
  correlation kept outside metric labels.
- **B7.5** Add audited administrative/support tools with least privilege, approval
  for destructive actions, and no routine exposure of routes/media.
- **B7.6** Establish incident response, breach notification inputs, credential/key
  rotation, user communication, and tenant-specific repair procedures.
- **B7.7** Perform load, isolation, authorization, dependency-failure, and security
  testing at expected launch scale plus agreed headroom.

### Exit gates

- Load tests meet the Track A latency/reliability budget at launch capacity and
  agreed headroom without tenant starvation.
- Abuse controls block tested scenarios without breaking ordinary offline retry.
- Administrative actions are least-privileged, logged, reviewable, and reversible
  where feasible.
- An incident exercise demonstrates token revocation, key rotation, service
  containment, restore, and user-impact assessment.

## B8 — Migration and multi-user release gate

### Work and evidence

- **B8.1** Rehearse production migration on a restored copy, including ownership
  backfill, private-media transition, personal-owner account linking, and rollback.
- **B8.2** Run old-client/new-API, migration-client/new-API, and fully authenticated
  client matrices across Android and Streamlit.
- **B8.3** Verify the complete no-regression feature inventory for the original
  owner and a newly created user.
- **B8.4** Run cross-tenant authorization tests for every endpoint, repository
  operation, database policy, storage action, durable job, export, and deletion.
- **B8.5** Verify local account migration, logout/wipe, account switching, offline
  recording, queued synchronization, and process/reboot recovery.
- **B8.6** Audit privacy/retention documentation and feed the resulting data map to
  Track C's Data Safety and policy work.
- **B8.7** Remove legacy production authorization only after migration completion
  telemetry proves no supported client depends on it.

### Track B definition of done

- Every production request and object is authorized to a verified stable user or
  narrowly defined service role.
- Cross-tenant test coverage finds no data, media, job, cache, log, or integration
  leakage.
- The original owner's server and device data migrates with reconciled counts and
  no ID/media/publishing loss.
- Android safely supports login, refresh, offline work, logout, local wipe, and
  account switching.
- Streamlit uses the same identity/authorization model and retains current journeys.
- Private media, quotas, per-user iNaturalist, export, deletion, retention, abuse
  controls, and audited support operations are verified.
- The global pairing key is not a public-production authorization path.
- Track A reliability and performance gates still pass under multi-user load.

## Webapp changes required by Track B

Track B requires webapp work. It is not optional because both clients access the
same journal records.

Required changes include:

- map Streamlit's Google OIDC/session identity to the same immutable internal user
  ID used by Android and the API;
- replace email/global-owner assumptions with owner/collaborator-scoped repository
  calls and database authorization;
- propagate authorization context through Library, Journal, maps, Species Review,
  publishing, media, quests, archive/delete, and collaboration flows;
- adopt private authorized media delivery instead of permanent public URLs;
- support account profile, export, deletion, and support/recovery entry points, or
  link clearly to authoritative external pages that do;
- preserve and security-test existing collaborator behavior; and
- remain compatible during expand/backfill/migration while the personal owner and
  supported Android clients transition.

These are identity and authorization changes, not permission to redesign or
remove Streamlit product functionality.
