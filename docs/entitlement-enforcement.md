# Backend entitlement enforcement staging

`GET /v1/me/entitlement` is the authenticated, server-authoritative discovery
endpoint. It resolves the canonical `app_users.id`, then returns the effective
plan, source, billing period, status, expiration, server policy, feature flags,
limits, and current usage. Older Google access tokens without a `uid` claim are
resolved through the durable `google_subject` shadow only; email is never used
as an account key.

New hike and photo writes send `owner_user_id` together with the legacy
`owner_subject` and `owner_email` fields. The latter two remain rolling-deploy
compatibility fields. Canonical ownership wins when the values conflict.

## Current enforcement stage

Existing mobile routes remain observe-only. The checked-in
`EXISTING_MOBILE_ENTITLEMENT_ENFORCEMENT_ENABLED` value is deliberately false:
deploying the entitlement tables and endpoint must not change the paid Android
application's current behavior. A request header, query parameter, or body
field claiming to be Android, paid, Plus, or Lifetime is not trusted evidence
and cannot enable access.

The server exposes reusable helpers for feature decisions and idempotent quota
reservation/release. They are intentionally dormant on existing routes until a
separately reviewed migration can supply cryptographically verified store or
operator evidence and can distinguish the legacy paid Android population.

## Remaining enforcement hook points

When verified migration evidence is deployed, enforcement should be added as a
reserve/write/release transaction around `POST /v1/hikes` and
`POST /v1/hikes/{hike_id}/photos`. Plus feature decisions should be added before
Field Briefing, hike comparison, Place Profiles, historical weather, advanced
species intelligence/review, provenance/history, and future offline-map pack
routes. A denied reservation must reject before storage upload; a failed write
must release its reservation, while a successful canonical database insert lets
the migration trigger commit it. Delete operations already reduce durable usage
through canonical ownership counts.
