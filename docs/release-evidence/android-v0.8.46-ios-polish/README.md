# HikeJournal Android 0.8.46 build 181 release evidence

**Release scope:** iOS and Android. Android APK/AAB are the only distributed
artifacts. The iOS app is a local simulator build for user review; there is no
iOS archive or App Store upload.

**Release tag:** `android-v0.8.46-ios-parity-polish` (platform-qualified since
canonical `VERSION` remains `0.8.46`).

## Changes

- iOS batch celebration image collection is deterministic.
- iOS Maps JSON test fixture now forms a valid FeatureCollection.
- iOS Field Guide uses parsed observation dates and supports scientific-name
  sorting.
- iOS journal photo detail can share a protected staged still image with its
  caption.
- Android has no functional changes; build 181 advances the Android version
  code for the requested artifact.
- API, Web and shared server behavior have no functional changes.

## Version and artifacts

- Canonical `VERSION`: `0.8.46` (unchanged).
- Android `versionName`: `0.8.46` (unchanged).
- Android `versionCode`: `181` (previous: `180`).
- iOS marketing version/build: `0.8.46` / `18` (unchanged; no upload).
- API version: `0.8.46` (unchanged).
- APK SHA-256: `dfa140212844ecb4f06ecb017da8dce145e4b5c45c72b9587d2b99d1c9051363`.
- AAB SHA-256: `de62512e58fea9b4e510a33ae84171e0055c18ae71e5307e17b88e62caee06c9`.
- Permanent Android signer SHA-256:
  `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Validation

- HikeJournal Domain: 33 tests passed.
- HikeJournal Maps: 29 tests passed.
- Android Debug unit tests: 180 passed; Android Release unit tests: 180 passed.
- Android `lintRelease`: passed.
- iOS Debug app built, installed and launched on iPhone 17 Pro / iOS 26.5.
- Android signed APK/AAB build and APK release verifier: passed; package
  `com.hikejournal.app`, version name `0.8.46`, version code `181`, target API
  `36`; no verifier findings.
- Strict AAB signature and expected signer check: passed in
  `./build_android.command personal`.
- Android 180 to 181 in-place upgrade: passed on Android 15 / API 35 with the
  existing permanent signer; upgraded app launched without an
  `AndroidRuntime` fatal error.
- Debug-log triage: the 300-line post-upgrade `AndroidRuntime` log check
  contained no fatal error. No physical-device logs were supplied.

## Launch gate still open

The Android app does not yet contain Play Billing purchase/restore UI or a
client-to-server purchase-token verification path. Shared mobile API
entitlement enforcement remains disabled. Store product records are not set up.
This GitHub release is an installable engineering candidate and must not be
represented as enabling paid Plus on Google Play.
