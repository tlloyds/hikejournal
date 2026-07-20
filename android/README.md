# HikeJournal for Android

This is the native phone companion to the Streamlit HikeJournal app. It shares
the current Supabase database and Cloudflare R2 photo library through the small
`mobile_api.py` service in the repository root.

## Use it tonight

1. For local use, keep the Mac and Android phone on the same Wi-Fi network.
2. Double-click `start_hikejournal_mobile.command` in the repository root and leave its Terminal window open. For cellular/anywhere use, deploy `deploy/mobile/Dockerfile` and paste its HTTPS address plus pairing key into Android settings.
3. Transfer `dist/HikeJournal.apk` to the phone and open it.
4. Allow installation from the app you used to open the APK if Android asks.
5. HikeJournal should connect to `http://192.168.0.157:8506` automatically.

If the Mac receives a different local IP address, open the gear in HikeJournal
and replace the server address. The API always uses port `8506`.

## Included in v0.5.2

- Native Library with search, current/archive browsing, and cached offline reads
- Journal detail with notes, metadata, photos, and species labels
- Create and edit hikes with durable offline drafts
- App-owned photo storage, preserved EXIF/GPS, and background R2 upload retries
- Optional handoff to the Streamlit species-review queue
- Full-screen photo viewing, caption editing, and deletion
- Personal field guide with 400+ confirmed species, search, encounter counts,
  image-led species records, and Journal handoffs
- Searchable hike filters across the species field guide and iNaturalist publishing queue
- Native MapLibre sightings map with confirmed-species filtering, photo-backed
  point inspectors, and Journal handoffs
- Trail/satellite map switching with imagery attribution
- Photo-first species review with alternate suggestions, confirm, reject, and skip
- Existing journal photos can be sent to species review from the full-screen viewer, online or offline
- Native iNaturalist publishing with grouped same-species photos, notes, tags,
  geoprivacy, captive/cultivated state, explicit public confirmation, and finished-record handoff
- Cached review, species, map, and journal reads plus queued hike/photo/caption/review writes when offline
- Visible sync status with retry and attention states, backed by Room and WorkManager
- User-managed MapLibre trail packs; satellite pack downloads activate only when a licensed offline style is configured
- Configurable local or hosted companion address and pairing key
- Streamlit deep links for review, maps, and publishing

The app intentionally keeps Supabase and R2 credentials out of the APK.
The paired companion token only authorizes this narrow local API.

## Iterate

Double-click `build_android.command` in the repository root. The finished APK is
copied to `dist/HikeJournal.apk`.

Android code is split by responsibility:

- `data/Models.kt`: the client/server contract
- `data/HikeJournalApi.kt`: HTTP and multipart transport
- `data/HikeJournalRepository.kt`: caching and data operations
- `data/FieldSync.kt`: app-owned photos, local overlays, durable mutations, and background sync
- `data/local/OfflineDatabase.kt`: Room mutation queue
- `data/OfflineMapPacks.kt`: MapLibre offline region lifecycle
- `AppViewModel.kt`: application state and actions
- `ui/HikeJournalApp.kt`: native screens and interactions
- `ui/SpeciesScreens.kt`: field-guide index and species encounter records
- `ui/HikeFilter.kt`: shared searchable outing scope selector
- `ui/SpeciesReviewScreen.kt`: native species decision queue
- `ui/PublishingScreen.kt`: confirmed-observation publishing workspace
- `ui/SightingsMapScreen.kt`: MapLibre sightings map and encounter inspector
- `ui/theme/Theme.kt`: typography and visual system

The same FastAPI companion runs locally or as the hosted container in
`../deploy/mobile`. Android can switch endpoints without a rebuild.

The durable offline-write and anywhere-sync design lives in
`../ANDROID_OFFLINE_PLAN.md`.
