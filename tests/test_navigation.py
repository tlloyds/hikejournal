from hike_journal.navigation import (
    apply_navigation,
    build_internal_view_href,
    close_viewer_state,
    hydrate_query_state,
    query_state_for_view,
    set_species_log_record_query_state,
    sync_viewer_state,
)


def test_hydrate_query_state_parses_supported_values_once() -> None:
    state = {"query_state_signature": None, "journal_page": 1}
    query = {
        "journal_page": "3",
        "journal_page_size": "0",
        "species_log_mapped_only": "yes",
        "species_log_include_secondary": "off",
        "map_photo_range_start": "10",
        "map_photo_range_end": "20",
    }

    assert hydrate_query_state(state, query)
    assert state["journal_page"] == 3
    assert state["journal_page_size"] == 0
    assert state["species_log_mapped_only"] is True
    assert state["species_log_include_secondary"] is False
    assert state["map_photo_range"] == (10, 20)
    assert not hydrate_query_state(state, query)


def test_hydrate_query_state_ignores_invalid_values() -> None:
    state = {"query_state_signature": None, "journal_page": 2, "species_log_mapped_only": True}

    hydrate_query_state(state, {"journal_page": "0", "species_log_mapped_only": "perhaps"})

    assert state["journal_page"] == 2
    assert state["species_log_mapped_only"] is True


def test_navigation_replaces_stale_context() -> None:
    state = {"journal_page": 2, "journal_page_size": 9, "selected_hike_id": "old"}
    query = {"hike": "old", "photo": "old-photo", "map_photo": "old-map", "scope": "standalone"}

    apply_navigation(state, query, view="Journal", hike_id="new")

    assert state["active_view"] == "Journal"
    assert state["pending_view"] == "Journal"
    assert state["selected_hike_id"] == "new"
    assert query == {"view": "Journal", "journal_page": "2", "journal_page_size": "9", "hike": "new"}


def test_query_state_and_href_preserve_species_log_context() -> None:
    state = {
        "species_log_query": "oak & pine",
        "species_log_page": 2,
        "species_log_page_size": 8,
        "species_log_hike_filter": "All hikes",
        "species_log_sort": "Most recent",
        "species_log_posted_filter": "All",
        "species_log_mapped_only": True,
        "species_log_include_secondary": False,
        "species_log_focus_key": None,
        "species_log_record_open": False,
    }

    query = query_state_for_view("Species Log", state)
    href = build_internal_view_href(view="Species Log", state=state)

    assert query["species_log_mapped_only"] == "1"
    assert query["species_log_include_secondary"] == "0"
    assert "oak%20%26%20pine" in href


def test_species_record_and_viewer_state_are_isolated() -> None:
    query = {"species_log_focus_key": "old", "photo": "photo-2"}
    state = {"viewer_open": False, "viewer_index": 0}

    set_species_log_record_query_state(query, "scientific:quercus", True)
    found = sync_viewer_state(state, query, [{"id": "photo-1"}, {"id": "photo-2"}])

    assert query["species_log_focus_key"] == "scientific:quercus"
    assert query["species_log_record_open"] == "1"
    assert found
    assert state == {"viewer_open": True, "viewer_index": 1}


def test_closing_viewer_removes_photo_deep_link() -> None:
    state = {"viewer_open": True, "viewer_index": 1}
    query = {"view": "Journal", "hike": "hike-1", "photo": "photo-2"}

    close_viewer_state(state, query)

    assert state["viewer_open"] is False
    assert query == {"view": "Journal", "hike": "hike-1"}
