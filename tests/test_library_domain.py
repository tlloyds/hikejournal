from hike_journal.domain.library import (
    count_unique_species,
    filter_standalone_observations,
    filter_standalone_photos,
    filter_hike_library,
    filter_hikes_for_user,
    record_visible_for_user,
    standalone_journal_is_active,
)


def test_visibility_respects_owner_and_visible_hike_scope() -> None:
    context = {"mode": "google", "email": "owner@example.com", "subject": "user-1", "auth_configured": True}
    hikes = [
        {"id": "mine", "owner_subject": "user-1", "owner_email": None},
        {"id": "theirs", "owner_subject": "user-2", "owner_email": "other@example.com"},
    ]

    assert [hike["id"] for hike in filter_hikes_for_user(hikes, context)] == ["mine"]
    assert record_visible_for_user({"hike_id": "mine"}, {"mine"}, context)
    assert record_visible_for_user({"hike_id": None, "owner_email": "owner@example.com"}, {"mine"}, context)
    assert not record_visible_for_user({"hike_id": "theirs"}, {"mine"}, context)


def test_library_filter_searches_location_tags_and_preserves_sorting() -> None:
    hikes = [
        {"id": "older", "title": "Loop", "hike_date": "2025-01-01", "created_at": "1", "is_archived": False, "location_tags": [{"name": "Black Bear Wilderness"}]},
        {"id": "newer", "title": "Scrub", "hike_date": "2026-01-01", "created_at": "2", "is_archived": False, "location_tags": []},
    ]

    assert [hike["id"] for hike in filter_hike_library(hikes, query="black bear", scope="Active", sort_order="Newest first")] == ["older"]
    assert [hike["id"] for hike in filter_hike_library(hikes, query="", scope="Active", sort_order="Newest first")] == ["newer", "older"]


def test_unique_species_prefers_scientific_identity() -> None:
    observations = [
        {"common_name": "Dewberry", "scientific_name": "Rubus trivialis"},
        {"common_name": "Southern dewberry", "scientific_name": "Rubus trivialis"},
        {"common_name": "Oak", "scientific_name": "Quercus virginiana"},
    ]

    assert count_unique_species(observations) == 2


def test_standalone_journal_requires_explicit_scope_and_no_hike() -> None:
    assert standalone_journal_is_active(active_view="Journal", requested_scope="standalone", selected_hike=None)
    assert not standalone_journal_is_active(active_view="Journal", requested_scope="global", selected_hike=None)
    assert not standalone_journal_is_active(
        active_view="Journal",
        requested_scope="standalone",
        selected_hike={"id": "hike-1"},
    )


def test_standalone_filters_reject_hike_linked_records() -> None:
    context = {"mode": "local-dev"}
    photos = [{"id": "standalone", "hike_id": None}, {"id": "linked", "hike_id": "hike-1"}]
    observations = [{"id": "standalone", "hike_id": None}, {"id": "linked", "hike_id": "hike-1"}]

    assert [row["id"] for row in filter_standalone_photos(photos, {"hike-1"}, context)] == ["standalone"]
    assert [row["id"] for row in filter_standalone_observations(observations, {"hike-1"}, context)] == ["standalone"]
