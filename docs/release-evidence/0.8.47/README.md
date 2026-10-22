# HikeJournal v0.8.47 release evidence

**Release scope:** Android and iOS. GitHub distributes the signed Android APK.
The iOS implementation is built and tested locally; no iOS distribution or
App Store Connect upload is performed. API, Web, and shared server behavior
have **No functional changes**.

## Changes and versions

- Both native hike-sharing screens offer Keepsake first (default), Keepsake
  last, and No keepsake. Keepsake modes reserve one of 20 image slots, allowing
  19 album photos; No keepsake allows 20.
- Switching to a keepsake retains the first 19 selected photos. Photo order is
  preserved through staging and system-share attachment construction.
- No-keepsake sharing skips keepsake generation and requires an available
  photo. Completely unavailable photo selections produce an error instead of
  opening an empty share sheet.
- Root `VERSION` and Android `versionName`: `0.8.47` (previously `0.8.46`).
- Android `versionCode`: `182` (previously `181`).
- iOS `MARKETING_VERSION`: `0.8.47`; `CURRENT_PROJECT_VERSION`: `19`
  (previously `18`).
- API version reporting follows canonical `VERSION`; no API contract change.

## Validation

- Android Debug unit suite: **183 passed**, zero failures/errors/skips.
- Android Release unit suite: **183 passed**, zero failures/errors/skips.
- Android Release lint: **passed**, zero errors, 60 warnings and one hint in
  the existing application; no finding names the changed sharing source.
- Android 15 / API 35 instrumentation: **3 passed**. Tests cover mode selection,
  dynamic Select all limits, trimming 20 selections to 19, disabling an empty
  no-keepsake share, actual FileProvider attachments and image ordering for
  every mode, and entirely unavailable photos.
- iOS Debug simulator build: **passed** with Xcode 26.6.
- iOS hosted XCTest: **77 passed**, zero failures/skips on iPhone 17 Pro /
  iOS 26.5. New staged-file tests exercise 19-plus-keepsake vs. 20-photo exports,
  both keepsake positions, selected-photo order, partial failures, empty exports,
  keepsake-only exports, and exclusion of videos/blank URLs. Existing 1080×1350
  keepsake rendering also passed.
- iOS Release device archive: **passed** at
  `/tmp/HikeJournal-v0.8.47.xcarchive`, with signing disabled for this local
  validation. This archive is not an iOS distribution artifact.
- Mobile API/config/contract tests: **96 passed**, one existing
  Starlette/AnyIO deprecation warning.
- iOS canonical version validator and `git diff --check`: **passed**.
- `./build_android.command personal`: **passed**, producing the canonical signed
  APK and AAB. APK release verification reported **PASS, no findings**; package
  `com.hikejournal.app`, version `0.8.47`, build `182`, target SDK `36`.
- Strict AAB JAR signature verification and permanent signer identity checks:
  **passed** before artifact promotion.
- APK signature verification for API 26–27: **passed** with the previous
  certificate through APK Signature Scheme v2; API 28–36: **passed** with the
  permanent certificate through APK Signature Scheme v3.
- Android 15 / API 35 accepted an **in-place update from build 181 to 182**.
  The release app launched successfully (`Status: ok`); the post-upgrade
  AndroidRuntime log contained no fatal exception, and no HikeJournal ANR was
  recorded.

## Debug-log triage

- No new production logging or media-permission changes were introduced.
- The emulator initially reported startup ANRs in SystemUI, the Pixel launcher,
  and Google services. No HikeJournal ANR was recorded; the launcher was stopped
  and the final sharing instrumentation run passed.
- The UI test was corrected to scroll its lazy grid after inserting the
  keepsake preview, before asserting the selection counter.
- Xcode warnings concern existing unnecessary `try` expressions in unrelated
  tests and skipped AppIntents metadata extraction. The changed sharing files
  compiled without a warning.
- No physical-device runtime log bundle was supplied.

## Android artifacts

| Artifact | SHA-256 | Distribution |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.47.apk` | `d2c22038d09bab72e2610b5d59155e87647b5f26541d3a0dd60a7bbc82115430` | Verified signed release APK; attach to GitHub release |
| `dist/HikeJournal-v0.8.47.aab` | `7da6771c16e8974c1443d52dd294fcac5a44ffb19f79298b424837d01ea79f9e` | Verified signed release AAB; retained locally |

Expected permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

The API 26–27 signing-lineage certificate SHA-256 is
`E5:BE:9F:29:C9:22:01:C8:67:19:86:8D:E1:AB:34:04:BA:D2:70:87:6B:41:B2:B6:9C:11:0B:68:9C:73:AC:1C`.

The GitHub release tag is `v0.8.47`, titled **HikeJournal v0.8.47**. No Web,
API, or iOS distribution artifact is attached.
