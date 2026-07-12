from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any


PostingResolver = Callable[[dict[str, Any]], dict[str, Any]]


def get_publish_state(observation: dict[str, Any], posting_resolver: PostingResolver) -> str:
    posting = posting_resolver(observation)
    if posting.get("observation_id"):
        if posting.get("photo_attached") is False:
            return "Needs attention"
        return "Posted"
    return "Ready to post"


def count_publish_states(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"Ready to post": 0, "Needs attention": 0, "Posted": 0}
    for row in rows:
        state = str(row.get("publish_state") or "")
        counts[state] = counts.get(state, 0) + 1
    return counts


def build_publish_rows(
    hikes: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    photos: list[dict[str, Any]],
    *,
    posting_resolver: PostingResolver,
) -> list[dict[str, Any]]:
    hike_by_id = {str(hike["id"]): hike for hike in hikes}
    photo_by_id = {str(photo["id"]): photo for photo in photos}
    rows: list[dict[str, Any]] = []
    for observation in confirmed_observations:
        photo = photo_by_id.get(str(observation.get("photo_id")))
        if not photo:
            continue
        hike = hike_by_id.get(str(observation.get("hike_id")), {})
        if not hike and not observation.get("hike_id"):
            hike = {
                "title": "Standalone sighting",
                "hike_date": photo.get("taken_at") or photo.get("created_at") or "",
                "location_name": photo.get("caption") or "Not attached to a hike",
            }
        rows.append(
            {
                "observation": observation,
                "photo": photo,
                "hike": hike,
                "publish_state": get_publish_state(observation, posting_resolver),
            }
        )
    rows.sort(
        key=lambda row: (
            {"Needs attention": 0, "Ready to post": 1, "Posted": 2}.get(row["publish_state"], 3),
            row["photo"].get("taken_at") or row["photo"].get("created_at") or "",
        )
    )
    return rows


def filter_publish_rows(
    rows: list[dict[str, Any]],
    hikes: list[dict[str, Any]],
    *,
    publish_filter: str,
    hike_filter: str,
    query: str,
    quick_upload_filter: str,
) -> list[dict[str, Any]]:
    hike_title_to_id = {
        str(hike.get("title") or "Untitled hike"): str(hike.get("id") or "")
        for hike in hikes
    }
    normalized_query = query.strip().casefold()
    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        if publish_filter != "All" and row["publish_state"] != publish_filter:
            continue
        observation = row["observation"]
        hike = row["hike"]
        if hike_filter == quick_upload_filter and observation.get("hike_id"):
            continue
        if hike_filter not in {"All hikes", quick_upload_filter} and str(observation.get("hike_id") or "") != hike_title_to_id.get(hike_filter):
            continue
        haystack = " ".join(
            str(value or "")
            for value in [
                observation.get("common_name"),
                observation.get("scientific_name"),
                observation.get("taxon_id"),
                hike.get("title"),
                hike.get("location_name"),
            ]
        ).casefold()
        if normalized_query and normalized_query not in haystack:
            continue
        filtered_rows.append(row)
    return filtered_rows


def synchronize_publish_selection(
    state: MutableMapping[str, Any],
    rows: list[dict[str, Any]],
) -> set[str]:
    valid_ids = {str(row["observation"]["id"]) for row in rows}
    selected_ids = {
        str(observation_id)
        for observation_id in state.get("publish_selected_ids") or set()
        if str(observation_id) in valid_ids
    }
    for observation_id in valid_ids:
        checkbox_key = f"publish_select_{observation_id}"
        if checkbox_key not in state:
            continue
        if state[checkbox_key]:
            selected_ids.add(observation_id)
        else:
            selected_ids.discard(observation_id)
    state["publish_selected_ids"] = selected_ids
    return selected_ids


def set_publish_rows_selected(
    state: MutableMapping[str, Any],
    rows: list[dict[str, Any]],
    selected: bool,
    *,
    update_widgets: bool = True,
) -> set[str]:
    selected_ids = set(state.get("publish_selected_ids") or set())
    for row in rows:
        observation_id = str(row["observation"]["id"])
        if selected:
            selected_ids.add(observation_id)
        else:
            selected_ids.discard(observation_id)
        if update_widgets:
            state[f"publish_select_{observation_id}"] = selected
    state["publish_selected_ids"] = selected_ids
    return selected_ids


def reset_publish_page(state: MutableMapping[str, Any]) -> None:
    state["publish_page"] = 1
