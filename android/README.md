# HikeJournal for Android

This is the native phone companion to the Streamlit HikeJournal app. It shares
the current Supabase database and Cloudflare R2 photo library through the small
`mobile_api.py` service in the repository root.

## Use it tonight

1. For local use, keep the Mac and Android phone on the same Wi-Fi network.
2. Double-click `start_hikejournal_mobile.command` in the repository root and leave its Terminal window open. For cellular/anywhere use, deploy `deploy/mobile/Dockerfile` and paste its HTTPS address plus pairing key into Android settings.
3. Transfer `dist/HikeJournal-v0.6.1.apk` to the phone and open it.
4. Allow installation from the app you used to open the APK if Android asks.
5. HikeJournal should connect to `http://192.168.0.157:8506` automatically.

If the Mac receives a different local IP address, open the gear in HikeJournal
and replace the server address. The API always uses port `8506`.

Native hike recording does not need the companion or a network connection.
Pairing is needed when queued hikes, routes, and photos are ready to sync.

## Fixed in v0.6.1

- Live hike tracking opens on the satellite map by default
- Unsynced hikes can be deleted locally even when a recording contains no GPS
  points or the phone is offline
- Outing maps keep geotagged photos clickable alongside recorded routes and no
  longer fail for hikes with zero or one mapped photo

## Included in v0.6.0

- Start a hike directly from the Library `+` action instead of recording in
  MapMyRun and importing a TCX file
- Full-screen live route, active timer, distance, GPS accuracy, and current
  position while recording
- Persistent Android notification with a running chronometer, distance, and
  Pause/Resume controls; End reopens HikeJournal for confirmation
- Pause/resume segments that do not draw or measure a false straight line
  across the break
- Local-first GPS and timing checkpoints that survive screen-off, task swipes,
  and normal process recreation
- Finished recordings saved as `Untitled hike` with date, active duration,
  measured distance, local route, and—when enough GPS points were accepted—an
  automatically generated TCX upload
- Immediate name/location editing and the existing Journal photo workflow after
  ending a hike
- Offline recording and finalization, followed by dependency-ordered route and
  photo sync when connectivity returns

On the first recording, grant **Precise location** and notification access and
make sure phone Location is enabled. HikeJournal deliberately does not request
background-location permission; the visible foreground notification keeps a
started hike active while the screen is locked. Explicitly force-stopping the
app or revoking permission stops collection and restores the saved session in a
paused state the next time HikeJournal opens.

## Also included from v0.5

- iNaturalist can now be connected from Settings and an empty Species Review queue
- Publishing now starts iNaturalist authorization before attempting an unconnected post

- Everyday sightings default to Species Review during upload, with a clear opt-out
- The Library `+` action now starts either a full hike or an everyday sighting
- Hike creation searches and links entries to the imported location library
- Newly created hikes appear immediately, followed by a delayed companion refresh
- Photo uploads use clear `Upload photos` language and keep picker confirmation above system navigation
- Journal photos can be multi-selected and sent to Species Review after upload
- Synced photos automatically swap local file previews for durable remote URLs without reopening the hike
- One clear `Upload photos` action that opens local phone albums directly,
  preserving unredacted MediaStore access and album-wide selection for up to 500 files
- A fixed, high-contrast photo confirmation action that remains fully above
  Android gesture and navigation insets
- Android photo/video, selected-media, legacy storage, and media-location
  permissions requested together before HikeJournal reads embedded GPS
- Pre-upload GPS verification for every selected file, with missing-location warnings before anything is saved
- Embedded video location extraction for map-ready clips when the source file provides coordinates
- Hike-scoped native maps with imported route lines and just that outing's
  geotagged photos
- "View on map" from any geotagged photo, focused directly on its trail location
- Immediate journal-opening feedback plus cache-first hike details for faster archive navigation
- Observation-type filters across the native field guide, including plants,
  animals, birds, mammals, insects, and other major taxonomic groups
- Native Trail Medals nested in the Library, with 36 polished lifetime
  achievements across hikes, mileage, long outings, Field Quests, rare finds,
  the Field Guide, and taxon specialties
- Offline-safe, deterministic medal progress with an upcoming-medal summary and
  detailed criteria for every locked or earned medal
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
copied to `dist/HikeJournal-v<version>.apk` (currently
`dist/HikeJournal-v0.6.1.apk`).

Android code is split by responsibility:

- `data/Models.kt`: the client/server contract
- `data/HikeJournalApi.kt`: HTTP and multipart transport
- `data/HikeJournalRepository.kt`: caching and data operations
- `data/FieldSync.kt`: app-owned photos, local overlays, durable mutations, and background sync
- `data/local/OfflineDatabase.kt`: Room mutation queue plus durable recording sessions and GPS points
- `tracking/`: recording state, location filtering, foreground service, notification, and TCX generation
- `data/OfflineMapPacks.kt`: MapLibre offline region lifecycle
- `AppViewModel.kt`: application state and actions
- `ui/HikeJournalApp.kt`: native screens and interactions
- `ui/TrackingScreen.kt`: live recording map and controls
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
