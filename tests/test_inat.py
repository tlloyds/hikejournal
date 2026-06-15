from hike_journal.services.inat import (
    build_observation_sync_candidate,
    extract_observation_taxon_snapshot,
    extract_taxon_enrichment,
    parse_candidate,
)


def test_parse_candidate_prefers_highest_score() -> None:
    payload = {
        "results": [
            {"score": 0.32, "taxon": {"id": 1, "name": "Quercus virginiana", "preferred_common_name": "Live Oak"}},
            {"score": 0.91, "taxon": {"id": 2, "name": "Tillandsia usneoides", "preferred_common_name": "Spanish Moss"}},
        ]
    }

    result = parse_candidate(payload)

    assert result is not None
    assert result.common_name == "Spanish Moss"
    assert result.scientific_name == "Tillandsia usneoides"
    assert result.confidence == 0.91
    assert result.taxon_id == 2


def test_extract_taxon_enrichment_collects_aliases_and_summary() -> None:
    taxon = {
        "name": "Sagittaria lancifolia",
        "preferred_common_name": "lanceleaf arrowhead",
        "english_common_name": "duck potato",
        "rank": "species",
        "iconic_taxon_name": "Plantae",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Sagittaria_lancifolia",
        "wikipedia_summary": "<i><b>Sagittaria lancifolia</b></i>, the <b>bulltongue arrowhead</b>, is a wetland plant.",
    }

    enrichment = extract_taxon_enrichment(taxon)

    assert enrichment["preferred_common_name"] == "lanceleaf arrowhead"
    assert enrichment["english_common_name"] == "duck potato"
    assert enrichment["rank"] == "species"
    assert enrichment["iconic_taxon_name"] == "Plantae"
    assert "lanceleaf arrowhead" in enrichment["alias_names"]
    assert "duck potato" in enrichment["alias_names"]
    assert "bulltongue arrowhead" in enrichment["alias_names"]


def test_extract_observation_taxon_snapshot_reads_active_taxon() -> None:
    payload = {
        "results": [
            {
                "id": 371091929,
                "community_taxon_id": 123,
                "quality_grade": "needs_id",
                "updated_at": "2026-06-15T12:00:00Z",
                "taxon": {
                    "id": 456,
                    "name": "Phytolacca americana",
                    "preferred_common_name": "American pokeweed",
                    "rank": "species",
                    "iconic_taxon_name": "Plantae",
                },
                "identifications": [{"id": 1}, {"id": 2}],
            }
        ]
    }

    snapshot = extract_observation_taxon_snapshot(payload)

    assert snapshot is not None
    assert snapshot["observation_id"] == 371091929
    assert snapshot["taxon_id"] == 456
    assert snapshot["common_name"] == "American pokeweed"
    assert snapshot["scientific_name"] == "Phytolacca americana"
    assert snapshot["community_taxon_id"] == 123
    assert snapshot["identification_count"] == 2


def test_build_observation_sync_candidate_returns_none_when_taxon_matches() -> None:
    local = {"id": "local-1", "taxon_id": 456, "common_name": "American pokeweed", "scientific_name": "Phytolacca americana"}
    remote = {"id": 371091929, "taxon": {"id": 456, "name": "Phytolacca americana", "preferred_common_name": "American pokeweed"}}

    assert build_observation_sync_candidate(local, remote) is None


def test_build_observation_sync_candidate_detects_changed_taxon() -> None:
    local = {
        "id": "local-1",
        "taxon_id": 456,
        "common_name": "American pokeweed",
        "scientific_name": "Phytolacca americana",
        "inat_observation_id": 371091929,
        "inat_observation_url": "https://www.inaturalist.org/observations/371091929",
    }
    remote = {
        "id": 371091929,
        "taxon": {
            "id": 789,
            "name": "Phytolacca rigida",
            "preferred_common_name": "Maritime pokeweed",
        },
    }

    candidate = build_observation_sync_candidate(local, remote)

    assert candidate is not None
    assert candidate["reason"] == "changed_taxon"
    assert candidate["local"]["taxon_id"] == 456
    assert candidate["inat"]["taxon_id"] == 789
    assert candidate["inat"]["common_name"] == "Maritime pokeweed"


def test_build_observation_sync_candidate_ignores_missing_remote_taxon() -> None:
    local = {"id": "local-1", "taxon_id": 456, "common_name": "American pokeweed", "scientific_name": "Phytolacca americana"}
    remote = {"id": 371091929, "taxon": None}

    assert build_observation_sync_candidate(local, remote) is None


def test_build_observation_sync_candidate_offers_name_only_local_update() -> None:
    local = {
        "id": "local-1",
        "taxon_id": None,
        "common_name": "Maritime pokeweed",
        "scientific_name": "Phytolacca rigida",
        "inat_observation_id": 371091929,
    }
    remote = {
        "id": 371091929,
        "taxon": {
            "id": 789,
            "name": "Phytolacca rigida",
            "preferred_common_name": "Maritime pokeweed",
        },
    }

    candidate = build_observation_sync_candidate(local, remote)

    assert candidate is not None
    assert candidate["reason"] == "missing_local_taxon"
    assert candidate["inat"]["taxon_id"] == 789
