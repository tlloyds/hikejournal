from __future__ import annotations

from typing import Any

import streamlit as st

from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.supabase_client import get_supabase


def _repository() -> HikeJournalRepository:
    return HikeJournalRepository(get_supabase())


@st.cache_data(show_spinner=False)
def fetch_hikes() -> list[dict[str, Any]]:
    return _repository().list_hikes()


@st.cache_data(show_spinner=False)
def fetch_hike_locations() -> list[dict[str, Any]]:
    return _repository().list_hike_locations()


@st.cache_data(show_spinner=False)
def fetch_hike_location_tags() -> list[dict[str, Any]]:
    return _repository().list_hike_location_tags()


@st.cache_data(show_spinner=False)
def fetch_hike_route_import(hike_id: str) -> dict[str, Any] | None:
    return _repository().get_hike_route_import(hike_id)


@st.cache_data(show_spinner=False)
def fetch_all_hike_route_imports() -> list[dict[str, Any]]:
    return _repository().list_hike_route_imports()


@st.cache_data(show_spinner=False)
def fetch_hike_photos(hike_id: str) -> list[dict[str, Any]]:
    return _repository().list_photos(hike_id)


@st.cache_data(show_spinner=False)
def fetch_standalone_photos() -> list[dict[str, Any]]:
    return _repository().list_standalone_photos()


@st.cache_data(show_spinner=False)
def fetch_hike_map_photos(hike_id: str) -> list[dict[str, Any]]:
    return _repository().list_map_photos(hike_id)


@st.cache_data(show_spinner=False)
def fetch_all_map_photos() -> list[dict[str, Any]]:
    return _repository().list_map_photos()


@st.cache_data(show_spinner=False)
def fetch_review_queue_photos() -> list[dict[str, Any]]:
    return _repository().list_review_queue_photos()


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


@st.cache_data(show_spinner=False)
def fetch_photo_records_for_ids(photo_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    return _repository().list_photo_records_for_ids(list(photo_ids))


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
    fetch_hikes,
    fetch_hike_locations,
    fetch_hike_location_tags,
    fetch_hike_route_import,
    fetch_all_hike_route_imports,
    fetch_hike_photos,
    fetch_standalone_photos,
    fetch_hike_map_photos,
    fetch_all_map_photos,
    fetch_review_queue_photos,
    fetch_photo_hike_refs,
    fetch_photo_storage_records,
    fetch_hike_observations,
    fetch_hike_lightweight_observations,
    fetch_all_lightweight_observations,
    fetch_lightweight_observations_for_photo_ids,
    fetch_confirmed_observations_light,
    fetch_photo_records_for_ids,
    fetch_observations_by_ids,
    fetch_species_log_photo_preferences,
    fetch_observations_for_photo_ids,
    fetch_confirmed_observation_hike_refs,
)


def invalidate_data_cache() -> None:
    for query in _CACHED_QUERIES:
        query.clear()
