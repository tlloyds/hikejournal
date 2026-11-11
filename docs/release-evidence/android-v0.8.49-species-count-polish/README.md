# Android species count and filter polish — evidence

Scope: **Android only**. Date: **November 11, 2026** (America/New_York).
Runtime source: `ae190c461efe133fe1bb2068ed1d1c63cad6b1a3`. Version: **0.8.49 / build 196** (previously 195).
Shared `VERSION` is unchanged. Tag: `android-v0.8.49-species-count-polish`.

iOS, Web, and API: **No functional changes**. No unaffected-platform builds,
artifacts, deployments, or version/build increments.

## Checks

- Field Guide and Publish instrumentation: **2 passed** on Android 15 / API 35.
  Visual inspection confirmed smaller counts beside the species name and
  regular-weight filter values. Fixtures use the supplied reference photograph
  and synthetic records; no private account writes.
- Unit tests: **183 Debug + 183 Release passed**.
- Release lint: **0 errors, 61 existing warnings, 1 hint**.
- `./build_android.command personal`: **passed**. Canonical signed APK/AAB
  produced; APK release verifier **PASS, no findings**, target SDK **36**.
- Strict AAB signature verification and expected permanent signer identity:
  **passed** in artifact promotion.
- APK signature verification: **passed** for SDK **26–27** and **28–36**.
  Both signing-lineage entries retain installed-data capability.
- Signed upgrade **195 → 196**: **passed**. App ID and first-install time
  remained unchanged; launch succeeded, with **no AndroidRuntime errors**.
- `git diff --check`: **passed**.

## Visual evidence

- [Species screen](species-field-guide.png): smaller count aligned with the
  name and lighter “All hikes”/“All types” values.
- [Publish filter](publish-filter.png): the shared outing value also uses
  regular weight.
- [Detailed results](validation.json), [test results](ui-tests.xml), and
  [artifact checksums](SHA256SUMS).

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `dist/HikeJournal-v0.8.49.apk` | 64,380,206 | `f5b756f7fe09563e37bbf25f9cc879c2222ccda081ddd77d511cce730e3f18e6` |
| `dist/HikeJournal-v0.8.49.aab` | 31,549,723 | `ec1aa4b9c943e254129b88e96818fade058bd23c4cb086d77d0665ad13d24ff3` |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage

The first instrumentation attempt could not install the debug test app over
an existing permanently signed release. The test runner cleaned up that
installation; the subsequent two-test run passed. The signed build-195 baseline
was then restored before independently checking the signed 195 → 196 upgrade.
This was a test setup/signature mismatch, not an app test failure.

Existing `requestSingleUpdate`/`Locale` deprecations and the existing lint
warnings/hint remain. The SDK 26–27 verifier retains its expected warning about
the newer signature scheme. No production logging was added, and no new
runtime crash was observed. No physical-device log bundle was supplied.
