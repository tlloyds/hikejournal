from inspect import signature

import app

from hike_journal.ui.views.library import render_library_view
from hike_journal.ui.views.journal import (
    JournalActions,
    render_journal_view,
    render_standalone_journal_view,
)
from hike_journal.ui.views.map import render_map_view
from hike_journal.ui.views.publishing import PublishingActions, render_publishing_view
from hike_journal.ui.views.species_log import render_species_log_view
from hike_journal.ui.views.species_review import SpeciesReviewActions, render_species_review_view


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

    app.render_map_tab(object(), [], {}, selected_hike=None)

    assert captured["format_confidence_label"] is app.format_confidence_label


def test_login_gate_uses_wordmark_hero_and_left_aligned_action(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(app, "render_hero", lambda *args, **kwargs: captured.update(kwargs))
    monkeypatch.setattr(app, "section_heading", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "write", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        app.st,
        "columns",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Login action must not use centering columns")),
    )

    app.render_login_gate()

    assert captured["login_mode"] is True


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


def test_journal_action_contract_contains_every_app_callback() -> None:
    assert set(JournalActions.__dataclass_fields__) == {
        "_parse_date",
        "paginate_photos",
        "persist_uploaded_photo",
        "render_alternate_suggestions",
        "render_bottom_review_handoff",
        "render_known_species_assignment_toolbar",
        "render_photo_management_toolbar",
        "render_photo_note_editor",
        "render_photo_species_actions",
        "render_quick_upload_dialog",
        "render_secondary_species_summary",
        "render_selection_toolbar",
        "render_species_summary",
        "sync_hike_cover_checkbox",
        "sync_journal_review_checkbox",
        "sync_known_species_checkbox",
    }


def test_app_standalone_journal_wrapper_forwards_action_contract(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(
        app,
        "render_standalone_journal_view",
        lambda *args, **kwargs: captured.update(kwargs),
    )

    app.render_standalone_journal_tab(object(), object(), object(), [], {}, {}, {}, [])

    assert isinstance(captured["actions"], JournalActions)
    assert captured["actions"].render_quick_upload_dialog is app.render_quick_upload_dialog


def test_app_hike_journal_wrapper_forwards_action_contract(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(app, "render_journal_view", lambda *args, **kwargs: captured.update(kwargs))

    app.render_journal_tab(object(), object(), object(), {"id": "hike-1"}, [], {}, {}, None, [])

    assert isinstance(captured["actions"], JournalActions)
    assert captured["actions"].persist_uploaded_photo is app.persist_uploaded_photo
    assert captured["actions"].sync_hike_cover_checkbox is app.sync_hike_cover_checkbox


def test_journal_views_require_the_action_contract() -> None:
    assert "actions" in signature(render_journal_view).parameters
    assert "actions" in signature(render_standalone_journal_view).parameters


def test_species_review_action_contract_contains_every_app_callback() -> None:
    assert set(SpeciesReviewActions.__dataclass_fields__) == {
        "build_publish_rows",
        "count_publish_states",
        "paginate_items",
        "render_add_species_popover",
        "render_alternate_suggestions",
        "render_back_to_top_link",
        "render_community_id_request_controls",
        "render_inat_token_manager",
        "render_photo_note_editor",
        "render_publishing_section",
        "render_secondary_species_summary",
        "render_species_management_toolbar",
        "render_species_summary",
    }


def test_app_species_review_wrapper_forwards_action_contract(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(app, "render_species_review_view", lambda *args, **kwargs: captured.update(kwargs))

    app.render_species_tab(object(), object(), [], [], [], [], {}, {})

    assert isinstance(captured["actions"], SpeciesReviewActions)
    assert captured["actions"].render_species_management_toolbar is app.render_species_management_toolbar
    assert captured["actions"].render_publishing_section is app.render_publishing_section


def test_species_review_view_requires_the_action_contract() -> None:
    assert "actions" in signature(render_species_review_view).parameters


def test_publishing_action_contract_contains_every_app_callback() -> None:
    assert set(PublishingActions.__dataclass_fields__) == {
        "get_inat_posting",
        "inat_connection_action_label",
        "invalidate_data_cache",
        "is_inat_client_ready",
        "open_inat_token_dialog",
        "open_publish_plan",
        "paginate_items",
        "render_inat_posting_controls",
        "render_publish_lane_management_controls",
        "resolve_page_size",
    }


def test_app_publishing_wrapper_forwards_action_contract(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(app, "render_publishing_view", lambda *args, **kwargs: captured.update(kwargs))

    app.render_publishing_section(object(), object(), [], [], [])

    assert isinstance(captured["actions"], PublishingActions)
    assert captured["quick_upload_hike_filter"] == app.QUICK_UPLOAD_HIKE_FILTER
    assert captured["actions"].open_publish_plan is app.open_publish_plan


def test_publishing_view_requires_the_action_contract() -> None:
    assert "actions" in signature(render_publishing_view).parameters
