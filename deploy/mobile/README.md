# HikeJournal anywhere companion

This directory packages the existing FastAPI companion as a small HTTPS service.
It keeps Supabase, R2, and iNaturalist credentials on a trusted server while
allowing Android to sync over cellular or any Wi-Fi.

This is a deployment procedure, not evidence that the current working tree,
schema migration, alerts, or restore process are live in production. Record
those results separately before treating a personal APK as release-ready.

## Deploy on Google Cloud Run (recommended)

The repository-root `Dockerfile` and `cloudbuild.json` make this API directly
deployable from a GitHub connection in Cloud Run:

1. Back up Supabase and record an R2/Supabase Storage object inventory. Apply
   `sql/mobile_jobs_migration.sql` to Supabase **before** deploying this API
   revision. The migration is additive; a hosted API intentionally refuses to
   start without its durable job table and lease/update functions.
2. In Google Cloud Console, open **Cloud Build → Triggers** and connect the
   `tlloyds/hikejournal` GitHub repository to the `main` branch.
3. Set the trigger region to `us-east1`, choose **Cloud Build configuration
   file (YAML or JSON)**, and enter `/cloudbuild.json` as the configuration
   location. Do not use the generated Dockerfile build: it only builds an
   image and cannot set the logging mode required by a user-managed service
   account.
4. Select a build service account that can write to the
   `cloud-run-source-deploy` Artifact Registry repository and deploy the
   `hikejournal-git` Cloud Run service.
5. The checked-in build configuration sends logs to Cloud Logging, builds and
   pushes the image in `us-east1`, and deploys it to the existing
   `hikejournal-git` service. This preserves that service's environment
   variables and public URL.
6. Under **Variables & Secrets**, add the production values from `.env`:
   `MOBILE_API_TOKEN`, `MOBILE_OWNER_EMAIL`, `MOBILE_OWNER_SUBJECT`,
   `SUPABASE_URL`, `SUPABASE_KEY`,
   storage settings (`STORAGE_BACKEND` and either the R2 or Supabase values),
   `SPECIES_DISCOVERY_ENABLED=true`, and
   `INAT_DISCOVERY_BASE_URL=https://api.inaturalist.org/v2`.
   Historical weather is enabled by default through Open-Meteo's free
   non-commercial endpoint. Set `WEATHER_ENRICHMENT_ENABLED=false` to disable
   it, or configure `OPEN_METEO_FORECAST_URL`, `OPEN_METEO_ARCHIVE_URL`, and
   `OPEN_METEO_API_KEY` for a paid/customer-compatible endpoint.
   `INAT_ACCESS_TOKEN` is only needed if iNaturalist publishing is enabled; the
   Nearby species list itself uses public iNaturalist data. To allow
   Android to connect iNaturalist itself, also add `INAT_OAUTH_CLIENT_ID`,
   `INAT_OAUTH_CLIENT_SECRET`, and `MOBILE_INAT_OAUTH_REDIRECT_URI`. Register
   that exact callback URL with the same iNaturalist OAuth application; it must
   end in `/v1/inat/oauth/callback`. Set `MOBILE_OWNER_SUBJECT` once to a stable,
   non-email identifier for the personal owner and do not change it after jobs
   exist. Hosted startup requires an explicit high-entropy pairing token of at
   least 32 characters plus both owner fields; readiness fails closed when they
   are absent or weak. Optional `MOBILE_JOB_RECOVERY_INTERVAL_SECONDS` (5-300 seconds) and
   `MOBILE_HEALTH_CACHE_SECONDS` (1-60 seconds) tune the in-process recovery scan
   and readiness cache. Do not commit or upload `.env`.
7. Set memory to at least **1 GiB** to leave room for photo processing, then
   deploy. Verify `/health/live` returns an `ok` response and `/health/ready`
   returns HTTP 200 with `configuration`, `database`, `storage`, and `job_store`
   all `ok`.

