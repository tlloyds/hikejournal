from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, Callable


StateDefault = Any | Callable[[], Any]


SESSION_DEFAULTS: dict[str, StateDefault] = {
    "selected_hike_id": None,
    "viewer_open": False,
    "viewer_index": 0,
    "journal_page": 1,
    "journal_page_size": 9,
    "species_page": 1,
    "species_page_size": 6,
    "species_selected_ids": set,
    "known_species_selected_ids": set,
    "known_species_notice": None,
    "species_review_stage": "All",
    "species_review_stage_signature": tuple,
    "species_review_stage_selection_signature": tuple,
    "species_review_mode": "Review",
    "delete_photo_ids": set,
    "delete_mode": False,
    "active_view": "Library",
    "pending_view": None,
    "query_state_signature": None,
    "inat_auth_error": None,
    "inat_auth_notice": None,
    "inat_token_input": "",
    "inat_oauth_state": None,
    "inat_oauth_attempt_state": None,
    "inat_token_dialog_open": False,
    "species_log_hike_filter": "All hikes",
    "species_log_mapped_only": False,
    "species_log_include_secondary": True,
    "species_log_sort": "Most recent",
    "species_log_posted_filter": "All",
    "species_log_page": 1,
    "journal_upload_nonce": 0,
    "quick_upload_nonce": 0,
    "journal_upload_notice": None,
    "quick_upload_notice": None,
    "species_log_page_size": 8,
    "species_log_focus_key": None,
    "species_log_record_open": False,
    "species_review_initialized_signature": None,
    "inat_post_feedback": dict,
    "inat_sync_candidates": dict,
    "inat_sync_selected_ids": set,
    "inat_sync_checked_count": 0,
    "inat_sync_error": None,
    "inat_sync_notice": None,
    "viewer_notice": None,
    "library_group_by": "Month",
    "library_page": 1,
    "library_page_size": 8,
    "publish_filter": "Ready to post",
    "publish_selected_ids": set,
    "publish_page": 1,
    "publish_page_size": 8,
    "publish_query": "",
    "publish_hike_filter": "All hikes",
    "publish_batch_notice": None,
    "location_library_notice": None,
}


def initialize_session_state(state: MutableMapping[str, Any]) -> None:
    """Populate missing Streamlit state without overwriting an active session."""
    for key, default in SESSION_DEFAULTS.items():
        if key not in state:
            state[key] = default() if callable(default) else default


def reset_home_navigation_state(state: MutableMapping[str, Any]) -> None:
    """Clear transient navigation state so the app returns to its home view."""
    state["selected_hike_id"] = None
    state["viewer_open"] = False
    state["viewer_index"] = 0
    state["active_view"] = "Library"
    state["pending_view"] = None
    state["journal_page"] = 1
    state["species_page"] = 1
    state["species_log_page"] = 1
    state["library_page"] = 1
    state["species_log_focus_key"] = None
    state["species_log_record_open"] = False
