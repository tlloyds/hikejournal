# HikeJournal API — location and species read reduction

## Release scope

API only. `VERSION` remains `0.8.45`; no mobile build numbers change. Android,
iOS, Web, and shared client code have no functional changes, and no mobile
artifacts are produced.

## Investigation

The Supabase usage chart attributed the 30 September 2026 egress spike
(618.81 MB) entirely to PostgREST. In the retained 24-hour request log,
`hike_locations` was read about 4.7 thousand times and
`hike_location_tags` about 360 times. Each hike-tag lookup was paired with a
13-page, roughly 12,647-row download of the nationwide location library.
This happened as a side effect of resolving visible hikes for archive, detail,
species, and other API requests. The route-import endpoint had only 51 reads
in the same window, so local replay animation was not the primary cause.

Species-observation requests also showed repeated HTTP 400 responses: mobile
projections requested `species_observations.owner_user_id`, which does not
exist in the schema. The retry used a broader observation projection.

## API changes

- Resolve hike place tags with only the visible hike IDs and their referenced
  location IDs. Fetch a canonical redirect target by slug only when needed.
- Query only the requested state and the signed-in user's personal places for
  the mobile place picker. A selected place in a hike edit now uses a direct
  lookup instead of scanning the national library. Saved-area discovery actions
  resolve that area's ID directly. Missing or inaccessible IDs no longer
  trigger a national scan.
- Remove the nonexistent owner column from mobile species-observation
  projections, allowing the narrow read to succeed without a retry.

## Validation and rollout

- Full Python suite: 551 passed, one dependency deprecation warning.
- `git diff --check`: passed.
- No SQL migration is required. The existing API contract and Android binary
  are unchanged.
- Cloud Build `deploy-main-to-cloud-run` succeeded for code commit `a1ea0eb`
  (build `46c116b4-df5e-43f5-a283-9db68225a8e8`). Cloud Run `/health`
  returned HTTP 200 with version `0.8.45`.
- Post-deployment Supabase egress measurement is pending new app traffic and
  the next hourly usage update.

## Debug-log triage

The retained Supabase API Gateway logs identified the query shapes and counts
above. No Android device debug-log bundle was supplied. The usage chart is
hourly and measures all PostgREST traffic, so the reduction must be confirmed
with new usage and request logs after deployment.
