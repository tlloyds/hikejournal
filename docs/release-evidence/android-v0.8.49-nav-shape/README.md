# Android 0.8.49 bottom navigation shapes — release evidence

## Scope and revision

- Platform: **Android only**.
- `VERSION` / Android `versionName`: **0.8.49**, unchanged.
- Android `versionCode`: **193** (previous: **192**).
- iOS, Web, and API behavior/source/build artifacts: unchanged.
- Platform-qualified tag: `android-v0.8.49-nav-shape`.
- Source commit: the commit targeted by `android-v0.8.49-nav-shape`.

## Build and checks

- `./build_android.command personal`: **passed**.
- APK release verifier: **PASS, no findings**; package
  `com.hikejournal.app`, version **0.8.49**, build **193**, target SDK **36**.
- Strict AAB signature verification and permanent signer identity: **passed**.
- Permanent signer SHA-256:
  `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.
- APK signature verification passed with minimum SDKs **26** and **28**. The
  APK lineage contains both the former Android Debug signer and permanent
  signer, with installed-data capability retained by both.
- Android 15 / API 35 accepted the signed in-place upgrade from build **192** to
  **193**, reported version code **193**, and launched without a fatal app
  exception. The emulator remained on the safety acknowledgement screen, so
  the bottom navigation was not visually inspected in the running app.
- Release compilation passed. Unit test suites were not run for this
  visual-only update.
- `git diff --check`: **passed**.

## Debug-log triage

The release build reported the existing deprecated `requestSingleUpdate` call
in `SpeciesScreens.kt`. The post-launch AndroidRuntime log contained no fatal
app exception. No production logging was added.

## Artifacts

| Artifact | Bytes | SHA-256 | Distribution |
| --- | ---: | --- | --- |
| `dist/HikeJournal-v0.8.49.apk` | 63,781,688 | `55b7e093a0ad94f722135761a02637e0f18f8142e69df42cdecc06850d3ee960` | Verified APK; GitHub release attachment |
| `dist/HikeJournal-v0.8.49.aab` | 30,931,261 | `eaa38fe82753aff1c6bba0500c84b8dd6e626547d10c4780798ca61115f3e02a` | Verified AAB; GitHub release attachment |

Detailed notes: [`docs/release-notes/0.8.49-android-bottom-navigation-shapes.md`](../../release-notes/0.8.49-android-bottom-navigation-shapes.md).
