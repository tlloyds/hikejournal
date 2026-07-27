# HikeJournal anywhere companion

This directory packages the existing FastAPI companion as a small HTTPS service. It keeps Supabase, R2, and iNaturalist credentials on a trusted server while allowing Android to sync over cellular or any Wi-Fi.

## Deploy on Google Cloud Run (recommended)

The repository-root `Dockerfile` and `cloudbuild.json` make this API directly
deployable from a GitHub connection in Cloud Run:

1. In Google Cloud Console, open **Cloud Build → Triggers** and connect the
   `tlloyds/hikejournal` GitHub repository to the `main` branch.
2. Set the trigger region to `us-east1`, choose **Cloud Build configuration
   file (YAML or JSON)**, and enter `/cloudbuild.json` as the configuration
   location. Do not use the generated Dockerfile build: it only builds an
   image and cannot set the logging mode required by a user-managed service
   account.
3. Select a build service account that can write to the
   `cloud-run-source-deploy` Artifact Registry repository and deploy the
   `hikejournal-git` Cloud Run service.
4. The checked-in build configuration sends logs to Cloud Logging, builds and
   pushes the image in `us-east1`, and deploys it to the existing
   `hikejournal-git` service. This preserves that service's environment
   variables and public URL.
5. Under **Variables & Secrets**, add the production values from `.env`:
   `MOBILE_API_TOKEN`, `MOBILE_OWNER_EMAIL`, `SUPABASE_URL`, `SUPABASE_KEY`,
   storage settings (`STORAGE_BACKEND` and either the R2 or Supabase values),
   `SPECIES_DISCOVERY_ENABLED=true`, and
   `INAT_DISCOVERY_BASE_URL=https://api.inaturalist.org/v2`.
   `INAT_ACCESS_TOKEN` is only needed if iNaturalist publishing is enabled; the
   Nearby species list itself uses public iNaturalist data. To allow
   Android to connect iNaturalist itself, also add `INAT_OAUTH_CLIENT_ID`,
   `INAT_OAUTH_CLIENT_SECRET`, and `MOBILE_INAT_OAUTH_REDIRECT_URI`. Register
   that exact callback URL with the same iNaturalist OAuth application; it must
   end in `/v1/inat/oauth/callback`. Do not commit or upload `.env`.
6. Set memory to at least **1 GiB** to leave room for photo processing, then
   deploy. Verify the generated URL ends in `/health` and returns an `ok`
   response.

Copy that HTTPS URL and the `MOBILE_API_TOKEN` into Android's **Companion
connection** settings. Future pushes to `main` will redeploy the API.

The Streamlit web interface is a separate service. This deployment only moves
the Android companion API off the local Mac.

## Other hosts

1. Create a private web service from `deploy/mobile/Dockerfile`, or use the included Render blueprint.
2. Add the environment variables listed in `render.yaml`. Use a new random `MOBILE_API_TOKEN`; do not reuse a Supabase or R2 secret.
3. Confirm `https://your-service.example/health` returns `{"status":"ok","service":"hikejournal-mobile"}`.
4. In Android, open **Settings → Companion connection**, paste the HTTPS service address and its pairing key, then reconnect.

The container runs as an unprivileged user, contains no `.env` file, exposes only the API port, and supports platform health checks. The local Mac launcher remains useful for development.

## Production boundary

The pairing key is appropriate for this single-owner build. Before distributing HikeJournal to other people, replace it with Supabase Auth JWT verification and owner-scoped RLS. Do not publish a multi-user build while the legacy permissive database policies remain active.
