from hike_journal.services.species_identification import build_known_species_catalog, select_shared_candidate


def candidate(taxon_id: int, *, support: int, top1: int) -> dict:
    return {
        "taxon_id": taxon_id,
        "support_count": support,
        "top1_count": top1,
    }


def test_selects_candidate_supported_by_every_photo_and_top_choice_majority() -> None:
    selected = select_shared_candidate(
        [candidate(10, support=3, top1=2), candidate(20, support=3, top1=1)],
        photo_count=3,
    )

    assert selected is not None
    assert selected["taxon_id"] == 10


def test_rejects_candidate_missing_from_one_photos_results() -> None:
    selected = select_shared_candidate(
        [candidate(10, support=2, top1=2)],
        photo_count=3,
    )

    assert selected is None


def test_two_photo_group_requires_both_top_choices_to_agree() -> None:
    selected = select_shared_candidate(
        [candidate(10, support=2, top1=1), candidate(20, support=2, top1=1)],
        photo_count=2,
    )

    assert selected is None


def test_known_species_catalog_deduplicates_taxa_and_counts_prior_records() -> None:
    catalog = build_known_species_catalog(
        [
            {"id": "obs-1", "taxon_id": 101, "common_name": "Southern dewberry", "scientific_name": "Rubus trivialis"},
            {"id": "obs-2", "taxon_id": 101, "common_name": "southern dewberry", "scientific_name": "Rubus trivialis"},
            {"id": "obs-3", "taxon_id": 202, "common_name": "Gallberry", "scientific_name": "Ilex glabra"},
        ]
    )

    assert [entry["taxon_id"] for entry in catalog] == [202, 101]
    assert catalog[1]["seen_count"] == 2
    assert catalog[1]["source_observation_id"] == "obs-1"


def test_known_species_catalog_keeps_name_only_manual_taxa() -> None:
    catalog = build_known_species_catalog(
        [{"id": "obs-1", "taxon_id": None, "common_name": "Local morph", "scientific_name": "Species example"}]
    )

    assert catalog == [
        {
            "taxon_id": None,
            "common_name": "Local morph",
            "scientific_name": "Species example",
            "source_observation_id": "obs-1",
            "seen_count": 1,
        }
    ]
