from hike_journal.services.species_identification import (
    build_known_species_catalog,
    is_species_log_main_photo,
    select_shared_candidate,
    update_species_log_main_photo_payload,
)


def candidate(
    taxon_id: int,
    *,
    support: int,
    top1: int,
    best_confidence: float = 0,
    average_confidence: float = 0,
) -> dict:
    return {
        "taxon_id": taxon_id,
        "support_count": support,
        "top1_count": top1,
        "best_confidence": best_confidence,
        "average_confidence": average_confidence,
        "total_confidence": average_confidence * support,
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


def test_two_photo_group_uses_the_highest_confidence_top_choice() -> None:
    selected = select_shared_candidate(
        [
            candidate(10, support=2, top1=1, best_confidence=0.76, average_confidence=0.61),
            candidate(20, support=2, top1=1, best_confidence=0.91, average_confidence=0.58),
        ],
        photo_count=2,
    )

    assert selected is not None
    assert selected["taxon_id"] == 20


def test_two_photo_group_ignores_non_top_suggestions_even_with_high_confidence() -> None:
    selected = select_shared_candidate(
        [
            candidate(10, support=2, top1=1, best_confidence=0.80),
            candidate(20, support=2, top1=1, best_confidence=0.72),
            candidate(30, support=2, top1=0, best_confidence=0.95),
        ],
        photo_count=2,
    )

    assert selected is not None
    assert selected["taxon_id"] == 10


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


def test_species_log_main_photo_payload_preserves_existing_metadata() -> None:
    original = {"taxon_enrichment": {"rank": "species"}, "source": "known_species"}

    selected = update_species_log_main_photo_payload(original, selected=True)
    cleared = update_species_log_main_photo_payload(selected, selected=False)

    assert selected["species_log_main_photo"] is True
    assert selected["taxon_enrichment"] == {"rank": "species"}
    assert "species_log_main_photo" not in original
    assert cleared == original


def test_species_log_main_photo_requires_explicit_true_flag() -> None:
    assert is_species_log_main_photo({"raw_response_json": {"species_log_main_photo": True}})
    assert not is_species_log_main_photo({"raw_response_json": {"species_log_main_photo": False}})
    assert not is_species_log_main_photo({"raw_response_json": None})
