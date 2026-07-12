from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

import streamlit as st

from hike_journal.review_state import (
    apply_species_review_defaults,
    initialize_stage_selection,
    set_photo_selected,
    synchronize_species_selection,
)
from hike_journal.services.inat import InatClient
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.ui.components import format_photo_meta_html, render_clickable_photo_with_view


REVIEW_QUEUE_STATUS = "in_review"


@dataclass(frozen=True)
class SpeciesReviewActions:
    build_publish_rows: Any
    count_publish_states: Any
    paginate_items: Any
    render_add_species_popover: Any
    render_alternate_suggestions: Any
    render_back_to_top_link: Any
    render_community_id_request_controls: Any
    render_inat_token_manager: Any
    render_photo_note_editor: Any
    render_publishing_section: Any
    render_secondary_species_summary: Any
    render_species_management_toolbar: Any
    render_species_summary: Any


def get_review_state_label(observation: dict[str, Any] | None) -> str:
    if not observation:
        return "Waiting for suggestion"
    status = str(observation.get("status") or "").lower()
    if status == "pending":
        return "Ready for decision"
    if status == "confirmed":
        return "Confirmed"
    if status == "rejected":
        return "Rejected"
    return "Waiting for suggestion"


def render_review_state_chip(state: str) -> str:
    slug = state.lower().replace(" ", "-")
    return f"<span class='status-pill review-{slug}'>{escape(state)}</span>"


def render_species_review_entry_header(review_state: str, outing_title: str, outing_date: str | None = None) -> str:
    date_markup = f"<span>• {escape(str(outing_date))}</span>" if outing_date else ""
    return (
        "<div class='species-review-entry-head'>"
        "<div class='species-review-entry-kicker'>"
        f"{render_review_state_chip(review_state)}"
        f"<span>{escape(outing_title)}</span>"
        f"{date_markup}"
        "</div>"
        "</div>"
    )


