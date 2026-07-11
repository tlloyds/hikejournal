from inspect import signature

import app

from hike_journal.ui.views.library import render_library_view
from hike_journal.ui.views.map import render_map_view
from hike_journal.ui.views.species_log import render_species_log_view


def test_library_view_accepts_its_app_callbacks() -> None:
    expected = {
        "navigate_to",
        "paginate_items",
        "render_back_to_top_link",
        "render_create_hike_dialog",
        "render_edit_hike_dialog",
        "render_quick_upload_dialog",
        "reset_library_page",
    }

    assert expected.issubset(signature(render_library_view).parameters)


def test_map_view_accepts_confidence_formatter() -> None:
    assert "format_confidence_label" in signature(render_map_view).parameters


def test_species_log_view_accepts_its_app_callbacks() -> None:
    expected = {
        "quick_upload_hike_filter",
        "build_species_log_record_href",
        "paginate_items",
        "render_back_to_top_link",
        "render_species_log_inat_sync_panel",
        "render_species_log_toolbar",
        "render_species_record_dialog",
        "reset_species_log_page",
        "resolve_page_size",
        "set_species_log_record_query_state",
    }

    assert expected.issubset(signature(render_species_log_view).parameters)


def test_app_library_wrapper_forwards_every_callback(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(app, "render_library_view", lambda *args, **kwargs: captured.update(kwargs))

    app.render_library_tab(object(), object(), [], [], [], {}, {})

    assert set(captured) == {
        "navigate_to",
        "paginate_items",
        "render_back_to_top_link",
        "render_create_hike_dialog",
        "render_edit_hike_dialog",
        "render_quick_upload_dialog",
        "reset_library_page",
    }


def test_app_map_wrapper_forwards_confidence_formatter(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(app, "render_map_view", lambda *args, **kwargs: captured.update(kwargs))

    app.render_map_tab([], {}, {}, selected_hike=None, route_imports_by_hike={})

    assert captured["format_confidence_label"] is app.format_confidence_label


def test_app_species_log_wrapper_forwards_every_callback(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(app, "render_species_log_view", lambda *args, **kwargs: captured.update(kwargs))

    app.render_species_log_tab(object(), object(), [], {})

    assert set(captured) == {
        "quick_upload_hike_filter",
        "build_species_log_record_href",
        "paginate_items",
        "render_back_to_top_link",
        "render_species_log_inat_sync_panel",
        "render_species_log_toolbar",
        "render_species_record_dialog",
        "reset_species_log_page",
        "resolve_page_size",
        "set_species_log_record_query_state",
    }
