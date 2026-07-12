from hike_journal.review_state import (
    apply_species_review_defaults,
    clear_species_selection,
    initialize_stage_selection,
    set_photo_selected,
    sync_visible_widget_selection,
    synchronize_species_selection,
)


PHOTOS = [{"id": "photo-1"}, {"id": "photo-2"}]


def test_review_defaults_initialize_once_per_queue_signature() -> None:
    state = {"species_review_initialized_signature": None, "species_selected_ids": set()}

    assert apply_species_review_defaults(state, PHOTOS)
    assert state["species_page"] == 1
    assert state["species_page_size"] == 0
    assert state["species_selected_ids"] == {"photo-1", "photo-2"}
    state["species_page"] = 3
    assert not apply_species_review_defaults(state, PHOTOS)
    assert state["species_page"] == 3


def test_synchronize_selection_drops_stale_ids_and_reads_widgets() -> None:
    state = {
        "species_selected_ids": {"photo-1", "stale"},
        "species_select_photo-1": False,
        "species_select_photo-2": True,
    }

    selected = synchronize_species_selection(state, PHOTOS)

    assert selected == {"photo-2"}
    assert state["species_selected_ids"] == {"photo-2"}


def test_stage_selection_only_resets_when_stage_or_photos_change() -> None:
    state = {"species_review_stage_selection_signature": None, "species_selected_ids": set()}

    assert initialize_stage_selection(state, "Needs IDs", PHOTOS)
    set_photo_selected(state, "photo-1", False)
    assert not initialize_stage_selection(state, "Needs IDs", PHOTOS)
    assert state["species_selected_ids"] == {"photo-2"}
    assert initialize_stage_selection(state, "Finished", PHOTOS)
    assert state["species_selected_ids"] == {"photo-1", "photo-2"}


def test_visible_widget_sync_preserves_selection_outside_the_lane() -> None:
    state = {
        "species_selected_ids": {"outside", "photo-1"},
        "species_select_photo-1": False,
        "species_select_photo-2": True,
    }

    assert sync_visible_widget_selection(state, PHOTOS) == {"photo-2"}
    assert state["species_selected_ids"] == {"outside", "photo-2"}


def test_clear_selection_updates_existing_widgets() -> None:
    state = {
        "species_selected_ids": {"photo-1", "photo-2", "outside"},
        "species_select_photo-1": True,
    }

    clear_species_selection(state, PHOTOS)

    assert state["species_selected_ids"] == {"outside"}
    assert state["species_select_photo-1"] is False
