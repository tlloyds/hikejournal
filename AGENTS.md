# HikeJournal agent notes

## Release and versioning

- The canonical release version is the plain-text value in `VERSION`.
- Android `versionName`, the mobile API health/version responses, and the APK
  filename must all use that value.
- Development builds use `./build_android.command debug` and must remain named
  `dist/HikeJournal-v<VERSION>-debug.apk`; they are never release artifacts.
- For a release, update `VERSION` once, increment Android `versionCode`, configure
  the permanent signing inputs plus `ANDROID_EXPECTED_SIGNER_SHA256`, and run
  `./build_android.command personal`. Verify the canonical APK and AAB are named
  `dist/HikeJournal-v<VERSION>.apk` and `.aab`, pass the release verifier, strict
  AAB signature verification, and match the expected signer before publishing.
- While upgrades from the historical debug-signed APK remain supported, retain
  the previous keystore plus `ANDROID_SIGNING_LINEAGE_PATH` and the
  `ANDROID_PREVIOUS_*` inputs. Personal APKs must include the tested signing
  lineage, preserve installed app data during an in-place upgrade, and still
  report the permanent certificate as the current signer. The AAB remains
  signed only by the permanent key.
- Commit and push the change to `main`, then create the matching GitHub release
  tag `v<VERSION>` with title `HikeJournal v<VERSION>` and attach only that
  verified, permanently signed canonical APK (and AAB where the release process
  requires it). Never attach `-debug` or `-unsigned` artifacts.
- Keep this guidance in sync when the release workflow changes so future Codex
  requests do not leave the API and APK versions out of step.
- The Android photo upload path must keep the GPS-safe phone-original browser
  (`LocalMediaPickerDialog`/`LocalMediaLibrary`) wired into the journal. Do not
  replace it with a system/Google Photos-only picker: cloud-provider URIs may
  redact EXIF GPS, which breaks photo maps and coordinate-backed iNaturalist
  publishing. Any Play permission change must go through the photo/video
  permissions declaration review, not by removing this path.