def render_species_review_view(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    hikes: list[dict[str, Any]],
    review_queue_photos: list[dict[str, Any]],
    publish_confirmed_observations: list[dict[str, Any]],
    publish_photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    *,
    actions: SpeciesReviewActions,
) -> None:
    st.markdown("<div id='species-top'></div>", unsafe_allow_html=True)
    hike_by_id = {str(hike["id"]): hike for hike in hikes}
    review_mode = st.session_state.species_review_mode

    selected_photos = sorted(
        [photo for photo in review_queue_photos if photo.get("processing_status") == REVIEW_QUEUE_STATUS],
        key=lambda photo: (
            0 if not primary_observation_by_photo.get(photo["id"]) else 1,
            0 if (primary_observation_by_photo.get(photo["id"]) or {}).get("status") == "pending" else 1,
            photo.get("taken_at") or "",
            photo.get("created_at") or "",
        ),
    )
    review_waiting_count = len([photo for photo in selected_photos if photo["id"] not in primary_observation_by_photo])
    review_pending_count = len(
        [
            photo
            for photo in selected_photos
            if (primary_observation_by_photo.get(photo["id"]) or {}).get("status") == "pending"
        ]
    )
    review_confirmed_count = len(
        [
            photo
            for photo in selected_photos
            if (primary_observation_by_photo.get(photo["id"]) or {}).get("status") == "confirmed"
        ]
    )
    review_rejected_count = len(
        [
            photo
            for photo in selected_photos
            if (primary_observation_by_photo.get(photo["id"]) or {}).get("status") == "rejected"
        ]
    )
    publish_rows = actions.build_publish_rows(hikes, publish_confirmed_observations, publish_photos)
    publish_counts = actions.count_publish_states(publish_rows)

    if review_mode == "Publish":
        compact_title = "Publishing queue"
        compact_meta = (
            f"<span>{publish_counts['Ready to post']} ready</span>"
            f"<span>{publish_counts['Needs attention']} need attention</span>"
            f"<span>{publish_counts['Posted']} already posted</span>"
        )
    else:
        compact_title = "Review queue"
        compact_meta = (
            f"<span>{len(selected_photos)} queued</span>"
            f"<span>{review_waiting_count} waiting for suggestion</span>"
            f"<span>{review_pending_count} ready for decision</span>"
            f"<span>{review_confirmed_count} confirmed</span>"
        )

    st.markdown(
        f"""
        <section class="workspace-compact-strip">
            <div class="workspace-compact-head">
                <p class="workspace-lane-label">Species review</p>
                <h2 class="workspace-compact-title">{compact_title}</h2>
            </div>
            <div class="workspace-compact-meta">{compact_meta}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    review_option = f"Review · {len(selected_photos)}"
    publish_focus_count = publish_counts["Ready to post"] + publish_counts["Needs attention"]
    publish_option = f"Publish · {publish_focus_count}"
    current_mode_option = review_option if st.session_state.species_review_mode == "Review" else publish_option
    st.markdown(
        """
        <div class="workspace-mode-strip">
            <div class="workspace-mode-copy">
                <p class="workspace-lane-label">Workspace</p>
                <p class="workspace-mode-caption">Choose whether you are deciding IDs or publishing finished records.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    selected_mode_option = st.segmented_control(
        "Workspace",
        [review_option, publish_option],
        default=current_mode_option,
        key="species_review_mode_switch",
        label_visibility="collapsed",
    )
    selected_mode = "Review" if selected_mode_option == review_option else "Publish"
    if selected_mode != st.session_state.species_review_mode:
        st.session_state.species_review_mode = selected_mode
        st.rerun()
    st.markdown(
        f"<div class='workspace-mode-note'>{'Move through species decisions one queue at a time.' if st.session_state.species_review_mode == 'Review' else 'Publish confirmed sightings without leaving the review workspace.'}</div>",
        unsafe_allow_html=True,
    )

    actions.render_inat_token_manager(inat_client, st.session_state.current_user_context)
    st.write("")
    if st.session_state.species_review_mode == "Review":
        if selected_photos:
            apply_species_review_defaults(st.session_state, selected_photos)
            synchronize_species_selection(st.session_state, selected_photos)
            review_stage_default = "Needs decisions" if review_pending_count else ("Needs IDs" if review_waiting_count else "All")
            current_signature = tuple(photo["id"] for photo in selected_photos)
            review_signature_changed = st.session_state.species_review_stage_signature != current_signature
            if review_signature_changed:
                st.session_state.species_review_stage_signature = current_signature
            review_stage_labels = {
                "Needs IDs": f"Needs IDs · {review_waiting_count}",
                "Needs decisions": f"Needs decisions · {review_pending_count}",
                "Finished": f"Finished · {review_confirmed_count + review_rejected_count}",
                "All": f"All · {len(selected_photos)}",
            }
            if review_signature_changed:
                requested_stage = str(st.query_params.get("species_review_stage") or "")
                if requested_stage in review_stage_labels:
                    st.session_state.species_review_stage = requested_stage
                else:
                    st.session_state.species_review_stage = review_stage_default
            elif st.session_state.species_review_stage not in review_stage_labels:
                st.session_state.species_review_stage = review_stage_default
            st.markdown(
                """
                <div class="review-filter-strip">
                    <div class="review-filter-copy">
                        <p class="workspace-lane-label">Review stage</p>
                        <p class="review-filter-caption">Work one kind of task at a time: get suggestions first, then make your decisions.</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            selected_stage_label = st.segmented_control(
                "Review stage",
                list(review_stage_labels.values()),
                default=review_stage_labels.get(st.session_state.species_review_stage, review_stage_labels[review_stage_default]),
                key="species_review_stage_switch",
                label_visibility="collapsed",
            )
            selected_stage = next(
                (key for key, value in review_stage_labels.items() if value == selected_stage_label),
                st.session_state.species_review_stage if st.session_state.species_review_stage in review_stage_labels else review_stage_default,
            )
            if selected_stage != st.session_state.species_review_stage:
                st.session_state.species_review_stage = selected_stage
                st.session_state.species_page = 1
                st.rerun()

            def _matches_review_stage(photo: dict[str, Any]) -> bool:
                if st.session_state.species_review_stage == "All":
                    return True
                primary = primary_observation_by_photo.get(photo["id"])
                state = get_review_state_label(primary)
                return (
                    (st.session_state.species_review_stage == "Needs IDs" and state == "Waiting for suggestion")
                    or (st.session_state.species_review_stage == "Needs decisions" and state == "Ready for decision")
                    or (st.session_state.species_review_stage == "Finished" and state in {"Confirmed", "Rejected"})
                )

            filtered_review_photos = [photo for photo in selected_photos if _matches_review_stage(photo)]
            if not filtered_review_photos:
                st.info("Nothing is sitting in this review stage right now.")
                return

            initialize_stage_selection(
                st.session_state,
                st.session_state.species_review_stage,
                filtered_review_photos,
            )

            page_photos, total_pages = actions.paginate_items(filtered_review_photos, "species_page", "species_page_size")
            actions.render_species_management_toolbar(
                repository,
                inat_client,
                filtered_review_photos,
                page_photos,
                observations_by_photo,
                primary_observation_by_photo,
                total_pages,
                st.session_state.species_review_stage,
            )

            for photo_index, photo in enumerate(page_photos):
                primary_observation = primary_observation_by_photo.get(photo["id"])
                photo_observations = observations_by_photo.get(photo["id"], [])
                hike = hike_by_id.get(str(photo.get("hike_id")), {})
                outing_title = hike.get("title") or ("Standalone sighting" if not photo.get("hike_id") else "Open outing")
                outing_date = str(hike.get("hike_date") or "")
                review_state = get_review_state_label(primary_observation)
                if photo_index > 0:
                    st.divider()
                cols = st.columns([0.42, 0.58], gap="large")
                with cols[0]:
                    render_clickable_photo_with_view(photo, selected_hike_id=photo["hike_id"], source_view="Species Review")
                with cols[1]:
                    st.markdown(
                        render_species_review_entry_header(review_state, outing_title, outing_date),
                        unsafe_allow_html=True,
                    )
                    selected_key = f"species_select_{photo['id']}"
                    current_selected = photo["id"] in st.session_state.species_selected_ids
                    if selected_key not in st.session_state:
                        st.session_state[selected_key] = current_selected
                    review_selected = st.checkbox("Select photo", key=selected_key)
                    set_photo_selected(
                        st.session_state,
                        photo["id"],
                        review_selected,
                        update_widget=False,
                    )
                    st.markdown(
                        f"<p class='photo-meta'>{format_photo_meta_html(photo, selected_hike_id=photo.get('hike_id'), link_coordinates=True, include_map_link=True)}</p>",
                        unsafe_allow_html=True,
                    )
                    actions.render_photo_note_editor(repository, photo, key_prefix=f"review_note_{photo['id']}")
                    if primary_observation:
                        actions.render_species_summary(
                            repository,
                            primary_observation,
                            inat_client=inat_client,
                            photo=photo,
                            key_prefix=f"review_{photo['id']}",
                            show_details=True,
                        )
                        actions.render_alternate_suggestions(repository, inat_client, primary_observation, photo, key_prefix=f"review_{photo['id']}")
                        actions.render_community_id_request_controls(
                            repository,
                            inat_client,
                            primary_observation,
                            photo,
                            key_prefix=f"review_community_{photo['id']}",
                        )
                        actions.render_secondary_species_summary(photo_observations, primary_observation["id"])
                    else:
                        st.caption("No suggestion has been saved for this photo yet.")
                    actions.render_add_species_popover(
                        repository,
                        inat_client,
                        photo.get("hike_id"),
                        photo,
                        photo_observations,
                        key_prefix=f"review_add_{photo['id']}",
                    )
            if st.session_state.species_page_size == 0 and page_photos:
                actions.render_back_to_top_link("species-top")
        else:
            st.info("Mark photos for review in the Journal and they will appear here.")
    else:
        actions.render_publishing_section(
            repository,
            inat_client,
            hikes,
            publish_confirmed_observations,
            publish_photos,
        )
