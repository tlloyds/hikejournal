# Android 0.8.49 photo viewer zoom — release evidence

## Scope and revision

- Platform: Android only.
- Canonical `VERSION` / Android `versionName`: **0.8.49**, unchanged.
- Android `versionCode`: **189** (previous: **188**).
- Platform-qualified tag: `android-v0.8.49-photo-viewer-zoom`.
- Source commit: the commit targeted by `android-v0.8.49-photo-viewer-zoom`.

## Build and checks

- `:app:testDebugUnitTest`: **183 passed**, zero failures, errors, or skipped.
- `:app:testReleaseUnitTest`: **183 passed**, zero failures, errors, or skipped.
- `:app:lintRelease`: **passed**, zero errors, 61 warnings, one hint.
- `./build_android.command personal`: **passed**. The script created the
  canonical signed APK and AAB after the personal-release configuration,
  strict AAB JAR signature, permanent signer identity, APK verification, and
  signing-lineage promotion checks passed.
- APK release verifier: **PASS, no findings**; package
  `com.hikejournal.app`, version **0.8.49**, build **189**, target SDK **36**.
- Permanent signer SHA-256:
  `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.
- API 26–27 signature verification: v2 signer digest
  `e5be9f29c92201c86719868de1ab3404bad270876b41b2b69c110b689c73ac1c`.
- API 28–35 signature verification: v3 signer digest matches the expected
  permanent signer above.
- The build-188 APK was downloaded from
  `android-v0.8.49-multi-hike-sharing-visibility`; its SHA-256 matched the
  published release asset. Android 15 / API 35 accepted the signed in-place
  upgrade to build **189**. App UID **10227** and first-install time
  **2026-10-23 08:53:40** were preserved. `MainActivity` resumed and the
  post-launch AndroidRuntime error log was empty.
- `git diff --check`: **passed**.
- The zoom gestures were not manually exercised inside an authenticated
  journal session.

## Debug-log triage

No AndroidRuntime errors followed the emulator restart and launch. Existing
release lint counts (61 warnings and one hint) and deprecated location / test
`Locale` API warnings remain. The release package retained
`libandroidx.graphics.path.so` and `libmaplibre.so` because the build tools
could not strip them. API 26–27 signature inspection reports the known warning
for the v3 proof-of-rotation scheme. No production logging was added.

## Artifacts

| Artifact | Bytes | SHA-256 | Distribution |
| --- | ---: | --- | --- |
| `dist/HikeJournal-v0.8.49.apk` | 63,461,312 | `6d523094946066759e1e659aa50d49f50cd4d8ccf5c6277cd89237a3e5e25b59` | Verified signed APK; attached to the GitHub release |
| `dist/HikeJournal-v0.8.49.aab` | 30,608,613 | `3efd04e1969412c306e5a14d6b550182702b33720cb862216cb91aaecafe0d81` | Verified signed AAB; retained locally |

Release notes: [0.8.49 Android photo viewer zoom](../../release-notes/0.8.49-android-photo-viewer-zoom.md).
