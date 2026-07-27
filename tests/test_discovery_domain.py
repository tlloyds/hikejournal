from datetime import date

import pytest

from hike_journal.domain.discovery import (
    attach_collection_progress,
    build_collection_index,
    candidate_taxon_snapshot,
    classify_data_density,
    credited_species_taxon_id,
    discovery_cache_key,
    normalize_radius,
    normalize_species_counts,
    seasonal_months,
)


def test_seasonal_months_wrap_the_calendar() -> None:
    assert seasonal_months(date(2026, 1, 10)) == (12, 1, 2)
    assert seasonal_months(date(2026, 12, 10)) == (11, 12, 1)


def test_discovery_cache_key_rounds_coordinates_and_is_stable() -> None:
    first = discovery_cache_key(
        lat=28.12344,
        lng=-82.12344,
        radius_km=10,
        months=(6, 7, 8),
        iconic_taxon="Plantae",
        observed_after="2016-01-01",
    )
    second = discovery_cache_key(
        lat=28.1234,
        lng=-82.1234,
        radius_km=10,
        months=(8, 7, 6),
        iconic_taxon="Plantae",
        observed_after="2016-01-01",
    )

    assert first == second


def test_normalize_radius_rejects_unplanned_expansion() -> None:
    assert normalize_radius(10) == 10
    with pytest.raises(ValueError):
        normalize_radius(15)


def test_species_counts_are_deduplicated_banded_and_species_only() -> None:
    payload = {
        "results": [
            {
                "count": 90,
                "taxon": {
                    "id": 1,
                    "rank": "species",
                    "name": "Eudocimus albus",
                    "preferred_common_name": "White Ibis",
                    "default_photo": {
                        "medium_url": "https://img.example/ibis.jpg",
                        "attribution": "Photo by A",
                        "license_code": "cc-by",
                    },
                },
            },
            {"count": 80, "taxon": {"id": 2, "rank": "genus", "name": "Quercus"}},
            {"count": 70, "taxon": {"id": 1, "rank": "species", "name": "Eudocimus albus"}},
        ]
    }

    taxa = normalize_species_counts(payload)

    assert [item["taxon_id"] for item in taxa] == [1]
    assert taxa[0]["frequency_band"] == "Often reported"
    assert taxa[0]["reference_photo"]["license_code"] == "cc-by"


def test_collection_credit_excludes_genus_only_records() -> None:
    assert credited_species_taxon_id({"taxon_id": 1, "rank": "genus", "scientific_name": "Quercus"}) is None
    assert credited_species_taxon_id({"taxon_id": 2, "rank": "species", "scientific_name": "Quercus virginiana"}) == 2
    assert credited_species_taxon_id({"taxon_id": 3, "rank": "", "scientific_name": "Tillandsia usneoides"}) == 3


def test_candidate_snapshot_credits_subspecies_to_parent_species() -> None:
    snapshot = candidate_taxon_snapshot(
        taxon_id=44,
        scientific_name="Example bird floridana",
        raw_payload={
            "results": [
                {
                    "taxon": {
                        "id": 44,
                        "rank": "subspecies",
                        "ancestor_ids": [1, 2, 33],
                        "iconic_taxon_name": "Aves",
                    }
                }
            ]
        },
    )

    assert snapshot == {
        "rank": "subspecies",
        "iconic_taxon_name": "Aves",
        "species_taxon_id": 33,
    }


def test_candidate_snapshot_ignores_self_at_end_of_v2_ancestor_ids() -> None:
    snapshot = candidate_taxon_snapshot(
        taxon_id=559678,
        scientific_name="Dendrocygna autumnalis fulgens",
        raw_payload={
            "results": [
                {
                    "taxon": {
                        "id": 559678,
                        "rank": "subspecies",
                        "ancestor_ids": [1, 2, 6890, 6893, 559678],
                    }
                }
            ]
        },
    )

    assert snapshot["species_taxon_id"] == 6893


@pytest.mark.parametrize(
    ("observation_taxon_id", "observation_name", "species_taxon_id", "species_name"),
    [
        (559678, "Dendrocygna autumnalis fulgens", 6893, "Dendrocygna autumnalis"),
        (27140, "Coluber constrictor priapus", 27137, "Coluber constrictor"),
        (30985, "Sistrurus miliarius barbouri", 30983, "Sistrurus miliarius"),
    ],
)
def test_infraspecies_without_backfill_credit_exact_parent_species(
    observation_taxon_id: int,
    observation_name: str,
    species_taxon_id: int,
    species_name: str,
) -> None:
    collection = build_collection_index(
        [
            {
                "taxon_id": observation_taxon_id,
                "species_taxon_id": None,
                "rank": None,
                "scientific_name": observation_name,
                "photo_id": "local-photo",
            }
        ],
        {"local-photo": {"public_url": "mine.jpg", "taken_at": "2026-07-20"}},
    )

    result = attach_collection_progress(
        [{"taxon_id": species_taxon_id, "scientific_name": species_name}],
        collection,
    )

    assert result["taxa"][0]["collected"] is True
    assert result["taxa"][0]["collection_photo_url"] == "mine.jpg"


def test_infraspecies_name_fallback_does_not_credit_another_species_in_genus() -> None:
    collection = build_collection_index(
        [
            {
                "taxon_id": 27140,
                "species_taxon_id": None,
                "scientific_name": "Coluber constrictor priapus",
            }
        ],
        {},
    )

    result = attach_collection_progress(
        [{"taxon_id": 999, "scientific_name": "Coluber flagellum"}],
        collection,
    )

    assert result["taxa"][0]["collected"] is False


def test_collection_progress_prefers_latest_personal_photo() -> None:
    collection = build_collection_index(
        [
            {"taxon_id": 2, "rank": "species", "photo_id": "old"},
            {"taxon_id": 2, "rank": "species", "photo_id": "new"},
        ],
        {
            "old": {"taken_at": "2025-01-01", "public_url": "old.jpg"},
            "new": {"taken_at": "2026-01-01", "public_url": "new.jpg"},
        },
    )
    result = attach_collection_progress(
        [{"taxon_id": 2, "common_name": "Live Oak"}],
        collection,
        focus_taxon_ids=[2],
    )

    assert result["progress"]["collected_count"] == 1
    assert result["taxa"][0]["collection_photo_url"] == "new.jpg"
    assert result["taxa"][0]["focus_order"] == 1


def test_sparse_data_is_reported_without_mutating_results() -> None:
    taxa = [{"taxon_id": 1, "observation_count": 2}]

    density = classify_data_density(taxa)

    assert density["level"] == "sparse"
    assert "25 km" in density["message"]
