from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from html import escape
import math
import secrets
from typing import Any
from urllib.parse import quote, urlencode

import streamlit as st
import streamlit.components.v1 as components

from hike_journal.config import (
    build_inat_token_identity,
    delete_inat_token_record_for_user,
    load_inat_access_token_for_user,
    load_inat_token_record_for_user,
    settings,
)
from hike_journal.models import HikeDraft, SpeciesCandidate
from hike_journal.services.exif import extract_metadata
from hike_journal.services.image_processing import optimize_image
from hike_journal.services.inat import (
    InatAuthError,
    InatClient,
    InatComputerVisionBlockedError,
    InatConfigurationError,
    InatRequestError,
    InatRateLimitError,
    build_observation_sync_candidate,
    build_oauth_authorize_url,
    exchange_oauth_code,
    normalize_access_token,
    parse_candidates,
    persist_access_token,
    persist_access_token_for_user,
    resolve_access_token_for_user,
    save_oauth_token_payload_for_user,
)
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.storage import StorageService
from hike_journal.services.supabase_client import get_supabase
from hike_journal.services.tcx import (
    ParsedTcxRouteImport,
    TcxParseError,
    estimate_elevation_meta_from_track_geojson,
    parse_tcx_bytes,
)
from hike_journal.ui.components import (
    format_photo_meta,
    format_photo_meta_html,
    get_photo_thumbnail_url,
    render_clickable_photo,
    render_clickable_photo_with_view,
    render_hero,
    render_library_cover,
    render_observation_badge,
    render_rich_map,
    section_heading,
)
from hike_journal.ui.theme import apply_theme


st.set_page_config(page_title="HikeJournal", page_icon="🥾", layout="wide")
apply_theme()
REVIEW_QUEUE_STATUS = "in_review"
TCX_IMPORT_TYPES = ["tcx", "xml"]
GROUPED_ID_MAX_PHOTOS = 8


if "selected_hike_id" not in st.session_state:
    st.session_state.selected_hike_id = None
if "viewer_open" not in st.session_state:
    st.session_state.viewer_open = False
if "viewer_index" not in st.session_state:
    st.session_state.viewer_index = 0
if "journal_page" not in st.session_state:
    st.session_state.journal_page = 1
if "journal_page_size" not in st.session_state:
    st.session_state.journal_page_size = 9
if "species_page" not in st.session_state:
    st.session_state.species_page = 1
if "species_page_size" not in st.session_state:
    st.session_state.species_page_size = 6
if "species_selected_ids" not in st.session_state:
    st.session_state.species_selected_ids = set()
if "species_review_filter" not in st.session_state:
    st.session_state.species_review_filter = "All"
if "species_review_stage" not in st.session_state:
    st.session_state.species_review_stage = "All"
if "species_review_stage_signature" not in st.session_state:
    st.session_state.species_review_stage_signature = ()
if "species_review_stage_selection_signature" not in st.session_state:
    st.session_state.species_review_stage_selection_signature = ()
if "species_review_mode" not in st.session_state:
    st.session_state.species_review_mode = "Review"
if "delete_photo_ids" not in st.session_state:
    st.session_state.delete_photo_ids = set()
if "delete_mode" not in st.session_state:
    st.session_state.delete_mode = False
if "active_view" not in st.session_state:
    st.session_state.active_view = "Library"
if "active_view_picker" not in st.session_state:
    st.session_state.active_view_picker = "Library"
if "pending_view" not in st.session_state:
    st.session_state.pending_view = None
if "query_state_signature" not in st.session_state:
    st.session_state.query_state_signature = None
if "inat_auth_error" not in st.session_state:
    st.session_state.inat_auth_error = None
if "inat_auth_notice" not in st.session_state:
    st.session_state.inat_auth_notice = None
if "inat_token_input" not in st.session_state:
    st.session_state.inat_token_input = ""
if "inat_oauth_state" not in st.session_state:
    st.session_state.inat_oauth_state = None
if "inat_token_dialog_open" not in st.session_state:
    st.session_state.inat_token_dialog_open = False
if "species_log_hike_filter" not in st.session_state:
    st.session_state.species_log_hike_filter = "All hikes"
if "species_log_mapped_only" not in st.session_state:
    st.session_state.species_log_mapped_only = False
if "species_log_include_secondary" not in st.session_state:
    st.session_state.species_log_include_secondary = True
if "species_log_sort" not in st.session_state:
    st.session_state.species_log_sort = "Most recent"
if "species_log_posted_filter" not in st.session_state:
    st.session_state.species_log_posted_filter = "All"
if "species_log_page" not in st.session_state:
    st.session_state.species_log_page = 1
if "journal_upload_nonce" not in st.session_state:
    st.session_state.journal_upload_nonce = 0
if "quick_upload_nonce" not in st.session_state:
    st.session_state.quick_upload_nonce = 0
if "journal_upload_notice" not in st.session_state:
    st.session_state.journal_upload_notice = None
if "quick_upload_notice" not in st.session_state:
    st.session_state.quick_upload_notice = None
if "species_log_page_size" not in st.session_state:
    st.session_state.species_log_page_size = 8
if "species_log_focus_key" not in st.session_state:
    st.session_state.species_log_focus_key = None
if "species_log_record_open" not in st.session_state:
    st.session_state.species_log_record_open = False
if "species_review_initialized_signature" not in st.session_state:
    st.session_state.species_review_initialized_signature = None
if "inat_post_feedback" not in st.session_state:
    st.session_state.inat_post_feedback = {}
if "inat_sync_candidates" not in st.session_state:
    st.session_state.inat_sync_candidates = {}
if "inat_sync_selected_ids" not in st.session_state:
    st.session_state.inat_sync_selected_ids = set()
if "inat_sync_checked_count" not in st.session_state:
    st.session_state.inat_sync_checked_count = 0
if "inat_sync_error" not in st.session_state:
    st.session_state.inat_sync_error = None
if "inat_sync_notice" not in st.session_state:
    st.session_state.inat_sync_notice = None
if "viewer_notice" not in st.session_state:
    st.session_state.viewer_notice = None
if "library_group_by" not in st.session_state:
    st.session_state.library_group_by = "Month"
if "library_page" not in st.session_state:
    st.session_state.library_page = 1
if "library_page_size" not in st.session_state:
    st.session_state.library_page_size = 8
if "publish_filter" not in st.session_state:
    st.session_state.publish_filter = "Ready to post"
if "publish_selected_ids" not in st.session_state:
    st.session_state.publish_selected_ids = set()
if "publish_page" not in st.session_state:
    st.session_state.publish_page = 1
if "publish_page_size" not in st.session_state:
    st.session_state.publish_page_size = 8


def get_inat_access_token_for_context(user_context: dict[str, Any]) -> str:
    if user_context.get("mode") == "google":
        try:
            return resolve_access_token_for_user(
                subject=user_context.get("subject"),
                email=user_context.get("email"),
            ) or load_inat_access_token_for_user(
                subject=user_context.get("subject"),
                email=user_context.get("email"),
                env_fallback="",
            )
        except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
            st.session_state.inat_auth_notice = None
            st.session_state.inat_auth_error = str(exc)
            return ""
    return settings.inat_access_token


def maybe_migrate_legacy_inat_token(user_context: dict[str, Any]) -> None:
    if user_context.get("mode") != "google":
        return
    identity = build_inat_token_identity(user_context.get("subject"), user_context.get("email"))
    if not identity or st.session_state.get("inat_legacy_migrated_for") == identity:
        return
    user_token = load_inat_access_token_for_user(
        subject=user_context.get("subject"),
        email=user_context.get("email"),
        env_fallback="",
    )
    if user_token:
        st.session_state.inat_legacy_migrated_for = identity
        return
    legacy_token = settings.inat_access_token_env.strip() or ""
    global_runtime_token = settings.inat_access_token
    token_to_migrate = global_runtime_token or legacy_token
    if token_to_migrate and user_context.get("is_admin"):
        persist_access_token_for_user(
            token_to_migrate,
            subject=user_context.get("subject"),
            email=user_context.get("email"),
        )
    st.session_state.inat_legacy_migrated_for = identity


def maybe_handle_inat_oauth_callback(user_context: dict[str, Any]) -> None:
    query_code = st.query_params.get("code")
    query_state = st.query_params.get("state")
    query_error = st.query_params.get("error")
    if not query_state or not str(query_state).startswith("inat:"):
        return
    if query_error:
        st.session_state.inat_auth_notice = None
        st.session_state.inat_auth_error = f"iNaturalist sign-in did not complete: {query_error}"
        for key in ["code", "state", "error"]:
            if key in st.query_params:
                del st.query_params[key]
        st.rerun()
    if not query_code:
        return
    if user_context.get("mode") != "google":
        st.session_state.inat_auth_notice = None
        st.session_state.inat_auth_error = "Sign in to HikeJournal with Google before connecting iNaturalist."
        for key in ["code", "state"]:
            if key in st.query_params:
                del st.query_params[key]
        st.rerun()
    expected_state = st.session_state.get("inat_oauth_state")
    if expected_state and str(query_state) != str(expected_state):
        st.session_state.inat_auth_notice = None
        st.session_state.inat_auth_error = "The iNaturalist OAuth state did not match. Please try connecting again."
        for key in ["code", "state"]:
            if key in st.query_params:
                del st.query_params[key]
        st.rerun()
    try:
        token_payload = exchange_oauth_code(code=str(query_code))
        save_oauth_token_payload_for_user(
            token_payload,
            subject=user_context.get("subject"),
            email=user_context.get("email"),
        )
    except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
        st.session_state.inat_auth_notice = None
        st.session_state.inat_auth_error = str(exc)
        for key in ["code", "state"]:
            if key in st.query_params:
                del st.query_params[key]
        st.rerun()
    st.session_state.inat_oauth_state = None
    st.session_state.inat_auth_error = None
    st.session_state.inat_auth_notice = "Connected your iNaturalist account."
    for key in ["code", "state"]:
        if key in st.query_params:
            del st.query_params[key]
    st.rerun()


