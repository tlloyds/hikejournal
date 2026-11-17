from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
from hashlib import file_digest
from zipfile import ZipFile
from types import SimpleNamespace

import pytest

import mobile_api
from hike_journal.services import edibility
from hike_journal.services.edibility import (
    EdibilityReference,
    assess_evidence,
    derive_profile,
    load_edibility_reference,
)
from hike_journal.services.inat import InatClient
from hike_journal.services.repositories import HikeJournalRepository
from scripts.backfill_taxon_edibility import assess_batch
from scripts.build_ethnobotany_cross_references import _binding, _duke_records, _kew_records
from scripts.import_food_plants import USE_FIELDS, normalize_evidence, read_verified_archive, stage_release


def plant(**overrides):
    return {
        **dict.fromkeys(USE_FIELDS, 0),
        "WCFP_ID": 1,
        "LSID_accepted": "100-1",
        "taxon_name_accepted": "Example taxon",
        "taxon_authors_accepted": "A.Author",
        "kingdom": "Plantae",
        "phylum": "Tracheophyta",
        "family": "Exampleaceae",
        "human_food": 1,
        "cultivated_GRIN": 0,
        "references_food": "A. Author (2000). Synthetic fixture.",
        "references_uses": None,
        "Link": "https://example.test/1",
        **overrides,
    }


def taxonomy(**overrides):
    return {
        "100-1": [{
            "taxon_status": "Accepted",
            "taxon_name": "Example taxon",
            "taxon_authors": "A.Author",
            "taxon_rank": "Species",
            "family": "Exampleaceae",
            "hybrid_formula": "",
            "genus_hybrid": "",
            "species_hybrid": "",
            "plant_name_id": "123",
            **overrides,
        }],
    }


def source_row(**overrides):
    return {**normalize_evidence([plant()], taxonomy())[0][0], **overrides}


def identity(**overrides):
    return {
        "taxon_id": 42,
        "scientific_name": "Example taxon",
        "rank": "species",
        "is_active": True,
        "family": "Exampleaceae",
        "ancestor_ids": [211194],
        "iconic_taxon_name": "Plantae",
        **overrides,
    }


def test_import_preserves_provenance_and_excludes_nonfood_and_nonvascular():
    rows, report = normalize_evidence([
        plant(poisons=1, cultivated_GRIN=1),
        plant(WCFP_ID=2, human_food=0, animal_food=1, medicines=1),
        plant(WCFP_ID=3, phylum="Chlorophyta"),
    ], taxonomy())
    assert report["non_human_food"] == report["non_vascular"] == report["matchable_rank"] == 1
    assert rows[0]["evidence_types"] == ["food_documented", "poison_use"]
    assert rows[0]["provenance"]["wcvp_plant_name_id"] == "123"
    assert rows[0]["source_references"]["food"] == plant()["references_food"]
    assert source_row()["rank"] == "species"
    assert normalize_evidence([plant()], taxonomy(taxon_authors="Conflicting author"))[0][0]["rank"] == "unknown"


@pytest.mark.parametrize("rows", [
    [plant(), plant()],
    [plant(human_food="1")],
    [plant(references_food=None)],
    [plant(phylum=None)],
])
def test_import_rejects_duplicate_and_malformed_evidence(rows):
    with pytest.raises(ValueError):
        normalize_evidence(rows, taxonomy())


@pytest.mark.parametrize("changes, ids", [
    ({"family": "Otheraceae"}, {42}),
    ({"scientific_name": "Example different", "common_name": "Example taxon"}, {42}),
    ({}, {42, 43}),
    ({}, None),
    ({"taxon_id": None}, {42}),
    ({"rank": "genus"}, {42}),
    ({"rank": "subspecies"}, {42}),
    ({"rank": "cultivar"}, {42}),
    ({"is_active": False, "current_synonymous_taxon_ids": [11, 12]}, {42}),
    ({"authority": "Different author"}, {42}),
    ({"ancestor_ids": []}, {42}),
    ({"iconic_taxon_name": "Fungi"}, {42}),
])
def test_incompatible_identity_never_yields_a_profile(changes, ids):
    row = source_row()
    target = identity(**changes)
    match = assess_evidence(row, target, ids)
    assert match["review_status"] == "needs_review"
    assert derive_profile(target, [row], [match]) is None


