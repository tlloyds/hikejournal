# HikeJournal 0.8.43 Android performance release evidence

**Release scope:** Android + API. iOS and Web have no functional changes and no artifacts are shipped for them.

**Release tag:** `android-v0.8.43-performance` (platform-qualified because the canonical Android/API version remains `0.8.43`).

## Changes

- Render signed-in Species from an account-scoped disk snapshot while the API revalidates the list.
- Keep network fetches outside the shared disk-cache mutex, serialize loads by cache resource, and parse cached JSON off the UI dispatcher.
- Defer Species discovery until Nearby or Quests opens and fetch its two collections concurrently.
- Restrict confirmed observation reads for `/v1/species` and `/v1/hikes` to visible hikes and their unlinked/visible-photo observations.
- Add non-payload Android HTTP, cache read/write/parse, and cache-lock timings.

## Version and artifacts

- Canonical `VERSION`: `0.8.43` (unchanged).
- Android `versionName`: `0.8.43`.
- Android `versionCode`: `168` (previous: `167`).
- Mobile API version: `0.8.43`; no endpoint, schema, or response contract change.
- iOS `MARKETING_VERSION`: `0.8.43`; no iOS build or upload.

| Artifact | SHA-256 | Verification |
| --- | --- | --- |
| `dist/HikeJournal-v0.8.43.apk` | `b2886a160f79f07c2d7a8a7aeb139bccabacee5cd59c2c92456b06c14c960d02` | Signed personal release APK |
| `dist/HikeJournal-v0.8.43.aab` | `043dfc14a399ff7ee522a739907fe18ed9f5afecef8039c86c138fd9580ce201` | Signed personal release bundle |

The expected permanent Android signer SHA-256 is `93:B9:88:87:E3:74:9C:DB:22:D6:3D:ED:7B:40:81:70:6D:D4:B3:8A:5A:0E:22:AA:86:AB:84:F0:24:35:5E:A1`.

## Validation results

- `./build_android.command personal`: passed, including release lint, canonical APK/AAB promotion, APK artifact verification, strict AAB signature verification, and expected signer identity.
- APK Signature Scheme v3 rotation was exercised through signature verification for Android API levels 26–27 (previous certificate) and API 28+ (permanent certificate).
- Android debug and release unit tests: 169 passed in each variant, across 48 suites per variant.
- `tests/test_mobile_api.py`, `tests/test_mobile_auth.py`, and `tests/test_repositories.py`: 121 passed.
- `python3 -m py_compile mobile_api.py hike_journal/services/repositories.py tests/test_mobile_api.py tests/test_repositories.py`: passed.
- `git diff --check`: passed.
- Android compiler warning: existing deprecated location API use in `SpeciesScreens.kt` only.

## Runtime and deployment evidence

No physical-device before/after timing or production log bundle was available. Android logs now include safe HTTP and cache-stage timings for triaging the reported delay. The repository's Cloud Build trigger is configured to deploy on pushes to `main`; this machine has no active `gcloud` project, so the Cloud Run deployment revision and readiness check could not be independently verified here.
