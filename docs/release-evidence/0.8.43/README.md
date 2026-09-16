# HikeJournal 0.8.43 Android release evidence

**Captured:** 2026-09-16

**Release scope:** Android only. The mobile API and iOS app have no functional
changes in this release. iOS version metadata remains synchronized with the
canonical version, but no iOS artifact is produced.

**Release tag:** `android-v0.8.43-species-review-sync` (the canonical
`v0.8.43` tag already contains the preceding 0.8.43 Android release).

## Change summary

- Multi-select species-review changes are persisted atomically in the Android
  Room queue before WorkManager is scheduled.
- Android no longer waits for a UI-scoped `syncNow()` call to submit review
  choices. The durable field-sync worker owns the work and retries it after
  process recreation or loss of app focus.
- Review-only syncs use the same foreground `dataSync` worker path as large
  photo transfers and expose progress in the background notification.
- The Android phone-original media picker and EXIF/GPS-preserving upload path
  are unchanged.

## Version and artifacts

- canonical `VERSION`: `0.8.43`
- Android `versionName`: `0.8.43`
- Android `versionCode`: `167`
- mobile API version: `0.8.43` (canonical shared version; no API code change)
- iOS `MARKETING_VERSION`: `0.8.43` (metadata synchronization only)

| Artifact | SHA-256 | Classification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.43.apk` | `bc167a0931af56f0309babcd13a9d356f569a10f6145bbeb2bafac35e566486b` | Signed personal Android release APK |
| `dist/HikeJournal-v0.8.43.aab` | `8da68b00fc5144b3a9c2c12bd925c962e071ab6845cc36f682917adb3201a857` | Signed personal Android release bundle |

The Android signer SHA-256 is
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.
The release script passed strict AAB signature verification, expected-signer
identity checks, and the release artifact verifier with no findings.

## Automated verification

- Android debug and release unit tests: passed (169 tests across 48 suites in
  each variant).
- Android personal release build, release lint, APK/AAB packaging, strict
  signature verification, and artifact verification: passed.
- iOS `HikeJournalSync` package tests: 16 passed.
- Full iOS app build/test was attempted but the existing cached MapLibre
  XCFramework is missing its `Info.plist`; this is an environment/package-cache
  failure unrelated to the Android change. No iOS artifact is shipped.
- The only Android compile warning was the pre-existing deprecated location
  API use in `SpeciesScreens.kt`; no new warning was introduced by this change.
