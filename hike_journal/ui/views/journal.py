from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Any

import streamlit as st

from hike_journal.domain.library import photo_owner_email, photo_owner_subject
from hike_journal.domain.locations import (
    location_library_options,
    maybe_store_hike_location_tags,
    selected_location_defaults,
)
from hike_journal.domain.routes import (
    format_duration_compact,
    format_elevation_compact,
    parse_uploaded_route_import,
    route_import_meta,
    sync_hike_route_import,
)
from hike_journal.queries import fetch_hike_locations, invalidate_data_cache
from hike_journal.services.exif import extract_metadata
from hike_journal.services.image_processing import optimize_image
from hike_journal.services.inat import InatClient
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.storage import StorageService
from hike_journal.ui.components import format_photo_meta_html, render_clickable_photo, section_heading


REVIEW_QUEUE_STATUS = "in_review"
TCX_IMPORT_TYPES = ["tcx", "xml"]


@dataclass(frozen=True)
class JournalActions:
    _parse_date: Any
    paginate_photos: Any
    persist_uploaded_photo: Any
    render_alternate_suggestions: Any
    render_bottom_review_handoff: Any
    render_known_species_assignment_toolbar: Any
    render_photo_management_toolbar: Any
    render_photo_note_editor: Any
    render_photo_species_actions: Any
    render_quick_upload_dialog: Any
    render_secondary_species_summary: Any
    render_selection_toolbar: Any
    render_species_summary: Any
    sync_hike_cover_checkbox: Any
    sync_journal_review_checkbox: Any
    sync_known_species_checkbox: Any


def render_standalone_journal_view(
    repository: HikeJournalRepository,
    storage: StorageService,
    inat_client: InatClient,
    photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    user_context: dict[str, Any],
    known_species: list[dict[str, Any]],
    *,
    actions: JournalActions,
) -> None:
    st.markdown("<div id='journal-top'></div>", unsafe_allow_html=True)
    section_heading(
        "Photo Journal",
        "Everyday sightings and standalone field notes",
        "Keep neighborhood finds, one-off observations, and quick uploads together in one place, even when they were never part of a hike.",
    )
    st.write("")

    top_cols = st.columns([0.76, 0.24], gap="small")
    top_cols[0].caption("These photos still flow into species review, the master map, and your species log.")
    if top_cols[1].button("Quick upload", key="standalone_quick_upload", use_container_width=True, type="primary"):
        actions.render_quick_upload_dialog(storage, repository, user_context)

    if not photos:
        st.info("No standalone photos yet. Use Quick upload whenever you want to save a sighting outside a formal hike.")
        return

    review_selected_count = len([photo for photo in photos if photo.get("processing_status") == REVIEW_QUEUE_STATUS])
    actions.render_selection_toolbar(repository, photos, "journal")
    st.markdown("### Photo Field Notes")
    page_photos, total_pages = actions.paginate_photos(photos)
    actions.render_photo_management_toolbar(repository, storage, page_photos, photos, total_pages)
    actions.render_known_species_assignment_toolbar(
        repository,
        inat_client,
        page_photos,
        photos,
        primary_observation_by_photo,
        known_species,
        key_prefix="standalone",
    )
    for index, photo in enumerate(page_photos):
        primary_observation = primary_observation_by_photo.get(photo["id"])
        photo_observations = observations_by_photo.get(photo["id"], [])
        row_cols = st.columns([0.4, 0.6], gap="large")
        with row_cols[0]:
            render_clickable_photo(photo, selected_hike_id=None, scope="standalone")
        with row_cols[1]:
            st.markdown(
                f"<p class='photo-meta'>{format_photo_meta_html(photo, selected_hike_id=None, link_coordinates=True, include_map_link=True)}</p>",
                unsafe_allow_html=True,
            )
            actions.render_photo_note_editor(repository, photo, key_prefix=f"standalone_note_{photo['id']}")
            if primary_observation:
                is_confirmed = primary_observation.get("status") == "confirmed"
                actions.render_species_summary(
                    repository,
                    primary_observation,
                    inat_client=inat_client,
                    photo=photo,
                    place_guess=None,
                    key_prefix=f"standalone_{photo['id']}",
                    show_details=is_confirmed,
                    show_confidence=not is_confirmed,
                )
                actions.render_alternate_suggestions(repository, inat_client, primary_observation, photo, key_prefix=f"standalone_{photo['id']}")
                actions.render_secondary_species_summary(photo_observations, primary_observation["id"])
            else:
                st.caption("No species attached to this photo yet.")
            actions.render_photo_species_actions(
                repository,
                inat_client,
                photo,
                photo_observations,
                primary_observation,
                known_species,
                hike_id=None,
                key_prefix="standalone",
            )
            control_cols = st.columns([0.45, 0.35, 0.2], gap="small")
            selected = photo.get("processing_status") == REVIEW_QUEUE_STATUS
            checkbox_key = f"photo_select_{photo['id']}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = selected
            with control_cols[0]:
                st.checkbox(
                    "Queue for review",
                    key=checkbox_key,
                    on_change=actions.sync_journal_review_checkbox,
                    args=(repository, photo["id"], checkbox_key),
                )
            if not primary_observation:
                known_species_key = f"known_species_select_{photo['id']}"
                if known_species_key not in st.session_state:
                    st.session_state[known_species_key] = photo["id"] in st.session_state.known_species_selected_ids
                with control_cols[1]:
                    st.checkbox(
                        "Bulk select",
                        key=known_species_key,
                        on_change=actions.sync_known_species_checkbox,
                        args=(photo["id"], known_species_key),
                    )
            if st.session_state.delete_mode:
                delete_key = f"delete_photo_{photo['id']}"
                current_delete = photo["id"] in st.session_state.delete_photo_ids
                if delete_key not in st.session_state:
                    st.session_state[delete_key] = current_delete
                with control_cols[2]:
                    delete_toggle = st.checkbox("Mark to delete", key=delete_key)
                    if delete_toggle:
                        st.session_state.delete_photo_ids.add(photo["id"])
                    else:
                        st.session_state.delete_photo_ids.discard(photo["id"])
        if index < len(page_photos) - 1:
            st.divider()
    actions.render_bottom_review_handoff(anchor_id="journal-top", selected_count=review_selected_count, hike_id=None)


