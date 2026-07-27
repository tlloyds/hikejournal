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


QUEST_FOCUS_LIMIT = 10


def _discovery_status_label(item: dict[str, Any]) -> str:
    frequency_band = str(item.get("frequency_band") or "Nearby record")
    if item.get("collected"):
        return f"Logged in your collection · {frequency_band}"
    return frequency_band


def _build_discovery_species_row_html(
    item: dict[str, Any],
    *,
    show_focus: bool,
    focus_selected: bool = False,
) -> str:
    collected = bool(item.get("collected"))
    photo_url = (
        item.get("collection_photo_url")
        if collected and item.get("collection_photo_url")
        else (item.get("reference_photo") or {}).get("url")
    )
    photo = item.get("reference_photo") or {}
    attribution = str(photo.get("attribution") or "").strip()
    status = _discovery_status_label(item)
    focus_order = item.get("focus_order")
    focus_copy = (
        f"<span class='field-quest-focus'>Quest pick {int(focus_order)} of {QUEST_FOCUS_LIMIT}</span>"
        if show_focus and focus_order
        else ""
    )
    common_name = str(item.get("common_name") or "Species")
    if photo_url:
        image = (
            f"<img src='{escape(str(photo_url), quote=True)}' "
            f"alt='{escape(common_name, quote=True)}'>"
        )
        link_copy = "Open photo" if collected else "View in color"
        aria_copy = (
            f"Open your {common_name} observation"
            if collected
            else f"View {common_name} in color"
        )
        image_markup = (
            f"<a class='field-quest-species-image-link' "
            f"href='{escape(str(photo_url), quote=True)}' target='_blank' "
            f"rel='noopener noreferrer' aria-label='{escape(aria_copy, quote=True)}'>"
            f"{image}<span>{link_copy}</span></a>"
        )
    else:
        image_markup = "<div class='field-quest-image-fallback'>No image</div>"
    attribution_copy = f" · {escape(attribution)}" if attribution and not collected else ""
    match_reason = str(item.get("match_reason") or "").strip()
    wikipedia_url = str(item.get("wikipedia_url") or "").strip()
    wikipedia_summary = str(item.get("wikipedia_summary") or "").strip()
    context_markup = ""
    if match_reason or wikipedia_summary or wikipedia_url:
        wikipedia_markup = (
            f" <a href='{escape(wikipedia_url, quote=True)}' target='_blank' "
            "rel='noopener noreferrer'>Read on Wikipedia</a>"
            if wikipedia_url
            else ""
        )
        context_markup = (
            "<details class='field-quest-species-context'><summary>Why it’s here</summary>"
            f"<p>{escape(match_reason)}</p>"
            f"{f'<p>{escape(wikipedia_summary)}</p>' if wikipedia_summary else ''}"
            f"{wikipedia_markup}</details>"
        )
    collected_class = " is-collected" if collected else " is-unseen"
    focus_class = " is-focus-selected" if focus_selected else ""
    return (
        f'<div class="field-quest-species-row{collected_class}{focus_class}">'
        f'<div class="field-quest-species-image">{image_markup}</div>'
        '<div class="field-quest-species-copy">'
        f'<div class="field-quest-species-kicker">{escape(status)} {focus_copy}</div>'
        f'<div class="field-quest-species-name">{escape(str(item.get("common_name") or "Unknown species"))}</div>'
        f'<div class="field-quest-species-scientific">{escape(str(item.get("scientific_name") or ""))}</div>'
        f'<div class="field-quest-species-meta">{int(item.get("observation_count") or 0):,} '
        f"research-grade reports nearby{attribution_copy}</div>"
        f"{context_markup}"
        "</div>"
        f'<div class="field-quest-species-rank">{int(item.get("nearby_rank") or 0):02d}</div>'
        "</div>"
    )


def _build_focus_picker_html(
    taxa: list[dict[str, Any]],
    focus_ids: list[int],
    *,
    noun: str = "selected",
) -> str:
    lookup = {int(item["taxon_id"]): item for item in taxa}
    slots: list[str] = []
    for index in range(QUEST_FOCUS_LIMIT):
        item = lookup.get(focus_ids[index]) if index < len(focus_ids) else None
        name = str((item or {}).get("common_name") or "Choose a species")
        slot_class = " is-filled" if item else ""
        slots.append(
            f"<li class='field-quest-focus-slot{slot_class}'>"
            f"<span>{index + 1}</span><strong>{escape(name)}</strong></li>"
        )
    count = len(focus_ids)
    complete_class = " is-complete" if count == QUEST_FOCUS_LIMIT else ""
    return (
        f"<div class='field-quest-focus-picker{complete_class}'>"
        "<div class='field-quest-focus-picker-copy'>"
        f"<span>Quest targets</span><strong>{count} of {QUEST_FOCUS_LIMIT} {escape(noun)}</strong>"
        "</div>"
        f"<ol>{''.join(slots)}</ol>"
        "</div>"
    )


