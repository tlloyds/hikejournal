# Trail Keepsake branding — release evidence

Scope: **Android only**. Date: **November 11, 2026** (America/New_York).
Runtime source: `7d8cb7d08fc9110e243db69296bc597fdcf5136a`. Version: **0.8.49 / build 200** (previously 199).
Shared `VERSION` is unchanged. Tag: `android-v0.8.49-keepsake-branding`.

iOS, Web, and API: **No functional changes**. No unaffected-platform builds,
artifacts, deployments, or version/build increments.

## Validation

- Production-exporter preview: **1 passed**, Android 15 / API 35. Rendered
  actual satellite imagery with a synthetic sample route, the standard
  1080 × 1350 export, a 540 × 675 preview, and a long hike title. All three
  images were visually checked; the standard preview was approved before commit.
- Share-preparation instrumentation: **2 passed**, including keepsake-first,
  keepsake-last, and no-keepsake photo ordering/limits, and the empty-share guard.
- Unit tests: **183 Debug + 183 Release passed**, including **9 share tests**
  in each variant covering carousel ordering, photo limits, route bounds,
  satellite style/endpoints, date, distance, and active duration.
- Release lint: **0 errors, 59 existing warnings, 1 hint**.
- `./build_android.command personal`: **passed**. APK release verifier:
  **PASS, no findings**, version **0.8.49**, build **200**, target SDK **36**.
- Strict AAB signature verification and expected permanent signer identity:
  **passed** in artifact-promotion gates.
- APK signatures verified for SDK **26–27** and **28–36**. Both signing-lineage
  entries retain installed-data capability.
- Signed upgrade **199 → 200**: **passed**. App ID and first-install time were
  preserved; launch succeeded with **no AndroidRuntime errors**.
- `git diff --check`: **passed**.

## Visual evidence

- [Approved standard export](trail-keepsake-preview.png), 1080 × 1350.
- [Small in-app preview](trail-keepsake-preview-small.png), 540 × 675.
- [Long hike-title export](trail-keepsake-long-title.png), 1080 × 1350.

These images came from the production `renderHikeShareCard` exporter and its
actual satellite snapshot path, using a synthetic sample route/hike in the
Bronson State Forest area. They are design-review samples, not a user's hike
history. The preview was approved before committing the implementation.

[Detailed results](validation.json), [share-preparation tests](share-preparation-tests.xml),
[preview render test](preview-render-test.xml), and [checksums](SHA256SUMS)
record the checks. The local preview harness is not part of the shipped app.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `dist/HikeJournal-v0.8.49.apk` | 64,421,222 | `1e9f524c791a6cc6c198bdd59831e5dd7ae6e055aeaa36bdaeed422b75ffe2a4` |
| `dist/HikeJournal-v0.8.49.aab` | 31,591,383 | `aa56727d3bd81c97d56df27b984ff5c8a3536c6e564c1793d1a68171fd16e464` |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage

Final validation passed without test failures. The temporary preview runner
initially had a return-type initialization issue; it was corrected before the
successful render, and the local runner was removed from the production tree.
The 59 existing lint warnings and 1 hint remain. The SDK 26–27 signature check
retains its expected warning about the newer signature scheme. No production
logging was added. Previews use a synthetic sample hike/route without account
writes or sharing to another app. The signed build-199 baseline was restored
after debug tests before checking the 199 → 200 upgrade. No physical-phone
log bundle was supplied.
