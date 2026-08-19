from __future__ import annotations

from typing import Any

import streamlit as st

from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.storage import StorageService
from hike_journal.services.supabase_client import get_supabase


def _repository() -> HikeJournalRepository:
    client = get_supabase()
    storage = StorageService(client)
    return HikeJournalRepository(
        client,
        media_url_resolver=storage.resolve_download_url,
    )


def _raw_repository() -> HikeJournalRepository:
    """Return durable database rows suitable for Streamlit's data cache."""
    return HikeJournalRepository(get_supabase())


def _resolve_media_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    return _repository().decorate_media_row(row) if row else None


def _resolve_media_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _repository().decorate_media_rows(rows)


@st.cache_data(show_spinner=False)
def _fetch_hikes_raw() -> list[dict[str, Any]]:
    return _raw_repository().list_hikes()


def fetch_hikes() -> list[dict[str, Any]]:
    return _resolve_media_rows(_fetch_hikes_raw())


@st.cache_data(show_spinner=False)
def fetch_hike_locations() -> list[dict[str, Any]]:
    return _repository().list_hike_locations()


@st.cache_data(show_spinner=False)
def fetch_hike_location_tags() -> list[dict[str, Any]]:
    return _repository().list_hike_location_tags()


@st.cache_data(show_spinner=False)
def _fetch_hike_route_import_raw(hike_id: str) -> dict[str, Any] | None:
    return _raw_repository().get_hike_route_import(hike_id)


def fetch_hike_route_import(hike_id: str) -> dict[str, Any] | None:
    return _resolve_media_row(_fetch_hike_route_import_raw(hike_id))


@st.cache_data(show_spinner=False)
def _fetch_all_hike_route_imports_raw() -> list[dict[str, Any]]:
    return _raw_repository().list_hike_route_imports()


def fetch_all_hike_route_imports() -> list[dict[str, Any]]:
    return _resolve_media_rows(_fetch_all_hike_route_imports_raw())


@st.cache_data(show_spinner=False, ttl=60)
def fetch_unindexed_map_routes(visible_hike_ids: tuple[str, ...], hike_id: str | None) -> list[dict[str, Any]]:
    return _repository().list_unindexed_map_routes(
        visible_hike_ids=list(visible_hike_ids),
        hike_id=hike_id,
    )


@st.cache_data(show_spinner=False, ttl=900)
def _fetch_hike_photos_raw(hike_id: str) -> list[dict[str, Any]]:
    return _raw_repository().list_photos(hike_id)


def fetch_hike_photos(hike_id: str) -> list[dict[str, Any]]:
    return _resolve_media_rows(_fetch_hike_photos_raw(hike_id))


@st.cache_data(show_spinner=False, ttl=900)
def _fetch_standalone_photos_raw() -> list[dict[str, Any]]:
    return _raw_repository().list_standalone_photos()


def fetch_standalone_photos() -> list[dict[str, Any]]:
    return _resolve_media_rows(_fetch_standalone_photos_raw())


@st.cache_data(show_spinner=False, ttl=900)
def _fetch_hike_map_photos_raw(hike_id: str) -> list[dict[str, Any]]:
    return _raw_repository().list_map_photos(hike_id)


def fetch_hike_map_photos(hike_id: str) -> list[dict[str, Any]]:
    return _resolve_media_rows(_fetch_hike_map_photos_raw(hike_id))


@st.cache_data(show_spinner=False, ttl=900)
def _fetch_all_map_photos_raw() -> list[dict[str, Any]]:
    return _raw_repository().list_map_photos()


def fetch_all_map_photos() -> list[dict[str, Any]]:
    return _resolve_media_rows(_fetch_all_map_photos_raw())


@st.cache_data(show_spinner=False, ttl=900)
def _fetch_review_queue_photos_raw() -> list[dict[str, Any]]:
    return _raw_repository().list_review_queue_photos()


def fetch_review_queue_photos() -> list[dict[str, Any]]:
    return _resolve_media_rows(_fetch_review_queue_photos_raw())


@st.cache_data(show_spinner=False)
def fetch_photo_hike_refs() -> list[dict[str, Any]]:
    return _repository().list_photo_hike_refs()


@st.cache_data(show_spinner=False)
def fetch_photo_storage_records() -> list[dict[str, Any]]:
    return _repository().list_photo_storage_records()


@st.cache_data(show_spinner=False)
def fetch_hike_observations(hike_id: str) -> list[dict[str, Any]]:
    return _repository().list_observations(hike_id)


@st.cache_data(show_spinner=False)
def fetch_hike_lightweight_observations(hike_id: str) -> list[dict[str, Any]]:
    return _repository().list_lightweight_observations(hike_id=hike_id)


@st.cache_data(show_spinner=False)
def fetch_all_lightweight_observations() -> list[dict[str, Any]]:
    return _repository().list_lightweight_observations()


@st.cache_data(show_spinner=False)
def fetch_lightweight_observations_for_photo_ids(photo_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    return _repository().list_lightweight_observations(photo_ids=list(photo_ids))


@st.cache_data(show_spinner=False)
def fetch_confirmed_observations_light() -> list[dict[str, Any]]:
    return _repository().list_lightweight_observations(status="confirmed")


@st.cache_data(show_spinner=False, ttl=900)
def _fetch_photo_records_for_ids_raw(photo_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    return _raw_repository().list_photo_records_for_ids(list(photo_ids))


def fetch_photo_records_for_ids(photo_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    return _resolve_media_rows(_fetch_photo_records_for_ids_raw(photo_ids))


@st.cache_data(show_spinner=False)
def fetch_observations_by_ids(observation_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    return _repository().list_observations_by_ids(list(observation_ids))


@st.cache_data(show_spinner=False)
def fetch_species_log_photo_preferences(observation_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    return _repository().list_species_log_photo_preferences(list(observation_ids))


@st.cache_data(show_spinner=False)
def fetch_observations_for_photo_ids(photo_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    return _repository().list_observations_for_photo_ids(list(photo_ids))


@st.cache_data(show_spinner=False)
def fetch_confirmed_observation_hike_refs() -> list[dict[str, Any]]:
    return _repository().list_confirmed_observation_hike_refs()


_CACHED_QUERIES = (
    _fetch_hikes_raw,
    fetch_hike_locations,
    fetch_hike_location_tags,
    _fetch_hike_route_import_raw,
    _fetch_all_hike_route_imports_raw,
    fetch_unindexed_map_routes,
    _fetch_hike_photos_raw,
    _fetch_standalone_photos_raw,
    _fetch_hike_map_photos_raw,
    _fetch_all_map_photos_raw,
    _fetch_review_queue_photos_raw,
    fetch_photo_hike_refs,
    fetch_photo_storage_records,
    fetch_hike_observations,
    fetch_hike_lightweight_observations,
    fetch_all_lightweight_observations,
    fetch_lightweight_observations_for_photo_ids,
    fetch_confirmed_observations_light,
    _fetch_photo_records_for_ids_raw,
    fetch_observations_by_ids,
    fetch_species_log_photo_preferences,
    fetch_observations_for_photo_ids,
    fetch_confirmed_observation_hike_refs,
)


def invalidate_data_cache() -> None:
    for query in _CACHED_QUERIES:
        query.clear()
