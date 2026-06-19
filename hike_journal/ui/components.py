from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any
from urllib.parse import quote, urlencode

import folium
import streamlit as st
from folium.plugins import Fullscreen, MarkerCluster, MiniMap
import streamlit.components.v1 as components


def get_photo_derivatives(photo: dict[str, Any]) -> dict[str, Any]:
    exif_json = photo.get("exif_json") or {}
    if not isinstance(exif_json, dict):
        return {}
    derivatives = exif_json.get("derivatives") or {}
    return derivatives if isinstance(derivatives, dict) else {}


def get_photo_thumbnail_url(photo: dict[str, Any]) -> str:
    return str(photo["public_url"])


def render_hero(
    selected_hike: dict[str, Any] | None,
    hike_count: int,
    photo_count: int,
    species_count: int,
    *,
    route_import: dict[str, Any] | None = None,
    total_miles: float | None = None,
) -> None:
    if selected_hike:
        title = selected_hike["title"]
        date_label = selected_hike.get("hike_date", "")
        distance = selected_hike.get("distance_miles")
        location = selected_hike.get("location_name") or "Private field log"
        route_meta = {}
        if route_import:
            track_geojson = route_import.get("track_geojson") or {}
            if isinstance(track_geojson, dict):
                route_meta = track_geojson.get("meta") or {}
        supporting_bits = [location, str(date_label)]
        if distance is not None:
            supporting_bits.append(f"{float(distance):.1f} miles")
        duration_seconds = route_import.get("duration_seconds") if route_import else None
        if duration_seconds:
            total_seconds = int(duration_seconds)
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            supporting_bits.append(f"{hours}h {minutes}m" if hours else f"{minutes}m")
        elevation_gain = route_meta.get("elevation_gain_feet") if isinstance(route_meta, dict) else None
        if elevation_gain:
            supporting_bits.append(f"{int(elevation_gain):,} ft gain")
        supporting = " • ".join(bit for bit in supporting_bits if bit)
        summary = selected_hike.get("notes") or "A quiet record of what was blooming, moving, and worth remembering on this specific outing."
        metric_items = [
            f"{distance:.1f} mi" if distance is not None else "Distance n/a",
            f"{photo_count} photos in view",
            f"{species_count} unique species",
            (f"{total_miles:.0f} mi total archive" if total_miles is not None else f"{hike_count} hikes logged"),
        ]
    else:
        title = "HikeJournal"
        supporting = "A private trail journal for hikes, photos, notes, and species sightings."
        summary = "Start a new outing, add the moments you want to keep, and revisit the whole record from your library."
        total_miles_label = f"{total_miles:,.0f} mi logged" if total_miles else "0 mi logged"
        metric_items = [
            f"{hike_count} hikes logged",
            total_miles_label,
            f"{photo_count} photos in view",
            f"{species_count} unique species",
        ]

    st.markdown(
        f"""
        <section class="hero-shell">
            <div class="hero-kicker">Field Journal • Florida Ready</div>
            <h1 class="hero-brand">{title}</h1>
            <p class="hero-subcopy">{supporting}</p>
            <div class="metric-line">
                {''.join(f"<span>{escape(item)}</span>" for item in metric_items if item)}
            </div>
            <p class="hero-subcopy">{summary}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def section_heading(label: str, title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="section-shell">
            <p class="section-label">{label}</p>
            <h2 style="margin:0;">{title}</h2>
            <p style="margin:0.55rem 0 0; color: rgba(31,42,38,0.74); line-height:1.7;">{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_observation_badge(status: str) -> None:
    st.markdown(f'<span class="status-pill {status}">{status}</span>', unsafe_allow_html=True)


def format_photo_meta(photo: dict[str, Any]) -> str:
    pieces: list[str] = []
    taken_at = photo.get("taken_at")
    if taken_at:
        try:
            parsed = datetime.fromisoformat(str(taken_at).replace("Z", "+00:00"))
            pieces.append(parsed.strftime("%b %d, %Y • %I:%M %p"))
        except ValueError:
            pieces.append(str(taken_at))
    if photo.get("lat") is not None and photo.get("lng") is not None:
        pieces.append(f"{photo['lat']:.5f}, {photo['lng']:.5f}")
    if photo.get("route_context_label"):
        pieces.append(str(photo["route_context_label"]))
    pieces.append(f"{photo.get('width', '?')}×{photo.get('height', '?')}")
    return " • ".join(pieces)


def format_photo_meta_html(
    photo: dict[str, Any],
    *,
    selected_hike_id: str | None = None,
    link_coordinates: bool = False,
    include_map_link: bool = False,
) -> str:
    pieces: list[str] = []
    taken_at = photo.get("taken_at")
    if taken_at:
        try:
            parsed = datetime.fromisoformat(str(taken_at).replace("Z", "+00:00"))
            pieces.append(escape(parsed.strftime("%b %d, %Y • %I:%M %p")))
        except ValueError:
            pieces.append(escape(str(taken_at)))
    if photo.get("lat") is not None and photo.get("lng") is not None:
        coords_label = f"{photo['lat']:.5f}, {photo['lng']:.5f}"
        href = None
        if link_coordinates:
            if selected_hike_id:
                href = f"?hike={quote(selected_hike_id)}&view=Map&map_photo={quote(photo['id'])}"
            else:
                href = f"?view=Map&scope=global&map_photo={quote(photo['id'])}"
        if href:
            pieces.append(f'<a class="photo-meta-link" href="{href}" target="_self">{escape(coords_label)}</a>')
            if include_map_link:
                pieces.append(f'<a class="photo-meta-link" href="{href}" target="_self">Open on map</a>')
        else:
            pieces.append(escape(coords_label))
    if photo.get("route_context_label"):
        pieces.append(escape(str(photo["route_context_label"])))
    pieces.append(escape(f"{photo.get('width', '?')}×{photo.get('height', '?')}"))
    return " • ".join(pieces)


def _pagination_query_for_view(source_view: str) -> dict[str, str]:
    query: dict[str, str] = {}
    if source_view == "Journal":
        query["journal_page"] = str(int(st.session_state.get("journal_page", 1)))
        query["journal_page_size"] = str(int(st.session_state.get("journal_page_size", 9)))
    elif source_view == "Species Review":
        query["species_page"] = str(int(st.session_state.get("species_page", 1)))
        query["species_page_size"] = str(int(st.session_state.get("species_page_size", 6)))
        query["species_review_mode"] = str(st.session_state.get("species_review_mode", "Review"))
        query["species_review_stage"] = str(st.session_state.get("species_review_stage", "All"))
    elif source_view == "Map":
        query["map_layer_mode"] = str(st.session_state.get("map_layer_mode", "Both"))
        query["map_species_filter"] = str(st.session_state.get("map_species_filter", "All confirmed species"))
        map_range = st.session_state.get("map_photo_range")
        if isinstance(map_range, (list, tuple)) and len(map_range) == 2:
            query["map_photo_range_start"] = str(int(map_range[0]))
            query["map_photo_range_end"] = str(int(map_range[1]))
    elif source_view == "Species Log":
        query["species_log_query"] = str(st.session_state.get("species_log_query", "")).strip()
        query["species_log_page"] = str(int(st.session_state.get("species_log_page", 1)))
        query["species_log_page_size"] = str(int(st.session_state.get("species_log_page_size", 8)))
        query["species_log_hike_filter"] = str(st.session_state.get("species_log_hike_filter", "All hikes"))
        query["species_log_sort"] = str(st.session_state.get("species_log_sort", "Most recent"))
        query["species_log_posted_filter"] = str(st.session_state.get("species_log_posted_filter", "All"))
        query["species_log_mapped_only"] = "1" if st.session_state.get("species_log_mapped_only") else "0"
        query["species_log_include_secondary"] = "1" if st.session_state.get("species_log_include_secondary", True) else "0"
        if st.session_state.get("species_log_focus_key"):
            query["species_log_focus_key"] = str(st.session_state.get("species_log_focus_key"))
        query["species_log_record_open"] = "1" if st.session_state.get("species_log_record_open") else "0"
    return query


def _build_internal_href(
    *,
    source_view: str,
    hike_id: str | None = None,
    photo_id: str | None = None,
    map_photo_id: str | None = None,
    scope: str | None = None,
) -> str:
    query: dict[str, str] = {"view": source_view}
    if hike_id:
        query["hike"] = str(hike_id)
    if scope:
        query["scope"] = str(scope)
    if photo_id:
        query["photo"] = str(photo_id)
    if map_photo_id:
        query["map_photo"] = str(map_photo_id)
    query.update(_pagination_query_for_view(source_view))
    return f"?{urlencode(query, quote_via=quote)}"


def render_clickable_photo(
    photo: dict[str, Any],
    *,
    selected_hike_id: str | None,
    variant: str = "default",
    scope: str | None = None,
) -> None:
    href = _build_internal_href(
        source_view="Journal",
        hike_id=selected_hike_id,
        photo_id=photo["id"],
        scope=scope,
    )
    alt = escape(photo.get('caption') or photo.get('id') or 'Trail photo')
    src = escape(get_photo_thumbnail_url(photo))
    st.markdown(
        f"""
        <a class="photo-link photo-link--{escape(variant)}" href="{href}" target="_self">
            <img src="{src}" alt="{alt}" loading="lazy" decoding="async">
        </a>
        """,
        unsafe_allow_html=True,
    )


def render_clickable_photo_with_view(
    photo: dict[str, Any],
    *,
    selected_hike_id: str | None,
    source_view: str,
    variant: str = "default",
    scope: str | None = None,
) -> None:
    hike_id = selected_hike_id
    if source_view in {"Species Review", "Species Log"}:
        hike_id = None
    href = _build_internal_href(
        source_view=source_view,
        hike_id=hike_id,
        photo_id=photo["id"],
        scope=scope,
    )
    alt = escape(photo.get('caption') or photo.get('id') or 'Trail photo')
    src = escape(get_photo_thumbnail_url(photo))
    st.markdown(
        f"""
        <a class="photo-link photo-link--{escape(variant)}" href="{href}" target="_self">
            <img src="{src}" alt="{alt}" loading="lazy" decoding="async">
        </a>
        """,
        unsafe_allow_html=True,
    )


def render_library_cover(photo: dict[str, Any] | None, *, hike_id: str, title: str) -> None:
    journal_href = _build_internal_href(source_view="Journal", hike_id=hike_id)
    if photo and photo.get("public_url"):
        alt = escape(title or "Hike cover photo")
        src = escape(get_photo_thumbnail_url(photo))
        st.markdown(
            f"""
            <a class="photo-link photo-link--library-cover" href="{journal_href}" target="_self">
                <img src="{src}" alt="{alt}" loading="lazy" decoding="async">
            </a>
            """,
            unsafe_allow_html=True,
        )
        return

    initial = escape((title or "H")[:1].upper())
    st.markdown(
        f"""
        <a class="library-cover-placeholder" href="{journal_href}" target="_self">
            <div class="library-cover-mark">{initial}</div>
            <div class="library-cover-copy">Set a cover photo from the journal</div>
        </a>
        """,
        unsafe_allow_html=True,
    )


def render_rich_map(
    *,
    photos: list[dict[str, Any]],
    route_groups: list[list[dict[str, Any]]],
    geotagged_points: list[dict[str, Any]],
    species_points: list[dict[str, Any]],
    focused_photo_id: str | None = None,
    source_view: str = "Map",
) -> None:
    flattened_route_points = [point for group in route_groups for point in group]
    if not geotagged_points and not species_points and not flattened_route_points:
        st.info("No geotagged photos are available for this hike yet.")
        return

    all_points = geotagged_points + species_points
    focused_point = next((point for point in all_points if point.get("photo_id") == focused_photo_id), None)
    center_source = all_points or flattened_route_points
    center_lat = focused_point["lat"] if focused_point else sum(point["lat"] for point in center_source) / len(center_source)
    center_lng = focused_point["lng"] if focused_point else sum(point["lng"] for point in center_source) / len(center_source)

    fmap = folium.Map(location=[center_lat, center_lng], zoom_start=12, tiles=None, control_scale=True)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri",
        name="Satellite",
        overlay=False,
        control=True,
        show=True,
    ).add_to(fmap)
    folium.TileLayer(
        tiles="https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri",
        name="Topo",
        overlay=False,
        control=True,
        show=False,
    ).add_to(fmap)
    folium.TileLayer(
        tiles="CartoDB Positron",
        name="Light",
        overlay=False,
        control=True,
        show=False,
    ).add_to(fmap)
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="Street",
        overlay=False,
        control=True,
        show=False,
    ).add_to(fmap)

    Fullscreen(position="topright", title="Full screen", title_cancel="Exit full screen").add_to(fmap)
    MiniMap(toggle_display=True, position="bottomright").add_to(fmap)

    bounds: list[tuple[float, float]] = []
    for route_points in route_groups:
        if len(route_points) < 2:
            continue
        # Soft outer trace keeps the hike legible on satellite imagery.
        folium.PolyLine(
            [(point["lat"], point["lng"]) for point in route_points],
            color="#F6F0E4",
            weight=8,
            opacity=0.64,
        ).add_to(fmap)
        folium.PolyLine(
            [(point["lat"], point["lng"]) for point in route_points],
            color="#30473A",
            weight=4.5,
            opacity=0.94,
            tooltip="Hike path",
        ).add_to(fmap)
        bounds.extend((point["lat"], point["lng"]) for point in route_points)

    marker_cluster = MarkerCluster(name="Photo cluster").add_to(fmap)
    species_layer = folium.FeatureGroup(name="Confirmed species", show=True).add_to(fmap)
    for point in geotagged_points:
        popup_html = _popup_html(point, source_view)
        is_focused = point.get("photo_id") == focused_photo_id
        folium.CircleMarker(
            [point["lat"], point["lng"]],
            popup=folium.Popup(popup_html, max_width=360, show=is_focused),
            tooltip=point["title"],
            radius=8 if is_focused else 5,
            color="#30473A" if is_focused else "#F6F0E4",
            weight=3 if is_focused else 1.5,
            fill=True,
            fill_color="#F3EBDD" if is_focused else "#89B8C7",
            fill_opacity=0.88,
        ).add_to(marker_cluster)
        bounds.append((point["lat"], point["lng"]))

    for point in species_points:
        popup_html = _popup_html(point, source_view)
        is_focused = point.get("photo_id") == focused_photo_id
        folium.CircleMarker(
            [point["lat"], point["lng"]],
            radius=10 if is_focused else 8,
            color="#F6F0E4",
            weight=3 if is_focused else 2,
            fill=True,
            fill_color="#B88C5A" if is_focused else "#30473A",
            fill_opacity=0.92,
            popup=folium.Popup(popup_html, max_width=360, show=is_focused),
            tooltip=point["title"],
        ).add_to(species_layer)
        bounds.append((point["lat"], point["lng"]))

    if bounds:
        fmap.fit_bounds(bounds, padding=(24, 24))

    folium.LayerControl(collapsed=False).add_to(fmap)
    components.html(fmap._repr_html_(), height=620, scrolling=False)


def _popup_html(point: dict[str, Any], source_view: str) -> str:
    hike_id = point.get("hike_id")
    href = _build_internal_href(
        source_view=source_view,
        hike_id=str(hike_id) if hike_id else None,
        photo_id=point["photo_id"],
    )
    title = escape(point.get("title") or "Trail photo")
    subtitle = escape(point.get("subtitle") or "")
    image_url = escape(point.get("image_url") or "")
    image_block = f'<img src="{image_url}" style="display:block;width:100%;max-width:300px;height:180px;object-fit:cover;border-radius:14px;margin-bottom:10px;">' if image_url else ""
    return (
        f"<div style='width:300px;font-family:Manrope,sans-serif;'>"
        f"{image_block}"
        f"<div style='font-weight:800;font-size:15px;color:#1F2A26;margin-bottom:6px;'>{title}</div>"
        f"<div style='font-size:13px;line-height:1.45;color:#47534d;margin-bottom:10px;'>{subtitle}</div>"
        f"<div style='display:flex;gap:10px;flex-wrap:wrap;'>"
        f"<a href='{href}' target='_self' style='display:inline-flex;align-items:center;gap:6px;font-weight:800;color:#30473A;text-decoration:none;'>Open viewer</a>"
        f"<a href='{image_url}' target='_blank' rel='noopener noreferrer' style='display:inline-flex;align-items:center;gap:6px;font-weight:800;color:#30473A;text-decoration:none;'>Full image</a>"
        f"</div>"
        f"</div>"
    )
