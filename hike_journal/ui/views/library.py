from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import quote

import streamlit as st

from hike_journal.domain.library import (
    build_standalone_library_item,
    count_records_by_key,
    count_unique_species,
    count_unique_species_by_key,
    filter_hike_library,
    group_hikes_for_library,
    record_visible_for_user,
)
from hike_journal.domain.locations import format_hike_location_label
from hike_journal.domain.routes import compute_total_mileage, format_total_miles
from hike_journal.queries import fetch_standalone_photos
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.storage import StorageService
from hike_journal.ui.components import render_clickable_photo, render_library_cover


def render_library_view(
    repository: HikeJournalRepository,
    storage: StorageService,
    hikes: list[dict[str, Any]],
    photo_refs: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    cover_photos_by_id: dict[str, dict[str, Any]],
    user_context: dict[str, Any],
    *,
    navigate_to: Any,
    paginate_items: Any,
    render_back_to_top_link: Any,
    render_create_hike_dialog: Any,
    render_edit_hike_dialog: Any,
    render_quick_upload_dialog: Any,
    reset_library_page: Any,
) -> None:
    st.markdown("<div id='library-top'></div>", unsafe_allow_html=True)
    if st.session_state.location_library_notice:
        st.success(str(st.session_state.location_library_notice))
        st.session_state.location_library_notice = None
    total_photo_count = len(photo_refs)
    total_confirmed_count = count_unique_species(confirmed_observations)
    total_outing_count = len(hikes)
    total_logged_miles = compute_total_mileage(hikes)
    featured_hike = next(
        (
            hike
            for hike in sorted(hikes, key=lambda item: str(item.get("hike_date") or ""), reverse=True)
            if hike.get("cover_photo_id") and str(hike.get("cover_photo_id")) in cover_photos_by_id
        ),
        None,
    )
    featured_photo = cover_photos_by_id.get(str(featured_hike.get("cover_photo_id"))) if featured_hike else None
    featured_image = (
        f'<img class="library-hero-media" src="{escape(str(featured_photo.get("public_url")), quote=True)}" alt="" decoding="async">'
        if featured_photo and featured_photo.get("public_url")
        else ""
    )
    featured_action = (
        f'<a class="library-hero-action" href="?view=Journal&amp;hike={quote(str(featured_hike["id"]))}" target="_self">Continue {escape(str(featured_hike.get("title") or "latest outing"))}</a>'
        if featured_hike
        else ""
    )
    standalone_photos = [
        photo for photo in fetch_standalone_photos()
        if record_visible_for_user(photo, {hike["id"] for hike in hikes}, user_context)
    ]
    st.markdown(
        f"""
        <section class="library-hero{' library-hero--photo' if featured_image else ''}">
            {featured_image}
            <div class="library-hero-scrim"></div>
            <div class="library-hero-copy">
                <p class="library-hero-label">Field journal · Florida</p>
                <h1 class="library-hero-title">HikeJournal</h1>
                <p class="library-hero-body">Outings, photographs, maps, and species observations in one living field record.</p>
                {featured_action}
            </div>
        </section>
        <div class="library-index-line">
            <span>{total_outing_count} outings</span>
            <span>{format_total_miles(total_logged_miles)}</span>
            <span>{total_photo_count} photographs</span>
            <span>{total_confirmed_count} species</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    with st.container(key="library_filters"):
        controls = st.columns([0.44, 0.24, 0.16, 0.16], gap="small")
        query = controls[0].text_input(
            "Search hikes",
            placeholder="Bronson, Black Bear, scrub, loop...",
            label_visibility="collapsed",
            key="library_query",
            on_change=reset_library_page,
        )
        archive_mode = controls[1].segmented_control(
            "Browse",
            ["Everything", "Current outings", "Archived outings", "Everyday"],
            default="Current outings",
            key="library_archive_mode",
            label_visibility="collapsed",
            on_change=reset_library_page,
        )
        sort_order = controls[2].selectbox("Sort", ["Newest first", "Oldest first", "Title"], label_visibility="collapsed", key="library_sort", on_change=reset_library_page)
        group_by = controls[3].selectbox("Group", ["Month", "Year", "None"], label_visibility="collapsed", key="library_group_by", on_change=reset_library_page)
    with st.container(key="library_action_rail"):
        action_rail = st.columns([0.62, 0.18, 0.2], gap="small")
        action_rail[0].markdown(
            "<div class='library-rail-note'>Browse current outings, archived outings, or everyday sightings without losing the shape of the archive.</div>",
            unsafe_allow_html=True,
        )
        if action_rail[1].button("Quick upload", use_container_width=True, type="secondary", key="library_quick_upload"):
            render_quick_upload_dialog(storage, repository, user_context)
        if action_rail[2].button("New hike", use_container_width=True, type="primary"):
            render_create_hike_dialog(repository, storage, user_context)

    photo_counts = count_records_by_key(photo_refs, "hike_id")
    confirmed_counts = count_unique_species_by_key(confirmed_observations, "hike_id")
    hike_scope = {
        "Everything": "All",
        "Current outings": "Active",
        "Archived outings": "Archived",
        "Everyday": "All",
    }.get(archive_mode, "Active")
    library_items = list(filter_hike_library(hikes, query=query, scope=hike_scope, sort_order=sort_order))
    standalone_item = build_standalone_library_item(
        photos=standalone_photos,
        confirmed_observations=confirmed_observations,
        query=query,
        scope="All" if archive_mode in {"Everything", "Everyday"} else "Active",
    )
    show_hikes = archive_mode in {"Everything", "Current outings", "Archived outings"}
    show_standalone = archive_mode in {"Everything", "Everyday"}

    if not library_items and not (show_standalone and standalone_item):
        st.info("Nothing matched this library view yet.")
        return
    if show_standalone and not show_hikes and not standalone_item:
        st.info("No standalone sightings matched that search yet.")
        return

    if show_standalone and standalone_item:
        st.markdown("<div class='library-section-label'>Everyday sightings</div>", unsafe_allow_html=True)
        with st.container(key="library_card_standalone"):
            st.markdown("<div class='library-row-shell library-row-shell--standalone'>", unsafe_allow_html=True)
            standalone_row = st.columns([0.22, 0.5, 0.28], gap="large")
            cover_photo = standalone_item.get("_cover_photo")
            with standalone_row[0]:
                if cover_photo:
                    render_clickable_photo(cover_photo, selected_hike_id=None, variant="library-cover", scope="standalone")
                else:
                    st.markdown(
                        """
                        <a class="library-cover-placeholder" href="?view=Journal&scope=standalone" target="_self">
                            <div class="library-cover-mark">S</div>
                            <div class="library-cover-copy">Open your standalone photo journal</div>
                        </a>
                        """,
                        unsafe_allow_html=True,
                    )
            with standalone_row[1]:
                standalone_notes = (standalone_item.get("notes") or "").strip()
                if len(standalone_notes) > 180:
                    standalone_notes = standalone_notes[:177].rstrip() + "..."
                st.markdown(
                    f"""
                    <div class="library-row-copy">
                        <div class="library-row-kicker">Always available</div>
                        <p class="library-row-title">{escape(standalone_item.get("title") or "Everyday sightings")}</p>
                        <p class="library-row-subtitle">{escape(standalone_item.get("location_name") or "Neighborhood finds, one-off sightings, and quick uploads that were never part of a formal outing.")}</p>
                        <div class="library-row-stats">
                            <span>Standalone archive</span>
                            <span>{standalone_item.get('_photo_count', 0)} photos</span>
                            <span>{standalone_item.get('_confirmed_count', 0)} unique species</span>
                        </div>
                        {f"<p class='library-row-notes'>{escape(standalone_notes)}</p>" if standalone_notes else ""}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with standalone_row[2]:
                st.markdown(
                    f"""
                    <div class="library-action-intro">
                        <span class="library-action-count">{standalone_item.get('_photo_count', 0)} photos</span>
                        <span class="library-action-separator">•</span>
                        <span>{standalone_item.get('_confirmed_count', 0)} unique species</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Open photos", key=f"library_open_{standalone_item['id']}", use_container_width=True):
                    navigate_to(view="Journal", scope="standalone")
                utility_markup = (
                    "<a class='library-inline-action' href='?view=Map&scope=global' target='_self'>Master map</a>"
                    "<a class='library-inline-action' href='?view=Species%20Log' target='_self'>Sightings log</a>"
                )
                st.markdown(f"<div class='library-row-utility'>{utility_markup}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        if show_hikes and library_items:
            st.divider()

    page_hikes: list[dict[str, Any]] = []
    total_pages = 1
    if show_hikes and library_items:
        outings_label = {
            "Current outings": "Current outings",
            "Archived outings": "Archived outings",
        }.get(archive_mode, "Outings")
        st.markdown(f"<div class='library-section-label'>{escape(outings_label)}</div>", unsafe_allow_html=True)
        page_hikes, total_pages = paginate_items(library_items, "library_page", "library_page_size")
        with st.container(key="library_toolbar"):
            library_toolbar = st.columns([0.16, 0.14, 0.44, 0.26], gap="small")
            page_size_options = [6, 8, 12, 18, 0]
            page_size = library_toolbar[0].selectbox(
                "Per page",
                page_size_options,
                index=page_size_options.index(st.session_state.library_page_size),
                key="library_page_size_select",
                format_func=lambda value: "All" if value == 0 else str(value),
            )
            if page_size != st.session_state.library_page_size:
                st.session_state.library_page_size = page_size
                st.session_state.library_page = 1
                st.rerun()
            requested_page = library_toolbar[1].number_input(
                "Page",
                min_value=1,
                max_value=total_pages,
                value=st.session_state.library_page,
                step=1,
                key="library_page_number",
            )
            if requested_page != st.session_state.library_page:
                st.session_state.library_page = int(requested_page)
                st.rerun()
            library_toolbar[2].markdown(
                f"<div class='utility-rail-status'>{len(page_hikes)} outings on this page • {len(library_items)} matched overall</div>",
                unsafe_allow_html=True,
            )
            with library_toolbar[3].popover("Manage"):
                st.caption(f"Page {st.session_state.library_page} of {total_pages}")
                nav_cols = st.columns(2, gap="small")
                if nav_cols[0].button("Previous", key="library_prev_page", use_container_width=True, disabled=st.session_state.library_page <= 1):
                    st.session_state.library_page -= 1
                    st.rerun()
                if nav_cols[1].button("Next", key="library_next_page", use_container_width=True, disabled=st.session_state.library_page >= total_pages):
                    st.session_state.library_page += 1
                    st.rerun()

    if show_hikes and not library_items and show_standalone and standalone_item:
        return
    if show_hikes and not library_items:
        st.info("No outings matched that search.")
        return

    grouped_hikes = group_hikes_for_library(page_hikes, group_by) if page_hikes else []
    rendered_index = 0
    total_hikes = len(page_hikes)
    for group_label, group_items in grouped_hikes:
        if group_label:
            st.markdown(f"<div class='library-group-label'>{escape(group_label)}</div>", unsafe_allow_html=True)
        for hike in group_items:
            cover_photo = cover_photos_by_id.get(str(hike.get("cover_photo_id")))
            title = hike.get("title") or "Untitled hike"
            location_name = format_hike_location_label(hike)
            distance_label = f"{float(hike.get('distance_miles') or 0):.1f} mi" if hike.get("distance_miles") is not None else "Distance n/a"
            photo_count = hike.get('_photo_count', photo_counts.get(hike['id'], 0))
            confirmed_count = hike.get('_confirmed_count', confirmed_counts.get(hike['id'], 0))
            archived_markup = "<span class='library-row-status'>Archived</span>" if hike.get("is_archived") else ""
            notes = (hike.get("notes") or "").strip()
            if len(notes) > 180:
                notes = notes[:177].rstrip() + "..."
            with st.container(key=f"library_card_{hike['id']}"):
                st.markdown("<div class='library-row-shell'>", unsafe_allow_html=True)
                row = st.columns([0.22, 0.5, 0.28], gap="large")
                with row[0]:
                    render_library_cover(cover_photo, hike_id=hike["id"], title=title)
                with row[1]:
                    st.markdown(
                        f"""
                        <div class="library-row-copy">
                            <div class="library-row-kicker">{escape(str(hike.get('hike_date') or 'Undated outing'))}{archived_markup}</div>
                            <p class="library-row-title">{escape(title)}</p>
                            <p class="library-row-subtitle">{escape(location_name)}</p>
                            <div class="library-row-stats">
                                <span>{distance_label}</span>
                                <span>{photo_count} photos</span>
                                <span>{confirmed_count} unique species</span>
                            </div>
                            {f"<p class='library-row-notes'>{escape(notes)}</p>" if notes else ""}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with row[2]:
                    st.markdown(
                        f"""
                        <div class="library-action-intro">
                            <span class="library-action-count">{photo_count} photos</span>
                            <span class="library-action-separator">•</span>
                            <span>{confirmed_count} unique species</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    top_action_cols = st.columns(2, gap="small")
                    if top_action_cols[0].button("Open", key=f"library_open_{hike['id']}", use_container_width=True):
                        navigate_to(view="Journal", hike_id=hike["id"])
                    if top_action_cols[1].button("Manage", key=f"library_manage_{hike['id']}", use_container_width=True, type="primary"):
                        render_edit_hike_dialog(repository, storage, hike)
                    bottom_action_cols = st.columns(2, gap="small")
                    if bottom_action_cols[0].button("Map", key=f"library_map_{hike['id']}", use_container_width=True, type="secondary"):
                        navigate_to(view="Map", hike_id=hike["id"])
                    if bottom_action_cols[1].button("Sightings", key=f"library_sightings_{hike['id']}", use_container_width=True, type="secondary"):
                        st.session_state.species_log_hike_filter = title
                        navigate_to(view="Species Log")
                st.markdown("</div>", unsafe_allow_html=True)
            rendered_index += 1
            if rendered_index < total_hikes:
                st.divider()
    if show_hikes and st.session_state.library_page_size == 0 and page_hikes:
        render_back_to_top_link("library-top")
