# HikeJournal

HikeJournal is a private field journal for specific hikes on specific dates. It lets you create a hike, upload optimized photos, edit notes and captions, manually select photos for species review, and map both geotagged photos and confirmed species.

## Stack

- Streamlit for the app UI
- Supabase Postgres + Storage for persistence
- Pillow for EXIF handling and image optimization
- Requests for the iNaturalist integration
- Pydeck for the map view

## Setup

1. Create a Python environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your Supabase values.
4. Run the SQL in [sql/schema.sql](/Users/adl/Documents/Playground/hike-journal/sql/schema.sql).
5. Start the app:
   ```bash
   streamlit run app.py
   ```

For local use on this Mac, you can also just run:

```bash
./start_hikejournal.command
```

That script uses the repo's existing virtualenv and opens the app on port `8505`.

If you already have a running project from the earlier single-observation version, also run:

- [sql/multi_observations_migration.sql](/Users/adl/Documents/Playground/hike-journal/sql/multi_observations_migration.sql)
- [sql/auth_sharing_migration.sql](/Users/adl/Documents/Playground/hike-journal/sql/auth_sharing_migration.sql) for hike ownership, archive state, and collaborators

## Environment

Recommended Python:

- `Python 3.12` or `Python 3.13`

Required now:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_BUCKET` (defaults to `hike-journal`)
- `ADMIN_EMAILS` comma-separated list for people who should still see developer controls
- `ALLOWED_EMAILS` comma-separated list for people who can sign in; defaults to `ADMIN_EMAILS`
- `REQUIRE_GOOGLE_AUTH` set to `true` when you want Google sign-in enforced

Needed later for species scoring:

- `INAT_ACCESS_TOKEN`
- `INAT_BASE_URL` defaults to `https://api.inaturalist.org/v1`
- `INAT_CV_REQUEST_INTERVAL_SECONDS` defaults to `2.5` for slower image-ID requests

## Google Auth

The app is wired for Streamlit's native Google OIDC flow.

1. Copy [.streamlit/secrets.toml.example](/Users/adl/Documents/Playground/hike-journal/.streamlit/secrets.toml.example) to `.streamlit/secrets.toml`
2. Fill in your Google client id and client secret
3. Add this local callback URI in Google Cloud Console:
   - `http://localhost:8505/oauth2callback`
4. Add your production callback URI when you know the final domain:
   - `https://your-domain.com/oauth2callback`
5. Set `REQUIRE_GOOGLE_AUTH=true` in `.env` when you're ready to enforce sign-in

The app uses Google sign-in for the Streamlit session and stores hike ownership/collaboration metadata in Supabase.

## Notes

- The app stores optimized JPEGs only.
- HEIC uploads are supported and normalized into optimized JPEGs.
- Species scoring only runs on photos you manually select.
- The map includes a toggle for all geotagged photos vs confirmed species.
- Hikes can be archived and collaborators can be stored per hike after the auth/sharing migration is applied.
- Photos can now carry one primary observation plus additional secondary species.
- The iNaturalist client is wired for bearer-token auth. If your eventual access flow differs, the integration point is isolated in `hike_journal/services/inat.py`.
