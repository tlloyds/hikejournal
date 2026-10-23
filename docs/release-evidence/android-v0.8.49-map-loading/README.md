# HikeJournal Android 0.8.49 map-loading release evidence

**Release scope:** Android only. iOS, API, Web, and shared code have **No
functional changes**.

**Release tag:** `android-v0.8.49-map-loading`.

## Cause and correction

The viewport photo refactor in `8d2ccc4` assigned `initialBounds` and
`waitForInitialBounds` to a remembered map controller outside
`AndroidView.update`. The subsequent camera-focus fix in `41e0107` correctly
allowed late summary bounds to replace a fallback fit, but still depended on
that native update being called.

When the summary arrived after the map style loaded and routes/photos were
unchanged, Compose could skip the native update lambda because none of its
captured inputs changed. Merely assigning fields on the remembered controller
did not invalidate it. The map stayed unfocused, and its initial viewport
photo request was not delivered. Toggling the empty photo layer could not
repair that missing camera update. The later releases did not revert the map
code: this was a latent timing-dependent integration bug.

Both summary inputs are now captured and assigned inside `AndroidView.update`.
A bounds-only or loading-only change therefore updates MapLibre and runs the
existing fit/viewport logic. Bounded photo requests, clustering, route caching,
media permissions, and GPS-safe phone-original browsing are retained.

## Versions and platform impact

- Canonical `VERSION` / Android `versionName`: **0.8.49**, unchanged.
- Android `versionCode`: **185** (previously 184).
- iOS: **No functional changes**; version/build metadata unchanged; no build,
  archive, or upload.
- API: **No functional changes**; version/contracts unchanged; no manual API
  deployment required.
- Web: **No functional changes**; no Web artifacts.
- Shared code: **No functional changes**.

## Validation

- Added a real MapLibre/Compose Android instrumentation regression test before
  changing production code. On the previous code, late summary bounds with
  otherwise unchanged empty route/photo lists timed out after 10 seconds:
  there was no focused viewport callback. The same test passed after the fix.
  The previous JVM bounds-policy test did not exercise this native update path.
- Android 15 / API 35 instrumentation: **3 passed**, zero failures/errors/skips.
  Coverage includes late summary arrival, rendering a returned photo marker,
  hiding and restoring that marker, subsequent camera/viewport callbacks,
  loading completion with unchanged cached routes, and late summary bounds
  replacing an earlier cached route fit.
- `:app:testDebugUnitTest`: **183 passed**, zero failures/errors/skips.
- `:app:testReleaseUnitTest`: **183 passed**, zero failures/errors/skips.
- `:app:lintRelease`: **passed**, zero errors, 61 existing warnings and one hint.
- `./build_android.command personal`: **passed**; canonical signed APK and AAB
  were promoted only after verification.
- APK release verifier: **PASS, no findings**; package `com.hikejournal.app`,
  version `0.8.49`, build `185`, target SDK `36`, expected permanent signer.
- Strict AAB signature verification and permanent signer identity: **passed**
  in the personal build's promotion gates.
- APK signing-lineage verification: **passed** for API 26–27 (previous signer,
  v2) and API 28–36 (permanent signer, v3).
- Android 15 / API 35 accepted an **in-place signed upgrade from build 184 to
  185**. Package app ID `10227` and first-install timestamp were preserved.
  Version `0.8.49` / build `185` launched successfully and remained the resumed
  activity. Post-upgrade AndroidRuntime logging contained no fatal exception.
- Read-only production checks: `/health` returned version `0.8.49`; OpenAPI
  includes both map endpoints. An administrative aggregate database RPC check
  returned **6,654 geotagged photos** and matching bounds; a broad viewport
  returned **4 clusters covering all 6,654 matches**. No production writes or
  database migration were needed.
- `git diff --check`: **passed**.

## Artifacts

| Artifact | Bytes | SHA-256 | Distribution |
| --- | --- | --- | --- |
| `dist/HikeJournal-v0.8.49.apk` | 63,444,928 | `3ac8ab0ee5559b593da2f8a45d61bca8521f9a37c9500751cbd321bf65443569` | Verified signed release APK; GitHub release attachment |
| `dist/HikeJournal-v0.8.49.aab` | 30,529,862 | `4b1df61e44d61776bfa900d736a36cce288efc7809f55c9a60fa66ba61ed0a1e` | Verified signed AAB; retained locally |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage and limits

The baseline instrumentation failure was the expected map-startup timeout; it
was eliminated by the production fix. An initial test installation encountered
a signed-release/debug certificate mismatch on the emulator; the subsequent
instrumentation run installed successfully. No production logging was added.
Release lint's warning/hint count is unchanged. The API 26–27 signature check
retains the expected warning about the newer v3 signature scheme. No
physical-device log bundle or authenticated phone session was supplied; map
integration and signed-upgrade validation used the Android emulator.
