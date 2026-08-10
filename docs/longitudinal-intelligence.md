# Longitudinal natural-history layer

HikeJournal 0.7 adds a shared `place × species × season × time` domain layer. The Android app remains the primary field surface; the Streamlit Places view provides the larger-screen analysis.

## What is live

- Place Profiles summarize visits, mileage, confirmed observations, distinct taxa, personal seasonality, and cumulative species discovery. Visit history includes the actual hike cover, and life groups expand into complete species lists with encounter counts. Archived hikes are omitted.
- Species detail includes a 12-month band derived only from the owner’s dated confirmed observations.
- Field Briefing deterministically combines current Nearby/iNaturalist reports with the owner’s collection, same-month returns, place history, active Field Quest targets, and rediscovery age. Reference photos appear with each expected find, and any taxon can open the same public-sightings map used by Nearby. Reasons are returned with every recommendation. iNaturalist frequency is never described as encounter probability.
- Field Marks can be created during native GPS recording as Wildlife, Plant, Trail condition, Water, Campsite, Hazard, or Note. They are written to Room in the same transaction as their pending sync operation, survive process death, wait for an offline-created hike to sync, and appear on the live and final route maps.
- Hike Comparison shows outing facts and confirmed species recorded on both, only the first outing, or only the second.
- Confirmed observations expose understandable confidence, provenance, optional plant phenophases, and append-only identification history. Android edits use the durable mutation queue.
- Streamlit’s **Places over time** view provides seasonal, cumulative-biodiversity, visit-table, and two-hike comparison analysis.
- Completed route uploads now trigger best-effort historical weather enrichment. Android Journal can retry or refresh it, and Hike Comparison displays it when present. Recording and route persistence never depend on the provider.

## Persistence

Run [`sql/longitudinal_intelligence_migration.sql`](../sql/longitudinal_intelligence_migration.sql) once in the Supabase SQL editor before using Field Marks or editing natural-history metadata. It is additive and preserves existing records.

The migration adds:

- current observation fields: `observed_on`, `occurrence_precision`, `identification_confidence`, and `identification_provenance`;
- append-only `identification_events` with a safe legacy backfill;
- normalized multi-value `observation_annotations`;
- owner-ready `field_marks`;
- provider-neutral `hike_weather_snapshots` storage;
- an atomic `set_observation_natural_history` RPC;
- indexes, forced RLS, and service-role-only access.

Android Room schema 3 adds `field_marks` plus `MIGRATION_2_3`. The local row and pending operation are committed together. A successful retry marks the row synced; a permanent error remains visible through the existing sync-attention experience.

## API contracts

- `GET /v1/places/{location_id}/profile`
- `GET /v1/field-briefing?location_id=…&date=YYYY-MM-DD`
- `GET /v1/hikes/{hike_id}/comparison?other_hike_id=…`
- `POST /v1/hikes/{hike_id}/field-marks`
- `PUT /v1/observations/{observation_id}/natural-history`
- `POST /v1/hikes/{hike_id}/weather?force=false`

Hike detail responses now include canonical location identity, Field Marks, and an optional weather snapshot. Species detail responses include `seasonal_history`. Photo observation labels include provenance/history only when an observation ID exists, preserving compatibility with older clients and test fixtures.

## Historical weather

The default provider is Open-Meteo because its non-commercial API requires no key, provides a free 10,000-call daily allowance, and covers the required hourly archive variables. Its free service has no uptime guarantee. Open-Meteo data are attributed in the Android Journal under CC BY 4.0.

For a recorded route, `route-centroid-interval-v1` averages the track coordinates into a documented representative anchor and selects only hourly samples overlapping the actual route start/duration interval. Hikes without a usable route can fall back to a saved-place coordinate and the full hike date in Open-Meteo’s resolved local timezone. Stored snapshots retain provider/dataset, algorithm version, anchor, UTC interval, aggregation basis, selected hourly samples, and attribution.

Configuration is optional for personal use:

- `WEATHER_ENRICHMENT_ENABLED=true`
- `OPEN_METEO_FORECAST_URL=https://api.open-meteo.com/v1/forecast`
- `OPEN_METEO_ARCHIVE_URL=https://archive-api.open-meteo.com/v1/archive`
- `WEATHER_REQUEST_TIMEOUT_SECONDS=20`

For commercial use, configure the paid customer endpoints and `OPEN_METEO_API_KEY`; do not rely on the free non-commercial endpoint.

## Known limits and next work

- Voice notes are not shipped yet. Current photo media uses public delivery URLs, which is not an acceptable default for private field audio. Voice needs app-owned recording, a private storage bucket or signed-download path, upload retry, interruption tests, and graceful permission handling.
- Route overlap is intentionally absent until a documented geospatial buffer/intersection algorithm can replace fake precision.
- The first Field Briefing requires service; Android then retains the last successful response in its normal disk cache.
- Field Marks are namespaced consistently with the current Room database. Track A’s future per-environment/account database namespace remains the authoritative follow-up for every offline table, including Field Marks.
