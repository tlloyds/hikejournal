# Android 0.8.49 navigation refinement — release evidence

## Scope and revision

- Platform: **Android only**.
- `VERSION` / Android `versionName`: **0.8.49**, unchanged.
- Android `versionCode`: **191** (previous: **190**).
- iOS, Web, and API: no source or build changes.
- Platform-qualified tag: `android-v0.8.49-nav-refinement`.
- Source commit: the commit targeted by `android-v0.8.49-nav-refinement`.

## Build and checks

- `./build_android.command personal`: **passed**.
- APK release verifier: **PASS, no findings**; package
  `com.hikejournal.app`, version **0.8.49**, build **191**, target SDK **36**.
- Strict AAB signature verification and permanent signer identity: **passed**.
- Permanent signer SHA-256:
  `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.
- `apksigner verify --verbose --print-certs` passed with minimum SDKs **26**
  and **28**. The APK signing lineage contains the former Android Debug
  signer and permanent signer; both retain installed-data capability.
- Android 15 / API 35 accepted the signed in-place upgrade from build **190**
  to **191**, reported version code **191**, and launched the app. It reached
  the safety acknowledgment and then Google sign-in setup. The main navigation
  was not reached because emulator setup requires a Google account.
- Android unit tests: **183 Debug passed**, **183 Release passed**.
- `git diff --check`: **passed**.
- AndroidRuntime error filter after install and launch: **no app-process
  exception entries**.

## Debug-log triage

The observed AndroidRuntime entries were normal emulator process startup and
exit messages. No fatal app exception or new production logging was observed.

## Artifacts

| Artifact | Bytes | SHA-256 | Distribution |
| --- | ---: | --- | --- |
| `dist/HikeJournal-v0.8.49.apk` | 63,781,688 | `c62e3fefafa57c9b3d638fec9f55ab12c38e7780fdd1ba732c8a56a6a6a34667` | Verified APK; GitHub release attachment |
| `dist/HikeJournal-v0.8.49.aab` | 30,932,033 | `9b18eb36d6ede61024c882ac320ef99256c2556740472eeea186308e99e92b2c` | Verified AAB; GitHub release attachment |

Detailed notes: [`docs/release-notes/0.8.49-android-nav-refinement.md`](../../release-notes/0.8.49-android-nav-refinement.md).
