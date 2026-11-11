# Calmer species details, Hikes titles, and search — evidence

Scope: **Android only**. Date: **November 11, 2026** (America/New_York).
Runtime source: `df7656eef4b293882fd1b07876720c82ec64ea3e`. Version: **0.8.49 / build 198** (previously 197).
Shared `VERSION` is unchanged. Tag: `android-v0.8.49-detail-typography`.

iOS, Web, and API: **No functional changes**. No unaffected-platform builds,
artifacts, deployments, or version/build increments.

## Validation

- **3 affected-screen instrumentation checks passed**, Android 15 / API 35.
  Species details used three encounter records. The reminder is outside the
  initial viewport and below the final record; selecting an encounter still
  opens the correct photo. Hikes and Field Guide layouts were also checked.
- Unit tests: **183 Debug + 183 Release passed**.
- Release lint: **0 errors, 59 remaining warnings, 1 hint**.
- Search-icon source audit: **zero remaining material search-icon usages** in
  Android main sources. Search callbacks and field labels are preserved.
- The real weight-350 font retains attribution/license and derivative naming;
  its bytes were verified inside the signed APK.
- `./build_android.command personal`: **passed**. APK release verifier:
  **PASS, no findings**, version **0.8.49**, build **198**, target SDK **36**.
- Strict AAB signature verification and expected permanent signer identity:
  **passed** in artifact-promotion gates.
- APK signatures verified for SDK **26–27** and **28–36**. Both signing-lineage
  entries retain installed-data capability.
- Signed upgrade **197 → 198**: **passed**. App ID and first-install time were
  preserved; launch succeeded with **no AndroidRuntime errors**.
- `git diff --check`: **passed**.

## Visual evidence

- [Species detail introduction](species-detail.png).
- [Three field records and reminder below them](species-records-footer.png).
- [Hikes overview](hikes.png) and [list title](hikes-list.png).
- [Full-width Field Guide search](field-guide-search.png).

[Detailed results](validation.json), [UI test report](ui-tests.xml), and
[checksums](SHA256SUMS) record the validation. Captures use synthetic records
and the supplied reference photograph, without a private account.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `dist/HikeJournal-v0.8.49.apk` | 64,421,222 | `4e2bfdbca3128bd38ff5112f86231563ae3337261e605eb954984fee5223b4e3` |
| `dist/HikeJournal-v0.8.49.aab` | 31,591,419 | `a492234f84d7271a78f29fac731a9b078f1a9b225a625da5ee7c151fdf9c3f0d` |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage

All final targeted checks passed without test failures. Existing
`requestSingleUpdate`/`Locale` deprecations and the remaining lint warnings/hint
persist. The SDK 26–27 verifier retains its expected warning about the newer
signature scheme. No production logging was added. Screens used local synthetic
records and the supplied reference photo, without account writes. The signed
build-197 baseline was restored after debug tests before checking the signed
197 → 198 upgrade. No physical-phone log bundle was supplied.
