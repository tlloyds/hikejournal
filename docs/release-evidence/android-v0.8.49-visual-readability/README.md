# Android 0.8.49 readability and navigation polish — release evidence

## Scope and revision

- Platform: **Android only**.
- `VERSION` / Android `versionName`: **0.8.49**, unchanged.
- Android `versionCode`: **192** (previous: **191**).
- iOS, Web, and API behavior/source/build artifacts: unchanged.
- Platform-qualified tag: `android-v0.8.49-visual-readability`.
- Source commit: the commit targeted by `android-v0.8.49-visual-readability`.

## Build and checks

- `./build_android.command personal`: **passed**.
- APK release verifier: **PASS, no findings**; package
  `com.hikejournal.app`, version **0.8.49**, build **192**, target SDK **36**.
- Strict AAB signature verification and permanent signer identity: **passed**.
- Permanent signer SHA-256:
  `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.
- APK signature verification passed with minimum SDKs **26** and **28**. The
  APK lineage contains both the former Android Debug signer and permanent
  signer, with installed-data capability retained by both.
- Android 15 / API 35 accepted the signed in-place upgrade from build **191**
  to **192** and reported version code **192**. The app launched to the safety
  notice and Google sign-in setup; main navigation was not opened because the
  emulator requires a Google account.
- `:app:compileDebugKotlin`: **passed**. Unit test suites were not run for
  this visual-only update.
- `git diff --check`: **passed**.
- AndroidRuntime filter after install and launch: **no app fatal exception**.

## Debug-log triage

The release build reported the existing deprecated `requestSingleUpdate` call
in `SpeciesScreens.kt`. The post-upgrade app-process log contained no fatal
exception. No production logging was added.

## Artifacts

| Artifact | Bytes | SHA-256 | Distribution |
| --- | ---: | --- | --- |
| `dist/HikeJournal-v0.8.49.apk` | 63,781,688 | `bad7590002213db9935491d057bd94d786b40e611f52b57ade214f2d5f392891` | Verified APK; GitHub release attachment |
| `dist/HikeJournal-v0.8.49.aab` | 30,931,696 | `1b743a53d2591a86cf1ae71b8fa9271523cb3e37b1c4945de67a96baf37e68b3` | Verified AAB; GitHub release attachment |

Detailed notes: [`docs/release-notes/0.8.49-android-visual-readability.md`](../../release-notes/0.8.49-android-visual-readability.md).
