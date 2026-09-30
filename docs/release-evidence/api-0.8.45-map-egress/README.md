# HikeJournal API map egress release evidence

**Release scope:** API only. Canonical `VERSION` remains `0.8.45`.

**Release tag:** `api-0.8.45-map-egress`.

## Changes

- Added the owner-scoped `mobile_map_sightings` function and switched the
  Android map API to the compact result. The map still receives all of the
  current account's geotagged hike and standalone photos with their primary
  confirmed species names.
- Scoped map route listing to the user's visible hike IDs and limited returned
  columns to route GeoJSON. Replay reads return the full track and metadata
  without also transferring indexed PostGIS geometry.
- No Android, iOS, or Web behavior changes; no mobile artifacts were built.

## Validation and deployment

- `tests/test_mobile_api.py` and `tests/test_repositories.py`: 99 passed, one
  dependency deprecation warning.
- Supabase migration `sql/mobile_map_egress_migration.sql`: applied in the
  production SQL editor; it returned `Success. No rows returned` and requested
  a PostgREST schema reload.
- Cloud Build trigger `deploy-main-to-cloud-run` succeeded for commit `361ccae`
  (build `c19bc68e-0358-4c41-981c-48d4831a3158`). HTTPS `/health` returned
  HTTP 200 with `{"status":"ok","service":"hikejournal-mobile","version":"0.8.45"}`.
- No new runtime log bundle was supplied. Historic PostgREST logs did not
  identify which request accounted for the prior daily spike; egress savings
  remain to be measured from usage after deployment.

## Compatibility

The API retains a legacy map-query fallback while the additive function is
being installed. The Android request contract and artifact versions remain
unchanged.
