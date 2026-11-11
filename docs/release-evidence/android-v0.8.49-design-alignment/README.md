# Android 0.8.49 design alignment — release evidence

**Scope:** Android only. **Date:** November 10, 2026 (America/New_York).

- Android version: **0.8.49 / build 194** (previous build 193).
- Canonical `VERSION`: **0.8.49**, unchanged.
- Runtime source commit: `0e04c4174b9f1782b84ede48aa75b902f5de63a3`.
- Release tag: `android-v0.8.49-design-alignment` (targets the final evidence commit).
- iOS, Web, API, shared code: **No functional changes**; no builds/deployments
  or version/build-number changes for those platforms.

## Validation

- Android 15 / API 35 instrumentation: **22 passed** — 14 screen/map/
  celebration checks plus 8 sign-in, state-picker, guide, and safety checks.
  Coverage includes a 320 dp Review header, visible actions and warnings above
  navigation, native map imagery/markers, missing-thumbnail fallback, return
  from background, late map bounds, explicit public-post confirmation, and
  first-run callbacks. Screens use local fixtures and do not write to an account.
- JVM suites: **183 Debug passed** and **183 Release passed**.
- `:app:lintRelease`: **passed**, **0 errors, 61 existing warnings, 1 hint**.
- `./build_android.command personal`: **passed**. APK release verifier:
  **PASS, no findings**; version **0.8.49**, build **194**, target SDK **36**.
- Strict AAB signature verification and permanent signer identity: **passed**
  in the build's promotion gates.
- APK signature verification: **passed** for API **26–27** (previous signer,
  v2) and API **28–36** (permanent signer, v3). Both lineage entries retain
  installed-data capability.
- Signed Android 15 upgrade **193 → 194**: **passed**. App ID and first-install
  time were preserved. The saved safety acknowledgment survived, and the new
  branded setup screen was visible. AndroidRuntime error filter: **no entries**.
- `git diff --check`: **passed**.

The signed-upgrade package app ID was **10253**; first-install time remained
**2026-11-10 23:01:46**. Test names, totals, signatures, upgrade details, and artifact
hashes are in [validation.json](validation.json).

## Visual evidence

[All 18 screens](screens-overview.png) cover Hikes, Field Guide, Review,
Publish, medals, species detail, planning, discovery celebrations, the map,
Google sign-in, state selection, the first-run guide, and the safety entry.
Individual WebP captures are in [screens/](screens/). The photo is a local
fixture derived from the supplied screenshot; no private account is displayed.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `dist/HikeJournal-v0.8.49.apk` | 64,380,206 | `18f798ad35aad0469f570db6779e5e6377fd1f71256ee3c5248b13562c1a9415` |
| `dist/HikeJournal-v0.8.49.aab` | 31,548,356 | `7b34eb8d643b2f7051276de8e2bb85a895483c053f2671261813368153464059` |

Both artifacts passed the permanent signing checks and are intended as GitHub
release attachments. Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage and limits

The existing Android 8.1 navigation-bar attribute was placed in a versioned
style so the Android 8.0 minimum passes lint. The first candidate was held by
the artifact verifier because optional font metadata contained an HTTP designer
website; those URL records were removed, the packaged derivative was given its
own family name, and original copyright/license records and font licenses were
retained. Glyph and metric tables were verified unchanged. The verifier policy
was not weakened. No failed candidate was published.

The existing guide test had one extra Next click for the four-page guide; its
step count is corrected, and the guide and safety suites pass. Emulator
release/debug signature conflicts were resolved before test runs. Existing
`requestSingleUpdate` and unit-test `Locale` deprecations remain. The API 26–27
signature check retains the expected warning about the newer v3 scheme. No
production logging was added, and post-upgrade AndroidRuntime logging is clean.
No physical-phone debug-log bundle or authenticated journal session was
provided; visual and interaction evidence comes from the emulator and fixtures.


Detailed changes: [release notes](../../release-notes/0.8.49-android-design-alignment.md).
