# HikeJournal anywhere companion

This directory packages the existing FastAPI companion as a small HTTPS service. It keeps Supabase, R2, and iNaturalist credentials on a trusted server while allowing Android to sync over cellular or any Wi-Fi.

## Deploy on Google Cloud Run (recommended)

The repository-root `Dockerfile` makes this API directly deployable from a
GitHub connection in Cloud Run:

1. In Google Cloud Console, open **Cloud Run** and choose **Deploy container**.
2. Select **Continuously deploy from a repository**, connect the `tlloyds/hikejournal`
   GitHub repository, and choose the `main` branch.
3. Use **Dockerfile** as the build type. Leave the root directory as the
   repository root, so Cloud Run uses `Dockerfile`.
4. Name the service `hikejournal-mobile`, select a nearby region, and allow
   unauthenticated invocations. The API itself requires the pairing key; this
   setting lets the installed app reach it over HTTPS.
5. Under **Variables & Secrets**, add the production values from `.env`:
   `MOBILE_API_TOKEN`, `MOBILE_OWNER_EMAIL`, `SUPABASE_URL`, `SUPABASE_KEY`,
   storage settings (`STORAGE_BACKEND` and either the R2 or Supabase values),
   and `INAT_ACCESS_TOKEN` if iNaturalist publishing is enabled. Do not commit
   or upload `.env`.
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
