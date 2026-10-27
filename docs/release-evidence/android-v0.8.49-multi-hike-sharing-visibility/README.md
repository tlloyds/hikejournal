# HikeJournal Android 0.8.49 multi-hike share visibility release evidence

**Release scope:** Android only. iOS, API, Web, and shared code have **No
functional changes**.

**Release tag:** `android-v0.8.49-multi-hike-sharing-visibility`.

**Base commit:** `3f6890941f3d29fffc6e8495a39e2bdc3262ccda`.

## Cause and correction

The multi-hike action was already inserted below the Trail Keepsake choices and
above the card preview. It used a `TextButton` without explicit icon or text
colors. On the dark-green share background, the default content tint had too
little contrast. The user's screenshot showed the share icon faintly, with the
label unreadable.

Replace the low-contrast text-only treatment with a full-width outlined
button. Set an amber border and explicit amber colors on both the icon and
label. The hit area, same-day eligibility check, and navigation to the
multi-hike picker are unchanged.

## Versions and platform impact

- Canonical `VERSION` / Android `versionName`: **0.8.49**, unchanged.
- Android `versionCode`: **188** (previously **187**).
- iOS: **No functional changes**; version/build metadata unchanged; no build,
  archive, or upload.
- API: **No functional changes**; version/contracts unchanged; no deployment.
- Web: **No functional changes**; no Web artifacts.
- Shared code: **No functional changes**.

## Validation

- `:app:lintRelease`: **passed**, zero errors, 61 existing warnings and one
  hint.
- `./build_android.command personal`, using an isolated build cache:
  **passed**. Canonical APK and AAB were promoted after release verification
  and signing checks.
- APK release verifier: **PASS, no findings**; package `com.hikejournal.app`,
  version `0.8.49`, build `188`, target SDK `36`, expected permanent signer.
- Strict AAB signature verification and permanent signer identity passed in
  the personal build's promotion gates.
- The previous signed APK was downloaded from
  `android-v0.8.49-multi-hike-sharing` and matched its published SHA-256:
  `f8608aaa61e1067a808df4b4ff1586c4e63a2bed919344f1469ed5abf098bfe8`.
- Android 15 / API 35 accepted the in-place signed upgrade from build **187**
  to **188**. App UID **10227** and first-install time
  **2026-10-23 08:53:40** were preserved. The declared `MainActivity` launched
  and remained resumed; the post-launch AndroidRuntime error log was empty.
- `git diff --check`: **passed**.
- Unit and instrumentation test suites were not run. The updated share screen
  was not exercised with an authenticated multi-hike journal on the emulator.

## Artifacts

| Artifact | Bytes | SHA-256 | Distribution |
| --- | ---: | --- | --- |
| `dist/HikeJournal-v0.8.49.apk` | 63,461,312 | `8f9a2c116ebcc205592fc5276dda5f5f17cfff9a9a4c302dd51efb23bc26148a` | Verified signed release APK; GitHub release attachment |
| `dist/HikeJournal-v0.8.49.aab` | 30,592,172 | `5b242a1861ca256d7c816504072a260b0868d0a23f7eec99554a89df9d4baeaf` | Verified signed AAB; retained locally |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage and limits

The installed build 188 launched as the resumed activity after the emulator
upgrade; no AndroidRuntime exception was recorded. Release packaging could not
strip `libandroidx.graphics.path.so` and `libmaplibre.so`, so the build retained
them and completed successfully. No new production logging was added. No
authenticated multi-hike journal session or physical-device log bundle was
available to verify the updated control in a live share session.