Copy that HTTPS URL and the `MOBILE_API_TOKEN` into Android's **Companion
connection** settings. With the documented repository-wide trigger, future
pushes to `main` can redeploy the API even for a web-only change. Path-filtered
mobile deployment triggers remain Track A work.

The personal Android build separately requires an owner-supplied HTTPS
`MOBILE_TRAIL_MAP_STYLE_URL`. The debug MapLibre demo style is not an accepted
production provider; provider licensing, quota, attribution, privacy, and
offline-storage rights remain unresolved until the owner selects one. Satellite
views separately use Esri World Imagery, whose attribution, quota, privacy, and
permitted-use terms also require approval.

The Streamlit web interface is a separate service. This deployment only moves
the Android companion API off the local Mac.

The container installs `requirements-mobile.txt`, not the Streamlit dependency
set. This is a deployment boundary, not a data split: mobile and web still share
the Supabase schema, object storage, and domain/service modules.

## Operational endpoints

- `GET /health` preserves the legacy APK/platform response.
- `GET /health/live` proves only that the API process can answer. Container
  health checks use this route so a dependency outage does not cause a restart
  loop.
- `GET /health/ready` checks database, storage, and durable job persistence and
  returns HTTP 503 when any dependency is unavailable. Probes run concurrently
  with bounded timeouts and their result is briefly cached. The route never
  returns raw exception details.
- `GET /v1/operations/health` and `GET /v1/operations/metrics` require the
  pairing key. Metrics include bounded route-template request counts/latency and
  non-identifying queue depth, retry, oldest-active, and needs-attention data.

Request metrics are in-process and reset on each instance/revision. Cloud
Logging or the selected host must remain the durable, cross-instance source for
latency/error alerts. Job metrics are derived from durable rows, capped at 1,000
sampled jobs with an explicit truncation flag. See
`docs/TRACK_A_OPERATIONS_RUNBOOK.md` for alert and restore-drill gates.
Uvicorn's raw access log is disabled so OAuth codes, state, coordinates, and
search terms are not copied into container logs. The hosting platform may still
record request URLs; configure and verify query-string redaction/exclusion plus
restricted log access and retention before production use.
No dashboard, alert destination, backup schedule, or successful restore drill is
created merely by deploying these endpoints.

## Other hosts

1. Create a private web service from `deploy/mobile/Dockerfile`, or use the included Render blueprint.
2. Add the environment variables listed in `render.yaml`. Use a new high-entropy
   `MOBILE_API_TOKEN` of at least 32 characters; do not reuse a Supabase or R2
   secret. Configure both owner fields and record a rotation/re-pairing plan.
3. Confirm `https://your-service.example/health` returns
   `{"status":"ok","service":"hikejournal-mobile","version":"<VERSION>"}`.
4. In Android, open **Settings → Companion connection**, paste the HTTPS service address and its pairing key, then reconnect.

The container runs as an unprivileged user, contains no `.env` file, exposes only the API port, and supports platform health checks. The local Mac launcher remains useful for development.

## Production boundary

The pairing key is appropriate for this single-owner build. Before distributing HikeJournal to other people, replace it with Supabase Auth JWT verification and owner-scoped RLS. Do not publish a multi-user build while the legacy permissive database policies remain active.

Job execution still runs inside the API process. When the Supabase migration is
applied and the durable store is required, database records, request
fingerprints, fenced lease updates, bounded retries, periodic in-process scans,
and status-poll redispatch are available. Local development can fall back to an
in-memory store and is not restart-durable. Cloud Run can throttle background
CPU after a request, and there is no external durable dispatcher or independent
lease heartbeat. A later Track A phase should move dispatch to Cloud Tasks or a
dedicated worker.

Interrupted iNaturalist creates stop for review rather than being blindly
replayed. That is a safer failure state, not an exactly-once guarantee: the API
cannot atomically learn whether the remote create succeeded when its response is
lost. Resolve and failure-test that boundary before claiming the A2 publication
exit gate.
