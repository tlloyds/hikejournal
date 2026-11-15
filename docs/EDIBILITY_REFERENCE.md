# Edibility & Ethnobotany

The Android Field Guide shows cited human food uses for exact, confirmed vascular plant taxa. Private photo viewers can show an optional per-tag indicator. The setting defaults off. The detail shows food use and toxicity separately, including the limits of the source. The existing identification safety acknowledgment still applies.

## Source and mapping audit

The pinned release is *World Checklist of Food Plants 2026 (WCFP): Data*, Diazgranados, Gianella, Kor, Gori, Khoury, Gora et al., Royal Botanic Gardens, Kew, deposited on Figshare, version 2. Figshare's versioned metadata identifies the archive and grants CC BY 4.0. Its computed and supplied MD5 both match the downloaded archive. HikeJournal also pins the locally computed SHA-256 in the [source manifest](../data/wcfp-source-v2.json). Attribution to all authors, the DOI, license, and HikeJournal's selection and matching changes travel with the API profile. [Release metadata](https://api.figshare.com/v2/articles/31441615/versions/2) · [Archive DOI](https://doi.org/10.6084/m9.figshare.31441615.v2) · [Checklist portal](https://wcfp.hpc4ai.unito.it/about) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

The archive includes `WCFP.xlsx` with `WCFP`, `Data descriptors`, and `References` sheets, a distribution CSV, and analysis code and inputs. The importer reads only the published `WCFP` sheet and the WCVP taxonomy snapshot documented in `Code/README`. The README credits Govaerts, Nic Lughadha, Black, Turner and Paton and explicitly licenses that snapshot under CC BY 4.0. No other archive files or third-party works cited by the checklist are republished. The raw archive stays outside Git and the Android binary. [WCVP citation](https://doi.org/10.1038/s41597-021-00997-6)

| Source fields | HikeJournal mapping |
| --- | --- |
| `WCFP_ID`, `LSID_accepted`, `Link` | Release-scoped record key, source identifier, provenance URL |
| `taxon_name_accepted`, `taxon_authors_accepted`, `family` | Original taxonomic identity plus normalized lookup name. Exactly one accepted WCVP entry must agree on LSID, name, authority, and family to supply a rank. |
| `kingdom`, `phylum` | Only `Plantae` / `Tracheophyta` is in scope. |
| `human_food`, `references_food` | The explicit human-food flag and nonempty food citation are required. Animal food, medicines, and the other categories do not qualify. |
| `poisons`, `references_uses` | An independent poison-use warning and the broad non-food citations. The source gives no exposure, hazardous part, dose, or circumstances. The detail preserves this limit. |
| `cultivated_GRIN` | Optional context that GRIN lists the taxon as cultivated. This supplies no cultivar-specific applicability. |
| WCVP `plant_name_id`, `taxon_rank`, hybrid flags | Provenance and rank validation. Hybrids, graft-chimaerae, and unverified ranks are retained for audit and excluded from automatic profiles. |

The workbook does not describe food parts, preparation, conditional food use, or hazard severity. Unflagged toxicity remains unknown. The distribution file describes occurrence. It cannot establish where food use occurred. The schema supports explicit conditional, disputed, toxicity and parts evidence for reviewed future imports. The current API allowlist includes only WCFP.

Automatic iNaturalist matching requires an active vascular plant, exact scientific name, a unique active exact-name result, the same supported rank, and matching family. An authority mismatch fails if iNaturalist provides an authority. Reviews can override name differences using documented crosswalks or explicitly reviewed applicability, with ID, authority, rank, and family validated again. An iNaturalist synonym link must point from one inactive same-rank taxon to exactly the requested active taxon. Inactive/split taxa and name or family conflicts do not receive a profile. No match is inherited by a descendant or taken from a species group. The records behind ambiguous decisions are preserved in `taxon_edibility_matches`.

### Local results

| Check | Result |
| --- | --- |
| Workbook rows | 26,622 |
| Vascular human-food evidence staged locally | 26,377 |
| Verified publishable rank | 24,986 |
| Unsupported rank or unverified WCVP identity | 1,391 |
| Nonvascular records skipped | 245 |
| Vascular records flagged with a poison use | 808 |
| Nine deliberately selected iNaturalist IDs | Four exact matches, three unsupported/inactive, one missing food record, one unresolved, zero lookup errors |
| Local PostgreSQL evidence table including indexes and TOAST | 44,425,216 bytes (42.4 MiB) |
| Local PostgreSQL read of 200 IDs with four matches | 0.20–0.23 ms median and 0.46–0.63 ms p95 across two runs of 50 warmed reads in PGlite |

Verified positive examples from that sample include `Vaccinium corymbosum` (WCFP record 5374), `Callicarpa americana` (7585), `Quercus virginiana` (8066), and `Phytolacca americana` (7890, poison-use warning). The sample covers selected paths and does not estimate journal-wide match coverage. The latency is local SQL plus local result handling. A managed Supabase round trip and full endpoint latency remain to be measured.

## Development and staging workflow

Use a disposable local or explicitly selected staging database and a service-role credential for that database. The write commands require an explicit URL and read only `EDIBILITY_IMPORT_SERVICE_KEY` for database authentication. Keep `EDIBILITY_ENABLED=false` during data setup. This document records the procedure for a future staging environment.

1. Apply [the additive migration](../sql/taxon_edibility_migration.sql) after the base journal and taxonomy migrations.
2. Download the pinned archive outside the checkout and validate it with a dry run.

   ```sh
   curl -fL https://ndownloader.figshare.com/files/67533435 -o /tmp/wcfp-v2.zip
   uv run --with-requirements requirements.txt --with openpyxl==3.1.5 \
     python scripts/import_food_plants.py /tmp/wcfp-v2.zip --dry-run
   uv run --with-requirements requirements.txt --with openpyxl==3.1.5 \
     python scripts/backfill_taxon_edibility.py --archive /tmp/wcfp-v2.zip --dry-run \
     --taxon-ids 52740 49193 48599 49013 54818 48353 47347 121265 999999999
   ```

3. Stage the evidence, then audit against distinct confirmed journal taxon IDs. The staging import is idempotent and may be resumed by repeating the same command. Partial imports remain inactive. Use the versioned manifest for an independently reviewed new release.

   ```sh
   uv run --with-requirements requirements.txt --with openpyxl==3.1.5 \
     python scripts/import_food_plants.py /tmp/wcfp-v2.zip --stage \
     --supabase-url "$EDIBILITY_STAGING_URL" --batch-size 100
   uv run --with-requirements requirements.txt \
     python scripts/backfill_taxon_edibility.py --supabase-url "$EDIBILITY_STAGING_URL" \
     --version 2 --dry-run --batch-size 25 --limit 500
   ```

4. Review the coverage counters and investigate unsupported and ambiguous rows. Repeat with `--write` to persist the audit decisions and profiles. A completed batch prints a resumable `after_taxon_id` cursor. Continue with `--after-taxon-id <cursor>`. Each batch publishes changes for one release atomically, including the removal of previously matched profiles where applicable. New observations of already matched taxa need only the API's indexed query. Run the backfill periodically to enroll newly encountered taxa and renew mapping validation before profiles age out. An explicit `--taxon-ids` pass verifies a targeted ID fresh, even if an older observation enrichment was a negative prefilter.

   A version-scoped `--reviewed-mappings` JSON file may contain entries like this synthetic example. `manual_review` requires an accountable review of exact applicability. `verified_identifier` also requires the original `source_taxon_id`. `verified_synonym` requires `synonym_taxon_id`. Use `rejected` for an explicit exclusion. Explicit decisions are stored and reused on later backfills of the same release. Supply the file again to amend a decision. New releases require a new mapping audit.

   ```json
   [{
     "record_key": "1",
     "taxon_id": 42,
     "accepted_name": "Example taxon",
     "authority": "A.Author",
     "method": "verified_identifier",
     "source_taxon_id": "100-1"
   }]
   ```

5. After audit, activate and test in staging with `EDIBILITY_ENABLED=true`. Confirm the known/unknown/warning cases, then redo the same reads with the flag off and after source withdrawal.

   ```sh
   uv run --with-requirements requirements.txt \
     python scripts/backfill_taxon_edibility.py --supabase-url "$EDIBILITY_STAGING_URL" --version 2 --activate
   ```

   Roll back by setting `EDIBILITY_ENABLED=false` on all API workers, withdrawing with `--withdraw --version 2`, or reactivating a previous complete release with `--activate --version <previous>`. The release and audit records are retained. Production activation requires explicit approval after the staging, license, coverage, and safety review.

## API and offline behavior

| Surface | Behavior |
| --- | --- |
| Private species list and detail | Additive `edibility`, `edibility_reference_enabled`, and `edibility_dataset_version`. Mixed-rank or mixed-identity groups have no group profile. |
| Private hike, everyday and encounter photos | A nullable profile on each confirmed exact tag. No food-use payload is populated on candidates, unconfirmed observations, review queues, shared assets, or public discovery/map results. |
| Missing migration, disabled flag, release withdrawal or failed lookup | The journal still opens and returns null for food-use data. The UI hides the section when it learns the release is inactive. When a release is active but a taxon has no match, detail shows neutral no-data copy. |
| Source changes | The API reads one active release per response, with no process-wide reference cache. Android keeps the latest version learned from refreshed responses and suppresses cached data from another version. Reads started before a newer refresh cannot restore its version. |
| Offline | Existing JSON caches retain the exact taxon and release ID. Cached reference data expires after at most 24 hours from the last server read. Profiles are also suppressed after 30 days without taxonomic revalidation. Remote withdrawal takes effect on a relevant refresh or expiry. |
| Changes to a photo ID | A persistent local cutoff suppresses responses started before an assignment, review decision, tag removal, or photo deletion. Successful sync advances that cutoff again. A fresh journal read supplies the new per-tag reference when an exact profile exists. |

No food or taxonomy provider is called from the food-use request path or directly from Android. The backend reads profiles in chunks of up to 200 distinct IDs from already visible rows. Under the flag, species list/detail bypass the existing process-level observation cache to use current assignments across API workers. The protected OpenAPI fingerprint remains unchanged because these additive response objects use the existing untyped dictionary shapes. Ecology and existing species identity fields are preserved.

## Verification and outstanding work

- `uv run --with-requirements requirements.txt --with openpyxl==3.1.5 pytest -q` passed 586 tests with one Starlette dependency deprecation warning.
- From `android/`, `./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug :app:connectedDebugAndroidTest` passed 191 JVM tests and 44 Android 15 emulator tests. Debug lint reported zero errors, 61 warnings and two hints. The debug APK built with an isolated application ID so the existing emulator installation could stay in place. An existing share test was corrected to scroll through the lazy list before looking up an off-screen control.
- The migration was applied twice in local PGlite. Local checks covered incomplete and staged release activation, duplicate import, stale assessments and attempts to omit a prior manual review, rollback, withdrawal, exact joins, and service-role restrictions. The local full data load used the validated normalized archive and did not connect to Supabase.
- A hosted staging run, journal-wide match audit, and a physical-device smoke test are pending. Measure managed PostgreSQL and end-to-end endpoint latency with representative journal data. Review high-risk records independently and confirm store disclosures and terms before production activation. The existing acknowledgment and foraging warning continue to apply to the educational reference.
- iOS and web UI parity, additional datasets, fungi, and medically oriented material are outside this implementation. Onboard each additional dataset with its own reviewed license, mappings, evidence semantics, version, and tests.
