from datetime import datetime

from hike_journal.domain.library import (
    count_unique_species,
    filter_standalone_observations,
    filter_standalone_photos,
    filter_hike_library,
    filter_hikes_for_user,
    record_visible_for_user,
    standalone_journal_is_active,
    entry_sort_datetime,
)
from hike_journal.domain.species_filters import (
    SPECIES_TYPE_OPTIONS,
    observation_matches_species_type,
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


def test_durable_subject_takes_precedence_over_conflicting_email() -> None:
    context = {
        "mode": "google",
        "email": "reused@example.com",
        "subject": "current-subject",
        "auth_configured": True,
    }
    conflicting = {
        "id": "not-mine",
        "owner_subject": "different-subject",
        "owner_email": "reused@example.com",
    }
    legacy_email_only = {
        "id": "legacy-mine",
        "owner_subject": None,
        "owner_email": "reused@example.com",
    }

    assert filter_hikes_for_user([conflicting, legacy_email_only], context) == [legacy_email_only]
    assert not record_visible_for_user(conflicting, set(), context)
    assert record_visible_for_user(legacy_email_only, set(), context)

    apple_context = {
        **context,
        "mode": "apple",
        "identity_provider": "apple",
        "subject": "apple:current-subject",
    }
    assert filter_hikes_for_user([legacy_email_only], apple_context) == []
    assert not record_visible_for_user(legacy_email_only, set(), apple_context)


def test_canonical_user_id_takes_precedence_over_legacy_subject_and_email() -> None:
    current = {
        "mode": "google",
        "identity_provider": "google",
        "user_id": "11111111-1111-4111-8111-111111111111",
        "subject": "shared-subject",
        "email": "shared@example.com",
        "auth_configured": True,
    }
    canonical_other_user = {
        "id": "other",
        "owner_user_id": "22222222-2222-4222-8222-222222222222",
        "owner_subject": "shared-subject",
        "owner_email": "shared@example.com",
    }
    canonical_current_user = {
        "id": "mine",
        "owner_user_id": current["user_id"],
        "owner_subject": "stale-subject",
        "owner_email": "stale@example.com",
    }

    assert filter_hikes_for_user(
        [canonical_other_user, canonical_current_user], current
    ) == [canonical_current_user]
    assert not record_visible_for_user(canonical_other_user, set(), current)
    assert record_visible_for_user(canonical_current_user, set(), current)


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


def test_species_type_filter_supports_specific_and_broad_animal_groups() -> None:
    bird = {"iconic_taxon_name": "Aves"}
    plant = {"iconic_taxon_name": "Plantae"}
    protozoan = {"iconic_taxon_name": "Protozoa"}

    assert observation_matches_species_type(bird, "Birds")
    assert observation_matches_species_type(bird, "Animals")
    assert not observation_matches_species_type(plant, "Animals")
    assert observation_matches_species_type(protozoan, "Other life")
    assert "Birds" in SPECIES_TYPE_OPTIONS
    assert observation_matches_species_type(bird, "All types")


def test_standalone_journal_requires_explicit_scope_and_no_hike() -> None:
    assert standalone_journal_is_active(active_view="Journal", requested_scope="standalone", selected_hike=None)
    assert not standalone_journal_is_active(active_view="Journal", requested_scope="global", selected_hike=None)
    assert not standalone_journal_is_active(
        active_view="Journal",
        requested_scope="standalone",
        selected_hike={"id": "hike-1"},
    )


def test_species_log_sort_dates_normalize_offset_aware_timestamps() -> None:
    timestamp = entry_sort_datetime(
        {"photo": {"taken_at": "2026-07-30T22:15:00-04:00"}, "hike": {}}
    )
    hike_day = entry_sort_datetime({"photo": {}, "hike": {"hike_date": "2026-07-31"}})

    assert timestamp == datetime(2026, 7, 31, 2, 15)
    assert timestamp.tzinfo is None
    assert timestamp > hike_day


def test_standalone_filters_reject_hike_linked_records() -> None:
    context = {"mode": "local-dev"}
    photos = [{"id": "standalone", "hike_id": None}, {"id": "linked", "hike_id": "hike-1"}]
    observations = [{"id": "standalone", "hike_id": None}, {"id": "linked", "hike_id": "hike-1"}]

    assert [row["id"] for row in filter_standalone_photos(photos, {"hike-1"}, context)] == ["standalone"]
    assert [row["id"] for row in filter_standalone_observations(observations, {"hike-1"}, context)] == ["standalone"]
