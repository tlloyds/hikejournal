# Android 0.8.49 brand redesign — release evidence

## Scope and revision

- Platforms: Android + Web + API public pages.
- `VERSION` / Android `versionName`: **0.8.49**, unchanged.
- Android `versionCode`: **190** (previous: **189**).
- iOS: no source or build changes.
- Platform-qualified tag: `android-v0.8.49-brand-redesign`.
- Source commit: the commit targeted by `android-v0.8.49-brand-redesign`.

## Build and checks

- `./build_android.command personal`: **passed**.
- APK release verifier: **PASS, no findings**; package
  `com.hikejournal.app`, version **0.8.49**, build **190**, target SDK **36**.
- Strict AAB JAR signature verification and permanent signer identity: **passed**.
- Permanent signer SHA-256:
  `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.
- `apksigner verify --verbose --print-certs` with minimum SDKs 26 and 28:
  **passed**. `apksigner lineage --in <APK> --print-certs` showed the previous
  Android Debug certificate and permanent HikeJournal certificate. Both
  entries retain installed-data capability.
- Android 15 / API 35 accepted an in-place upgrade from the signed build **189**
  to **190**. The package reports version code 190 and launched to the required
  safety acknowledgment screen.
- Android test suites: **183 Debug passed**, **183 Release passed**.
- Public-page/API tests: **94 passed**, one existing Starlette/AnyIO
  deprecation warning.
- `git diff --check`: **passed**.
- Bluehost deployment completed over SSH to the HikeJournal site root.
  The homepage plus `/privacy/`, `/support/`, and `/account-deletion/` were
  verified live; deployed homepage and asset hashes matched the local source.
  The temporary SSH key was removed, the uploaded staging ZIP was moved to
  cPanel Trash, and pre-deployment files were saved to
  `/home3/mftphilo/hikejournal-backups/HikeJournal-site-before-brand-redesign-2026-11-08.tar.gz`.
- AndroidRuntime error filter after upgrade and launch: **no entries**.

## Debug-log triage

The release build reported the existing deprecated `requestSingleUpdate` call
in the species screen. Unit-test compilation reported the existing deprecated
`Locale` constructor. The API test run reported the existing Starlette/AnyIO
blocking portal deprecation. No production logging was added.

## Artifacts

| Artifact | Bytes | SHA-256 | Distribution |
| --- | ---: | --- | --- |
| `dist/HikeJournal-v0.8.49.apk` | 63,781,688 | `416368aab4d5dc1f424c666d797903a302e6ac81c602181efac00277da04daf1` | Verified APK; GitHub release attachment |
| `dist/HikeJournal-v0.8.49.aab` | 30,928,027 | `b912ca142debec9a343e026c09d9ad8d741051566e7679bf89d49f15868a1a7e` | Verified AAB; GitHub release attachment |

Detailed notes: [`docs/release-notes/0.8.49-android-brand-redesign.md`](../../release-notes/0.8.49-android-brand-redesign.md).
