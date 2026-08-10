from datetime import date

from hike_journal.domain.longitudinal import (
    build_field_briefing,
    build_hike_comparison,
    build_place_profile,
    build_seasonal_history,
)


def observation(taxon_id: int, observed_on: str | None, hike_id: str = "hike-1", **values):
    return {
        "taxon_id": taxon_id,
        "common_name": values.pop("common_name", f"Species {taxon_id}"),
        "scientific_name": f"Taxon {taxon_id}",
        "iconic_taxon_name": values.pop("iconic_taxon_name", "Plantae"),
        "observed_on": observed_on,
        "hike_id": hike_id,
        **values,
    }


def test_seasonal_history_handles_years_missing_dates_and_phenophases():
    history = build_seasonal_history(
        [
            observation(1, "2024-02-04", phenophases=[{"code": "flowering"}]),
            observation(1, "2025-02-18", phenophases=[{"code": "flowering"}]),
            observation(1, "2025-03-01", phenophases=[{"code": "fruiting"}]),
            observation(1, None),
        ]
    )

    assert history["observation_count"] == 3
    assert history["months"][1]["count"] == 2
    assert history["first_observed_on"] == "2024-02-04"
    assert history["latest_observed_on"] == "2025-03-01"
    assert history["years"][0]["first_observed_on"] == "2025-02-18"
    assert history["phenophases"] == [
        {"code": "flowering", "count": 2},
        {"code": "fruiting", "count": 1},
    ]


def test_place_profile_deduplicates_species_and_tracks_progression():
    hikes = [
        {"id": "hike-1", "title": "Spring", "hike_date": "2025-03-01", "distance_miles": 2},
        {"id": "hike-2", "title": "Summer", "hike_date": "2025-07-01", "distance_miles": 3},
    ]
    observations = [
        observation(1, "2025-03-01", "hike-1"),
        observation(1, "2025-03-01", "hike-1"),
        observation(1, "2025-07-01", "hike-2"),
        observation(2, "2025-07-01", "hike-2", iconic_taxon_name="Aves"),
    ]

    profile = build_place_profile({"id": "place-1", "name": "Oak Flat"}, hikes, observations)

    assert profile["summary"]["outing_count"] == 2
    assert profile["summary"]["species_count"] == 2
    assert profile["summary"]["observation_count"] == 4
    assert profile["visits"][0]["new_species_count"] == 1
    assert profile["visits"][0]["cumulative_species_count"] == 2


def test_hike_comparison_uses_species_set_math():
    comparison = build_hike_comparison(
        {"id": "a", "title": "A"},
        {"id": "b", "title": "B"},
        [observation(1, "2025-01-01", "a"), observation(2, "2025-01-01", "a"),
         observation(2, "2025-02-01", "b"), observation(3, "2025-02-01", "b")],
    )

    assert [item["taxon_id"] for item in comparison["species"]["shared"]] == [2]
    assert [item["taxon_id"] for item in comparison["species"]["only_a"]] == [1]
    assert [item["taxon_id"] for item in comparison["species"]["only_b"]] == [3]


def test_field_briefing_is_deterministic_and_explains_personal_reasons():
    nearby = [
        {"taxon_id": 2, "common_name": "Return", "nearby_rank": 1},
        {"taxon_id": 1, "common_name": "New", "nearby_rank": 2},
        {"taxon_id": 2, "common_name": "Duplicate", "nearby_rank": 3},
    ]
    history = [observation(2, "2024-08-10"), observation(2, "2025-08-12")]

    first = build_field_briefing(
        target_date=date(2026, 8, 9), nearby_taxa=nearby, observations=history
    )
    second = build_field_briefing(
        target_date=date(2026, 8, 9), nearby_taxa=nearby, observations=history
    )

    assert first == second
    assert first["recommendation_count"] == 2
    assert first["sections"][0]["title"] == "Seasonal returns"
    assert "2024, 2025" in first["sections"][0]["items"][0]["reasons"][0]
    assert any(section["title"] == "Missing from your Field Guide" for section in first["sections"])