def render_journal_view(
    repository: HikeJournalRepository,
    storage: StorageService,
    inat_client: InatClient,
    selected_hike: dict[str, Any],
    photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    route_import: dict[str, Any] | None,
    known_species: list[dict[str, Any]],
    *,
    actions: JournalActions,
) -> None:
    st.markdown("<div id='journal-top'></div>", unsafe_allow_html=True)
    section_heading(
        "Outing workspace",
        "Details and photographs",
        "Update the route and field notes, add photographs, or continue through the outing record below.",
    )
    st.write("")

    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        hike_locations = fetch_hike_locations()
        location_options = location_library_options(hike_locations)
        with st.form("edit_hike_form"):
            title = st.text_input("Title", value=selected_hike.get("title", ""))
            hike_date = st.date_input("Date", value=actions._parse_date(selected_hike.get("hike_date")))
            distance_value = float(selected_hike.get("distance_miles") or 0.0)
            distance = st.number_input("Distance (miles)", min_value=0.0, step=0.5, value=distance_value)
            location_name = st.text_input("Location", value=selected_hike.get("location_name") or "")
            selected_locations = st.multiselect(
                "Location tags",
                options=location_options,
                default=selected_location_defaults(selected_hike),
                accept_new_options=True,
                placeholder="Start typing Bronson, Chuluota, Econ...",
            )
            notes = st.text_area("Hike notes", value=selected_hike.get("notes") or "", height=180)
            route_import_file = st.file_uploader(
                "MapMyRun TCX exports",
                type=TCX_IMPORT_TYPES,
                accept_multiple_files=True,
                help="Upload one or more TCX files to replace the outing route data here.",
            )
            use_imported_route_fields = st.checkbox("Use TCX date and distance for this outing", value=True)
            remove_route_import = st.checkbox("Remove the saved route import", value=False)
            if st.form_submit_button("Save hike details"):
                parsed_route_import, _, route_import_error = parse_uploaded_route_import(route_import_file)
                if route_import_error:
                    st.warning(route_import_error)
                    return
                target_hike_date = parsed_route_import.visited_on if parsed_route_import and use_imported_route_fields and parsed_route_import.visited_on else hike_date
                target_distance = parsed_route_import.distance_miles if parsed_route_import and use_imported_route_fields and parsed_route_import.distance_miles is not None else (distance or None)
                saved_location_name = location_name.strip() or ", ".join(selected_locations[:3])
                repository.update_hike(
                    selected_hike["id"],
                    title=title,
                    hike_date=target_hike_date,
                    distance_miles=target_distance,
                    location_name=saved_location_name,
                    notes=notes,
                )
                maybe_store_hike_location_tags(repository, selected_hike["id"], selected_locations, hike_locations)
                _, route_import_error = sync_hike_route_import(
                    repository=repository,
                    storage=storage,
                    hike_id=selected_hike["id"],
                    uploaded_file=route_import_file,
                    existing_route_import=route_import,
                    remove_existing=remove_route_import,
                )
                if route_import_error:
                    st.warning(route_import_error)
                invalidate_data_cache()
                st.success("Hike updated.")
                st.rerun()

        route_info_cols = st.columns([0.68, 0.32], gap="small")
        with route_info_cols[0]:
            st.markdown("##### Route import")
            if route_import:
                imported_pieces = []
                if route_import.get("distance_miles") is not None:
                    imported_pieces.append(f"{float(route_import['distance_miles']):.2f} mi")
                duration_label = format_duration_compact(route_import.get("duration_seconds"))
                if duration_label:
                    imported_pieces.append(duration_label)
                elevation_label = format_elevation_compact(route_import_meta(route_import).get("elevation_gain_feet"))
                if elevation_label:
                    imported_pieces.append(elevation_label)
                if route_import.get("track_point_count"):
                    imported_pieces.append(f"{int(route_import['track_point_count'])} GPS pts")
                source_line = " • ".join(imported_pieces) or "Imported route data"
                started_at_label = ""
                if route_import.get("started_at"):
                    try:
                        started_at_label = datetime.fromisoformat(str(route_import["started_at"]).replace("Z", "+00:00")).strftime("%b %d, %Y • %I:%M %p")
                    except ValueError:
                        started_at_label = str(route_import["started_at"])
                st.markdown(
                    f"""
                    <div class="journal-route-card">
                        <div class="journal-route-kicker">MapMyRun TCX attached</div>
                        <div class="journal-route-meta">{escape(source_line)}</div>
                        <div class="journal-route-file">{escape(route_import.get("source_file_name") or "Unnamed export")}</div>
                        {f"<div class='journal-route-file'>{escape(started_at_label)}</div>" if started_at_label else ""}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No route export attached yet. Add a TCX file to make the outing map follow the real track instead of just connecting photo points.")
    with right:
        st.markdown("##### Upload photos")
        st.caption("Photos are optimized on upload so the journal stays quick to browse.")
        if st.session_state.journal_upload_notice:
            st.success(str(st.session_state.journal_upload_notice))
            st.session_state.journal_upload_notice = None
        upload_widget_key = f"journal_upload_files_{selected_hike['id']}_{st.session_state.journal_upload_nonce}"
        with st.form("upload_photos_form", clear_on_submit=True):
            uploaded_files = st.file_uploader(
                "Drop in one or many trail photos",
                type=["jpg", "jpeg", "png", "webp", "heic"],
                accept_multiple_files=True,
                label_visibility="collapsed",
                key=upload_widget_key,
            )
            submitted = st.form_submit_button("Upload selected photos")
            if submitted:
                if not uploaded_files:
                    st.warning("Choose at least one photo to upload.")
                else:
                    geotagged_uploads = 0
                    timestamped_uploads = 0
                    total_uploads = len(uploaded_files)
                    upload_status = st.empty()
                    upload_progress = st.progress(0, text="Preparing photos for upload...")
                    with st.spinner("Optimizing and uploading photos..."):
                        for index, uploaded_file in enumerate(uploaded_files, start=1):
                            upload_status.caption(f"Uploading photo {index} of {total_uploads}")
                            original_bytes = uploaded_file.getvalue()
                            metadata = extract_metadata(original_bytes)
                            if metadata.lat is not None and metadata.lng is not None:
                                geotagged_uploads += 1
                            if metadata.taken_at is not None:
                                timestamped_uploads += 1
                            processed = optimize_image(original_bytes)
                            actions.persist_uploaded_photo(
                                repository=repository,
                                storage=storage,
                                processed_image=processed,
                                original_exif_json=metadata.exif_json,
                                lat=metadata.lat,
                                lng=metadata.lng,
                                taken_at=metadata.taken_at,
                                hike_id=selected_hike["id"],
                                owner_subject=photo_owner_subject(selected_hike, st.session_state.current_user_context),
                                owner_email=photo_owner_email(selected_hike, st.session_state.current_user_context),
                                caption=None,
                                processing_status="ready",
                            )
                            upload_progress.progress(index / total_uploads, text=f"Uploaded {index} of {total_uploads} photos")
                    invalidate_data_cache()
                    st.session_state.pop(upload_widget_key, None)
                    st.session_state.journal_upload_nonce += 1
                    st.session_state.journal_upload_notice = f"Uploaded {total_uploads} photo{'s' if total_uploads != 1 else ''}."
                    if geotagged_uploads == 0:
                        st.warning(
                            "These photos were added successfully, but none of them included embedded GPS coordinates. "
                            "If you want them to appear on the map, upload original files that still carry location data."
                        )
                    elif geotagged_uploads < len(uploaded_files):
                        st.caption(
                            f"{geotagged_uploads} of {len(uploaded_files)} photos included map coordinates. "
                            f"{timestamped_uploads} included capture times."
                        )
                    st.rerun()

    st.write("")
    if not photos:
        st.info("No photos yet. Upload a few trail photos to start this entry.")
        return

    review_selected_count = len([photo for photo in photos if photo.get("processing_status") == REVIEW_QUEUE_STATUS])
    actions.render_selection_toolbar(repository, photos, "journal")
    st.markdown("### Photo Field Notes")
    page_photos, total_pages = actions.paginate_photos(photos)
    actions.render_photo_management_toolbar(repository, storage, page_photos, photos, total_pages)
    actions.render_known_species_assignment_toolbar(
        repository,
        inat_client,
        page_photos,
        photos,
        primary_observation_by_photo,
        known_species,
        key_prefix=f"hike_{selected_hike['id']}",
    )
    for index, photo in enumerate(page_photos):
        primary_observation = primary_observation_by_photo.get(photo["id"])
        photo_observations = observations_by_photo.get(photo["id"], [])
        row_cols = st.columns([0.4, 0.6], gap="large")
        with row_cols[0]:
            render_clickable_photo(photo, selected_hike_id=selected_hike["id"])
        with row_cols[1]:
            st.markdown(
                f"<p class='photo-meta'>{format_photo_meta_html(photo, selected_hike_id=selected_hike['id'], link_coordinates=True, include_map_link=True)}</p>",
                unsafe_allow_html=True,
            )
            actions.render_photo_note_editor(repository, photo, key_prefix=f"journal_note_{photo['id']}")
            if primary_observation:
                is_confirmed = primary_observation.get("status") == "confirmed"
                actions.render_species_summary(
                    repository,
                    primary_observation,
                    inat_client=inat_client,
                    photo=photo,
                    place_guess=selected_hike.get("location_name"),
                    key_prefix=f"journal_{photo['id']}",
                    show_details=is_confirmed,
                    show_confidence=not is_confirmed,
                )
                actions.render_alternate_suggestions(repository, inat_client, primary_observation, photo, key_prefix=f"journal_{photo['id']}")
                actions.render_secondary_species_summary(photo_observations, primary_observation["id"])
            else:
                st.caption("No species attached to this photo yet.")
            actions.render_photo_species_actions(
                repository,
                inat_client,
                photo,
                photo_observations,
                primary_observation,
                known_species,
                hike_id=selected_hike.get("id"),
                key_prefix="journal",
            )
            if st.session_state.get("journal_cover_update_error"):
                st.error(st.session_state.pop("journal_cover_update_error"))
            control_cols = st.columns([0.4, 0.3, 0.3], gap="small")
            selected = photo.get("processing_status") == REVIEW_QUEUE_STATUS
            checkbox_key = f"photo_select_{photo['id']}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = selected
            with control_cols[0]:
                st.checkbox(
                    "Queue for review",
                    key=checkbox_key,
                    on_change=actions.sync_journal_review_checkbox,
                    args=(repository, photo["id"], checkbox_key),
                )
            with control_cols[1]:
                current_cover_photo_id = selected_hike.get("cover_photo_id")
                cover_checkbox_key = f"cover_photo_select_{photo['id']}"
                is_cover_photo = str(current_cover_photo_id or "") == str(photo["id"])
                st.session_state[cover_checkbox_key] = is_cover_photo
                st.checkbox(
                    "Cover photo",
                    key=cover_checkbox_key,
                    on_change=actions.sync_hike_cover_checkbox,
                    args=(repository, selected_hike["id"], photo["id"], cover_checkbox_key),
                )
            if not primary_observation:
                known_species_key = f"known_species_select_{photo['id']}"
                if known_species_key not in st.session_state:
                    st.session_state[known_species_key] = photo["id"] in st.session_state.known_species_selected_ids
                with control_cols[2]:
                    st.checkbox(
                        "Bulk select",
                        key=known_species_key,
                        on_change=actions.sync_known_species_checkbox,
                        args=(photo["id"], known_species_key),
                    )
            if st.session_state.delete_mode:
                delete_key = f"delete_photo_{photo['id']}"
                current_delete = photo["id"] in st.session_state.delete_photo_ids
                if delete_key not in st.session_state:
                    st.session_state[delete_key] = current_delete
                delete_toggle = st.checkbox("Mark to delete", key=delete_key)
                if delete_toggle:
                    st.session_state.delete_photo_ids.add(photo["id"])
                else:
                    st.session_state.delete_photo_ids.discard(photo["id"])
        if index < len(page_photos) - 1:
            st.divider()
    actions.render_bottom_review_handoff(anchor_id="journal-top", selected_count=review_selected_count, hike_id=str(selected_hike["id"]))
