# HikeJournal Android 0.8.43 route replay release evidence

**Release scope:** Android only. iOS, API, Web, and shared code have no
functional changes and no artifacts are shipped for them.

**Release tag:** `android-v0.8.43-route-replay` (platform-qualified because
the canonical `VERSION` remains `0.8.43`).

## Changes

- Add a 24-second distance-weighted reveal of a saved route to the Android
  Journal, with a moving marker, play/pause, replay, and scrubbing.
- Keep the full route visible as context and preserve separate track segments.
- Leave live tracking, route import/storage, and the existing static Journal
  route preview behavior unchanged.

## Version and artifacts

- Canonical `VERSION`: `0.8.43` (unchanged).
- Android `versionName`: `0.8.43`.
- Android `versionCode`: `170` (previous: `169`).
- iOS build/version metadata: unchanged; no iOS archive or upload.
- API version and contracts: unchanged; no API deployment required.

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.43.apk` | `4cc363b25f311aabbc40ce0afe9ee732c6ed6e4910834d926096983d747ed2fa` | Signed release APK; attached to GitHub release |
| `dist/HikeJournal-v0.8.43.aab` | `6ab4dec682c494792484eb024681605958842531d7501acfa8390372078c6057` | Signed release AAB; strict signature verified, not attached |

Expected permanent Android signer SHA-256: `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Validation results

- `:app:testDebugUnitTest` and `:app:testReleaseUnitTest`: passed, 172 tests
  across 49 suites in each variant.
- `./build_android.command personal`: passed, including release lint and
  signed APK/AAB packaging.
- APK release artifact verifier: passed with no findings; package
  `com.hikejournal.app`, version name `0.8.43`, version code `170`, expected
  permanent signer.
- Strict AAB signature and signer identity checks: passed as part of the
  personal release build.
- APK signing lineage: `apksigner` verified the configured prior signer for
  API 26–27 (SHA-256
  `e5be9f29c92201c86719868de1ab3404bad270876b41b2b69c110b689c73ac1c`) and
  the permanent signer for API 28+.
- Android 15 emulator upgrade smoke check: installed version code 166 upgraded
  to 170 with `adb install -r`; `MainActivity` launched and no
  `AndroidRuntime` errors were logged.
- `git diff --check`: passed.

## Debug-log triage

No new Android debug logging was added. The Android 15 emulator launch produced
no `AndroidRuntime` errors. No physical-device runtime log bundle was available
for separate triage.

## Deployment

The signed APK is published as an asset on
`android-v0.8.43-route-replay`. No server deployment is required because the
API is unchanged.
