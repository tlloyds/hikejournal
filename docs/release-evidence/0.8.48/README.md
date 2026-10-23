# HikeJournal v0.8.48 release evidence

**Release scope:** Android and iOS. The GitHub release distributes the signed
Android APK. The iOS implementation is built, tested, and archived locally;
there is no App Store Connect/TestFlight upload. API, Web, and shared server
behavior have **No functional changes**.

## Changes and versions

- A versioned identification-safety acknowledgment gates the app on both native
  platforms, including upgrades whose users already completed onboarding.
- The user must affirm understanding before continuing; merely opening the
  notice or its Settings copy does not acknowledge it.
- The full notice explains HikeJournal's independence from iNaturalist,
  identification uncertainty, independent expert verification, and the
  prohibition on using app IDs for eating/tasting, food/drink preparation,
  medicinal use, or touching/handling safety decisions.
- Confidence scores and saved/confirmed IDs explicitly do not guarantee
  accuracy or safety. Photo identification, Species Review, and collected
  Field Guide species details retain short reminders.
- Acknowledgment is stored locally for notice version **1**, independently of
  the app version and onboarding completion. It is not sent to the server.
- Canonical `VERSION` / Android `versionName`: **0.8.48** (previously 0.8.47).
- Android `versionCode`: **183** (previously 182).
- iOS `MARKETING_VERSION`: **0.8.48**, `CURRENT_PROJECT_VERSION`: **20**
  (previously 19).
- Android GPS-safe original-media browsing and media permissions are unchanged.

## Validation

- Android Debug and Release unit suites: **183 passed in each variant**, zero
  failures/errors/skips.
- Android Release lint: **passed**, zero errors, 61 warnings and one hint.
- Android 15 / API 35 instrumentation: **6 passed**. New tests cover disabled
  continuation before explicit acknowledgment, entry after acknowledgment,
  persistence across preference instances, a material notice-version update,
  and the read-only Settings copy. The prior keepsake-sharing UI/export tests
  also passed.
- iOS Debug simulator build and hosted XCTest: **passed, 81 tests**, zero
  failures/skips, on iPhone 17 Pro / iOS 26.5 with Xcode 26.6. Safety tests cover
  fresh/previously onboarded users, persistence through store recreation and
  onboarding replay, notice-version changes, and isolated preference domains.
- Final iOS Release device archive: **passed** at
  `/tmp/HikeJournal-v0.8.48-final.xcarchive`, with signing disabled for local
  validation. This is not an iOS distribution artifact.
- Mobile API/config/contract tests: **96 passed**, one existing
  Starlette/AnyIO deprecation warning.
- `./build_android.command personal`: **passed**. The canonical APK release
  verifier reported **PASS, no findings**; package `com.hikejournal.app`,
  version `0.8.48`, build `183`, target SDK `36`.
- Strict AAB signature verification and permanent signer checks: **passed**
  before artifact promotion.
- APK signing-lineage verification: **passed** for API 26–27 (previous
  certificate, v2) and API 28–36 (permanent certificate, v3).
- iOS canonical version validation and `git diff --check`: **passed**.
- Manual Android screen check: attempting to continue before acknowledgment
  stayed on the notice. After explicitly acknowledging and waiting for the app
  to open, a cold restart did not show the notice again. The screen was visually
  inspected on the emulator.
- iOS safety screen was installed, launched, and visually inspected on the
  iPhone 17 Pro simulator; the initial continuation button is visibly disabled.
- Android 15 / API 35 accepted an **in-place update from build 182 to 183**.
  Launch returned `Status: ok`, and the upgraded release displayed the new safety
  notice. The post-upgrade AndroidRuntime log had no fatal exception, and the
  ANR log had no HikeJournal entry.

## Android artifacts

| Artifact | SHA-256 | Distribution |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.48.apk` | `3ed3d1536674ea1efb98f2c909ed3999fe80e3a96bc823d634292a3c27c0bade` | Verified signed release APK; GitHub release attachment |
| `dist/HikeJournal-v0.8.48.aab` | `47c31d0614849d79e490163442bda687334fee302db78e09f1a31f27a97108bb` | Verified signed release AAB; retained locally |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage

No new production logging was introduced. Existing Kotlin warnings concern the
legacy one-shot location API, and Xcode warnings concern unrelated unnecessary
`try` expressions and skipped AppIntents metadata extraction. No physical-device
log bundle was supplied. Lint also suggests the KTX `SharedPreferences.edit`
extension for the new preference store, which uses the same edit/apply pattern
as the repository's existing preference stores. This is a style suggestion;
release lint passed. The release-app smoke check recorded no app fatal exception
or ANR.

## Wording reference

The notice links to iNaturalist's official
[explanation of computer-vision limits](https://help.inaturalist.org/en/support/solutions/articles/151000170369-why-can-t-computer-vision-identify-my-photo-correctly-).
HikeJournal's safety wording is its own notice; it does not represent an
iNaturalist endorsement.