def main() -> None:
    user_context = get_user_context()
    st.session_state.current_user_context = user_context
    maybe_handle_inat_oauth_callback(user_context)

    if settings.require_google_auth and not user_context["auth_configured"]:
        render_auth_configuration_state()
        return

    if settings.require_google_auth and not user_context["is_logged_in"]:
        render_login_gate()
        return

    if settings.require_google_auth and user_context["mode"] == "google" and not user_context["is_allowed"]:
        render_access_denied(user_context)
        return

    if not settings.supabase_configured:
        render_setup_state()
        return

    supabase = get_supabase()
    repository = HikeJournalRepository(supabase)
    storage = StorageService(supabase)
    inat_access_token = get_inat_access_token_for_context(user_context)
    inat_client = InatClient(access_token=inat_access_token)
    sync_pagination_state_from_query_params()
    maybe_migrate_legacy_inat_token(user_context)

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
        render_setup_state(reason=str(exc))
        return

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
    standalone_journal_active = (
        st.session_state.active_view == "Journal"
        and requested_scope == "standalone"
        and selected_hike is None
    )

    with st.sidebar:
        render_sidebar(repository, storage, visible_hikes, user_context, st.session_state.active_view)

    render_mobile_shell(visible_hikes, st.session_state.active_view)

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
        photos = [
            photo
            for photo in fetch_standalone_photos()
            if record_visible_for_user(photo, visible_hike_ids, user_context)
        ]
        standalone_photo_ids = tuple(photo["id"] for photo in photos if photo.get("id"))
        all_visible_observations = [
            observation
            for observation in (fetch_observations_for_photo_ids(standalone_photo_ids) if standalone_photo_ids else [])
            if record_visible_for_user(observation, visible_hike_ids, user_context)
            and not observation.get("hike_id")
        ]
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
        species_log_context = build_species_log_context(
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

    observations_by_photo = group_observations_by_photo(observations)
    primary_observation_by_photo = {
        photo_id: get_primary_observation(photo_observations)
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
        all_visible_photos = dedupe_records_by_id(review_queue_photos + publish_photos)
        review_observations = fetch_observations_for_photo_ids(review_photo_ids) if review_photo_ids else []
        all_visible_observations = dedupe_records_by_id(review_observations + publish_confirmed_observations)
        confirmed_visible_observations = [
            observation for observation in all_visible_observations if observation.get("status") == "confirmed"
        ]
    all_visible_observations_by_photo = group_observations_by_photo(all_visible_observations)
    all_visible_primary_observation_by_photo = {
        photo_id: get_primary_observation(photo_observations)
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

    sync_viewer_from_query_params(viewer_photos)

    hero_hike = selected_hike if st.session_state.active_view in {"Journal", "Map"} else None
    if standalone_journal_active:
        hero_photo_count = len(photos)
        hero_confirmed_count = count_unique_species([item for item in observations if item.get("status") == "confirmed"])
    else:
        hero_photo_count = len(photos) if hero_hike else (
            len(library_photo_refs) if st.session_state.active_view == "Library" else len(all_visible_photos)
        )
        hero_confirmed_count = count_unique_species([item for item in observations if item.get("status") == "confirmed"]) if hero_hike else (
            visible_unique_species_count if st.session_state.active_view == "Library" else count_unique_species(confirmed_visible_observations)
        )
    render_hero(
        hero_hike,
        len(visible_hikes),
        hero_photo_count,
        hero_confirmed_count,
        route_import=route_import if hero_hike else None,
        total_miles=total_logged_miles,
    )
    st.write("")

    if not selected_hike and not standalone_journal_active and st.session_state.active_view not in top_level_views:
        render_empty_state()
        return

    if st.session_state.active_view == "Library":
        render_library_tab(
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
            render_standalone_journal_tab(
                repository,
                storage,
                inat_client,
                photos,
                observations_by_photo,
                primary_observation_by_photo,
                user_context,
            )
        else:
            render_journal_tab(repository, storage, inat_client, selected_hike, photos, observations_by_photo, primary_observation_by_photo, route_import)
    elif st.session_state.active_view == "Species Review":
        render_species_tab(
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
            render_map_tab(
                photos,
                observations_by_photo,
                primary_observation_by_photo,
                selected_hike=selected_hike,
                route_imports_by_hike={selected_hike["id"]: route_import} if selected_hike and route_import else {},
            )
        else:
            render_map_tab(
                all_visible_photos,
                all_visible_observations_by_photo,
                all_visible_primary_observation_by_photo,
                selected_hike=None,
                route_imports_by_hike=route_imports_by_hike,
            )
    elif st.session_state.active_view == "Species Log":
        render_species_log_tab(
            repository,
            inat_client,
            visible_hikes,
            species_log_context or {},
        )

    if st.session_state.inat_token_dialog_open:
        render_inat_token_dialog(inat_client, user_context)
    elif st.session_state.viewer_open:
        st.session_state.viewer_open = False
        render_photo_viewer(
            repository,
            inat_client,
            viewer_photos,
            viewer_observations_by_photo,
            viewer_primary_observation_by_photo,
        )

    render_footer()


@st.cache_data(show_spinner=False)
def fetch_hikes() -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_hikes()


@st.cache_data(show_spinner=False)
def fetch_hike_route_import(hike_id: str) -> dict[str, Any] | None:
    return HikeJournalRepository(get_supabase()).get_hike_route_import(hike_id)


@st.cache_data(show_spinner=False)
def fetch_all_hike_route_imports() -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_hike_route_imports()


@st.cache_data(show_spinner=False)
def fetch_hike_photos(hike_id: str) -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_photos(hike_id)


@st.cache_data(show_spinner=False)
def fetch_all_photos() -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_all_photos()


@st.cache_data(show_spinner=False)
def fetch_standalone_photos() -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_standalone_photos()


@st.cache_data(show_spinner=False)
def fetch_hike_map_photos(hike_id: str) -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_map_photos(hike_id)


@st.cache_data(show_spinner=False)
def fetch_all_map_photos() -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_map_photos()


@st.cache_data(show_spinner=False)
def fetch_review_queue_photos() -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_review_queue_photos()


@st.cache_data(show_spinner=False)
def fetch_photo_hike_refs() -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_photo_hike_refs()


@st.cache_data(show_spinner=False)
def fetch_photo_storage_records() -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_photo_storage_records()


@st.cache_data(show_spinner=False)
def fetch_hike_observations(hike_id: str) -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_observations(hike_id)


@st.cache_data(show_spinner=False)
def fetch_hike_lightweight_observations(hike_id: str) -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_lightweight_observations(hike_id=hike_id)


@st.cache_data(show_spinner=False)
def fetch_all_lightweight_observations() -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_lightweight_observations()


@st.cache_data(show_spinner=False)
def fetch_lightweight_observations_for_photo_ids(photo_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_lightweight_observations(photo_ids=list(photo_ids))


@st.cache_data(show_spinner=False)
def fetch_confirmed_observations_light() -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_lightweight_observations(status="confirmed")


@st.cache_data(show_spinner=False)
def fetch_photo_records_for_ids(photo_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_photo_records_for_ids(list(photo_ids))


@st.cache_data(show_spinner=False)
def fetch_observations_by_ids(observation_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_observations_by_ids(list(observation_ids))


@st.cache_data(show_spinner=False)
def fetch_observations_for_photo_ids(photo_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_observations_for_photo_ids(list(photo_ids))


@st.cache_data(show_spinner=False)
def fetch_confirmed_observation_hike_refs() -> list[dict[str, Any]]:
    return HikeJournalRepository(get_supabase()).list_confirmed_observation_hike_refs()


def invalidate_data_cache() -> None:
    fetch_hikes.clear()
    fetch_hike_route_import.clear()
    fetch_all_hike_route_imports.clear()
    fetch_hike_photos.clear()
    fetch_all_photos.clear()
    fetch_hike_map_photos.clear()
    fetch_all_map_photos.clear()
    fetch_review_queue_photos.clear()
    fetch_photo_hike_refs.clear()
    fetch_photo_storage_records.clear()
    fetch_hike_observations.clear()
    fetch_hike_lightweight_observations.clear()
    fetch_all_lightweight_observations.clear()
    fetch_lightweight_observations_for_photo_ids.clear()
    fetch_confirmed_observations_light.clear()
    fetch_photo_records_for_ids.clear()
    fetch_observations_by_ids.clear()
    fetch_observations_for_photo_ids.clear()
    fetch_confirmed_observation_hike_refs.clear()


def format_duration_compact(value: int | float | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        total_seconds = max(0, int(round(float(value))))
    except (TypeError, ValueError):
        return None
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
    return f"{seconds}s"


def format_total_miles(value: float | int | None) -> str:
    if value in (None, ""):
        return "0 mi logged"
    try:
        miles = float(value)
    except (TypeError, ValueError):
        return "0 mi logged"
    if miles >= 100:
        return f"{miles:,.0f} mi logged"
    return f"{miles:,.1f} mi logged"


def route_import_meta(route_import: dict[str, Any] | None) -> dict[str, Any]:
    if not route_import:
        return {}
    track_geojson = route_import.get("track_geojson") or {}
    if not isinstance(track_geojson, dict):
        return {}
    meta = track_geojson.get("meta") or {}
    stored_meta = meta if isinstance(meta, dict) else {}
    computed_meta = estimate_elevation_meta_from_track_geojson(track_geojson)
    if not computed_meta:
        return stored_meta
    return {**stored_meta, **computed_meta}


def format_elevation_compact(feet: Any) -> str | None:
    if feet in (None, ""):
        return None
    try:
        value = int(round(float(feet)))
    except (TypeError, ValueError):
        return None
    return f"{value:,} ft gain"


def parse_uploaded_route_import(uploaded_file) -> tuple[ParsedTcxRouteImport | None, bytes | None, str | None]:
    if not uploaded_file:
        return None, None, None
    file_name = str(getattr(uploaded_file, "name", "") or "").strip()
    if not file_name:
        return None, None, None
    try:
        file_bytes = uploaded_file.getvalue()
    except Exception:
        return None, None, "Could not read the uploaded TCX file."
    try:
        parsed = parse_tcx_bytes(file_bytes)
    except TcxParseError as exc:
        return None, None, str(exc)
    return parsed, file_bytes, None


def sync_hike_route_import(
    *,
    repository: HikeJournalRepository,
    storage: StorageService,
    hike_id: str,
    uploaded_file,
    existing_route_import: dict[str, Any] | None,
    remove_existing: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    active_route_import = existing_route_import
    parsed: ParsedTcxRouteImport | None = None
    file_bytes: bytes | None = None
    if uploaded_file:
        parsed, file_bytes, error = parse_uploaded_route_import(uploaded_file)
        if error:
            return active_route_import, error

    if remove_existing and existing_route_import:
        try:
            deleted = repository.delete_hike_route_import(hike_id)
        except Exception:
            return active_route_import, "Run sql/hike_route_imports_migration.sql before deleting imported routes."
        if deleted and deleted.get("source_storage_path"):
            storage.delete_file(str(deleted["source_storage_path"]))
        active_route_import = None

    if not uploaded_file or parsed is None or file_bytes is None:
        return active_route_import, None

    storage_path, public_url = storage.upload_hike_route_import(hike_id, file_bytes)
    payload = {
        "source_type": "mapmyrun_tcx",
        "source_file_name": str(getattr(uploaded_file, "name", "") or "").strip() or None,
        "source_storage_path": storage_path,
        "source_public_url": public_url,
        "started_at": parsed.started_at,
        "distance_miles": round(parsed.distance_miles, 3) if parsed.distance_miles is not None else None,
        "duration_seconds": parsed.duration_seconds,
        "track_point_count": parsed.track_point_count,
        "start_lat": parsed.start_latitude,
        "start_lng": parsed.start_longitude,
        "end_lat": parsed.end_latitude,
        "end_lng": parsed.end_longitude,
        "track_geojson": parsed.track_geojson,
    }
    try:
        updated = repository.upsert_hike_route_import(hike_id, payload)
    except Exception:
        storage.delete_file(storage_path)
        return active_route_import, "Run sql/hike_route_imports_migration.sql before saving imported routes."
    old_storage_path = str((existing_route_import or {}).get("source_storage_path") or "").strip()
    if old_storage_path and old_storage_path != storage_path:
        storage.delete_file(old_storage_path)
    return updated, None


def route_import_to_route_points(route_import: dict[str, Any] | None) -> list[dict[str, float]]:
    if not route_import:
        return []
    geojson = route_import.get("track_geojson") or {}
    coordinates = geojson.get("coordinates") if isinstance(geojson, dict) else None
    if not isinstance(coordinates, list):
        return []
    points: list[dict[str, float]] = []
    for coordinate in coordinates:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
            continue
        try:
            lng = float(coordinate[0])
            lat = float(coordinate[1])
        except (TypeError, ValueError):
            continue
        points.append({"lat": lat, "lng": lng})
    return points


def count_unique_species(observations: list[dict[str, Any]]) -> int:
    return len({build_species_group_key(observation) for observation in observations if build_species_group_key(observation)})


def count_unique_species_by_key(observations: list[dict[str, Any]], key: str) -> dict[str, int]:
    buckets: dict[str, set[str]] = defaultdict(set)
    for observation in observations:
        record_key = observation.get(key)
        if not record_key:
            continue
        buckets[str(record_key)].add(build_species_group_key(observation))
    return {bucket_key: len(values) for bucket_key, values in buckets.items()}


def compute_total_mileage(hikes: list[dict[str, Any]]) -> float:
    total = 0.0
    for hike in hikes:
        try:
            distance = float(hike.get("distance_miles"))
        except (TypeError, ValueError):
            continue
        total += distance
    return total


def _route_progress_label(progress: float) -> str:
    if progress <= 0.2:
        return "Start of hike"
    if progress <= 0.45:
        return "Early miles"
    if progress <= 0.7:
        return "Mid-hike"
    if progress <= 0.9:
        return "Late miles"
    return "Finish stretch"


def _haversine_distance_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_miles = 3958.7613
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    return 2 * radius_miles * math.asin(min(1.0, math.sqrt(a)))


def annotate_photos_with_route_context(
    photos: list[dict[str, Any]],
    *,
    route_import: dict[str, Any] | None,
    hike_distance_miles: float | None,
) -> list[dict[str, Any]]:
    route_points = route_import_to_route_points(route_import)
    if len(route_points) < 2 or not photos:
        return photos

    cumulative_miles = [0.0]
    total_line_distance = 0.0
    for index in range(1, len(route_points)):
        segment = _haversine_distance_miles(
            route_points[index - 1]["lat"],
            route_points[index - 1]["lng"],
            route_points[index]["lat"],
            route_points[index]["lng"],
        )
        total_line_distance += segment
        cumulative_miles.append(total_line_distance)
    reference_distance = float(hike_distance_miles or 0.0) or total_line_distance

    for photo in photos:
        photo.pop("route_context_label", None)
        lat = photo.get("lat")
        lng = photo.get("lng")
        if lat is None or lng is None:
            continue
        nearest_index = 0
        nearest_distance = None
        for index, point in enumerate(route_points):
            distance_to_point = (float(point["lat"]) - float(lat)) ** 2 + (float(point["lng"]) - float(lng)) ** 2
            if nearest_distance is None or distance_to_point < nearest_distance:
                nearest_distance = distance_to_point
                nearest_index = index
        progress = nearest_index / max(1, len(route_points) - 1)
        approx_mile = reference_distance * progress
        photo["route_context_label"] = f"{_route_progress_label(progress)} • approx mile {approx_mile:.1f}"
    return photos


def get_user_context() -> dict[str, Any]:
    auth_configured = is_google_auth_configured()
    streamlit_logged_in = bool(getattr(st.user, "is_logged_in", False)) if auth_configured else False
    if auth_configured and streamlit_logged_in:
        email = normalize_email(st.user.get("email"))
        display_name = st.user.get("name") or email or "Hiker"
        allowed_emails = getattr(settings, "allowed_emails", settings.admin_emails)
        is_allowed = bool(email and email in allowed_emails)
        return {
            "auth_configured": True,
            "is_logged_in": True,
            "subject": st.user.get("sub"),
            "email": email,
            "display_name": display_name,
            "is_allowed": is_allowed,
            "is_admin": bool(email and email in settings.admin_emails),
            "mode": "google",
        }

    if settings.require_google_auth:
        return {
            "auth_configured": auth_configured,
            "is_logged_in": False,
            "subject": None,
            "email": None,
            "display_name": "Guest",
            "is_allowed": False,
            "is_admin": False,
            "mode": "signed-out" if auth_configured else "auth-misconfigured",
        }

    if not auth_configured or not settings.require_google_auth:
        return {
            "auth_configured": auth_configured,
            "is_logged_in": True,
            "subject": "local-dev-user",
            "email": next(iter(settings.admin_emails), "local@hikejournal.dev"),
            "display_name": "Local admin",
            "is_allowed": True,
            "is_admin": True,
            "mode": "local-dev",
        }

    return {
        "auth_configured": True,
        "is_logged_in": False,
        "subject": None,
        "email": None,
        "display_name": "Guest",
        "is_allowed": False,
        "is_admin": False,
        "mode": "signed-out",
    }

def is_google_auth_configured() -> bool:
    try:
        auth_config = st.secrets.get("auth", {})
    except Exception:
        return False
    if not auth_config:
        return False
    return bool(auth_config.get("client_id") and auth_config.get("redirect_uri") and auth_config.get("cookie_secret"))


def render_login_gate() -> None:
    render_hero(None, 0, 0, 0)
    st.write("")
    section_heading(
        "Sign In",
        "Use Google to open your field journal",
        "Each Google account gets its own private hike library. Sign in to open yours.",
    )
    st.write("")
    action_cols = st.columns([0.34, 0.32, 0.34])
    with action_cols[1]:
        if st.button("Continue with Google", use_container_width=True, type="primary"):
            try:
                st.login()
            except Exception as exc:  # pragma: no cover - depends on local auth secrets
                st.error(f"Google sign-in is not configured cleanly yet: {exc}")


def render_access_denied(user_context: dict[str, Any]) -> None:
    render_hero(None, 0, 0, 0)
    st.write("")
    section_heading(
        "Private Journal",
        "This Google account is not allowed here",
        "HikeJournal is locked to the journal owner. Sign out and use the owner account to continue.",
    )
    if user_context.get("email"):
        st.error(f"{user_context['email']} is not on the allowed account list.")
    action_cols = st.columns([0.34, 0.32, 0.34])
    with action_cols[1]:
        if st.button("Sign out", use_container_width=True):
            try:
                st.logout()
            except Exception as exc:  # pragma: no cover - depends on local auth session
                st.error(f"Could not sign out cleanly: {exc}")


def render_inat_token_manager(inat_client: InatClient, user_context: dict[str, Any]) -> None:
    should_expand = bool(st.session_state.inat_auth_error) or not is_inat_client_ready(inat_client)
    with st.expander("iNaturalist connection", expanded=should_expand):
        render_inat_token_controls(inat_client, user_context, form_key="inat_token_form", disconnect_key="inat_disconnect_button")


@st.dialog("iNaturalist connection", width="large")
def render_inat_token_dialog(inat_client: InatClient, user_context: dict[str, Any]) -> None:
    render_inat_token_controls(
        inat_client,
        user_context,
        form_key="inat_token_dialog_form",
        disconnect_key="inat_dialog_disconnect_button",
    )
    if st.button("Close", key="inat_token_dialog_close", type="secondary"):
        st.session_state.inat_token_dialog_open = False
        st.rerun()


def open_inat_token_dialog() -> None:
    st.session_state.viewer_open = False
    if "photo" in st.query_params:
        del st.query_params["photo"]
    st.session_state.inat_token_dialog_open = True
    st.rerun()


def is_inat_client_ready(inat_client: InatClient) -> bool:
    if not inat_client.is_configured:
        return False
    expiry = inat_client.token_expiry
    return expiry is None or expiry > datetime.now(UTC)


def inat_connection_action_label(inat_client: InatClient) -> str:
    if not inat_client.is_configured:
        return "Connect iNaturalist"
    if not is_inat_client_ready(inat_client):
        return "Refresh iNaturalist"
    return "Manage iNaturalist"


def inat_not_ready_message(inat_client: InatClient) -> str:
    if not inat_client.is_configured:
        return "Connect iNaturalist before using this action."
    if not is_inat_client_ready(inat_client):
        return "Refresh your expired iNaturalist token before using this action."
    return ""


def render_inat_token_controls(
    inat_client: InatClient,
    user_context: dict[str, Any],
    *,
    form_key: str,
    disconnect_key: str,
) -> None:
    token_record = None
    if user_context.get("mode") == "google":
        token_record = load_inat_token_record_for_user(
            subject=user_context.get("subject"),
            email=user_context.get("email"),
        )
    if user_context.get("mode") == "google" and user_context.get("email"):
        token_kind = str((token_record or {}).get("token_kind") or "manual").strip().lower() if token_record else "manual"
        if token_record and token_kind == "oauth":
            st.caption(f"iNaturalist is connected for {user_context['email']} through OAuth.")
        elif token_record or inat_client.is_configured:
            st.caption(f"Using the iNaturalist token saved for {user_context['email']}.")
        else:
            st.caption(f"No iNaturalist token is currently saved for {user_context['email']}.")
    if st.session_state.inat_auth_error:
        st.error(st.session_state.inat_auth_error)
    if st.session_state.inat_auth_notice:
        st.success(st.session_state.inat_auth_notice)

    if inat_client.is_configured and inat_client.token_expiry:
        expires_local = inat_client.token_expiry.astimezone()
        if is_inat_client_ready(inat_client):
            st.caption(f"Current token expires {expires_local.strftime('%B %d, %Y at %I:%M %p %Z')}.")
        else:
            st.warning(f"This iNaturalist token expired {expires_local.strftime('%B %d, %Y at %I:%M %p %Z')}. Paste a fresh token before posting or checking IDs.")
    elif inat_client.is_configured:
        st.caption("A token is configured, but HikeJournal could not read an expiry date from it.")
    else:
        if user_context.get("mode") == "google":
            st.caption("Paste your iNaturalist token here once, and HikeJournal will save it for your signed-in Google account on this server.")
        else:
            st.caption("Paste your iNaturalist token here once, and HikeJournal will keep using it on this machine.")

    if user_context.get("mode") == "google":
        oauth_cols = st.columns([0.62, 0.38], gap="small")
        if settings.inat_oauth_configured:
            state = f"inat:{secrets.token_urlsafe(24)}"
            st.session_state.inat_oauth_state = state
            authorize_url = build_oauth_authorize_url(state=state)
            oauth_cols[0].markdown(
                f"<a class='viewer-link' href='{authorize_url}' target='_self'>Connect iNaturalist</a>",
                unsafe_allow_html=True,
            )
            if token_record and oauth_cols[1].button("Disconnect", use_container_width=True, key=disconnect_key):
                delete_inat_token_record_for_user(
                    subject=user_context.get("subject"),
                    email=user_context.get("email"),
                )
                st.session_state.inat_auth_notice = "Disconnected your iNaturalist account."
                st.session_state.inat_auth_error = None
                st.rerun()
        else:
            st.caption(
                "OAuth is not configured yet for iNaturalist. Register an iNaturalist app and set the redirect URI to "
                f"`{settings.inat_oauth_redirect_uri}`."
            )

    st.markdown(
        "Get a fresh token from [iNaturalist API token](https://www.inaturalist.org/users/api_token). "
        "You can paste either the raw token or the full JSON snippet from that page."
    )

    with st.form(form_key, clear_on_submit=False):
        token_value = st.text_input(
            "API token",
            value=st.session_state.inat_token_input,
            type="password",
            placeholder="eyJhbGciOi...",
        )
        submitted = st.form_submit_button("Save token", type="primary", use_container_width=True)

    if submitted:
        normalized_token = normalize_access_token(token_value)
        st.session_state.inat_token_input = token_value
        if not normalized_token:
            st.session_state.inat_auth_notice = None
            st.session_state.inat_auth_error = "Paste a token before saving."
            st.rerun()

        candidate_client = InatClient(access_token=normalized_token)
        try:
            candidate_client.validate_credentials()
        except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
            st.session_state.inat_auth_notice = None
            st.session_state.inat_auth_error = str(exc)
            st.rerun()

        if user_context.get("mode") == "google":
            persist_access_token_for_user(
                normalized_token,
                subject=user_context.get("subject"),
                email=user_context.get("email"),
            )
        else:
            persist_access_token(normalized_token)
        expires_local = candidate_client.token_expiry.astimezone() if candidate_client.token_expiry else None
        st.session_state.inat_auth_error = None
        st.session_state.inat_token_input = ""
        if expires_local:
            st.session_state.inat_auth_notice = (
                f"Saved a fresh iNaturalist token. It expires {expires_local.strftime('%B %d, %Y at %I:%M %p %Z')}."
            )
        else:
            st.session_state.inat_auth_notice = "Saved a fresh iNaturalist token."
        st.session_state.inat_token_dialog_open = False
        st.rerun()


def render_auth_configuration_state() -> None:
    render_hero(None, 0, 0, 0)
    st.write("")
    section_heading(
        "Authentication Required",
        "Google sign-in is required before this journal can open",
        "This journal is private. Finish the Google sign-in setup so each hiker can open their own library.",
    )
    st.error("Google sign-in is required, but the app still needs a valid authentication setup before anyone can enter.")


def render_setup_state(reason: str | None = None) -> None:
    render_hero(None, 0, 0, 0)
    st.write("")
    section_heading(
        "Setup",
        "Connect storage before you start logging hikes",
        "Add the project connection and schema so HikeJournal can save outings, photos, and species notes.",
    )
    if reason:
        st.warning("Supabase is connected, but HikeJournal still needs its database schema and storage policies.")
        st.caption(reason)
    st.code(
        "\n".join(
            [
                "cp .env.example .env",
                "# Fill in SUPABASE_URL and SUPABASE_KEY",
                "# Run sql/schema.sql in the Supabase SQL editor",
                "streamlit run app.py",
            ]
        ),
        language="bash",
    )


def format_storage_bytes(byte_count: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(max(byte_count, 0))
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"
    return f"{value:.1f} {units[unit_index]}"


def calculate_visible_storage_usage(
    records: list[dict[str, Any]],
    *,
    visible_hike_ids: set[str],
    user_context: dict[str, Any],
) -> dict[str, Any]:
    visible_records = [record for record in records if record_visible_for_user(record, visible_hike_ids, user_context)]
    original_bytes = sum(int(record.get("file_size") or 0) for record in visible_records)
    derivative_bytes = 0
    total_bytes = original_bytes
    if settings.storage_backend == "r2":
        free_limit_bytes = 10 * (1024 ** 3)
        backend_label = "Cloudflare R2"
        free_label = "about 10 GB free"
    else:
        free_limit_bytes = 1024 ** 3
        backend_label = "Supabase Storage"
        free_label = "about 1 GB free"
    ratio = min(total_bytes / free_limit_bytes, 1.0) if free_limit_bytes else 0.0
    remaining_bytes = max(free_limit_bytes - total_bytes, 0)
    return {
        "photo_count": len(visible_records),
        "original_bytes": original_bytes,
        "derivative_bytes": derivative_bytes,
        "total_bytes": total_bytes,
        "remaining_bytes": remaining_bytes,
        "ratio": ratio,
        "free_limit_bytes": free_limit_bytes,
        "backend_label": backend_label,
        "free_label": free_label,
    }


def render_sidebar(
    repository: HikeJournalRepository,
    storage: StorageService,
    hikes: list[dict[str, Any]],
    user_context: dict[str, Any],
    active_view: str,
) -> None:
    if user_context["mode"] == "google":
        identity_line = f"{user_context['display_name']} • {user_context['email']}"
    elif user_context["mode"] == "local-dev":
        identity_line = "Signed in locally"
    else:
        identity_line = "A private trail journal for hikes, photos, and sightings."

    st.markdown(
        f"""
        <div class="sidebar-brand-shell">
            <div class="sidebar-brand-kicker">Field Journal</div>
            <div class="sidebar-brand-wordmark">HikeJournal</div>
            <div class="sidebar-brand-meta">{escape(identity_line)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='sidebar-section-label'>Create</div>", unsafe_allow_html=True)
    if st.button("New outing", use_container_width=True, type="primary"):
        render_create_hike_dialog(repository, storage, user_context)
    if st.button("Quick upload", use_container_width=True, type="secondary"):
        render_quick_upload_dialog(storage, repository, user_context)

    current_hike = next((hike for hike in hikes if hike["id"] == st.session_state.selected_hike_id), None)
    st.markdown("<div class='sidebar-section-label'>Navigate</div>", unsafe_allow_html=True)
    nav_items = [
        ("Library", "Library", "?view=Library"),
        ("Species review", "Species Review", "?view=Species%20Review"),
        ("Master map", "Map", "?view=Map&scope=global"),
        ("Species log", "Species Log", "?view=Species%20Log"),
    ]
    nav_markup = []
    for label, view_name, href in nav_items:
        active_class = " active" if active_view == view_name else ""
        nav_markup.append(f'<a class="sidebar-nav-link{active_class}" href="{href}" target="_self">{escape(label)}</a>')
    st.markdown(f"<div class='sidebar-nav-shell'>{''.join(nav_markup)}</div>", unsafe_allow_html=True)

    if current_hike:
        journal_href = f"?view=Journal&hike={quote(current_hike['id'])}"
        outing_map_href = f"?view=Map&hike={quote(current_hike['id'])}"
        st.markdown("<div class='sidebar-section-label'>Open outing</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="sidebar-current-hike">
                <div class="sidebar-current-label">In progress</div>
                <div class="sidebar-current-title">{escape(current_hike.get('title') or 'Untitled outing')}</div>
                <div class="sidebar-current-meta">
                    {escape(str(current_hike.get('hike_date') or ''))}
                    {' • ' + escape(current_hike.get('location_name') or '') if current_hike.get('location_name') else ''}
                </div>
                <div class="sidebar-current-actions">
                    <a class="sidebar-current-action{' active' if active_view == 'Journal' else ''}" href="{journal_href}" target="_self">Journal</a>
                    <a class="sidebar-current-action{' active' if active_view == 'Map' else ''}" href="{outing_map_href}" target="_self">Map</a>
                    <a class="sidebar-current-action subtle" href="?view=Library&scope=global" target="_self">Close</a>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div class='sidebar-section-label'>Open outing</div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="sidebar-current-hike">
                <div class="sidebar-current-label">No outing open</div>
                <div class="sidebar-current-meta">Open a hike from the library to keep its journal and map one click away while you browse the wider record.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not hikes:
        st.caption("No outings yet. Start one to begin your journal.")

    visible_hike_ids = {hike["id"] for hike in hikes}
    storage_usage = calculate_visible_storage_usage(
        fetch_photo_storage_records(),
        visible_hike_ids=visible_hike_ids,
        user_context=user_context,
    )
    st.write("")
    st.markdown("<div class='sidebar-section-label'>Storage</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="sidebar-storage-shell">
            <div class="sidebar-storage-line">
                <strong>{escape(format_storage_bytes(storage_usage['total_bytes']))}</strong>
                <span>of {escape(storage_usage['free_label'])}</span>
            </div>
            <div class="sidebar-storage-bar">
                <span style="width:{storage_usage['ratio'] * 100:.1f}%"></span>
            </div>
            <div class="sidebar-storage-meta">
                <span>{escape(storage_usage['backend_label'])}</span>
                <span>{storage_usage['photo_count']} photos</span>
                <span>{escape(format_storage_bytes(storage_usage['remaining_bytes']))} left</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown("<div class='sidebar-section-label'>Account</div>", unsafe_allow_html=True)
    if user_context["auth_configured"] and user_context["mode"] != "google":
        if st.button("Sign in with Google", use_container_width=True, type="secondary"):
            try:
                st.login()
            except Exception as exc:  # pragma: no cover - depends on local auth secrets
                st.error(f"Google sign-in is not configured cleanly yet: {exc}")
    if user_context["mode"] == "google":
        if st.button("Sign out", use_container_width=True, type="tertiary"):
            try:
                st.logout()
            except Exception as exc:  # pragma: no cover - depends on local auth secrets
                st.error(f"Google sign-out hit a configuration problem: {exc}")


def render_mobile_shell(hikes: list[dict[str, Any]], active_view: str) -> None:
    current_hike = next((hike for hike in hikes if hike["id"] == st.session_state.selected_hike_id), None)
    nav_items: list[tuple[str, str, str]] = [
        ("Library", "Library", build_internal_view_href(view="Library")),
        ("Review", "Species Review", build_internal_view_href(view="Species Review")),
        ("Map", "Map", build_internal_view_href(view="Map", scope="global")),
        ("Log", "Species Log", build_internal_view_href(view="Species Log")),
    ]
    if current_hike:
        nav_items.insert(
            1,
            (
                "Journal",
                "Journal",
                build_internal_view_href(view="Journal", hike_id=str(current_hike["id"])),
            ),
        )

    nav_links = []
    for label, view_name, href in nav_items:
        active_class = " active" if active_view == view_name else ""
        nav_links.append(
            f'<a class="mobile-bottom-nav-link{active_class}" href="{escape(href)}" target="_self">{escape(label)}</a>'
        )

    if current_hike:
        current_title = escape(current_hike.get("title") or "Untitled outing")
        current_meta = escape(str(current_hike.get("hike_date") or ""))
        current_location = current_hike.get("location_name")
        if current_location:
            current_meta = f"{current_meta} • {escape(str(current_location))}" if current_meta else escape(str(current_location))
        current_markup = f"""
            <div class="mobile-current-shell">
                <div>
                    <div class="mobile-current-label">Open outing</div>
                    <div class="mobile-current-title">{current_title}</div>
                    <div class="mobile-current-meta">{current_meta}</div>
                </div>
                <a class="mobile-current-close" href="{escape(build_internal_view_href(view='Library', scope='global'))}" target="_self">Close</a>
            </div>
        """
    else:
        current_markup = f"""
            <div class="mobile-current-shell mobile-current-shell--quiet">
                <div>
                    <div class="mobile-current-label">HikeJournal</div>
                    <div class="mobile-current-title">{escape(active_view)}</div>
                </div>
            </div>
        """

    st.html(
        f"""
        <style>
        .mobile-app-shell {{
            display: none !important;
        }}
        @media (max-width: 640px) {{
            .mobile-app-shell {{
                display: block !important;
            }}
            .mobile-app-shell .mobile-current-shell {{
                position: fixed;
                z-index: 999998;
                top: env(safe-area-inset-top, 0px);
                left: 0;
                right: 0;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.8rem;
                min-height: 4.8rem;
                padding: 0.65rem 1rem 0.7rem;
                background: rgba(245,239,228,0.96);
                border-bottom: 1px solid rgba(32,44,36,0.1);
                box-shadow: 0 14px 34px rgba(32,44,36,0.08);
            }}
            .mobile-app-shell .mobile-bottom-nav {{
                position: fixed;
                z-index: 999999;
                left: 0.75rem;
                right: 0.75rem;
                bottom: calc(0.65rem + env(safe-area-inset-bottom, 0px));
                display: grid;
                grid-auto-flow: column;
                grid-auto-columns: 1fr;
                gap: 0.35rem;
                padding: 0.45rem;
                border: 1px solid rgba(32,44,36,0.16);
                border-radius: 24px;
                background: rgba(246,240,229,0.96);
                box-shadow: 0 18px 46px rgba(32,44,36,0.22);
            }}
        }}
        </style>
        <div id="hikejournal-build-mobile-shell-df7fde9" hidden></div>
        <div class="mobile-app-shell">
            {current_markup}
            <nav class="mobile-bottom-nav" aria-label="Mobile navigation">
                {''.join(nav_links)}
            </nav>
        </div>
        """
    )

def render_empty_state() -> None:
    section_heading(
        "Choose a Hike",
        "Open an outing to continue",
        "Pick a hike from your library or start a new one to add notes, photos, and species sightings.",
    )


def render_footer() -> None:
    st.markdown(
        """
        <footer class="app-footer">
            <span>Created by </span>
            <a href="https://www.wtsorlando.com" target="_blank" rel="noopener noreferrer">Web Technology Strategies, LLC</a>
        </footer>
        """,
        unsafe_allow_html=True,
    )


def navigate_to(
    *,
    view: str,
    hike_id: str | None = None,
    photo_id: str | None = None,
    map_photo_id: str | None = None,
    scope: str | None = None,
) -> None:
    st.session_state.active_view = view
    st.session_state.pending_view = view
    st.query_params["view"] = view
    for key, value in get_query_state_for_view(view).items():
        st.query_params[key] = value
    if scope:
        st.query_params["scope"] = scope
    elif "scope" in st.query_params:
        del st.query_params["scope"]
    if hike_id:
        st.session_state.selected_hike_id = hike_id
        st.query_params["hike"] = hike_id
    else:
        st.session_state.selected_hike_id = None
        if "hike" in st.query_params:
            del st.query_params["hike"]
    if photo_id:
        st.query_params["photo"] = photo_id
    elif "photo" in st.query_params:
        del st.query_params["photo"]
    if map_photo_id:
        st.query_params["map_photo"] = map_photo_id
    elif "map_photo" in st.query_params:
        del st.query_params["map_photo"]
    st.rerun()


def sync_pagination_state_from_query_params() -> None:
    current_signature = tuple(
        (key, str(st.query_params.get(key, "")))
        for key in [
            "journal_page",
            "journal_page_size",
            "species_page",
            "species_page_size",
            "species_review_mode",
            "species_review_stage",
            "species_log_page",
            "species_log_page_size",
            "species_log_focus_key",
            "species_log_record_open",
            "map_layer_mode",
            "map_species_filter",
            "species_log_query",
            "species_log_hike_filter",
            "species_log_sort",
            "species_log_posted_filter",
            "species_log_mapped_only",
            "species_log_include_secondary",
            "map_photo_range_start",
            "map_photo_range_end",
        ]
    )
    if st.session_state.query_state_signature == current_signature:
        return

    _sync_positive_int_query_param("journal_page", minimum=1)
    _sync_positive_int_query_param("species_page", minimum=1)
    _sync_positive_int_query_param("journal_page_size", minimum=0)
    _sync_positive_int_query_param("species_page_size", minimum=0)
    _sync_string_query_param("species_review_mode")
    _sync_string_query_param("species_review_stage")
    _sync_positive_int_query_param("species_log_page", minimum=1)
    _sync_positive_int_query_param("species_log_page_size", minimum=0)
    _sync_string_query_param("species_log_focus_key")
    _sync_bool_query_param("species_log_record_open")
    _sync_string_query_param("map_layer_mode")
    _sync_string_query_param("map_species_filter")
    _sync_string_query_param("species_log_query")
    _sync_string_query_param("species_log_hike_filter")
    _sync_string_query_param("species_log_sort")
    _sync_string_query_param("species_log_posted_filter")
    _sync_bool_query_param("species_log_mapped_only")
    _sync_bool_query_param("species_log_include_secondary")
    map_range_start = _parse_positive_int_query_param("map_photo_range_start", minimum=1)
    map_range_end = _parse_positive_int_query_param("map_photo_range_end", minimum=1)
    if map_range_start is not None and map_range_end is not None:
        st.session_state.map_photo_range = (map_range_start, map_range_end)
    st.session_state.query_state_signature = current_signature


def get_query_state_for_view(view: str) -> dict[str, str]:
    if view == "Journal":
        return {
            "journal_page": str(int(st.session_state.get("journal_page", 1))),
            "journal_page_size": str(int(st.session_state.get("journal_page_size", 9))),
        }
    if view == "Species Review":
        return {
            "species_page": str(int(st.session_state.get("species_page", 1))),
            "species_page_size": str(int(st.session_state.get("species_page_size", 6))),
            "species_review_mode": str(st.session_state.get("species_review_mode", "Review")),
            "species_review_stage": str(st.session_state.get("species_review_stage", "All")),
        }
    if view == "Map":
        query = {
            "map_layer_mode": str(st.session_state.get("map_layer_mode", "Both")),
            "map_species_filter": str(st.session_state.get("map_species_filter", "All confirmed species")),
        }
        map_range = st.session_state.get("map_photo_range")
        if isinstance(map_range, (tuple, list)) and len(map_range) == 2:
            query["map_photo_range_start"] = str(int(map_range[0]))
            query["map_photo_range_end"] = str(int(map_range[1]))
        return query
    if view == "Species Log":
        return {
            "species_log_query": str(st.session_state.get("species_log_query", "")).strip(),
            "species_log_page": str(int(st.session_state.get("species_log_page", 1))),
            "species_log_page_size": str(int(st.session_state.get("species_log_page_size", 8))),
            "species_log_hike_filter": str(st.session_state.get("species_log_hike_filter", "All hikes")),
            "species_log_sort": str(st.session_state.get("species_log_sort", "Most recent")),
            "species_log_posted_filter": str(st.session_state.get("species_log_posted_filter", "All")),
            "species_log_mapped_only": "1" if st.session_state.get("species_log_mapped_only") else "0",
            "species_log_include_secondary": "1" if st.session_state.get("species_log_include_secondary", True) else "0",
            "species_log_focus_key": str(st.session_state.get("species_log_focus_key") or ""),
            "species_log_record_open": "1" if st.session_state.get("species_log_record_open") else "0",
        }
    return {}


def _sync_positive_int_query_param(key: str, *, minimum: int) -> None:
    parsed = _parse_positive_int_query_param(key, minimum=minimum)
    if parsed is not None:
        st.session_state[key] = parsed


def _parse_positive_int_query_param(key: str, *, minimum: int) -> int | None:
    raw_value = st.query_params.get(key)
    if raw_value is None:
        return None
    try:
        parsed = int(str(raw_value))
    except (TypeError, ValueError):
        return None
    if parsed < minimum:
        return None
    return parsed


def _sync_string_query_param(key: str) -> None:
    raw_value = st.query_params.get(key)
    if raw_value is None:
        return
    st.session_state[key] = str(raw_value)


def _sync_bool_query_param(key: str) -> None:
    raw_value = st.query_params.get(key)
    if raw_value is None:
        return
    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        st.session_state[key] = True
    elif normalized in {"0", "false", "no", "off"}:
        st.session_state[key] = False


@st.dialog("New Hike", width="large")
def render_create_hike_dialog(repository: HikeJournalRepository, storage: StorageService, user_context: dict[str, Any]) -> None:
    st.caption("Start a new outing and add it to your library.")
    with st.form("create_hike_dialog_form", clear_on_submit=True):
        title = st.text_input("Hike title", placeholder="Black Bear Wilderness Loop")
        hike_date = st.date_input("Hike date", value=date.today())
        distance = st.number_input("Distance (miles)", min_value=0.0, step=0.5, value=0.0)
        location_name = st.text_input("Location", placeholder="Seminole State Forest")
        notes = st.text_area("Opening notes", placeholder="What stood out about the day?", height=140)
        route_import_file = st.file_uploader(
            "MapMyRun TCX export",
            type=TCX_IMPORT_TYPES,
            accept_multiple_files=False,
            help="Optional: upload the TCX export for this outing to save the route line and route stats.",
        )
        use_imported_route_fields = st.checkbox("Use TCX date and distance for this outing", value=True)
        submitted = st.form_submit_button("Create hike", use_container_width=True)
        if submitted:
            if not title.strip():
                st.warning("Add a hike title to save this outing.")
            else:
                parsed_route_import, _, route_import_error = parse_uploaded_route_import(route_import_file)
                if route_import_error:
                    st.warning(route_import_error)
                    return
                target_hike_date = parsed_route_import.visited_on if parsed_route_import and use_imported_route_fields and parsed_route_import.visited_on else hike_date
                target_distance = parsed_route_import.distance_miles if parsed_route_import and use_imported_route_fields and parsed_route_import.distance_miles is not None else (distance or None)
                draft = HikeDraft(
                    title=title,
                    hike_date=target_hike_date,
                    distance_miles=target_distance,
                    location_name=location_name,
                    notes=notes,
                    owner_subject=user_context.get("subject") if user_context.get("mode") == "google" else None,
                    owner_email=user_context.get("email") if user_context.get("mode") == "google" else None,
                )
                created = repository.create_hike(draft)
                if route_import_file:
                    _, route_import_error = sync_hike_route_import(
                        repository=repository,
                        storage=storage,
                        hike_id=created["id"],
                        uploaded_file=route_import_file,
                        existing_route_import=None,
                        remove_existing=False,
                    )
                    if route_import_error:
                        st.warning(route_import_error)
                invalidate_data_cache()
                navigate_to(view="Journal", hike_id=created["id"])


@st.dialog("Quick Upload", width="large")
def render_quick_upload_dialog(
    storage: StorageService,
    repository: HikeJournalRepository,
    user_context: dict[str, Any],
) -> None:
    st.caption("Add one or more photos without opening a hike. They will still appear in species review, the master map, and the species log.")
    if st.session_state.quick_upload_notice:
        st.success(str(st.session_state.quick_upload_notice))
        st.session_state.quick_upload_notice = None
    upload_widget_key = f"quick_upload_files_{st.session_state.quick_upload_nonce}"
    with st.form("quick_upload_dialog_form", clear_on_submit=True):
        uploaded_files = st.file_uploader(
            "Drop in one or many photos",
            type=["jpg", "jpeg", "png", "webp", "heic"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key=upload_widget_key,
        )
        shared_note = st.text_area(
            "Shared photo note",
            placeholder="Optional note applied to each uploaded photo in this batch",
            height=120,
        )
        queue_for_review = st.checkbox("Queue these for species review right away", value=True)
        submitted = st.form_submit_button("Upload photos", use_container_width=True)
        if submitted:
            if not uploaded_files:
                st.warning("Choose at least one photo to upload.")
                return
            owner_subject = user_context.get("subject") if user_context.get("mode") in {"google", "local-dev"} else None
            owner_email = user_context.get("email") if user_context.get("mode") in {"google", "local-dev"} else None
            geotagged_uploads = 0
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
                    processed = optimize_image(original_bytes)
                    persist_uploaded_photo(
                        repository=repository,
                        storage=storage,
                        processed_image=processed,
                        original_exif_json=metadata.exif_json,
                        lat=metadata.lat,
                        lng=metadata.lng,
                        taken_at=metadata.taken_at,
                        hike_id=None,
                        owner_subject=owner_subject,
                        owner_email=owner_email,
                        caption=shared_note.strip() or None,
                        processing_status=REVIEW_QUEUE_STATUS if queue_for_review else "ready",
                    )
                    upload_progress.progress(index / total_uploads, text=f"Uploaded {index} of {total_uploads} photos")
            invalidate_data_cache()
            st.session_state.pop(upload_widget_key, None)
            st.session_state.quick_upload_nonce += 1
            st.session_state.quick_upload_notice = f"Saved {total_uploads} photo{'s' if total_uploads != 1 else ''} outside any specific hike."
            if geotagged_uploads == 0:
                st.warning("These photos uploaded cleanly, but none of them carried GPS coordinates for the map.")
            navigate_to(view="Species Review")


def persist_uploaded_photo(
    *,
    repository: HikeJournalRepository,
    storage: StorageService,
    processed_image,
    original_exif_json: dict[str, Any],
    lat: float | None,
    lng: float | None,
    taken_at: datetime | None,
    hike_id: str | None,
    owner_subject: str | None,
    owner_email: str | None,
    caption: str | None,
    processing_status: str,
) -> dict[str, Any]:
    if hike_id:
        storage_path, public_url = storage.upload_hike_photo(
            hike_id,
            processed_image.bytes_data,
            processed_image.content_type,
        )
    else:
        storage_path, public_url = storage.upload_standalone_photo(
            processed_image.bytes_data,
            processed_image.content_type,
        )
    exif_json = dict(original_exif_json or {})
    exif_json.pop("derivatives", None)
    return repository.create_photo(
        {
            "hike_id": hike_id,
            "owner_subject": owner_subject,
            "owner_email": owner_email,
            "storage_path": storage_path,
            "public_url": public_url,
            "caption": caption,
            "taken_at": taken_at.isoformat() if taken_at else None,
            "lat": lat,
            "lng": lng,
            "width": processed_image.width,
            "height": processed_image.height,
            "file_size": len(processed_image.bytes_data),
            "content_type": processed_image.content_type,
            "processing_status": processing_status,
            "exif_json": exif_json,
        }
    )


@st.dialog("Manage Hike", width="large")
def render_edit_hike_dialog(
    repository: HikeJournalRepository,
    storage: StorageService,
    hike: dict[str, Any],
) -> None:
    st.caption("Update the details for this outing or archive it when you want it out of the main list.")
    existing_route_import = fetch_hike_route_import(hike["id"])
    with st.form(f"edit_hike_dialog_{hike['id']}"):
        title = st.text_input("Title", value=hike.get("title") or "")
        hike_date = st.date_input("Date", value=_parse_date(hike.get("hike_date")))
        distance_value = float(hike.get("distance_miles") or 0.0)
        distance = st.number_input("Distance (miles)", min_value=0.0, step=0.5, value=distance_value)
        location_name = st.text_input("Location", value=hike.get("location_name") or "")
        notes = st.text_area("Notes", value=hike.get("notes") or "", height=140)
        route_import_file = st.file_uploader(
            "MapMyRun TCX export",
            type=TCX_IMPORT_TYPES,
            accept_multiple_files=False,
            help="Upload a new TCX file to replace the saved route for this outing.",
        )
        use_imported_route_fields = st.checkbox("Use TCX date and distance for this outing", value=True)
        remove_route_import = st.checkbox("Remove the saved route import", value=False)
        archive_label = "Archive this hike from the active list"
        is_archived = st.checkbox(archive_label, value=bool(hike.get("is_archived")))
        submitted = st.form_submit_button("Save hike settings", use_container_width=True)
        if submitted:
            parsed_route_import, _, route_import_error = parse_uploaded_route_import(route_import_file)
            if route_import_error:
                st.warning(route_import_error)
                return
            target_hike_date = parsed_route_import.visited_on if parsed_route_import and use_imported_route_fields and parsed_route_import.visited_on else hike_date
            target_distance = parsed_route_import.distance_miles if parsed_route_import and use_imported_route_fields and parsed_route_import.distance_miles is not None else (distance or None)
            repository.update_hike(
                hike["id"],
                title=title,
                hike_date=target_hike_date,
                distance_miles=target_distance,
                location_name=location_name,
                notes=notes,
            )
            _, route_import_error = sync_hike_route_import(
                repository=repository,
                storage=storage,
                hike_id=hike["id"],
                uploaded_file=route_import_file,
                existing_route_import=existing_route_import,
                remove_existing=remove_route_import,
            )
            if route_import_error:
                st.warning(route_import_error)
            try:
                repository.update_hike_archive(hike["id"], is_archived)
            except Exception:
                pass
            invalidate_data_cache()
            if is_archived and st.session_state.selected_hike_id == hike["id"]:
                st.session_state.active_view = "Library"
                st.session_state.pending_view = "Library"
            st.rerun()


def render_library_tab(
    repository: HikeJournalRepository,
    storage: StorageService,
    hikes: list[dict[str, Any]],
    photo_refs: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    cover_photos_by_id: dict[str, dict[str, Any]],
    user_context: dict[str, Any],
) -> None:
    st.markdown("<div id='library-top'></div>", unsafe_allow_html=True)
    total_photo_count = len(photo_refs)
    total_confirmed_count = count_unique_species(confirmed_observations)
    total_outing_count = len(hikes)
    total_logged_miles = compute_total_mileage(hikes)
    standalone_photos = [
        photo for photo in fetch_standalone_photos()
        if record_visible_for_user(photo, {hike["id"] for hike in hikes}, user_context)
    ]
    st.markdown(
        f"""
        <section class="library-hero">
            <div class="library-hero-copy">
                <p class="library-hero-label">Library</p>
                <h2 class="library-hero-title">Your field archive, shaped like a living trail record.</h2>
                <p class="library-hero-body">Move between outings, everyday sightings, maps, and confirmed species without losing the story of where each sighting belongs.</p>
                <div class="library-hero-meta">
                    <span>{total_outing_count} outings</span>
                    <span>{format_total_miles(total_logged_miles)}</span>
                    <span>{total_photo_count} archived photos</span>
                    <span>{total_confirmed_count} unique species</span>
                </div>
            </div>
        </section>
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
            location_name = hike.get("location_name") or "Unknown location"
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


def render_standalone_journal_tab(
    repository: HikeJournalRepository,
    storage: StorageService,
    inat_client: InatClient,
    photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    user_context: dict[str, Any],
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
        render_quick_upload_dialog(storage, repository, user_context)

    if not photos:
        st.info("No standalone photos yet. Use Quick upload whenever you want to save a sighting outside a formal hike.")
        return

    review_selected_count = len([photo for photo in photos if photo.get("processing_status") == REVIEW_QUEUE_STATUS])
    render_selection_toolbar(repository, photos, "journal")
    st.markdown("### Photo Field Notes")
    page_photos, total_pages = paginate_photos(photos)
    render_photo_management_toolbar(repository, storage, page_photos, photos, total_pages)
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
            render_photo_note_editor(repository, photo, key_prefix=f"standalone_note_{photo['id']}")
            if primary_observation:
                is_confirmed = primary_observation.get("status") == "confirmed"
                render_species_summary(
                    repository,
                    primary_observation,
                    inat_client=inat_client,
                    photo=photo,
                    place_guess=None,
                    key_prefix=f"standalone_{photo['id']}",
                    show_details=is_confirmed,
                    show_confidence=not is_confirmed,
                )
                render_alternate_suggestions(repository, inat_client, primary_observation, photo, key_prefix=f"standalone_{photo['id']}")
                render_secondary_species_summary(photo_observations, primary_observation["id"])
            else:
                st.caption("No species attached to this photo yet.")
            render_add_species_popover(repository, inat_client, None, photo, photo_observations, key_prefix=f"standalone_add_{photo['id']}")
            control_cols = st.columns([0.38, 0.26, 0.18, 0.18], gap="small")
            selected = photo.get("processing_status") == REVIEW_QUEUE_STATUS
            checkbox_key = f"photo_select_{photo['id']}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = selected
            with control_cols[0]:
                st.checkbox(
                    "Select for species review",
                    key=checkbox_key,
                    on_change=sync_journal_review_checkbox,
                    args=(repository, photo["id"], checkbox_key),
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
    render_bottom_review_handoff(anchor_id="journal-top", selected_count=review_selected_count, hike_id=None)


def render_journal_tab(
    repository: HikeJournalRepository,
    storage: StorageService,
    inat_client: InatClient,
    selected_hike: dict[str, Any],
    photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    route_import: dict[str, Any] | None,
) -> None:
    st.markdown("<div id='journal-top'></div>", unsafe_allow_html=True)
    section_heading(
        "Journal",
        "Field notes for this outing",
        "Keep the story of the day, add the photos you want to remember, and mark the frames worth identifying.",
    )
    st.write("")

    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        with st.form("edit_hike_form"):
            title = st.text_input("Title", value=selected_hike.get("title", ""))
            hike_date = st.date_input("Date", value=_parse_date(selected_hike.get("hike_date")))
            distance_value = float(selected_hike.get("distance_miles") or 0.0)
            distance = st.number_input("Distance (miles)", min_value=0.0, step=0.5, value=distance_value)
            location_name = st.text_input("Location", value=selected_hike.get("location_name") or "")
            notes = st.text_area("Hike notes", value=selected_hike.get("notes") or "", height=180)
            route_import_file = st.file_uploader(
                "MapMyRun TCX export",
                type=TCX_IMPORT_TYPES,
                accept_multiple_files=False,
                help="Upload or replace the outing route export here.",
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
                repository.update_hike(
                    selected_hike["id"],
                    title=title,
                    hike_date=target_hike_date,
                    distance_miles=target_distance,
                    location_name=location_name,
                    notes=notes,
                )
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
                            persist_uploaded_photo(
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
    render_selection_toolbar(repository, photos, "journal")
    st.markdown("### Photo Field Notes")
    page_photos, total_pages = paginate_photos(photos)
    render_photo_management_toolbar(repository, storage, page_photos, photos, total_pages)
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
            render_photo_note_editor(repository, photo, key_prefix=f"journal_note_{photo['id']}")
            if primary_observation:
                is_confirmed = primary_observation.get("status") == "confirmed"
                render_species_summary(
                    repository,
                    primary_observation,
                    inat_client=inat_client,
                    photo=photo,
                    place_guess=selected_hike.get("location_name"),
                    key_prefix=f"journal_{photo['id']}",
                    show_details=is_confirmed,
                    show_confidence=not is_confirmed,
                )
                render_alternate_suggestions(repository, inat_client, primary_observation, photo, key_prefix=f"journal_{photo['id']}")
                render_secondary_species_summary(photo_observations, primary_observation["id"])
            else:
                st.caption("No species attached to this photo yet.")
            render_add_species_popover(repository, inat_client, selected_hike.get("id"), photo, photo_observations, key_prefix=f"journal_add_{photo['id']}")
            control_cols = st.columns([0.38, 0.26, 0.18, 0.18], gap="small")
            selected = photo.get("processing_status") == REVIEW_QUEUE_STATUS
            checkbox_key = f"photo_select_{photo['id']}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = selected
            with control_cols[0]:
                st.checkbox(
                    "Select for species review",
                    key=checkbox_key,
                    on_change=sync_journal_review_checkbox,
                    args=(repository, photo["id"], checkbox_key),
                )
            with control_cols[1]:
                current_cover_photo_id = selected_hike.get("cover_photo_id")
                if str(current_cover_photo_id or "") == photo["id"]:
                    st.button("Cover photo", key=f"cover_active_{photo['id']}", disabled=True, use_container_width=True)
                elif st.button("Use as cover", key=f"cover_set_{photo['id']}", use_container_width=True, type="secondary"):
                    try:
                        repository.update_hike_cover_photo(selected_hike["id"], photo["id"])
                    except Exception as exc:
                        st.error(f"Cover photos need the new library migration before they can be saved: {exc}")
                        return
                    invalidate_data_cache()
                    st.success("Saved this as the hike cover photo.")
                    st.rerun()
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
    render_bottom_review_handoff(anchor_id="journal-top", selected_count=review_selected_count, hike_id=str(selected_hike["id"]))


def render_species_tab(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    hikes: list[dict[str, Any]],
    review_queue_photos: list[dict[str, Any]],
    publish_confirmed_observations: list[dict[str, Any]],
    publish_photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
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
    publish_rows = build_publish_rows(hikes, publish_confirmed_observations, publish_photos)
    publish_counts = count_publish_states(publish_rows)

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

    render_inat_token_manager(inat_client, st.session_state.current_user_context)
    st.write("")
    if st.session_state.species_review_mode == "Review":
        if selected_photos:
            apply_species_review_default_state(selected_photos)
            synchronize_species_selection(selected_photos)
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

            stage_selection_signature = (
                st.session_state.species_review_stage,
                tuple(photo["id"] for photo in filtered_review_photos),
            )
            visible_stage_ids = {photo["id"] for photo in filtered_review_photos}
            if st.session_state.species_review_stage_selection_signature != stage_selection_signature:
                st.session_state.species_review_stage_selection_signature = stage_selection_signature
                st.session_state.species_selected_ids = set(visible_stage_ids)
                for photo in filtered_review_photos:
                    st.session_state[f"species_select_{photo['id']}"] = True

            page_photos, total_pages = paginate_items(filtered_review_photos, "species_page", "species_page_size")
            render_species_management_toolbar(
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
                    if review_selected:
                        st.session_state.species_selected_ids.add(photo["id"])
                    else:
                        st.session_state.species_selected_ids.discard(photo["id"])
                    st.markdown(
                        f"<p class='photo-meta'>{format_photo_meta_html(photo, selected_hike_id=photo.get('hike_id'), link_coordinates=True, include_map_link=True)}</p>",
                        unsafe_allow_html=True,
                    )
                    render_photo_note_editor(repository, photo, key_prefix=f"review_note_{photo['id']}")
                    if primary_observation:
                        render_species_summary(
                            repository,
                            primary_observation,
                            inat_client=inat_client,
                            photo=photo,
                            key_prefix=f"review_{photo['id']}",
                            show_details=True,
                        )
                        render_alternate_suggestions(repository, inat_client, primary_observation, photo, key_prefix=f"review_{photo['id']}")
                        render_community_id_request_controls(
                            repository,
                            inat_client,
                            primary_observation,
                            photo,
                            key_prefix=f"review_community_{photo['id']}",
                        )
                        render_secondary_species_summary(photo_observations, primary_observation["id"])
                    else:
                        st.caption("No suggestion has been saved for this photo yet.")
                    render_add_species_popover(repository, inat_client, photo.get("hike_id"), photo, photo_observations, key_prefix=f"review_add_{photo['id']}")
            if st.session_state.species_page_size == 0 and page_photos:
                render_back_to_top_link("species-top")
        else:
            st.info("Mark photos for review in the Journal and they will appear here.")
    else:
        render_publishing_section(
            repository,
            inat_client,
            hikes,
            publish_confirmed_observations,
            publish_photos,
        )


def render_map_tab(
    photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    *,
    selected_hike: dict[str, Any] | None,
    route_imports_by_hike: dict[str, dict[str, Any]],
) -> None:
    if selected_hike:
        section_heading(
            "Trail Map",
            "See where the day unfolded",
            "Follow the route, open geotagged photos, and view confirmed species where you found them.",
        )
    else:
        section_heading(
            "Trail Map",
            "See the full field record at once",
            "Browse geotagged photos across every outing, filter confirmed species, and jump straight into the photo you want.",
        )
    st.write("")
    geotagged_photos = [photo for photo in photos if photo.get("lat") is not None and photo.get("lng") is not None]
    imported_route_groups: list[list[dict[str, float]]] = []
    if selected_hike:
        selected_route_points = route_import_to_route_points(route_imports_by_hike.get(str(selected_hike["id"])))
        imported_route_groups = [selected_route_points] if len(selected_route_points) >= 2 else []
    else:
        imported_route_groups = [
            points
            for points in (
                route_import_to_route_points(route_import)
                for route_import in route_imports_by_hike.values()
            )
            if len(points) >= 2
        ]

    if not geotagged_photos and not imported_route_groups:
        timestamped_photos = len([photo for photo in photos if photo.get("taken_at")])
        st.warning(
            "No map coordinates are available for the photos in view yet."
        )
        if photos:
            st.caption(
                f"{len(photos)} photos are loaded. {timestamped_photos} include capture times, but none of them currently include GPS coordinates."
            )
        return

    confirmed_species = []
    for photo in geotagged_photos:
        for observation in observations_by_photo.get(photo["id"], []):
            if observation.get("status") == "confirmed":
                confirmed_species.append((photo, observation))

    focused_photo_id = str(st.query_params.get("map_photo")) if st.query_params.get("map_photo") else None
    focused_index = None
    if focused_photo_id:
        ordered_for_focus = sorted(
            geotagged_photos,
            key=lambda photo: (photo.get("taken_at") or "", photo.get("created_at") or "", photo["id"]),
        )
        for index, photo in enumerate(ordered_for_focus, start=1):
            if photo["id"] == focused_photo_id:
                focused_index = index
                break

    unique_species = sorted(
        {
            observation.get("common_name") or observation.get("scientific_name") or "Confirmed species"
            for _, observation in confirmed_species
        }
    )
    valid_layer_modes = {"Both", "Photos", "Species"}
    if st.session_state.get("map_layer_mode") not in valid_layer_modes:
        st.session_state.map_layer_mode = "Both"
    valid_species_filters = {"All confirmed species", *unique_species}
    if st.session_state.get("map_species_filter") not in valid_species_filters:
        st.session_state.map_species_filter = "All confirmed species"
    control_cols = st.columns([0.26, 0.26, 0.22, 0.26], gap="small")
    layer_mode = control_cols[0].radio(
        "Map layer",
        ["Both", "Photos", "Species"],
        horizontal=True,
        label_visibility="collapsed",
        key="map_layer_mode",
    )
    species_filter = control_cols[1].selectbox(
        "Species filter",
        ["All confirmed species", *unique_species],
        label_visibility="collapsed",
        key="map_species_filter",
    )
    photo_count = len(geotagged_photos)
    max_index = max(1, photo_count)
    if focused_index:
        st.session_state.map_photo_range = (focused_index, focused_index)
    else:
        current_range = st.session_state.get("map_photo_range", (1, max_index))
        if not (
            isinstance(current_range, (tuple, list))
            and len(current_range) == 2
        ):
            current_range = (1, max_index)
        start_value = min(max(1, int(current_range[0])), max_index)
        end_value = min(max(start_value, int(current_range[1])), max_index)
        st.session_state.map_photo_range = (start_value, end_value)
    segment = control_cols[2].slider(
        "Photo range",
        min_value=1,
        max_value=max_index,
        key="map_photo_range",
        label_visibility="collapsed",
    )
    scope_label = "in this outing" if selected_hike else "across your library"
    control_cols[3].caption(f"{photo_count} geotagged photos • {len(unique_species)} unique species {scope_label}")

    ordered_photos = sorted(geotagged_photos, key=lambda photo: (photo.get("taken_at") or "", photo.get("created_at") or "", photo["id"]))
    start_index, end_index = segment
    segment_photos = ordered_photos[start_index - 1 : end_index]

    geotagged_points = []
    species_points = []
    route_groups: list[list[dict[str, Any]]] = []
    route_points = []
    route_points_by_hike: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sequence, photo in enumerate(segment_photos, start=start_index):
        primary_observation = primary_observation_by_photo.get(photo["id"])
        title = primary_observation.get("common_name") if primary_observation else "Trail photo"
        geotagged_points.append(
            {
                "photo_id": photo["id"],
                "hike_id": photo["hike_id"],
                "lat": photo["lat"],
                "lng": photo["lng"],
                "title": title,
                "subtitle": f"Photo {sequence} • {format_photo_meta(photo)}",
                "image_url": get_photo_thumbnail_url(photo),
            }
        )
        if selected_hike:
            route_points.append({"lat": photo["lat"], "lng": photo["lng"]})
        else:
            if photo.get("hike_id"):
                route_points_by_hike[str(photo["hike_id"])].append({"lat": photo["lat"], "lng": photo["lng"]})
        for observation in observations_by_photo.get(photo["id"], []):
            if observation.get("status") != "confirmed":
                continue
            species_name = observation.get("common_name") or observation.get("scientific_name") or "Confirmed species"
            if species_filter != "All confirmed species" and species_name != species_filter:
                continue
            role = "Primary" if observation.get("is_primary") else "Secondary"
            species_points.append(
                {
                    "photo_id": photo["id"],
                    "hike_id": photo["hike_id"],
                    "lat": photo["lat"],
                    "lng": photo["lng"],
                    "title": species_name,
                    "subtitle": f"{role} • {observation.get('scientific_name') or ''} • {format_confidence_label(observation)}",
                    "image_url": get_photo_thumbnail_url(photo),
                }
            )

    if layer_mode == "Photos":
        species_points = []
    elif layer_mode == "Species":
        geotagged_points = []

    if selected_hike:
        route_groups = imported_route_groups or ([route_points] if len(route_points) >= 2 else [])
    else:
        route_groups = list(imported_route_groups)
        for hike_id, points in route_points_by_hike.items():
            if hike_id in route_imports_by_hike:
                continue
            if len(points) >= 2:
                route_groups.append(points)

    render_rich_map(
        photos=photos,
        route_groups=route_groups,
        geotagged_points=geotagged_points,
        species_points=species_points,
        focused_photo_id=focused_photo_id,
        source_view="Map",
    )
    if focused_photo_id:
        st.caption("Centered on the photo you opened from the journal.")
        if "map_photo" in st.query_params:
            del st.query_params["map_photo"]
        if st.query_params.get("view") == "Map":
            del st.query_params["view"]


def render_species_log_tab(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    hikes: list[dict[str, Any]],
    species_log_context: dict[str, Any],
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
        "Your field guide",
        "Search by the name you know, then open one species record at a time to revisit where and when you found it.",
    )
    st.write("")

    all_species = species_log_context.get("all_species", [])
    species_rows = species_log_context.get("species_rows", [])
    representative_observations = species_log_context.get("representative_observations", {})
    posted_observations = species_log_context.get("posted_observations", [])
    if not all_species:
        st.info("Confirmed species will appear here once you begin reviewing photos.")
        return

    hike_options = ["All hikes", *[hike.get("title") or "Untitled hike" for hike in hikes]]
    valid_hike_filter = st.session_state.get("species_log_hike_filter", "All hikes")
    if valid_hike_filter not in hike_options:
        st.session_state.species_log_hike_filter = "All hikes"
    sort_options = ["Most recent", "Most seen", "A-Z", "Newest species first"]
    if st.session_state.get("species_log_sort") not in sort_options:
        st.session_state.species_log_sort = "Most recent"

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
        render_species_record_dialog(page_rows, species_lookup, representative_observations)
    if st.session_state.species_log_page_size == 0 and page_rows:
        render_back_to_top_link("species-log-top")


def render_species_log_inat_sync_panel(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    posted_observations: list[dict[str, Any]],
) -> None:
    candidates = st.session_state.get("inat_sync_candidates") or {}
    panel_cols = st.columns([0.54, 0.18, 0.14, 0.14], gap="small")
    panel_cols[0].markdown(
        (
            "<div class='utility-rail-status'>"
            f"{len(posted_observations)} posted iNaturalist record{'s' if len(posted_observations) != 1 else ''} can be checked for ID changes"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    if panel_cols[1].button(
        "Check iNaturalist IDs",
        key="inat_sync_check_species_log",
        use_container_width=True,
        disabled=not posted_observations or not is_inat_client_ready(inat_client),
    ):
        run_species_log_inat_sync(inat_client, posted_observations)
        st.rerun()
    if panel_cols[2].button(
        "Clear sync",
        key="inat_sync_clear_species_log",
        use_container_width=True,
        disabled=not candidates and not st.session_state.get("inat_sync_error") and not st.session_state.get("inat_sync_notice"),
    ):
        st.session_state.inat_sync_candidates = {}
        st.session_state.inat_sync_selected_ids = set()
        st.session_state.inat_sync_error = None
        st.session_state.inat_sync_notice = None
        st.session_state.inat_sync_checked_count = 0
        st.rerun()
    panel_cols[3].markdown(
        f"<div class='utility-rail-status'>{len(candidates)} change{'s' if len(candidates) != 1 else ''} found</div>",
        unsafe_allow_html=True,
    )

    if not is_inat_client_ready(inat_client):
        st.caption(inat_not_ready_message(inat_client).replace("using this action", "checking posted IDs"))
        if st.button(inat_connection_action_label(inat_client), key="inat_sync_connect", type="secondary"):
            open_inat_token_dialog()
    if st.session_state.get("inat_sync_error"):
        st.error(st.session_state.inat_sync_error)
    elif st.session_state.get("inat_sync_notice"):
        st.success(st.session_state.inat_sync_notice)

    if not candidates:
        return

    valid_ids = {str(candidate.get("observation_id") or "") for candidate in candidates.values() if candidate.get("observation_id")}
    st.session_state.inat_sync_selected_ids = {
        observation_id for observation_id in st.session_state.inat_sync_selected_ids if observation_id in valid_ids
    }
    st.session_state.inat_sync_selected_ids = {
        observation_id
        for observation_id in valid_ids
        if st.session_state.get(f"inat_sync_select_{observation_id}", observation_id in st.session_state.inat_sync_selected_ids)
    }
    selected_ids = set(st.session_state.inat_sync_selected_ids)
    queue_cols = st.columns([0.18, 0.18, 0.20, 0.20, 0.24], gap="small")
    queue_cols[0].markdown(
        f"<div class='utility-rail-status'>{len(selected_ids)} selected</div>",
        unsafe_allow_html=True,
    )
    if queue_cols[1].button("Select all", key="inat_sync_select_all", use_container_width=True, disabled=not valid_ids):
        st.session_state.inat_sync_selected_ids = set(valid_ids)
        for observation_id in valid_ids:
            st.session_state[f"inat_sync_select_{observation_id}"] = True
        st.rerun()
    if queue_cols[2].button("Clear selected", key="inat_sync_clear_selected", use_container_width=True, disabled=not selected_ids):
        st.session_state.inat_sync_selected_ids = set()
        for observation_id in valid_ids:
            checkbox_key = f"inat_sync_select_{observation_id}"
            if checkbox_key in st.session_state:
                st.session_state[checkbox_key] = False
        st.rerun()
    if queue_cols[3].button(f"Update selected ({len(selected_ids)})", key="inat_sync_update_selected", use_container_width=True, disabled=not selected_ids):
        update_inat_sync_candidates(repository, inat_client, selected_ids)
        st.rerun()
    if queue_cols[4].button(f"Skip selected ({len(selected_ids)})", key="inat_sync_skip_selected", use_container_width=True, disabled=not selected_ids):
        for observation_id in selected_ids:
            st.session_state.inat_sync_candidates.pop(observation_id, None)
            st.session_state.inat_sync_selected_ids.discard(observation_id)
        st.session_state.inat_sync_notice = f"Skipped {len(selected_ids)} iNaturalist ID change{'s' if len(selected_ids) != 1 else ''}."
        st.session_state.inat_sync_error = None
        st.rerun()

    st.markdown(
        "<div class='species-log-detail-head'><p class='workspace-lane-label'>iNaturalist ID changes</p></div>",
        unsafe_allow_html=True,
    )
    for candidate in list(candidates.values()):
        observation_id = str(candidate.get("observation_id") or "")
        local = candidate.get("local") or {}
        inat = candidate.get("inat") or {}
        local_label = format_taxon_sync_label(local)
        inat_label = format_taxon_sync_label(inat)
        select_key = f"inat_sync_select_{observation_id}"
        if select_key not in st.session_state:
            st.session_state[select_key] = observation_id in st.session_state.inat_sync_selected_ids
        row_cols = st.columns([0.10, 0.26, 0.26, 0.16, 0.11, 0.11], gap="small")
        is_selected = row_cols[0].checkbox("Select", key=select_key)
        if is_selected:
            st.session_state.inat_sync_selected_ids.add(observation_id)
        else:
            st.session_state.inat_sync_selected_ids.discard(observation_id)
        row_cols[1].markdown(f"**HikeJournal**  \n{local_label}")
        row_cols[2].markdown(f"**iNaturalist now**  \n{inat_label}")
        link = candidate.get("inat_observation_url")
        if link:
            row_cols[3].markdown(f"[View on iNaturalist]({link})")
        else:
            row_cols[3].caption(f"iNat #{candidate.get('inat_observation_id') or 'unknown'}")
        if row_cols[4].button("Update", key=f"inat_sync_apply_{observation_id}", use_container_width=True):
            update_inat_sync_candidates(repository, inat_client, {observation_id})
            st.rerun()
        if row_cols[5].button("Skip", key=f"inat_sync_skip_{observation_id}", use_container_width=True):
            st.session_state.inat_sync_candidates.pop(observation_id, None)
            st.session_state.inat_sync_selected_ids.discard(observation_id)
            st.session_state.inat_sync_notice = "Skipped that iNaturalist ID change."
            st.session_state.inat_sync_error = None
            st.rerun()


def update_inat_sync_candidates(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    observation_ids: set[str],
) -> None:
    candidates = st.session_state.get("inat_sync_candidates") or {}
    updated_count = 0
    for observation_id in list(observation_ids):
        candidate = candidates.get(observation_id)
        if not candidate:
            st.session_state.inat_sync_selected_ids.discard(observation_id)
            continue
        inat = candidate.get("inat") or {}
        try:
            updated = repository.apply_observation_inat_sync(observation_id, inat_snapshot=inat)
            ensure_taxon_enrichment(repository, inat_client, updated)
        except Exception as exc:
            st.session_state.inat_sync_error = f"Could not update {inat.get('common_name') or inat.get('scientific_name') or 'one iNaturalist record'}: {exc}"
            break
        else:
            updated_count += 1
            st.session_state.inat_sync_candidates.pop(observation_id, None)
            st.session_state.inat_sync_selected_ids.discard(observation_id)
    if updated_count:
        st.session_state.inat_sync_notice = f"Updated {updated_count} HikeJournal ID{'s' if updated_count != 1 else ''} from iNaturalist."
        if not st.session_state.get("inat_sync_error"):
            st.session_state.inat_sync_error = None
        invalidate_data_cache()


def run_species_log_inat_sync(inat_client: InatClient, posted_observations: list[dict[str, Any]]) -> None:
    st.session_state.inat_sync_candidates = {}
    st.session_state.inat_sync_selected_ids = set()
    st.session_state.inat_sync_error = None
    st.session_state.inat_sync_notice = None
    st.session_state.inat_sync_checked_count = 0
    try:
        inat_client.validate_credentials()
    except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
        st.session_state.inat_sync_error = str(exc)
        return

    observations_by_inat_id = {
        str(observation.get("inat_observation_id")): observation
        for observation in posted_observations
        if observation.get("inat_observation_id")
    }
    progress = st.progress(0, text="Checking iNaturalist IDs...")
    total = len(observations_by_inat_id)
    checked = 0
    candidates: dict[str, dict[str, Any]] = {}
    try:
        for batch_ids in chunk_list(list(observations_by_inat_id), 30):
            remote_observations = inat_client.fetch_observations(batch_ids)
            remote_by_id = {str(remote.get("id")): remote for remote in remote_observations if remote.get("id") is not None}
            for inat_id in batch_ids:
                checked += 1
                local_observation = observations_by_inat_id[inat_id]
                remote_observation = remote_by_id.get(str(inat_id))
                if remote_observation:
                    candidate = build_observation_sync_candidate(local_observation, remote_observation)
                    if candidate and candidate.get("observation_id"):
                        candidates[str(candidate["observation_id"])] = candidate
                        st.session_state.inat_sync_candidates = dict(candidates)
                progress.progress(checked / max(total, 1), text=f"Checked {checked} of {total} iNaturalist records")
    except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
        st.session_state.inat_sync_error = f"iNaturalist sync stopped after {checked} of {total} records: {exc}"
        st.session_state.inat_sync_checked_count = checked
        progress.empty()
        return

    st.session_state.inat_sync_candidates = candidates
    st.session_state.inat_sync_checked_count = checked
    st.session_state.inat_sync_notice = f"Checked {checked} posted iNaturalist records and found {len(candidates)} ID change{'s' if len(candidates) != 1 else ''}."
    progress.empty()


def format_taxon_sync_label(payload: dict[str, Any]) -> str:
    common_name = str(payload.get("common_name") or "").strip()
    scientific_name = str(payload.get("scientific_name") or "").strip()
    taxon_id = payload.get("taxon_id")
    pieces = [item for item in [common_name, scientific_name] if item]
    label = " / ".join(pieces) if pieces else "Unknown ID"
    if taxon_id not in (None, ""):
        label = f"{label} (`{taxon_id}`)"
    return label


def chunk_list(values: list[Any], size: int) -> list[list[Any]]:
    return [values[start:start + size] for start in range(0, len(values), size)]


def dismiss_species_record_dialog() -> None:
    st.session_state.species_log_record_open = False


@st.dialog("Species record", width="large", on_dismiss=dismiss_species_record_dialog)
def render_species_record_dialog(
    page_rows: list[dict[str, Any]],
    species_lookup: dict[str, dict[str, Any]],
    representative_observations: dict[str, dict[str, Any]],
) -> None:
    if not page_rows or st.session_state.species_log_focus_key not in species_lookup:
        st.session_state.species_log_record_open = False
        return

    page_keys = [row["key"] for row in page_rows]
    focus_row = species_lookup[st.session_state.species_log_focus_key]
    observation = representative_observations.get(focus_row["representative_id"], focus_row["observation"])
    common_name = focus_row["common_name"]
    scientific_name = focus_row["scientific_name"]
    lead_photo = focus_row["lead_photo"]
    focus_index = page_keys.index(st.session_state.species_log_focus_key)

    focus_nav_cols = st.columns([0.58, 0.14, 0.14, 0.14], gap="small")
    focus_nav_cols[0].markdown(
        f"""
        <div class='species-log-focus-rail'>
            <p class='workspace-lane-label'>Open record</p>
            <p class='species-log-focus-caption'>Viewing {focus_index + 1} of {len(page_rows)} species on this page.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    prev_disabled = focus_index <= 0
    next_disabled = focus_index >= len(page_rows) - 1
    if focus_nav_cols[1].button("Previous", key="species_log_prev_record", use_container_width=True, disabled=prev_disabled):
        st.session_state.species_log_focus_key = page_keys[focus_index - 1]
        st.session_state.species_log_record_open = True
        set_species_log_record_query_state(page_keys[focus_index - 1], True)
        st.rerun()
    if focus_nav_cols[2].button("Next", key="species_log_next_record", use_container_width=True, disabled=next_disabled):
        st.session_state.species_log_focus_key = page_keys[focus_index + 1]
        st.session_state.species_log_record_open = True
        set_species_log_record_query_state(page_keys[focus_index + 1], True)
        st.rerun()
    if focus_nav_cols[3].button("Close", key="species_log_close_record", use_container_width=True):
        st.session_state.species_log_record_open = False
        set_species_log_record_query_state(st.session_state.species_log_focus_key, False)
        st.rerun()

    st.markdown("<div class='species-record-dialog-shell'>", unsafe_allow_html=True)
    summary_cols = st.columns([0.24, 0.76], gap="large")
    with summary_cols[0]:
        render_clickable_photo_with_view(
            lead_photo,
            selected_hike_id=None,
            source_view="Species Log",
            variant="species-log-lead",
        )
    with summary_cols[1]:
        st.markdown(
            f"""
            <div class='species-log-header'>
                <div class='species-log-kicker'>Species record</div>
                <p class='species-log-title'>{escape(common_name)}</p>
                {f"<p class='species-log-subtitle'>{escape(scientific_name)}</p>" if scientific_name else ""}
                <div class='species-log-stats'>
                    <span>{focus_row['sighting_count']} sighting{'s' if focus_row['sighting_count'] != 1 else ''}</span>
                    <span>{focus_row['hike_count']} hike{'s' if focus_row['hike_count'] != 1 else ''}</span>
                    <span>First seen {escape(focus_row['first_seen_label'])}</span>
                    <span>Last seen {escape(focus_row['last_seen_label'])}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        enrichment = get_taxon_enrichment(observation)
        if enrichment:
            alias_names = enrichment.get("alias_names") or []
            alias_names = [alias for alias in alias_names if alias and alias.lower() != common_name.lower()]
            if alias_names:
                st.caption("Also known as: " + ", ".join(alias_names[:5]))
            wikipedia_url = enrichment.get("wikipedia_url")
            wiki_summary = enrichment.get("wikipedia_summary")
            utility_parts = []
            if wikipedia_url:
                utility_parts.append(f"<a href='{escape(str(wikipedia_url))}' target='_blank' rel='noopener noreferrer'>Wikipedia</a>")
            if get_inat_posting(observation).get("observation_url"):
                utility_parts.append(
                    f"<a href='{escape(str(get_inat_posting(observation)['observation_url']))}' target='_blank' rel='noopener noreferrer'>iNaturalist</a>"
                )
            if utility_parts:
                st.markdown(
                    f"<div class='species-log-guide-links'>{' '.join(utility_parts)}</div>",
                    unsafe_allow_html=True,
                )
            if wiki_summary:
                st.markdown(
                    f"<div class='species-log-guide-summary'>{escape(clean_summary_text(wiki_summary))}</div>",
                    unsafe_allow_html=True,
                )

    st.markdown(
        "<div class='species-log-detail-head'><p class='workspace-lane-label'>Encounters</p></div>",
        unsafe_allow_html=True,
    )
    for encounter_index, encounter in enumerate(focus_row["encounters"]):
        encounter_hike = encounter["hike"]
        lead_entry = encounter["entries"][0]
        is_standalone = not bool(encounter_hike.get("id"))
        outing_title = encounter_hike.get("title") or ("Standalone sighting" if is_standalone else "Hike")
        outing_location = encounter_hike.get("location_name") or (lead_entry["photo"].get("caption") or ("Not attached to a hike" if is_standalone else "Unknown location"))
        outing_date = encounter_hike.get("hike_date") or format_species_log_date_label(_entry_sort_datetime(lead_entry))
        outing_href = f"?view=Journal&hike={quote(str(encounter_hike.get('id') or ''))}" if encounter_hike.get("id") else ""
        map_href = (
            f"?view=Map&hike={quote(str(encounter_hike.get('id') or ''))}"
            if encounter_hike.get("id")
            else f"?view=Map&scope=global&map_photo={quote(str(lead_entry['photo']['id']))}"
        )
        supporting_entries = encounter["entries"][1:3]
        has_supporting_photos = len(supporting_entries) > 0
        encounter_cols = st.columns([0.16, 0.54, 0.30], gap="medium") if has_supporting_photos else st.columns([0.16, 0.84], gap="medium")
        with encounter_cols[0]:
            render_clickable_photo_with_view(
                lead_entry["photo"],
                selected_hike_id=None,
                source_view="Species Log",
                variant="species-log-encounter-lead",
            )
        with encounter_cols[1]:
            st.markdown(
                f"""
                <div class='species-log-encounter-head'>
                    <p class='species-log-encounter-title'>{escape(outing_title)}</p>
                    <p class='species-log-encounter-meta'>{escape(outing_location)} • {escape(outing_date)} • 
                    {len(encounter['entries'])} photo{'s' if len(encounter['entries']) != 1 else ''}</p>
                    <div class='species-log-actions'>{'' if is_standalone else f"<a href='{outing_href}' target='_self'>Open outing</a>"}
                    <a href='{map_href}' target='_self'>Open outing map</a></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if lead_entry["photo"].get("lat") is not None and lead_entry["photo"].get("lng") is not None:
                st.markdown(
                    f"<p class='photo-meta'>{format_photo_meta_html(lead_entry['photo'], selected_hike_id=encounter_hike.get('id'), link_coordinates=True, include_map_link=True)}</p>",
                    unsafe_allow_html=True,
                )
            if not has_supporting_photos:
                st.markdown(
                    "<div class='species-log-single-note'>Single-photo encounter</div>",
                    unsafe_allow_html=True,
                )
        if has_supporting_photos:
            with encounter_cols[2]:
                thumb_cols = st.columns(2, gap="small")
                for idx, entry in enumerate(supporting_entries):
                    with thumb_cols[idx]:
                        render_clickable_photo_with_view(
                            entry["photo"],
                            selected_hike_id=None,
                            source_view="Species Log",
                            variant="species-log-thumb",
                        )
                st.markdown("<div class='species-log-thumb-label'>More from this outing</div>", unsafe_allow_html=True)
                if len(encounter["entries"]) > 3:
                    st.markdown(
                        f"<div class='species-log-more'>+{len(encounter['entries']) - 3} more photo{'s' if len(encounter['entries']) - 3 != 1 else ''}</div>",
                        unsafe_allow_html=True,
                    )
        if encounter_index < len(focus_row["encounters"]) - 1:
            st.divider()
    st.markdown("</div>", unsafe_allow_html=True)


@st.dialog("Photo Viewer", width="large")
def render_photo_viewer(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
) -> None:
    if not photos:
        st.session_state.viewer_open = False
        return

    st.session_state.viewer_index = max(0, min(st.session_state.viewer_index, len(photos) - 1))
    photo = photos[st.session_state.viewer_index]
    primary_observation = primary_observation_by_photo.get(photo["id"])
    photo_observations = observations_by_photo.get(photo["id"], [])
    if st.session_state.get("viewer_notice"):
        st.success(str(st.session_state.viewer_notice))
        st.session_state.viewer_notice = None
    if st.session_state.get("active_view") == "Species Log":
        st.markdown(
            "<div class='viewer-context'>Opened from Species Log. Close returns you to your filtered results.</div>",
            unsafe_allow_html=True,
        )

    image_cols = st.columns([0.12, 0.76, 0.12])
    with image_cols[1]:
        st.image(photo["public_url"], width=720)
        viewer_links = st.columns(4, gap="small")
        viewer_links[0].link_button("Open full-size image", photo["public_url"], use_container_width=True)
        if photo.get("hike_id"):
            if viewer_links[1].button("Open outing", use_container_width=True, key=f"viewer_outing_{photo['id']}"):
                navigate_to(view="Journal", hike_id=photo["hike_id"], photo_id=photo["id"])
        if photo.get("lat") is not None and photo.get("lng") is not None:
            if viewer_links[2].button("Open on map", use_container_width=True, key=f"viewer_map_{photo['id']}"):
                navigate_to(view="Map", hike_id=photo.get("hike_id"), map_photo_id=photo["id"])
        if photo.get("hike_id"):
            if viewer_links[3].button("Use as cover", use_container_width=True, key=f"viewer_cover_{photo['id']}"):
                try:
                    repository.update_hike_cover_photo(photo["hike_id"], photo["id"])
                except Exception as exc:
                    st.error(f"Cover photos need the new library migration before they can be saved: {exc}")
                    return
                invalidate_data_cache()
                st.session_state.viewer_open = True
                st.session_state.viewer_notice = "Saved this as the hike cover photo."
                st.rerun()
    st.markdown(f"<p class='photo-meta'>{format_photo_meta(photo)}</p>", unsafe_allow_html=True)
    render_photo_note_editor(repository, photo, key_prefix=f"viewer_note_{photo['id']}")
    if primary_observation:
        render_species_summary(
            repository,
            primary_observation,
            inat_client=inat_client,
            photo=photo,
            key_prefix=f"viewer_{photo['id']}",
            show_details=True,
        )
        render_alternate_suggestions(repository, inat_client, primary_observation, photo, key_prefix=f"viewer_{photo['id']}")
        render_secondary_species_summary(photo_observations, primary_observation["id"])
        render_add_species_popover(repository, inat_client, photo.get("hike_id"), photo, photo_observations, key_prefix=f"viewer_add_{photo['id']}")
    else:
        st.caption("No species has been attached to this photo yet.")
        render_add_species_popover(repository, inat_client, photo.get("hike_id"), photo, photo_observations, key_prefix=f"viewer_add_{photo['id']}")

    controls = st.columns([1, 1, 1, 1])
    if controls[0].button("Previous", use_container_width=True, key="viewer_previous"):
        st.session_state.viewer_index = (st.session_state.viewer_index - 1) % len(photos)
        st.session_state.viewer_open = True
        st.query_params["photo"] = photos[st.session_state.viewer_index]["id"]
        st.rerun()
    controls[1].markdown(f"<div class='photo-meta' style='padding-top:0.85rem; text-align:center;'>{st.session_state.viewer_index + 1} / {len(photos)}</div>", unsafe_allow_html=True)
    if controls[2].button("Next", use_container_width=True, key="viewer_next"):
        st.session_state.viewer_index = (st.session_state.viewer_index + 1) % len(photos)
        st.session_state.viewer_open = True
        st.query_params["photo"] = photos[st.session_state.viewer_index]["id"]
        st.rerun()
    if controls[3].button("Close", use_container_width=True, key="viewer_close"):
        st.session_state.viewer_open = False
        for key, value in get_query_state_for_view(st.session_state.active_view).items():
            if value == "":
                if key in st.query_params:
                    del st.query_params[key]
            else:
                st.query_params[key] = value
        if "photo" in st.query_params:
            del st.query_params["photo"]
        st.rerun()


def render_selection_toolbar(repository: HikeJournalRepository, photos: list[dict[str, Any]], prefix: str) -> None:
    if not photos:
        return
    photo_ids = [photo["id"] for photo in photos]
    selected_count = len([photo for photo in photos if photo.get("processing_status") == REVIEW_QUEUE_STATUS])
    cols = st.columns([0.36, 0.18, 0.18, 0.28], gap="small")
    cols[0].caption(f"{selected_count} of {len(photo_ids)} photos selected for species review")
    if cols[1].button("Queue whole hike", key=f"{prefix}_select_all", use_container_width=True):
        repository.update_photo_processing_statuses(photo_ids, REVIEW_QUEUE_STATUS)
        reset_journal_review_widget_state(photo_ids)
        invalidate_data_cache()
        st.rerun()
    if cols[2].button("Clear hike", key=f"{prefix}_clear_selection", use_container_width=True):
        repository.update_photo_processing_statuses(photo_ids, "ready")
        reset_journal_review_widget_state(photo_ids)
        invalidate_data_cache()
        st.rerun()


def sync_journal_review_checkbox(
    repository: HikeJournalRepository,
    photo_id: str,
    checkbox_key: str,
) -> None:
    is_selected = bool(st.session_state.get(checkbox_key))
    new_status = REVIEW_QUEUE_STATUS if is_selected else "ready"
    repository.update_photo_processing_status(photo_id, new_status)
    invalidate_data_cache()


def reset_journal_review_widget_state(photo_ids: list[str]) -> None:
    for photo_id in photo_ids:
        checkbox_key = f"photo_select_{photo_id}"
        if checkbox_key in st.session_state:
            del st.session_state[checkbox_key]


def render_species_summary(
    repository: HikeJournalRepository,
    observation: dict[str, Any],
    *,
    inat_client: InatClient,
    photo: dict[str, Any],
    place_guess: str | None = None,
    key_prefix: str,
    show_details: bool,
    show_confidence: bool = True,
) -> None:
    render_observation_badge(observation.get("status", "pending"))
    confidence = format_confidence_label(observation) if show_confidence else "&nbsp;"
    info_cols = st.columns([0.88, 0.12], gap="small")
    with info_cols[0]:
        enrichment = get_taxon_enrichment(observation)
        manual_override = get_manual_species_override(observation)
        common_name = escape(observation.get("common_name") or "Unknown species")
        scientific_name = escape(observation.get("scientific_name") or "")
        meta_bits = [escape(bit) for bit in [enrichment.get("rank"), enrichment.get("iconic_taxon_name")] if bit]
        meta_line = " • ".join(meta_bits)
        publish_chip = render_publish_state_chip(get_publish_state(observation)) if observation.get("status") == "confirmed" else ""
        st.markdown(
            f"""
            <div class="species-summary-block">
                <div class="species-summary-name">{common_name}</div>
                <div class="species-summary-scientific">{scientific_name}</div>
                <div class="species-summary-confidence">{confidence}</div>
                <div class="species-summary-meta">{meta_line or '&nbsp;'}</div>
                {f"<div class='publish-state-line'>{publish_chip}</div>" if publish_chip else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )
        if show_details:
            if manual_override:
                st.markdown(
                    "<div class='species-detail'><strong>Manual correction:</strong> reference notes were cleared so this entry does not show details from the earlier identification.</div>",
                    unsafe_allow_html=True,
                )
            else:
                alias_names = enrichment.get("alias_names") or []
                alias_names = [alias for alias in alias_names if alias and alias.lower() != (observation.get("common_name") or "").lower()]
                if alias_names:
                    st.markdown(f"<div class='species-detail'><strong>Also known as:</strong> {escape(', '.join(alias_names[:6]))}</div>", unsafe_allow_html=True)
                wikipedia_url = enrichment.get("wikipedia_url")
                if wikipedia_url:
                    st.markdown(f"<a class='viewer-link' href='{wikipedia_url}' target='_blank' rel='noopener noreferrer'>Read more on Wikipedia</a>", unsafe_allow_html=True)
                wikipedia_summary = enrichment.get("wikipedia_summary")
                if wikipedia_summary:
                    st.markdown(f"<div class='species-detail'>{escape(clean_summary_text(wikipedia_summary))}</div>", unsafe_allow_html=True)
        render_inat_posting_controls(
            repository,
            inat_client,
            observation,
            photo,
            place_guess=place_guess,
            key_prefix=key_prefix,
        )
    with info_cols[1]:
        with st.popover("✎"):
            with st.form(f"{key_prefix}_species_form", enter_to_submit=False):
                common_name = st.text_input("Common name", value=observation.get("common_name") or "", key=f"{key_prefix}_common_name")
                scientific_name = st.text_input("Scientific name", value=observation.get("scientific_name") or "", key=f"{key_prefix}_scientific_name")
                role = st.selectbox(
                    "Role",
                    ["Primary subject", "Secondary species"],
                    index=0 if observation.get("is_primary") else 1,
                    key=f"{key_prefix}_role",
                )
                if st.form_submit_button("Save species info", use_container_width=True):
                    original_common = (observation.get("common_name") or "").strip()
                    original_scientific = (observation.get("scientific_name") or "").strip()
                    next_common = common_name.strip()
                    next_scientific = scientific_name.strip()
                    changed_names = (next_common != original_common) or (next_scientific != original_scientific)
                    manual_correction_from_rejected = changed_names and observation.get("status") == "rejected"
                    updated = repository.update_observation_details(
                        observation["id"],
                        common_name=common_name,
                        scientific_name=scientific_name,
                        photo_id=observation.get("photo_id"),
                        is_primary=role == "Primary subject",
                        status="confirmed" if manual_correction_from_rejected else None,
                        source="manual_override" if manual_correction_from_rejected else None,
                        taxon_id=None if manual_correction_from_rejected else observation.get("taxon_id"),
                        clear_confidence=manual_correction_from_rejected,
                    )
                    sync_species_override_payload(repository, observation, updated)
                    invalidate_data_cache()
                    st.rerun()


def render_secondary_species_summary(photo_observations: list[dict[str, Any]], primary_observation_id: str | None) -> None:
    secondary_observations = [
        observation
        for observation in photo_observations
        if observation.get("id") != primary_observation_id
    ]
    if not secondary_observations:
        return
    labels = []
    for observation in secondary_observations:
        name = observation.get("common_name") or observation.get("scientific_name") or "Unnamed species"
        role = "secondary"
        status = observation.get("status") or "pending"
        labels.append(f"{name} ({role}, {status})")
    st.caption("Also seen in this photo: " + ", ".join(labels))


def render_photo_note_editor(
    repository: HikeJournalRepository,
    photo: dict[str, Any],
    *,
    key_prefix: str,
) -> None:
    note = str(photo.get("caption") or "").strip()
    if note:
        st.markdown(
            f"<div class='species-detail'><strong>Photo note:</strong> {escape(note)}</div>",
            unsafe_allow_html=True,
        )
    with st.popover("Photo note"):
        with st.form(f"{key_prefix}_photo_note_form", enter_to_submit=False):
            updated_note = st.text_area(
                "Photo note",
                value=note,
                height=140,
                placeholder="Add a location detail, habitat note, behavior, or anything worth remembering.",
                key=f"{key_prefix}_photo_note_value",
            )
            if st.form_submit_button("Save photo note", use_container_width=True):
                repository.update_photo_caption(photo["id"], updated_note)
                invalidate_data_cache()
                if key_prefix.startswith("viewer_"):
                    st.session_state.viewer_open = True
                    st.session_state.viewer_notice = "Saved the photo note."
                st.rerun()


def get_alternate_inat_suggestions(observation: dict[str, Any], *, limit: int = 4) -> list[SpeciesCandidate]:
    raw_payload = observation.get("raw_response_json") or {}
    if not isinstance(raw_payload, dict) or raw_payload.get("manual_override"):
        return []
    if raw_payload.get("grouped_cv") and isinstance(raw_payload.get("aggregate_candidates"), list):
        candidates: list[SpeciesCandidate] = []
        for item in raw_payload.get("aggregate_candidates") or []:
            if not isinstance(item, dict):
                continue
            try:
                confidence = float(item.get("average_confidence") or item.get("confidence") or 0)
            except (TypeError, ValueError):
                confidence = 0.0
            candidates.append(
                SpeciesCandidate(
                    common_name=str(item.get("common_name") or item.get("scientific_name") or "Unknown species"),
                    scientific_name=str(item.get("scientific_name") or item.get("common_name") or "Unknown species"),
                    confidence=confidence,
                    taxon_id=item.get("taxon_id"),
                    raw_payload=raw_payload,
                )
            )
        candidates = candidates[: limit + 1]
    else:
        try:
            candidates = parse_candidates(raw_payload, limit=limit + 1)
        except Exception:
            return []
    current_taxon_id = observation.get("taxon_id")
    current_name = (observation.get("scientific_name") or observation.get("common_name") or "").strip().lower()
    alternates: list[SpeciesCandidate] = []
    for candidate in candidates:
        if current_taxon_id is not None and candidate.taxon_id == current_taxon_id:
            continue
        candidate_name = (candidate.scientific_name or candidate.common_name or "").strip().lower()
        if current_name and candidate_name == current_name:
            continue
        alternates.append(candidate)
        if len(alternates) >= limit:
            break
    return alternates


def render_alternate_suggestions(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    observation: dict[str, Any],
    photo: dict[str, Any],
    *,
    key_prefix: str,
) -> None:
    alternates = get_alternate_inat_suggestions(observation)
    if not alternates:
        return
    st.markdown(
        """
        <div class="alternate-suggestions-shell">
            <p class="workspace-lane-label">Other iNaturalist suggestions</p>
            <p class="alternate-suggestions-caption">Pick another top guess if it looks better, then save it without reprocessing.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    option_ids = [""] + [str(candidate.taxon_id) for candidate in alternates]
    candidate_by_id = {str(candidate.taxon_id): candidate for candidate in alternates}
    selected_candidate_id = st.selectbox(
        "Other iNaturalist suggestions",
        option_ids,
        key=f"{key_prefix}_alternate_choice",
        label_visibility="collapsed",
        format_func=lambda value: (
            "Choose another iNaturalist suggestion"
            if value == ""
            else f"{candidate_by_id[value].common_name or candidate_by_id[value].scientific_name} · {format_confidence_percent(candidate_by_id[value].confidence)}"
        ),
    )
    chosen_candidate = candidate_by_id.get(selected_candidate_id)
    if chosen_candidate:
        common_name = chosen_candidate.common_name or chosen_candidate.scientific_name
        scientific_name = chosen_candidate.scientific_name or ""
        scientific_markup = f" <em>{escape(scientific_name)}</em>" if scientific_name else ""
        cols = st.columns([0.7, 0.3], gap="small")
        cols[0].markdown(
            f"<div class='alternate-suggestion-meta'><strong>{escape(common_name)}</strong>{scientific_markup}</div>",
            unsafe_allow_html=True,
        )
        if cols[1].button("Use suggestion", key=f"{key_prefix}_alt_apply_{chosen_candidate.taxon_id}", use_container_width=True):
            next_status = "confirmed" if observation.get("status") == "confirmed" else "pending"
            updated = repository.apply_candidate_to_observation(
                observation["id"],
                photo_id=photo["id"],
                candidate=chosen_candidate,
                status=next_status,
                is_primary=bool(observation.get("is_primary")),
            )
            ensure_taxon_enrichment(repository, inat_client, updated)
            invalidate_data_cache()
            if key_prefix.startswith("viewer_"):
                st.session_state.viewer_open = True
                st.session_state.viewer_notice = f"Saved {common_name} from iNaturalist suggestions."
            st.rerun()


def render_add_species_popover(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    hike_id: str | None,
    photo: dict[str, Any],
    photo_observations: list[dict[str, Any]],
    *,
    key_prefix: str,
) -> None:
    existing_taxon_ids = {int(observation["taxon_id"]) for observation in photo_observations if observation.get("taxon_id") is not None}
    with st.popover("Add another species"):
        query = st.text_input("Search species", key=f"{key_prefix}_query", placeholder="Bee, duck potato, Vaccinium...")
        results: list[dict[str, Any]] = []
        if query.strip():
            try:
                results = [item for item in inat_client.autocomplete_taxa(query) if item.get("id") is not None][:8]
            except Exception:
                results = []
        if not query.strip():
            st.caption("Search by common name or scientific name.")
            return
        if not results:
            st.caption("No matching species came back for that search.")
            return

        def _format_taxon_option(option: dict[str, Any]) -> str:
            common_name = option.get("preferred_common_name") or option.get("matched_term") or option.get("name") or "Unknown species"
            scientific_name = option.get("name") or ""
            rank = option.get("rank") or ""
            return f"{common_name} — {scientific_name} {f'({rank})' if rank else ''}".strip()

        selected_taxon = st.selectbox(
            "Matches",
            results,
            format_func=_format_taxon_option,
            key=f"{key_prefix}_selected_taxon",
        )
        current_primary = get_primary_observation(photo_observations)
        default_primary = (
            not any(observation.get("is_primary") for observation in photo_observations)
            or (current_primary or {}).get("status") == "rejected"
        )
        with st.form(f"{key_prefix}_add_species_form", enter_to_submit=False):
            role = st.selectbox(
                "Add as",
                ["Secondary species", "Primary subject"],
                index=1 if default_primary else 0,
                key=f"{key_prefix}_add_role",
            )
            status = st.selectbox(
                "Review state",
                ["confirmed", "pending"],
                index=0,
                key=f"{key_prefix}_add_status",
                format_func=lambda value: "Confirmed" if value == "confirmed" else "Pending",
            )
            duplicate = int(selected_taxon["id"]) in existing_taxon_ids
            if duplicate:
                st.caption("That species is already attached to this photo.")
            if st.form_submit_button("Add species", use_container_width=True, disabled=duplicate):
                try:
                    observation = repository.create_manual_observation(
                        hike_id=hike_id,
                        photo_id=photo["id"],
                        owner_subject=photo.get("owner_subject"),
                        owner_email=photo.get("owner_email"),
                        taxon_id=int(selected_taxon["id"]),
                        common_name=str(selected_taxon.get("preferred_common_name") or selected_taxon.get("matched_term") or selected_taxon.get("name") or "Unknown species"),
                        scientific_name=str(selected_taxon.get("name") or selected_taxon.get("preferred_common_name") or "Unknown species"),
                        source="manual_add",
                        raw_payload={"manual_taxon": selected_taxon},
                        is_primary=role == "Primary subject",
                        status=status,
                    )
                except RuntimeError as exc:
                    st.error(str(exc))
                else:
                    ensure_taxon_enrichment(repository, inat_client, observation)
                    invalidate_data_cache()
                    st.rerun()


def render_community_id_request_controls(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    observation: dict[str, Any],
    photo: dict[str, Any],
    *,
    key_prefix: str,
) -> None:
    if observation.get("status") != "pending":
        return
    st.markdown(
        """
        <div class="alternate-suggestions-shell">
            <p class="workspace-lane-label">Send to iNaturalist for ID</p>
            <p class="alternate-suggestions-caption">Replace the current suggestion with an unknown or broader taxon, then move it to publishing.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.popover("Submit as..."):
        mode = st.radio(
            "Submit as",
            ["Unknown organism", "Broad taxon"],
            key=f"{key_prefix}_mode",
            horizontal=True,
        )
        selected_taxon: dict[str, Any] | None = None
        if mode == "Broad taxon":
            query = st.text_input(
                "Search iNaturalist taxon",
                key=f"{key_prefix}_query",
                placeholder="Plants, Animals, Fungi, Rhexia...",
            )
            results: list[dict[str, Any]] = []
            if query.strip():
                try:
                    results = [item for item in inat_client.autocomplete_taxa(query) if item.get("id") is not None][:10]
                except Exception as exc:
                    st.caption(f"Taxon search did not come back cleanly: {exc}")
            else:
                st.caption("Search for a broad group or genus. Examples: Plants, Fungi, Reptiles, Rhexia.")
            if results:
                selected_taxon = st.selectbox(
                    "Taxon match",
                    results,
                    format_func=format_taxon_option,
                    key=f"{key_prefix}_selected_taxon",
                )
            elif query.strip():
                st.caption("No matching taxa came back.")

        ready_to_submit = mode == "Unknown organism" or selected_taxon is not None
        if st.button("Move to publishing", key=f"{key_prefix}_submit", use_container_width=True, disabled=not ready_to_submit):
            apply_community_id_request(
                repository,
                inat_client,
                observation,
                photo,
                selected_taxon=selected_taxon,
            )
            st.session_state.species_selected_ids.discard(photo["id"])
            st.session_state.species_review_stage = "Needs decisions"
            invalidate_data_cache()
            st.rerun()


def format_taxon_option(option: dict[str, Any]) -> str:
    common_name = option.get("preferred_common_name") or option.get("matched_term") or option.get("name") or "Unknown taxon"
    scientific_name = option.get("name") or ""
    rank = option.get("rank") or ""
    if scientific_name and scientific_name != common_name:
        label = f"{common_name} — {scientific_name}"
    else:
        label = str(common_name)
    return f"{label} {f'({rank})' if rank else ''}".strip()


def apply_community_id_request(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    observation: dict[str, Any],
    photo: dict[str, Any],
    *,
    selected_taxon: dict[str, Any] | None,
) -> dict[str, Any]:
    if selected_taxon:
        common_name = str(selected_taxon.get("preferred_common_name") or selected_taxon.get("matched_term") or selected_taxon.get("name") or "Unknown taxon")
        scientific_name = str(selected_taxon.get("name") or selected_taxon.get("preferred_common_name") or common_name)
        taxon_id = int(selected_taxon["id"])
        request_payload = {"mode": "broad_taxon", "selected_taxon": selected_taxon}
    else:
        common_name = "Unknown organism"
        scientific_name = ""
        taxon_id = None
        request_payload = {"mode": "unknown_organism", "selected_taxon": None}

    updated = repository.update_observation_details(
        observation["id"],
        common_name=common_name,
        scientific_name=scientific_name,
        photo_id=photo.get("id"),
        is_primary=True,
        status="confirmed",
        source="community_id_request",
        taxon_id=taxon_id,
        clear_confidence=True,
    )
    raw_payload = dict(observation.get("raw_response_json") or {})
    raw_payload["community_id_request"] = {
        **request_payload,
        "requested_at": datetime.utcnow().isoformat(),
        "replaced_identification": {
            "taxon_id": observation.get("taxon_id"),
            "common_name": observation.get("common_name"),
            "scientific_name": observation.get("scientific_name"),
            "confidence": observation.get("confidence"),
            "source": observation.get("source"),
        },
    }
    raw_payload.pop("taxon_enrichment", None)
    updated = repository.update_observation_raw_payload(updated["id"], raw_payload)
    if taxon_id is not None:
        ensure_taxon_enrichment(repository, inat_client, updated)
    if photo.get("id"):
        repository.update_photo_processing_status(photo["id"], "ready")
    return updated


def format_confidence_percent(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "0%"
    if number <= 1:
        number *= 100
    return f"{round(number):.0f}%"


def format_confidence_label(observation: dict[str, Any]) -> str:
    if observation.get("source") == "community_id_request":
        return "Community ID request"
    if observation.get("confidence") in (None, ""):
        return "Manual entry"
    return f"Confidence: {format_confidence_percent(observation.get('confidence'))}"


def get_inat_posting(observation: dict[str, Any]) -> dict[str, Any]:
    raw_payload = observation.get("raw_response_json") or {}
    raw_posting = raw_payload.get("inat_posting") or {}
    raw_posting = raw_posting if isinstance(raw_posting, dict) else {}
    if observation.get("inat_observation_id"):
        posting = {
            "observation_id": observation.get("inat_observation_id"),
            "observation_url": observation.get("inat_observation_url") or build_inat_observation_url(observation.get("inat_observation_id")),
            "posted_at": observation.get("inat_posted_at"),
            "photo_attached": observation.get("inat_photo_attached"),
        }
        for key in (
            "photo_count",
            "attached_photo_count",
            "local_photo_ids",
            "attached_local_photo_ids",
            "failed_local_photo_ids",
        ):
            if key in raw_posting:
                posting[key] = raw_posting[key]
        return posting
    return raw_posting


def get_inat_web_base_url() -> str:
    base_url = settings.inat_base_url.rstrip("/")
    if "api.inaturalist.org" in base_url:
        return "https://www.inaturalist.org"
    if base_url.endswith("/v1"):
        return base_url[:-3]
    return base_url


def build_inat_observation_url(observation_id: int | str) -> str:
    return f"{get_inat_web_base_url()}/observations/{observation_id}"


def build_inat_extra_photo_candidates(
    observation: dict[str, Any],
    photo: dict[str, Any],
) -> list[dict[str, Any]]:
    hike_id = str(photo.get("hike_id") or "").strip()
    current_photo_id = str(photo.get("id") or "").strip()
    species_group_key = build_species_group_key(observation)
    if not hike_id or not current_photo_id or not species_group_key:
        return []
    hike_photos = fetch_hike_photos(hike_id)
    lightweight_observations = fetch_hike_lightweight_observations(hike_id)
    observations_by_photo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in lightweight_observations:
        photo_id = str(record.get("photo_id") or "").strip()
        if photo_id:
            observations_by_photo[photo_id].append(record)
    candidates: list[dict[str, Any]] = []
    for hike_photo in hike_photos:
        photo_id = str(hike_photo.get("id") or "").strip()
        if not photo_id or photo_id == current_photo_id:
            continue
        matching_observations = [
            record
            for record in observations_by_photo.get(photo_id, [])
            if record.get("status") == "confirmed" and build_species_group_key(record) == species_group_key
        ]
        if not matching_observations:
            continue
        matching_observations.sort(
            key=lambda record: (
                0 if record.get("is_primary") else 1,
                str(record.get("identified_at") or ""),
            )
        )
        matched_observation = matching_observations[0]
        if matched_observation.get("inat_observation_id"):
            continue
        if not hike_photo.get("public_url"):
            continue
        candidates.append(
            {
                "photo": hike_photo,
                "observation": matched_observation,
                "label": format_photo_meta(hike_photo) or f"Photo {photo_id[:8]}",
            }
        )
    return candidates


def _normalize_inat_post_photos(
    lead_photo: dict[str, Any],
    extra_photos: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    ordered_photos = [lead_photo, *(extra_photos or [])]
    normalized: list[dict[str, Any]] = []
    seen_photo_ids: set[str] = set()
    for candidate in ordered_photos:
        photo_id = str(candidate.get("id") or "").strip()
        if not photo_id or photo_id in seen_photo_ids:
            continue
        seen_photo_ids.add(photo_id)
        normalized.append(candidate)
    return normalized


def _format_inat_multi_photo_message(posting: dict[str, Any]) -> str:
    attached_count = posting.get("attached_photo_count")
    requested_count = posting.get("photo_count")
    try:
        attached_count_int = int(attached_count) if attached_count not in (None, "") else None
    except (TypeError, ValueError):
        attached_count_int = None
    try:
        requested_count_int = int(requested_count) if requested_count not in (None, "") else None
    except (TypeError, ValueError):
        requested_count_int = None
    if attached_count_int and attached_count_int > 1:
        return f"Posted this observation to iNaturalist with {attached_count_int} photos."
    if requested_count_int and requested_count_int > 1:
        return f"Posted this observation to iNaturalist with {requested_count_int} photos."
    return "Posted this observation to iNaturalist."


def render_inat_posting_controls(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    observation: dict[str, Any],
    photo: dict[str, Any],
    *,
    place_guess: str | None,
    key_prefix: str,
) -> None:
    if observation.get("status") != "confirmed":
        return
    observation_id = str(observation.get("id") or "")
    feedback = (st.session_state.get("inat_post_feedback") or {}).get(observation_id)
    if isinstance(feedback, dict) and feedback.get("message"):
        level = str(feedback.get("level") or "info")
        if level == "error":
            st.error(str(feedback["message"]))
        elif level == "warning":
            st.warning(str(feedback["message"]))
        else:
            st.success(str(feedback["message"]))
        st.session_state.inat_post_feedback.pop(observation_id, None)
    posting = get_inat_posting(observation)
    observation_url = posting.get("observation_url")
    photo_attached = posting.get("photo_attached")
    attached_photo_count = posting.get("attached_photo_count")
    requested_photo_count = posting.get("photo_count")
    if observation_url:
        st.markdown(
            f"<div class='inat-posting-link-row'><a class='viewer-link viewer-link--inat' href='{escape(str(observation_url))}' target='_blank' rel='noopener noreferrer'>View on iNaturalist</a></div>",
            unsafe_allow_html=True,
        )
        if photo_attached is False:
            try:
                attached_count_int = int(attached_photo_count) if attached_photo_count not in (None, "") else None
                requested_count_int = int(requested_photo_count) if requested_photo_count not in (None, "") else None
            except (TypeError, ValueError):
                attached_count_int = None
                requested_count_int = None
            if attached_count_int is not None and requested_count_int and requested_count_int > 1:
                st.caption(f"Attached {attached_count_int} of {requested_count_int} selected photos.")
            else:
                st.caption("This observation was posted, but its photo did not finish uploading to iNaturalist.")
        elif attached_photo_count not in (None, "", 0, 1, "1"):
            try:
                st.caption(f"Posted with {int(attached_photo_count)} photos.")
            except (TypeError, ValueError):
                pass
        return
    extra_photo_candidates = build_inat_extra_photo_candidates(observation, photo)
    if not is_inat_client_ready(inat_client):
        connect_cols = st.columns([0.42, 0.58], gap="small")
        connect_cols[0].button("Post to iNaturalist", key=f"{key_prefix}_post_inat_disabled", type="secondary", disabled=True)
        if connect_cols[1].button(inat_connection_action_label(inat_client), key=f"{key_prefix}_connect_inat", type="secondary"):
            open_inat_token_dialog()
        st.caption(inat_not_ready_message(inat_client).replace("using this action", "posting this confirmed sighting"))
        return
    if st.button("Post to iNaturalist", key=f"{key_prefix}_post_inat", type="secondary"):
        try:
            with st.spinner("Posting to iNaturalist..."):
                posting_result = post_observation_to_inaturalist(
                    repository,
                    inat_client,
                    observation,
                    photo,
                    place_guess=place_guess,
                )
        except (InatConfigurationError, InatAuthError, InatRequestError, RuntimeError) as exc:
            st.session_state.inat_auth_notice = None
            st.session_state.inat_auth_error = str(exc)
            st.session_state.inat_post_feedback[observation_id] = {
                "level": "error",
                "message": str(exc),
            }
            st.error(str(exc))
            return
        st.session_state.inat_auth_error = None
        observation["raw_response_json"] = {
            **(observation.get("raw_response_json") or {}),
            "inat_posting": posting_result,
        }
        if key_prefix.startswith("viewer_"):
            st.session_state.viewer_open = True
            st.session_state.viewer_notice = _format_inat_multi_photo_message(posting_result)
        else:
            st.session_state.inat_post_feedback[observation_id] = {
                "level": "success",
                "message": _format_inat_multi_photo_message(posting_result),
            }
        st.rerun()
    if not extra_photo_candidates:
        return
    with st.popover("Post with more photos"):
        st.caption("Bundle other confirmed photos of this same species from this outing into one iNaturalist observation.")
        with st.form(f"{key_prefix}_inat_multi_photo_form", enter_to_submit=False):
            st.caption("The current photo will be used as the lead image.")
            selected_extra_photos: list[dict[str, Any]] = []
            for index, candidate in enumerate(extra_photo_candidates, start=1):
                candidate_photo = candidate["photo"]
                candidate_label = f"Photo {index + 1}: {candidate['label']}"
                checkbox_key = f"{key_prefix}_inat_related_{candidate_photo['id']}"
                if st.checkbox(candidate_label, key=checkbox_key):
                    selected_extra_photos.append(candidate_photo)
            selected_total = 1 + len(selected_extra_photos)
            submit_label = f"Post grouped observation ({selected_total} photos)"
            if st.form_submit_button(submit_label, use_container_width=True, type="secondary"):
                try:
                    with st.spinner("Posting grouped observation to iNaturalist..."):
                        posting_result = post_observation_to_inaturalist(
                            repository,
                            inat_client,
                            observation,
                            photo,
                            place_guess=place_guess,
                            extra_photos=selected_extra_photos,
                        )
                except (InatConfigurationError, InatAuthError, InatRequestError, RuntimeError) as exc:
                    st.session_state.inat_auth_notice = None
                    st.session_state.inat_auth_error = str(exc)
                    st.session_state.inat_post_feedback[observation_id] = {
                        "level": "error",
                        "message": str(exc),
                    }
                    st.error(str(exc))
                    return
                st.session_state.inat_auth_error = None
                observation["raw_response_json"] = {
                    **(observation.get("raw_response_json") or {}),
                    "inat_posting": posting_result,
                }
                if key_prefix.startswith("viewer_"):
                    st.session_state.viewer_open = True
                    st.session_state.viewer_notice = _format_inat_multi_photo_message(posting_result)
                else:
                    st.session_state.inat_post_feedback[observation_id] = {
                        "level": "success",
                        "message": _format_inat_multi_photo_message(posting_result),
                    }
                st.rerun()


def post_observation_to_inaturalist(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    observation: dict[str, Any],
    photo: dict[str, Any],
    *,
    place_guess: str | None,
    extra_photos: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    inat_client.validate_credentials()
    observed_on = _parse_datetime(photo.get("taken_at"))
    upload_photos = _normalize_inat_post_photos(photo, extra_photos)
    if not upload_photos:
        raise RuntimeError("Choose at least one photo before posting to iNaturalist.")
    upload_payloads: list[dict[str, Any]] = []
    for upload_photo in upload_photos:
        public_url = str(upload_photo.get("public_url") or "").strip()
        if not public_url:
            raise RuntimeError("One of the selected photos is missing a public image URL, so HikeJournal could not send it to iNaturalist.")
        try:
            image_bytes = _download_public_image(public_url)
        except Exception as exc:
            raise RuntimeError("HikeJournal could not download one of the selected photos for iNaturalist.") from exc
        upload_payloads.append(
            {
                "photo": upload_photo,
                "image_bytes": image_bytes,
                "content_type": upload_photo.get("content_type") or "image/jpeg",
            }
        )
    species_guess = observation.get("common_name") or observation.get("scientific_name")
    created_observation = inat_client.create_observation(
        taxon_id=observation.get("taxon_id"),
        species_guess=species_guess,
        observed_on=observed_on,
        lat=photo.get("lat"),
        lng=photo.get("lng"),
        place_guess=place_guess,
        description="Posted from HikeJournal.",
        tags=["HikeJournal"],
    )
    created_id = created_observation.get("id")
    if created_id in (None, ""):
        raise InatRequestError("iNaturalist created a response, but HikeJournal could not find the new observation ID.")
    posting_payload = {
        "observation_id": int(created_id),
        "observation_url": created_observation.get("uri") or created_observation.get("html_url") or build_inat_observation_url(created_id),
        "posted_at": datetime.now().astimezone().isoformat(),
        "posted_by_subject": st.session_state.current_user_context.get("subject"),
        "posted_by_email": st.session_state.current_user_context.get("email"),
        "photo_attached": True,
        "photo_count": len(upload_payloads),
        "attached_photo_count": 0,
        "local_photo_ids": [str(item["photo"]["id"]) for item in upload_payloads],
        "attached_local_photo_ids": [],
        "failed_local_photo_ids": [],
    }
    raw_payload = dict(observation.get("raw_response_json") or {})
    upload_errors: list[str] = []
    for upload_payload in upload_payloads:
        upload_photo = upload_payload["photo"]
        photo_id = str(upload_photo["id"])
        try:
            inat_client.attach_photo_to_observation(
                observation_id=int(created_id),
                image_bytes=upload_payload["image_bytes"],
                filename=f"{photo_id}.jpg",
                content_type=upload_payload["content_type"],
            )
        except InatRequestError as exc:
            posting_payload["photo_attached"] = False
            posting_payload["failed_local_photo_ids"].append(photo_id)
            upload_errors.append(f"{photo_id[:8]}: {exc}")
        else:
            posting_payload["attached_local_photo_ids"].append(photo_id)
    posting_payload["attached_photo_count"] = len(posting_payload["attached_local_photo_ids"])
    raw_payload["inat_posting"] = posting_payload
    repository.update_observation_raw_payload(observation["id"], raw_payload)
    repository.update_observation_inat_posting(
        observation["id"],
        inat_observation_id=int(created_id),
        inat_observation_url=posting_payload["observation_url"],
        inat_posted_at=posting_payload["posted_at"],
        inat_photo_attached=bool(posting_payload["photo_attached"]),
    )
    if upload_errors:
        attached_count = posting_payload["attached_photo_count"]
        requested_count = posting_payload["photo_count"]
        raise InatRequestError(
            f"iNaturalist created the observation, but only attached {attached_count} of {requested_count} photos. "
            f"You can still open it there and add the remaining photos manually. Details: {'; '.join(upload_errors)}"
        )
    invalidate_data_cache()
    return posting_payload


def confirm_observation(repository: HikeJournalRepository, inat_client: InatClient, observation: dict[str, Any]) -> None:
    ensure_taxon_enrichment(repository, inat_client, observation)


def get_taxon_enrichment(observation: dict[str, Any]) -> dict[str, Any]:
    raw_payload = observation.get("raw_response_json") or {}
    enrichment = raw_payload.get("taxon_enrichment")
    return enrichment if isinstance(enrichment, dict) else {}


def get_manual_species_override(observation: dict[str, Any]) -> dict[str, Any]:
    raw_payload = observation.get("raw_response_json") or {}
    manual_override = raw_payload.get("manual_override")
    return manual_override if isinstance(manual_override, dict) else {}


def build_species_search_terms(observation: dict[str, Any]) -> list[str]:
    enrichment = get_taxon_enrichment(observation)
    alias_names = enrichment.get("alias_names") or []
    scientific_name = str(observation.get("scientific_name") or "").strip()
    scientific_parts = [part.strip().lower() for part in scientific_name.split() if part.strip()]
    values = [
        observation.get("common_name"),
        scientific_name,
        enrichment.get("preferred_common_name"),
        enrichment.get("english_common_name"),
        enrichment.get("wikipedia_summary"),
        *alias_names,
        *scientific_parts[:2],
    ]
    terms = []
    for value in values:
        if not value:
            continue
        cleaned = clean_summary_text(str(value)).strip().lower()
        if cleaned:
            terms.append(cleaned)
    return terms


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_taxon_autocomplete_results(query: str, access_token: str, base_url: str) -> list[dict[str, Any]]:
    return InatClient(access_token=access_token, base_url=base_url).autocomplete_taxa(query)


def build_species_taxon_search_hints(query: str, inat_client: InatClient) -> dict[str, set[str] | set[int]]:
    normalized_query = query.strip().lower()
    hints: dict[str, set[str] | set[int]] = {
        "taxon_ids": set(),
        "scientific_prefixes": set(),
        "name_terms": set(),
    }
    if not normalized_query or len(normalized_query) < 3:
        return hints
    try:
        results = fetch_taxon_autocomplete_results(query, inat_client.access_token, inat_client.base_url)
    except Exception:
        return hints

    taxon_ids = hints["taxon_ids"]
    scientific_prefixes = hints["scientific_prefixes"]
    name_terms = hints["name_terms"]

    for item in results:
        try:
            taxon_id = item.get("id")
            if taxon_id is not None:
                taxon_ids.add(int(taxon_id))
        except (TypeError, ValueError):
            pass
        for value in [item.get("matched_term"), item.get("preferred_common_name"), item.get("name")]:
            if not value:
                continue
            cleaned = clean_summary_text(str(value)).strip().lower()
            if cleaned:
                name_terms.add(cleaned)
        rank = str(item.get("rank") or "").strip().lower()
        if rank in {"genus", "subgenus"}:
            scientific_name = str(item.get("name") or "").strip().lower()
            if scientific_name:
                scientific_prefixes.add(scientific_name)
    return hints


def observation_matches_taxon_search_hints(
    observation: dict[str, Any],
    taxon_search_hints: dict[str, set[str] | set[int]],
) -> bool:
    matched_taxon_ids = taxon_search_hints.get("taxon_ids") or set()
    scientific_prefixes = taxon_search_hints.get("scientific_prefixes") or set()
    name_terms = taxon_search_hints.get("name_terms") or set()
    try:
        taxon_id = observation.get("taxon_id")
        if taxon_id is not None and int(taxon_id) in matched_taxon_ids:
            return True
    except (TypeError, ValueError):
        pass

    scientific_name = str(observation.get("scientific_name") or "").strip().lower()
    common_name = str(observation.get("common_name") or "").strip().lower()
    if any(scientific_name == prefix or scientific_name.startswith(prefix + " ") for prefix in scientific_prefixes):
        return True
    if any(term and (term in common_name or term in scientific_name) for term in name_terms):
        return True
    return False


def clean_summary_text(value: str) -> str:
    import re

    without_tags = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", without_tags).strip()


def ensure_taxon_enrichment(repository: HikeJournalRepository, inat_client: InatClient, observation: dict[str, Any]) -> None:
    raw_payload = dict(observation.get("raw_response_json") or {})
    enrichment = raw_payload.get("taxon_enrichment")
    if raw_payload.get("manual_override"):
        return
    taxon_id = observation.get("taxon_id")
    if enrichment or not taxon_id:
        return
    try:
        raw_payload["taxon_enrichment"] = inat_client.fetch_taxon_enrichment(int(taxon_id))
        repository.update_observation_raw_payload(observation["id"], raw_payload)
        invalidate_data_cache()
    except (InatConfigurationError, InatRequestError, ValueError):
        return


def sync_species_override_payload(
    repository: HikeJournalRepository,
    original_observation: dict[str, Any],
    updated_observation: dict[str, Any],
) -> None:
    original_common = (original_observation.get("common_name") or "").strip() or None
    original_scientific = (original_observation.get("scientific_name") or "").strip() or None
    updated_common = (updated_observation.get("common_name") or "").strip() or None
    updated_scientific = (updated_observation.get("scientific_name") or "").strip() or None

    raw_payload = dict(original_observation.get("raw_response_json") or {})
    enrichment = raw_payload.get("taxon_enrichment")
    original_snapshot = raw_payload.get("original_identification")
    changed_names = (updated_common != original_common) or (updated_scientific != original_scientific)

    if changed_names:
        if not isinstance(original_snapshot, dict):
            raw_payload["original_identification"] = {
                "common_name": original_common,
                "scientific_name": original_scientific,
                "taxon_id": original_observation.get("taxon_id"),
                "taxon_enrichment": enrichment if isinstance(enrichment, dict) else None,
            }
        raw_payload["manual_override"] = {
            "common_name": updated_common,
            "scientific_name": updated_scientific,
            "edited_at": datetime.utcnow().isoformat(),
        }
        raw_payload.pop("taxon_enrichment", None)
    else:
        raw_payload.pop("manual_override", None)
        if not isinstance(raw_payload.get("taxon_enrichment"), dict):
            original_snapshot = raw_payload.get("original_identification") or {}
            restored = original_snapshot.get("taxon_enrichment")
            if isinstance(restored, dict):
                raw_payload["taxon_enrichment"] = restored

    repository.update_observation_raw_payload(updated_observation["id"], raw_payload)
    invalidate_data_cache()


def group_observations_by_photo(observations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        grouped[observation["photo_id"]].append(observation)
    return grouped


def get_primary_observation(photo_observations: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not photo_observations:
        return None
    status_priority = {
        "confirmed": 0,
        "pending": 1,
        "rejected": 3,
    }

    def observation_priority(observation: dict[str, Any]) -> tuple[int, int, str]:
        status = str(observation.get("status") or "pending")
        is_primary = bool(observation.get("is_primary"))
        rejected_penalty = 1 if status == "rejected" else 0
        return (
            rejected_penalty,
            0 if is_primary and status != "rejected" else 1,
            f"{status_priority.get(status, 2)}::{observation.get('identified_at') or observation.get('created_at') or ''}",
        )

    return min(photo_observations, key=observation_priority)


def filter_hikes_for_user(
    hikes: list[dict[str, Any]],
    user_context: dict[str, Any],
) -> list[dict[str, Any]]:
    if user_context["mode"] == "local-dev":
        return hikes

    email = normalize_email(user_context.get("email"))
    subject = user_context.get("subject")
    visible = []
    for hike in hikes:
        owner_email = normalize_email(hike.get("owner_email"))
        owner_subject = hike.get("owner_subject")
        if owner_subject and subject and owner_subject == subject:
            visible.append(hike)
            continue
        if owner_email and email and owner_email == email:
            visible.append(hike)
            continue
        if not owner_email and not owner_subject and not user_context["auth_configured"]:
            visible.append(hike)
    return visible


def user_owns_record(record: dict[str, Any], user_context: dict[str, Any]) -> bool:
    if user_context["mode"] == "local-dev":
        return True
    email = normalize_email(user_context.get("email"))
    subject = user_context.get("subject")
    owner_email = normalize_email(record.get("owner_email"))
    owner_subject = record.get("owner_subject")
    if owner_subject and subject and owner_subject == subject:
        return True
    if owner_email and email and owner_email == email:
        return True
    return False


def record_visible_for_user(
    record: dict[str, Any],
    visible_hike_ids: set[str],
    user_context: dict[str, Any],
) -> bool:
    hike_id = record.get("hike_id")
    if hike_id and hike_id in visible_hike_ids:
        return True
    if not hike_id:
        return user_owns_record(record, user_context)
    return False


def filter_hike_library(
    hikes: list[dict[str, Any]],
    *,
    query: str,
    scope: str,
    sort_order: str,
) -> list[dict[str, Any]]:
    normalized_query = query.strip().lower()
    filtered = []
    for hike in hikes:
        is_archived = bool(hike.get("is_archived"))
        if scope == "Active" and is_archived:
            continue
        if scope == "Archived" and not is_archived:
            continue
        haystack = " ".join(
            str(hike.get(field) or "")
            for field in ["title", "location_name", "notes", "hike_date"]
        ).lower()
        if normalized_query and normalized_query not in haystack:
            continue
        filtered.append(hike)

    if sort_order == "Oldest first":
        filtered.sort(key=lambda hike: (str(hike.get("hike_date") or ""), str(hike.get("created_at") or "")))
    elif sort_order == "Title":
        filtered.sort(key=lambda hike: (str(hike.get("title") or "").lower(), str(hike.get("hike_date") or "")), reverse=False)
    else:
        filtered.sort(key=lambda hike: (str(hike.get("hike_date") or ""), str(hike.get("created_at") or "")), reverse=True)
    return filtered


def group_hikes_for_library(hikes: list[dict[str, Any]], group_by: str) -> list[tuple[str | None, list[dict[str, Any]]]]:
    if group_by == "None":
        return [(None, hikes)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for hike in hikes:
        hike_date = _parse_date(hike.get("hike_date"))
        label = hike_date.strftime("%Y") if group_by == "Year" else hike_date.strftime("%B %Y")
        grouped[label].append(hike)
    return list(grouped.items())


def format_hike_choice(hike: dict[str, Any]) -> str:
    archive_prefix = "Archived • " if hike.get("is_archived") else ""
    location = hike.get("location_name") or "Unknown place"
    return f"{archive_prefix}{hike.get('title') or 'Untitled hike'} • {hike.get('hike_date') or ''} • {location}"


def parse_collaborator_lines(value: str) -> list[str]:
    emails = []
    seen = set()
    for raw in value.splitlines():
        email = normalize_email(raw)
        if not email or email in seen:
            continue
        seen.add(email)
        emails.append(email)
    return emails


def count_records_by_key(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        record_key = record.get(key)
        if record_key:
            counts[record_key] += 1
    return counts


def group_records_by_key(records: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        record_key = record.get(key)
        if record_key:
            groups[str(record_key)].append(record)
    return groups


def build_standalone_library_item(
    *,
    photos: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    query: str,
    scope: str,
) -> dict[str, Any] | None:
    if not photos or scope == "Archived":
        return None
    latest_photo = max(
        photos,
        key=lambda photo: (photo.get("taken_at") or "", photo.get("created_at") or "", photo["id"]),
    )
    confirmed_count = count_unique_species([record for record in confirmed_observations if not record.get("hike_id")])
    title = "Everyday Sightings"
    location_name = "Photos and species notes not attached to a hike yet."
    notes = "A catch-all journal for quick uploads, neighborhood finds, and anything you want to identify outside a formal outing."
    search_haystack = " ".join(
        [
            title,
            location_name,
            notes,
            str(latest_photo.get("taken_at") or latest_photo.get("created_at") or ""),
        ]
    ).lower()
    normalized_query = query.strip().lower()
    if normalized_query and normalized_query not in search_haystack:
        return None
    date_value = latest_photo.get("taken_at") or latest_photo.get("created_at") or ""
    date_label = str(date_value)[:10] if date_value else "Anytime"
    return {
        "id": "__standalone__",
        "title": title,
        "location_name": location_name,
        "notes": notes,
        "hike_date": date_label,
        "created_at": latest_photo.get("created_at"),
        "is_archived": False,
        "_is_standalone": True,
        "_cover_photo": latest_photo,
        "_photo_count": len(photos),
        "_confirmed_count": confirmed_count,
    }


def build_species_log_context(
    *,
    hikes: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    photos: list[dict[str, Any]],
    inat_client: InatClient,
) -> dict[str, Any]:
    hike_by_id = {hike["id"]: hike for hike in hikes}
    hike_title_to_id = {str(hike.get("title") or "Untitled hike"): hike["id"] for hike in hikes}
    photo_by_id = {photo["id"]: photo for photo in photos}
    query = str(st.session_state.get("species_log_query", "")).strip()
    normalized_query = query.lower()
    hike_filter = str(st.session_state.get("species_log_hike_filter", "All hikes"))
    mapped_only = bool(st.session_state.get("species_log_mapped_only", False))
    include_secondary = bool(st.session_state.get("species_log_include_secondary", True))
    sort_order = str(st.session_state.get("species_log_sort", "Most recent"))
    posted_filter = str(st.session_state.get("species_log_posted_filter", "All"))
    taxon_search_hints = build_species_taxon_search_hints(query, inat_client)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in confirmed_observations:
        photo = photo_by_id.get(observation.get("photo_id"))
        if not photo:
            continue
        if hike_filter != "All hikes" and observation.get("hike_id") != hike_title_to_id.get(hike_filter):
            continue
        if mapped_only and (photo.get("lat") is None or photo.get("lng") is None):
            continue
        if not include_secondary and not observation.get("is_primary"):
            continue
        if posted_filter == "Posted" and not observation.get("inat_observation_id"):
            continue
        if posted_filter == "Not posted" and observation.get("inat_observation_id"):
            continue
        hike = hike_by_id.get(observation.get("hike_id"), {})
        grouped[build_species_group_key(observation)].append(
            {"observation": observation, "photo": photo, "hike": hike}
        )

    all_species = list(grouped.values())
    representative_observations: dict[str, dict[str, Any]] = {}
    matching_groups: list[list[dict[str, Any]]] = []

    if normalized_query and all_species:
        representative_ids = tuple(entries[0]["observation"]["id"] for entries in all_species)
        full_representatives = fetch_observations_by_ids(representative_ids) if representative_ids else []
        representative_observations = {observation["id"]: observation for observation in full_representatives}
    for entries in all_species:
        observation = representative_observations.get(entries[0]["observation"]["id"], entries[0]["observation"])
        query_match = (
            not normalized_query
            or any(normalized_query in term for term in build_species_search_terms(observation))
            or observation_matches_taxon_search_hints(observation, taxon_search_hints)
        )
        if query_match:
            matching_groups.append(entries)

    species_rows = []
    ordered_viewer_photos: list[dict[str, Any]] = []
    ordered_viewer_observations: list[dict[str, Any]] = []
    seen_photo_ids: set[str] = set()
    seen_observation_ids: set[str] = set()

    for entries in matching_groups:
        entries_sorted = sorted(
            entries,
            key=lambda entry: (
                _entry_sort_datetime(entry),
                entry["photo"].get("created_at") or "",
                entry["photo"]["id"],
            ),
            reverse=True,
        )
        representative_observation = representative_observations.get(
            entries_sorted[0]["observation"]["id"], entries_sorted[0]["observation"]
        )
        encounters_by_hike: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entry in entries_sorted:
            encounter_key = str(entry["hike"].get("id") or entry["observation"].get("hike_id") or f"standalone:{entry['photo']['id']}")
            encounters_by_hike[encounter_key].append(entry)
        encounters = []
        for encounter_entries in encounters_by_hike.values():
            encounter_entries = sorted(
                encounter_entries,
                key=lambda entry: (
                    _entry_sort_datetime(entry),
                    entry["photo"].get("created_at") or "",
                    entry["photo"]["id"],
                ),
                reverse=True,
            )
            encounters.append(
                {
                    "hike": encounter_entries[0]["hike"],
                    "entries": encounter_entries,
                    "latest_seen": _entry_sort_datetime(encounter_entries[0]),
                }
            )
        encounters.sort(key=lambda encounter: encounter["latest_seen"], reverse=True)

        latest_seen = _entry_sort_datetime(entries_sorted[0])
        earliest_seen = min(_entry_sort_datetime(entry) for entry in entries_sorted)
        common_name = representative_observation.get("common_name") or representative_observation.get("scientific_name") or "Unknown species"
        scientific_name = representative_observation.get("scientific_name") or ""
        species_rows.append(
            {
                "key": build_species_group_key(representative_observation),
                "representative_id": representative_observation["id"],
                "observation": representative_observation,
                "common_name": common_name,
                "scientific_name": scientific_name,
                "lead_photo": entries_sorted[0]["photo"],
                "sighting_count": len(entries_sorted),
                "hike_count": len({entry["hike"].get("id") for entry in entries_sorted if entry.get("hike")}),
                "first_seen_label": format_species_log_date_label(earliest_seen),
                "first_seen_sort": earliest_seen,
                "last_seen_label": format_species_log_date_label(latest_seen),
                "last_seen_sort": latest_seen,
                "encounters": encounters,
            }
        )

    if sort_order == "Most seen":
        species_rows.sort(key=lambda row: (-row["sighting_count"], row["common_name"].lower()))
    elif sort_order == "A-Z":
        species_rows.sort(key=lambda row: (row["common_name"].lower(), row["scientific_name"].lower()))
    elif sort_order == "Newest species first":
        species_rows.sort(key=lambda row: (row["first_seen_sort"], row["common_name"].lower()), reverse=True)
    else:
        species_rows.sort(key=lambda row: (row["last_seen_sort"], row["common_name"].lower()), reverse=True)

    for row in species_rows:
        for encounter in row["encounters"]:
            for entry in encounter["entries"]:
                photo_id = entry["photo"]["id"]
                observation_id = entry["observation"]["id"]
                if photo_id not in seen_photo_ids:
                    ordered_viewer_photos.append(entry["photo"])
                    seen_photo_ids.add(photo_id)
                if observation_id not in seen_observation_ids:
                    ordered_viewer_observations.append(entry["observation"])
                    seen_observation_ids.add(observation_id)

    return {
        "all_species": all_species,
        "species_rows": species_rows,
        "representative_observations": representative_observations,
        "posted_observations": [observation for observation in confirmed_observations if observation.get("inat_observation_id")],
        "viewer_photos": ordered_viewer_photos,
        "viewer_observations": ordered_viewer_observations,
    }


def build_species_group_key(observation: dict[str, Any]) -> str:
    scientific = (observation.get("scientific_name") or "").strip().lower()
    common = (observation.get("common_name") or "").strip().lower()
    if scientific:
        return f"scientific:{scientific}"
    if common:
        return f"common:{common}"
    taxon_id = observation.get("taxon_id")
    if taxon_id not in (None, ""):
        return f"taxon:{taxon_id}"
    return "unknown"


def _entry_sort_datetime(entry: dict[str, Any]) -> datetime:
    photo = entry.get("photo") or {}
    hike = entry.get("hike") or {}
    parsed_taken = _parse_datetime(photo.get("taken_at"))
    if parsed_taken:
        return parsed_taken
    hike_date = hike.get("hike_date")
    if hike_date:
        return datetime.combine(_parse_date(hike_date), datetime.min.time())
    return datetime.min


def format_species_log_date_label(value: datetime) -> str:
    if value == datetime.min:
        return "Unknown date"
    return value.strftime("%b %d, %Y")


def _format_species_log_focus_label(row: dict[str, Any]) -> str:
    common_name = row.get("common_name") or "Unknown species"
    scientific_name = row.get("scientific_name") or ""
    sightings = int(row.get("sighting_count") or 0)
    if scientific_name:
        return f"{common_name} — {scientific_name} · {sightings}"
    return f"{common_name} · {sightings}"


def normalize_email(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def photo_owner_subject(hike: dict[str, Any] | None, user_context: dict[str, Any]) -> str | None:
    return (hike or {}).get("owner_subject") or user_context.get("subject")


def photo_owner_email(hike: dict[str, Any] | None, user_context: dict[str, Any]) -> str | None:
    return normalize_email((hike or {}).get("owner_email")) or normalize_email(user_context.get("email"))


def paginate_photos(photos: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    return paginate_items(photos, "journal_page", "journal_page_size")


def paginate_items(items: list[dict[str, Any]], page_key: str, page_size_key: str) -> tuple[list[dict[str, Any]], int]:
    page_size = resolve_page_size(len(items), st.session_state[page_size_key])
    total_pages = max(1, math.ceil(len(items) / page_size))
    st.session_state[page_key] = min(max(1, st.session_state[page_key]), total_pages)
    start = (st.session_state[page_key] - 1) * page_size
    end = start + page_size
    return items[start:end], total_pages


def render_photo_management_toolbar(
    repository: HikeJournalRepository,
    storage: StorageService,
    page_photos: list[dict[str, Any]],
    all_deletable_photos: list[dict[str, Any]],
    total_pages: int,
) -> None:
    cols = st.columns([0.16, 0.14, 0.28, 0.18, 0.24], gap="small")
    page_size_options = [6, 9, 12, 18, 0]
    page_size = cols[0].selectbox(
        "Per page",
        page_size_options,
        index=page_size_options.index(st.session_state.journal_page_size),
        key="journal_page_size_select",
        format_func=lambda value: "All" if value == 0 else str(value),
    )
    if page_size != st.session_state.journal_page_size:
        st.session_state.journal_page_size = page_size
        st.session_state.journal_page = 1
        st.rerun()
    requested_page = cols[1].number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        value=st.session_state.journal_page,
        step=1,
        key="journal_page_number",
    )
    if requested_page != st.session_state.journal_page:
        st.session_state.journal_page = int(requested_page)
        st.rerun()
    cols[2].markdown(
        f"<div class='utility-rail-status'>{len(page_photos)} photos on this page • {len(st.session_state.delete_photo_ids)} marked for deletion</div>",
        unsafe_allow_html=True,
    )
    st.session_state.delete_mode = cols[3].toggle(
        "Delete mode",
        value=st.session_state.delete_mode,
        key="journal_delete_mode",
    )
    with cols[4].popover("Manage"):
        st.caption(f"Page {st.session_state.journal_page} of {total_pages}")
        nav_cols = st.columns(2, gap="small")
        if nav_cols[0].button("Previous", use_container_width=True, disabled=st.session_state.journal_page <= 1):
            st.session_state.journal_page -= 1
            st.rerun()
        if nav_cols[1].button("Next", use_container_width=True, disabled=st.session_state.journal_page >= total_pages):
            st.session_state.journal_page += 1
            st.rerun()
        st.divider()
        if st.session_state.delete_mode and page_photos:
            bulk_cols = st.columns(2, gap="small")
            if bulk_cols[0].button("Mark page", use_container_width=True):
                st.session_state.delete_photo_ids.update(photo["id"] for photo in page_photos)
                for photo in page_photos:
                    st.session_state[f"delete_photo_{photo['id']}"] = True
                st.rerun()
            if bulk_cols[1].button("Clear page", use_container_width=True):
                for photo in page_photos:
                    st.session_state.delete_photo_ids.discard(photo["id"])
                    checkbox_key = f"delete_photo_{photo['id']}"
                    if checkbox_key in st.session_state:
                        st.session_state[checkbox_key] = False
                st.rerun()
            st.caption("Delete mode is on. Use the checkboxes below the photos to choose what to remove.")
        if st.button(
            f"Delete selected ({len(st.session_state.delete_photo_ids)})",
            use_container_width=True,
            disabled=not st.session_state.delete_photo_ids,
        ):
            for photo in all_deletable_photos:
                if photo["id"] in st.session_state.delete_photo_ids:
                    storage.delete_file(photo.get("storage_path") or "")
                    repository.delete_photo(photo["id"])
            invalidate_data_cache()
            st.session_state.delete_photo_ids = set()
            for key in list(st.session_state.keys()):
                if key.startswith("delete_photo_"):
                    del st.session_state[key]
            st.rerun()


def render_species_management_toolbar(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    selected_photos: list[dict[str, Any]],
    page_photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    total_pages: int,
    review_stage: str,
) -> None:
    unprocessed_queue = [photo for photo in selected_photos if photo["id"] not in primary_observation_by_photo]
    pending_queue = [
        photo
        for photo in selected_photos
        if (primary_observation_by_photo.get(photo["id"]) or {}).get("status") == "pending"
    ]
    visible_ids = {photo["id"] for photo in selected_photos}
    selected_ids = {
        photo["id"]
        for photo in selected_photos
        if st.session_state.get(f"species_select_{photo['id']}", photo["id"] in st.session_state.species_selected_ids)
    }
    st.session_state.species_selected_ids = (set(st.session_state.species_selected_ids) - visible_ids) | selected_ids
    selected_count = len(selected_ids)
    cols = st.columns([0.16, 0.14, 0.34, 0.14, 0.22], gap="small")
    page_size_options = [4, 6, 8, 10, 0]
    page_size = cols[0].selectbox(
        "Per page",
        page_size_options,
        index=page_size_options.index(st.session_state.species_page_size),
        key="species_page_size_select",
        format_func=lambda value: "All" if value == 0 else str(value),
    )
    if page_size != st.session_state.species_page_size:
        st.session_state.species_page_size = page_size
        st.session_state.species_page = 1
        st.rerun()
    requested_page = cols[1].number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        value=st.session_state.species_page,
        step=1,
        key="species_page_number",
    )
    if requested_page != st.session_state.species_page:
        st.session_state.species_page = int(requested_page)
        st.rerun()
    stage_copy = {
        "Needs IDs": f"{len(unprocessed_queue)} waiting for a first suggestion in this lane",
        "Needs decisions": f"{len(pending_queue)} ready for your decision in this lane",
        "Finished": f"{len(selected_photos) - len(unprocessed_queue) - len(pending_queue)} already resolved in this lane",
        "All": (
            f"{len(selected_photos)} selected for review • "
            f"{len(unprocessed_queue)} waiting for a first suggestion • "
            f"{len(pending_queue)} ready for your decision"
        ),
    }
    cols[2].markdown(
        f"<div class='utility-rail-status'>{stage_copy.get(review_stage, stage_copy['All'])}</div>",
        unsafe_allow_html=True,
    )
    cols[3].markdown(
        f"<div class='utility-rail-status review-page-status'>{selected_count} selected</div>",
        unsafe_allow_html=True,
    )
    with cols[4].popover("Manage"):
        st.caption(f"Page {st.session_state.species_page} of {total_pages}")
        nav_cols = st.columns(2, gap="small")
        if nav_cols[0].button("Previous", key="species_prev_page", use_container_width=True, disabled=st.session_state.species_page <= 1):
            st.session_state.species_page -= 1
            st.rerun()
        if nav_cols[1].button("Next", key="species_next_page", use_container_width=True, disabled=st.session_state.species_page >= total_pages):
            st.session_state.species_page += 1
            st.rerun()
        st.divider()
        queue_cols = st.columns(2, gap="small")
        if queue_cols[0].button("Select page", key="species_select_page", use_container_width=True):
            for photo in page_photos:
                st.session_state.species_selected_ids.add(photo["id"])
                st.session_state[f"species_select_{photo['id']}"] = True
            st.rerun()
        if queue_cols[1].button("Clear page", key="species_clear_page", use_container_width=True):
            for photo in page_photos:
                st.session_state.species_selected_ids.discard(photo["id"])
                st.session_state[f"species_select_{photo['id']}"] = False
            st.rerun()
        queue_scope_cols = st.columns(2, gap="small")
        if queue_scope_cols[0].button("Select review", key="species_select_queue", use_container_width=True):
            for photo in selected_photos:
                st.session_state.species_selected_ids.add(photo["id"])
            st.rerun()
        if queue_scope_cols[1].button("Clear selection", key="species_clear_queue", use_container_width=True):
            clear_species_selection(selected_photos)
            st.rerun()
        if st.button("Remove all from review", key="species_remove_all_queue", use_container_width=True, type="secondary", disabled=not selected_photos):
            repository.update_photo_processing_statuses([photo["id"] for photo in selected_photos], "ready")
            invalidate_data_cache()
            clear_species_selection(selected_photos)
            st.rerun()
    if not selected_count:
        st.caption("Select one or more photos to review, confirm, reject, or remove from this list.")
        return

    selected_photos_only = [photo for photo in selected_photos if photo["id"] in selected_ids]
    selected_unprocessed = [photo for photo in selected_photos_only if photo["id"] not in primary_observation_by_photo]
    grouped_scope_ids = {str(photo.get("hike_id") or "standalone") for photo in selected_unprocessed}
    grouped_scope_valid = len(grouped_scope_ids) <= 1
    selected_pending = [
        primary_observation_by_photo.get(photo["id"])
        for photo in selected_photos_only
        if (primary_observation_by_photo.get(photo["id"]) or {}).get("status") == "pending"
    ]
    selected_scored = [
        primary_observation_by_photo.get(photo["id"])
        for photo in selected_photos_only
        if primary_observation_by_photo.get(photo["id"])
    ]
    batch_cols = st.columns([0.22, 0.18, 0.18, 0.16, 0.16, 0.1], gap="small")
    if batch_cols[0].button(
        f"Process selected ({len(selected_unprocessed)})",
        key="species_process_selected",
        use_container_width=True,
        disabled=not is_inat_client_ready(inat_client) or not selected_unprocessed,
    ):
        processed_count = process_species_photos(repository, inat_client, selected_photos_only, primary_observation_by_photo)
        if processed_count:
            st.session_state.species_review_stage = "Needs decisions"
            st.session_state.species_page = 1
        st.rerun()
    if batch_cols[1].button(
        f"Single ID ({len(selected_unprocessed)})",
        key="species_process_grouped",
        use_container_width=True,
        disabled=(
            not is_inat_client_ready(inat_client)
            or len(selected_unprocessed) < 2
            or len(selected_unprocessed) > GROUPED_ID_MAX_PHOTOS
            or not grouped_scope_valid
        ),
        type="secondary",
    ):
        processed_count = process_species_photo_group(repository, inat_client, selected_photos_only, primary_observation_by_photo)
        if processed_count:
            st.session_state.species_review_stage = "Needs decisions"
            st.session_state.species_page = 1
        st.rerun()
    if batch_cols[2].button(
        f"Confirm selected ({selected_count})",
        key="species_confirm_selected",
        use_container_width=True,
        disabled=not selected_pending,
    ):
        confirm_observations(repository, inat_client, [item for item in selected_pending if item])
        clear_species_selection(selected_photos_only)
        st.rerun()
    if batch_cols[3].button(
        f"Reject selected ({selected_count})",
        key="species_reject_selected",
        use_container_width=True,
        disabled=not selected_scored,
        type="secondary",
    ):
        reject_observations(repository, selected_scored, selected_photos_only)
        clear_species_selection(selected_photos_only)
        st.rerun()
    if batch_cols[4].button(
        f"Remove from review ({len(selected_photos_only)})",
        key="species_remove_selected",
        use_container_width=True,
        disabled=not selected_photos_only,
        type="secondary",
    ):
        repository.update_photo_processing_statuses([photo["id"] for photo in selected_photos_only], "ready")
        invalidate_data_cache()
        clear_species_selection(selected_photos_only)
        st.rerun()
    batch_cols[5].button("Clear", key="species_clear_selected_batch", use_container_width=True, type="tertiary", disabled=not selected_count, on_click=clear_species_selection, args=(selected_photos_only,))
    if len(selected_unprocessed) == 1:
        st.caption("Single ID needs at least 2 unprocessed photos.")
    elif len(selected_unprocessed) > GROUPED_ID_MAX_PHOTOS:
        st.caption(f"Single ID works on up to {GROUPED_ID_MAX_PHOTOS} photos at a time.")
    elif not grouped_scope_valid:
        st.caption("Single ID works on one outing at a time, or on a standalone batch without a hike.")


def render_publishing_section(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    hikes: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    photos: list[dict[str, Any]],
) -> None:
    if not confirmed_observations:
        st.info("Confirmed species will show up here once you start reviewing photos.")
        return

    rows = build_publish_rows(hikes, confirmed_observations, photos)
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
        reset_publish_page()
        st.rerun()

    filtered_rows = [row for row in rows if publish_filter == "All" or row["publish_state"] == publish_filter]
    synchronize_publish_selection(filtered_rows)

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
        invalidate_data_cache()
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
        st.session_state.publish_page = 1
        st.rerun()
    total_pages = max(1, math.ceil(max(1, len(filtered_rows)) / resolve_page_size(len(filtered_rows), st.session_state.publish_page_size)))
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
        f"<div class='utility-rail-status'>{len(selected_rows)} selected • {len([row for row in filtered_rows if row['publish_state'] in {'Ready to post', 'Needs attention'}])} actionable</div>",
        unsafe_allow_html=True,
    )
    cols[3].markdown(
        f"<div class='utility-rail-status review-page-status'>{publish_filter}</div>",
        unsafe_allow_html=True,
    )
    page_rows, total_pages = paginate_items(filtered_rows, "publish_page", "publish_page_size")
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
            for row in page_rows:
                st.session_state.publish_selected_ids.add(row["observation"]["id"])
                st.session_state[f"publish_select_{row['observation']['id']}"] = True
            st.rerun()
        if select_cols[1].button("Clear page", key="publish_clear_page", use_container_width=True):
            for row in page_rows:
                st.session_state.publish_selected_ids.discard(row["observation"]["id"])
                st.session_state[f"publish_select_{row['observation']['id']}"] = False
            st.rerun()

    if not filtered_rows:
        st.info("Nothing matches this publishing filter right now.")
        return

    selected_ready_rows = [row for row in selected_rows if row["publish_state"] in {"Ready to post", "Needs attention"}]
    action_cols = st.columns([0.3, 0.26, 0.18, 0.12, 0.14], gap="small")
    if action_cols[0].button(
        f"Post selected ({len(selected_ready_rows)})",
        key="publish_post_selected",
        use_container_width=True,
        disabled=not is_inat_client_ready(inat_client) or not selected_ready_rows,
    ):
        post_selected_observations_to_inaturalist(repository, inat_client, selected_ready_rows)
        clear_publish_selection(selected_rows)
        st.rerun()
    if is_inat_client_ready(inat_client):
        action_cols[1].button(
            "Select ready to post",
            key="publish_select_ready",
            use_container_width=True,
            type="secondary",
            on_click=select_publish_rows,
            args=([row for row in filtered_rows if row["publish_state"] == "Ready to post"],),
        )
    elif action_cols[1].button(inat_connection_action_label(inat_client), key="publish_connect_inat", use_container_width=True, type="secondary"):
        open_inat_token_dialog()
    action_cols[2].button(
        "Clear selection",
        key="publish_clear_selection",
        use_container_width=True,
        type="secondary",
        disabled=not selected_rows,
        on_click=clear_publish_selection,
        args=(selected_rows,),
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
        posting = get_inat_posting(observation)
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
            publish_row_markup = (
                "<div class=\"publish-row-shell\">"
                "<div class=\"publish-row-header\">"
                f"{render_publish_state_chip(row['publish_state'])}"
                f"{posted_note_markup}"
                "</div>"
                f"<div class=\"species-summary-name\">{escape(observation.get('common_name') or observation.get('scientific_name') or 'Unknown species')}</div>"
                f"<div class=\"species-summary-scientific\">{escape(observation.get('scientific_name') or '')}</div>"
                f"<div class=\"species-summary-meta\">{escape(hike.get('title') or 'Untitled outing')} • {escape(str(hike.get('hike_date') or ''))}</div>"
                f"<p class='photo-meta publish-photo-meta'>{format_photo_meta_html(photo, selected_hike_id=photo.get('hike_id'), link_coordinates=True, include_map_link=True)}</p>"
                "</div>"
            )
            st.markdown(
                publish_row_markup,
                unsafe_allow_html=True,
            )
        select_key = f"publish_select_{observation['id']}"
        with cols[2]:
            current_selected = observation["id"] in st.session_state.publish_selected_ids
            if select_key not in st.session_state:
                st.session_state[select_key] = current_selected
            is_selected = st.checkbox("Select for publishing", key=select_key)
            if is_selected:
                st.session_state.publish_selected_ids.add(observation["id"])
            else:
                st.session_state.publish_selected_ids.discard(observation["id"])
        with cols[3]:
            if row["publish_state"] in {"Posted", "Ready to post", "Needs attention"}:
                render_publish_lane_management_controls(
                    repository,
                    inat_client,
                    observation,
                    photo,
                    key_prefix=f"publish_manage_{observation['id']}",
                )
                render_inat_posting_controls(
                    repository,
                    inat_client,
                    observation,
                    photo,
                    place_guess=hike.get("location_name"),
                    key_prefix=f"publish_row_{observation['id']}",
                )


def render_publish_state_chip(state: str) -> str:
    slug = state.lower().replace(" ", "-")
    return f"<span class='status-pill publish-{slug}'>{escape(state)}</span>"


def render_publish_lane_management_controls(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    observation: dict[str, Any],
    photo: dict[str, Any],
    *,
    key_prefix: str,
) -> None:
    posting = get_inat_posting(observation)
    already_posted = bool(posting.get("observation_id"))
    with st.popover("Manage ID"):
        if already_posted:
            st.caption("This record has already been posted. Edit or remove the iNaturalist observation there.")
            return

        st.caption("Change the confirmed ID before posting, or send this sighting back to review.")
        render_alternate_suggestions(
            repository,
            inat_client,
            observation,
            photo,
            key_prefix=f"{key_prefix}_alt",
        )

        with st.form(f"{key_prefix}_manual_form", enter_to_submit=False):
            st.markdown("<div class='sidebar-control-label'>Manual ID</div>", unsafe_allow_html=True)
            common_name = st.text_input("Common name", value=observation.get("common_name") or "", key=f"{key_prefix}_common")
            scientific_name = st.text_input("Scientific name", value=observation.get("scientific_name") or "", key=f"{key_prefix}_scientific")
            taxon_id_text = st.text_input(
                "iNaturalist taxon ID",
                value=str(observation.get("taxon_id") or ""),
                key=f"{key_prefix}_taxon_id",
                help="Optional. Leave blank if you only know the name.",
            )
            if st.form_submit_button("Save corrected ID", use_container_width=True):
                if not common_name.strip() and not scientific_name.strip():
                    st.error("Add at least a common name or scientific name.")
                    return
                taxon_id: int | None = None
                if taxon_id_text.strip():
                    try:
                        taxon_id = int(taxon_id_text.strip())
                    except ValueError:
                        st.error("Taxon ID must be a number.")
                        return
                updated = repository.update_observation_details(
                    observation["id"],
                    common_name=common_name,
                    scientific_name=scientific_name,
                    photo_id=observation.get("photo_id"),
                    is_primary=bool(observation.get("is_primary")),
                    status="confirmed",
                    source="manual_override",
                    taxon_id=taxon_id,
                    clear_confidence=True,
                )
                sync_species_override_payload(repository, observation, updated)
                if taxon_id is not None:
                    ensure_taxon_enrichment(repository, inat_client, updated)
                invalidate_data_cache()
                st.rerun()

        st.divider()
        st.caption("Remove from publish lane keeps the sighting, but sends it back to Species Review.")
        if st.button("Remove from publish lane", key=f"{key_prefix}_return_to_review", use_container_width=True, type="secondary"):
            repository.update_observation_status(observation["id"], "pending")
            repository.update_photo_processing_status(photo["id"], REVIEW_QUEUE_STATUS)
            st.session_state.publish_selected_ids.discard(observation["id"])
            st.session_state.species_review_mode = "Review"
            st.session_state.species_review_stage = "Needs decisions"
            invalidate_data_cache()
            st.rerun()


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


def get_publish_state(observation: dict[str, Any]) -> str:
    posting = get_inat_posting(observation)
    if posting.get("observation_id"):
        if posting.get("photo_attached") is False:
            return "Needs attention"
        return "Posted"
    return "Ready to post"


def count_publish_states(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"Ready to post": 0, "Needs attention": 0, "Posted": 0}
    for row in rows:
        counts[row["publish_state"]] = counts.get(row["publish_state"], 0) + 1
    return counts


def build_publish_rows(
    hikes: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    photos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hike_by_id = {str(hike["id"]): hike for hike in hikes}
    photo_by_id = {str(photo["id"]): photo for photo in photos}
    rows: list[dict[str, Any]] = []
    for observation in confirmed_observations:
        photo = photo_by_id.get(str(observation.get("photo_id")))
        if not photo:
            continue
        hike = hike_by_id.get(str(observation.get("hike_id")), {})
        if not hike and not observation.get("hike_id"):
            hike = {"title": "Standalone sighting", "hike_date": photo.get("taken_at") or photo.get("created_at") or "", "location_name": photo.get("caption") or "Not attached to a hike"}
        rows.append(
            {
                "observation": observation,
                "photo": photo,
                "hike": hike,
                "publish_state": get_publish_state(observation),
            }
        )
    rows.sort(
        key=lambda row: (
            {"Needs attention": 0, "Ready to post": 1, "Posted": 2}.get(row["publish_state"], 3),
            row["photo"].get("taken_at") or row["photo"].get("created_at") or "",
        ),
        reverse=False,
    )
    return rows


def synchronize_publish_selection(rows: list[dict[str, Any]]) -> None:
    valid_ids = {row["observation"]["id"] for row in rows}
    st.session_state.publish_selected_ids = {
        observation_id for observation_id in st.session_state.publish_selected_ids if observation_id in valid_ids
    }
    for row in rows:
        checkbox_key = f"publish_select_{row['observation']['id']}"
        if checkbox_key not in st.session_state:
            continue
        if st.session_state[checkbox_key]:
            st.session_state.publish_selected_ids.add(row["observation"]["id"])
        else:
            st.session_state.publish_selected_ids.discard(row["observation"]["id"])


def clear_publish_selection(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        observation_id = row["observation"]["id"]
        st.session_state.publish_selected_ids.discard(observation_id)
        checkbox_key = f"publish_select_{observation_id}"
        if checkbox_key in st.session_state:
            st.session_state[checkbox_key] = False


def select_publish_rows(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        observation_id = row["observation"]["id"]
        st.session_state.publish_selected_ids.add(observation_id)
        st.session_state[f"publish_select_{observation_id}"] = True


def fetch_full_observation_for_post(observation_id: str) -> dict[str, Any] | None:
    observations = fetch_observations_by_ids((str(observation_id),))
    return observations[0] if observations else None


def post_selected_observations_to_inaturalist(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return
    try:
        inat_client.validate_credentials()
    except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
        st.session_state.inat_auth_notice = None
        st.session_state.inat_auth_error = str(exc)
        st.error(str(exc))
        return
    progress_text = st.empty()
    progress_bar = st.progress(0, text="Preparing observations for iNaturalist...")
    total = len(rows)
    with st.spinner("Posting observations to iNaturalist..."):
        for index, row in enumerate(rows, start=1):
            progress_text.caption(f"Posting observation {index} of {total}")
            full_observation = fetch_full_observation_for_post(row["observation"]["id"])
            if not full_observation:
                st.error("HikeJournal could not load an observation needed for posting.")
                continue
            try:
                post_observation_to_inaturalist(
                    repository,
                    inat_client,
                    full_observation,
                    row["photo"],
                    place_guess=row["hike"].get("location_name"),
                )
            except (InatConfigurationError, InatAuthError, InatRequestError, RuntimeError) as exc:
                st.error(f"{row['observation']['common_name'] or row['observation']['scientific_name'] or row['observation']['id']}: {exc}")
            else:
                progress_bar.progress(index / total, text=f"Posted {index} of {total} observations")
    invalidate_data_cache()


def render_species_log_toolbar(
    species_rows: list[dict[str, Any]],
    page_rows: list[dict[str, Any]],
    total_pages: int,
) -> None:
    cols = st.columns([0.16, 0.14, 0.46, 0.24], gap="small")
    page_size_options = [8, 12, 16, 24, 0]
    page_size = cols[0].selectbox(
        "Per page",
        page_size_options,
        index=page_size_options.index(st.session_state.species_log_page_size),
        key="species_log_page_size_select",
        format_func=lambda value: "All" if value == 0 else str(value),
    )
    if page_size != st.session_state.species_log_page_size:
        st.session_state.species_log_page_size = page_size
        st.session_state.species_log_page = 1
        st.rerun()
    requested_page = cols[1].number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        value=st.session_state.species_log_page,
        step=1,
        key="species_log_page_number",
    )
    if requested_page != st.session_state.species_log_page:
        st.session_state.species_log_page = int(requested_page)
        st.rerun()
    cols[2].markdown(
        f"<div class='utility-rail-status'>{len(page_rows)} species on this page • {len(species_rows)} matched overall</div>",
        unsafe_allow_html=True,
    )
    with cols[3].popover("Manage"):
        st.caption(f"Page {st.session_state.species_log_page} of {total_pages}")
        nav_cols = st.columns(2, gap="small")
        if nav_cols[0].button(
            "Previous",
            key="species_log_prev_page",
            use_container_width=True,
            disabled=st.session_state.species_log_page <= 1,
        ):
            st.session_state.species_log_page -= 1
            st.rerun()
        if nav_cols[1].button(
            "Next",
            key="species_log_next_page",
            use_container_width=True,
            disabled=st.session_state.species_log_page >= total_pages,
        ):
            st.session_state.species_log_page += 1
            st.rerun()


def _candidate_identity_key(candidate: SpeciesCandidate) -> str:
    if candidate.taxon_id is not None:
        return f"taxon:{candidate.taxon_id}"
    scientific = (candidate.scientific_name or "").strip().lower()
    common = (candidate.common_name or "").strip().lower()
    return f"name:{scientific or common or 'unknown'}"


def _build_grouped_species_candidate(
    inat_client: InatClient,
    photos_to_process: list[dict[str, Any]],
) -> tuple[SpeciesCandidate, list[dict[str, Any]], list[str]]:
    aggregate: dict[str, dict[str, Any]] = {}
    processed_photos: list[dict[str, Any]] = []
    warnings: list[str] = []
    per_photo_candidates: list[dict[str, Any]] = []

    for photo in photos_to_process:
        try:
            candidates, _payload = inat_client.score_species_candidates(
                image_bytes=_download_public_image(photo["public_url"]),
                filename=f"{photo['id']}.jpg",
                lat=photo.get("lat"),
                lng=photo.get("lng"),
                observed_on=_parse_datetime(photo.get("taken_at")),
                limit=5,
            )
        except (InatConfigurationError, InatAuthError):
            raise
        except (InatRequestError, RuntimeError) as exc:
            warnings.append(f"{photo['id'][:8]}: {exc}")
            continue

        processed_photos.append(photo)
        compact_candidates: list[dict[str, Any]] = []
        for rank, candidate in enumerate(candidates, start=1):
            key = _candidate_identity_key(candidate)
            entry = aggregate.setdefault(
                key,
                {
                    "taxon_id": candidate.taxon_id,
                    "common_name": candidate.common_name,
                    "scientific_name": candidate.scientific_name,
                    "support_count": 0,
                    "top1_count": 0,
                    "total_confidence": 0.0,
                    "best_confidence": 0.0,
                },
            )
            entry["support_count"] += 1
            entry["total_confidence"] += float(candidate.confidence or 0)
            entry["best_confidence"] = max(entry["best_confidence"], float(candidate.confidence or 0))
            if rank == 1:
                entry["top1_count"] += 1
            compact_candidates.append(
                {
                    "taxon_id": candidate.taxon_id,
                    "common_name": candidate.common_name,
                    "scientific_name": candidate.scientific_name,
                    "confidence": float(candidate.confidence or 0),
                    "rank": rank,
                }
            )
        per_photo_candidates.append({"photo_id": photo["id"], "candidates": compact_candidates})

    if len(processed_photos) < 2:
        raise InatRequestError(
            "Grouped ID needs at least 2 photos with usable suggestions. Try the regular Process selected button or choose a tighter set."
        )

    aggregate_candidates = sorted(
        (
            {
                **entry,
                "average_confidence": (entry["total_confidence"] / entry["support_count"]) if entry["support_count"] else 0.0,
            }
            for entry in aggregate.values()
        ),
        key=lambda entry: (
            int(entry["top1_count"]),
            int(entry["support_count"]),
            float(entry["total_confidence"]),
            float(entry["best_confidence"]),
        ),
        reverse=True,
    )
    top_match = aggregate_candidates[0]
    raw_payload = {
        "grouped_cv": True,
        "group_size": len(processed_photos),
        "group_photo_ids": [photo["id"] for photo in processed_photos],
        "aggregate_candidates": aggregate_candidates,
        "per_photo_candidates": per_photo_candidates,
        "results": [
            {
                "combined_score": entry["average_confidence"],
                "support_count": entry["support_count"],
                "top1_count": entry["top1_count"],
                "taxon": {
                    "id": entry["taxon_id"],
                    "preferred_common_name": entry["common_name"],
                    "name": entry["scientific_name"],
                },
            }
            for entry in aggregate_candidates
        ],
    }
    grouped_candidate = SpeciesCandidate(
        common_name=str(top_match.get("common_name") or top_match.get("scientific_name") or "Unknown species"),
        scientific_name=str(top_match.get("scientific_name") or top_match.get("common_name") or "Unknown species"),
        confidence=float(top_match.get("average_confidence") or 0),
        taxon_id=top_match.get("taxon_id"),
        raw_payload=raw_payload,
    )
    return grouped_candidate, processed_photos, warnings


def process_species_photo_group(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    photos_to_consider: list[dict[str, Any]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
) -> int:
    photos_to_process = [photo for photo in photos_to_consider if photo["id"] not in primary_observation_by_photo]
    if len(photos_to_process) < 2:
        st.info("Pick at least 2 unprocessed photos to save one shared iNaturalist suggestion.")
        return 0
    if len(photos_to_process) > GROUPED_ID_MAX_PHOTOS:
        st.info(f"Grouped ID works on up to {GROUPED_ID_MAX_PHOTOS} photos at a time.")
        return 0
    grouped_scope_ids = {str(photo.get("hike_id") or "standalone") for photo in photos_to_process}
    if len(grouped_scope_ids) > 1:
        st.info("Grouped ID works on one outing at a time, or on a standalone batch without a hike.")
        return 0
    try:
        inat_client.validate_credentials()
    except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
        st.session_state.inat_auth_notice = None
        st.session_state.inat_auth_error = str(exc)
        st.error(str(exc))
        return 0

    st.session_state.inat_auth_error = None
    with st.spinner("Scoring the selected photos together as one shared ID..."):
        try:
            grouped_candidate, processed_photos, warnings = _build_grouped_species_candidate(inat_client, photos_to_process)
        except (InatConfigurationError, InatAuthError) as exc:
            st.session_state.inat_auth_notice = None
            st.session_state.inat_auth_error = str(exc)
            st.error(str(exc))
            return 0
        except (InatRequestError, RuntimeError) as exc:
            st.error(str(exc))
            return 0

        saved_names = []
        for photo in processed_photos:
            observation = repository.upsert_observation(
                photo.get("hike_id"),
                photo["id"],
                grouped_candidate,
                owner_subject=photo.get("owner_subject"),
                owner_email=photo.get("owner_email"),
            )
            ensure_taxon_enrichment(repository, inat_client, observation)
            saved_names.append(photo["id"])

    invalidate_data_cache()
    if warnings:
        st.warning("Grouped ID skipped a few photos that did not produce a usable suggestion:\n\n- " + "\n- ".join(warnings))
    st.success(
        f"Saved one shared iNaturalist suggestion across {len(saved_names)} photos: "
        f"{grouped_candidate.common_name or grouped_candidate.scientific_name}."
    )
    return len(saved_names)


def process_species_photos(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    photos_to_consider: list[dict[str, Any]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
) -> int:
    photos_to_process = [photo for photo in photos_to_consider if photo["id"] not in primary_observation_by_photo]
    if not photos_to_process:
        st.info("Everything selected here already has a saved species suggestion.")
        return 0
    try:
        inat_client.validate_credentials()
    except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
        st.session_state.inat_auth_notice = None
        st.session_state.inat_auth_error = str(exc)
        st.error(str(exc))
        return 0
    st.session_state.inat_auth_error = None
    total_photos = len(photos_to_process)
    successful_count = 0
    progress_text = st.empty()
    progress_bar = st.progress(0, text="Preparing photos for identification...")
    with st.spinner("Sending photos to iNaturalist..."):
        for index, photo in enumerate(photos_to_process, start=1):
            progress_text.caption(
                f"Processing photo {index} of {total_photos}. "
                f"HikeJournal is spacing image-ID requests about {inat_client.cv_request_interval_seconds:g}s apart so iNaturalist does not throttle the batch."
            )
            try:
                candidate = inat_client.identify_species(
                    image_bytes=_download_public_image(photo["public_url"]),
                    filename=f"{photo['id']}.jpg",
                    lat=photo.get("lat"),
                    lng=photo.get("lng"),
                    observed_on=_parse_datetime(photo.get("taken_at")),
                )
                observation = repository.upsert_observation(
                    photo.get("hike_id"),
                    photo["id"],
                    candidate,
                    owner_subject=photo.get("owner_subject"),
                    owner_email=photo.get("owner_email"),
                )
                ensure_taxon_enrichment(repository, inat_client, observation)
            except (InatConfigurationError, InatAuthError) as exc:
                st.session_state.inat_auth_notice = None
                st.session_state.inat_auth_error = str(exc)
                progress_bar.empty()
                progress_text.caption(f"Stopped after {index - 1} of {total_photos} photos.")
                st.error(str(exc))
                break
            except InatRateLimitError as exc:
                st.session_state.inat_auth_notice = None
                st.session_state.inat_auth_error = str(exc)
                progress_bar.empty()
                progress_text.caption(
                    f"iNaturalist asked HikeJournal to slow down after {successful_count} of {total_photos} photos. "
                    "The remaining photos are still selected in Needs IDs."
                )
                st.warning(str(exc))
                break
            except InatComputerVisionBlockedError as exc:
                st.session_state.inat_auth_notice = None
                st.session_state.inat_auth_error = str(exc)
                progress_bar.empty()
                progress_text.caption(
                    f"Stopped after {successful_count} of {total_photos} photos because iNaturalist blocked CV suggestions from this server. "
                    "The remaining photos are still selected in Needs IDs."
                )
                st.warning(str(exc))
                break
            except (InatRequestError, RuntimeError) as exc:
                st.error(f"{photo['id'][:8]}: {exc}")
            else:
                successful_count += 1
                progress_bar.progress(index / total_photos, text=f"Processed {index} of {total_photos} photos")
    invalidate_data_cache()
    if not st.session_state.inat_auth_error:
        progress_text.caption(f"Finished processing {total_photos} photo{'s' if total_photos != 1 else ''}.")
    return successful_count


def confirm_observations(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    observations: list[dict[str, Any]],
) -> None:
    confirmed_photo_ids: set[str] = set()
    for observation in observations:
        confirm_observation(repository, inat_client, observation)
        repository.update_observation_status(observation["id"], "confirmed")
        if observation.get("photo_id"):
            confirmed_photo_ids.add(str(observation["photo_id"]))
    repository.update_photo_processing_statuses(list(confirmed_photo_ids), "ready")
    invalidate_data_cache()


def reject_observations(
    repository: HikeJournalRepository,
    observations: list[dict[str, Any] | None],
    photos: list[dict[str, Any]],
) -> None:
    rejected_photo_ids: set[str] = set()
    for observation in observations:
        if not observation:
            continue
        repository.update_observation_status(observation["id"], "rejected")
        if observation.get("photo_id"):
            rejected_photo_ids.add(str(observation["photo_id"]))
    photo_ids_to_reset = [
        photo["id"]
        for photo in photos
        if not rejected_photo_ids or photo["id"] in rejected_photo_ids
    ]
    repository.update_photo_processing_statuses(photo_ids_to_reset, "ready")
    invalidate_data_cache()


def synchronize_species_selection(selected_photos: list[dict[str, Any]]) -> None:
    valid_ids = {photo["id"] for photo in selected_photos}
    st.session_state.species_selected_ids = {
        photo_id for photo_id in st.session_state.species_selected_ids if photo_id in valid_ids
    }
    for photo in selected_photos:
        checkbox_key = f"species_select_{photo['id']}"
        if checkbox_key not in st.session_state:
            continue
        if st.session_state[checkbox_key]:
            st.session_state.species_selected_ids.add(photo["id"])
        else:
            st.session_state.species_selected_ids.discard(photo["id"])


def apply_species_review_default_state(selected_photos: list[dict[str, Any]]) -> None:
    signature = tuple(photo["id"] for photo in selected_photos)
    if st.session_state.species_review_initialized_signature == signature:
        return
    st.session_state.species_review_initialized_signature = signature
    st.session_state.species_page = 1
    st.session_state.species_page_size = 0 if selected_photos else 6
    st.session_state.species_selected_ids = {photo["id"] for photo in selected_photos}
    for photo in selected_photos:
        st.session_state[f"species_select_{photo['id']}"] = True


def clear_species_selection(photos: list[dict[str, Any]]) -> None:
    for photo in photos:
        st.session_state.species_selected_ids.discard(photo["id"])
        checkbox_key = f"species_select_{photo['id']}"
        if checkbox_key in st.session_state:
            st.session_state[checkbox_key] = False


def reset_species_log_page() -> None:
    st.session_state.species_log_page = 1
    st.session_state.species_log_focus_key = None


def reset_library_page() -> None:
    st.session_state.library_page = 1


def reset_publish_page() -> None:
    st.session_state.publish_page = 1


def dedupe_records_by_id(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for record in records:
        record_id = str(record.get("id") or "")
        if not record_id or record_id in seen_ids:
            continue
        seen_ids.add(record_id)
        deduped.append(record)
    return deduped


def resolve_page_size(total_items: int, configured_size: int) -> int:
    if configured_size == 0:
        return max(1, total_items)
    return configured_size


def render_back_to_top_link(anchor_id: str) -> None:
    st.markdown(
        f"""
        <div class="back-to-top-shell">
            <a class="back-to-top-link" href="#{anchor_id}">Back to top</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_internal_view_href(*, view: str, hike_id: str | None = None, scope: str | None = None) -> str:
    params: dict[str, Any] = {"view": view}
    params.update(get_query_state_for_view(view))
    if hike_id:
        params["hike"] = hike_id
    if scope:
        params["scope"] = scope
    return f"?{urlencode(params, quote_via=quote)}"


def build_species_log_record_href(focus_key: str) -> str:
    params = {"view": "Species Log", **get_query_state_for_view("Species Log")}
    params["species_log_focus_key"] = str(focus_key)
    params["species_log_record_open"] = "1"
    return f"?{urlencode(params, quote_via=quote)}"


def set_species_log_record_query_state(focus_key: str | None, is_open: bool) -> None:
    if focus_key:
        st.query_params["species_log_focus_key"] = str(focus_key)
    elif "species_log_focus_key" in st.query_params:
        del st.query_params["species_log_focus_key"]
    st.query_params["species_log_record_open"] = "1" if is_open else "0"


def render_bottom_review_handoff(*, anchor_id: str, selected_count: int, hike_id: str | None = None) -> None:
    if selected_count <= 0 and st.session_state.journal_page_size != 0:
        return
    actions: list[str] = []
    if selected_count > 0:
        actions.append(
            f"<a class='journal-footer-link journal-footer-link--accent' href='{escape(build_internal_view_href(view='Species Review', hike_id=hike_id))}' target='_self'>Open Species Review ({selected_count})</a>"
        )
    if st.session_state.journal_page_size == 0:
        actions.append(f"<a class='journal-footer-link' href='#{escape(anchor_id)}'>Back to top</a>")
    if actions:
        st.markdown(
            f"<div class='journal-footer-actions'>{''.join(actions)}</div>",
            unsafe_allow_html=True,
        )


def sync_viewer_from_query_params(photos: list[dict[str, Any]]) -> None:
    photo_id = st.query_params.get("photo")
    if not photo_id:
        return
    for index, photo in enumerate(photos):
        if photo["id"] == str(photo_id):
            st.session_state.viewer_open = True
            st.session_state.viewer_index = index
            break


def _download_public_image(public_url: str) -> bytes:
    import requests

    response = requests.get(public_url, timeout=30)
    response.raise_for_status()
    return response.content


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


if __name__ == "__main__":
    main()
