# HikeJournal API location egress evidence

**Scope:** API only. Canonical version stays `0.8.45`; Android, iOS, Web, and
shared clients have no functional changes or new artifacts.

**Release tag:** `api-0.8.45-location-egress`.

## Before the change

- Supabase usage on 30 September 2026: 618.81 MB PostgREST egress (100% of
  that day's egress in the chart).
- Retained 24-hour request logs: approximately 4.7k `hike_locations` reads,
  360 `hike_location_tags` reads, 1.9k `photos` reads, 1.8k
  `species_observations` reads, and 51 `hike_route_imports` reads.
- A single location resolution requested offsets 0 through 12,000 in
  1,000-row pages (`select=*`). Repeated species-observation queries requested
  the absent `owner_user_id` column, returned HTTP 400, and retried broadly.

## Validation

- `uv run --with-requirements requirements.txt pytest -q`: 551 passed, one
  dependency deprecation warning.
- Focused tests assert that hike, place picker, and selected-place writes use
  scoped projections; canonical place aliases still resolve correctly.
- Cloud Build `deploy-main-to-cloud-run` succeeded for code commit `a1ea0eb`
  (build `46c116b4-df5e-43f5-a283-9db68225a8e8`). HTTPS `/health`
  returned HTTP 200 with `{"status":"ok","service":"hikejournal-mobile","version":"0.8.45"}`.
- Post-deployment usage verification is pending new app traffic and the next
  hourly Supabase egress update.