def test_verified_crosswalk_and_synonym_recheck_current_identity():
    row = source_row()
    target = identity(scientific_name="Transfer taxon")
    crosswalk = {
        "record_key": "1", "taxon_id": 42, "accepted_name": "Transfer taxon",
        "authority": "A.Author", "method": "verified_identifier", "source_taxon_id": "100-1",
    }
    assert assess_evidence(row, target, None, reviewed=crosswalk)["review_status"] == "reviewed"
    assert assess_evidence(row, target, None, reviewed={**crosswalk, "source_taxon_id": "200-1"})["reason"] == "crosswalk_mismatch"
    assert assess_evidence(row, identity(), None, reviewed=crosswalk)["reason"] == "reviewed_identity_changed"

    crosswalk.update(method="verified_synonym", synonym_taxon_id=15)
    synonym = identity(taxon_id=15, is_active=False, current_synonymous_taxon_ids=[42])
    assert assess_evidence(row, target, None, reviewed=crosswalk, synonym=synonym)["match_method"] == "verified_synonym"
    assert assess_evidence(
        row, target, None, reviewed=crosswalk,
        synonym={**synonym, "current_synonymous_taxon_ids": [42, 43]},
    )["reason"] == "unverified_synonym"


def test_profile_keeps_conflict_toxicity_and_food_use_independent():
    food = source_row()
    warning = source_row(record_key="2", evidence_types=["food_conditional", "toxicity_concern"], parts=["fixture part"])
    disputed = source_row(record_key="3", evidence_types=["food_disputed"])
    target = identity()
    matches = [assess_evidence(row, target, {42}) for row in [food, warning, disputed]]

    documented = derive_profile(target, [food], matches[:1])
    assert documented["food_use_status"] == "documented"
    assert documented["toxicity_status"] == "unknown"
    assert documented["documented_parts"] == []
    conditional = derive_profile(target, [food, warning], matches[:2])
    assert conditional["food_use_status"] == "conditional"
    assert conditional["toxicity_status"] == "documented_concern"
    profile = derive_profile(target, [food, warning, disputed], matches)
    assert profile["food_use_status"] == "disputed"
    assert profile["has_documented_food_use"] and profile["evidence_conflict"]
    assert profile["record_keys"] == ["1", "2", "3"]
    assert profile["documented_parts"] == ["fixture part"]


def test_checklist_poison_use_does_not_establish_toxicity_even_in_older_profiles():
    target = identity()
    row = source_row(evidence_types=["food_documented", "poison_use"])
    profile = derive_profile(target, [row], [assess_evidence(row, target, {42})])
    assert profile["checklist_poison_use"]
    assert profile["toxicity_status"] == "unknown"
    legacy = {key: value for key, value in profile.items() if key != "checklist_poison_use"}
    legacy["toxicity_status"] = "documented_concern"
    repository = SimpleNamespace(read_edibility_profiles=lambda ids: ("legacy", {"42": legacy}))
    reference = load_edibility_reference(repository, [{**target, "status": "confirmed"}], enabled=True)
    assert reference.profiles["42"]["checklist_poison_use"]
    assert reference.profiles["42"]["toxicity_status"] == "unknown"


def test_backfill_checks_unique_names_and_uses_cached_negatives():
    lookups = []
    inat = SimpleNamespace(
        fetch_taxon_reference_identity=lambda value: lookups.append(value) or identity(taxon_id=value),
        find_active_scientific_taxon_ids=lambda _: {42, 44},
    )
    row = source_row()
    report = Counter()
    result = assess_batch(
        [{"taxon_id": 40, "enrichment": identity(taxon_id=40, scientific_name="Missing taxon")}, {"taxon_id": 42}],
        inat, lambda name, keys: [row] if name == "example taxon" else [], {}, report,
    )
    assert lookups == [42]
    assert all(item["profile"] is None for item in result)
    assert report["missing_source_evidence"] == report["ambiguous_or_rejected"] == 1


