from __future__ import annotations

from typing import Any

import streamlit as st

from hike_journal.domain.map_data import bounds_from_point_features, fallback_route_features, normalize_bounds, viewport_from_value
from hike_journal.queries import fetch_unindexed_map_routes
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.ui.components import section_heading
from hike_journal.ui.map_component import map_viewer_url, render_maplibre


DEFAULT_MASTER_MAP_PHOTO_LIMIT = 250


def render_map_view(
    repository: HikeJournalRepository,
    visible_hikes: list[dict[str, Any]],
    user_context: dict[str, Any],
    *,
    selected_hike: dict[str, Any] | None,
    format_confidence_label: Any,
) -> None:
    del user_context  # visibility is represented by visible_hikes
    if selected_hike:
        section_heading(
            "Outing map",
            "Route and observations",
            "Follow the track, open geotagged photographs, and inspect confirmed species in place.",
        )
    else:
        section_heading(
            "Master map",
            "Your field record in place",
            "Browse geotagged photographs across every outing and filter the confirmed species layered over them.",
        )
    st.write("")

    visible_hike_ids = [str(hike["id"]) for hike in visible_hikes if hike.get("id")]
    selected_hike_id = str(selected_hike["id"]) if selected_hike else None
    summary = repository.get_map_summary(visible_hike_ids=visible_hike_ids, hike_id=selected_hike_id)
    photo_count = max(0, int(summary.get("photo_count") or 0))
    species_names = [str(name) for name in summary.get("species") or [] if str(name).strip()]
    species_count = int(summary.get("species_count") or len(species_names))

    valid_layer_modes = {"Both", "Photos", "Species"}
    if st.session_state.get("map_layer_mode") not in valid_layer_modes:
        st.session_state.map_layer_mode = "Both"
    valid_species_filters = {"All confirmed species", *species_names}
    if st.session_state.get("map_species_filter") not in valid_species_filters:
        st.session_state.map_species_filter = "All confirmed species"

    controls = st.columns([0.24, 0.28, 0.25, 0.23], gap="small")
    layer_mode = controls[0].radio(
        "Map layer",
        ["Both", "Photos", "Species"],
        horizontal=True,
        label_visibility="collapsed",
        key="map_layer_mode",
    )
    species_filter = controls[1].selectbox(
        "Species filter",
        ["All confirmed species", *species_names],
        label_visibility="collapsed",
        key="map_species_filter",
        disabled=layer_mode == "Photos",
    )

    max_index = max(1, photo_count)
    map_scope = selected_hike_id or "master"
    scope_changed = st.session_state.get("map_photo_range_scope") not in {None, map_scope}
    range_is_new = "map_photo_range" not in st.session_state or scope_changed
    if range_is_new:
        default_start = max(1, max_index - DEFAULT_MASTER_MAP_PHOTO_LIMIT + 1) if not selected_hike else 1
        st.session_state.map_photo_range = (default_start, max_index)
    current_range = st.session_state.get("map_photo_range", (1, max_index))
    start = min(max(1, int(current_range[0])), max_index)
    end = min(max(start, int(current_range[1])), max_index)
    st.session_state.map_photo_range = (start, end)
    st.session_state.map_photo_range_scope = map_scope
    photo_range = controls[2].slider(
        "Photo range",
        min_value=1,
        max_value=max_index,
        key="map_photo_range",
        label_visibility="collapsed",
        disabled=photo_count == 0,
    )
    displayed_count = 0 if photo_count == 0 else photo_range[1] - photo_range[0] + 1
    scope_label = "in this outing" if selected_hike else "across your library"
    controls[3].caption(f"{displayed_count:,} of {photo_count:,} photos • {species_count:,} species {scope_label}")

    fit_bounds = normalize_bounds(summary.get("bounds"))
    component_key = f"maplibre_{map_scope}"
    component_state = st.session_state.get(component_key, {})
    viewport_value = component_state.get("viewport") if isinstance(component_state, dict) else None
    range_signature = (int(photo_range[0]), int(photo_range[1]))
    range_state_key = f"maplibre_range_signature_{map_scope}"
    previous_range_signature = st.session_state.get(range_state_key)
    range_changed = previous_range_signature is not None and previous_range_signature != range_signature
    st.session_state[range_state_key] = range_signature
    should_refit = viewport_value is None or range_changed
    viewport = viewport_from_value(None if should_refit else viewport_value, fallback_bounds=fit_bounds)

    markers = repository.get_map_viewport(
        visible_hike_ids=visible_hike_ids,
        hike_id=selected_hike_id,
        viewport=viewport,
        layer_mode=layer_mode,
        species_filter=species_filter,
        range_start=photo_range[0],
        range_end=photo_range[1],
    )
    routes = repository.get_map_routes_viewport(
        visible_hike_ids=visible_hike_ids,
        hike_id=selected_hike_id,
        viewport=viewport,
    )
    route_count, indexed_route_count = repository.get_map_route_index_status(
        visible_hike_ids=visible_hike_ids,
        hike_id=selected_hike_id,
    )
    if indexed_route_count < route_count:
        transitional_routes = fallback_route_features(
            fetch_unindexed_map_routes(tuple(visible_hike_ids), selected_hike_id),
            visible_hike_ids=set(visible_hike_ids),
            selected_hike_id=selected_hike_id,
            viewport=viewport,
        )
        routes["features"] = [*(routes.get("features") or []), *(transitional_routes.get("features") or [])]
    if not summary.get("spatial_rpc_ready") and not routes.get("features"):
        routes = fallback_route_features(
            repository.list_hike_route_imports(),
            visible_hike_ids=set(visible_hike_ids),
            selected_hike_id=selected_hike_id,
            viewport=viewport,
        )

    selection = component_state.get("selection") if isinstance(component_state, dict) else None
    selected_photo_id = str((selection or {}).get("photo_id") or st.query_params.get("map_photo") or "").strip()
    detail = repository.get_map_photo_detail(photo_id=selected_photo_id, visible_hike_ids=visible_hike_ids) if selected_photo_id else None
    if detail:
        for observation in detail.get("observations") or []:
            observation["confidence_label"] = format_confidence_label(observation)
        detail["viewer_url"] = map_viewer_url(detail, selected_hike_id=selected_hike_id)

    requested_fit_bounds = (bounds_from_point_features(markers) or fit_bounds) if should_refit else None
    fit_request = f"{map_scope}:{range_signature[0]}:{range_signature[1]}" if should_refit else None

    if not summary.get("spatial_rpc_ready"):
        st.info("The map is using its compatibility query path. Apply sql/scalable_maps_migration.sql to enable spatial clustering and zoom-aware route queries.")
    elif indexed_route_count < route_count:
        st.info(
            f"{route_count - indexed_route_count} saved routes still need their spatial backfill. "
            "They are shown through the compatibility path for now; rerun sql/scalable_maps_migration.sql to index them."
        )
    if photo_count == 0 and not routes.get("features"):
        st.warning("No map coordinates are available for the photos in view yet.")
        return

    render_maplibre(
        key=component_key,
        markers=markers,
        routes=routes,
        fit_bounds=requested_fit_bounds,
        fit_request=fit_request,
        detail=detail,
    )

    meta = markers.get("meta") or {}
    matched = int(meta.get("matched") or 0)
    if matched:
        mode = "clustered" if meta.get("clustered") else "visible"
        st.caption(f"{matched:,} map records in this area • {mode} for zoom {viewport.zoom:.1f}")
