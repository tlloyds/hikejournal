# Android 0.8.49 typography and Review polish — release evidence

**Scope:** Android only. **Date:** November 10, 2026 (America/New_York).

- Runtime source: `1663f7d76e39978ae20f82c0cf25f1e5c0095e96`.
- Version: **0.8.49 / build 195**, previously build 194. `VERSION` unchanged.
- Tag: `android-v0.8.49-type-review-polish`.
- iOS, Web, API, shared code: **No functional changes**. No artifacts,
  deployments, or platform version/build-number changes for those surfaces.

## Validation

- Android 15 / API 35: **7 affected-screen instrumentation checks passed**.
  Batch ID coverage includes one waiting observation, a suggested observation
  with two other waiting observations, offline disablement, and opening the
  existing planner from an eligible observation. Hikes, Field Guide, Review,
  Publish, a compact Review header, and map photo previews were checked with
  local fixtures, without account writes.
- JVM suites: **183 Debug passed**, **183 Release passed**.
- `:app:lintRelease`: **passed**, **0 errors, 61 existing warnings, 1 hint**.
- `./build_android.command personal`: **passed**. APK release verifier:
  **PASS, no findings**; version **0.8.49**, build **195**, target SDK **36**.
- Strict AAB signature verification and expected permanent signer identity:
  **passed** in the build's artifact-promotion gates.
- APK signature verification passed for API **26–27** (previous signer, v2)
  and API **28–36** (permanent signer, v3). Both signing-lineage entries retain
  installed-data capability.
- Signed Android 15 upgrade **194 → 195**: **passed**. Package app ID and
  first-install time were preserved; the upgraded app launched successfully.
  AndroidRuntime error filter: **no entries**.
- `git diff --check`: **passed**.

App ID remained **10258** and first-install time remained **2026-11-10 23:28:38**.
Detailed test cases, counts, signatures, and artifact hashes are in
[validation.json](validation.json).

## Visual evidence and font provenance

[Screen overview](screens-overview.png) and individual captures in [screens/](screens/)
show the lighter Hikes hierarchy, smaller species names, matched orange labels,
white badge text, observation-level Batch ID, and the map photo date. The local
photo fixture comes from the supplied screenshot; no private account is shown.

The Illustrator metadata explicitly names `Quicksand-Light` and
`Quicksand-VariableFont_wght.ttf`. It does not identify every outlined/rasterized
face. Quicksand is the app's brand/UI family; the editorial serif is the retained
Cormorant Garamond family, not a positively identified Illustrator font.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `dist/HikeJournal-v0.8.49.apk` | 64,380,206 | `f8e3dc9be8540aca1568861daf7c2c1e26c8af2f7b4ea7959310f767918f3a47` |
| `dist/HikeJournal-v0.8.49.aab` | 31,548,868 | `1113f2b6fd1ad3c4a24f4e40863c3cefd5ca59d4a479f24d3de3fc4b041af448` |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage

The existing visual test was updated to expect Batch ID in the observation
instead of the header. The final affected-screen run has no failures. Existing
`requestSingleUpdate` and unit-test `Locale` deprecations remain, as do the
existing lint warnings/hint. The API 26–27 verifier retains its expected warning
about the newer v3 scheme. No production logging was added. No physical-phone
log bundle was supplied; visual and interaction checks used the emulator.


[Detailed changes](../../release-notes/0.8.49-android-type-review-polish.md).
