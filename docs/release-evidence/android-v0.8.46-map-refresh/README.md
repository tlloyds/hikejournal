# HikeJournal Android 0.8.46 main-map refresh release evidence

**Release scope:** Android only. iOS, API, Web, and shared code have no
functional changes.

**Release tag:** `android-v0.8.46-map-refresh` (platform-qualified because
canonical `VERSION` remains `0.8.46`).

## Changes

- Set the map-loading state before reading the local map cache, preventing a
  cached extent from winning the first camera fit while the server summary is
  still loading.
- Track whether summary bounds have been applied separately from any earlier
  fallback fit. The first server summary can now focus the map and trigger its
  matching viewport request.
- Add a regression test for applying late summary bounds after an earlier fit.

## Version and artifacts

- Canonical `VERSION`: `0.8.46` (unchanged).
- Android `versionName`: `0.8.46` (unchanged).
- Android `versionCode`: `180` (previous: `179`).
- iOS version/build metadata: unchanged; no iOS archive or upload.
- API version/contracts: unchanged; no API deployment.
- Web: no functional changes; no Web artifacts.
- Shared code: no functional changes.

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.46.apk` | `89a0f7d2d522c856b22b50af6a8afc16c5ece5abbbd94d12a772b2dd57012af7` | Signed canonical APK; permanent signer verified; attach to GitHub release |
| `dist/HikeJournal-v0.8.46.aab` | `f75cc7e644dc3cab6c748d58607df8041cc712cacfb13c28d76bc0a081515aea` | Signed AAB; strict signature verified; not attached |

Expected permanent Android signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Validation results

- Android debug and release unit tests: 180 passed in each variant.
- `./build_android.command personal`: passed; signed canonical APK and AAB
  were promoted after signature checks.
- APK release verifier: passed with no findings; package
  `com.hikejournal.app`, version name `0.8.46`, version code `180`, and the
  expected permanent signer.
- Strict AAB signature verification and expected signer identity: passed.
- Signing lineage was applied. Android 15 accepted the in-place upgrade from
  version code `179` to `180` and launched without a runtime error.
- `:app:lintRelease`: passed.
- `git diff --check`: passed.

## Debug-log triage

The Android 15 emulator's targeted `AndroidRuntime` log check was empty after
upgrade; no physical-device log bundle was supplied. A read-only production SQL
smoke check confirmed the viewport RPC returned matches and overview clusters
across the tested photo bounds, with no row-cap or empty-result issue.

## Deployment

The signed APK is published on `android-v0.8.46-map-refresh`. The signed AAB
was built and verified but not attached. No API deployment is needed.
