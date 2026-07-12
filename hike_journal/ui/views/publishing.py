from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
import math
from typing import Any

import streamlit as st

from hike_journal.domain.library import format_species_log_date_label
from hike_journal.publishing_state import (
    build_publish_rows,
    count_publish_states,
    filter_publish_rows,
    reset_publish_page,
    set_publish_rows_selected,
    synchronize_publish_selection,
)
from hike_journal.services.inat import InatClient
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.ui.components import format_photo_meta_html, render_clickable_photo_with_view


@dataclass(frozen=True)
class PublishingActions:
    get_inat_posting: Any
    inat_connection_action_label: Any
    invalidate_data_cache: Any
    is_inat_client_ready: Any
    open_inat_token_dialog: Any
    open_publish_plan: Any
    paginate_items: Any
    render_inat_posting_controls: Any
    render_publish_lane_management_controls: Any
    resolve_page_size: Any


def render_publish_state_chip(state: str) -> str:
    slug = state.lower().replace(" ", "-")
    return f"<span class='status-pill publish-{slug}'>{escape(state)}</span>"


def render_publishing_view(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    hikes: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    photos: list[dict[str, Any]],
    *,
    quick_upload_hike_filter: str,
    actions: PublishingActions,
) -> None:
    if not confirmed_observations:
        st.info("Confirmed species will show up here once you start reviewing photos.")
        return
    if st.session_state.publish_batch_notice:
        notice = st.session_state.publish_batch_notice
        if notice.get("level") == "warning":
            st.warning(str(notice.get("message") or "Some iNaturalist posts need attention."))
        else:
            st.success(str(notice.get("message") or "Finished posting to iNaturalist."))
        st.session_state.publish_batch_notice = None

    rows = build_publish_rows(
        hikes,
        confirmed_observations,
        photos,
        posting_resolver=actions.get_inat_posting,
    )
    counts = count_publish_states(rows)
    publish_filter_labels = {
        "Ready to post": f"Ready · {counts['Ready to post']}",
        "Needs attention": f"Needs attention · {counts['Needs attention']}",
        "Posted": f"Posted · {counts['Posted']}",
        "All": f"All · {len(rows)}",
    }
    st.markdown(
        """
        <div class="publish-filter-strip">
            <div class="publish-filter-copy">
                <p class="workspace-lane-label">Publishing state</p>
                <p class="publish-filter-caption">Move between what is ready to send, what needs another look, and what has already gone out.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    selected_filter_label = st.segmented_control(
        "Publishing filter",
        list(publish_filter_labels.values()),
        default=publish_filter_labels.get(st.session_state.publish_filter, publish_filter_labels["Ready to post"]),
        key="publish_filter_switch",
        label_visibility="collapsed",
    )
    publish_filter = next(
        (key for key, value in publish_filter_labels.items() if value == selected_filter_label),
        st.session_state.publish_filter if st.session_state.publish_filter in publish_filter_labels else "Ready to post",
    )
    if publish_filter != st.session_state.publish_filter:
        st.session_state.publish_filter = publish_filter
        reset_publish_page(st.session_state)
        st.rerun()

    hike_options = ["All hikes", quick_upload_hike_filter, *[hike.get("title") or "Untitled hike" for hike in hikes]]
    if st.session_state.publish_hike_filter not in hike_options:
        st.session_state.publish_hike_filter = "All hikes"

    def _reset_page() -> None:
        reset_publish_page(st.session_state)

    publish_filters = st.columns([0.68, 0.32], gap="small")
    publish_query = publish_filters[0].text_input(
        "Search publishing queue",
        placeholder="Alligator, oak, mushroom...",
        key="publish_query",
        label_visibility="collapsed",
        on_change=_reset_page,
    )
    publish_hike_filter = publish_filters[1].selectbox(
        "Hike filter",
        hike_options,
        key="publish_hike_filter",
        label_visibility="collapsed",
        on_change=_reset_page,
    )
    filtered_rows = filter_publish_rows(
        rows,
        hikes,
        publish_filter=publish_filter,
        hike_filter=publish_hike_filter,
        query=publish_query,
        quick_upload_filter=quick_upload_hike_filter,
    )
    synchronize_publish_selection(st.session_state, filtered_rows)

    st.markdown(
        f"""
        <div class="publish-queue-summary">
            <span>{len(filtered_rows)} in this queue</span>
            <span>{counts['Ready to post']} ready</span>
            <span>{counts['Needs attention']} need attention</span>
            <span>{counts['Posted']} posted</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Refresh publishing queue", key="publish_refresh_queue", type="secondary"):
        actions.invalidate_data_cache()
        st.rerun()

    cols = st.columns([0.16, 0.14, 0.42, 0.1, 0.18], gap="small")
    page_size_options = [6, 8, 12, 18, 0]
    page_size = cols[0].selectbox(
        "Per page",
        page_size_options,
        index=page_size_options.index(st.session_state.publish_page_size),
        key="publish_page_size_select",
        format_func=lambda value: "All" if value == 0 else str(value),
    )
    if page_size != st.session_state.publish_page_size:
        st.session_state.publish_page_size = page_size
        reset_publish_page(st.session_state)
        st.rerun()
    total_pages = max(
        1,
        math.ceil(
            max(1, len(filtered_rows))
            / actions.resolve_page_size(len(filtered_rows), st.session_state.publish_page_size)
        ),
    )
    requested_page = cols[1].number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        value=min(st.session_state.publish_page, total_pages),
        step=1,
        key="publish_page_number",
    )
    if requested_page != st.session_state.publish_page:
        st.session_state.publish_page = int(requested_page)
        st.rerun()
    selected_ids = set(st.session_state.publish_selected_ids)
    selected_rows = [row for row in filtered_rows if row["observation"]["id"] in selected_ids]
    cols[2].markdown(
        f"<div class='utility-rail-status'>{len(selected_rows)} selected • {len([row for row in filtered_rows if row['publish_state'] == 'Ready to post'])} ready</div>",
        unsafe_allow_html=True,
    )
    cols[3].markdown(
        f"<div class='utility-rail-status review-page-status'>{publish_filter}</div>",
        unsafe_allow_html=True,
    )
    page_rows, total_pages = actions.paginate_items(filtered_rows, "publish_page", "publish_page_size")
    with cols[4].popover("Manage"):
        st.caption(f"Page {st.session_state.publish_page} of {total_pages}")
        nav_cols = st.columns(2, gap="small")
        if nav_cols[0].button("Previous", key="publish_prev_page", use_container_width=True, disabled=st.session_state.publish_page <= 1):
            st.session_state.publish_page -= 1
            st.rerun()
        if nav_cols[1].button("Next", key="publish_next_page", use_container_width=True, disabled=st.session_state.publish_page >= total_pages):
            st.session_state.publish_page += 1
            st.rerun()
        st.divider()
        select_cols = st.columns(2, gap="small")
        if select_cols[0].button("Select page", key="publish_select_page", use_container_width=True):
            set_publish_rows_selected(st.session_state, page_rows, True)
            st.rerun()
        if select_cols[1].button("Clear page", key="publish_clear_page", use_container_width=True):
            set_publish_rows_selected(st.session_state, page_rows, False)
            st.rerun()

    if not filtered_rows:
        st.info("Nothing matches this publishing filter right now.")
        return

    selected_ready_rows = [row for row in selected_rows if row["publish_state"] == "Ready to post"]
    action_cols = st.columns([0.3, 0.26, 0.18, 0.12, 0.14], gap="small")
    if action_cols[0].button(
        f"Post selected ({len(selected_ready_rows)})",
        key="publish_post_selected",
        use_container_width=True,
        disabled=not actions.is_inat_client_ready(inat_client) or not selected_ready_rows,
    ):
        actions.open_publish_plan(repository, inat_client, selected_ready_rows)
    if actions.is_inat_client_ready(inat_client):
        action_cols[1].button(
            "Select ready to post",
            key="publish_select_ready",
            use_container_width=True,
            type="secondary",
            on_click=set_publish_rows_selected,
            args=(st.session_state, [row for row in filtered_rows if row["publish_state"] == "Ready to post"], True),
        )
    elif action_cols[1].button(
        actions.inat_connection_action_label(inat_client),
        key="publish_connect_inat",
        use_container_width=True,
        type="secondary",
    ):
        actions.open_inat_token_dialog()
    action_cols[2].button(
        "Clear selection",
        key="publish_clear_selection",
        use_container_width=True,
        type="secondary",
        disabled=not selected_rows,
        on_click=set_publish_rows_selected,
        args=(st.session_state, selected_rows, False),
    )
    action_cols[3].markdown(
        f"<div class='utility-rail-status review-page-status'>{len(selected_rows)} selected</div>",
        unsafe_allow_html=True,
    )
    action_cols[4].markdown(
        f"<div class='utility-rail-status review-page-status'>{len(filtered_rows)} in view</div>",
        unsafe_allow_html=True,
    )

    for index, row in enumerate(page_rows):
        photo = row["photo"]
        observation = row["observation"]
        hike = row["hike"]
        posting = actions.get_inat_posting(observation)
        posted_label = ""
        if posting.get("posted_at"):
            try:
                posted_label = format_species_log_date_label(datetime.fromisoformat(str(posting["posted_at"])))
            except Exception:
                posted_label = str(posting["posted_at"])[:10]
        if index > 0:
            st.divider()
        row_container = st.container()
        cols = row_container.columns([0.12, 0.5, 0.14, 0.24], gap="medium")
        with cols[0]:
            render_clickable_photo_with_view(
                photo,
                selected_hike_id=photo.get("hike_id"),
                source_view="Species Review",
                variant="publish-thumb",
            )
        with cols[1]:
            posted_note_markup = (
                f"<span class='publish-posted-note'>Posted {escape(posted_label)}</span>"
                if posted_label and row["publish_state"] == "Posted"
                else ""
            )
            grouped_note_markup = (
                f"<span class='publish-posted-note'>Grouped observation • {int(posting.get('photo_count') or 1)} photos</span>"
                if posting.get("grouped")
                else ""
            )
            publish_row_markup = (
                '<div class="publish-row-shell">'
                '<div class="publish-row-header">'
                f"{render_publish_state_chip(row['publish_state'])}"
                f"{posted_note_markup}"
                f"{grouped_note_markup}"
                "</div>"
                f"<div class=\"species-summary-name\">{escape(observation.get('common_name') or observation.get('scientific_name') or 'Unknown species')}</div>"
                f"<div class=\"species-summary-scientific\">{escape(observation.get('scientific_name') or '')}</div>"
                f"<div class=\"species-summary-meta\">{escape(hike.get('title') or 'Untitled outing')} • {escape(str(hike.get('hike_date') or ''))}</div>"
                f"<p class='photo-meta publish-photo-meta'>{format_photo_meta_html(photo, selected_hike_id=photo.get('hike_id'), link_coordinates=True, include_map_link=True)}</p>"
                "</div>"
            )
            st.markdown(publish_row_markup, unsafe_allow_html=True)
        select_key = f"publish_select_{observation['id']}"
        with cols[2]:
            current_selected = observation["id"] in st.session_state.publish_selected_ids
            if select_key not in st.session_state:
                st.session_state[select_key] = current_selected
            is_selected = st.checkbox("Select for publishing", key=select_key)
            set_publish_rows_selected(
                st.session_state,
                [row],
                is_selected,
                update_widgets=False,
            )
        with cols[3]:
            if row["publish_state"] in {"Posted", "Ready to post", "Needs attention"}:
                actions.render_publish_lane_management_controls(
                    repository,
                    inat_client,
                    observation,
                    photo,
                    key_prefix=f"publish_manage_{observation['id']}",
                )
                actions.render_inat_posting_controls(
                    repository,
                    inat_client,
                    observation,
                    photo,
                    place_guess=hike.get("location_name"),
                    key_prefix=f"publish_row_{observation['id']}",
                )
