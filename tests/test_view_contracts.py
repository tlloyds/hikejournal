from inspect import getsource, signature

import app

from hike_journal.ui.views.badges import render_badges_view
from hike_journal.ui.views.library import render_library_view
from hike_journal.ui.views.journal import (
    JournalActions,
    render_journal_view,
    render_standalone_journal_view,
)
from hike_journal.ui.views.map import render_map_view
from hike_journal.ui.views.publishing import PublishingActions, render_publishing_view
from hike_journal.ui.views.species_log import (
    _render_nearby_mode,
    _render_quests_mode,
    render_species_log_view,
)
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


def test_badges_view_accepts_owner_scoped_inputs() -> None:
    assert set(signature(render_badges_view).parameters) == {
        "repository",
        "hikes",
        "confirmed_observations",
        "user_context",
    }


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


def test_species_log_view_exposes_collection_nearby_and_field_quests() -> None:
    source = getsource(render_species_log_view)

    assert '["Collection", "Nearby", "Field Quests"]' in source
    assert '"Observation type"' in source
    assert "species_log_type_filter" in source
    assert "_render_nearby_mode" in source
    assert "_render_quests_mode" in source


def test_species_discovery_uses_searchable_areas_and_direct_focus_controls() -> None:
    nearby_source = getsource(_render_nearby_mode)
    quests_source = getsource(_render_quests_mode)

    assert '"Search saved trails"' in nearby_source
    assert 'placeholder="Type a trail name…"' in nearby_source
    assert "index=default_index" in nearby_source
    assert "st.multiselect" not in nearby_source
    assert "st.multiselect" not in quests_source
    assert "focus_state_key=focus_state_key" in nearby_source
    assert "focus_state_key=focus_state_key" in quests_source
    assert "disabled=not focus_ids" in nearby_source
    assert '"Expand to 100 species"' in nearby_source
    assert 'payload["focus_taxa"]' in quests_source
    assert '"Open quest"' in quests_source
    assert '"Change targets"' in quests_source
    assert '"Delete permanently"' in quests_source


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


def test_app_badges_wrapper_forwards_collection_data(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(app, "render_badges_view", lambda *args: captured.extend(args))
    repository = object()
    hikes = [{"id": "hike-1"}]
    observations = [{"taxon_id": 42}]
    user_context = {"subject": "user-1"}

    app.render_badges_tab(repository, hikes, observations, user_context)

    assert captured == [repository, hikes, observations, user_context]


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


def test_open_outing_sidebar_uses_html_safe_markup_without_a_location() -> None:
    markup = app.build_open_outing_sidebar_markup(
        {
            "id": "hike-1",
            "title": "Aldi",
            "hike_date": "2026-08-01",
            "location_name": None,
        },
        active_view="Journal",
    )

    assert "\n" not in markup
    assert '<div class="sidebar-current-actions">' in markup
    assert 'class="sidebar-current-action active"' in markup
    assert 'href="?view=Journal&amp;hike=hike-1"' in markup
    assert 'href="?view=Map&amp;hike=hike-1"' in markup
    assert '<div class="sidebar-current-meta">2026-08-01</div>' in markup


def test_open_outing_sidebar_escapes_hike_details() -> None:
    markup = app.build_open_outing_sidebar_markup(
        {
            "id": "hike & 1",
            "title": "<Aldi>",
            "hike_date": "2026-08-01",
            "location_name": "<Trail>",
        },
        active_view="Map",
    )

    assert "&lt;Aldi&gt;" in markup
    assert "2026-08-01 • &lt;Trail&gt;" in markup
    assert "hike%20%26%201" in markup
    assert 'class="sidebar-current-action active"' in markup


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
        "persist_uploaded_video",
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
