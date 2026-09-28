# HikeJournal Android 0.8.44 Species Review connectivity release evidence

**Release scope:** Android only. Canonical `VERSION` remains `0.8.44`.

**Release tag:** `android-v0.8.44-species-review-connectivity`.

## Changes

- Base connectivity state on Android's `INTERNET` and `VALIDATED` capabilities
  so loss and restoration of internet access emit a state transition.
- Reload a previously requested Species Review queue on reconnection.

## Version and artifacts

- Canonical `VERSION`: `0.8.44` (unchanged).
- Android `versionName`: `0.8.44` (unchanged).
- Android `versionCode`: `174` (previous: `173`).
- iOS, API, Web, and shared code: no functional changes; no unrelated
  artifacts were built or shipped.

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.44.apk` | `ef5bfc81d5593b8f07d6c5274991e1c3ea6e6275d6ee22cda748d95c4a508895` | Signed release APK; attach to platform release |
| `dist/HikeJournal-v0.8.44.aab` | `b22d95db831df9ca682928544b18bf9f0899d1aed38a8eb8c1f124a1895074d8` | Signed release AAB; strict signature verified; not attached |

Expected permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Validation results

- `:app:testDebugUnitTest` and `:app:testReleaseUnitTest`: passed, 175 tests
  across 49 suites in each variant.
- `./build_android.command personal`: passed, including release lint,
  canonical APK/AAB promotion, APK verifier, strict AAB signature, and
  permanent signer identity checks.
- The release APK was post-signed with the configured previous/current signer
  lineage. Android 15 installed the signed `versionCode` `173` release APK,
  accepted the in-place upgrade to `versionCode` `174`, and launched
  `MainActivity` without an `AndroidRuntime` fatal exception.
- No authenticated review queue was available on the emulator for an
  end-to-end Species Review interaction; the reconnect transition predicate
  passed unit tests in both build variants.
- `git diff --check`: passed.

## Debug-log triage

The supplied screenshot showed an offline cached queue and disabled decisions.
No device log bundle was supplied. The emulator launch produced no
`AndroidRuntime` fatal exception, and no new Android debug logging was added.

## Android deployment

The signed APK will be published as an asset on GitHub release
`android-v0.8.44-species-review-connectivity`.
