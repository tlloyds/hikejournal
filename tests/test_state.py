from hike_journal.ui.state import SESSION_DEFAULTS, initialize_session_state, reset_home_navigation_state


def test_initialize_session_state_preserves_existing_values() -> None:
    state = {"active_view": "Map", "journal_page": 4}

    initialize_session_state(state)

    assert state["active_view"] == "Map"
    assert state["journal_page"] == 4
    assert set(SESSION_DEFAULTS).issubset(state)


def test_initialize_session_state_creates_independent_mutable_values() -> None:
    first: dict = {}
    second: dict = {}

    initialize_session_state(first)
    initialize_session_state(second)
    first["species_selected_ids"].add("photo-1")
    first["inat_post_feedback"]["observation-1"] = "done"

    assert second["species_selected_ids"] == set()
    assert second["inat_post_feedback"] == {}


def test_reset_home_navigation_state_clears_transient_navigation() -> None:
    state = {
        "selected_hike_id": "hike-1",
        "viewer_open": True,
        "viewer_index": 4,
        "active_view": "Journal",
        "pending_view": "Map",
        "journal_page": 3,
        "species_page": 2,
        "species_log_page": 4,
        "library_page": 5,
        "species_log_focus_key": "oak",
        "species_log_record_open": True,
        "unrelated_preference": "keep",
    }

    reset_home_navigation_state(state)

    assert state == {
        "selected_hike_id": None,
        "viewer_open": False,
        "viewer_index": 0,
        "active_view": "Library",
        "pending_view": None,
        "journal_page": 1,
        "species_page": 1,
        "species_log_page": 1,
        "library_page": 1,
        "species_log_focus_key": None,
        "species_log_record_open": False,
        "unrelated_preference": "keep",
    }
