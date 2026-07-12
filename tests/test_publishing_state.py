from hike_journal.publishing_state import (
    build_publish_rows,
    count_publish_states,
    filter_publish_rows,
    get_publish_state,
    reset_publish_page,
    set_publish_rows_selected,
    synchronize_publish_selection,
)


def posting_resolver(observation: dict) -> dict:
    return observation.get("_posting") or {}


def row(
    suffix: str,
    *,
    state: str = "Ready to post",
    hike_id: str | None = "hike-1",
    common_name: str = "Swamp lily",
) -> dict:
    return {
        "observation": {
            "id": f"observation-{suffix}",
            "hike_id": hike_id,
            "common_name": common_name,
            "scientific_name": "Crinum americanum",
            "taxon_id": 123,
        },
        "photo": {"id": f"photo-{suffix}"},
        "hike": {
            "id": hike_id,
            "title": "Black Bear Wilderness" if hike_id else "Standalone sighting",
            "location_name": "Sanford",
        },
        "publish_state": state,
    }


def test_publish_state_distinguishes_ready_posted_and_missing_photo() -> None:
    assert get_publish_state({}, posting_resolver) == "Ready to post"
    assert get_publish_state({"_posting": {"observation_id": 42}}, posting_resolver) == "Posted"
    assert get_publish_state(
        {"_posting": {"observation_id": 42, "photo_attached": False}},
        posting_resolver,
    ) == "Needs attention"


def test_build_publish_rows_preserves_ordering_and_standalone_fallback() -> None:
    hikes = [{"id": "hike-1", "title": "Black Bear Wilderness"}]
    observations = [
        {"id": "ready", "photo_id": "photo-ready", "hike_id": "hike-1"},
        {
            "id": "attention",
            "photo_id": "photo-attention",
            "hike_id": None,
            "_posting": {"observation_id": 42, "photo_attached": False},
        },
        {"id": "missing-photo", "photo_id": "not-found", "hike_id": "hike-1"},
    ]
    photos = [
        {"id": "photo-ready", "taken_at": "2026-07-11T12:00:00"},
        {"id": "photo-attention", "taken_at": "2026-07-10T12:00:00", "caption": "Backyard"},
    ]

    rows = build_publish_rows(hikes, observations, photos, posting_resolver=posting_resolver)

    assert [item["observation"]["id"] for item in rows] == ["attention", "ready"]
    assert rows[0]["hike"] == {
        "title": "Standalone sighting",
        "hike_date": "2026-07-10T12:00:00",
        "location_name": "Backyard",
    }
    assert count_publish_states(rows) == {
        "Ready to post": 1,
        "Needs attention": 1,
        "Posted": 0,
    }


def test_filter_publish_rows_combines_state_hike_and_search_filters() -> None:
    hikes = [{"id": "hike-1", "title": "Black Bear Wilderness"}]
    rows = [
        row("ready"),
        row("posted", state="Posted", common_name="Live oak"),
        row("quick", hike_id=None, common_name="Backyard mushroom"),
    ]

    assert filter_publish_rows(
        rows,
        hikes,
        publish_filter="Ready to post",
        hike_filter="Black Bear Wilderness",
        query="lily",
        quick_upload_filter="Quick uploads",
    ) == [rows[0]]
    assert filter_publish_rows(
        rows,
        hikes,
        publish_filter="All",
        hike_filter="Quick uploads",
        query="mushroom",
        quick_upload_filter="Quick uploads",
    ) == [rows[2]]


def test_selection_sync_prunes_hidden_rows_and_respects_widgets() -> None:
    rows = [row("a"), row("b")]
    state = {
        "publish_selected_ids": {"observation-a", "observation-hidden"},
        "publish_select_observation-a": False,
        "publish_select_observation-b": True,
    }

    assert synchronize_publish_selection(state, rows) == {"observation-b"}
    assert state["publish_selected_ids"] == {"observation-b"}


def test_bulk_selection_updates_ids_and_checkbox_state() -> None:
    rows = [row("a"), row("b")]
    state = {"publish_selected_ids": {"observation-existing"}}

    assert set_publish_rows_selected(state, rows, True) == {
        "observation-existing",
        "observation-a",
        "observation-b",
    }
    assert state["publish_select_observation-a"] is True
    assert state["publish_select_observation-b"] is True

    assert set_publish_rows_selected(state, [rows[0]], False) == {
        "observation-existing",
        "observation-b",
    }
    assert state["publish_select_observation-a"] is False


def test_reset_publish_page_only_resets_the_page() -> None:
    state = {"publish_page": 4, "publish_page_size": 18}

    reset_publish_page(state)

    assert state == {"publish_page": 1, "publish_page_size": 18}
