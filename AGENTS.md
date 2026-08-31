# HikeJournal agent notes

## Release and versioning

- Begin every release by declaring its scope: iOS, Android, Web, API, or shared.
  Only rebuild, version-bump, package, and publish artifacts for affected
  platforms. An unaffected platform must not be rebuilt or packaged unless
  required to validate shared code. iOS-only changes do not produce a new
  Android APK/AAB; Android-only changes do not trigger an iOS archive.
- Preserve independent platform build numbers and versions. Never increment
  Android `versionCode` for an iOS-only release, or iOS
  `CURRENT_PROJECT_VERSION` for an Android-only release.
- `VERSION` remains the canonical shared Android/API semantic version.
  Android `versionName`, mobile API version/health responses, and Android
  artifact filenames must use it.
- `ios/Config/Version.xcconfig` supplies iOS `MARKETING_VERSION` and is
  generated from `VERSION` by `./ios/Scripts/sync_version.sh`. The current iOS
  validator requires these values to match when building iOS. Do not change
  `VERSION` solely to force an iOS build. `CURRENT_PROJECT_VERSION` is the
  independent iOS build number and must increase for each App Store Connect
  upload.
- Android releases:
  - Update `VERSION` only when the Android/API semantic version changes.
  - Increment Android `versionCode` for each distributed Android build.
  - Configure the permanent signing inputs and
    `ANDROID_EXPECTED_SIGNER_SHA256`.
  - Run `./build_android.command personal`.
  - Verify canonical artifacts:
    `dist/HikeJournal-v<VERSION>.apk` and
    `dist/HikeJournal-v<VERSION>.aab`.
  - Require release-verifier success, strict AAB signature verification,
    expected permanent signer identity, and tested signing lineage for
    upgrades.
  - Never publish `-debug` or `-unsigned` artifacts.
- iOS releases:
  - Increment only the iOS build metadata required for the release.
  - Run the iOS build/tests and archive workflow when an iOS artifact is being
    shipped.
  - Do not build or package Android unless shared-code validation requires it.
- Web/API/shared releases:
  - Run the relevant tests and deployment workflow for the changed surfaces.
  - Do not create mobile artifacts unless the mobile clients are affected or
    required for shared-code validation.
- Release notes must document every platform explicitly, including “No
  functional changes” for unaffected platforms. Include code changes,
  version/build changes, validation results, and any debug-log triage.
- Commit and push the release to `main`.
- For releases that change `VERSION`, create tag `v<VERSION>` with title
  `HikeJournal v<VERSION>`. For platform-only releases that keep `VERSION`
  unchanged, use a unique platform-qualified tag instead of reusing an
  existing tag. Attach only verified artifacts for affected platforms.
- Keep this guidance synchronized with the actual release workflow.
- The Android photo upload path must keep the GPS-safe phone-original browser
  (`LocalMediaPickerDialog`/`LocalMediaLibrary`) wired into the journal. Do not
  replace it with a system/Google Photos-only picker: cloud-provider URIs may
  redact EXIF GPS, which breaks photo maps and coordinate-backed iNaturalist
  publishing. Any Play permission change must go through the photo/video
  permissions declaration review, not by removing this path.
