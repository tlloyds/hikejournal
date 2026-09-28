# HikeJournal Android 0.8.43 route replay framing and speed release evidence

**Release scope:** Android only. iOS, API, Web, and shared code have no
functional changes and no artifacts are shipped for them.

**Release tag:** `android-v0.8.43-route-replay-framing-speed` (platform-qualified
because the canonical `VERSION` remains `0.8.43`).

## Changes

- Fit the full route above the replay header and playback controls.
- Add `0.5×`, `1×`, and `2×` controls; speed changes during playback continue
  from the current position. The displayed total duration adjusts to 48, 24,
  or 12 seconds.

## Version and artifacts

- Canonical `VERSION`: `0.8.43` (unchanged).
- Android `versionName`: `0.8.43`.
- Android `versionCode`: `172` (previous: `171`).
- iOS build/version metadata: unchanged; no iOS archive or upload.
- API version and contracts: unchanged; no API deployment required.

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.43.apk` | `2d98a340a7fb2e16f2e5b5063cada8563a878fe398caba644c92aec794962c79` | Signed release APK; attach to GitHub release |
| `dist/HikeJournal-v0.8.43.aab` | `da81f2ddcd20d98a435bb34b9432f275d5c4de87ec29e9609689eb34cf026809` | Signed release AAB; strict signature verified, not attached |

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
- Android 15 emulator: installed version code `172` and launched `MainActivity`
  without an `AndroidRuntime` error. The profile displayed first-run onboarding,
  so the route framing and speed controls could not be opened for a visual
  smoke check.
- `git diff --check`: passed.

## Debug-log triage

No new Android debug logging was added. The emulator launch produced no
`AndroidRuntime` errors. No physical-device runtime log bundle was available
for separate triage.

## Deployment

The signed APK will be published as an asset on
`android-v0.8.43-route-replay-framing-speed`. No server deployment is required
because the API is unchanged.
