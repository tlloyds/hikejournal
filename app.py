from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from html import escape
import math
import secrets
from typing import Any
from urllib.parse import quote

import streamlit as st

from hike_journal.config import (
    build_inat_token_identity,
    delete_inat_token_record_for_user,
    load_inat_access_token_for_user,
    load_inat_token_record_for_user,
    settings,
)
from hike_journal.models import HikeDraft, SpeciesCandidate
from hike_journal.application import ApplicationActions, run_application
from hike_journal.navigation import (
    apply_navigation,
    build_internal_view_href as build_view_href,
    build_species_log_record_href as build_species_record_href,
    hydrate_query_state,
    query_state_for_view,
    set_species_log_record_query_state as update_species_record_query_state,
    sync_viewer_state,
)
from hike_journal.domain.locations import (
    autotag_matching_hikes,
    load_seed_hike_locations,
    location_library_options,
    maybe_store_hike_location_tags,
    selected_location_defaults,
)
from hike_journal.domain.routes import (
    delete_hike_and_assets,
    parse_uploaded_route_import,
    sync_hike_route_import,
)
from hike_journal.domain.library import (
    build_species_group_key,
    entry_sort_datetime as _entry_sort_datetime,
    format_species_log_date_label,
    normalize_email,
    record_visible_for_user,
)
from hike_journal.queries import (
    fetch_hike_lightweight_observations,
    fetch_hike_locations,
    fetch_hike_photos,
    fetch_hike_route_import,
    fetch_observations_by_ids,
    fetch_photo_storage_records,
    fetch_species_log_photo_preferences,
    invalidate_data_cache,
)
from hike_journal.review_state import (
    clear_species_selection as clear_review_selection,
    set_photos_selected,
    sync_visible_widget_selection,
)
from hike_journal.publishing_state import (
    build_publish_rows as build_publish_rows_state,
    count_publish_states as count_publish_states_state,
    get_publish_state as get_publish_state_value,
    set_publish_rows_selected,
)
from hike_journal.services.exif import extract_metadata
from hike_journal.services.encounters import (
    build_publish_encounter_plan,
    build_review_photo_encounter_plan,
    split_encounter_plan,
    split_review_photo_encounter_plan,
)
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
from hike_journal.services.species_identification import (
    is_species_log_main_photo,
    select_shared_candidate,
    update_species_log_main_photo_payload,
)
from hike_journal.services.storage import StorageService
from hike_journal.ui.components import (
    format_photo_meta,
    format_photo_meta_html,
    get_photo_thumbnail_url,
    render_clickable_photo_with_view,
    render_hero,
    render_observation_badge,
    section_heading,
)
from hike_journal.ui.theme import apply_theme
from hike_journal.ui.state import initialize_session_state
from hike_journal.ui.views.library import render_library_view
from hike_journal.ui.views.journal import JournalActions, render_journal_view, render_standalone_journal_view
from hike_journal.ui.views.map import render_map_view
from hike_journal.ui.views.publishing import (
    PublishingActions,
    render_publish_state_chip,
    render_publishing_view,
)
from hike_journal.ui.views.species_log import render_species_log_view
from hike_journal.ui.views.species_review import SpeciesReviewActions, render_species_review_view


st.set_page_config(page_title="HikeJournal", page_icon="🥾", layout="wide")
apply_theme()
REVIEW_QUEUE_STATUS = "in_review"
TCX_IMPORT_TYPES = ["tcx", "xml"]
GROUPED_ID_MAX_PHOTOS = 8
SMART_ID_MAX_DISTANCE_METERS = 12
SMART_ID_MAX_MINUTES = 2
GROUPED_PUBLISH_MAX_PHOTOS = 8
QUICK_UPLOAD_HIKE_FILTER = "Quick uploads"

initialize_session_state(st.session_state)


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
    run_application(
        ApplicationActions(
            build_species_log_context=build_species_log_context,
            dedupe_records_by_id=dedupe_records_by_id,
            get_inat_access_token_for_context=get_inat_access_token_for_context,
            get_primary_observation=get_primary_observation,
            get_user_context=get_user_context,
            group_observations_by_photo=group_observations_by_photo,
            maybe_handle_inat_oauth_callback=maybe_handle_inat_oauth_callback,
            maybe_migrate_legacy_inat_token=maybe_migrate_legacy_inat_token,
            render_access_denied=render_access_denied,
            render_auth_configuration_state=render_auth_configuration_state,
            render_empty_state=render_empty_state,
            render_footer=render_footer,
            render_inat_token_dialog=render_inat_token_dialog,
            render_journal_tab=render_journal_tab,
            render_library_tab=render_library_tab,
            render_login_gate=render_login_gate,
            render_map_tab=render_map_tab,
            render_mobile_shell=render_mobile_shell,
            render_photo_viewer=render_photo_viewer,
            render_setup_state=render_setup_state,
            render_sidebar=render_sidebar,
            render_species_log_tab=render_species_log_tab,
            render_species_tab=render_species_tab,
            render_standalone_journal_tab=render_standalone_journal_tab,
            sync_pagination_state_from_query_params=sync_pagination_state_from_query_params,
            sync_viewer_from_query_params=sync_viewer_from_query_params,
        )
    )


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
                f"<a class='viewer-link' href='{escape(authorize_url)}' target='_blank' rel='noopener noreferrer'>Connect iNaturalist</a>",
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
        <a class="sidebar-brand-shell" href="?view=Library&amp;scope=global" target="_self" aria-label="Open HikeJournal Library">
            <div class="sidebar-brand-kicker">Field Journal</div>
            <div class="sidebar-brand-wordmark">HikeJournal</div>
            <div class="sidebar-brand-meta">{escape(identity_line)}</div>
        </a>
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

    render_location_library_sidebar_tools(repository, hikes)

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


def render_location_library_sidebar_tools(repository: HikeJournalRepository, hikes: list[dict[str, Any]]) -> None:
    locations = fetch_hike_locations()
    seed_count = len(load_seed_hike_locations())
    st.write("")
    st.markdown("<div class='sidebar-section-label'>Locations</div>", unsafe_allow_html=True)
    with st.popover("Location library", use_container_width=True):
        st.caption(f"{len(locations)} locations loaded • {seed_count} in seed file")
        if st.session_state.location_library_notice:
            st.success(str(st.session_state.location_library_notice))
            st.session_state.location_library_notice = None
        action_cols = st.columns(2, gap="small")
        if action_cols[0].button("Import", key="sidebar_import_location_library", use_container_width=True):
            imported_count = repository.upsert_hike_locations(load_seed_hike_locations())
            invalidate_data_cache()
            st.session_state.location_library_notice = f"Imported {imported_count} mapped Central Florida locations."
            st.rerun()
        if action_cols[1].button("Auto-tag", key="sidebar_autotag_hike_locations", use_container_width=True):
            latest_locations = fetch_hike_locations()
            tagged_count = autotag_matching_hikes(repository, hikes, latest_locations)
            invalidate_data_cache()
            st.session_state.location_library_notice = f"Tagged {tagged_count} existing hike{'s' if tagged_count != 1 else ''} from title/location matches."
            st.rerun()
        st.divider()
        with st.form("sidebar_add_location_form"):
            name = st.text_input("Add location", placeholder="Black Bear Wilderness Area")
            aliases = st.text_input("Aliases", placeholder="Optional, comma-separated")
            location_type = st.text_input("Type", placeholder="preserve, state forest, trail...")
            submitted = st.form_submit_button("Add", use_container_width=True)
            if submitted:
                clean_name = name.strip()
                if not clean_name:
                    st.warning("Add a location name first.")
                    return
                created = repository.upsert_hike_location(
                    clean_name,
                    source="manual",
                    location_type=location_type.strip() or "manual",
                    aliases=[alias.strip() for alias in aliases.split(",") if alias.strip()],
                )
                invalidate_data_cache()
                if created:
                    st.session_state.location_library_notice = f"Added {clean_name} to the location library."
                else:
                    st.session_state.location_library_notice = f"Tried to add {clean_name}, but the database did not return a saved location."
                st.rerun()


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
                bottom: calc(4.15rem + env(safe-area-inset-bottom, 0px));
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
    apply_navigation(
        st.session_state,
        st.query_params,
        view=view,
        hike_id=hike_id,
        photo_id=photo_id,
        map_photo_id=map_photo_id,
        scope=scope,
    )
    st.rerun()


def sync_pagination_state_from_query_params() -> None:
    hydrate_query_state(st.session_state, st.query_params)


def get_query_state_for_view(view: str) -> dict[str, str]:
    return query_state_for_view(view, st.session_state)


