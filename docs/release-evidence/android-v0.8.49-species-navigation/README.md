# Cleaner species navigation and Hikes shortcuts — evidence

Scope: **Android only**. Date: **November 11, 2026** (America/New_York).
Runtime source: `5b3f9f8db9c362540df01ea063e2b73fb6b4a68d`. Version: **0.8.49 / build 197** (previously 196).
Shared `VERSION` is unchanged. Tag: `android-v0.8.49-species-navigation`.

iOS, Web, and API: **No functional changes**. No unaffected-platform builds,
artifacts, deployments, or version/build increments.

## Checks

- **4 affected-screen instrumentation checks passed**, Android 15 / API 35.
  Coverage includes the short-collection state, common-name and scientific-name
  letter jumps, position jumps under Most recent, sheet dismissal after a
  selection, the absence of the old rail, and the Hikes screen/actions.
- Both Hikes shortcuts fit on a single line with no text overflow in **6 layout
  configurations**: 320, 360, and 393 dp at font scales 1.0 and 1.3. Both actions
  still invoke their existing callbacks.
- Unit tests: **183 Debug + 183 Release passed**.
- Release lint: **0 errors, 59 remaining warnings, 1 hint**.
- `./build_android.command personal`: **passed**. APK release verifier:
  **PASS, no findings**; version **0.8.49**, build **197**, target SDK **36**.
- Strict AAB signature verification and expected permanent signer identity:
  **passed** in artifact-promotion gates.
- APK signatures verified for SDK **26–27** and **28–36**. Both signing-lineage
  entries retain installed-data capability.
- Signed upgrade **196 → 197**: **passed**. App ID and first-install time were
  preserved; launch succeeded with **no AndroidRuntime errors**.
- `git diff --check`: **passed**.

## Visual evidence

- [Full-width species index](species-index.png).
- [On-demand letter choices](jump-sheet.png).
- [Scrolled collection without the rail](species-after-jump.png).
- [Hikes shortcuts](hikes.png).

Compact-width behavior is recorded in the layout assertions and
[validation.json](validation.json); [ui-tests.xml](ui-tests.xml) contains the
four-test result. Captures show synthetic records and the supplied reference
photograph, without a private account.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `dist/HikeJournal-v0.8.49.apk` | 64,380,206 | `4493087e70cf2894046053c572e1dbe9854434123a3a54f0e19a2095d98ef309` |
| `dist/HikeJournal-v0.8.49.aab` | 31,552,229 | `d981a47a87ae829da805aa98fbfccde831723759191eb004d9aaf427ba37d623` |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage

The compact-width check initially reported overflow in the labels’
wrap-content text bounds. Both labels now use their full cell width with
centered text; all six width/font-scale configurations pass without overflow.

Existing `requestSingleUpdate`/`Locale` deprecations and the remaining lint
warnings/hint persist. The SDK 26–27 verifier retains its expected warning
about the newer signature scheme. No production logging was added. Tests used
local synthetic records and the supplied reference photo, with no account
writes. Debug tests ran separately from the signed-release upgrade baseline;
build 196 was restored before checking the 196 → 197 upgrade. No physical-phone
log bundle was supplied.