def test_inat_exact_lookup_ignores_common_names_and_incomplete_results(monkeypatch):
    client = InatClient(access_token="")
    data = {
        "total_results": 3,
        "results": [
            {"name": "Example taxon", "id": 42, "is_active": True},
            {"name": "Different taxon", "preferred_common_name": "Example taxon", "id": 43, "is_active": True},
            {"name": "Example taxon", "id": 44, "is_active": False},
        ],
    }
    monkeypatch.setattr(client, "_request", lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: data))
    assert client.find_active_scientific_taxon_ids("Example taxon") == {42}
    data["total_results"] += 1
    assert client.find_active_scientific_taxon_ids("Example taxon") is None


def test_cross_reference_import_retains_original_locators_and_rejects_ambiguous_taxa():
    pages = [""] * 11 + ["Exampleaceae\nExample taxon A.Author\n100-1 | HF PO MA | [2, 14]"]
    duke = {
        "TAXON": "Example taxon", "TAXAUTHOR": "A.Author", "FAMILY": "EXAMPLEACEAE",
        "SPRANK": "", "SPXNAM": "", "ETHNO": "12", "REFERENCE": "cited work",
    }
    names = {"example taxon"}
    candidates = list(_kew_records(pages, names)) + list(_duke_records([duke], names))
    assert not list(_duke_records([{**duke, "SPRANK": "var."}, {**duke, "REFERENCE": ""}], names))
    assert _binding(candidates, identity(family="Anotheraceae"), {42}) == []
    assert _binding(candidates, identity(), {42, 43}) == []
    kew, duke_ref = _binding(candidates, identity(), {42})
    assert kew["locator"] == "Page 12 · IPNI 100-1"
    assert kew["categories"] == ["HF", "PO", "MA"]
    assert kew["reference_ids"] == [2, 14]
    assert duke_ref["record_keys"] == [12]
    assert duke_ref["reference_keys"] == ["cited work"]


def test_discovery_sources_are_bound_to_confirmed_exact_taxa_without_changing_classification(monkeypatch):
    cross_reference = {"source": "duke", "summary": "Indexed food and poison use.", "locator": "Test locator"}
    monkeypatch.setattr(edibility, "_CROSS_REFERENCE", {
        "taxa": {"42": {**identity(), "cross_references": [cross_reference]}},
    })
    repository = SimpleNamespace(read_edibility_profiles=lambda ids: (None, {}))
    observation = {**identity(), "status": "confirmed"}
    profile = load_edibility_reference(repository, [observation], enabled=True).profiles["42"]
    assert profile["cross_references"] == [{
        **{key: cross_reference[key] for key in ("summary", "locator")},
        "source_url": profile["sources"][0]["url"],
    }]
    assert profile["food_use_status"] == profile["toxicity_status"] == "unknown"
    assert not profile["has_documented_food_use"]
    for changed in ({"status": "pending"}, {"rank": "variety"}, {"scientific_name": "Example different"}):
        mismatched = observation | changed
        assert load_edibility_reference(repository, [mismatched], enabled=True).for_observation(mismatched) is None
    monkeypatch.setattr(edibility, "_PART_REFERENCE", {
        "taxa": {"42": {**identity(), "traditional_uses": [{"source": "duke", "note": "Historically used."}]}},
    })
    combined = load_edibility_reference(repository, [observation], enabled=True).profiles["42"]
    assert combined["review_status"] == "reviewed"
    assert len(combined["sources"]) == len(combined["traditional_uses"]) == len(combined["cross_references"]) == 1


