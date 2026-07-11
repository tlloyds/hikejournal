from __future__ import annotations

from collections import defaultdict
from typing import Any

import streamlit as st

from hike_journal.domain.routes import route_import_to_route_groups
from hike_journal.ui.components import (
    format_photo_meta,
    get_photo_thumbnail_url,
    render_rich_map,
    section_heading,
)


def render_map_view(
    photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    *,
    selected_hike: dict[str, Any] | None,
    route_imports_by_hike: dict[str, dict[str, Any]],
    format_confidence_label: Any,
) -> None:
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
    geotagged_photos = [photo for photo in photos if photo.get("lat") is not None and photo.get("lng") is not None]
    imported_route_groups: list[list[dict[str, float]]] = []
    if selected_hike:
        imported_route_groups = route_import_to_route_groups(route_imports_by_hike.get(str(selected_hike["id"])))
    else:
        imported_route_groups = [
            points
            for route_import in route_imports_by_hike.values()
            for points in route_import_to_route_groups(route_import)
        ]

    if not geotagged_photos and not imported_route_groups:
        timestamped_photos = len([photo for photo in photos if photo.get("taken_at")])
        st.warning(
            "No map coordinates are available for the photos in view yet."
        )
        if photos:
            st.caption(
                f"{len(photos)} photos are loaded. {timestamped_photos} include capture times, but none of them currently include GPS coordinates."
            )
        return

    confirmed_species = []
    for photo in geotagged_photos:
        for observation in observations_by_photo.get(photo["id"], []):
            if observation.get("status") == "confirmed":
                confirmed_species.append((photo, observation))

    focused_photo_id = str(st.query_params.get("map_photo")) if st.query_params.get("map_photo") else None
    focused_index = None
    if focused_photo_id:
        ordered_for_focus = sorted(
            geotagged_photos,
            key=lambda photo: (photo.get("taken_at") or "", photo.get("created_at") or "", photo["id"]),
        )
        for index, photo in enumerate(ordered_for_focus, start=1):
            if photo["id"] == focused_photo_id:
                focused_index = index
                break

    unique_species = sorted(
        {
            observation.get("common_name") or observation.get("scientific_name") or "Confirmed species"
            for _, observation in confirmed_species
        }
    )
    valid_layer_modes = {"Both", "Photos", "Species"}
    if st.session_state.get("map_layer_mode") not in valid_layer_modes:
        st.session_state.map_layer_mode = "Both"
    valid_species_filters = {"All confirmed species", *unique_species}
    if st.session_state.get("map_species_filter") not in valid_species_filters:
        st.session_state.map_species_filter = "All confirmed species"
    control_cols = st.columns([0.26, 0.26, 0.22, 0.26], gap="small")
    layer_mode = control_cols[0].radio(
        "Map layer",
        ["Both", "Photos", "Species"],
        horizontal=True,
        label_visibility="collapsed",
        key="map_layer_mode",
    )
    species_filter = control_cols[1].selectbox(
        "Species filter",
        ["All confirmed species", *unique_species],
        label_visibility="collapsed",
        key="map_species_filter",
    )
    photo_count = len(geotagged_photos)
    max_index = max(1, photo_count)
    if focused_index:
        st.session_state.map_photo_range = (focused_index, focused_index)
    else:
        current_range = st.session_state.get("map_photo_range", (1, max_index))
        if not (
            isinstance(current_range, (tuple, list))
            and len(current_range) == 2
        ):
            current_range = (1, max_index)
        start_value = min(max(1, int(current_range[0])), max_index)
        end_value = min(max(start_value, int(current_range[1])), max_index)
        st.session_state.map_photo_range = (start_value, end_value)
    segment = control_cols[2].slider(
        "Photo range",
        min_value=1,
        max_value=max_index,
        key="map_photo_range",
        label_visibility="collapsed",
    )
    scope_label = "in this outing" if selected_hike else "across your library"
    control_cols[3].caption(f"{photo_count} geotagged photos • {len(unique_species)} unique species {scope_label}")

    ordered_photos = sorted(geotagged_photos, key=lambda photo: (photo.get("taken_at") or "", photo.get("created_at") or "", photo["id"]))
    start_index, end_index = segment
    segment_photos = ordered_photos[start_index - 1 : end_index]

    geotagged_points = []
    species_points = []
    route_groups: list[list[dict[str, Any]]] = []
    route_points = []
    route_points_by_hike: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sequence, photo in enumerate(segment_photos, start=start_index):
        primary_observation = primary_observation_by_photo.get(photo["id"])
        title = primary_observation.get("common_name") if primary_observation else "Trail photo"
        geotagged_points.append(
            {
                "photo_id": photo["id"],
                "hike_id": photo["hike_id"],
                "lat": photo["lat"],
                "lng": photo["lng"],
                "title": title,
                "subtitle": f"Photo {sequence} • {format_photo_meta(photo)}",
                "image_url": get_photo_thumbnail_url(photo),
            }
        )
        if selected_hike:
            route_points.append({"lat": photo["lat"], "lng": photo["lng"]})
        else:
            if photo.get("hike_id"):
                route_points_by_hike[str(photo["hike_id"])].append({"lat": photo["lat"], "lng": photo["lng"]})
        for observation in observations_by_photo.get(photo["id"], []):
            if observation.get("status") != "confirmed":
                continue
            species_name = observation.get("common_name") or observation.get("scientific_name") or "Confirmed species"
            if species_filter != "All confirmed species" and species_name != species_filter:
                continue
            role = "Primary" if observation.get("is_primary") else "Secondary"
            species_points.append(
                {
                    "photo_id": photo["id"],
                    "hike_id": photo["hike_id"],
                    "lat": photo["lat"],
                    "lng": photo["lng"],
                    "title": species_name,
                    "subtitle": f"{role} • {observation.get('scientific_name') or ''} • {format_confidence_label(observation)}",
                    "image_url": get_photo_thumbnail_url(photo),
                }
            )

    if layer_mode == "Photos":
        species_points = []
    elif layer_mode == "Species":
        geotagged_points = []

    if selected_hike:
        route_groups = imported_route_groups or ([route_points] if len(route_points) >= 2 else [])
    else:
        route_groups = list(imported_route_groups)
        for hike_id, points in route_points_by_hike.items():
            if hike_id in route_imports_by_hike:
                continue
            if len(points) >= 2:
                route_groups.append(points)

    render_rich_map(
        photos=photos,
        route_groups=route_groups,
        geotagged_points=geotagged_points,
        species_points=species_points,
        focused_photo_id=focused_photo_id,
        source_view="Map",
    )
    if focused_photo_id:
        st.caption("Centered on the photo you opened from the journal.")
        if "map_photo" in st.query_params:
            del st.query_params["map_photo"]
        if st.query_params.get("view") == "Map":
            del st.query_params["view"]
