from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any
from urllib.parse import quote, urlencode

import streamlit as st


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
    cover_photo_url: str | None = None,
    login_mode: bool = False,
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

    hero_class = "hero-shell hero-shell--photo" if cover_photo_url else "hero-shell"
    if login_mode:
        hero_class += " hero-shell--login"
    photo_markup = (
        f'<img class="hero-media" src="{escape(cover_photo_url, quote=True)}" alt="" decoding="async">'
        if cover_photo_url
        else ""
    )
    st.html(
        f"""
        <section class="{hero_class}">
            {photo_markup}
            <div class="hero-scrim"></div>
            <div class="hero-content">
                <div class="hero-kicker">Field Journal · Florida</div>
                <h1 class="hero-brand">{escape(str(title))}</h1>
                <p class="hero-subcopy">{escape(str(supporting))}</p>
                <div class="metric-line">
                    {''.join(f"<span>{escape(item)}</span>" for item in metric_items if item)}
                </div>
                <p class="hero-subcopy hero-summary">{escape(str(summary))}</p>
            </div>
        </section>
        """
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