def _normalize_focus_taxon_ids(value: Any, taxa: list[dict[str, Any]]) -> list[int]:
    valid_ids = {int(item["taxon_id"]) for item in taxa}
    normalized: list[int] = []
    for raw_id in value if isinstance(value, (list, tuple, set)) else []:
        try:
            taxon_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if taxon_id in valid_ids and taxon_id not in normalized:
            normalized.append(taxon_id)
        if len(normalized) == QUEST_FOCUS_LIMIT:
            break
    return normalized


def _toggle_focus_taxon_id(current: list[int], taxon_id: int) -> list[int]:
    if taxon_id in current:
        return [current_id for current_id in current if current_id != taxon_id]
    if len(current) >= QUEST_FOCUS_LIMIT:
        return current
    return [*current, taxon_id]


def _render_discovery_species_rows(
    taxa: list[dict[str, Any]],
    *,
    show_focus: bool,
    focus_state_key: str | None = None,
    key_prefix: str = "discovery",
) -> None:
    focus_ids = (
        _normalize_focus_taxon_ids(st.session_state.get(focus_state_key), taxa)
        if focus_state_key
        else []
    )
    if focus_state_key:
        st.session_state[focus_state_key] = focus_ids
    for item in taxa:
        taxon_id = int(item["taxon_id"])
        focus_selected = taxon_id in focus_ids
        display_item = {
            **item,
            "focus_order": focus_ids.index(taxon_id) + 1 if focus_selected else None,
        }
        if not focus_state_key:
            st.html(
                _build_discovery_species_row_html(
                    item,
                    show_focus=show_focus,
                    focus_selected=bool(show_focus and item.get("focus_order")),
                )
            )
            continue
        with st.container(key=f"species_focus_row_{key_prefix}_{taxon_id}"):
            row = st.columns([0.87, 0.13], gap="small", vertical_alignment="center")
            with row[0]:
                st.html(
                    _build_discovery_species_row_html(
                        display_item,
                        show_focus=True,
                        focus_selected=focus_selected,
                    )
                )
            button_label = (
                f"Selected {focus_ids.index(taxon_id) + 1}/{QUEST_FOCUS_LIMIT}"
                if focus_selected
                else "Select"
            )
            if row[1].button(
                button_label,
                key=f"focus_action_{key_prefix}_{taxon_id}",
                disabled=len(focus_ids) >= QUEST_FOCUS_LIMIT and not focus_selected,
                help="Remove this quest target" if focus_selected else "Select this species for the quest",
                use_container_width=True,
            ):
                st.session_state[focus_state_key] = _toggle_focus_taxon_id(focus_ids, taxon_id)
                st.rerun()


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
    selected_area_id = st.session_state.get("species_nearby_area_id")
    selected_area_name = str(st.session_state.get("species_nearby_area_name") or "")
    default_index = next(
        (
            index
            for index, candidate in enumerate(areas)
            if candidate["id"] == selected_area_id
            or str(candidate["name"]).casefold() == selected_area_name.casefold()
        ),
        None,
    )
    with st.container(key="species_discovery_controls"):
        controls = st.columns([0.35, 0.18, 0.19, 0.28], gap="small")
        area = controls[0].selectbox(
            "Search saved trails",
            areas,
            index=default_index,
            format_func=lambda candidate: str(candidate["name"]),
            placeholder="Type a trail name…",
            help="Open this list and type to filter your saved trails.",
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
    if area is None:
        st.caption("Start typing above, then choose a saved trail with coordinates.")
        return
    discovery_query_key = "|".join(
        [str(area["id"]), target_date.isoformat(), str(radius), str(group_label)]
    )
    if st.session_state.get("species_nearby_query_key") != discovery_query_key:
        st.session_state.species_nearby_query_key = discovery_query_key
        st.session_state.species_nearby_limit = 50
    result_limit = int(st.session_state.get("species_nearby_limit", 50))
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
                limit=result_limit,
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

    focus_state_key = "species_nearby_focus_ids"
    focus_ids = _normalize_focus_taxon_ids(
        st.session_state.get(focus_state_key),
        nearby["taxa"],
    )
    st.session_state[focus_state_key] = focus_ids
    if (
        result_limit == 50
        and progress["total_count"] == 50
        and progress["collected_count"] == 50
    ):
        expansion = st.columns([0.30, 0.70])
        if expansion[0].button(
            "Expand to 100 species",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.species_nearby_limit = 100
            st.rerun()
        expansion[1].caption("You completed the first 50. Open the next 50 nearby species.")
    elif result_limit == 100:
        st.caption("Expanded field list · showing up to 100 nearby species.")

    st.markdown("#### Build a Field Quest")
    st.caption("Choose between one and ten targets. Species already in your collection are eligible.")
    st.html(_build_focus_picker_html(nearby["taxa"], focus_ids))
    action_cols = st.columns([0.24, 0.16, 0.60])
    if action_cols[0].button(
        (
            "Save Field Quest"
            if focus_ids
            else "Choose at least one"
        ),
        type="primary",
        use_container_width=True,
        disabled=not focus_ids,
        help="Choose at least one species before saving." if not focus_ids else None,
    ):
        focus_order = {taxon_id: index + 1 for index, taxon_id in enumerate(focus_ids)}
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
            st.session_state[focus_state_key] = []
            st.session_state.species_quest_selected_id = saved["id"]
            st.session_state.species_log_mode = "Field Quests"
            st.rerun()
    if action_cols[1].button(
        "Clear picks",
        use_container_width=True,
        disabled=not focus_ids,
    ):
        st.session_state[focus_state_key] = []
        st.rerun()
    action_cols[2].caption(
        f"Source refreshed {nearby['source']['fetched_at'][:10]}"
        + (" · cached result" if nearby["source"]["from_cache"] else "")
    )
    _render_discovery_species_rows(
        nearby["taxa"],
        show_focus=True,
        focus_state_key=focus_state_key,
        key_prefix="nearby",
    )


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
    selected_id = st.session_state.get("species_quest_selected_id")
    quest = next(
        (candidate for candidate in quests if str(candidate["id"]) == str(selected_id)),
        quests[0] if len(quests) == 1 else None,
    )
    if quest is None:
        st.markdown("#### Choose a Field Quest")
        tile_columns = st.columns(2, gap="medium")
        for index, candidate in enumerate(quests):
            candidate_payload = service.quest_payload(
                candidate,
                observations=context.get("confirmed_observations") or [],
                photos_by_id=context.get("photos_by_id") or {},
            )
            candidate_progress = candidate_payload["focus_progress"]
            with tile_columns[index % 2].container(border=True):
                st.markdown(f"**{candidate_payload['title']}**")
                st.caption(
                    f"{candidate_payload['area']['name']} · "
                    f"{candidate_progress['collected_count']} of {candidate_progress['total_count']} found"
                )
                if st.button(
                    "Open quest",
                    key=f"open_species_quest_{candidate['id']}",
                    use_container_width=True,
                ):
                    st.session_state.species_quest_selected_id = candidate["id"]
                    st.rerun()
        return
    if len(quests) > 1 and st.button("← All quests"):
        st.session_state.species_quest_selected_id = None
        st.rerun()
    st.session_state.species_quest_selected_id = quest["id"]
    payload = service.quest_payload(
        quest,
        observations=context.get("confirmed_observations") or [],
        photos_by_id=context.get("photos_by_id") or {},
    )
    progress = payload["focus_progress"]
    focus_taxa = payload["focus_taxa"]
    st.markdown(
        f"""
        <div class="field-quest-progress-copy">
            <div><span>{escape(payload['title'])}</span><strong>{progress['collected_count']} of {progress['total_count']} found</strong></div>
            <p>{escape(payload['area']['name'])} · {escape(payload['period']['label'])} · {progress['remaining_count']} target{'s' if progress['remaining_count'] != 1 else ''} remaining</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    completion = progress["collected_count"] / progress["total_count"] if progress["total_count"] else 0.0
    st.progress(completion)

    focus_state_key = f"species_quest_focus_ids_{quest['id']}"
    if focus_state_key not in st.session_state:
        st.session_state[focus_state_key] = [
            int(item["taxon_id"])
            for item in sorted(
                payload["taxa"],
                key=lambda item: int(item.get("focus_order") or 999),
            )
            if item.get("focus_order")
        ][:QUEST_FOCUS_LIMIT]
    focus_ids = _normalize_focus_taxon_ids(
        st.session_state.get(focus_state_key),
        payload["taxa"],
    )
    st.session_state[focus_state_key] = focus_ids
    edit_state_key = f"species_quest_editing_{quest['id']}"
    editing = bool(st.session_state.get(edit_state_key))
    st.html(_build_focus_picker_html(payload["taxa"], focus_ids, noun="chosen"))
    edit_actions = st.columns([0.24, 0.76])
    if edit_actions[0].button(
        "Cancel changes" if editing else "Change targets",
        use_container_width=True,
    ):
        if editing:
            st.session_state[focus_state_key] = [
                int(item["taxon_id"])
                for item in sorted(
                    payload["taxa"],
                    key=lambda item: int(item.get("focus_order") or 999),
                )
                if item.get("focus_order")
            ][:QUEST_FOCUS_LIMIT]
        st.session_state[edit_state_key] = not editing
        st.rerun()
    edit_actions[1].caption(
        "Your quest shows only the targets you choose. The original nearby list stays available while changing them."
    )

    if editing:
        save_cols = st.columns([0.24, 0.76])
        if save_cols[0].button(
            "Save targets",
            type="primary",
            use_container_width=True,
            disabled=not focus_ids,
        ):
            repository.update_species_quest(
                str(quest["id"]),
                focus_taxon_ids=focus_ids,
            )
            st.session_state[edit_state_key] = False
            st.rerun()
        save_cols[1].caption(
            f"{len(focus_ids)} of {QUEST_FOCUS_LIMIT} selected · logged species can remain quest targets."
        )
        _render_discovery_species_rows(
            payload["taxa"],
            show_focus=True,
            focus_state_key=focus_state_key,
            key_prefix=f"quest_{quest['id']}",
        )
    elif focus_taxa:
        st.markdown("#### Your quest targets")
        _render_discovery_species_rows(
            focus_taxa,
            show_focus=True,
            key_prefix=f"quest_targets_{quest['id']}",
        )
    else:
        st.info("This older quest has no targets yet. Choose at least one species to make it actionable.")

    with st.expander("Manage this quest"):
        title = st.text_input(
            "Quest name",
            value=str(payload["title"]),
            max_chars=160,
            key=f"species_quest_title_{quest['id']}",
        )
        hike_by_label = {
            "No linked outing": None,
            **{str(hike.get("title") or "Untitled hike"): hike["id"] for hike in hikes},
        }
        current_hike_id = payload.get("linked_hike_id")
        hike_labels = list(hike_by_label)
        hike_index = next(
            (
                index
                for index, label in enumerate(hike_labels)
                if hike_by_label[label] == current_hike_id
            ),
            0,
        )
        linked_hike_label = st.selectbox(
            "Linked outing",
            hike_labels,
            index=hike_index,
            key=f"species_quest_hike_{quest['id']}",
        )
        manage_actions = st.columns([0.24, 0.20, 0.20, 0.36])
        if manage_actions[0].button(
            "Save details",
            type="primary",
            use_container_width=True,
            key=f"save_quest_details_{quest['id']}",
            disabled=not title.strip(),
        ):
            repository.update_species_quest(
                str(quest["id"]),
                title=title,
                linked_hike_id=hike_by_label[linked_hike_label],
                set_linked_hike=True,
            )
            st.rerun()
        next_status = "archived" if payload["status"] == "active" else "active"
        if manage_actions[1].button(
            "Archive" if next_status == "archived" else "Restore",
            use_container_width=True,
            key=f"archive_quest_{quest['id']}",
        ):
            repository.update_species_quest(str(quest["id"]), status=next_status)
            st.session_state.pop(focus_state_key, None)
            st.session_state.species_quest_selected_id = None
            st.rerun()
        delete_state_key = f"species_quest_delete_confirm_{quest['id']}"
        if manage_actions[2].button(
            "Delete quest",
            use_container_width=True,
            key=f"delete_quest_{quest['id']}",
        ):
            st.session_state[delete_state_key] = True
            st.rerun()
        manage_actions[3].caption("Archiving is reversible. Deleting removes the quest and its saved target list.")
        if st.session_state.get(delete_state_key):
            st.warning(f'Delete “{payload["title"]}” permanently? Your observations will not be affected.')
            confirm_actions = st.columns([0.24, 0.20, 0.56])
            if confirm_actions[0].button(
                "Delete permanently",
                type="primary",
                use_container_width=True,
                key=f"confirm_delete_quest_{quest['id']}",
            ):
                repository.delete_species_quest(str(quest["id"]))
                for state_key in (focus_state_key, edit_state_key, delete_state_key):
                    st.session_state.pop(state_key, None)
                st.session_state.species_quest_selected_id = None
                st.rerun()
            if confirm_actions[1].button(
                "Cancel",
                use_container_width=True,
                key=f"cancel_delete_quest_{quest['id']}",
            ):
                st.session_state.pop(delete_state_key, None)
                st.rerun()


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
            "Choose a saved trail to see which species are reported there most often this season.",
        ),
        "Field Quests": (
            "Field quests",
            "Keep one clear target list for the outing, then watch confirmed observations complete it.",
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
