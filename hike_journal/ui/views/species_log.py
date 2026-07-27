from __future__ import annotations

from datetime import date
from html import escape
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from hike_journal.config import settings
from hike_journal.domain.discovery import (
    DISCOVERY_ALGORITHM_VERSION,
    DISCOVERY_GROUPS,
    DISCOVERY_RADII_KM,
)
from hike_journal.services.discovery import SpeciesDiscoveryService
from hike_journal.services.inat import InatClient, InatRateLimitError, InatRequestError
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.ui.components import get_photo_thumbnail_url, section_heading


def _build_discovery_species_row_html(item: dict[str, Any], *, show_focus: bool) -> str:
    collected = bool(item.get("collected"))
    photo_url = (
        item.get("collection_photo_url")
        if collected and item.get("collection_photo_url")
        else (item.get("reference_photo") or {}).get("url")
    )
    photo = item.get("reference_photo") or {}
    attribution = str(photo.get("attribution") or "").strip()
    status = "Logged in your collection" if collected else str(item.get("frequency_band") or "Nearby record")
    focus_order = item.get("focus_order")
    focus_copy = (
        f"<span class='field-quest-focus'>Focus {int(focus_order)}</span>"
        if show_focus and focus_order
        else ""
    )
    image_markup = (
        f"<img src='{escape(str(photo_url))}' alt='{escape(str(item.get('common_name') or 'Species'))}'>"
        if photo_url
        else "<div class='field-quest-image-fallback'>No image</div>"
    )
    attribution_copy = f" · {escape(attribution)}" if attribution and not collected else ""
    collected_class = " is-collected" if collected else " is-unseen"
    return (
        f'<div class="field-quest-species-row{collected_class}">'
        f'<div class="field-quest-species-image">{image_markup}</div>'
        '<div class="field-quest-species-copy">'
        f'<div class="field-quest-species-kicker">{escape(status)} {focus_copy}</div>'
        f'<div class="field-quest-species-name">{escape(str(item.get("common_name") or "Unknown species"))}</div>'
        f'<div class="field-quest-species-scientific">{escape(str(item.get("scientific_name") or ""))}</div>'
        f'<div class="field-quest-species-meta">{int(item.get("observation_count") or 0):,} '
        f"research-grade reports nearby{attribution_copy}</div>"
        "</div>"
        f'<div class="field-quest-species-rank">{int(item.get("nearby_rank") or 0):02d}</div>'
        "</div>"
    )


def _render_discovery_species_rows(taxa: list[dict[str, Any]], *, show_focus: bool) -> None:
    for item in taxa:
        st.html(_build_discovery_species_row_html(item, show_focus=show_focus))


