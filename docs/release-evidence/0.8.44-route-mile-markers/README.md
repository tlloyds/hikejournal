# HikeJournal 0.8.44 route replay mile markers release evidence

**Release scope:** Android plus mobile API version metadata. iOS, Web, and
shared code have no functional changes and no artifacts are shipped for them.

**Release tag:** `v0.8.44`.

## Changes

- Show elapsed and total route distance in miles during playback.
- Add numbered map markers at whole-mile points; each marker changes to orange
  when the replay reaches that distance.
- Preserve 24-second base playback, selectable speeds, and the camera fit
  around the title and controls.

## Version and artifacts

- Canonical `VERSION`: `0.8.44` (previous: `0.8.43`).
- Android `versionName`: `0.8.44`.
- Android `versionCode`: `173` (previous: `172`).
- iOS `MARKETING_VERSION`: synchronized to `0.8.44`; `CURRENT_PROJECT_VERSION`
  unchanged; no iOS archive or upload.
- Mobile API reported version: `0.8.44`; no API behavior or contract changes.

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.44.apk` | `dbaed7ae6f2632961458ea1514197360697958802bb69c5f154f717241dec321` | Signed release APK; attach to GitHub release |
| `dist/HikeJournal-v0.8.44.aab` | `77751ce1f6ba0431df4f8fdfc57b2442fa83e6140e3288a965809d3871a10297` | Signed release AAB; strict signature verified, not attached |

Expected permanent signer SHA-256: `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Validation results

- `:app:testDebugUnitTest` and `:app:testReleaseUnitTest`: passed, 173 tests
  across 49 suites in each variant.
- Mobile API version/operations tests: passed, 10 tests via
  `tests/test_mobile_operations.py` and `tests/test_mobile_config_contract.py`.
- `./ios/Scripts/sync_version.sh --check`: passed; iOS marketing version
  matches canonical version `0.8.44`.
- `./build_android.command personal`: passed for canonical version `0.8.44`,
  including release lint, signed packaging, canonical artifact promotion, APK
  verifier, strict AAB signature, and expected signer identity.
- APK signing lineage: `apksigner` verified the configured previous signer
  for API 26–27 (SHA-256
  `e5be9f29c92201c86719868de1ab3404bad270876b41b2b69c110b689c73ac1c`) and
  the permanent signer for API 28+.
- Android 15 emulator: installed version code `173` and launched `MainActivity`
  without an `AndroidRuntime` error. Its first-run profile had no hike to open,
  so mile-marker rendering could not be visually exercised.
- API deployment/readiness: the Cloud Build trigger is configured for pushes
  to `main`; this machine has no active `gcloud` project, so the Cloud Run
  revision and readiness could not be independently verified.
- `git diff --check`: passed.

## Debug-log triage

No new Android debug logging was added. The emulator launch produced no
`AndroidRuntime` errors. No physical-device runtime log bundle was available
for separate triage.

## API deployment

The Cloud Build trigger is configured to deploy on pushes to `main`. This
machine has no active `gcloud` project, so the Cloud Run revision and readiness
cannot be independently verified from here.

## Android deployment

The signed APK will be published as an asset on GitHub release `v0.8.44`.
