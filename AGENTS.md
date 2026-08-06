# HikeJournal agent notes

## Release and versioning

- The canonical release version is the plain-text value in `VERSION`.
- Android `versionName`, the mobile API health/version responses, and the APK
  filename must all use that value.
- For a release, update `VERSION` once, increment Android `versionCode`, run
  `./build_android.command`, and verify the APK is named
  `dist/HikeJournal-v<VERSION>.apk`.
- Commit and push the change to `main`, then create the matching GitHub release
  tag `v<VERSION>` with title `HikeJournal v<VERSION>` and attach that APK.
- Keep this guidance in sync when the release workflow changes so future Codex
  requests do not leave the API and APK versions out of step.