def _render_nearby_mode(
    repository: HikeJournalRepository,
    hikes: list[dict[str, Any]],
    context: dict[str, Any],
) -> None:
    if not settings.species_discovery_enabled:
        st.info("Nearby species discovery is currently turned off.")
        return
    service = SpeciesDiscoveryService(repository)
    areas = service.list_areas(repository)
    if not areas:
        st.warning("No coordinate-backed hike locations are available yet.")
        return
    area_by_label = {area["name"]: area for area in areas}
    labels = list(area_by_label)
    selected_area_id = st.session_state.get("species_nearby_area_id")
    selected_area_name = str(st.session_state.get("species_nearby_area_name") or "")
    default_index = next(
        (
            index
            for index, label in enumerate(labels)
            if area_by_label[label]["id"] == selected_area_id
            or label.casefold() == selected_area_name.casefold()
        ),
        0,
    )
    with st.container(key="species_discovery_controls"):
        controls = st.columns([0.35, 0.18, 0.19, 0.28], gap="small")
        area_label = controls[0].selectbox(
            "Area",
            labels,
            index=default_index,
            placeholder="Search saved trails",
        )
        target_date = controls[1].date_input("Season", value=date.today())
        radius = controls[2].segmented_control(
            "Radius",
            list(DISCOVERY_RADII_KM),
            default=st.session_state.get("species_nearby_radius", 10),
            format_func=lambda value: f"{value} km",
        ) or 10
        group_label = controls[3].selectbox(
            "Species group",
            list(DISCOVERY_GROUPS),
            index=list(DISCOVERY_GROUPS).index(
                st.session_state.get("species_nearby_group", "All Life")
                if st.session_state.get("species_nearby_group", "All Life") in DISCOVERY_GROUPS
                else "All Life"
            ),
        )
    area = area_by_label[area_label]
    st.session_state.species_nearby_area_id = area["id"]
    st.session_state.species_nearby_area_name = area["name"]
    st.session_state.species_nearby_radius = radius
    st.session_state.species_nearby_group = group_label
    try:
        with st.spinner("Reading recent field reports…"):
            nearby = service.nearby(
                area=area,
                target_date=target_date,
                radius_km=radius,
                iconic_taxon=group_label,
                observations=context.get("confirmed_observations") or [],
                photos_by_id=context.get("photos_by_id") or {},
            )
    except (ValueError, InatRequestError, InatRateLimitError) as exc:
        st.error(str(exc))
        return

    progress = nearby["progress"]
    st.markdown(
        f"""
        <div class="field-quest-progress-copy">
            <div>
                <span>{escape(nearby['area']['name'])}</span>
                <strong>{progress['collected_count']} of {progress['total_count']} logged</strong>
            </div>
            <p>{escape(nearby['period']['label'])} · {nearby['area']['radius_km']} km · reporting frequency, not encounter probability</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    completion = progress["collected_count"] / progress["total_count"] if progress["total_count"] else 0.0
    st.progress(completion)
    if nearby["data_density"]["message"]:
        st.warning(nearby["data_density"]["message"])
    if not nearby["taxa"]:
        st.info("No research-grade species reports matched this area and season.")
        return

    unseen = [item for item in nearby["taxa"] if not item.get("collected")]
    focus_options = {
        f"{item['common_name']} · {item['scientific_name']}": int(item["taxon_id"])
        for item in unseen
    }
    selected_focus_labels = st.multiselect(
        "Focus finds",
        list(focus_options),
        max_selections=5,
        placeholder="Choose up to five species for the next outing",
        help="Focus finds are saved with the quest and can be changed later.",
    )
    action_cols = st.columns([0.24, 0.76])
    if action_cols[0].button("Save Field Quest", type="primary", use_container_width=True):
        selected_ids = [focus_options[label] for label in selected_focus_labels]
        focus_order = {taxon_id: index + 1 for index, taxon_id in enumerate(selected_ids)}
        quest_taxa = [
            {**item, "focus_order": focus_order.get(int(item["taxon_id"]))}
            for item in nearby["taxa"]
        ]
        user_context = st.session_state.get("current_user_context") or {}
        try:
            saved = repository.create_species_quest(
                {
                    "owner_subject": user_context.get("subject"),
                    "owner_email": str(user_context.get("email") or "").strip().lower() or None,
                    "location_id": area["id"],
                    "linked_hike_id": None,
                    "title": f"{area['name']} · {nearby['period']['label']}",
                    "status": "active",
                    "area_name": area["name"],
                    "lat": nearby["area"]["lat"],
                    "lng": nearby["area"]["lng"],
                    "radius_km": radius,
                    "target_date": target_date.isoformat(),
                    "months": nearby["period"]["months"],
                    "iconic_taxon": nearby["filters"]["iconic_taxon"],
                    "algorithm_version": DISCOVERY_ALGORITHM_VERSION,
                    "target_count": len(quest_taxa),
                },
                quest_taxa,
            )
        except RuntimeError as exc:
            st.error(str(exc))
        else:
            st.session_state.species_quest_selected_id = saved["id"]
            st.session_state.species_log_mode = "Field Quests"
            st.rerun()
    action_cols[1].caption(
        f"Source refreshed {nearby['source']['fetched_at'][:10]}"
        + (" · cached result" if nearby["source"]["from_cache"] else "")
    )
    _render_discovery_species_rows(nearby["taxa"], show_focus=False)


def _render_quests_mode(
    repository: HikeJournalRepository,
    hikes: list[dict[str, Any]],
    context: dict[str, Any],
) -> None:
    user_context = st.session_state.get("current_user_context") or {}
    service = SpeciesDiscoveryService(repository)
    quests = repository.list_species_quests(
        owner_subject=user_context.get("subject"),
        owner_email=user_context.get("email"),
    )
    status_filter = st.segmented_control(
        "Quest status",
        ["Active", "Archived"],
        default=st.session_state.get("species_quest_status_filter", "Active"),
        label_visibility="collapsed",
    ) or "Active"
    st.session_state.species_quest_status_filter = status_filter
    quests = [quest for quest in quests if str(quest.get("status")) == status_filter.lower()]
    if not quests:
        st.info(
            "No saved Field Quests yet. Open Nearby, choose an area and season, then save its checklist."
            if status_filter == "Active"
            else "No archived Field Quests."
        )
        return
    quest_by_label = {
        f"{quest.get('title') or 'Field Quest'} · {str(quest.get('created_at') or '')[:10]}": quest
        for quest in quests
    }
    labels = list(quest_by_label)
    selected_id = st.session_state.get("species_quest_selected_id")
    selected_index = next(
        (index for index, label in enumerate(labels) if str(quest_by_label[label]["id"]) == str(selected_id)),
        0,
    )
    selected_label = st.selectbox("Saved quest", labels, index=selected_index)
    quest = quest_by_label[selected_label]
    st.session_state.species_quest_selected_id = quest["id"]
    payload = service.quest_payload(
        quest,
        observations=context.get("confirmed_observations") or [],
        photos_by_id=context.get("photos_by_id") or {},
    )
    progress = payload["progress"]
    st.markdown(
        f"""
        <div class="field-quest-progress-copy">
            <div><span>{escape(payload['area']['name'])}</span><strong>{progress['collected_count']} of {progress['total_count']} logged</strong></div>
            <p>{escape(payload['period']['label'])} · frozen checklist · {progress['remaining_count']} remaining</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    completion = progress["collected_count"] / progress["total_count"] if progress["total_count"] else 0.0
    st.progress(completion)

    taxon_by_label = {
        f"{item['common_name']} · {item['scientific_name']}": int(item["taxon_id"])
        for item in payload["taxa"]
        if not item.get("collected")
    }
    selected_focus = [
        label
        for label, taxon_id in taxon_by_label.items()
        if any(
            int(item["taxon_id"]) == taxon_id and item.get("focus_order")
            for item in payload["taxa"]
        )
    ]
    focus_labels = st.multiselect(
        "Focus finds",
        list(taxon_by_label),
        default=selected_focus,
        max_selections=5,
    )
    hike_by_label = {"No linked outing": None, **{str(hike.get("title") or "Untitled hike"): hike["id"] for hike in hikes}}
    current_hike_id = payload.get("linked_hike_id")
    hike_labels = list(hike_by_label)
    hike_index = next(
        (index for index, label in enumerate(hike_labels) if hike_by_label[label] == current_hike_id),
        0,
    )
    linked_hike_label = st.selectbox("Linked outing", hike_labels, index=hike_index)
    actions = st.columns([0.22, 0.22, 0.56])
    if actions[0].button("Save quest", type="primary", use_container_width=True):
        repository.update_species_quest(
            str(quest["id"]),
            linked_hike_id=hike_by_label[linked_hike_label],
            set_linked_hike=True,
            focus_taxon_ids=[taxon_by_label[label] for label in focus_labels],
        )
        st.rerun()
    next_status = "archived" if payload["status"] == "active" else "active"
    if actions[1].button(
        "Archive" if next_status == "archived" else "Restore",
        use_container_width=True,
    ):
        repository.update_species_quest(str(quest["id"]), status=next_status)
        st.session_state.species_quest_selected_id = None
        st.rerun()
    actions[2].caption("Completed focus finds remain in the frozen checklist and continue to count toward progress.")
    _render_discovery_species_rows(payload["taxa"], show_focus=True)


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
    selected_mode = st.segmented_control(
        "Species Log mode",
        ["Collection", "Nearby", "Field Quests"],
        default=st.session_state.get("species_log_mode", "Collection"),
        label_visibility="collapsed",
        key="species_log_mode_selector",
    ) or "Collection"
    st.session_state.species_log_mode = selected_mode
    mode_copy = {
        "Collection": (
            "Field index",
            "Search the species record, then open an entry to revisit where and when it was observed.",
        ),
        "Nearby": (
            "Seasonal field reports",
            "Choose a saved trail to see which unlogged species are reported there most often this season.",
        ),
        "Field Quests": (
            "Saved checklists",
            "Keep a stable area checklist, choose focus finds, and watch confirmed species advance it.",
        ),
    }
    eyebrow, description = mode_copy[selected_mode]
    section_heading(
        "Species Log",
        eyebrow,
        description,
    )
    st.write("")

    all_species = species_log_context.get("all_species", [])
    species_rows = species_log_context.get("species_rows", [])
    representative_observations = species_log_context.get("representative_observations", {})
    posted_observations = species_log_context.get("posted_observations", [])
    if selected_mode == "Nearby":
        _render_nearby_mode(repository, hikes, species_log_context)
        return
    if selected_mode == "Field Quests":
        _render_quests_mode(repository, hikes, species_log_context)
        return
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
