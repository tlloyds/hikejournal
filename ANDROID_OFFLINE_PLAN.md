# HikeJournal Android offline plan

The Android app and Streamlit should remain two clients of the same Supabase database and R2 photo library. Offline support belongs in the Android client and its sync API; it does not require splitting the data model or replacing the web app.

## What works in Android v0.6

- Hikes can be recorded entirely offline with a foreground GPS service, live
  route, active timer, distance, and durable pause/resume segments.
- Recording state, accepted GPS points, distance, and timing checkpoints live in
  Room. Screen-off and task swipes keep recording; interrupted sessions recover
  safely without losing collected points.
- Ending a paused recording creates an `Untitled hike`, generates a segmented
  TCX route locally, and opens the existing edit-and-photo workflow. Hike and
  route operations wait on their parent creation before syncing.
- Previously loaded outings, journal details, species, review queue, publishing queue, and sightings remain readable without the companion.
- Creates, edits, archives, captions, deletions, photo selections, and species decisions enter a durable Room queue and overlay the UI immediately.
- Selected photos are copied into app-owned storage before the picker permission can disappear; original bytes retain EXIF date and coordinates.
- WorkManager syncs queued operations in order with network constraints, exponential retry, idempotent client IDs, and a visible attention state.
- The companion has a deployable HTTPS container, while the Mac launcher remains available for local development.
- MapLibre trail regions can be downloaded, listed, monitored, and deleted. Satellite packs require an explicitly configured provider style with offline rights.

## Target field workflow

1. Start, pause, resume, and end a hike with no signal.
2. Name the resulting outing, set its location, and capture photos and notes into app-owned storage while preserving original EXIF and coordinates.
3. Make species decisions against downloaded suggestions.
4. See every pending change in a small sync status surface.
5. When any network returns, sync automatically and idempotently into the same Supabase/R2 records used by Streamlit.

## Architecture

### Local-first data

- Add Room tables for outings, photo manifests, species decisions, and a durable `sync_operations` queue.
- Copy selected photos into app-owned storage immediately; never rely on a temporary Android picker URI.
- Give every local record a UUID and every mutation an idempotency key so retries cannot create duplicates.
- Track `local_only`, `queued`, `syncing`, `synced`, and `needs_attention` states.

### Anywhere connectivity

- Move the mutation endpoints from the Mac-only companion to a small authenticated cloud API.
- Preferred deployment: a Cloudflare Worker verifies Supabase user JWTs, issues or performs R2 uploads through an R2 binding, and writes owner-scoped metadata through Supabase.
- Keep the existing FastAPI companion for local development and compatibility.
- Keep all R2 and Supabase service credentials out of the APK. The app receives short-lived upload permission only.
- Streamlit continues reading and writing the same tables and bucket with no forked data.

### Sync behavior

- Use Android WorkManager with a network constraint and exponential retry.
- Sync metadata before media, then reconcile server IDs and refresh affected outings/species.
- Use last-write-wins for notes and captions initially; destructive conflicts and rejected uploads move to `needs_attention` instead of being silently discarded.
- Show a quiet global status such as `Offline · 8 changes saved` or `Synced just now`.

### Offline maps

- Use MapLibre OfflineManager to download a bounded field pack around an outing or selected map area.
- Let the user choose zoom/detail and show the estimated download size before saving.
- Street and satellite providers must explicitly permit offline tile storage. Production satellite packs should use a configured provider/account with offline rights rather than assuming viewed-tile cache is a permanent download.
- Store pack metadata locally and provide update/delete controls.

## Delivered slices

1. Durable offline outing/photo queue and visible sync status — delivered in v0.5.
2. Deployable authenticated cloud mutation API — delivered; account deployment and HTTPS URL remain environment setup.
3. Background R2 upload, retry, and attention handling — delivered in v0.5.
4. User-selected offline trail packs — delivered; satellite activation remains provider-account configuration.
5. Native offline hike recording and segmented route sync — delivered in v0.6.
