# HikeJournal Android 0.8.49 photo recommendation confidence release evidence

**Release scope:** Android only. iOS, API, Web, and shared code have **No
functional changes**.

**Release tag:** `android-v0.8.49-photo-recommendation-confidence`.

**Base commit:** `82b75be5c0fc628767767ae70573f6ae4a1810dc`.

## Cause and correction

`DirectPhotoReviewDialog` rendered common and scientific names but omitted the
candidate's confidence. The API response parser already populated that field,
and the regular Species Review candidate row already displayed it.

The single-photo dialog now calls the existing `reviewConfidenceLabel` for
each candidate and renders its result beneath the species names. This gives
the top suggestion and alternatives the same normalized percentage display
as Species Review. Missing/non-finite values follow the existing omission
policy. The source change adds one import and three lines in the dialog.

The iOS journal photo `recommendationView` already renders
`reviewConfidenceLabel(candidate.confidence)` for each candidate. No iOS
change or artifact was needed.

## Versions and platform impact

- Canonical `VERSION` / Android `versionName`: **0.8.49**, unchanged.
- Android `versionCode`: **186**, previously **185**.
- iOS: **No functional changes**; version/build metadata unchanged; no build,
  archive, or upload.
- API: **No functional changes**; version/contracts unchanged; no deployment.
- Web: **No functional changes**; no Web artifacts.
- Shared code: **No functional changes**.

## Validation

- Both Android unit variants passed: **183 tests across 50 suites per
  variant**, zero failures/errors/skips. Existing confidence tests cover
  normalization, fractional/percentage inputs, display, and missing or invalid
  values.
- Release lint passed with **zero errors, 61 existing warnings, and one hint**;
  these counts match build 185.
- `HIKEJOURNAL_ANDROID_BUILD_DIR="$HOME/.cache/hikejournal-android-confidence-186"
  ./build_android.command personal` passed. The isolated build cache prevents
  this release from replacing another checkout's build outputs.
- Canonical APK release verification: **PASS, no findings**; package
  `com.hikejournal.app`, version **0.8.49**, build **186**, target SDK **36**.
- Strict AAB JAR-signature verification and expected permanent signer checks
  passed before canonical APK/AAB promotion.
- Explicit `apksigner verify --verbose --print-certs` checks passed for API
  26–27 (previous signer, v2) and API 28–36 (permanent signer, v3).
- The previous APK was downloaded from GitHub release
  `android-v0.8.49-map-loading`. Its SHA-256 matched the published value
  `3ac8ab0ee5559b593da2f8a45d61bca8521f9a37c9500751cbd321bf65443569`.
- Android 15 / API 35 accepted the signed in-place upgrade from build **185**
  to **186**, preserving app ID **10227** and the first-install timestamp
  **2026-10-23 08:53:40**. `MainActivity` cold-started successfully and remained
  resumed. The post-launch crash log contained no AndroidRuntime exception.
- `git diff --check` passed.
- No authenticated recommendation session was available on the emulator.
  The single-photo dialog wiring and equivalent iOS implementation were
  inspected in source; live iNaturalist and physical-device UI were not tested.

## Artifacts

| Artifact | Bytes | SHA-256 | Distribution |
| --- | --- | --- | --- |
| `dist/HikeJournal-v0.8.49.apk` | 63,444,928 | `380c46b92f5f5ecaef803f0508a734e589da4400238502a8e1a73a398fe0cfd7` | Verified signed release APK; GitHub release attachment |
| `dist/HikeJournal-v0.8.49.aab` | 30,529,855 | `2c45fc1d19e003ab6cebdc38ebaa5050f022748b6885c17e6210309247c80a9d` | Verified signed AAB; retained locally |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage

No device log bundle was supplied and no production logging was added. The
post-upgrade emulator crash log contained no fatal exception. Existing location
API and test `Locale` deprecation warnings remain; lint counts are unchanged.
API 26–27 signing verification retains its expected warning about the newer v3
signature scheme.

## Workspace isolation

The release was prepared in a managed worktree from current `origin/main`.
Unrelated edits and untracked assets in the original iCloud checkout were
preserved and excluded from the release commit.
