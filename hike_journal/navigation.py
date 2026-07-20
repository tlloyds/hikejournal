from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any
from urllib.parse import quote, urlencode


QUERY_STATE_KEYS = (
    "journal_page",
    "journal_page_size",
    "species_page",
    "species_page_size",
    "species_review_mode",
    "species_review_stage",
    "species_log_page",
    "species_log_page_size",
    "species_log_focus_key",
    "species_log_record_open",
    "map_layer_mode",
    "map_species_filter",
    "species_log_query",
    "species_log_hike_filter",
    "species_log_sort",
    "species_log_posted_filter",
    "species_log_mapped_only",
    "species_log_include_secondary",
    "map_photo_range_start",
    "map_photo_range_end",
)


def parse_int_query_param(query_params: Mapping[str, Any], key: str, *, minimum: int) -> int | None:
    raw_value = query_params.get(key)
    if raw_value is None:
        return None
    try:
        parsed = int(str(raw_value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= minimum else None


def parse_bool_query_param(query_params: Mapping[str, Any], key: str) -> bool | None:
    raw_value = query_params.get(key)
    if raw_value is None:
        return None
    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def hydrate_query_state(
    state: MutableMapping[str, Any],
    query_params: Mapping[str, Any],
) -> bool:
    signature = tuple((key, str(query_params.get(key, ""))) for key in QUERY_STATE_KEYS)
    if state.get("query_state_signature") == signature:
        return False

    for key, minimum in {
        "journal_page": 1,
        "species_page": 1,
        "journal_page_size": 0,
        "species_page_size": 0,
        "species_log_page": 1,
        "species_log_page_size": 0,
    }.items():
        parsed = parse_int_query_param(query_params, key, minimum=minimum)
        if parsed is not None:
            state[key] = parsed

    for key in {
        "species_review_mode",
        "species_review_stage",
        "species_log_focus_key",
        "map_layer_mode",
        "map_species_filter",
        "species_log_query",
        "species_log_hike_filter",
        "species_log_sort",
        "species_log_posted_filter",
    }:
        raw_value = query_params.get(key)
        if raw_value is not None:
            state[key] = str(raw_value)

    for key in {
        "species_log_record_open",
        "species_log_mapped_only",
        "species_log_include_secondary",
    }:
        parsed = parse_bool_query_param(query_params, key)
        if parsed is not None:
            state[key] = parsed

    map_range_start = parse_int_query_param(query_params, "map_photo_range_start", minimum=1)
    map_range_end = parse_int_query_param(query_params, "map_photo_range_end", minimum=1)
    if map_range_start is not None and map_range_end is not None:
        state["map_photo_range"] = (map_range_start, map_range_end)
    state["query_state_signature"] = signature
    return True


def query_state_for_view(view: str, state: Mapping[str, Any]) -> dict[str, str]:
    if view == "Journal":
        return {
            "journal_page": str(int(state.get("journal_page", 1))),
            "journal_page_size": str(int(state.get("journal_page_size", 9))),
        }
    if view == "Species Review":
        return {
            "species_page": str(int(state.get("species_page", 1))),
            "species_page_size": str(int(state.get("species_page_size", 6))),
            "species_review_mode": str(state.get("species_review_mode", "Review")),
            "species_review_stage": str(state.get("species_review_stage", "All")),
        }
    if view == "Map":
        query = {
            "map_layer_mode": str(state.get("map_layer_mode", "Both")),
            "map_species_filter": str(state.get("map_species_filter", "All confirmed species")),
        }
        map_range = state.get("map_photo_range")
        if isinstance(map_range, (tuple, list)) and len(map_range) == 2:
            query["map_photo_range_start"] = str(int(map_range[0]))
            query["map_photo_range_end"] = str(int(map_range[1]))
        return query
    if view == "Species Log":
        return {
            "species_log_query": str(state.get("species_log_query", "")).strip(),
            "species_log_page": str(int(state.get("species_log_page", 1))),
            "species_log_page_size": str(int(state.get("species_log_page_size", 8))),
            "species_log_hike_filter": str(state.get("species_log_hike_filter", "All hikes")),
            "species_log_sort": str(state.get("species_log_sort", "Most recent")),
            "species_log_posted_filter": str(state.get("species_log_posted_filter", "All")),
            "species_log_mapped_only": "1" if state.get("species_log_mapped_only") else "0",
            "species_log_include_secondary": "1" if state.get("species_log_include_secondary", True) else "0",
            "species_log_focus_key": str(state.get("species_log_focus_key") or ""),
            "species_log_record_open": "1" if state.get("species_log_record_open") else "0",
        }
    return {}


def apply_navigation(
    state: MutableMapping[str, Any],
    query_params: MutableMapping[str, Any],
    *,
    view: str,
    hike_id: str | None = None,
    photo_id: str | None = None,
    map_photo_id: str | None = None,
    scope: str | None = None,
) -> None:
    state["active_view"] = view
    state["pending_view"] = view
    query_params["view"] = view
    query_params.update(query_state_for_view(view, state))
    _set_or_remove(query_params, "scope", scope)
    if hike_id:
        state["selected_hike_id"] = hike_id
        query_params["hike"] = hike_id
    else:
        state["selected_hike_id"] = None
        query_params.pop("hike", None)
    _set_or_remove(query_params, "photo", photo_id)
    _set_or_remove(query_params, "map_photo", map_photo_id)


def _set_or_remove(query_params: MutableMapping[str, Any], key: str, value: str | None) -> None:
    if value:
        query_params[key] = value
    else:
        query_params.pop(key, None)


def build_internal_view_href(
    *,
    view: str,
    state: Mapping[str, Any],
    hike_id: str | None = None,
    scope: str | None = None,
) -> str:
    params: dict[str, Any] = {"view": view, **query_state_for_view(view, state)}
    if hike_id:
        params["hike"] = hike_id
    if scope:
        params["scope"] = scope
    return f"?{urlencode(params, quote_via=quote)}"


def build_species_log_record_href(focus_key: str, state: Mapping[str, Any]) -> str:
    params = {"view": "Species Log", **query_state_for_view("Species Log", state)}
    params["species_log_focus_key"] = str(focus_key)
    params["species_log_record_open"] = "1"
    return f"?{urlencode(params, quote_via=quote)}"


def set_species_log_record_query_state(
    query_params: MutableMapping[str, Any],
    focus_key: str | None,
    is_open: bool,
) -> None:
    _set_or_remove(query_params, "species_log_focus_key", focus_key)
    query_params["species_log_record_open"] = "1" if is_open else "0"


def sync_viewer_state(
    state: MutableMapping[str, Any],
    query_params: Mapping[str, Any],
    photos: list[dict[str, Any]],
) -> bool:
    photo_id = query_params.get("photo")
    if not photo_id:
        return False
    for index, photo in enumerate(photos):
        if photo.get("id") == str(photo_id):
            state["viewer_open"] = True
            state["viewer_index"] = index
            return True
    return False


def close_viewer_state(
    state: MutableMapping[str, Any],
    query_params: MutableMapping[str, Any],
) -> None:
    """Close the photo viewer and remove the URL state that would reopen it."""
    state["viewer_open"] = False
    query_params.pop("photo", None)
