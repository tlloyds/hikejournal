# HikeJournal Android 0.8.43 photo-sharing release evidence

**Release scope:** Android only. iOS, API, Web, and shared code have no functional changes and no artifacts are shipped for them.

**Release tag:** `android-v0.8.43-photo-sharing` (platform-qualified because canonical `VERSION` remains `0.8.43`).

## Changes

- Add a single-photo share action to the shared Android photo viewer, covering both gallery and hike photos.
- Stage the original image in the private app cache and expose it to share targets with a temporary `FileProvider` read grant.
- Launch Android's native Sharesheet for one `image/*` stream and include the photo note when present.
- Keep the GPS-safe phone-original media browser and Android media permissions unchanged.

## Version and artifacts

- Canonical `VERSION`: `0.8.43` (unchanged).
- Android `versionName`: `0.8.43`.
- Android `versionCode`: `169` (previous: `168`).
- iOS build/version metadata: unchanged; no iOS archive or upload.
- API version and contracts: unchanged; no API deployment required.

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.43.apk` | `0eca59446e33197757983b78a2cb765dd2c9c61fa1ac620fb963aa3c5957ddc8` | Signed release APK; attached to GitHub release |
| `dist/HikeJournal-v0.8.43.aab` | `ef1932f23bb10072bb437ef06356e99aa5d38df2fb09817bbe183640d2487495` | Signed release AAB; verified, not attached |

Expected permanent signer SHA-256: `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Validation results

- `./build_android.command personal`: passed, including release lint, signed APK/AAB packaging, canonical APK/AAB promotion, APK artifact verification, strict AAB signature verification, and expected signer identity.
- APK artifact verifier: passed with no findings; package `com.hikejournal.app`, version name `0.8.43`, version code `169`.
- Signing lineage extracted from the APK and verified for API 26–27 using the previous signer and API 28+ using the permanent signer.
- `git diff --check`: passed.
- Android unit tests were not run.

## Debug-log triage

No new Android debug logging was added. The release build emitted no new compiler warnings. No physical-device runtime log bundle was available for separate triage.

## Deployment

The signed APK is published as an asset on `android-v0.8.43-photo-sharing`. No server deployment is needed because the API is unchanged.