def test_api_for_observation_uses_exact_tag_and_suppresses_mixed_species_groups():
    profile = {**identity(), "sources": [{"title": "Fixture dataset"}]}
    reference = EdibilityReference("release-2", {"42": profile})
    species = [
        {**identity(), "id": "first", "photo_id": "photo-1", "status": "confirmed", "species_taxon_id": 42},
        {**identity(taxon_id=43, rank="variety"), "id": "second", "photo_id": "photo-2",
         "status": "confirmed", "species_taxon_id": 42},
        {**identity(), "id": "pending", "status": "pending"},
        {**identity(scientific_name="Stale taxon"), "id": "stale", "status": "confirmed"},
    ]
    photos = {key: {"id": key} for key in ("photo-1", "photo-2")}
    tags = mobile_api._photo_payload(photos["photo-1"], species, reference=reference)["species"]
    assert [tag["edibility"] for tag in tags] == [profile, None, None, None]
    summary = mobile_api._build_species_payloads(species[:2], photos, {}, reference=reference)[0]
    assert summary["edibility"] is None and summary["edibility_reference_enabled"]
    assert summary["edibility_by_taxon"] == [profile]
    assert summary["ecology"]["label"] == "unknown"
    assert mobile_api._build_species_payloads(species[:1], photos, {}, reference=reference)[0]["edibility"] == profile


def test_reference_batches_distinct_ids_and_fails_closed_for_disable_withdrawal_and_outage():
    calls = []
    profile = identity()

    def read(ids):
        calls.append(ids)
        return "release-2", {"42": profile}

    repository = SimpleNamespace(read_edibility_profiles=read)
    observations = [
        {"status": "confirmed", "taxon_id": 42, "owner_subject": "one"},
        {"status": "confirmed", "taxon_id": 42, "owner_subject": "two"},
        {"status": "pending", "taxon_id": 43},
    ]
    reference = load_edibility_reference(repository, observations, enabled=True)
    assert reference.profiles == {
        "42": {**profile, "dataset_version": reference.release_id, "checklist_poison_use": False},
    }
    assert calls == [[42]]
    assert load_edibility_reference(repository, observations, enabled=False).release_id is None
    assert calls == [[42]]
    repository.read_edibility_profiles = lambda ids: (None, {})
    assert load_edibility_reference(repository, observations, enabled=True).profiles == {}
    assert load_edibility_reference(object(), observations, enabled=True).release_id is None


def test_reviewed_part_evidence_can_fill_a_missing_checklist_entry_without_inheriting():
    blueberry = {
        "taxon_id": 52739, "scientific_name": "Vaccinium fuscatum", "rank": "species",
        "iconic_taxon_name": "Plantae", "status": "confirmed",
    }
    genus = {**blueberry, "taxon_id": 48353, "scientific_name": "Vaccinium", "rank": "genus"}
    repository = SimpleNamespace(read_edibility_profiles=lambda ids: (None, {}))
    reference = load_edibility_reference(repository, [blueberry, genus], enabled=True)
    profile = reference.for_observation(blueberry)
    assert profile["food_use_status"] == "documented"
    assert profile["toxicity_status"] == "unknown"
    assert profile["dataset_version"] == reference.release_id
    assert reference.for_observation(genus) is None
    assert reference.for_observation({**blueberry, "rank": "genus"}) is None
    assert reference.for_observation({**blueberry, "scientific_name": "Vaccinium corymbosum"}) is None
    assert reference.for_observation({**blueberry, "status": "pending"}) is None
    claim, = profile["part_evidence"]
    assert (claim["part"], claim["kind"]) == ("Berries", "edible")
    assert claim["source_url"] == profile["sources"][0]["url"]


