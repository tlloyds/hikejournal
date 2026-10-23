# HikeJournal v0.8.49 release evidence

**Release scope:** Android and iOS. The GitHub release distributes the signed
Android APK. iOS is built, tested, and archived locally; there is no App Store
Connect/TestFlight upload. API, Web, and shared server behavior have **No
functional changes**.

## Changes and versions

- Improve the identification-safety acknowledgment, its Settings copy, and
  short identification reminders on both native platforms.
- The bundled Source Sans 3 variable font defaults to weight 200 (ExtraLight),
  and Cormorant Garamond defaults to weight 300 (Light). Explicit weight-axis
  selection now produces medium body text and semibold warnings/headings,
  rather than relying on a weight label applied to the same light font face.
- Use 18sp/pt body text, 15sp/pt reminder text, increased line spacing, a clean
  white-to-pale background, near-black ink, and a 640dp/pt maximum reading width.
- Underline the guidance link, strengthen the checkbox border on Android, and
  retain readable disabled acknowledgment-button labels. Buttons accommodate
  wrapping and have a minimum height of 56dp/pt.
- iOS uses adaptive light/dark palettes and scaled font sizes, responds to Bold
  Text, and respects Reduce Motion for the button's press animation.
- Photo-review reminders use fully opaque foreground colors.
- Notice wording, acknowledgment behavior, and notice version **1** are unchanged.
- Canonical `VERSION` / Android `versionName`: **0.8.49** (previously 0.8.48).
- Android `versionCode`: **184** (previously 183).
- iOS `MARKETING_VERSION`: **0.8.49**, `CURRENT_PROJECT_VERSION`: **21**
  (previously 20).
- Android GPS-safe original-media browsing and media permissions are unchanged.

## Contrast measurements

Ratios use the WCAG sRGB relative-luminance formula and the lower-contrast end
of each background gradient. The chosen text palettes exceed the 7:1 ordinary
text threshold described in W3C's
[Understanding Contrast (Enhanced)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-enhanced.html).
W3C also notes that thin fonts can appear faint despite a passing nominal
contrast ratio, which is why this change addresses the actual font weight too.
This is a palette assessment, not a complete WCAG audit of the application.

| Text / state | Foreground / background | Contrast |
| --- | --- | --- |
| Light notice body | `#101A14` / `#F4F6F0` | 16.35:1 |
| Light guidance link | `#164D33` / `#F4F6F0` | 9.00:1 |
| Dark iOS notice body | `#F4F8F0` / `#1A241D` | 14.86:1 |
| Dark iOS guidance link | `#C3E7CC` / `#1A241D` | 11.89:1 |
| Light enabled button | `#FFFFFF` / `#183A2D` | 12.49:1 |
| Dark iOS enabled button | `#122018` / `#C4DEC8` | 11.75:1 |
| Light disabled button | `#344237` / `#D9E0D7` | 7.87:1 |
| Dark iOS disabled button | `#EFF4EB` / `#344037` | 9.72:1 |
| Reminder on light parchment | `#101A14` / `#F4F0E5` | 15.63:1 |
| iOS photo reminder | `#FFFFFF` / `#18221C` | 16.35:1 |

## Validation

- Android Debug and Release unit suites: **183 passed each**, zero
  failures/errors/skips.
- Android Release lint: **passed**, zero errors, 61 warnings and one hint.
- Android 15 / API 35 instrumentation: **6 passed** at normal text scale,
  covering acknowledgment gating/Settings display and keepsake sharing/export.
  The **3 acknowledgment tests passed again at 200% text scale**, including
  scrolling to the acknowledgment and continuing successfully.
- Android screenshots reviewed at normal and 200% text scale: heavier text,
  clear foreground/background separation, wrapped button label, and scrollable
  notice content.
- iOS Debug simulator build and hosted XCTest: **81 passed**, zero
  failures/skips, on iPhone 17 Pro / iOS 26.5 with Xcode 26.6.
- iOS notice screenshots reviewed in light/dark appearance at the default
  `large` Dynamic Type size and in light appearance at
  `accessibility-extra-large`: text wraps without horizontal clipping and the
  acknowledgment button label remains readable.
- iOS Release device archive: **passed** at
  `/tmp/HikeJournal-v0.8.49.xcarchive`, with signing disabled for local
  validation. This is not an iOS distribution artifact.
- Mobile API/config/contract tests: **96 passed**, one existing
  Starlette/AnyIO deprecation warning.
- `./build_android.command personal`: **passed**. APK release verifier:
  **PASS, no findings**, package `com.hikejournal.app`, version `0.8.49`,
  build `184`, target SDK `36`.
- Strict AAB signature verification and permanent signer checks: **passed**
  before canonical artifact promotion.
- APK signing-lineage verification: **passed** for API 26–27 (previous
  certificate, v2) and API 28–36 (permanent certificate, v3).
- Android 15 / API 35 accepted an **in-place update from signed build 183 to
  184**. The updated package reports version `0.8.49`, launches successfully,
  and displays the safety notice. Post-upgrade AndroidRuntime and ANR logs show
  no app fatal exception or HikeJournal ANR.
- iOS canonical version validation and `git diff --check`: **passed**.

## Android artifacts

| Artifact | Bytes | SHA-256 | Distribution |
| --- | --- | --- | --- |
| `dist/HikeJournal-v0.8.49.apk` | 63,444,928 | `695e560c0edf6aba031af6edcd42c774d071d76f79cbb41d5d7aadff617fb4f0` | Verified signed release APK; GitHub release attachment |
| `dist/HikeJournal-v0.8.49.aab` | 30,529,862 | `689ad64034d681ce6c4e7f4574a2bdebb356ed531b48d53ddc4255a30b7c2d3d` | Verified signed release AAB; retained locally |

Permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Debug-log triage

No production logging was added. Android retains existing one-shot location
deprecation and SharedPreferences KTX style warnings. A transient Kotlin daemon
startup termination during validation recovered automatically; the full build
and tests completed successfully. Xcode retains unrelated unnecessary `try`
warnings and skipped AppIntents metadata extraction. API tests retain one
Starlette/AnyIO deprecation warning. No physical-device log bundle was supplied.
The signed release-app upgrade/smoke check recorded no app fatal exception or
ANR.
