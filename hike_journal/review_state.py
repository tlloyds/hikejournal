from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


def photo_ids(photos: list[dict[str, Any]]) -> set[str]:
    return {str(photo["id"]) for photo in photos if photo.get("id")}


def set_photo_selected(
    state: MutableMapping[str, Any],
    photo_id: str,
    selected: bool,
    *,
    update_widget: bool = True,
) -> None:
    selected_ids = set(state.get("species_selected_ids") or set())
    if selected:
        selected_ids.add(photo_id)
    else:
        selected_ids.discard(photo_id)
    state["species_selected_ids"] = selected_ids
    if update_widget:
        state[f"species_select_{photo_id}"] = selected


def set_photos_selected(
    state: MutableMapping[str, Any],
    photos: list[dict[str, Any]],
    selected: bool,
    *,
    update_widgets: bool = True,
) -> None:
    for photo_id in photo_ids(photos):
        set_photo_selected(state, photo_id, selected, update_widget=update_widgets)


def synchronize_species_selection(
    state: MutableMapping[str, Any],
    photos: list[dict[str, Any]],
) -> set[str]:
    valid_ids = photo_ids(photos)
    selected_ids = {
        str(photo_id)
        for photo_id in state.get("species_selected_ids") or set()
        if str(photo_id) in valid_ids
    }
    for photo_id in valid_ids:
        checkbox_key = f"species_select_{photo_id}"
        if checkbox_key not in state:
            continue
        if state[checkbox_key]:
            selected_ids.add(photo_id)
        else:
            selected_ids.discard(photo_id)
    state["species_selected_ids"] = selected_ids
    return selected_ids


def apply_species_review_defaults(
    state: MutableMapping[str, Any],
    photos: list[dict[str, Any]],
) -> bool:
    signature = tuple(str(photo["id"]) for photo in photos if photo.get("id"))
    if state.get("species_review_initialized_signature") == signature:
        return False
    state["species_review_initialized_signature"] = signature
    state["species_page"] = 1
    state["species_page_size"] = 0 if photos else 6
    state["species_selected_ids"] = set(signature)
    set_photos_selected(state, photos, True)
    return True


def initialize_stage_selection(
    state: MutableMapping[str, Any],
    review_stage: str,
    photos: list[dict[str, Any]],
) -> bool:
    signature = (review_stage, tuple(str(photo["id"]) for photo in photos if photo.get("id")))
    if state.get("species_review_stage_selection_signature") == signature:
        return False
    state["species_review_stage_selection_signature"] = signature
    state["species_selected_ids"] = photo_ids(photos)
    set_photos_selected(state, photos, True)
    return True


def sync_visible_widget_selection(
    state: MutableMapping[str, Any],
    photos: list[dict[str, Any]],
) -> set[str]:
    visible_ids = photo_ids(photos)
    current_selected = set(state.get("species_selected_ids") or set())
    selected_visible = {
        photo_id
        for photo_id in visible_ids
        if state.get(f"species_select_{photo_id}", photo_id in current_selected)
    }
    state["species_selected_ids"] = (current_selected - visible_ids) | selected_visible
    return selected_visible


def clear_species_selection(
    state: MutableMapping[str, Any],
    photos: list[dict[str, Any]],
) -> None:
    set_photos_selected(state, photos, False, update_widgets=False)
    for photo_id in photo_ids(photos):
        checkbox_key = f"species_select_{photo_id}"
        if checkbox_key in state:
            state[checkbox_key] = False
