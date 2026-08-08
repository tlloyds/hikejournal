# HikeJournal 0.6.29 Track A candidate evidence

**Captured:** 2026-08-07

**Classification:** working-tree personal-use candidate; not deployed, not
production-signed, and not a Google Play release

This record describes local verification of the changes layered on baseline
commit `528a7e81d7e4` on `main`. The working tree was intentionally uncommitted.
It does not prove that the Supabase migration is installed, the mobile API is
deployed, monitors/alerts are connected, a backup can be restored, or a
permanent signing key exists.

## Version and artifacts

- canonical `VERSION`: `0.6.29`
- Android `versionName`: `0.6.29`
- Android `versionCode`: `89`
- mobile API version: `0.6.29`

Locally generated, ignored artifacts:

| Artifact | SHA-256 | Classification |
| --- | --- | --- |
| `dist/HikeJournal-v0.6.29-debug.apk` | `c26c26ee40667ada00d3a82cfb8b572d1bd8145b5b69776525d6d9cd44eec27c` | Installable development APK; debug-signed/debuggable and intentionally contains the local pairing credential, LAN API URL, cleartext debug policy, and MapLibre demo style. Not release-safe. |
| `dist/HikeJournal-v0.6.29-unsigned.apk` | `06c30593f9f0fc0c68bf3c4e6e7d31ba7758994aab812e6bf7c131262edca7e9` | Minified release-shape APK for static inspection only; unsigned and built with explicit `.invalid` API/web/trail-style hosts. Not installable/releasable. |
| `dist/HikeJournal-v0.6.29-unsigned.aab` | `53278917eae48b41efb95233c8ca9caf527828ea716d616e2d19969a326bbd33` | Unsigned release-shape bundle for inspection only. Not uploadable to Play. |

An older `dist/HikeJournal-v0.6.29.apk` debug artifact remains on this machine
from before filename separation. It is not the final-tree build and must not be
published. New debug builds cannot overwrite the canonical signed-release name.

The development APK verifier reported the expected development warnings and
completed without an artifact-integrity failure. A canonical-name copy of the
unsigned release APK was run through release mode with a test signer pin and
failed only for the intentional unsigned signature and compiled `.invalid`
configuration hosts. The verifier correctly ignores MapLibre's dormant native
demo constant only when it is confined to `libmaplibre.so`; an app-level demo
host remains a release failure. Its
shrunk network-security resource was decoded successfully; it did not contain
a pairing credential or permit cleartext traffic. Both APK inspection and
direct AAB ELF inspection confirmed 16 KB-aligned arm64-v8a and x86_64 LOAD
segments.

## Automated verification

- Full Python suite: `334 passed`.
- Focused API/reliability/contract/artifact set: `135 passed`.
- Android debug and release unit tests: `87 passed` in each variant.
- Android debug and release lint: passed on AGP 8.13.0/API 36. Reports contained
  warnings but no errors; release had no insecure-network or missing-backup-rule
  warning.
- Debug `assembleDebug` through `build_android.command`: passed and artifact
  characterized automatically.
- Minified `assembleRelease` plus `bundleRelease`: passed with explicit HTTPS
  `.invalid` endpoints and trail style, producing only `-unsigned`
  outputs.
- Streamlit bare import: passed.
- Headless Streamlit smoke: `/_stcore/health` returned `ok`; `/` returned HTTP
  200.

## Emulator upgrade smoke

An API 36 arm64 emulator was upgraded in place from 0.6.28/versionCode 88 to
0.6.29/versionCode 89 with `adb install -r`.

- package first-install timestamp was preserved;
- prior local queued/attention state remained visible;
- `MainActivity` became the focused/resumed activity;
- the application process remained alive; and
- logcat and ApplicationExitInfo showed no crash or ANR (only the expected
  package-update termination of the old process).

The screen rendered the Library/offline state. Its LAN connection failure was
expected because the emulator did not have access to the configured personal
companion host. This smoke did not exercise real GPS, media permissions,
Keystore invalidation, upload, iNaturalist publication, or a production API.

## Webapp conclusion

No Streamlit UI change is required for this Track A slice. The full Python
suite, import, and headless HTTP smoke passed. This is regression evidence for
the local source tree, not a migrated shared-database integration test. Mobile
and web still share schema, storage, repositories, models, and some service
code, so future shared changes continue to require web regression checks.

## Blocking release evidence

Before this candidate can become a permanently signed personal release:

1. inventory/export local-only phone state and prove database plus object-store
   restore/reconciliation;
2. apply and verify `sql/mobile_jobs_migration.sql` in the target environment,
   deploy the compatible API, and prove restart/multi-instance recovery;
3. resolve ambiguous iNaturalist create/checkpoint handling and remaining
   synchronous publication durability;
4. choose and protect the permanent signing key, record its certificate
   SHA-256 digest, and rehearse the debug-signature data transition;
5. supply a real HTTPS trail map style and approve provider quota, licensing,
   attribution, privacy, and offline-use terms;
6. connect/test monitoring, alerts, backups, restore, and rollback; and
7. build a signed artifact that passes release verification and the full
   device/feature/failure matrix.
