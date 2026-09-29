# HikeJournal Android 0.8.44 iNaturalist connection release evidence

**Release scope:** Android only. Canonical `VERSION` remains `0.8.44`.

**Release tag:** `android-v0.8.44-inat-connect-during-sync`.

## Changes

- Removed the field-sync connectivity pre-check from iNaturalist OAuth startup;
  the OAuth URL request now runs even while field notes are queued or syncing.
- Added a visible connecting state and an inline Settings error so failures are
  not hidden behind the open dialog.
- Kept existing global error feedback for iNaturalist connection attempts
  outside Settings.

## Version and artifacts

- Canonical `VERSION`: `0.8.44` (unchanged).
- Android `versionName`: `0.8.44` (unchanged).
- Android `versionCode`: `175` (previous: `174`).
- iOS, API, Web, and shared code: no functional changes; no unrelated
  artifacts were built or shipped.

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.44.apk` | `b3edf0fe000e85fe8adf0e63be2af47199e0f8e279bdde58c163854c104afc73` | Signed release APK; attach to GitHub release |
| `dist/HikeJournal-v0.8.44.aab` | `a4560b9414f52d71be8bfb359d314164edd18915e80bb3e2ec71b99ab1876385` | Signed release AAB; strict signature verified; not attached |

Expected permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Validation results

- `:app:testDebugUnitTest` and `:app:testReleaseUnitTest`: passed, 175 tests
  across 49 suites in each variant.
- `:app:lintRelease`: passed. The personal release build also passed
  `lintVitalRelease`.
- `./build_android.command personal`: passed, including signed canonical
  APK/AAB promotion, release APK verifier with no findings, strict AAB JAR
  signature verification, and permanent signer identity checks.
- Signing lineage was applied using the configured previous and permanent
  signers. Android 15 installed the prior public release APK (version code
  `174`), accepted the in-place upgrade to version code `175`, and launched
  `MainActivity` without an `AndroidRuntime` fatal exception.
- No authenticated account or companion endpoint was available in the emulator
  for a live OAuth round trip. `git diff --check` passed.

## Root cause and debug-log triage

Commit `1f3b659` on August 31 tied the Android iNaturalist OAuth action to
`syncStatus.connected`. Commit `75d78ff` on September 28 updated that field to
require Android's validated-internet network capability to recover other
offline flows, but the OAuth pre-check remained. A transiently disconnected
field-sync state therefore prevented the OAuth API request from starting.
The error used the bottom-level app banner behind Settings, which obscured the
feedback. No phone log bundle was supplied and no new debug logging was added.

## Android deployment

The signed APK is published as the asset on GitHub release
`android-v0.8.44-inat-connect-during-sync`.