def test_parts_keep_plant_hazards_and_conditional_food_use_distinct():
    elderberry = {
        "taxon_id": 84300, "scientific_name": "Sambucus canadensis", "rank": "species",
        "iconic_taxon_name": "Plantae", "status": "confirmed",
    }
    baseline = {
        **elderberry, "food_use_status": "documented", "toxicity_status": "documented_concern",
        "review_status": "source_matched", "sources": [{"url": "https://example.test/checklist"}],
    }
    repository = SimpleNamespace(read_edibility_profiles=lambda ids: ("checklist", {"84300": baseline}))
    reference = load_edibility_reference(repository, [elderberry], enabled=True)
    profile = reference.for_observation(elderberry)
    assert profile["food_use_status"] == "conditional"
    assert profile["toxicity_status"] == "documented_concern"
    assert profile["has_documented_food_use"] and profile["checklist_poison_use"]
    assert not profile["evidence_conflict"]
    assert {(item["part"], item["kind"]) for item in profile["part_evidence"]} == {
        ("Leaves and stems", "toxic"), ("Berries", "conditional"), ("Flowers", "conditional"),
    }
    assert profile["sources"][-1] == baseline["sources"][0]


def test_traditional_use_can_stand_alone_without_a_food_or_toxicity_classification():
    wax_myrtle = {
        "taxon_id": 119956, "scientific_name": "Morella cerifera", "rank": "species",
        "iconic_taxon_name": "Plantae", "status": "confirmed",
    }
    repository = SimpleNamespace(read_edibility_profiles=lambda ids: (None, {}))
    reference = load_edibility_reference(repository, [wax_myrtle], enabled=True)
    profile = reference.for_observation(wax_myrtle)
    assert profile["food_use_status"] == profile["toxicity_status"] == "unknown"
    assert not profile["has_documented_food_use"]
    assert profile["part_evidence"] == []
    use, = profile["traditional_uses"]
    assert "candles" in use["note"]
    assert use["source_url"] == profile["sources"][0]["url"]
    assert reference.for_observation({**wax_myrtle, "rank": "variety"}) is None


def test_repository_does_not_combine_versions_during_a_bulk_read():
    calls = []
    source = {"title": "Fixture", "version": "2", "url": "https://example.test", "license": "CC BY 4.0", "attribution": "Author"}
    result = {"release_id": "first", "source": source, "profiles": {"1": {"scientific_name": "Example taxon"}}}

    def rpc(name, params):
        calls.append(params["p_taxon_ids"])
        return SimpleNamespace(execute=lambda: SimpleNamespace(data={**result, "release_id": str(len(calls))}))

    repository = HikeJournalRepository(SimpleNamespace(rpc=rpc))
    assert repository.read_edibility_profiles(list(range(1, 203))) == (None, {})
    assert list(map(len, calls)) == [200, 2]


def test_staging_retries_are_idempotent_and_never_activate_on_partial_failure():
    state = {"edibility_source_releases": {}, "taxon_food_use_evidence": {}}
    manifest = {"source_key": "wcfp", "version": "2", "archive_sha256": "a" * 64}

    class Table:
        def __init__(self, name):
            self.name = name

        def upsert(self, rows, *, on_conflict, ignore_duplicates):
            assert ignore_duplicates
            keys = on_conflict.split(",")
            for row in rows if isinstance(rows, list) else [rows]:
                if row.get("record_key") == "2" and fail:
                    raise OSError("Synthetic interruption")
                key = tuple(row[column] for column in keys)
                state[self.name].setdefault(key, {"id": "test-release", "active": False, **deepcopy(row)})
            return self

        def select(self, *args, **kwargs):
            return self

        def eq(self, *args):
            return self

        def single(self):
            return self

        def execute(self):
            return SimpleNamespace(data=next(iter(state[self.name].values())), count=len(state[self.name]))

    client = SimpleNamespace(table=Table)
    rows = [source_row(), source_row(record_key="2")]
    fail = True
    with pytest.raises(OSError):
        stage_release(client, manifest, rows, 1)
    assert len(state["taxon_food_use_evidence"]) == 1
    assert not state["edibility_source_releases"][("wcfp", "2")]["active"]
    fail = False
    assert stage_release(client, manifest, rows, 1) == "test-release"
    assert stage_release(client, manifest, rows, 2) == "test-release"
    assert len(state["taxon_food_use_evidence"]) == 2
    with pytest.raises(ValueError, match="metadata differs"):
        stage_release(client, {**manifest, "archive_sha256": "b" * 64}, rows, 1)


