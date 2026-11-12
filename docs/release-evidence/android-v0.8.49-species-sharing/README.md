# Species photo sharing — release evidence

Scope: **Android only**. Date: **November 12, 2026** (America/New_York).
Android **0.8.49 / build 201** (previous build 200).
Shared `VERSION` remains unchanged. Tag: `android-v0.8.49-species-sharing`.

iOS, Web, and API: **No functional changes**. No unaffected-platform builds,
artifacts, deployments, or version/build increments.

## Validation

- Unit tests: **187 Debug + 187 Release passed**, including four new species-sharing tests in each variant.
- Android 15 / API 35 instrumentation: **10 passed** across species and hike sharing. Covers species-detail entry/close, ordered selections and limits, every keepsake position, readable original attachments and captions, missing files, empty-export protection, repeated shares, and render dimensions.
- Final gallery UI checks after adding clipping: **3 passed**, including a visible heading after scrolling/selecting a photo.
- Release lint: **0 errors, 60 warnings (59 existing and one Canvas KTX style suggestion), 1 hint**.
- Visual QA: standard 1080 × 1350 keepsake, 540 × 675 preview, long common/scientific names, picker, and numbered photo selection checked.
- `./build_android.command personal`: **passed**, including release-verifier **PASS / no findings**, strict AAB verification, and permanent signer identity before promotion.
- APK SDK **26–27** and **28–36** signatures: **passed**. Both signing-lineage certificates retain installed-data capability.
- Signed upgrade **200 → 201**: **passed**; first-install time preserved, launcher started successfully, and no AndroidRuntime errors were found.
- `git diff --check`: **passed**.

## Visual evidence

- [Species share picker](species-share-screen.png).
- [Numbered photo selection](species-share-photo-selection.png).
- [Standard keepsake](species-keepsake.png).
- [Small preview](species-keepsake-small.png).
- [Long names](species-keepsake-long-name.png).

Images use the repository's local species photograph with synthetic Swamp
smartweed records. They do not represent a user's actual encounter history.
The production renderer and actual composables generated these images.

## Debug-log triage

Earlier checks exposed a preview/copy overlap and Android 15 dialog sizing around system bars; both were corrected before release. The gallery is clipped to its own scroll region. UI tests were adjusted to locate lazy photo rows inside the dialog, and native screenshots wait for window rendering. The initial debug-test installation conflicted with the installed release signer; the emulator state was saved/restored and the verified build-200 APK was reinstalled before the upgrade check. Final checks passed. The 59 existing lint warnings, one new suggestion to use the Canvas KTX convenience function, and the expected SDK 26–27 newer-signature warning remain. No production logging was added, no account writes or external shares were performed during testing, and no physical-phone log bundle was supplied.

## Verified artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `HikeJournal-v0.8.49.apk` | 64,437,606 | `383c1f252a63dce6573e24ef1526a6b945d435f3eb0de2dbfbcb33eb665fd0d3` |
| `HikeJournal-v0.8.49.aab` | 31,630,725 | `7219d67ab69c8f5a52583b9bcd36ddc5cfcc7f16e38b35c72416c00a5c43e8a5` |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

[Detailed validation](validation.json), [instrumentation](share-instrumentation-tests.xml),
[final gallery checks](final-gallery-ui-tests.xml), [build and release verifier](build-personal.log),
[upgrade](upgrade.json), and [checksums](SHA256SUMS).
