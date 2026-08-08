# HikeJournal

HikeJournal is a private field journal for specific hikes on specific dates. It lets you create a hike, upload optimized photos, edit notes and captions, manually select photos for species review, and map both geotagged photos and confirmed species.

## Delivery roadmaps

The active delivery plan is split into three compatibility-gated tracks:

- [Track A: personal release hardening](docs/roadmaps/TRACK_A_PERSONAL_RELEASE.md)
- [Track A implementation status](docs/roadmaps/TRACK_A_PROGRESS.md)
- [Track B: multi-user product](docs/roadmaps/TRACK_B_MULTI_USER.md)
- [Track C: Google Play publication](docs/roadmaps/TRACK_C_GOOGLE_PLAY.md)
- [Track A operations and restore runbook](docs/TRACK_A_OPERATIONS_RUNBOOK.md)
- [Android artifact verification](docs/ANDROID_ARTIFACT_VERIFICATION.md)

The [roadmap overview](docs/roadmaps/README.md) defines the shared no-regression
invariant, sequencing, evidence requirements, and webapp boundaries.

## Stack

- Streamlit for the app UI
- Supabase Postgres + Storage for persistence
- Pillow for EXIF handling and image optimization
- Requests for the iNaturalist integration
- MapLibre GL JS for the interactive map, with PostGIS viewport RPCs

## Setup

1. Create a Python environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your Supabase values.
4. Run the SQL in [sql/schema.sql](sql/schema.sql).
5. Run `sql/scalable_maps_migration.sql` to add PostGIS indexes and viewport map RPCs.
6. Run `sql/species_discovery_migration.sql` to add Nearby discovery snapshots
   and stable Field Quests.
7. Start the app:
   ```bash
   streamlit run app.py
   ```

For local use on this Mac, you can also just run:

```bash
./start_hikejournal.command
```

That script uses the repo's existing virtualenv and opens the app on port `8505`.

## Android

The native Android app can now record a hike directly—with an offline GPS route,
active timer, distance, pause/resume notification, and an `Untitled hike` handoff
to the existing Journal workflow. Build it with `./build_android.command`; the
versioned APK is written to `dist/`. The shared release version lives in
`VERSION` and is used by both Android and the mobile API. Installation, first-recording permissions,
and companion pairing are documented in [android/README.md](android/README.md).

If you already have a running project from the earlier single-observation version, also run:

- [sql/multi_observations_migration.sql](sql/multi_observations_migration.sql)
- [sql/auth_sharing_migration.sql](sql/auth_sharing_migration.sql) for hike ownership, archive state, and collaborators
- `sql/species_discovery_migration.sql` for species-level collection credit,
  the 24-hour shared iNaturalist cache, and owner-scoped Field Quests

## Environment

Recommended Python:

- `Python 3.12` or `Python 3.13`

Required now:

- `SUPABASE_URL`
- `SUPABASE_KEY` — a server-only Supabase secret/service-role key; never use a
  publishable or legacy `anon` key here, and never expose this value to a
  browser or Android build
- `SUPABASE_BUCKET` (defaults to `hike-journal`)
- `ADMIN_EMAILS` comma-separated list for people who should still see developer controls
- `ALLOWED_EMAILS` comma-separated list for people who can sign in; defaults to `ADMIN_EMAILS`
- `REQUIRE_GOOGLE_AUTH` set to `true` when you want Google sign-in enforced

Needed later for species scoring:

- `INAT_ACCESS_TOKEN`
- `INAT_BASE_URL` defaults to `https://api.inaturalist.org/v1`
- `INAT_DISCOVERY_BASE_URL` defaults to `https://api.inaturalist.org/v2`
- `INAT_CV_REQUEST_INTERVAL_SECONDS` defaults to `2.5` for slower image-ID requests
- `SPECIES_DISCOVERY_ENABLED` defaults to `true`; set it to `false` to hide
  Nearby and Field Quests during a rollout

## Google Auth

The app is wired for Streamlit's native Google OIDC flow.

1. Copy [.streamlit/secrets.toml.example](.streamlit/secrets.toml.example) to `.streamlit/secrets.toml`
2. Fill in your Google client id and client secret
3. Add this local callback URI in Google Cloud Console:
   - `http://localhost:8505/oauth2callback`
4. Add your production callback URI when you know the final domain:
   - `https://your-domain.com/oauth2callback`
5. Set `REQUIRE_GOOGLE_AUTH=true` in `.env` when you're ready to enforce sign-in

The app uses Google sign-in for the Streamlit session and stores hike ownership/collaboration metadata in Supabase.

## Database security

The app accesses Supabase only from the trusted Streamlit/mobile API server.
Run `sql/secure_rls_migration.sql` in the Supabase SQL Editor for an existing
project. It enables and forces RLS, removes permissive policies, revokes direct
access from `anon` and `authenticated`, and leaves access to the server's
secret/service-role key. The photo bucket remains publicly readable because
the UI uses public image URLs, but only the trusted server can upload, update,
or delete its objects.

Supabase may separately report `public.spatial_ref_sys` when PostGIS is
installed. That system lookup table is owned by Supabase's managed
`supabase_admin` role and cannot be altered by a project SQL migration. It
contains public coordinate-reference definitions rather than HikeJournal data;
the Supabase linter is tracking it as a managed PostGIS false positive.

## Notes

- The app stores optimized JPEGs only.
- HEIC uploads are supported and normalized into optimized JPEGs.
- Species scoring only runs on photos you manually select.
- The map includes a toggle for all geotagged photos vs confirmed species.
- Hikes can be archived and collaborators can be stored per hike after the auth/sharing migration is applied.
- Photos can now carry one primary observation plus additional secondary species.
- Species Log and Android now include Collection, seasonally ranked Nearby
  reports, and five-target Field Quests. Each quest keeps its original
  50-species nearby list as an editable candidate pool, while its main view and
  progress stay focused on the five chosen species.
- Unseen reference specimens can be opened in color, collected targets reveal
  the user's photograph, and quests can be renamed, linked, archived, restored,
  or permanently deleted without affecting observations.
- Nearby language describes iNaturalist reporting frequency, not encounter
  probability. Discovery queries are cached for 24 hours and do not require an
  iNaturalist account.
- The iNaturalist client is wired for bearer-token auth. If your eventual access flow differs, the integration point is isolated in `hike_journal/services/inat.py`.