def test_pinned_import_rejects_changed_archive_and_unexpected_headers(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    workbook.active.title = "WCFP"
    workbook.active.append(["wrong_column"])
    spreadsheet = tmp_path / "WCFP.xlsx"
    workbook.save(spreadsheet)
    path = tmp_path / "fixture.zip"
    with ZipFile(path, "w") as archive:
        archive.write(spreadsheet, "WCFP.xlsx")
    manifest = {
        "workbook": "WCFP.xlsx",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "archive_sha256": "a" * 64,
    }
    with pytest.raises(ValueError, match="differs from the pinned release"):
        read_verified_archive(path, manifest)
    for algorithm, name in (("sha256", "archive_sha256"), ("md5", "archive_md5")):
        with path.open("rb") as data:
            manifest[name] = file_digest(data, algorithm).hexdigest()
    with pytest.raises(ValueError, match="Unexpected WCFP workbook headers"):
        read_verified_archive(path, manifest)


def test_default_import_dry_run_never_connects(monkeypatch, tmp_path):
    from scripts import import_food_plants

    monkeypatch.setattr(import_food_plants, "read_verified_archive", lambda *args: ([source_row()], Counter()))
    monkeypatch.setattr(import_food_plants, "staging_client", lambda *args: pytest.fail("dry run connected"))
    monkeypatch.setattr("sys.argv", ["import_food_plants.py", str(tmp_path / "fixture.zip")])
    assert import_food_plants.main() == 0


def test_species_responses_clear_reference_data_when_disabled(monkeypatch):
    taxon = {
        **identity(), "id": "obs-1", "status": "confirmed", "photo_id": "photo-1",
    }
    stored = {
        **identity(), "dataset_version": "fixture-2", "food_use_status": "documented",
        "sources": [{"title": "Synthetic source"}],
    }
    lookups = []
    service = SimpleNamespace(
        repository=SimpleNamespace(
            read_edibility_profiles=lambda ids: lookups.append(ids) or ("fixture-2", {"42": stored}),
        ),
    )
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(mobile_api, "_visible_species_data", lambda *args, **kwargs: (
        [taxon], {"photo-1": {"id": "photo-1"}}, {},
    ))
    monkeypatch.setattr(mobile_api, "settings", replace(mobile_api.settings, edibility_enabled=True))
    listed = mobile_api.list_species()[0]
    current = {
        **stored,
        "dataset_version": listed["edibility_dataset_version"],
        "checklist_poison_use": False,
    }
    assert listed["edibility"] == current
    detail = mobile_api.get_species_detail("taxon:42")
    assert detail["edibility"] == current
    assert detail["encounters"][0]["photo"]["species"][0]["edibility"] == current
    assert lookups == [[42], [42]]
    monkeypatch.setattr(mobile_api, "settings", replace(mobile_api.settings, edibility_enabled=False))
    detail = mobile_api.get_species_detail("taxon:42")
    assert detail["edibility"] is detail["encounters"][0]["photo"]["species"][0]["edibility"] is None
    assert not detail["edibility_reference_enabled"]
    assert lookups == [[42], [42]]


def test_backfill_preserves_reviewed_rejection_without_publishing_a_profile():
    reviewed = {"record_key": "1", "taxon_id": 42, "method": "rejected"}
    target = identity()
    inat = SimpleNamespace(fetch_taxon_reference_identity=lambda _: target)
    assessments = assess_batch(
        [{"taxon_id": 42}], inat, lambda name, keys: [source_row()], {42: [reviewed]}, Counter(),
    )
    result = assessments[0]
    assert result["profile"] is None
    assert result["matches"][0]["review_status"] == "rejected"
    assert result["matches"][0]["review_basis"] == reviewed


def test_unresolved_conflict_does_not_publish_only_the_positive_record():
    food = source_row()
    hazard = source_row(record_key="2", family="Differentaceae", evidence_types=["toxicity_concern"])
    target = identity()
    matches = [assess_evidence(row, target, {42}) for row in [food, hazard]]
    assert derive_profile(target, [food, hazard], matches) is None
