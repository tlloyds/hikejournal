# HikeJournal Android 0.8.43 route replay controls release evidence

**Release scope:** Android only. iOS, API, Web, and shared code have no
functional changes and no artifacts are shipped for them.

**Release tag:** `android-v0.8.43-route-replay-controls` (platform-qualified
because the canonical `VERSION` remains `0.8.43`).

## Changes

- Lift the route replay controls above the bottom system area and strengthen
  contrast for the scrubber, play/pause button, and duration label.
- Preserve 24-second distance-weighted playback and route segment breaks.

## Version and artifacts

- Canonical `VERSION`: `0.8.43` (unchanged).
- Android `versionName`: `0.8.43`.
- Android `versionCode`: `171` (previous: `170`).
- iOS build/version metadata: unchanged; no iOS archive or upload.
- API version and contracts: unchanged; no API deployment required.

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.43.apk` | `52a5a2b7f54815de0daca341c27256a61c800ee6cb99890189d160eb14d79e32` | Signed release APK; attached to GitHub release |
| `dist/HikeJournal-v0.8.43.aab` | `22d82b7bd481176818a385ff7260d583d22ba3e4674ad4f447a89cb097ee2e7c` | Signed release AAB; strict signature verified, not attached |

Expected permanent signer SHA-256: `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Validation results

- `:app:testDebugUnitTest` and `:app:testReleaseUnitTest`: passed, 172 tests
  across 49 suites in each variant.
- `./build_android.command personal`: passed, including release lint, signed
  APK/AAB packaging, canonical artifact promotion, APK verifier, strict AAB
  signature verification, and expected signer identity.
- APK signing lineage: `apksigner` verified the configured previous signer
  for API 26–27 (SHA-256
  `e5be9f29c92201c86719868de1ab3404bad270876b41b2b69c110b689c73ac1c`) and
  the permanent signer for API 28+.
- Android 15 emulator: installed version code `171` and launched `MainActivity`
  without an `AndroidRuntime` error. The emulator profile displayed first-run
  onboarding, so route replay itself could not be opened for a visual check.
- `git diff --check`: passed.

## Debug-log triage

No new Android debug logging was added. The emulator launch produced no
`AndroidRuntime` errors. No physical-device runtime log bundle was available
for separate triage.

## Deployment

The signed APK is published as an asset on
`android-v0.8.43-route-replay-controls`. No server deployment is required
because the API is unchanged.
