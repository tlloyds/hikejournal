# New-species celebration wording — release evidence

Scope: **Android only**. Date: **November 11, 2026** (America/New_York).
Runtime source: `65ea9a950cf0503c60447c9b4f1bebc00dfe9ac2`. Version: **0.8.49 / build 199** (previously 198).
Shared `VERSION` is unchanged. Tag: `android-v0.8.49-discovery-copy`.

iOS, Web, and API: **No functional changes**. No unaffected-platform builds,
artifacts, deployments, or version/build increments.

## Validation

- New-species celebration instrumentation: **1 passed**, Android 15 / API 35.
  The preview uses the production celebration builder rather than hard-coded
  copy. The new description and Continue action are visible, and Continue
  invokes the existing dismissal callback. The screenshot was visually checked.
- Unit tests: **183 Debug + 183 Release passed**, including the existing
  discovery, badge-unlock, and Welcome Back/rediscovery cases.
- Release lint: **0 errors, 59 remaining warnings, 1 hint**.
- `./build_android.command personal`: **passed**. APK release verifier:
  **PASS, no findings**, version **0.8.49**, build **199**, target SDK **36**.
- Strict AAB signature verification and expected permanent signer identity:
  **passed** in artifact-promotion gates.
- APK signatures verified for SDK **26–27** and **28–36**. Both signing-lineage
  entries retain installed-data capability.
- Signed upgrade **198 → 199**: **passed**. App ID and first-install time were
  preserved; launch succeeded with **no AndroidRuntime errors**.
- `git diff --check`: **passed**.

## Visual evidence

[New-species preview](new-species.png) shows the real production-builder text
for a plant. Statistics retain the plural “Plants” label. The preview uses
synthetic records and the supplied reference photograph, without a private
account. The Welcome Back description and celebration layout are unchanged.

[Detailed results](validation.json), [UI test report](ui-tests.xml), and
[checksums](SHA256SUMS) record the checks.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `dist/HikeJournal-v0.8.49.apk` | 64,421,222 | `c6a4b91bd16c4cd3581c9436ea9311ec72ef16783e9e0aee5e0743d6e3876b30` |
| `dist/HikeJournal-v0.8.49.aab` | 31,591,242 | `affac8d920fa8407cf0a1ab28da94ab4b9f4577759208bcc7896cae4d8651684` |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage

Final checks passed without test failures. Existing
`requestSingleUpdate`/`Locale` deprecations and the remaining lint warnings/hint
persist. The SDK 26–27 verifier retains its expected warning about the newer
signature scheme. No production logging was added. The preview used synthetic
records and the supplied reference photo, without account writes. The signed
build-198 baseline was restored after debug tests before checking the signed
198 → 199 upgrade. No physical-phone log bundle was supplied.
