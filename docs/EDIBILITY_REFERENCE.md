# Edibility & Ethnobotany

The Android Field Guide shows cited food, toxicity, and traditional-use records for exact, confirmed vascular plant taxa. Private photo viewers can show an optional per-tag indicator. The setting defaults off. The first-use identification safety acknowledgment remains available from Settings. The passive photo and species views show evidence beside the relevant plant part.

## Source and mapping audit

The pinned release is *World Checklist of Food Plants 2026 (WCFP): Data*, Diazgranados, Gianella, Kor, Gori, Khoury, Gora et al., Royal Botanic Gardens, Kew, deposited on Figshare, version 2. Figshare's versioned metadata identifies the archive and grants CC BY 4.0. Its computed and supplied MD5 both match the downloaded archive. HikeJournal also pins the locally computed SHA-256 in the [source manifest](../data/wcfp-source-v2.json). Attribution to all authors, the DOI, license, and HikeJournal's selection and matching changes travel with the API profile. [Release metadata](https://api.figshare.com/v2/articles/31441615/versions/2) · [Archive DOI](https://doi.org/10.6084/m9.figshare.31441615.v2) · [Checklist portal](https://wcfp.hpc4ai.unito.it/about) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

The archive includes `WCFP.xlsx` with `WCFP`, `Data descriptors`, and `References` sheets, a distribution CSV, and analysis code and inputs. The importer reads only the published `WCFP` sheet and the WCVP taxonomy snapshot documented in `Code/README`. The README credits Govaerts, Nic Lughadha, Black, Turner and Paton and explicitly licenses that snapshot under CC BY 4.0. No other archive files or third-party works cited by the checklist are republished. The raw archive stays outside Git and the Android binary. [WCVP citation](https://doi.org/10.1038/s41597-021-00997-6)

| Source fields | HikeJournal mapping |
| --- | --- |
| `WCFP_ID`, `LSID_accepted`, `Link` | Release-scoped record key, source identifier, provenance URL |
| `taxon_name_accepted`, `taxon_authors_accepted`, `family` | Original taxonomic identity plus normalized lookup name. Exactly one accepted WCVP entry must agree on LSID, name, authority, and family to supply a rank. |
| `kingdom`, `phylum` | Only `Plantae` / `Tracheophyta` is in scope. |
| `human_food`, `references_food` | The explicit human-food flag and nonempty food citation are required. Animal food, medicines, and the other categories do not qualify. |
| `poisons`, `references_uses` | A record of use as a poison and broad non-food citations. Android shows this under Sources & notes because the category gives no plant part, exposure, or circumstances. |
| `cultivated_GRIN` | Optional context that GRIN lists the taxon as cultivated. This supplies no cultivar-specific applicability. |
| WCVP `plant_name_id`, `taxon_rank`, hybrid flags | Provenance and rank validation. Hybrids, graft-chimaerae, and unverified ranks are retained for audit and excluded from automatic profiles. |

The workbook does not describe food parts, preparation, conditional food use, or hazard severity. Unflagged toxicity remains unknown. The distribution file describes occurrence. It cannot establish where food use occurred. The database release allowlist remains WCFP. The API also reads the independent, reviewed plant-part catalog described below.

### Plant-part review

The [reviewed catalog](../hike_journal/services/edibility_parts.json) ships with the API. It contains 58 plant-part findings, 14 traditional-use records, and six supplemental citations across 50 vascular-plant species. Every mapped ID was verified against a unique, active iNaturalist exact scientific name and rank. Records bind to the confirmed observation's ID, scientific name, and rank. A catalog entry can provide evidence even when the checklist has no match.

Edibility and hazards are attached to the named plant part. Qualifiers preserve growing region, plant variety, maturity, and exposure when the source specifies them. A broad food listing displays **Used as food** and explains that the part and conditions are unknown. **Not edible** requires explicit evidence. Missing evidence, a higher-rank ID, and an expired cached reference have distinct messages. Historical medicine and other cultural uses have their own group, with citations and context where available. Preparation procedures, dosage, and efficacy claims are outside the catalog.

The Field Guide labels reviewed edible parts **Edible** and shows a separate hazard label when applicable. The **Edible** filter includes confirmed plants with documented human food use, including conditional and checklist-only findings. Those retain qualified labels. The detail page explains which parts the food and toxicity findings apply to.

The v0.10.0 production guide audit matched 417 visible plant entries. At release, 38 had plant-part findings, 100 had checklist-only findings, 273 had no exact reference, and six were identified above the species level. The v0.12.0 reviewed catalog and supplemental index together reach 203 of the 410 distinct species-level identities checked. This includes 196 identities from the supplemental index and 48 from the reviewed catalog, with overlap. The existing WCFP food checklist contributes additional coverage.

### Additional source review

The [supplemental index](../hike_journal/services/ethnobotany_cross_references.json) publishes 256 cross-references. Kew supplies 176 checklist entries and USDA supplies 1,388 cited Duke rows grouped across 80 species. HikeJournal checked species rank, family and the unique active iNaturalist name before publishing each match. These references appear alongside the original publications under **Sources & notes**. A checklist's broad use categories and archive row counts give readers a place to start. Food and toxicity labels rely on the human-food checklist and reviewed part evidence.

| Source | Audit and use |
| --- | --- |
| [USDA Ag Data Commons, Dr. Duke’s Ethnobotanical Databases](https://doi.org/10.15482/USDA.ADC/1239279) | CC0. The index preserves cited archive row IDs and bibliography keys. Five manually reviewed historical records also appear with their original citations. Chemistry, bioactivity, efficacy fields, and dosage tables are excluded. |
| [Kew World Checklist of Useful Plant Species](https://doi.org/10.5063/F1CV4G34) | CC BY 4.0. The index preserves use categories, PDF page, IPNI ID, and available bibliography numbers. The categories can include food, medicine, materials and other uses. |
| [UF/IFAS circular on 50 Florida plants](https://agris.fao.org/search/en/providers/122436/records/67598320c7a957febdf9ed2b), [UF/IFAS toxic weeds](https://ask.ifas.ufl.edu/publication/EP631/pdf), and [Florida Poison Control](https://floridapoisoncontrol.org/poisoning-in-florida/plants/) | Reviewed regional references document material uses of cabbage palm, historical uses of white crownbeard, and exposure-specific toxicology for pokeweed and Brazilian pepper. |
| [USDA NRCS plant guides](https://plants.usda.gov/DocumentLibrary/plantguide/pdf/pg_tyla.pdf), [USDA GRIN](https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail?id=8516), and the [European Medicines Agency](https://www.ema.europa.eu/en/medicines/herbal/passiflorae-herba) | Reviewed references add cattail food and craft details, Spanish moss dollmaking, a historical citation for American beautyberry, and the scope of the passionflower herbal monograph. |
| [MedWEP v1](https://doi.org/10.6084/m9.figshare.29190707.v1) | CC BY 4.0. Eleven species-name candidates. Use the references to check region and plant part. The reviewed hedge bindweed entry cites the primary [Sicilian field survey](https://doi.org/10.1186/s13002-015-0074-7). |
| [NIH NCCIH plant summaries](https://www.nccih.nih.gov/health/herbsataglance) and [USDA Forest Service species reviews](https://research.fs.usda.gov/feis/species-reviews) | Exact-name sources for manually reviewed facts. Included examples are the historical medicinal use of passionflower and the use of wax myrtle in candle making. |
| [Global Vegetable Species v1](https://doi.org/10.6084/m9.figshare.30556073.v1) and [Edible Plant Parts v1](https://doi.org/10.6084/m9.figshare.30556082.v1) | Both CC BY 4.0. The first matched 24 guide species and has no plant-part columns. The parts workbook covers 79 crop rows and matched two guide species. |
| [Native American Ethnobotany Database](https://naeb.brit.org/) and [Food Plants International](https://foodplantsinternational.com/) | Potential leads for original publications and community context. Bulk reuse terms for the original collections remain unverified. Indigenous use records should retain the community and source where documented. |

Archive fingerprints used for this review include Duke ZIP SHA-256 `ff325bc477c355799d12194e2d172c9e181ba44e59056c5ca97f41db595b7d19`, Kew PDF SHA-256 `626027154ce7d2a4a45bc6130f94becd6123f443aa2afa6d691f33c3ce239ecb`, and MedWEP XLSX SHA-256 `2d754334bc768302e203f08f6126abb463fccbe0be59b8f4af86f51e0db188b1`.

To rebuild the supplemental index, supply a JSON array of exact `taxon_id` and `scientific_name` targets, including the prior index targets you want to revalidate. The script verifies archive hashes and current iNaturalist identities. Keep the source downloads and any private journal export outside Git. Review the output and publish the citation-only index with the API.

```sh
uv run --with-requirements requirements.txt --with pymupdf==2.1 \
  python scripts/build_ethnobotany_cross_references.py \
  --kew-pdf /tmp/kew-checklist.pdf --duke-zip /tmp/duke.zip \
  --taxa /tmp/taxonomy-targets.json --output /tmp/ethnobotany-cross-references.json
```

### Newly confirmed plants

The API checks for references when a plant ID is confirmed and when the private Field Guide opens or refreshes. Recent confirmations get priority. If the lookup is still running, opening the species detail or refreshing the guide again picks up the result. No account setup or per-hike import is needed. IDs and scientific names sent to iNaturalist are public taxonomic identifiers. The shared lookup table contains no journal entries, locations, or account details.

The lookup checks the active WCFP release and a pinned candidate catalog covering 43,707 scientific names from Kew and USDA. Each positive match requires a current, active vascular taxon and the same rank and family. Automatic name matching also requires exactly one active iNaturalist taxon for that name. Persisted manual WCFP reviews retain their existing precedence. A missing record is cached and checked again after 14 days of elapsed time when the guide is used. An interrupted lookup can retry after its short database lease. Regional extension references and primary studies are still reviewed per claim, with citations and community context where documented.

Regenerate the shared candidate catalog when either published archive changes. Validate the sources and update the pinned fingerprints before running the importer for a new edition.

```sh
uv run --with-requirements requirements.txt --with pymupdf==2.1 \
  python scripts/build_ethnobotany_cross_references.py \
  --kew-pdf /tmp/kew-checklist.pdf --duke-zip /tmp/duke.zip \
  --candidate-index --output hike_journal/services/ethnobotany_candidates.json.gz
```

To add or withdraw a reviewed finding, edit the version-controlled catalog and deploy the API. The API includes a digest of both source files in the dataset version, which invalidates cached references on refresh. These references are available independently of the active WCFP release and have the same maximum 24-hour Android cache lifetime. `EDIBILITY_ENABLED=false` suppresses all three sources.

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

## Production rollout

On November 15, 2026, Cloud Build deployed the code from `v0.9.0` to Cloud Run. The additive migration was applied in Supabase and WCFP v2 was imported as an inactive release. The rollout audited the confirmed journal taxa before activating the dataset. The production import verified all 26,377 source rows. Exact matches preserve source attribution and independent poison-use warnings. Unresolved and ambiguous matches have no profile.

Cloud Run revision `hikejournal-git-00279-kdv` serves the API with `EDIBILITY_ENABLED=true`. The readiness endpoint returned HTTP 200 with all four dependencies healthy. Production reference reads and mobile payload serialization were checked with documented use, a warning, and an unconfirmed observation. Android build 204 already contains the UI. [Readiness endpoint](https://hikejournal-git-1048881557935.us-east1.run.app/health/ready)

## Development and staging workflow

Use a disposable local or explicitly selected staging database and a service-role credential for that database. The write commands require an explicit URL and read only `EDIBILITY_IMPORT_SERVICE_KEY` for database authentication. Keep `EDIBILITY_ENABLED=false` during data setup. This document records the procedure for a future staging environment.

1. Apply [the initial reference migration](../sql/taxon_edibility_migration.sql) after the base journal and taxonomy migrations. Apply [the automatic lookup migration](../sql/taxon_edibility_auto_lookup_migration.sql) before rolling out automatic lookups.
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

4. Review the coverage counters and investigate unsupported and ambiguous rows. Repeat with `--write` to persist the audit decisions and profiles. A completed batch prints a resumable `after_taxon_id` cursor. Continue with `--after-taxon-id <cursor>`. Each batch publishes changes for one release atomically, including the removal of previously matched profiles where applicable. Use this command for staging, bulk audits, and targeted corrections. An explicit `--taxon-ids` pass verifies a targeted ID fresh, even if an older observation enrichment was a negative prefilter.

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
| Private species list and detail | Additive `edibility`, `edibility_reference_enabled`, and `edibility_dataset_version`. A reference can carry `traditional_uses` and `cross_references` independently of food and toxicity fields. Each supplemental reference has a source URL, a short summary, and a publication or archive locator where available. Mixed-rank or mixed-identity groups carry individual exact references in `edibility_by_taxon` when available. |
| Private hike, everyday and encounter photos | A nullable profile on each confirmed exact tag. No food-use payload is populated on candidates, unconfirmed observations, review queues, shared assets, or public discovery/map results. |
| Missing migration, disabled flag, release withdrawal or failed lookup | The journal still opens. A disabled flag or failed lookup suppresses reference data. With WCFP withdrawn, reviewed catalog evidence remains available. Without an exact match, the detail explains the evidence gap or the unresolved rank. |
| Source changes | The API reads one active release per response, with no process-wide reference cache. Android keeps the latest version learned from refreshed responses and suppresses cached data from another version. Reads started before a newer refresh cannot restore its version. |
| Offline | Existing JSON caches retain the exact taxon and dataset version. Cached reference data expires after at most 24 hours from the last server read. WCFP profiles are suppressed after 30 days without taxonomic revalidation. Source withdrawal takes effect on a relevant refresh or expiry. |
| Changes to a photo ID | A persistent local cutoff suppresses responses started before an assignment, review decision, tag removal, or photo deletion. Successful sync advances that cutoff again. A fresh journal read supplies the new per-tag reference when an exact profile exists. |

The Android app reads exact references from the HikeJournal API. The backend reads profiles in chunks of up to 200 distinct IDs from already visible rows. A bounded server worker contacts the public iNaturalist taxonomy API for due taxa after confirmation or on a Field Guide read. Cached results and the reviewed catalog remain available if a lookup is slow or the provider fails. Under the flag, species list/detail bypass the existing process-level observation cache to use current assignments across API workers. The protected OpenAPI fingerprint remains unchanged because these additive response objects use the existing untyped dictionary shapes. Ecology and existing species identity fields are preserved.

## Verification and outstanding work

- The conversational Android and API update passed 590 Python tests, 195 Android JVM tests, and 49 Android 15 emulator tests. Debug lint reported zero errors. All 48 catalog mappings resolved to distinct, active iNaturalist taxa at the documented rank.
- `uv run --with-requirements requirements.txt --with openpyxl==3.1.5 pytest -q` passed 586 tests with one Starlette dependency deprecation warning.
- From `android/`, `./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug :app:connectedDebugAndroidTest` passed 191 JVM tests and 44 Android 15 emulator tests. Debug lint reported zero errors, 61 warnings and two hints. The debug APK built with an isolated application ID so the existing emulator installation could stay in place. An existing share test was corrected to scroll through the lazy list before looking up an off-screen control.
- The migration was applied twice in local PGlite. Local checks covered incomplete and staged release activation, duplicate import, stale assessments and attempts to omit a prior manual review, rollback, withdrawal, exact joins, and service-role restrictions. The local full data load used the validated normalized archive and did not connect to Supabase.
- The production import and confirmed-taxon audit passed, including direct checks of the source records behind each poison-use warning. A physical-device test with an authenticated account and representative endpoint latency measurement remain open. Profiles expire 30 days after validation. Automatic revalidation occurs during journal use. The existing acknowledgment and foraging warning continue to apply to the educational reference.
- iOS and web UI parity and fungi are outside this implementation. Onboard each additional dataset with its own reviewed license, mappings, evidence semantics, version, and tests.
