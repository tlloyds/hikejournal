# HikeJournal Android 0.8.49 multi-hike sharing release evidence

**Release scope:** Android only. iOS, API, Web, and shared code have **No
functional changes**.

**Release tag:** `android-v0.8.49-multi-hike-sharing`.

**Base commit:** `4e62d1e6fbae904e795627c4d266a3fc4e7e84c5`.

## Change

The share dialog previously prepared one hike card and that hike's selected
photos. The journal now offers a second flow for other saved hikes on the same
date. It keeps the original single-hike path available and starts the combined
flow with the currently open hike selected.

The multi-hike picker loads complete hike details through the repository when
another outing is selected. This supplies that hike's photo list and route for
its preview card without replacing the currently open journal. Photos are
selected independently for each outing and retain the selection order. The
first/last/no-keepsake choice applies to the group: all selected hike cards
appear before or after all selected photos, or no cards are included. Every
card and photo uses one of the existing 20 carousel slots, and videos remain
excluded. The existing GPS-safe phone-original media browser and upload flow
were not changed.

The multi-share chooser is exposed from the current hike's share preview only
when another hike exists for that date. It requires at least two selected
outings, displays one keepsake preview per included hike, and handles photo
download failures using the existing omitted-photo notice.

## Versions and platform impact

- Canonical `VERSION` / Android `versionName`: **0.8.49**, unchanged.
- Android `versionCode`: **187** (previously **186**).
- iOS: **No functional changes**; version/build metadata unchanged; no build,
  archive, or upload.
- API: **No functional changes**; version/contracts unchanged; no deployment.
- Web: **No functional changes**; no Web artifacts.
- Shared code: **No functional changes**.

## Validation

- Android release Kotlin compilation: **passed** as part of lint and the
  personal release build.
- `:app:lintRelease`: **passed**, zero errors, 61 existing warnings and one
  hint. The compiler reported the existing deprecated location update API.
- `./build_android.command personal`, using an isolated build cache:
  **passed**. Canonical APK and AAB were promoted after release verification
  and signing checks.
- APK release verifier: **PASS, no findings**; package `com.hikejournal.app`,
  version `0.8.49`, build `187`, target SDK `36`, expected permanent signer.
- Strict AAB signature verification and permanent signer identity passed in
  the personal build's promotion gates.
- `apksigner verify --verbose --print-certs --min-sdk-version 26` and the same
  command with minimum SDK `28`: **passed**. The APK embeds a signing lineage
  from the Android Debug certificate
  `e5:be:9f:29:c9:22:01:c8:67:19:86:8d:e1:ab:34:04:ba:d2:70:87:6b:41:b2:b6:9c:11:0b:68:9c:73:ac:1c`
  to the permanent release certificate below. Both lineage entries retain
  installed-data capability.
- The build 186 APK downloaded from
  `android-v0.8.49-photo-recommendation-confidence` matched its published
  SHA-256: `380c46b92f5f5ecaef803f0508a734e589da4400238502a8e1a73a398fe0cfd7`.
- Android 15 / API 35 accepted the signed in-place upgrade from build **186**
  to **187**. App UID **10227** and first-install time
  **2026-10-23 08:53:40** were preserved. The declared `MainActivity` launched
  and remained resumed. The post-launch AndroidRuntime error log was empty.
- `git diff --check`: **passed**.
- Unit and instrumentation test suites were not run for this request. An
  authenticated multi-hike journal session was not available for end-to-end
  UI sharing validation.

## Artifacts

| Artifact | Bytes | SHA-256 | Distribution |
| --- | ---: | --- | --- |
| `dist/HikeJournal-v0.8.49.apk` | 63,461,312 | `f8608aaa61e1067a808df4b4ff1586c4e63a2bed919344f1469ed5abf098bfe8` | Verified signed release APK; GitHub release attachment |
| `dist/HikeJournal-v0.8.49.aab` | 30,592,157 | `8eb33b5240d368e86da2585d1a2737f401b62fcc6ca80c1bd1e3baae5d55d941` | Verified signed AAB; retained locally |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage and limits

Immediately after installation, the generic Monkey launch command did not
resolve an activity while Package Manager was updating the package. A
subsequent resolver query found `.MainActivity`; launching it directly
succeeded. No AndroidRuntime exception appeared after launch. Release
packaging could not strip `libandroidx.graphics.path.so` and `libmaplibre.so`,
so the build retained those libraries and completed successfully. No new
production logging was added. No authenticated session, multi-hike UI share,
or physical-device log bundle was available.
