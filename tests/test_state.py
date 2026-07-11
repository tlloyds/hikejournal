from hike_journal.ui.state import SESSION_DEFAULTS, initialize_session_state


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
