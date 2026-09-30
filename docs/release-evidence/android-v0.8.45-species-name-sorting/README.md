# HikeJournal Android 0.8.45 species-name sorting release evidence

**Release scope:** Android only. iOS, API, Web, and shared code have no
functional changes; no unrelated artifacts are shipped.

**Release tag:** `android-v0.8.45-species-name-sorting` (platform-qualified
because canonical `VERSION` remains `0.8.45`).

## Changes

- Make the existing common-name A–Z choice explicit in the Species tab sort
  sheet.
- Add scientific-name A–Z sorting, with common name and record key as stable
  tie-breaks.
- Leave encounter-count and most-recent sorting unchanged.

## Version and artifacts

- Canonical `VERSION`: `0.8.45` (unchanged).
- Android `versionName`: `0.8.45` (unchanged).
- Android `versionCode`: `177` (previous: `176`).
- iOS version/build metadata: unchanged; no iOS archive or upload.
- API version/contracts: unchanged; no API deployment.
- Web: no functional changes; no Web artifacts.
- Shared code: no functional changes.

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.45.apk` | `e49332a387cfc4ac4c1f8906947bc16d1d57783bf77e401ae349af11af1995ec` | Signed canonical release APK; permanent signer verified; attach to GitHub release |
| `dist/HikeJournal-v0.8.45.aab` | `7e357a1f7e5b2a5282ea1daa37b9b801f2f0630a7cb6957b99a83c2c42394d4d` | Signed release AAB; strict signature verified; not attached |

Expected permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Validation results

- `./build_android.command personal`: passed, including release lint,
  production signing, APK/AAB packaging, canonical artifact promotion, release
  APK verifier, strict AAB signature verification, and expected signer check.
- Release APK verifier: passed with no findings; package
  `com.hikejournal.app`, version name `0.8.45`, version code `177`.
- Signing lineage was applied. Android 15 (API 35) installed the published
  version-code `176` APK, accepted the in-place upgrade to `177`, and launched
  the app without an Android runtime error.
- `git diff --check`: passed. Android unit tests were not run.

## Debug-log triage

No diagnostic logging was added. Compilation reported the existing
`LocationManager.requestSingleUpdate` deprecation at
`android/app/src/main/java/com/hikejournal/app/ui/SpeciesScreens.kt:1617`; the
line is outside this change. The emulator's Android runtime error log was
empty after upgrade and launch. No physical-device log bundle was available.

## Deployment

The signed APK is published as an asset on
`android-v0.8.45-species-name-sorting`. No server deployment is needed because
the API is unchanged.
