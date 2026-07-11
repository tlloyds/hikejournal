from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from hike_journal.services.inat import InatClient
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.ui.components import get_photo_thumbnail_url, section_heading


def render_species_log_view(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    hikes: list[dict[str, Any]],
    species_log_context: dict[str, Any],
    *,
    quick_upload_hike_filter: str,
    build_species_log_record_href: Any,
    paginate_items: Any,
    render_back_to_top_link: Any,
    render_species_log_inat_sync_panel: Any,
    render_species_log_toolbar: Any,
    render_species_record_dialog: Any,
    reset_species_log_page: Any,
    resolve_page_size: Any,
    set_species_log_record_query_state: Any,
) -> None:
    components.html(
        """
        <script>
        (function () {
          const doc = window.parent && window.parent.document ? window.parent.document : document;
          if (!doc || doc.__hjSpeciesLogEncounterCleanupInstalled) return;
          const prune = () => {
            doc.querySelectorAll('.species-log-encounter').forEach((node) => {
              if (!node.children.length && !(node.textContent || '').trim()) {
                node.remove();
              }
            });
          };
          prune();
          const observer = new MutationObserver(prune);
          observer.observe(doc.body, { childList: true, subtree: true });
          doc.__hjSpeciesLogEncounterCleanupInstalled = true;
        })();
        </script>
        """,
        height=0,
        width=0,
    )
    st.markdown("<div id='species-log-top'></div>", unsafe_allow_html=True)
    section_heading(
        "Species Log",
        "Field index",
        "Search the species record, then open an entry to revisit where and when it was observed.",
    )
    st.write("")

    all_species = species_log_context.get("all_species", [])
    species_rows = species_log_context.get("species_rows", [])
    representative_observations = species_log_context.get("representative_observations", {})
    posted_observations = species_log_context.get("posted_observations", [])
    if not all_species:
        st.info("Confirmed species will appear here once you begin reviewing photos.")
        return

    hike_options = ["All hikes", quick_upload_hike_filter, *[hike.get("title") or "Untitled hike" for hike in hikes]]
    valid_hike_filter = st.session_state.get("species_log_hike_filter", "All hikes")
    if valid_hike_filter not in hike_options:
        st.session_state.species_log_hike_filter = "All hikes"
    sort_options = ["Most recent", "Most seen", "A-Z", "Newest species first"]
    if st.session_state.get("species_log_sort") not in sort_options:
        st.session_state.species_log_sort = "Most recent"

    with st.container(key="species_log_filters"):
        controls = st.columns([0.28, 0.18, 0.14, 0.12, 0.14, 0.14], gap="small")
        query = controls[0].text_input(
            "Search species",
            placeholder="Blueberry, milkweed, duck potato, Vaccinium, oak...",
            key="species_log_query",
            label_visibility="collapsed",
            on_change=reset_species_log_page,
        )
        controls[1].selectbox(
            "Hike filter",
            hike_options,
            key="species_log_hike_filter",
            label_visibility="collapsed",
            on_change=reset_species_log_page,
        )
        controls[2].toggle(
            "Mapped only",
            key="species_log_mapped_only",
            on_change=reset_species_log_page,
        )
        controls[3].selectbox(
            "Posted filter",
            ["All", "Posted", "Not posted"],
            key="species_log_posted_filter",
            label_visibility="collapsed",
            on_change=reset_species_log_page,
        )
        controls[4].toggle(
            "Include secondary",
            key="species_log_include_secondary",
            on_change=reset_species_log_page,
        )
        controls[5].selectbox(
            "Sort species",
            sort_options,
            key="species_log_sort",
            label_visibility="collapsed",
            on_change=reset_species_log_page,
        )

    render_species_log_inat_sync_panel(repository, inat_client, posted_observations)

    if not species_rows:
        st.info("No confirmed species matched that search.")
        return

    page_rows, total_pages = paginate_items(species_rows, "species_log_page", "species_log_page_size")
    render_species_log_toolbar(species_rows, page_rows, total_pages)

    total_sightings = sum(row["sighting_count"] for row in species_rows)
    current_page_size = resolve_page_size(len(species_rows), st.session_state.species_log_page_size)
    visible_start = 0 if not page_rows else ((st.session_state.species_log_page - 1) * current_page_size) + 1
    visible_end = 0 if not page_rows else visible_start + len(page_rows) - 1
    st.markdown(
        f"<div class='species-log-results'>{len(species_rows)} species matched • {total_sightings} confirmed sightings"
        + (f" • showing {visible_start}-{visible_end}" if page_rows else "")
        + "</div>",
        unsafe_allow_html=True,
    )
    page_keys = [row["key"] for row in page_rows]
    if not page_keys:
        st.info("No confirmed species matched that search.")
        return
    if st.session_state.species_log_focus_key not in page_keys:
        st.session_state.species_log_focus_key = page_keys[0]

    species_lookup = {row["key"]: row for row in page_rows}
    st.markdown(
        f"""
        <div class='species-log-index-head species-log-index-head--browse'>
            <p class='workspace-lane-label'>Browse species in view</p>
            <p class='species-log-index-caption'>{len(page_rows)} record{'s' if len(page_rows) != 1 else ''} on this page. Open a species when you want to step into its full record.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    index_chunk_size = 4
    for start in range(0, len(page_rows), index_chunk_size):
        chunk = page_rows[start:start + index_chunk_size]
        index_cols = st.columns(index_chunk_size, gap="small")
        for idx, row in enumerate(chunk):
            thumb_url = get_photo_thumbnail_url(row["lead_photo"])
            is_current_focus = row["key"] == st.session_state.species_log_focus_key
            is_open_record = is_current_focus and st.session_state.species_log_record_open
            record_href = build_species_log_record_href(row["key"])
            with index_cols[idx]:
                st.markdown(
                    f"""
                    <a class='species-log-index-card-link' href='{escape(record_href)}' target='_self'>
                    <div class='species-log-index-card{" species-log-index-card--active" if is_current_focus else ""}{" species-log-index-card--open" if is_open_record else ""}'>
                        <img class='species-log-index-thumb' src='{escape(thumb_url)}' alt='{escape(row["common_name"])}'>
                        <div class='species-log-index-card-body'>
                            <div class='species-log-index-card-state'>{"Open now" if is_open_record else ("Last opened" if is_current_focus else "Species record")}</div>
                            <div class='species-log-index-card-title'>{escape(row["common_name"])}</div>
                            {f"<div class='species-log-index-card-subtitle'>{escape(row['scientific_name'])}</div>" if row.get('scientific_name') else ""}
                            <div class='species-log-index-card-meta'>{row['sighting_count']} sighting{'s' if row['sighting_count'] != 1 else ''} • {row['hike_count']} hike{'s' if row['hike_count'] != 1 else ''}</div>
                        </div>
                    </div>
                    </a>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Open record",
                    key=f"species_log_focus_{row['key']}",
                    use_container_width=True,
                    type="primary" if row["key"] == st.session_state.species_log_focus_key else "secondary",
                ):
                    st.session_state.species_log_focus_key = row["key"]
                    st.session_state.species_log_record_open = True
                    set_species_log_record_query_state(row["key"], True)
                    st.rerun()
    if (
        st.session_state.species_log_record_open
        and st.session_state.species_log_focus_key in species_lookup
        and not st.session_state.viewer_open
        and not st.session_state.inat_token_dialog_open
    ):
        render_species_record_dialog(repository, page_rows, species_lookup, representative_observations)
    if st.session_state.species_log_page_size == 0 and page_rows:
        render_back_to_top_link("species-log-top")
