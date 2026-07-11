from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from hike_journal.config import settings
from hike_journal.domain.library import (
    count_unique_species,
    filter_standalone_observations,
    filter_standalone_photos,
    filter_hikes_for_user,
    group_records_by_key,
    record_visible_for_user,
    standalone_journal_is_active,
)
from hike_journal.domain.locations import attach_location_tags_to_hikes
from hike_journal.domain.routes import annotate_photos_with_route_context, compute_total_mileage
from hike_journal.queries import (
    fetch_all_hike_route_imports,
    fetch_all_lightweight_observations,
    fetch_all_map_photos,
    fetch_confirmed_observation_hike_refs,
    fetch_confirmed_observations_light,
    fetch_hike_lightweight_observations,
    fetch_hike_location_tags,
    fetch_hike_locations,
    fetch_hike_map_photos,
    fetch_hike_observations,
    fetch_hike_photos,
    fetch_hike_route_import,
    fetch_hikes,
    fetch_observations_for_photo_ids,
    fetch_photo_hike_refs,
    fetch_photo_records_for_ids,
    fetch_review_queue_photos,
    fetch_standalone_photos,
)
from hike_journal.services.inat import InatClient
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.species_identification import build_known_species_catalog
from hike_journal.services.storage import StorageService
from hike_journal.services.supabase_client import get_supabase
from hike_journal.ui.components import render_hero


@dataclass(frozen=True)
class ApplicationActions:
    build_species_log_context: Any
    dedupe_records_by_id: Any
    get_inat_access_token_for_context: Any
    get_primary_observation: Any
    get_user_context: Any
    group_observations_by_photo: Any
    maybe_handle_inat_oauth_callback: Any
    maybe_migrate_legacy_inat_token: Any
    render_access_denied: Any
    render_auth_configuration_state: Any
    render_empty_state: Any
    render_footer: Any
    render_inat_token_dialog: Any
    render_journal_tab: Any
    render_library_tab: Any
    render_login_gate: Any
    render_map_tab: Any
    render_mobile_shell: Any
    render_photo_viewer: Any
    render_setup_state: Any
    render_sidebar: Any
    render_species_log_tab: Any
    render_species_tab: Any
    render_standalone_journal_tab: Any
    sync_pagination_state_from_query_params: Any
    sync_viewer_from_query_params: Any


