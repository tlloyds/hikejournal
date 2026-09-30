# HikeJournal 0.8.45 release evidence

**Release scope:** Android and API. No iOS or Web artifacts.

**Release tag:** `v0.8.45`.

## Changes

- Android archive and species-page requests now avoid repeat reads and
  unnecessary database columns while retaining explicit refresh, photo/route
  paging, and the original media workflow.
- API archive responses use compact database-side summaries. Everyday
  sightings honors the Android header-only request and returns standalone
  photos in bounded pages.
- Supabase production functions were installed from
  `sql/mobile_egress_summaries_migration.sql` before the API rollout. The SQL
  editor reported success; PostgREST schema reload was requested.

## Versions

- Canonical `VERSION`: `0.8.45` (previous: `0.8.44`).
- Android `versionName`: `0.8.45`.
- Android `versionCode`: `176` (previous: `175`).
- iOS marketing version metadata was synchronized to `0.8.45`; iOS build number
  was not changed and no iOS artifact was built.
- Web: no functional changes.
- Shared code: no functional changes.

## Validation

- `tests/test_mobile_api.py`: 80 passed.
- `uv run --with-requirements requirements.txt pytest -q`: 540 passed, 1 warning.
- Android `:app:testDebugUnitTest` and `:app:testReleaseUnitTest`: passed,
  175 tests across 49 suites in each variant.
- Android `:app:lintRelease`: passed.
- `./build_android.command personal`: passed. Canonical APK/AAB promotion passed.
- Release APK verifier: passed with no findings. Strict AAB signature
  verification and permanent signer identity checks: passed.
- Signing lineage was applied. Android 15 (API 35) accepted an in-place upgrade
  from the prior release (version code `175`) to `176`; `MainActivity` launched
  with no `FATAL EXCEPTION` in the captured runtime log.
- The `main` push deployed through the `deploy-main-to-cloud-run` trigger.
  HTTPS `/health` returned HTTP 200 with `{"status":"ok","service":"hikejournal-mobile","version":"0.8.45"}`.
- `git diff --check` and iOS version validator: passed.

## Artifacts

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.45.apk` | `6aadee6b431c178122578569c2037b868f6086f6372c7a96648a00ee40060048` | Signed canonical release APK; permanent signer verified; attach to GitHub release |
| `dist/HikeJournal-v0.8.45.aab` | `c21e668320e2e15384068b0f8980e9420f5d14850f0815b449e2aaa128a6219d` | Signed release AAB; strict signature verified; not attached |

Expected permanent signer SHA-256:
`93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Egress investigation and debug-log triage

The dashboard showed 6.392 GB uncached egress against the 5 GB quota. The
available PostgREST request logs did not retain enough history to attribute the
reported 644 MB day to a specific route. Code inspection found that the
Android Everyday sightings header request loaded all standalone photos and
observations despite `include_photos=false`, after which Android also fetched
the photos in pages. Archive summary reads enumerated photo rows to compute
counts and covers, and species pages selected review/publishing metadata they
do not display. This release bounds those requests and moves summary
aggregation into compact SQL results. The app's visible data and original
photo quality are preserved. No phone log bundle was supplied and no new
diagnostic logging was added.
