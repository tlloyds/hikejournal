from hike_journal.domain.locations import (
    attach_location_tags_to_hikes,
    canonical_location_id_map,
    canonicalize_hike_locations,
    resolve_location_selection,
    suggest_location_ids_for_hike,
)


def econ_locations():
    return [
        {
            "id": "econ-place",
            "name": "Econ River Wilderness",
            "slug": "econ-river-wilderness",
            "aliases": ["Econ River Wilderness Area"],
        },
        {
            "id": "econ-route",
            "name": "Econ River Wilderness Area",
            "slug": "econ-river-wilderness-area",
            "aliases": ["Econ River Wilderness"],
        },
    ]


def test_canonical_location_redirect_keeps_route_name_as_an_alias():
    locations = canonicalize_hike_locations(econ_locations())

    assert locations == [
        {
            "id": "econ-place",
            "name": "Econ River Wilderness",
            "slug": "econ-river-wilderness",
            "aliases": ["Econ River Wilderness Area"],
        }
    ]
    assert canonical_location_id_map(econ_locations()) == {
        "econ-place": "econ-place",
        "econ-route": "econ-place",
    }


def test_duplicate_location_tags_collapse_into_one_primary_place():
    hikes = [{"id": "hike-1", "title": "Econ walk"}]
    tags = [
        {"hike_id": "hike-1", "location_id": "econ-place", "is_primary": False},
        {"hike_id": "hike-1", "location_id": "econ-route", "is_primary": True},
    ]

    enriched = attach_location_tags_to_hikes(hikes, econ_locations(), tags)

    assert enriched[0]["location_tags"] == [
        {
            "id": "econ-place",
            "name": "Econ River Wilderness",
            "slug": "econ-river-wilderness",
            "aliases": ["Econ River Wilderness Area"],
            "is_primary": True,
        }
    ]


def test_location_suggestion_returns_only_the_canonical_place():
    matches = suggest_location_ids_for_hike(
        {
            "title": "Econ River Wilderness Area flower walk",
            "location_name": "Econ River Wilderness Area",
            "notes": "",
        },
        econ_locations(),
    )

    assert matches == ["econ-place"]


def test_manual_alias_selection_resolves_without_creating_a_duplicate():
    class Repository:
        def upsert_hike_location(self, *_args, **_kwargs):
            raise AssertionError("A known alias must not create a manual location")

    assert resolve_location_selection(
        Repository(),
        ["Econ River Wilderness Area"],
        econ_locations(),
    ) == ["econ-place"]