def run_application(actions: ApplicationActions) -> None:
    user_context = actions.get_user_context()
    st.session_state.current_user_context = user_context
    actions.maybe_handle_inat_oauth_callback(user_context)

    if settings.require_google_auth and not user_context["auth_configured"]:
        actions.render_auth_configuration_state()
        return

    if settings.require_google_auth and not user_context["is_logged_in"]:
        actions.render_login_gate()
        return

    if settings.require_google_auth and user_context["mode"] == "google" and not user_context["is_allowed"]:
        actions.render_access_denied(user_context)
        return

    if not settings.supabase_configured:
        actions.render_setup_state()
        return

    supabase = get_supabase()
    repository = HikeJournalRepository(supabase)
    storage = StorageService(supabase)
    inat_access_token = actions.get_inat_access_token_for_context(user_context)
    inat_client = InatClient(access_token=inat_access_token)
    actions.sync_pagination_state_from_query_params()
    actions.maybe_migrate_legacy_inat_token(user_context)

    if user_context["mode"] == "google" and user_context["is_admin"]:
        try:
            repository.claim_unowned_hikes(
                owner_subject=user_context.get("subject"),
                owner_email=user_context.get("email"),
            )
        except Exception:
            pass

    try:
        hikes = fetch_hikes()
    except Exception as exc:  # pragma: no cover - depends on remote project state
        actions.render_setup_state(reason=str(exc))
        return

    hike_locations = fetch_hike_locations()
    hike_location_tags = fetch_hike_location_tags()
    hikes = attach_location_tags_to_hikes(hikes, hike_locations, hike_location_tags)
    visible_hikes = filter_hikes_for_user(hikes, user_context)
    view_options = ["Library", "Journal", "Species Review", "Map", "Species Log"]

    query_hike_id = st.query_params.get("hike")
    query_photo_id = st.query_params.get("photo")
    requested_view = st.query_params.get("view")
    requested_scope = st.query_params.get("scope")
    top_level_views = {"Library", "Species Review", "Map", "Species Log"}
    if requested_view in view_options:
        st.session_state.active_view = str(requested_view)
        st.session_state.pending_view = str(requested_view)
    if requested_scope == "global":
        st.session_state.selected_hike_id = None
    elif query_hike_id:
        st.session_state.selected_hike_id = str(query_hike_id)

    if st.session_state.selected_hike_id and not any(hike["id"] == st.session_state.selected_hike_id for hike in visible_hikes):
        st.session_state.selected_hike_id = None

    visible_hike_ids = {hike["id"] for hike in visible_hikes}
    if query_photo_id:
        linked_photos = fetch_photo_records_for_ids((str(query_photo_id),))
        linked_photo = next(
            (
                photo
                for photo in linked_photos
                if photo.get("id") == str(query_photo_id)
                and record_visible_for_user(photo, visible_hike_ids, user_context)
            ),
            None,
        )
        current_view_hint = requested_view if requested_view in view_options else st.session_state.active_view
        if linked_photo and linked_photo.get("hike_id") and current_view_hint not in top_level_views and not query_hike_id:
            st.session_state.selected_hike_id = linked_photo["hike_id"]
            st.query_params["hike"] = linked_photo["hike_id"]

    if st.session_state.pending_view in view_options:
        st.session_state.active_view = st.session_state.pending_view
        st.session_state.pending_view = None
    if st.session_state.active_view not in view_options:
        st.session_state.active_view = "Library"

    selected_hike = next((hike for hike in visible_hikes if hike["id"] == st.session_state.selected_hike_id), None)
    standalone_journal_active = standalone_journal_is_active(
        active_view=st.session_state.active_view,
        requested_scope=requested_scope,
        selected_hike=selected_hike,
    )

    with st.sidebar:
        actions.render_sidebar(repository, storage, visible_hikes, user_context, st.session_state.active_view)

    actions.render_mobile_shell(visible_hikes, st.session_state.active_view)

    route_imports_by_hike: dict[str, dict[str, Any]] = {}
    if st.session_state.active_view in {"Map", "Species Log"} and visible_hikes:
        route_import_records = fetch_all_hike_route_imports()
        route_imports_by_hike = {
            str(item["hike_id"]): item
            for item in route_import_records
            if item.get("hike_id") and str(item.get("hike_id")) in visible_hike_ids
        }

    photos: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    route_import: dict[str, Any] | None = None
    all_visible_photos: list[dict[str, Any]] = []
    all_visible_observations: list[dict[str, Any]] = []
    confirmed_visible_observations: list[dict[str, Any]] = []
    library_photo_refs: list[dict[str, Any]] = []
    library_confirmed_refs: list[dict[str, Any]] = []
    library_cover_photos: dict[str, dict[str, Any]] = {}
    species_log_context: dict[str, Any] | None = None

    if st.session_state.active_view == "Journal" and selected_hike:
        photos = fetch_hike_photos(selected_hike["id"])
        observations = fetch_hike_observations(selected_hike["id"])
        route_import = fetch_hike_route_import(selected_hike["id"])
        annotate_photos_with_route_context(
            photos,
            route_import=route_import,
            hike_distance_miles=selected_hike.get("distance_miles"),
        )
    elif standalone_journal_active:
        photos = filter_standalone_photos(
            fetch_standalone_photos(),
            visible_hike_ids,
            user_context,
        )
        standalone_photo_ids = tuple(photo["id"] for photo in photos if photo.get("id"))
        all_visible_observations = filter_standalone_observations(
            fetch_observations_for_photo_ids(standalone_photo_ids) if standalone_photo_ids else [],
            visible_hike_ids,
            user_context,
        )
        observations = all_visible_observations

    if st.session_state.active_view in top_level_views:
        library_photo_refs = [record for record in fetch_photo_hike_refs() if record_visible_for_user(record, visible_hike_ids, user_context)]
        library_confirmed_refs = [
            record for record in fetch_confirmed_observation_hike_refs() if record_visible_for_user(record, visible_hike_ids, user_context)
        ]
        if st.session_state.active_view == "Library":
            cover_photo_ids = tuple(
                {
                    str(hike.get("cover_photo_id"))
                    for hike in visible_hikes
                    if hike.get("cover_photo_id")
                }
            )
            if cover_photo_ids:
                library_cover_photos = {
                    photo["id"]: photo
                    for photo in fetch_photo_records_for_ids(cover_photo_ids)
                }

    if st.session_state.active_view == "Map":
        if selected_hike:
            photos = fetch_hike_map_photos(selected_hike["id"])
            route_import = fetch_hike_route_import(selected_hike["id"])
            annotate_photos_with_route_context(
                photos,
                route_import=route_import,
                hike_distance_miles=selected_hike.get("distance_miles"),
            )
            if photos:
                observations = fetch_hike_lightweight_observations(selected_hike["id"])
        else:
            all_visible_photos = fetch_all_map_photos() if visible_hikes else []
            all_visible_photos = [photo for photo in all_visible_photos if record_visible_for_user(photo, visible_hike_ids, user_context)]
            for hike_id, grouped_photos in group_records_by_key(all_visible_photos, "hike_id").items():
                annotate_photos_with_route_context(
                    grouped_photos,
                    route_import=route_imports_by_hike.get(str(hike_id)),
                    hike_distance_miles=next((hike.get("distance_miles") for hike in visible_hikes if hike["id"] == hike_id), None),
                )
            all_visible_observations = fetch_all_lightweight_observations() if visible_hikes else []
            all_visible_observations = [
                observation for observation in all_visible_observations if record_visible_for_user(observation, visible_hike_ids, user_context)
            ]
            confirmed_visible_observations = [
                observation
                for observation in fetch_confirmed_observations_light()
                if record_visible_for_user(observation, visible_hike_ids, user_context)
            ]

    if st.session_state.active_view == "Species Log":
        confirmed_visible_observations = [
            observation
            for observation in fetch_confirmed_observations_light()
            if record_visible_for_user(observation, visible_hike_ids, user_context)
        ]
        species_log_photo_ids = tuple(
            {
                observation["photo_id"]
                for observation in confirmed_visible_observations
                if observation.get("photo_id")
            }
        )
        all_visible_photos = fetch_photo_records_for_ids(species_log_photo_ids) if species_log_photo_ids else []
        species_log_context = actions.build_species_log_context(
            hikes=visible_hikes,
            confirmed_observations=confirmed_visible_observations,
            photos=all_visible_photos,
            inat_client=inat_client,
        )
        all_visible_photos = species_log_context["viewer_photos"]
        for hike_id, grouped_photos in group_records_by_key(all_visible_photos, "hike_id").items():
            annotate_photos_with_route_context(
                grouped_photos,
                route_import=route_imports_by_hike.get(str(hike_id)),
                hike_distance_miles=next((hike.get("distance_miles") for hike in visible_hikes if hike["id"] == hike_id), None),
            )
        all_visible_observations = species_log_context["viewer_observations"]

    review_queue_photos: list[dict[str, Any]] = []
    publish_confirmed_observations: list[dict[str, Any]] = []
    publish_photos: list[dict[str, Any]] = []

    observations_by_photo = actions.group_observations_by_photo(observations)
    primary_observation_by_photo = {
        photo_id: actions.get_primary_observation(photo_observations)
        for photo_id, photo_observations in observations_by_photo.items()
    }
    if st.session_state.active_view == "Species Review":
        review_queue_photos = fetch_review_queue_photos() if visible_hikes else []
        review_queue_photos = [photo for photo in review_queue_photos if record_visible_for_user(photo, visible_hike_ids, user_context)]
        publish_confirmed_observations = [
            observation
            for observation in fetch_confirmed_observations_light()
            if record_visible_for_user(observation, visible_hike_ids, user_context)
        ]
        review_photo_ids = tuple(photo["id"] for photo in review_queue_photos)
        publish_photo_ids = tuple(
            {
                str(observation["photo_id"])
                for observation in publish_confirmed_observations
                if observation.get("photo_id")
            }
        )
        publish_photos = fetch_photo_records_for_ids(publish_photo_ids) if publish_photo_ids else []
        all_visible_photos = actions.dedupe_records_by_id(review_queue_photos + publish_photos)
        review_observations = fetch_observations_for_photo_ids(review_photo_ids) if review_photo_ids else []
        all_visible_observations = actions.dedupe_records_by_id(review_observations + publish_confirmed_observations)
        confirmed_visible_observations = [
            observation for observation in all_visible_observations if observation.get("status") == "confirmed"
        ]
    all_visible_observations_by_photo = actions.group_observations_by_photo(all_visible_observations)
    all_visible_primary_observation_by_photo = {
        photo_id: actions.get_primary_observation(photo_observations)
        for photo_id, photo_observations in all_visible_observations_by_photo.items()
    }
    if st.session_state.active_view == "Species Review":
        review_queue_photos = sorted(
            review_queue_photos,
            key=lambda photo: (
                0 if not all_visible_primary_observation_by_photo.get(photo["id"]) else 1,
                0 if (all_visible_primary_observation_by_photo.get(photo["id"]) or {}).get("status") == "pending" else 1,
                photo.get("taken_at") or "",
                photo.get("created_at") or "",
            ),
        )
    confirmed_count = len([item for item in observations if item.get("status") == "confirmed"])
    visible_confirmed_observations = [
        observation
        for observation in fetch_confirmed_observations_light()
        if record_visible_for_user(observation, visible_hike_ids, user_context)
    ] if visible_hikes else []
    known_species_catalog = build_known_species_catalog(visible_confirmed_observations)
    visible_unique_species_count = count_unique_species(visible_confirmed_observations)
    total_logged_miles = compute_total_mileage(visible_hikes)

    viewer_photos: list[dict[str, Any]]
    viewer_observations_by_photo: dict[str, list[dict[str, Any]]]
    viewer_primary_observation_by_photo: dict[str, dict[str, Any]]
    if st.session_state.active_view == "Journal":
        viewer_photos = photos
        viewer_observations_by_photo = observations_by_photo
        viewer_primary_observation_by_photo = primary_observation_by_photo
    elif st.session_state.active_view == "Species Review":
        viewer_photos = all_visible_photos
        viewer_observations_by_photo = all_visible_observations_by_photo
        viewer_primary_observation_by_photo = all_visible_primary_observation_by_photo
    elif st.session_state.active_view in {"Map", "Species Log"}:
        viewer_photos = all_visible_photos
        viewer_observations_by_photo = all_visible_observations_by_photo
        viewer_primary_observation_by_photo = all_visible_primary_observation_by_photo
    else:
        viewer_photos = photos
        viewer_observations_by_photo = observations_by_photo
        viewer_primary_observation_by_photo = primary_observation_by_photo

    actions.sync_viewer_from_query_params(viewer_photos)

    if st.session_state.active_view == "Journal" and selected_hike:
        cover_photo = next(
            (photo for photo in photos if str(photo.get("id")) == str(selected_hike.get("cover_photo_id") or "")),
            photos[0] if photos else None,
        )
        render_hero(
            selected_hike,
            len(visible_hikes),
            len(photos),
            count_unique_species([item for item in observations if item.get("status") == "confirmed"]),
            route_import=route_import,
            total_miles=total_logged_miles,
            cover_photo_url=str(cover_photo.get("public_url")) if cover_photo and cover_photo.get("public_url") else None,
        )
        st.write("")

    if not selected_hike and not standalone_journal_active and st.session_state.active_view not in top_level_views:
        actions.render_empty_state()
        return

    if st.session_state.active_view == "Library":
        actions.render_library_tab(
            repository,
            storage,
            visible_hikes,
            library_photo_refs,
            visible_confirmed_observations,
            library_cover_photos,
            user_context,
        )
    elif st.session_state.active_view == "Journal":
        if standalone_journal_active:
            actions.render_standalone_journal_tab(
                repository,
                storage,
                inat_client,
                photos,
                observations_by_photo,
                primary_observation_by_photo,
                user_context,
                known_species_catalog,
            )
        else:
            actions.render_journal_tab(
                repository,
                storage,
                inat_client,
                selected_hike,
                photos,
                observations_by_photo,
                primary_observation_by_photo,
                route_import,
                known_species_catalog,
            )
    elif st.session_state.active_view == "Species Review":
        actions.render_species_tab(
            repository,
            inat_client,
            visible_hikes,
            review_queue_photos,
            publish_confirmed_observations,
            publish_photos,
            all_visible_observations_by_photo,
            all_visible_primary_observation_by_photo,
        )
    elif st.session_state.active_view == "Map":
        if selected_hike:
            actions.render_map_tab(
                photos,
                observations_by_photo,
                primary_observation_by_photo,
                selected_hike=selected_hike,
                route_imports_by_hike={selected_hike["id"]: route_import} if selected_hike and route_import else {},
            )
        else:
            actions.render_map_tab(
                all_visible_photos,
                all_visible_observations_by_photo,
                all_visible_primary_observation_by_photo,
                selected_hike=None,
                route_imports_by_hike=route_imports_by_hike,
            )
    elif st.session_state.active_view == "Species Log":
        actions.render_species_log_tab(
            repository,
            inat_client,
            visible_hikes,
            species_log_context or {},
        )

    if st.session_state.inat_token_dialog_open:
        actions.render_inat_token_dialog(inat_client, user_context)
    elif st.session_state.viewer_open:
        st.session_state.viewer_open = False
        actions.render_photo_viewer(
            repository,
            inat_client,
            viewer_photos,
            viewer_observations_by_photo,
            viewer_primary_observation_by_photo,
        )

    actions.render_footer()