@st.dialog("New Hike", width="large")
def render_create_hike_dialog(repository: HikeJournalRepository, storage: StorageService, user_context: dict[str, Any]) -> None:
    st.caption("Start a new outing and add it to your library.")
    hike_locations = fetch_hike_locations()
    location_options = location_library_options(hike_locations)
    form_placeholder = st.empty()
    with form_placeholder.container():
        with st.form("create_hike_dialog_form", clear_on_submit=True):
            title = st.text_input("Hike title", placeholder="Black Bear Wilderness Loop")
            hike_date = st.date_input("Hike date", value=date.today())
            distance = st.number_input("Distance (miles)", min_value=0.0, step=0.5, value=0.0)
            location_name = st.text_input("Location", placeholder="Seminole State Forest")
            selected_locations = st.multiselect(
                "Location tags",
                options=location_options,
                default=[],
                accept_new_options=True,
                placeholder="Start typing Bronson, Chuluota, Econ...",
            )
            notes = st.text_area("Opening notes", placeholder="What stood out about the day?", height=140)
            route_import_file = st.file_uploader(
                "MapMyRun TCX exports",
                type=TCX_IMPORT_TYPES,
                accept_multiple_files=True,
                help="Optional: upload one or more TCX exports for this outing to save route lines and route stats.",
            )
            use_imported_route_fields = st.checkbox("Use TCX date and distance for this outing", value=True)
            submitted = st.form_submit_button("Create hike", use_container_width=True)

    if not submitted:
        return
    if not title.strip():
        st.warning("Add a hike title to save this outing.")
        return

    parsed_route_import, _, route_import_error = parse_uploaded_route_import(route_import_file)
    if route_import_error:
        st.warning(route_import_error)
        return

    form_placeholder.empty()
    with st.status("Creating hike...", expanded=True) as creation_status:
        target_hike_date = parsed_route_import.visited_on if parsed_route_import and use_imported_route_fields and parsed_route_import.visited_on else hike_date
        target_distance = parsed_route_import.distance_miles if parsed_route_import and use_imported_route_fields and parsed_route_import.distance_miles is not None else (distance or None)
        saved_location_name = location_name.strip() or ", ".join(selected_locations[:3])
        draft = HikeDraft(
            title=title,
            hike_date=target_hike_date,
            distance_miles=target_distance,
            location_name=saved_location_name,
            notes=notes,
            owner_subject=user_context.get("subject") if user_context.get("mode") == "google" else None,
            owner_email=user_context.get("email") if user_context.get("mode") == "google" else None,
        )
        creation_status.write("Saving outing details...")
        created = repository.create_hike(draft)
        maybe_store_hike_location_tags(repository, created["id"], selected_locations, hike_locations)
        if route_import_file:
            creation_status.write("Saving the imported route data...")
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
        creation_status.update(label="Hike created. Opening journal...", state="complete", expanded=False)
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
    hike_locations = fetch_hike_locations()
    location_options = location_library_options(hike_locations)
    with st.form(f"edit_hike_dialog_{hike['id']}"):
        title = st.text_input("Title", value=hike.get("title") or "")
        hike_date = st.date_input("Date", value=_parse_date(hike.get("hike_date")))
        distance_value = float(hike.get("distance_miles") or 0.0)
        distance = st.number_input("Distance (miles)", min_value=0.0, step=0.5, value=distance_value)
        location_name = st.text_input("Location", value=hike.get("location_name") or "")
        selected_locations = st.multiselect(
            "Location tags",
            options=location_options,
            default=selected_location_defaults(hike),
            accept_new_options=True,
            placeholder="Start typing Bronson, Chuluota, Econ...",
        )
        notes = st.text_area("Notes", value=hike.get("notes") or "", height=140)
        route_import_file = st.file_uploader(
            "MapMyRun TCX exports",
            type=TCX_IMPORT_TYPES,
            accept_multiple_files=True,
            help="Upload one or more TCX files to replace the saved route for this outing.",
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
            saved_location_name = location_name.strip() or ", ".join(selected_locations[:3])
            repository.update_hike(
                hike["id"],
                title=title,
                hike_date=target_hike_date,
                distance_miles=target_distance,
                location_name=saved_location_name,
                notes=notes,
            )
            maybe_store_hike_location_tags(repository, hike["id"], selected_locations, hike_locations)
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

    st.divider()
    st.markdown("##### Delete outing")
    st.caption("Deletes the hike, its photos, saved species suggestions, route import, and uploaded files.")
    confirm_delete = st.checkbox("I understand this permanently deletes the outing", key=f"delete_hike_confirm_{hike['id']}")
    delete_text = st.text_input(
        "Type DELETE to confirm",
        key=f"delete_hike_text_{hike['id']}",
        placeholder="DELETE",
    )
    if st.button(
        "Delete this hike",
        key=f"delete_hike_button_{hike['id']}",
        use_container_width=True,
        type="secondary",
        disabled=not confirm_delete or delete_text.strip() != "DELETE",
    ):
        with st.spinner("Deleting outing..."):
            delete_hike_and_assets(repository, storage, str(hike["id"]))
        st.session_state.selected_hike_id = None
        st.session_state.active_view = "Library"
        st.session_state.pending_view = "Library"
        invalidate_data_cache()
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
    render_library_view(
        repository,
        storage,
        hikes,
        photo_refs,
        confirmed_observations,
        cover_photos_by_id,
        user_context,
        navigate_to=navigate_to,
        paginate_items=paginate_items,
        render_back_to_top_link=render_back_to_top_link,
        render_create_hike_dialog=render_create_hike_dialog,
        render_edit_hike_dialog=render_edit_hike_dialog,
        render_quick_upload_dialog=render_quick_upload_dialog,
        reset_library_page=reset_library_page,
    )

def _journal_actions() -> JournalActions:
    return JournalActions(
        _parse_date=_parse_date,
        paginate_photos=paginate_photos,
        persist_uploaded_photo=persist_uploaded_photo,
        render_alternate_suggestions=render_alternate_suggestions,
        render_bottom_review_handoff=render_bottom_review_handoff,
        render_known_species_assignment_toolbar=render_known_species_assignment_toolbar,
        render_photo_management_toolbar=render_photo_management_toolbar,
        render_photo_note_editor=render_photo_note_editor,
        render_photo_species_actions=render_photo_species_actions,
        render_quick_upload_dialog=render_quick_upload_dialog,
        render_secondary_species_summary=render_secondary_species_summary,
        render_selection_toolbar=render_selection_toolbar,
        render_species_summary=render_species_summary,
        sync_hike_cover_checkbox=sync_hike_cover_checkbox,
        sync_journal_review_checkbox=sync_journal_review_checkbox,
        sync_known_species_checkbox=sync_known_species_checkbox,
    )


def render_standalone_journal_tab(
    repository: HikeJournalRepository,
    storage: StorageService,
    inat_client: InatClient,
    photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    user_context: dict[str, Any],
    known_species: list[dict[str, Any]],
) -> None:
    render_standalone_journal_view(
        repository,
        storage,
        inat_client,
        photos,
        observations_by_photo,
        primary_observation_by_photo,
        user_context,
        known_species,
        actions=_journal_actions(),
    )


def render_journal_tab(
    repository: HikeJournalRepository,
    storage: StorageService,
    inat_client: InatClient,
    selected_hike: dict[str, Any],
    photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    route_import: dict[str, Any] | None,
    known_species: list[dict[str, Any]],
) -> None:
    render_journal_view(
        repository,
        storage,
        inat_client,
        selected_hike,
        photos,
        observations_by_photo,
        primary_observation_by_photo,
        route_import,
        known_species,
        actions=_journal_actions(),
    )


def _species_review_actions() -> SpeciesReviewActions:
    return SpeciesReviewActions(
        build_publish_rows=build_publish_rows,
        count_publish_states=count_publish_states,
        paginate_items=paginate_items,
        render_add_species_popover=render_add_species_popover,
        render_alternate_suggestions=render_alternate_suggestions,
        render_back_to_top_link=render_back_to_top_link,
        render_community_id_request_controls=render_community_id_request_controls,
        render_inat_token_manager=render_inat_token_manager,
        render_photo_note_editor=render_photo_note_editor,
        render_publishing_section=render_publishing_section,
        render_secondary_species_summary=render_secondary_species_summary,
        render_species_management_toolbar=render_species_management_toolbar,
        render_species_summary=render_species_summary,
    )


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
    render_species_review_view(
        repository,
        inat_client,
        hikes,
        review_queue_photos,
        publish_confirmed_observations,
        publish_photos,
        observations_by_photo,
        primary_observation_by_photo,
        actions=_species_review_actions(),
    )

def render_map_tab(
    photos: list[dict[str, Any]],
    observations_by_photo: dict[str, list[dict[str, Any]]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    *,
    selected_hike: dict[str, Any] | None,
    route_imports_by_hike: dict[str, dict[str, Any]],
) -> None:
    render_map_view(
        photos,
        observations_by_photo,
        primary_observation_by_photo,
        selected_hike=selected_hike,
        route_imports_by_hike=route_imports_by_hike,
        format_confidence_label=format_confidence_label,
    )

def render_species_log_tab(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    hikes: list[dict[str, Any]],
    context: dict[str, Any],
) -> None:
    render_species_log_view(
        repository,
        inat_client,
        hikes,
        context,
        quick_upload_hike_filter=QUICK_UPLOAD_HIKE_FILTER,
        build_species_log_record_href=build_species_log_record_href,
        paginate_items=paginate_items,
        render_back_to_top_link=render_back_to_top_link,
        render_species_log_inat_sync_panel=render_species_log_inat_sync_panel,
        render_species_log_toolbar=render_species_log_toolbar,
        render_species_record_dialog=render_species_record_dialog,
        reset_species_log_page=reset_species_log_page,
        resolve_page_size=resolve_page_size,
        set_species_log_record_query_state=set_species_log_record_query_state,
    )

def render_species_log_inat_sync_panel(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    posted_observations: list[dict[str, Any]],
) -> None:
    candidates = st.session_state.get("inat_sync_candidates") or {}
    panel_container = st.container(key="species_log_sync_panel")
    panel_cols = panel_container.columns([0.54, 0.18, 0.14, 0.14], gap="small")
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


def set_species_log_main_photo(
    repository: HikeJournalRepository,
    species_observations: list[dict[str, Any]],
    selected_observation: dict[str, Any],
) -> None:
    selected_id = str(selected_observation["id"])
    observation_ids_to_update = {
        str(observation["id"])
        for observation in species_observations
        if is_species_log_main_photo(observation) or str(observation["id"]) == selected_id
    }
    full_observations = repository.list_observations_by_ids(list(observation_ids_to_update))
    for observation in full_observations:
        observation_id = str(observation["id"])
        should_select = observation_id == selected_id
        if should_select == is_species_log_main_photo(observation):
            continue
        repository.update_observation_raw_payload(
            observation_id,
            update_species_log_main_photo_payload(
                observation.get("raw_response_json"),
                selected=should_select,
            ),
        )
    invalidate_data_cache()
    st.session_state.species_log_main_photo_notice = "Saved this as the Species Log main photo."


def render_species_log_main_photo_action(
    *,
    repository: HikeJournalRepository,
    species_observations: list[dict[str, Any]],
    observation: dict[str, Any],
    key: str,
    use_container_width: bool = True,
) -> None:
    is_selected = is_species_log_main_photo(observation)
    if st.button(
        "Main photo" if is_selected else "Use as main photo",
        key=key,
        use_container_width=use_container_width,
        disabled=is_selected,
        type="primary" if is_selected else "secondary",
    ):
        set_species_log_main_photo(repository, species_observations, observation)
        st.rerun()


@st.dialog("Species record", width="large", on_dismiss=dismiss_species_record_dialog)
def render_species_record_dialog(
    repository: HikeJournalRepository,
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
    lead_observation = focus_row["lead_entry"]["observation"]
    focus_index = page_keys.index(st.session_state.species_log_focus_key)

    if st.session_state.get("species_log_main_photo_notice"):
        st.success(str(st.session_state.species_log_main_photo_notice))
        st.session_state.species_log_main_photo_notice = None

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
        render_species_log_main_photo_action(
            repository=repository,
            species_observations=focus_row["species_observations"],
            observation=lead_observation,
            key=f"species_log_lead_main_{focus_row['key']}",
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
            render_species_log_main_photo_action(
                repository=repository,
                species_observations=focus_row["species_observations"],
                observation=lead_entry["observation"],
                key=f"species_log_encounter_main_{focus_row['key']}_{encounter_index}_lead",
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
                        render_species_log_main_photo_action(
                            repository=repository,
                            species_observations=focus_row["species_observations"],
                            observation=entry["observation"],
                            key=f"species_log_encounter_main_{focus_row['key']}_{encounter_index}_{idx}",
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

    if st.session_state.get("active_view") == "Species Log":
        focus_key = st.session_state.get("species_log_focus_key")
        focused_observation = next(
            (
                candidate
                for candidate in photo_observations
                if build_species_group_key(candidate) == focus_key and candidate.get("status") == "confirmed"
            ),
            None,
        )
        if focused_observation:
            focused_species_observations = [
                candidate
                for grouped_observations in observations_by_photo.values()
                for candidate in grouped_observations
                if build_species_group_key(candidate) == focus_key and candidate.get("status") == "confirmed"
            ]
            render_species_log_main_photo_action(
                repository=repository,
                species_observations=focused_species_observations,
                observation=focused_observation,
                key=f"viewer_species_log_main_{photo['id']}_{focused_observation['id']}",
                use_container_width=True,
            )

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


def render_selection_toolbar(
    repository: HikeJournalRepository,
    photos: list[dict[str, Any]],
    prefix: str,
    *,
    compact: bool = False,
) -> None:
    if not photos:
        return
    photo_ids = [photo["id"] for photo in photos]
    selected_count = len([photo for photo in photos if photo.get("processing_status") == REVIEW_QUEUE_STATUS])
    if not compact:
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
        return
    with st.container(key=f"{prefix}_review_queue"):
        cols = st.columns([0.42, 0.29, 0.29], gap="small")
        cols[0].markdown(
            f"<div class='journal-control-label'><span>Species review</span><strong>{selected_count} of {len(photo_ids)} queued</strong></div>",
            unsafe_allow_html=True,
        )
        if cols[1].button("Queue whole hike", key=f"{prefix}_select_all", use_container_width=True, type="primary"):
            repository.update_photo_processing_statuses(photo_ids, REVIEW_QUEUE_STATUS)
            reset_journal_review_widget_state(photo_ids)
            invalidate_data_cache()
            st.rerun()
        if cols[2].button("Clear hike", key=f"{prefix}_clear_selection", use_container_width=True, disabled=not selected_count):
            repository.update_photo_processing_statuses(photo_ids, "ready")
            reset_journal_review_widget_state(photo_ids)
            invalidate_data_cache()
            st.rerun()


def render_known_species_assignment_toolbar(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    page_photos: list[dict[str, Any]],
    all_photos: list[dict[str, Any]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    known_species: list[dict[str, Any]],
    *,
    key_prefix: str,
    compact: bool = False,
) -> None:
    if st.session_state.known_species_notice:
        st.success(str(st.session_state.known_species_notice))
        st.session_state.known_species_notice = None
    available_photos = [photo for photo in all_photos if photo["id"] not in primary_observation_by_photo]
    available_ids = {str(photo["id"]) for photo in available_photos}
    st.session_state.known_species_selected_ids = {
        str(photo_id)
        for photo_id in st.session_state.known_species_selected_ids
        if str(photo_id) in available_ids
    }
    selected_photos = [
        photo for photo in available_photos if str(photo["id"]) in st.session_state.known_species_selected_ids
    ]
    selected_count = len(selected_photos)
    if not compact:
        cols = st.columns([0.38, 0.24, 0.2, 0.18], gap="small")
        cols[0].caption(f"{selected_count} untagged photo{'s' if selected_count != 1 else ''} selected for bulk tagging")
        if cols[1].button(
            f"Bulk assign ({selected_count})",
            key=f"{key_prefix}_assign_known_species",
            use_container_width=True,
            type="primary",
            disabled=not selected_photos or not known_species,
            help="Confirm a species from your journal without using computer vision or entering Species Review.",
        ):
            open_known_species_dialog(repository, inat_client, selected_photos, known_species)
        if cols[2].button(
            "Select page",
            key=f"{key_prefix}_select_known_species_page",
            use_container_width=True,
            disabled=not available_photos,
        ):
            for photo in page_photos:
                if photo["id"] in primary_observation_by_photo:
                    continue
                st.session_state.known_species_selected_ids.add(str(photo["id"]))
                st.session_state[f"known_species_select_{photo['id']}"] = True
            st.rerun()
        if cols[3].button(
            "Clear",
            key=f"{key_prefix}_clear_known_species_selection",
            use_container_width=True,
            disabled=not selected_photos,
        ):
            clear_known_species_selection(selected_photos)
            st.rerun()
        return
    with st.container(key=f"{key_prefix}_known_species"):
        cols = st.columns([0.34, 0.2, 0.17, 0.29], gap="small")
        cols[0].markdown(
            f"<div class='journal-control-label'><span>Known species</span><strong>{selected_count} untagged photo{'s' if selected_count != 1 else ''} selected</strong></div>",
            unsafe_allow_html=True,
        )
        if cols[1].button(
            "Select page",
            key=f"{key_prefix}_select_known_species_page",
            use_container_width=True,
            disabled=not available_photos,
        ):
            for photo in page_photos:
                if photo["id"] in primary_observation_by_photo:
                    continue
                st.session_state.known_species_selected_ids.add(str(photo["id"]))
                st.session_state[f"known_species_select_{photo['id']}"] = True
            st.rerun()
        if cols[2].button(
            "Clear selection",
            key=f"{key_prefix}_clear_known_species_selection",
            use_container_width=True,
            disabled=not selected_photos,
        ):
            clear_known_species_selection(selected_photos)
            st.rerun()
        if cols[3].button(
            f"Assign known species ({selected_count})",
            key=f"{key_prefix}_assign_known_species",
            use_container_width=True,
            type="primary",
            disabled=not selected_photos or not known_species,
            help="Confirm a species from your journal without using computer vision or entering Species Review.",
        ):
            open_known_species_dialog(repository, inat_client, selected_photos, known_species)


def sync_known_species_checkbox(photo_id: str, checkbox_key: str) -> None:
    if st.session_state.get(checkbox_key):
        st.session_state.known_species_selected_ids.add(str(photo_id))
    else:
        st.session_state.known_species_selected_ids.discard(str(photo_id))


def clear_known_species_selection(photos: list[dict[str, Any]]) -> None:
    for photo in photos:
        photo_id = str(photo["id"])
        st.session_state.known_species_selected_ids.discard(photo_id)
        st.session_state[f"known_species_select_{photo_id}"] = False


def sync_journal_review_checkbox(
    repository: HikeJournalRepository,
    photo_id: str,
    checkbox_key: str,
) -> None:
    is_selected = bool(st.session_state.get(checkbox_key))
    new_status = REVIEW_QUEUE_STATUS if is_selected else "ready"
    repository.update_photo_processing_status(photo_id, new_status)
    invalidate_data_cache()


def sync_hike_cover_checkbox(
    repository: HikeJournalRepository,
    hike_id: str,
    photo_id: str,
    checkbox_key: str,
) -> None:
    is_selected = bool(st.session_state.get(checkbox_key))
    new_cover_photo_id = photo_id if is_selected else None
    try:
        repository.update_hike_cover_photo(hike_id, new_cover_photo_id)
    except Exception as exc:
        st.session_state[checkbox_key] = not is_selected
        st.session_state["journal_cover_update_error"] = (
            f"Cover photos need the new library migration before they can be saved: {exc}"
        )
        return
    if is_selected:
        for state_key in list(st.session_state.keys()):
            if state_key.startswith("cover_photo_select_") and state_key != checkbox_key:
                st.session_state[state_key] = False
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
    if (
        observation.get("source") == "known_species"
        and not get_taxon_enrichment(observation)
        and ensure_taxon_enrichment(repository, inat_client, observation)
    ):
        st.rerun()
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


def render_photo_species_actions(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    photo: dict[str, Any],
    photo_observations: list[dict[str, Any]],
    primary_observation: dict[str, Any] | None,
    known_species: list[dict[str, Any]],
    *,
    hike_id: str | None,
    key_prefix: str,
) -> None:
    popover_key_prefix = f"{key_prefix}_add_{photo['id']}"
    if primary_observation:
        render_add_species_popover(
            repository,
            inat_client,
            hike_id,
            photo,
            photo_observations,
            key_prefix=popover_key_prefix,
        )
        return

    with st.container(key=f"photo_species_actions_{photo['id']}"):
        action_cols = st.columns(2, gap="small")
        with action_cols[0]:
            if st.button(
                "Tag known species",
                key=f"{key_prefix}_tag_known_{photo['id']}",
                use_container_width=True,
                type="primary",
                disabled=not known_species,
            ):
                open_known_species_dialog(repository, inat_client, [photo], known_species)
        with action_cols[1]:
            render_add_species_popover(
                repository,
                inat_client,
                hike_id,
                photo,
                photo_observations,
                key_prefix=popover_key_prefix,
                label="Search all species",
                use_container_width=True,
            )


def render_add_species_popover(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    hike_id: str | None,
    photo: dict[str, Any],
    photo_observations: list[dict[str, Any]],
    *,
    key_prefix: str,
    label: str = "Add another species",
    use_container_width: bool = False,
) -> None:
    existing_taxon_ids = {int(observation["taxon_id"]) for observation in photo_observations if observation.get("taxon_id") is not None}
    with st.popover(label, use_container_width=use_container_width):
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
        "requested_at": datetime.now(UTC).isoformat(),
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
            "local_observation_ids",
            "group_lead_observation_id",
            "grouped",
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


def _normalize_inat_post_records(
    lead_observation: dict[str, Any],
    lead_photo: dict[str, Any],
    related_records: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    ordered_records = [
        {"observation": lead_observation, "photo": lead_photo},
        *(related_records or []),
    ]
    normalized: list[dict[str, Any]] = []
    seen_photo_ids: set[str] = set()
    for record in ordered_records:
        photo = record.get("photo") or {}
        observation = record.get("observation") or {}
        photo_id = str(photo.get("id") or "").strip()
        observation_id = str(observation.get("id") or "").strip()
        if not observation_id:
            continue
        if not photo_id or photo_id in seen_photo_ids:
            continue
        seen_photo_ids.add(photo_id)
        normalized.append({"observation": observation, "photo": photo})
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
            selected_extra_records: list[dict[str, Any]] = []
            for index, candidate in enumerate(extra_photo_candidates, start=1):
                candidate_photo = candidate["photo"]
                candidate_label = f"Photo {index + 1}: {candidate['label']}"
                checkbox_key = f"{key_prefix}_inat_related_{candidate_photo['id']}"
                if st.checkbox(candidate_label, key=checkbox_key):
                    selected_extra_records.append(candidate)
            selected_total = 1 + len(selected_extra_records)
            submit_label = f"Post grouped observation ({selected_total} photos)"
            if selected_total > GROUPED_PUBLISH_MAX_PHOTOS:
                st.warning(f"Choose no more than {GROUPED_PUBLISH_MAX_PHOTOS} photos for one iNaturalist observation.")
            if st.form_submit_button(
                submit_label,
                use_container_width=True,
                type="secondary",
                disabled=selected_total > GROUPED_PUBLISH_MAX_PHOTOS,
            ):
                try:
                    with st.spinner("Posting grouped observation to iNaturalist..."):
                        posting_result = post_observation_to_inaturalist(
                            repository,
                            inat_client,
                            observation,
                            photo,
                            place_guess=place_guess,
                            related_records=selected_extra_records,
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
    related_records: list[dict[str, Any]] | None = None,
    raise_on_photo_failure: bool = True,
) -> dict[str, Any]:
    inat_client.validate_credentials()
    observed_on = _parse_datetime(photo.get("taken_at"))
    post_records = _normalize_inat_post_records(observation, photo, related_records)
    if not post_records:
        raise RuntimeError("Choose at least one photo before posting to iNaturalist.")
    if len(post_records) > GROUPED_PUBLISH_MAX_PHOTOS:
        raise RuntimeError(f"Choose no more than {GROUPED_PUBLISH_MAX_PHOTOS} photos for one iNaturalist observation.")
    full_observations = fetch_observations_by_ids(
        tuple(str(record["observation"]["id"]) for record in post_records)
    )
    full_observation_by_id = {str(record["id"]): record for record in full_observations}
    missing_observation_ids = [
        str(record["observation"]["id"])
        for record in post_records
        if str(record["observation"]["id"]) not in full_observation_by_id
    ]
    if missing_observation_ids:
        raise RuntimeError("HikeJournal could not load every selected observation needed for grouped posting.")
    upload_payloads: list[dict[str, Any]] = []
    for record in post_records:
        upload_photo = record["photo"]
        public_url = str(upload_photo.get("public_url") or "").strip()
        if not public_url:
            raise RuntimeError("One of the selected photos is missing a public image URL, so HikeJournal could not send it to iNaturalist.")
        try:
            image_bytes = _download_public_image(public_url)
        except Exception as exc:
            raise RuntimeError("HikeJournal could not download one of the selected photos for iNaturalist.") from exc
        upload_payloads.append(
            {
                "observation": full_observation_by_id[str(record["observation"]["id"])],
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
    local_observation_ids = [str(item["observation"]["id"]) for item in upload_payloads]
    lead_observation_id = str(observation["id"])
    posting_payload: dict[str, Any] = {
        "observation_id": int(created_id),
        "observation_url": created_observation.get("uri") or created_observation.get("html_url") or build_inat_observation_url(created_id),
        "posted_at": datetime.now().astimezone().isoformat(),
        "posted_by_subject": st.session_state.current_user_context.get("subject"),
        "posted_by_email": st.session_state.current_user_context.get("email"),
        "photo_attached": True,
        "photo_count": len(upload_payloads),
        "attached_photo_count": 0,
        "local_photo_ids": [str(item["photo"]["id"]) for item in upload_payloads],
        "local_observation_ids": local_observation_ids,
        "group_lead_observation_id": lead_observation_id,
        "grouped": len(upload_payloads) > 1,
        "attached_local_photo_ids": [],
        "failed_local_photo_ids": [],
    }
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
    if upload_errors:
        posting_payload["upload_errors"] = upload_errors
    for upload_payload in upload_payloads:
        local_observation = upload_payload["observation"]
        local_posting_payload = {
            **posting_payload,
            "group_role": "lead" if str(local_observation["id"]) == lead_observation_id else "member",
        }
        raw_payload = dict(local_observation.get("raw_response_json") or {})
        raw_payload["inat_posting"] = local_posting_payload
        repository.update_observation_raw_payload(local_observation["id"], raw_payload)
        repository.update_observation_inat_posting(
            local_observation["id"],
            inat_observation_id=int(created_id),
            inat_observation_url=posting_payload["observation_url"],
            inat_posted_at=posting_payload["posted_at"],
            inat_photo_attached=bool(posting_payload["photo_attached"]),
        )
    if upload_errors and raise_on_photo_failure:
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


def ensure_taxon_enrichment(repository: HikeJournalRepository, inat_client: InatClient, observation: dict[str, Any]) -> bool:
    raw_payload = dict(observation.get("raw_response_json") or {})
    enrichment = raw_payload.get("taxon_enrichment")
    if raw_payload.get("manual_override"):
        return False
    taxon_id = observation.get("taxon_id")
    if enrichment or not taxon_id:
        return bool(enrichment)
    try:
        raw_payload["taxon_enrichment"] = inat_client.fetch_taxon_enrichment(int(taxon_id))
        repository.update_observation_raw_payload(observation["id"], raw_payload)
        invalidate_data_cache()
        return True
    except (InatConfigurationError, InatRequestError, ValueError):
        return False


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
            "edited_at": datetime.now(UTC).isoformat(),
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

    preferences_are_inline = all(
        "species_log_main_photo" in observation
        for observation in confirmed_observations
    )
    if preferences_are_inline:
        preference_by_id = {
            str(observation["id"]): observation.get("species_log_main_photo") is True
            for observation in confirmed_observations
            if observation.get("id")
        }
    else:
        observation_ids = tuple(str(observation["id"]) for observation in confirmed_observations if observation.get("id"))
        preference_rows = fetch_species_log_photo_preferences(observation_ids) if observation_ids else []
        preference_by_id = {
            str(row["id"]): row.get("species_log_main_photo") is True
            for row in preference_rows
        }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lightweight_observation in confirmed_observations:
        observation = dict(lightweight_observation)
        if preference_by_id.get(str(observation.get("id"))):
            observation["raw_response_json"] = {"species_log_main_photo": True}
        photo = photo_by_id.get(observation.get("photo_id"))
        if not photo:
            continue
        if hike_filter == QUICK_UPLOAD_HIKE_FILTER and observation.get("hike_id"):
            continue
        if hike_filter not in {"All hikes", QUICK_UPLOAD_HIKE_FILTER} and observation.get("hike_id") != hike_title_to_id.get(hike_filter):
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
        preferred_entry = next(
            (entry for entry in entries_sorted if is_species_log_main_photo(entry["observation"])),
            entries_sorted[0],
        )
        representative_observation = preferred_entry["observation"]
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
            preferred_encounter_entry = next(
                (entry for entry in encounter_entries if is_species_log_main_photo(entry["observation"])),
                None,
            )
            if preferred_encounter_entry:
                encounter_entries.remove(preferred_encounter_entry)
                encounter_entries.insert(0, preferred_encounter_entry)
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
                "lead_photo": preferred_entry["photo"],
                "lead_entry": preferred_entry,
                "species_observations": [entry["observation"] for entry in entries_sorted],
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
    *,
    compact: bool = False,
) -> None:
    cols = st.columns([0.17, 0.14, 0.31, 0.17, 0.21] if compact else [0.16, 0.14, 0.28, 0.18, 0.24], gap="small")
    page_size_options = [6, 9, 12, 18, 0]
    page_size = cols[0].selectbox(
        "Photos per page" if compact else "Per page",
        page_size_options,
        index=page_size_options.index(st.session_state.journal_page_size),
        key="journal_page_size_select",
        format_func=lambda value: "All" if value == 0 else str(value),
    )
    if page_size != st.session_state.journal_page_size:
        st.session_state.journal_page_size = page_size
        st.session_state.journal_page = 1
        st.rerun()
    requested_page = cols[1].number_input("Page", min_value=1, max_value=total_pages, value=st.session_state.journal_page, step=1, key="journal_page_number")
    if requested_page != st.session_state.journal_page:
        st.session_state.journal_page = int(requested_page)
        st.rerun()
    if compact:
        cols[2].markdown(f"<div class='journal-control-label journal-control-label--browse'><span>Browse photos</span><strong>Page {st.session_state.journal_page} of {total_pages} · {len(page_photos)} shown</strong></div>", unsafe_allow_html=True)
    else:
        cols[2].markdown(f"<div class='utility-rail-status'>{len(page_photos)} photos on this page • {len(st.session_state.delete_photo_ids)} marked for deletion</div>", unsafe_allow_html=True)
    st.session_state.delete_mode = cols[3].toggle("Delete mode", value=st.session_state.delete_mode, key="journal_delete_mode")
    with cols[4].popover("Manage photos" if compact else "Manage", use_container_width=compact):
        _render_photo_management_popover(repository, storage, page_photos, all_deletable_photos, total_pages)


def _render_photo_management_popover(
    repository: HikeJournalRepository,
    storage: StorageService,
    page_photos: list[dict[str, Any]],
    all_deletable_photos: list[dict[str, Any]],
    total_pages: int,
) -> None:
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
    if st.button(f"Delete selected ({len(st.session_state.delete_photo_ids)})", use_container_width=True, disabled=not st.session_state.delete_photo_ids):
        photos_to_delete = [photo for photo in all_deletable_photos if photo["id"] in st.session_state.delete_photo_ids]
        total_to_delete = len(photos_to_delete)
        delete_progress = st.progress(0, text=f"Preparing to delete {total_to_delete} photos...")
        with st.status(f"Deleting {total_to_delete} photos...", expanded=True) as delete_status:
            for index, photo in enumerate(photos_to_delete, start=1):
                delete_status.write(f"Removing photo {index} of {total_to_delete}")
                storage.delete_file(photo.get("storage_path") or "")
                repository.delete_photo(photo["id"])
                delete_progress.progress(index / total_to_delete, text=f"Deleted {index} of {total_to_delete} photos")
            delete_status.update(label=f"Deleted {total_to_delete} photos.", state="complete", expanded=False)
        invalidate_data_cache()
        st.session_state.delete_photo_ids = set()
        for key in list(st.session_state.keys()):
            if key.startswith("delete_photo_"):
                del st.session_state[key]
        st.rerun()


@st.dialog("Review ID requests", width="medium")
def render_smart_id_plan_dialog(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    photos_to_process: list[dict[str, Any]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
) -> None:
    proposed_groups = build_review_photo_encounter_plan(
        photos_to_process,
        max_distance_meters=SMART_ID_MAX_DISTANCE_METERS,
        max_minutes=SMART_ID_MAX_MINUTES,
        max_photos=GROUPED_ID_MAX_PHOTOS,
    )
    display_groups = sorted(proposed_groups, key=lambda group: int(group["photo_count"]) == 1)
    st.markdown(
        f"""
        <div class="encounter-plan-marker encounter-plan-intro">
            <strong>{len(photos_to_process)} selected photos</strong>
            <span>Nearby photos are proposed as one decision. Check anything that should be submitted separately.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    separate_photo_ids: set[str] = set()
    for index, group in enumerate(display_groups, start=1):
        rows = group["rows"]
        photo_count = int(group["photo_count"])
        if index > 1:
            st.markdown('<div class="encounter-plan-divider"></div>', unsafe_allow_html=True)
        if photo_count > 1:
            st.markdown(
                f"""
                <div class="encounter-plan-heading">
                    <strong>Proposed Group · {photo_count} photos</strong>
                    <span>{float(group['time_span_minutes']):.1f} min · {float(group['max_distance_meters']):.0f} m spread</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="encounter-plan-heading"><strong>Individual</strong></div>',
                unsafe_allow_html=True,
            )

        for row_start in range(0, len(rows), 4):
            photo_rows = rows[row_start : row_start + 4]
            photo_columns = st.columns(4, gap="small")
            for photo_column, row in zip(photo_columns[: len(photo_rows)], photo_rows, strict=True):
                photo = row["photo"]
                with photo_column:
                    thumbnail_url = get_photo_thumbnail_url(photo)
                    st.markdown(
                        f'<div class="encounter-plan-thumbnail"><img src="{escape(thumbnail_url, quote=True)}" alt=""></div>',
                        unsafe_allow_html=True,
                    )
                    if photo_count > 1 and st.checkbox(
                        "Split",
                        key=f"smart_id_separate_{photo['id']}",
                        help="Submit this photo as an individual ID request.",
                    ):
                        separate_photo_ids.add(str(photo["id"]))

    planned_groups = split_review_photo_encounter_plan(
        proposed_groups,
        separate_photo_ids,
        max_photos=GROUPED_ID_MAX_PHOTOS,
    )
    grouped_count = len([group for group in planned_groups if int(group["photo_count"]) > 1])
    individual_count = len(planned_groups) - grouped_count
    request_count = len(planned_groups)
    st.markdown('<div class="encounter-plan-divider encounter-plan-footer-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        f"<div class='encounter-plan-summary'><strong>Plan: {request_count} ID request{'s' if request_count != 1 else ''}</strong> · "
        f"{grouped_count} grouped · {individual_count} individual. "
        "Two-photo groups use the highest-confidence top suggestion for both photos; larger groups that disagree after scoring split into individual suggestions.</div>",
        unsafe_allow_html=True,
    )
    if st.button(
        f"Submit {request_count} ID Request{'s' if request_count != 1 else ''}",
        key="smart_id_run_reviewed_plan",
        use_container_width=True,
        type="primary",
        disabled=not planned_groups or st.session_state.get("smart_id_plan_submission_started", False),
        on_click=mark_smart_id_plan_submission_started,
    ):
        processed_count = process_smart_species_photo_groups(
            repository,
            inat_client,
            photos_to_process,
            primary_observation_by_photo,
            planned_groups=planned_groups,
        )
        if processed_count:
            st.session_state.species_review_stage = "Needs decisions"
            st.session_state.species_page = 1
            clear_species_selection(photos_to_process)
        st.rerun()


def open_smart_id_plan(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    photos_to_process: list[dict[str, Any]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
) -> None:
    st.session_state.smart_id_plan_submission_started = False
    for photo in photos_to_process:
        st.session_state.pop(f"smart_id_separate_{photo['id']}", None)
    render_smart_id_plan_dialog(
        repository,
        inat_client,
        photos_to_process,
        primary_observation_by_photo,
    )


def mark_smart_id_plan_submission_started() -> None:
    st.session_state.smart_id_plan_submission_started = True


def format_known_species_option(species: dict[str, Any]) -> str:
    common_name = str(species.get("common_name") or species.get("scientific_name") or "Unknown species")
    scientific_name = str(species.get("scientific_name") or "")
    name = f"{common_name} — {scientific_name}" if scientific_name and scientific_name != common_name else common_name
    seen_count = int(species.get("seen_count") or 0)
    return f"{name} · {seen_count} prior record{'s' if seen_count != 1 else ''}"


def assign_known_species_to_photos(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    photos: list[dict[str, Any]],
    species: dict[str, Any],
) -> int:
    source_observation_id = str(species.get("source_observation_id") or "")
    source_observations = repository.list_observations_by_ids([source_observation_id]) if source_observation_id else []
    source_raw_payload = dict(source_observations[0].get("raw_response_json") or {}) if source_observations else {}
    taxon_enrichment = source_raw_payload.get("taxon_enrichment")
    if not isinstance(taxon_enrichment, dict) and species.get("taxon_id"):
        try:
            taxon_enrichment = inat_client.fetch_taxon_enrichment(int(species["taxon_id"]))
        except (InatConfigurationError, InatRequestError, ValueError):
            taxon_enrichment = None

    assigned_photo_ids: list[str] = []
    try:
        for photo in photos:
            repository.create_manual_observation(
                hike_id=photo.get("hike_id"),
                photo_id=photo["id"],
                taxon_id=species.get("taxon_id"),
                common_name=species.get("common_name"),
                scientific_name=species.get("scientific_name"),
                source="known_species",
                raw_payload={
                    "known_species_assignment": {
                        "source_observation_id": source_observation_id or None,
                        "catalog_seen_count": int(species.get("seen_count") or 0),
                        "assigned_at": datetime.now(UTC).isoformat(),
                    },
                    **({"taxon_enrichment": taxon_enrichment} if isinstance(taxon_enrichment, dict) else {}),
                },
                is_primary=True,
                status="confirmed",
                owner_subject=photo.get("owner_subject"),
                owner_email=photo.get("owner_email"),
            )
            assigned_photo_ids.append(str(photo["id"]))
    finally:
        if assigned_photo_ids:
            repository.update_photo_processing_statuses(assigned_photo_ids, "ready")
    return len(assigned_photo_ids)


@st.dialog("Assign known species", width="medium")
def render_known_species_dialog(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    photos: list[dict[str, Any]],
    known_species: list[dict[str, Any]],
) -> None:
    st.markdown(f"**{len(photos)} selected photo{'s' if len(photos) != 1 else ''}**")
    st.caption("Choose a species already established in your journal. This skips computer vision, confirms the ID, and sends the photos to Publishing.")
    selected_species = st.selectbox(
        "Known species",
        known_species,
        index=None,
        key="known_species_assignment_option",
        format_func=format_known_species_option,
        placeholder="Start typing a common or scientific name...",
    )
    if st.button(
        f"Assign to {len(photos)} photo{'s' if len(photos) != 1 else ''}",
        key="known_species_assignment_submit",
        use_container_width=True,
        type="primary",
        disabled=selected_species is None,
    ):
        assigned_count = assign_known_species_to_photos(repository, inat_client, photos, selected_species)
        clear_species_selection(photos)
        clear_known_species_selection(photos)
        invalidate_data_cache()
        st.session_state.known_species_notice = (
            f"Assigned {format_known_species_option(selected_species).split(' · ')[0]} to "
            f"{assigned_count} photo{'s' if assigned_count != 1 else ''}. Ready to publish."
        )
        st.rerun()


def open_known_species_dialog(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    photos: list[dict[str, Any]],
    known_species: list[dict[str, Any]],
) -> None:
    st.session_state.pop("known_species_assignment_option", None)
    render_known_species_dialog(repository, inat_client, photos, known_species)


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
    selected_ids = sync_visible_widget_selection(st.session_state, selected_photos)
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
            set_photos_selected(st.session_state, page_photos, True)
            st.rerun()
        if queue_cols[1].button("Clear page", key="species_clear_page", use_container_width=True):
            set_photos_selected(st.session_state, page_photos, False)
            st.rerun()
        queue_scope_cols = st.columns(2, gap="small")
        if queue_scope_cols[0].button("Select review", key="species_select_queue", use_container_width=True):
            set_photos_selected(st.session_state, selected_photos, True, update_widgets=False)
            st.rerun()
        if queue_scope_cols[1].button("Clear selection", key="species_clear_queue", use_container_width=True):
            clear_species_selection(selected_photos)
            st.rerun()
        if st.button("Remove all from review", key="species_remove_all_queue", use_container_width=True, type="secondary", disabled=not selected_photos):
            remove_photos_from_review(repository, selected_photos)
            clear_species_selection(selected_photos)
            st.rerun()
    if not selected_count:
        st.caption("Select one or more photos to review, confirm, reject, or remove from this list.")
        return

    selected_photos_only = [photo for photo in selected_photos if photo["id"] in selected_ids]
    selected_unprocessed = [photo for photo in selected_photos_only if photo["id"] not in primary_observation_by_photo]
    smart_id_groups = build_review_photo_encounter_plan(
        selected_unprocessed,
        max_distance_meters=SMART_ID_MAX_DISTANCE_METERS,
        max_minutes=SMART_ID_MAX_MINUTES,
        max_photos=GROUPED_ID_MAX_PHOTOS,
    )
    smart_group_count = len([group for group in smart_id_groups if int(group["photo_count"]) > 1])
    smart_single_count = len([group for group in smart_id_groups if int(group["photo_count"]) == 1])
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

    action_cols = st.columns([0.32, 0.18, 0.5], gap="small")
    if selected_unprocessed:
        primary_label = f"Submit IDs ({len(selected_unprocessed)})"
        primary_disabled = not is_inat_client_ready(inat_client)
    elif selected_pending:
        primary_label = f"Confirm selected ({len(selected_pending)})"
        primary_disabled = False
    elif selected_scored:
        primary_label = f"Reject selected ({len(selected_scored)})"
        primary_disabled = False
    else:
        primary_label = f"Remove from review ({len(selected_photos_only)})"
        primary_disabled = not selected_photos_only

    if action_cols[0].button(
        primary_label,
        key="species_primary_batch_action",
        use_container_width=True,
        disabled=primary_disabled,
        type="primary",
    ):
        if selected_unprocessed:
            open_smart_id_plan(repository, inat_client, selected_unprocessed, primary_observation_by_photo)
            return
        elif selected_pending:
            confirm_observations(repository, inat_client, [item for item in selected_pending if item])
            clear_species_selection(selected_photos_only)
        elif selected_scored:
            reject_observations(repository, selected_scored, selected_photos_only)
            clear_species_selection(selected_photos_only)
        else:
            remove_photos_from_review(repository, selected_photos_only)
            clear_species_selection(selected_photos_only)
        st.rerun()

    with action_cols[1].popover("More"):
        st.caption(f"{selected_count} selected")
        if st.button(
            f"Submit IDs ({len(selected_unprocessed)})",
            key="species_process_smart_groups",
            use_container_width=True,
            disabled=not is_inat_client_ready(inat_client) or not selected_unprocessed,
            type="primary",
        ):
            open_smart_id_plan(repository, inat_client, selected_unprocessed, primary_observation_by_photo)
        if st.button(
            f"Individual IDs ({len(selected_unprocessed)})",
            key="species_process_selected",
            use_container_width=True,
            disabled=not is_inat_client_ready(inat_client) or not selected_unprocessed,
        ):
            processed_count = process_species_photos(repository, inat_client, selected_photos_only, primary_observation_by_photo)
            if processed_count:
                st.session_state.species_review_stage = "Needs decisions"
                st.session_state.species_page = 1
            st.rerun()
        if st.button(
            f"Selected as one ID ({len(selected_unprocessed)})",
            key="species_process_grouped",
            use_container_width=True,
            disabled=(
                not is_inat_client_ready(inat_client)
                or len(selected_unprocessed) < 2
                or len(selected_unprocessed) > GROUPED_ID_MAX_PHOTOS
                or not grouped_scope_valid
            ),
        ):
            processed_count = process_species_photo_group(repository, inat_client, selected_photos_only, primary_observation_by_photo)
            if processed_count:
                st.session_state.species_review_stage = "Needs decisions"
                st.session_state.species_page = 1
            st.rerun()
        st.divider()
        if st.button(
            f"Confirm ({len(selected_pending)})",
            key="species_confirm_selected",
            use_container_width=True,
            disabled=not selected_pending,
        ):
            confirm_observations(repository, inat_client, [item for item in selected_pending if item])
            clear_species_selection(selected_photos_only)
            st.rerun()
        if st.button(
            f"Reject ({len(selected_scored)})",
            key="species_reject_selected",
            use_container_width=True,
            disabled=not selected_scored,
            type="secondary",
        ):
            reject_observations(repository, selected_scored, selected_photos_only)
            clear_species_selection(selected_photos_only)
            st.rerun()
        if st.button(
            f"Remove from review ({len(selected_photos_only)})",
            key="species_remove_selected",
            use_container_width=True,
            disabled=not selected_photos_only,
            type="secondary",
        ):
            remove_photos_from_review(repository, selected_photos_only)
            clear_species_selection(selected_photos_only)
            st.rerun()
        st.button(
            "Clear selection",
            key="species_clear_selected_batch",
            use_container_width=True,
            type="tertiary",
            disabled=not selected_count,
            on_click=clear_species_selection,
            args=(selected_photos_only,),
        )

    if selected_unprocessed and smart_id_groups:
        smart_pieces = [f"{smart_single_count} individual" if smart_single_count else "", f"{smart_group_count} grouped" if smart_group_count else ""]
        action_cols[2].caption(
            f"Submit IDs will prepare {len(smart_id_groups)} review decision{'s' if len(smart_id_groups) != 1 else ''}: "
            f"{', '.join(piece for piece in smart_pieces if piece)}. Auto-groups only within "
            f"{SMART_ID_MAX_MINUTES:g} min and {SMART_ID_MAX_DISTANCE_METERS:g} m."
        )
    if len(selected_unprocessed) == 1:
        st.caption("Single ID needs at least 2 unprocessed photos.")
    elif len(selected_unprocessed) > GROUPED_ID_MAX_PHOTOS:
        st.caption(f"Single ID works on up to {GROUPED_ID_MAX_PHOTOS} photos at a time.")
    elif not grouped_scope_valid:
        st.caption("Single ID works on one outing at a time, or on a standalone batch without a hike.")


def _publishing_actions() -> PublishingActions:
    return PublishingActions(
        get_inat_posting=get_inat_posting,
        inat_connection_action_label=inat_connection_action_label,
        invalidate_data_cache=invalidate_data_cache,
        is_inat_client_ready=is_inat_client_ready,
        open_inat_token_dialog=open_inat_token_dialog,
        open_publish_plan=open_publish_plan,
        paginate_items=paginate_items,
        render_inat_posting_controls=render_inat_posting_controls,
        render_publish_lane_management_controls=render_publish_lane_management_controls,
        resolve_page_size=resolve_page_size,
    )


def render_publishing_section(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    hikes: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    photos: list[dict[str, Any]],
) -> None:
    render_publishing_view(
        repository,
        inat_client,
        hikes,
        confirmed_observations,
        photos,
        quick_upload_hike_filter=QUICK_UPLOAD_HIKE_FILTER,
        actions=_publishing_actions(),
    )

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


def get_publish_state(observation: dict[str, Any]) -> str:
    return get_publish_state_value(observation, get_inat_posting)


def count_publish_states(rows: list[dict[str, Any]]) -> dict[str, int]:
    return count_publish_states_state(rows)


def build_publish_rows(
    hikes: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    photos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return build_publish_rows_state(
        hikes,
        confirmed_observations,
        photos,
        posting_resolver=get_inat_posting,
    )


def clear_publish_selection(rows: list[dict[str, Any]]) -> None:
    set_publish_rows_selected(st.session_state, rows, False)


def fetch_full_observation_for_post(observation_id: str) -> dict[str, Any] | None:
    observations = fetch_observations_by_ids((str(observation_id),))
    return observations[0] if observations else None


@st.dialog("Review iNaturalist posts", width="medium")
def render_publish_plan_dialog(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    rows: list[dict[str, Any]],
) -> None:
    groups = build_publish_encounter_plan(rows, max_photos=GROUPED_PUBLISH_MAX_PHOTOS)
    display_groups = sorted(groups, key=lambda group: int(group["photo_count"]) == 1)
    photo_count = sum(int(group["photo_count"]) for group in groups)
    st.markdown(
        f"""
        <div class="encounter-plan-marker encounter-plan-intro">
            <strong>{photo_count} selected photos</strong>
            <span>Same-species photos from one outing are grouped when they fall within 15 minutes and 50 meters.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    separate_photo_ids: set[str] = set()
    for index, group in enumerate(display_groups, start=1):
        lead_row = group["lead_row"]
        observation = lead_row["observation"]
        hike = lead_row["hike"]
        species_name = observation.get("common_name") or observation.get("scientific_name") or "Unknown species"
        group_photo_count = int(group["photo_count"])
        if index > 1:
            st.markdown('<div class="encounter-plan-divider"></div>', unsafe_allow_html=True)
        if group_photo_count > 1:
            st.markdown(
                f"""
                <div class="encounter-plan-heading">
                    <strong>Proposed Group · {group_photo_count} photos</strong>
                    <span>{escape(str(species_name))} · {float(group['time_span_minutes']):.0f} min · {float(group['max_distance_meters']):.0f} m spread</span>
                </div>
                <div class="encounter-plan-context">{escape(str(hike.get('title') or 'Standalone sighting'))}</div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="encounter-plan-heading">
                    <strong>Individual</strong>
                    <span>{escape(str(species_name))}</span>
                </div>
                <div class="encounter-plan-context">{escape(str(hike.get('title') or 'Standalone sighting'))}</div>
                """,
                unsafe_allow_html=True,
            )

        for row_start in range(0, len(group["rows"]), 4):
            photo_rows = group["rows"][row_start : row_start + 4]
            photo_columns = st.columns(4, gap="small")
            for photo_column, row in zip(photo_columns[: len(photo_rows)], photo_rows, strict=True):
                photo = row["photo"]
                with photo_column:
                    thumbnail_url = get_photo_thumbnail_url(photo)
                    st.markdown(
                        f'<div class="encounter-plan-thumbnail"><img src="{escape(thumbnail_url, quote=True)}" alt="{escape(str(species_name), quote=True)}"></div>',
                        unsafe_allow_html=True,
                    )
                    if group_photo_count > 1 and st.checkbox(
                        "Split",
                        key=f"publish_plan_split_{photo['id']}",
                        help="Post this photo as an individual iNaturalist observation.",
                    ):
                        separate_photo_ids.add(str(photo["id"]))
    planned_groups = split_encounter_plan(
        groups,
        separate_photo_ids,
        max_photos=GROUPED_PUBLISH_MAX_PHOTOS,
    )
    observation_count = len(planned_groups)
    grouped_count = len([group for group in planned_groups if int(group["photo_count"]) > 1])
    individual_count = observation_count - grouped_count
    oversized_groups = [group for group in planned_groups if group["oversized"]]
    st.markdown('<div class="encounter-plan-divider encounter-plan-footer-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        f"<div class='encounter-plan-summary'><strong>Plan: {observation_count} iNaturalist observation{'s' if observation_count != 1 else ''}</strong> · "
        f"{grouped_count} grouped · {individual_count} individual.</div>",
        unsafe_allow_html=True,
    )
    if oversized_groups:
        st.warning("Split enough photos from every oversized group to stay within the eight-photo limit.")
    if st.button(
        f"Post {observation_count} observations ({photo_count} photos)",
        key="publish_confirm_encounter_plan",
        use_container_width=True,
        type="primary",
        disabled=not planned_groups or bool(oversized_groups),
    ):
        processed_ids = post_publish_encounter_plan(repository, inat_client, planned_groups)
        processed_rows = [
            row
            for group in planned_groups
            for row in group["rows"]
            if str(row["observation"]["id"]) in processed_ids
        ]
        clear_publish_selection(processed_rows)
        st.rerun()


def open_publish_plan(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    rows: list[dict[str, Any]],
) -> None:
    for row in rows:
        st.session_state.pop(f"publish_plan_split_{row['photo']['id']}", None)
    render_publish_plan_dialog(repository, inat_client, rows)


def post_publish_encounter_plan(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    groups: list[dict[str, Any]],
) -> set[str]:
    if not groups:
        return set()
    try:
        inat_client.validate_credentials()
    except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
        st.session_state.inat_auth_notice = None
        st.session_state.inat_auth_error = str(exc)
        st.error(str(exc))
        return set()
    progress_text = st.empty()
    progress_bar = st.progress(0, text="Preparing observations for iNaturalist...")
    total = len(groups)
    processed_ids: set[str] = set()
    failed_groups = 0
    partial_groups = 0
    with st.spinner("Posting observations to iNaturalist..."):
        for index, group in enumerate(groups, start=1):
            row = group["lead_row"]
            progress_text.caption(f"Posting observation {index} of {total}")
            full_observation = fetch_full_observation_for_post(row["observation"]["id"])
            if not full_observation:
                st.error("HikeJournal could not load an observation needed for posting.")
                failed_groups += 1
                progress_bar.progress(index / total, text=f"Processed {index} of {total} observations")
                continue
            try:
                posting_result = post_observation_to_inaturalist(
                    repository,
                    inat_client,
                    full_observation,
                    row["photo"],
                    place_guess=row["hike"].get("location_name"),
                    related_records=group["rows"][1:],
                    raise_on_photo_failure=False,
                )
            except (InatConfigurationError, InatAuthError, InatRequestError, RuntimeError) as exc:
                failed_groups += 1
                message = f"{row['observation']['common_name'] or row['observation']['scientific_name'] or row['observation']['id']}: {exc}"
                st.session_state.inat_post_feedback[str(row["observation"]["id"])] = {
                    "level": "error",
                    "message": message,
                }
            except Exception as exc:  # pragma: no cover - depends on remote database state
                failed_groups += 1
                st.session_state.inat_post_feedback[str(row["observation"]["id"])] = {
                    "level": "error",
                    "message": f"HikeJournal could not finish this grouped post: {exc}",
                }
            else:
                processed_ids.update(str(group_row["observation"]["id"]) for group_row in group["rows"])
                upload_errors = posting_result.get("upload_errors") or []
                if upload_errors:
                    partial_groups += 1
                st.session_state.inat_post_feedback[str(row["observation"]["id"])] = {
                    "level": "warning" if upload_errors else "success",
                    "message": (
                        f"Posted one iNaturalist observation, but {len(upload_errors)} photo upload{'s' if len(upload_errors) != 1 else ''} need attention."
                        if upload_errors
                        else _format_inat_multi_photo_message(posting_result)
                    ),
                }
            progress_bar.progress(index / total, text=f"Processed {index} of {total} observations")
    invalidate_data_cache()
    posted_groups = total - failed_groups
    if failed_groups or partial_groups:
        st.session_state.publish_batch_notice = {
            "level": "warning",
            "message": (
                f"Posted {posted_groups} of {total} planned observations. "
                f"{partial_groups} posted observation{'s' if partial_groups != 1 else ''} still need photo attention; "
                f"{failed_groups} could not be created."
            ),
        }
    else:
        st.session_state.publish_batch_notice = {
            "level": "success",
            "message": f"Posted {total} iNaturalist observation{'s' if total != 1 else ''} from {len(processed_ids)} selected photos.",
        }
    return processed_ids


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
    *,
    require_consensus: bool = False,
) -> tuple[SpeciesCandidate | None, list[dict[str, Any]], dict[str, SpeciesCandidate], list[str]]:
    aggregate: dict[str, dict[str, Any]] = {}
    processed_photos: list[dict[str, Any]] = []
    individual_candidates: dict[str, SpeciesCandidate] = {}
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
        individual_candidates[str(photo["id"])] = candidates[0]
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

    if not processed_photos or (len(processed_photos) < 2 and not require_consensus):
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
    top_match = (
        select_shared_candidate(aggregate_candidates, photo_count=len(processed_photos))
        if require_consensus
        else aggregate_candidates[0]
    )
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
    grouped_candidate = None
    if top_match is not None:
        selected_confidence = (
            top_match.get("best_confidence")
            if require_consensus and len(processed_photos) == 2
            else top_match.get("average_confidence")
        )
        grouped_candidate = SpeciesCandidate(
            common_name=str(top_match.get("common_name") or top_match.get("scientific_name") or "Unknown species"),
            scientific_name=str(top_match.get("scientific_name") or top_match.get("common_name") or "Unknown species"),
            confidence=float(selected_confidence or 0),
            taxon_id=top_match.get("taxon_id"),
            raw_payload=raw_payload,
        )
    return grouped_candidate, processed_photos, individual_candidates, warnings


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
            grouped_candidate, processed_photos, _individual_candidates, warnings = _build_grouped_species_candidate(
                inat_client,
                photos_to_process,
            )
        except (InatConfigurationError, InatAuthError) as exc:
            st.session_state.inat_auth_notice = None
            st.session_state.inat_auth_error = str(exc)
            st.error(str(exc))
            return 0
        except (InatRequestError, RuntimeError) as exc:
            st.error(str(exc))
            return 0

        if grouped_candidate is None:
            st.error("The selected photos did not produce a shared suggestion.")
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


def process_smart_species_photo_groups(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    photos_to_consider: list[dict[str, Any]],
    primary_observation_by_photo: dict[str, dict[str, Any]],
    *,
    planned_groups: list[dict[str, Any]] | None = None,
) -> int:
    photos_to_process = [photo for photo in photos_to_consider if photo["id"] not in primary_observation_by_photo]
    if not photos_to_process:
        st.info("Everything selected here already has a saved species suggestion.")
        return 0
    groups = planned_groups or build_review_photo_encounter_plan(
        photos_to_process,
        max_distance_meters=SMART_ID_MAX_DISTANCE_METERS,
        max_minutes=SMART_ID_MAX_MINUTES,
        max_photos=GROUPED_ID_MAX_PHOTOS,
    )
    if not groups:
        st.info("No photos are ready for ID request processing.")
        return 0
    try:
        inat_client.validate_credentials()
    except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
        st.session_state.inat_auth_notice = None
        st.session_state.inat_auth_error = str(exc)
        st.error(str(exc))
        return 0

    st.session_state.inat_auth_error = None
    total_groups = len(groups)
    processed_count = 0
    auto_split_group_count = 0
    warning_messages: list[str] = []
    progress_text = st.empty()
    progress_bar = st.progress(0, text="Preparing ID request groups...")
    with st.spinner("Sending ID request groups to iNaturalist..."):
        for index, group in enumerate(groups, start=1):
            group_photos = [row["photo"] for row in group["rows"]]
            group_size = len(group_photos)
            progress_text.caption(
                f"Processing ID request {index} of {total_groups} "
                f"({'grouped' if group_size > 1 else 'single'}; {group_size} photo{'s' if group_size != 1 else ''})."
            )
            try:
                if group_size == 1:
                    photo = group_photos[0]
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
                    processed_count += 1
                else:
                    grouped_candidate, processed_photos, individual_candidates, warnings = _build_grouped_species_candidate(
                        inat_client,
                        group_photos,
                        require_consensus=True,
                    )
                    warning_messages.extend(warnings)
                    for photo in processed_photos:
                        candidate = grouped_candidate or individual_candidates[str(photo["id"])]
                        observation = repository.upsert_observation(
                            photo.get("hike_id"),
                            photo["id"],
                            candidate,
                            owner_subject=photo.get("owner_subject"),
                            owner_email=photo.get("owner_email"),
                        )
                        ensure_taxon_enrichment(repository, inat_client, observation)
                    if grouped_candidate is None:
                        auto_split_group_count += 1
                    processed_count += len(processed_photos)
            except (InatConfigurationError, InatAuthError) as exc:
                st.session_state.inat_auth_notice = None
                st.session_state.inat_auth_error = str(exc)
                progress_bar.empty()
                progress_text.caption(f"Stopped after {processed_count} photo{'s' if processed_count != 1 else ''}.")
                st.error(str(exc))
                break
            except InatRateLimitError as exc:
                st.session_state.inat_auth_notice = None
                st.session_state.inat_auth_error = str(exc)
                progress_bar.empty()
                progress_text.caption(
                    f"iNaturalist asked HikeJournal to slow down after {processed_count} photo{'s' if processed_count != 1 else ''}."
                )
                st.warning(str(exc))
                break
            except InatComputerVisionBlockedError as exc:
                st.session_state.inat_auth_notice = None
                st.session_state.inat_auth_error = str(exc)
                progress_bar.empty()
                progress_text.caption(
                    f"Stopped after {processed_count} photo{'s' if processed_count != 1 else ''} because iNaturalist blocked CV suggestions from this server."
                )
                st.warning(str(exc))
                break
            except (InatRequestError, RuntimeError) as exc:
                warning_messages.append(f"{group_photos[0]['id'][:8]}: {exc}")
            progress_bar.progress(index / total_groups, text=f"Processed {index} of {total_groups} review decisions")

    invalidate_data_cache()
    if warning_messages:
        st.warning("ID requests skipped a few photos or groups:\n\n- " + "\n- ".join(warning_messages))
    if auto_split_group_count:
        st.info(
            f"{auto_split_group_count} proposed group{'s' if auto_split_group_count != 1 else ''} "
            "did not agree strongly enough, so those photos received individual suggestions."
        )
    if not st.session_state.inat_auth_error:
        progress_text.caption(
            f"Finished {total_groups} planned review decision{'s' if total_groups != 1 else ''} "
            f"for {processed_count} photo{'s' if processed_count != 1 else ''}."
        )
    return processed_count


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
    rejected_observation_ids: list[str] = []
    for observation in observations:
        if not observation:
            continue
        rejected_observation_ids.append(str(observation["id"]))
        if observation.get("photo_id"):
            rejected_photo_ids.add(str(observation["photo_id"]))
    repository.delete_observations(rejected_observation_ids)
    photo_ids_to_reset = [
        photo["id"]
        for photo in photos
        if not rejected_photo_ids or photo["id"] in rejected_photo_ids
    ]
    repository.update_photo_processing_statuses(photo_ids_to_reset, REVIEW_QUEUE_STATUS)
    invalidate_data_cache()


def remove_photos_from_review(repository: HikeJournalRepository, photos: list[dict[str, Any]]) -> None:
    photo_ids = [str(photo["id"]) for photo in photos if photo.get("id")]
    repository.delete_observations_for_photo_ids(photo_ids)
    repository.update_photo_processing_statuses(photo_ids, "ready")
    invalidate_data_cache()


def clear_species_selection(photos: list[dict[str, Any]]) -> None:
    clear_review_selection(st.session_state, photos)


def reset_species_log_page() -> None:
    st.session_state.species_log_page = 1
    st.session_state.species_log_focus_key = None


def reset_library_page() -> None:
    st.session_state.library_page = 1


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
    return build_view_href(
        view=view,
        state=st.session_state,
        hike_id=hike_id,
        scope=scope,
    )


def build_species_log_record_href(focus_key: str) -> str:
    return build_species_record_href(focus_key, st.session_state)


def set_species_log_record_query_state(focus_key: str | None, is_open: bool) -> None:
    update_species_record_query_state(st.query_params, focus_key, is_open)


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
    sync_viewer_state(st.session_state, st.query_params, photos)


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
