from hike_journal.domain.badges import TRAIL_BADGE_CATALOG, calculate_trail_badges


def _named(badges, title):
    return next(badge for badge in badges if badge.definition.title == title)


def _species(
    taxon_id: int,
    iconic_taxon_name: str,
    *,
    species_taxon_id: int | None = None,
) -> dict:
    return {
        "taxon_id": taxon_id,
        "species_taxon_id": species_taxon_id or taxon_id,
        "rank": "species",
        "scientific_name": f"Species example{taxon_id}",
        "common_name": f"Species {taxon_id}",
        "iconic_taxon_name": iconic_taxon_name,
    }


def test_catalog_matches_the_android_collection_size() -> None:
    assert len(TRAIL_BADGE_CATALOG) == 36
    assert len({badge.id for badge in TRAIL_BADGE_CATALOG}) == 36


def test_hike_count_distance_and_longest_day_unlock_independently() -> None:
    hikes = [
        {"id": f"hike-{index}", "distance_miles": 12.0 if index == 0 else 10.0}
        for index in range(10)
    ]

    badges = calculate_trail_badges(hikes, [], [])

    assert _named(badges, "Trail Regular").earned
    assert _named(badges, "Century Afoot").earned
    assert _named(badges, "Double Digits").earned
    assert not _named(badges, "Seasoned Trekker").earned
    assert not _named(badges, "Endurance Day").earned


def test_field_guide_and_specialties_use_distinct_parent_species() -> None:
    plants = [_species(index, "Plantae") for index in range(1, 26)]
    duplicate_infraspecies = _species(
        999,
        "Plantae",
        species_taxon_id=plants[0]["species_taxon_id"],
    )

    badges = calculate_trail_badges([], plants + [duplicate_infraspecies], [])

    assert _named(badges, "Curious Naturalist").current == 25
    assert _named(badges, "Leaf Scout").earned
    assert not _named(badges, "Field Botanist").earned


def test_quest_requires_every_focus_target_and_deduplicates_rare_finds() -> None:
    observations = [_species(101, "Plantae"), _species(102, "Aves")]
    complete = {
        "taxa": [
            {
                "taxon_id": 101,
                "scientific_name": "Species example101",
                "focus_order": 1,
                "frequency_band": "Less often reported",
            },
            {
                "taxon_id": 102,
                "scientific_name": "Species example102",
                "focus_order": 2,
                "frequency_band": "Regularly reported",
            },
        ]
    }
    incomplete = {
        "taxa": [
            {
                "taxon_id": 101,
                "scientific_name": "Species example101",
                "focus_order": 1,
                "frequency_band": "Less often reported",
            },
            {
                "taxon_id": 103,
                "scientific_name": "Species example103",
                "focus_order": 2,
                "frequency_band": "Regularly reported",
            },
        ]
    }

    badges = calculate_trail_badges([], observations, [complete, incomplete])

    assert _named(badges, "Quest Complete").current == 1
    assert _named(badges, "Quest Complete").earned
    assert _named(badges, "Rare Find").current == 1
    assert not _named(badges, "Rare Company").earned
