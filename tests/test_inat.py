from hike_journal.services.inat import extract_taxon_enrichment, parse_candidate


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
