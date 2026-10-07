# HikeJournal 0.8.46 release evidence

**Release scope:** Android and API. No iOS or Web artifacts.

**Release tag:** `v0.8.46`.

## Changes

- Android now loads a compact count/extent summary and requests viewport-bound
  photo features as the user pans or zooms. Dense areas render as clusters that
  zoom in on selection.
- The API adds owner-scoped summary and viewport routes. Their PostGIS RPCs
  resolve all visible hikes directly, include standalone photos, aggregate at
  broad zoom levels, and cap the rendered response at 2,500 features. This
  avoids the same default row cap truncating a very large hike list.
- Authenticated `/v1/config` advertises `viewport_map_photos` after the
  production functions are installed.
- The previous first-100 limitation came from the PostgREST response cap on an
  unpaginated map sightings query. The old Android flow also kept that initial
  response instead of reloading for new camera bounds.
- Production Supabase installed the additive RPC migration from
  `sql/mobile_map_viewport_migration.sql` through the SQL editor. An initial
  run surfaced an aggregate `GROUP BY` error and rolled back; the corrected
  migration completed successfully. Empty-scope function smoke tests returned
  zero photos and an empty feature collection. The grants query confirmed the
  functions are executable by `service_role` and not by `anon` or
  `authenticated`.
- The current Free plan did not provide scheduled backups, and Point in Time
  Recovery was shown as a Pro-plan add-on. This migration only creates additive
  functions and changes no user rows; the matching rollback is included at
  `sql/rollback_mobile_map_viewport_migration.sql`.

## Versions

- Canonical `VERSION`: `0.8.46` (previous: `0.8.45`).
- Android `versionName`: `0.8.46`.
- Android `versionCode`: `179` (previous: `178`).
- iOS marketing version metadata was synchronized to `0.8.46`; iOS build
  number was not changed and no iOS artifact was built.
- Web: no functional changes.
- Shared user-facing behavior: no functional changes outside Android map.

## Validation

- Python full suite: pending.
- Python full suite: 556 passed, 1 Starlette/AnyIO deprecation warning.
- Android `:app:testDebugUnitTest` and `:app:testReleaseUnitTest`: passed,
  179 tests in each variant.
- Android `:app:lintRelease`: passed.
- `./build_android.command personal`: passed. Release APK and AAB were
  promoted after signature checks.
- APK release verifier: passed with no findings. Strict AAB signature
  verification and permanent signer identity checks: passed.
- Android 15 (API 35) accepted an in-place update from version code `178` to
  `179` using the permanent signing identity. The app launched with no
  `FATAL EXCEPTION` in the captured runtime log window.
- Production API deployment, `/health`, and authenticated config capability
  verification: pending after the main push.
- `git diff --check` and iOS version validator: passed.

## Artifacts

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.46.apk` | `b3e04e6718a95ca3e1e9bbbefda960a4fb5d5af8797a00138d4019c2a7c40b97` | Signed canonical release APK; attach to GitHub release |
| `dist/HikeJournal-v0.8.46.aab` | `6c21cfa7878d28be02b7049f7a49b79f100d51ffeab0208cd5ecd2c448e4cdfc` | Signed canonical release AAB; strict signature verified; not attached |

Expected permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.
