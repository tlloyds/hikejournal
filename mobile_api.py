from __future__ import annotations

import asyncio
from collections import defaultdict
import base64
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, date, datetime, timezone
from functools import lru_cache
import hashlib
import hmac
import logging
import json
import math
import os
import time
from pathlib import Path
from threading import Lock, Thread, local
from typing import Any, Annotated, Callable, Literal
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from supabase import Client, create_client

from hike_journal.config import settings
from hike_journal.domain.discovery import (
    DISCOVERY_ALGORITHM_VERSION,
    normalize_discovery_limit,
    normalize_radius,
    plain_text,
)
from hike_journal.domain.library import filter_hikes_for_user, record_visible_for_user, user_owns_record
from hike_journal.domain.locations import (
    attach_location_tags_to_hikes,
    canonical_location_id_map,
    canonicalize_hike_locations,
    suggest_location_ids_for_hike,
)
from hike_journal.domain.longitudinal import (
    build_field_briefing,
    build_hike_comparison,
    build_place_profile,
    build_seasonal_history,
)
from hike_journal.domain.routes import (
    delete_hike_and_assets,
    route_import_to_route_groups,
    sync_hike_route_import,
)
from hike_journal.models import HikeDraft, SpeciesCandidate
from hike_journal.services.exif import extract_metadata
from hike_journal.services.image_processing import optimize_image
from hike_journal.media import is_supported_video_upload, video_content_type
from hike_journal.mobile_contract import MOBILE_CONTRACT_VERSION, build_mobile_config
from hike_journal.services.api_runtime import RequestMetrics, run_dependency_probes
from hike_journal.services.app_store_server import (
    MAX_SIGNED_DATA_LENGTH,
    AppStoreAccountLinkError,
    AppStoreConfigurationError,
    AppStoreNotificationNotLinked,
    AppStoreServerVerifier,
    AppStoreVerificationError,
    build_app_store_server_verifier_from_environment,
)
from hike_journal.services.inat import (
    InatAuthError,
    InatClient,
    InatComputerVisionBlockedError,
    InatConfigurationError,
    InatRequestError,
    InatRateLimitError,
    build_oauth_authorize_url,
    exchange_oauth_code,
    fetch_api_token_for_oauth_access_token,
    parse_candidates,
    refresh_oauth_access_token,
    resolve_access_token_for_user,
)
from hike_journal.services.inat_publishing import (
    MAX_PUBLISH_IMAGE_BYTES,
    get_inat_posting,
    get_publish_state,
    publish_observation_group,
    publish_single_observation,
)
from hike_journal.services.encounters import build_publish_encounter_plan
from hike_journal.services.entitlements import (
    ClientPlatform,
    EntitlementService,
    EntitlementStoreError,
    FeatureAccessDecision,
    QuotaReservationDecision,
    QuotaResource,
    SupabaseEntitlementStore,
    feature_access,
)
from hike_journal.services.mobile_jobs import (
    InMemoryMobileJobStore,
    MobileJobIdempotencyConflict,
    MobileJobRecord,
    MobileJobStore,
    build_mobile_job_store,
    is_durable_mobile_job_id,
    is_mobile_job_recoverable,
    mobile_job_owner_key,
    mobile_job_request_fingerprint,
    validate_mobile_job_request,
)
from hike_journal.services.mobile_auth import (
    MobileAuthError,
    apple_auth_configuration_errors,
    create_apple_session,
    create_google_session,
    delete_mobile_account,
    google_web_client_id,
    mobile_auth_configuration_errors,
    mobile_auth_mode,
    mobile_session_secret,
    refresh_mobile_session,
    revoke_mobile_session,
    verify_access_token,
)
from hike_journal.public_pages import account_deletion_page, privacy_page, support_page
from hike_journal.services.species_identification import select_shared_candidate
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.discovery import SpeciesDiscoveryService
from hike_journal.services.outdoor_conditions import OutdoorConditionsService
from hike_journal.services.storage import StorageService
from hike_journal.services.taxonomy import ensure_observation_taxonomy
from hike_journal.services.weather import (
    OpenMeteoWeatherProvider,
    WeatherProviderError,
    enrich_hike_weather,
)
from hike_journal.services.wikipedia import enrich_missing_wikipedia_summaries


MAX_UPLOAD_BYTES = 30 * 1024 * 1024
EVERYDAY_JOURNAL_ID = "everyday"
MOBILE_JOB_OWNER_SCOPE = "single-owner"
SPECIES_REVIEW_JOB_TYPE = "species-review-batch"
SPECIES_PUBLISH_JOB_TYPE = "species-publish-batch"
MOBILE_JOB_MAX_LOCAL_WORKERS = 4
MOBILE_REVIEW_JOB_LEASE_SECONDS = 180
MOBILE_JOB_CACHE_FINGERPRINT_KEY = "_request_fingerprint"
# The current Android API surface predates server entitlements. Its commercial
# migration is intentionally observe-only until a separately deployed flow can
# supply cryptographically verified purchase/migration evidence. Existing
# routes therefore do not call the reservation or feature-decision helpers yet.
EXISTING_MOBILE_ENTITLEMENT_ENFORCEMENT_ENABLED = False
US_STATE_CODES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS "
    "MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
MOBILE_API_VERSION = Path(__file__).resolve().with_name("VERSION").read_text(encoding="utf-8").strip()
if not MOBILE_API_VERSION:
    raise RuntimeError("VERSION must contain the mobile API release version")
logger = logging.getLogger(__name__)


def _parse_picker_taken_at(value: str) -> datetime | None:
    raw = value.strip()
    if not raw or raw.casefold() == "null":
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Photo date and time must use ISO 8601 format.") from exc


def _validate_picker_coordinate(
    value: float | None,
    *,
    minimum: float,
    maximum: float,
    label: str,
) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise HTTPException(
            status_code=400,
            detail=f"Photo {label} must be between {minimum:g} and {maximum:g}.",
        )
    return value


def derive_mobile_api_token(supabase_key: str | None = None) -> str:
    """Return the configured pairing token without exposing infrastructure keys."""
    explicit = os.getenv("MOBILE_API_TOKEN", "").strip()
    if explicit:
        return explicit
    if os.getenv("MOBILE_REQUIRE_EXPLICIT_TOKEN", "").strip().lower() in {"1", "true", "yes"}:
        return ""
    source = (supabase_key if supabase_key is not None else settings.supabase_key).strip()
    if not source:
        return ""
    return hashlib.sha256(f"{source}:hikejournal-mobile-local-v1".encode()).hexdigest()


def _mobile_server_secret() -> str:
    return mobile_session_secret() if mobile_auth_mode() == "google" else derive_mobile_api_token()


def hosted_mobile_policy_enabled() -> bool:
    configured = os.getenv("MOBILE_REQUIRE_EXPLICIT_TOKEN", "").strip().lower()
    return configured in {"1", "true", "yes", "on"} or bool(
        os.getenv("K_SERVICE", "").strip()
    )


def _hosted_mobile_configuration_errors() -> list[str]:
    """Return non-secret configuration failures for the selected hosted auth mode."""
    if not hosted_mobile_policy_enabled():
        return []
    if mobile_auth_mode() == "google":
        return mobile_auth_configuration_errors()
    errors: list[str] = []
    token = os.getenv("MOBILE_API_TOKEN", "").strip()
    if len(token) < 32 or len(set(token)) < 12:
        errors.append("MOBILE_API_TOKEN must be a high-entropy value of at least 32 characters")
    owner_email = os.getenv("MOBILE_OWNER_EMAIL", "").strip().lower()
    if (
        not owner_email
        or "@" not in owner_email
        or owner_email.startswith("@")
        or owner_email.endswith("@")
        or any(character.isspace() for character in owner_email)
    ):
        errors.append("MOBILE_OWNER_EMAIL must identify the personal owner")
    if not os.getenv("MOBILE_OWNER_SUBJECT", "").strip():
        errors.append("MOBILE_OWNER_SUBJECT must be a stable personal-owner identifier")
    return errors


def _validate_hosted_mobile_configuration() -> None:
    errors = _hosted_mobile_configuration_errors()
    if errors:
        raise RuntimeError("Hosted mobile API configuration is invalid: " + "; ".join(errors))


def _auth_capabilities() -> tuple[str, ...]:
    if mobile_auth_mode() != "google":
        return ()
    capabilities = ["google_auth", "provider_neutral_identity", "user_places"]
    if not apple_auth_configuration_errors():
        capabilities.append("apple_auth")
    return tuple(capabilities)


def mobile_owner_email() -> str | None:
    explicit = os.getenv("MOBILE_OWNER_EMAIL", "").strip().lower()
    if explicit:
        return explicit
    return sorted(settings.admin_emails)[0] if settings.admin_emails else None


class HikeInput(BaseModel):
    id: str | None = Field(default=None, min_length=36, max_length=36)
    title: str = Field(min_length=1, max_length=160)
    hike_date: date
    distance_miles: float | None = Field(default=None, ge=0, le=1000)
    location_name: str = Field(default="", max_length=240)
    notes: str = Field(default="", max_length=20_000)
    location_id: str | None = Field(default=None, max_length=36)


class GoogleAuthInput(BaseModel):
    credential: str = Field(min_length=20, max_length=20_000)
    device_id: str = Field(min_length=8, max_length=160)
    nonce: str | None = Field(default=None, min_length=16, max_length=256)


class AppleAuthInput(BaseModel):
    identity_token: str = Field(min_length=20, max_length=20_000)
    device_id: str = Field(min_length=8, max_length=160)
    nonce: str = Field(min_length=16, max_length=256)
    display_name: str | None = Field(default=None, max_length=160)


class RefreshSessionInput(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)
    device_id: str = Field(min_length=8, max_length=160)


class LogoutInput(BaseModel):
    refresh_token: str = Field(default="", max_length=512)


class StoreKitTransactionSyncInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signedTransaction: str = Field(
        min_length=5,
        max_length=MAX_SIGNED_DATA_LENGTH,
    )
    signedRenewalInfo: str | None = Field(
        default=None,
        min_length=5,
        max_length=MAX_SIGNED_DATA_LENGTH,
    )


class AppStoreNotificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signedPayload: str = Field(
        min_length=5,
        max_length=MAX_SIGNED_DATA_LENGTH,
    )


class AppTransactionVerificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signedAppTransaction: str = Field(
        min_length=5,
        max_length=MAX_SIGNED_DATA_LENGTH,
    )


class HikeLocationInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class CaptionInput(BaseModel):
    caption: str = Field(default="", max_length=5_000)


class ArchiveInput(BaseModel):
    is_archived: bool


class CoverPhotoInput(BaseModel):
    photo_id: str | None = Field(default=None, max_length=36)


class ReviewQueueInput(BaseModel):
    queued: bool


class KnownSpeciesInput(BaseModel):
    taxon_id: int | None = None
    common_name: str = Field(default="", max_length=240)
    scientific_name: str = Field(default="", max_length=240)


class ReviewCandidateInput(BaseModel):
    taxon_id: int | None = None
    common_name: str = Field(default="", max_length=240)
    scientific_name: str = Field(default="", max_length=240)
    confidence: float | None = Field(default=None, ge=0, le=1)


class ReviewDecisionInput(BaseModel):
    action: Literal["confirm", "reject"]
    observation_id: str | None = None
    candidate: ReviewCandidateInput | None = None


class ReviewBatchGroupInput(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=8)


class ReviewBatchInput(BaseModel):
    groups: list[ReviewBatchGroupInput] = Field(min_length=1, max_length=50)
    client_request_id: str | None = Field(default=None, min_length=1, max_length=64)


class PublishInput(BaseModel):
    acknowledged_public: bool
    observation_ids: list[str] = Field(default_factory=list, max_length=10)
    description: str = Field(default="", max_length=5_000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    geoprivacy: Literal["open", "obscured", "private"] = "open"
    captive: bool = False


class PublishBatchGroupInput(BaseModel):
    observation_ids: list[str] = Field(min_length=1, max_length=8)


class PublishBatchInput(BaseModel):
    acknowledged_public: bool
    groups: list[PublishBatchGroupInput] = Field(min_length=1, max_length=50)
    client_request_id: str | None = Field(default=None, min_length=1, max_length=64)
    description: str = Field(default="", max_length=5_000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    geoprivacy: Literal["open", "obscured", "private"] = "open"
    captive: bool = False


class SpeciesQuestInput(BaseModel):
    area_id: str = Field(min_length=1, max_length=64)
    target_date: date
    radius_km: Literal[5, 10, 25] = 10
    iconic_taxon: str | None = Field(default=None, max_length=160)
    title: str = Field(default="", max_length=160)
    linked_hike_id: str | None = Field(default=None, max_length=36)
    result_limit: Literal[50, 100] = 50


class SpeciesQuestPatchInput(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    status: Literal["active", "archived"] | None = None
    linked_hike_id: str | None = Field(default=None, max_length=36)
    set_linked_hike: bool = False
    focus_taxon_ids: list[int] | None = Field(default=None, min_length=1, max_length=10)


class FieldMarkInput(BaseModel):
    id: str = Field(min_length=36, max_length=36)
    recording_session_id: str | None = Field(default=None, max_length=36)
    marked_at: datetime
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0, le=10_000)
    mark_type: Literal[
        "wildlife", "plant", "trail_condition", "water", "campsite", "hazard", "note"
    ]
    note: str = Field(default="", max_length=5_000)


class PhenophaseInput(BaseModel):
    code: Literal["vegetative", "budding", "flowering", "fruiting", "senescent"]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservationNaturalHistoryInput(BaseModel):
    confidence: Literal["tentative", "likely", "confident", "externally_confirmed"]
    provenance: Literal[
        "user", "inat_computer_vision", "inat_lookup", "inat_community",
        "external_expert", "imported_record", "legacy_import", "migration",
    ] = "user"
    phenophases: list[PhenophaseInput] = Field(default_factory=list, max_length=8)


class Services:
    def __init__(self) -> None:
        if not settings.supabase_configured:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required.")
        self.client: Client = create_client(settings.supabase_url, settings.supabase_key)
        self.storage = StorageService(self.client)
        self.repository = HikeJournalRepository(
            self.client,
            media_url_resolver=self.storage.resolve_download_url,
        )
        self.entitlement_store = SupabaseEntitlementStore(self.client)
        self.entitlements = EntitlementService(self.entitlement_store)
        self.mobile_job_store = build_mobile_job_store(self.client)


services: Services | None = None
_species_data_cache: dict[
    str,
    tuple[
        float,
        tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]],
    ],
] | None = None
_species_batch_jobs: dict[str, dict[str, Any]] = {}
_species_batch_jobs_lock = Lock()
_species_publish_jobs: dict[str, dict[str, Any]] = {}
_species_publish_jobs_lock = Lock()
_local_mobile_job_store: MobileJobStore = InMemoryMobileJobStore()
_mobile_job_dispatch_lock = Lock()
_mobile_jobs_dispatching: set[str] = set()
_mobile_job_worker = local()


class MobileJobLeaseLost(RuntimeError):
    """Stops a stale process worker after its durable lease has been replaced."""


def _invalidate_species_data_cache() -> None:
    global _species_data_cache
    _species_data_cache = None


def _species_data_cache_key(context: dict[str, Any]) -> str:
    user_id = str(context.get("user_id") or "").strip()
    subject = str(context.get("subject") or "").strip()
    email = str(context.get("email") or "").strip().lower()
    mode = str(context.get("mode") or "anonymous").strip()
    if user_id:
        stable_owner = f"uid:{user_id}"
    elif subject:
        stable_owner = f"subject:{subject}"
    elif email:
        stable_owner = f"email:{email}"
    else:
        stable_owner = f"mode:{mode}"
    return hashlib.sha256(stable_owner.encode("utf-8")).hexdigest()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global services
    _validate_hosted_mobile_configuration()
    services = Services()
    await asyncio.to_thread(_dispatch_recoverable_mobile_jobs)
    recovery_task = asyncio.create_task(_mobile_job_recovery_loop())
    try:
        yield
    finally:
        recovery_task.cancel()
        with suppress(asyncio.CancelledError):
            await recovery_task
        services = None


app = FastAPI(
    title="HikeJournal Mobile Companion API",
    version=MOBILE_API_VERSION,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
request_metrics = RequestMetrics()
_dependency_health_lock = Lock()
_dependency_health_cache: tuple[Any, float, dict[str, Any], bool] | None = None


def _request_route_template(request: Request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    return str(template) if template else "<unmatched>"


def _safe_request_id(request: Request) -> str:
    candidate = request.headers.get("x-request-id", "").strip()
    if candidate and len(candidate) <= 128 and all(
        character.isalnum() or character in "-_.:" for character in candidate
    ):
        return candidate
    return str(uuid4())


@app.middleware("http")
async def record_request_telemetry(request: Request, call_next: Callable[[Request], Any]):
    request_id = _safe_request_id(request)
    started = request_metrics.start_request()
    try:
        response = await call_next(request)
    except Exception:
        route = _request_route_template(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        request_metrics.finish_request(
            started=started,
            method=request.method,
            route=route,
            status_code=500,
        )
        logger.exception(
            (
                "Unhandled mobile API request failure request_id=%s method=%s "
                "route=%s status=%s latency_ms=%.2f"
            ),
            request_id,
            request.method,
            route,
            500,
            elapsed_ms,
            extra={
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status_code": 500,
                "latency_ms": round(elapsed_ms, 2),
            },
        )
        raise
    route = _request_route_template(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    request_metrics.finish_request(
        started=started,
        method=request.method,
        route=route,
        status_code=response.status_code,
    )
    logger.info(
        (
            "Mobile API request completed request_id=%s method=%s route=%s "
            "status=%s latency_ms=%.2f"
        ),
        request_id,
        request.method,
        route,
        response.status_code,
        elapsed_ms,
        extra={
            "request_id": request_id,
            "method": request.method,
            "route": route,
            "status_code": response.status_code,
            "latency_ms": round(elapsed_ms, 2),
        },
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-HikeJournal-API-Version"] = MOBILE_API_VERSION
    response.headers["X-HikeJournal-Contract-Version"] = MOBILE_CONTRACT_VERSION
    response.headers["Server-Timing"] = f"app;dur={elapsed_ms:.2f}"
    return response


_request_user_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "hikejournal_mobile_user_context",
    default=None,
)


async def require_mobile_key(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_hikejournal_key: Annotated[str | None, Header()] = None,
) -> None:
    if mobile_auth_mode() == "google":
        scheme, _, credential = (authorization or "").partition(" ")
        if scheme.casefold() != "bearer" or not credential:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in with Google to continue.")
        try:
            _request_user_context.set(verify_access_token(credential))
        except MobileAuthError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        return
    expected = derive_mobile_api_token()
    if not expected or not x_hikejournal_key or not hmac.compare_digest(expected, x_hikejournal_key):
        logger.warning(
            "Rejected invalid mobile pairing key route=%s",
            _request_route_template(request),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Pairing key is missing or invalid.")
    _request_user_context.set(None)


def get_services() -> Services:
    if services is None:
        raise HTTPException(status_code=503, detail="Mobile services are starting.")
    return services


@lru_cache(maxsize=1)
def get_app_store_server_verifier() -> AppStoreServerVerifier:
    """Build Apple verification only when an Apple endpoint is first used."""

    return build_app_store_server_verifier_from_environment()


def _require_app_store_server_verifier() -> AppStoreServerVerifier:
    try:
        return get_app_store_server_verifier()
    except AppStoreConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App Store server verification is not configured.",
        ) from exc


def _mobile_job_store() -> MobileJobStore:
    """Use durable Supabase jobs in service mode and an explicit local fallback in tests/dev."""
    active_services = services
    store = getattr(active_services, "mobile_job_store", None) if active_services is not None else None
    return store if isinstance(store, MobileJobStore) else _local_mobile_job_store


def _find_mobile_job_by_request(
    *,
    job_type: str,
    owner_context: dict[str, Any],
    client_request_id: str | None,
    request_payload: dict[str, Any] | None = None,
) -> MobileJobRecord | None:
    if not client_request_id:
        return None
    existing = _mobile_job_store().find_by_client_request(
        job_type=job_type,
        owner_scope=MOBILE_JOB_OWNER_SCOPE,
        owner_key=mobile_job_owner_key(owner_context),
        client_request_id=client_request_id,
    )
    if existing and request_payload is not None:
        try:
            validate_mobile_job_request(existing, request_payload)
        except MobileJobIdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return existing


def _validate_cached_mobile_job_request(
    cached_job: dict[str, Any],
    request_payload: dict[str, Any],
) -> None:
    """Validate current process-local entries without exposing the hash to clients."""
    expected = str(cached_job.get(MOBILE_JOB_CACHE_FINGERPRINT_KEY) or "")
    if not expected:
        # Compatibility for cache entries created before durable fingerprints
        # existed. They cannot be reconstructed without retaining raw input.
        return
    actual = mobile_job_request_fingerprint(request_payload)
    if not hmac.compare_digest(expected, actual):
        raise HTTPException(
            status_code=409,
            detail="This client request ID was already used for different background work.",
        )


def _get_mobile_job(job_id: str, *, job_type: str) -> MobileJobRecord | None:
    if not is_durable_mobile_job_id(job_id):
        # Older process-local tests/jobs used short IDs. Callers can still fall
        # back to those caches, but malformed public IDs never reach a UUID
        # column query in the durable store.
        return None
    record = _mobile_job_store().get(job_id)
    return record if record and record.job_type == job_type else None


def _create_mobile_job(
    *,
    job_type: str,
    owner_context: dict[str, Any],
    client_request_id: str | None,
    job: dict[str, Any],
    request_payload: dict[str, Any],
) -> tuple[MobileJobRecord, bool]:
    try:
        return _mobile_job_store().create(
            job_type=job_type,
            owner_scope=MOBILE_JOB_OWNER_SCOPE,
            owner_key=mobile_job_owner_key(owner_context),
            client_request_id=client_request_id,
            payload=job,
            request_payload=request_payload,
            job_id=str(job["job_id"]),
        )
    except MobileJobIdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _current_mobile_job_lease_owner() -> str | None:
    return getattr(_mobile_job_worker, "lease_owner", None)


def _clear_mobile_job_lease_owner() -> None:
    _mobile_job_worker.lease_owner = None


def _persist_mobile_job_update(job_id: str, **updates: Any) -> MobileJobRecord | None:
    lease_owner = _current_mobile_job_lease_owner()
    updated = _mobile_job_store().update(
        job_id,
        expected_lease_owner=lease_owner,
        lease_seconds=MOBILE_REVIEW_JOB_LEASE_SECONDS,
        **updates,
    )
    if lease_owner and updated is None:
        _clear_mobile_job_lease_owner()
        raise MobileJobLeaseLost(
            f"Worker lease for mobile job {job_id} was replaced before this update."
        )
    if updates.get("state") in {"completed", "failed", "cancelled"}:
        _clear_mobile_job_lease_owner()
    return updated


def _claim_mobile_job(job_id: str, *, job_type: str) -> bool:
    _clear_mobile_job_lease_owner()
    store = _mobile_job_store()
    record = store.get(job_id)
    if record is None:
        # Compatibility for direct unit tests and older process-local jobs.
        return True
    if record.job_type != job_type:
        return False
    worker_identity = f"{os.getenv('K_REVISION', 'local')}:{uuid4()}"
    claimed = store.acquire_lease(
        job_id,
        lease_owner=worker_identity,
        lease_seconds=1800,
    )
    if claimed is None:
        return False
    _mobile_job_worker.lease_owner = worker_identity
    return True


def _cache_mobile_job(record: MobileJobRecord) -> None:
    cached_payload = dict(record.payload)
    if record.request_fingerprint:
        cached_payload[MOBILE_JOB_CACHE_FINGERPRINT_KEY] = record.request_fingerprint
    if record.job_type == SPECIES_REVIEW_JOB_TYPE:
        with _species_batch_jobs_lock:
            _species_batch_jobs[record.job_id] = cached_payload
    elif record.job_type == SPECIES_PUBLISH_JOB_TYPE:
        with _species_publish_jobs_lock:
            _species_publish_jobs[record.job_id] = cached_payload


def _resume_species_review_job(
    record: MobileJobRecord,
    *,
    had_prior_attempt: bool | None = None,
) -> None:
    request = ReviewBatchInput.model_validate(record.request_payload)
    processed_ids = list(record.payload.get("processed_photo_ids") or [])
    processed_set = set(processed_ids)
    recovery_warnings: list[str] = []

    # A worker can stop after saving an observation but before its progress
    # callback is persisted. Treat an existing suggestion as completed so a
    # restart never repeats that external CV request or overwrites the result.
    should_reconcile = (
        had_prior_attempt if had_prior_attempt is not None else record.attempt_count > 0
    )
    if should_reconcile:
        svc = get_services()
        queue = _review_queue_payload(svc)
        queue_by_id = {str(item.get("id") or ""): item for item in queue}
        requested_ids = [photo_id for group in request.groups for photo_id in group.photo_ids]
        for photo_id in requested_ids:
            item = queue_by_id.get(photo_id)
            if photo_id in processed_set:
                continue
            if item is None or item.get("candidates"):
                processed_set.add(photo_id)
                processed_ids.append(photo_id)
                if item is None:
                    recovery_warnings.append(
                        f"Skipped {photo_id} because it is no longer waiting in species review."
                    )

    remaining_groups = [
        ReviewBatchGroupInput(
            photo_ids=[photo_id for photo_id in group.photo_ids if photo_id not in processed_set]
        )
        for group in request.groups
    ]
    remaining_groups = [group for group in remaining_groups if group.photo_ids]
    _cache_mobile_job(record)
    if processed_ids != list(record.payload.get("processed_photo_ids") or []) or recovery_warnings:
        _update_review_batch_job(
            record.job_id,
            processed_photo_ids=processed_ids,
            processed_count=len(processed_ids),
            warnings=list(record.payload.get("warnings") or []) + recovery_warnings,
        )

    if not remaining_groups:
        svc = get_services()
        processed_set = set(processed_ids)
        items = [
            item
            for item in _review_queue_payload(svc)
            if str(item.get("id") or "") in processed_set
        ]
        _update_review_batch_job(
            record.job_id,
            state="completed",
            processed_photo_ids=processed_ids,
            processed_count=len(processed_ids),
            current_photo_id=None,
            current_photo_number=int(record.payload.get("total_photos") or len(processed_ids)),
            items=items,
            error=None,
        )
        return

    resumed_request = request.model_copy(update={"groups": remaining_groups})
    svc, groups, full_photos_by_id, inat_client, _requested_ids = _prepare_species_batch_submission(
        resumed_request
    )
    _run_species_batch_job(
        record.job_id,
        svc,
        groups,
        full_photos_by_id,
        inat_client,
        int(record.payload.get("total_photos") or len(processed_ids) + len(_requested_ids)),
        lease_already_claimed=True,
    )


def _resume_species_publish_job(record: MobileJobRecord) -> None:
    request = PublishBatchInput.model_validate(record.request_payload)
    svc, records_by_group, inat_client, owner = _prepare_species_publish_batch(request)
    _cache_mobile_job(record)
    _run_species_publish_batch_job(
        record.job_id,
        svc,
        records_by_group,
        inat_client,
        owner,
        description=request.description,
        tags=request.tags,
        geoprivacy=request.geoprivacy,
        captive=request.captive,
        lease_already_claimed=True,
    )


def _resume_mobile_job(record: MobileJobRecord) -> None:
    _clear_mobile_job_lease_owner()
    try:
        if record.job_type not in {SPECIES_REVIEW_JOB_TYPE, SPECIES_PUBLISH_JOB_TYPE}:
            return
        # Claim before validation, reconciliation, or any other recovery work.
        # The database claim atomically rechecks the queued/retry/expiry state,
        # so a stale recovery snapshot can never write through a renewed lease.
        if not _claim_mobile_job(record.job_id, job_type=record.job_type):
            return
        claimed_record = _mobile_job_store().get(record.job_id) or record
        if record.job_type == SPECIES_REVIEW_JOB_TYPE:
            _resume_species_review_job(
                claimed_record,
                had_prior_attempt=record.attempt_count > 0,
            )
        else:
            _resume_species_publish_job(claimed_record)
    except MobileJobLeaseLost:
        logger.warning("Stopped stale worker for mobile job %s", record.job_id)
    except Exception as error:
        logger.exception("Could not recover durable mobile job %s", record.job_id)
        current_record = _mobile_job_store().get(record.job_id)
        if current_record and current_record.job_type == SPECIES_REVIEW_JOB_TYPE:
            retry_delay = _species_review_retry_delay(
                error,
                attempt_count=current_record.attempt_count,
            )
            if retry_delay is not None and current_record.attempt_count < current_record.max_attempts:
                retryable = _mobile_job_store().mark_retryable(
                    record.job_id,
                    error=_species_review_error_message(error, retrying=True),
                    retry_after_seconds=retry_delay,
                    expected_lease_owner=_current_mobile_job_lease_owner(),
                )
                if retryable:
                    _clear_mobile_job_lease_owner()
                    _cache_mobile_job(retryable)
                    return
        if not _current_mobile_job_lease_owner():
            # Preparation can fail before the normal worker claims the row.
            # Atomically claim it now; if another worker already did, leave
            # that replacement untouched instead of writing an unfenced error.
            failure_owner = f"{os.getenv('K_REVISION', 'local')}:recovery-error:{uuid4()}"
            claimed = _mobile_job_store().acquire_lease(
                record.job_id,
                lease_owner=failure_owner,
                lease_seconds=MOBILE_REVIEW_JOB_LEASE_SECONDS,
            )
            if claimed is None:
                logger.warning(
                    "Did not overwrite an already-claimed mobile job after recovery failed for %s",
                    record.job_id,
                )
                return
            _mobile_job_worker.lease_owner = failure_owner
        try:
            terminal_error = (
                _species_review_error_message(error, retrying=False)
                if record.job_type == SPECIES_REVIEW_JOB_TYPE
                else str(error) or "HikeJournal could not recover this background job."
            )
            _persist_mobile_job_update(
                record.job_id,
                state="failed",
                error=terminal_error,
            )
        except MobileJobLeaseLost:
            logger.warning(
                "Did not overwrite the replacement worker after recovery failed for mobile job %s",
                record.job_id,
            )
            return
        _cache_mobile_job(
            _mobile_job_store().get(record.job_id) or record
        )
    finally:
        with _mobile_job_dispatch_lock:
            _mobile_jobs_dispatching.discard(record.job_id)


def _start_mobile_job_dispatch(record: MobileJobRecord) -> bool:
    with _mobile_job_dispatch_lock:
        if record.job_id in _mobile_jobs_dispatching:
            return False
        if len(_mobile_jobs_dispatching) >= MOBILE_JOB_MAX_LOCAL_WORKERS:
            return False
        _mobile_jobs_dispatching.add(record.job_id)
    worker = Thread(
        target=_resume_mobile_job,
        args=(record,),
        name=f"mobile-job-{record.job_id[:8]}",
        daemon=True,
    )
    try:
        worker.start()
    except Exception:
        with _mobile_job_dispatch_lock:
            _mobile_jobs_dispatching.discard(record.job_id)
        logger.exception("Could not start local recovery worker for mobile job %s", record.job_id)
        return False
    return True


def _prepare_recoverable_mobile_job(record: MobileJobRecord) -> MobileJobRecord | None:
    store = _mobile_job_store()
    if record.state == "queued":
        return record
    if record.state == "failed":
        # Identification writes are local upserts and can be reconciled before
        # retry. A timed-out iNaturalist publish create is not safe to repeat
        # automatically because the remote API has no idempotency key.
        return record if record.job_type == SPECIES_REVIEW_JOB_TYPE else None
    if record.state == "running" and record.lease_expires_at:
        if not record.lease_owner:
            logger.warning(
                "Cannot safely recover running mobile job %s without its prior lease owner",
                record.job_id,
            )
            return None
        if record.attempt_count >= record.max_attempts:
            store.fail_expired_lease(
                record.job_id,
                expected_lease_owner=record.lease_owner,
                error=(
                    "The background worker stopped on its final attempt. "
                    "Review this job before starting it again."
                ),
            )
            return None
        if record.job_type == SPECIES_REVIEW_JOB_TYPE:
            # Leave the expired row untouched until the recovery worker's
            # atomic lease claim. This avoids an unfenced state transition
            # between the recovery scan and worker startup.
            return record
        store.fail_expired_lease(
            record.job_id,
            expected_lease_owner=record.lease_owner,
            error=(
                "The publishing worker stopped while iNaturalist may have been creating an observation. "
                "Review the publish queue before trying this group again."
            ),
        )
    return None


def _dispatch_recoverable_mobile_jobs(*, job_id: str | None = None) -> int:
    if job_id is not None and not is_durable_mobile_job_id(job_id):
        return 0
    try:
        store = _mobile_job_store()
        if job_id is not None:
            record = store.get(job_id)
            records = (
                [record]
                if record
                and record.job_type in {SPECIES_REVIEW_JOB_TYPE, SPECIES_PUBLISH_JOB_TYPE}
                and is_mobile_job_recoverable(record)
                else []
            )
        else:
            records = store.list_recoverable(
                job_types={SPECIES_REVIEW_JOB_TYPE, SPECIES_PUBLISH_JOB_TYPE}
            )
    except Exception:
        logger.exception("Could not inspect durable mobile jobs for recovery")
        return 0
    dispatched = 0
    for record in records:
        try:
            recoverable = _prepare_recoverable_mobile_job(record)
            if recoverable and _start_mobile_job_dispatch(recoverable):
                dispatched += 1
        except Exception:
            logger.exception("Could not prepare durable mobile job %s for recovery", record.job_id)
    return dispatched


async def _mobile_job_recovery_loop() -> None:
    raw_interval = os.getenv("MOBILE_JOB_RECOVERY_INTERVAL_SECONDS", "15").strip()
    try:
        interval = max(5, min(int(raw_interval), 300))
    except ValueError:
        interval = 15
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(_dispatch_recoverable_mobile_jobs)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Recovery is periodic by design. One transient database or local
            # thread failure must not permanently stop all future scans.
            logger.exception("Durable mobile job recovery iteration failed")


def _user_context() -> dict[str, Any]:
    authenticated = _request_user_context.get()
    if authenticated is not None:
        return authenticated
    email = mobile_owner_email()
    if not email:
        return {"mode": "local-dev", "email": None, "subject": None, "auth_configured": False}
    return {
        "mode": "google",
        "email": email,
        "subject": os.getenv("MOBILE_OWNER_SUBJECT", "").strip() or None,
        "auth_configured": True,
    }


def current_entitlement_user_id(
    svc: Services,
    *,
    context: dict[str, Any] | None = None,
) -> str:
    """Resolve the canonical account without ever treating email as identity."""
    owner = context if context is not None else _user_context()
    user_id = str(owner.get("user_id") or "").strip()
    if user_id:
        return user_id

    # Access tokens minted before uid/idp claims carry the historical Google
    # subject. Keep those tokens usable through the non-destructive shadow
    # column; Apple and other providers must reauthenticate rather than fall
    # back to an email or a Google subject lookup.
    subject = str(owner.get("subject") or "").strip()
    provider = str(
        owner.get("identity_provider") or owner.get("mode") or ""
    ).strip().lower()
    if not subject or provider not in {"", "google", "legacy", "local", "local-dev"}:
        raise HTTPException(
            status_code=409,
            detail="Sign in again to attach this session to your HikeJournal account.",
        )
    try:
        response = (
            svc.client.table("app_users")
            .select("id")
            .eq("google_subject", subject)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise EntitlementStoreError(
            "Could not resolve the account for entitlement access."
        ) from exc
    rows = response.data or []
    resolved_user_id = str(rows[0].get("id") or "").strip() if rows else ""
    if not resolved_user_id:
        raise HTTPException(
            status_code=409,
            detail="Sign in again to attach this session to your HikeJournal account.",
        )
    return resolved_user_id


def entitlement_feature_decision(
    svc: Services,
    feature: str,
    *,
    server_platform: ClientPlatform = ClientPlatform.UNKNOWN,
    trusted_legacy_paid_android: bool = False,
) -> FeatureAccessDecision:
    """Return a server decision; callers must not derive trust from request data."""
    user_id = current_entitlement_user_id(svc)
    snapshot = svc.entitlements.snapshot(user_id)
    return feature_access(
        snapshot,
        feature,
        platform=server_platform,
        trusted_legacy_paid_android=trusted_legacy_paid_android,
    )


def reserve_entitlement_quota(
    svc: Services,
    *,
    resource: QuotaResource,
    request_id: str,
    resource_id: str,
    ttl_seconds: int = 900,
) -> QuotaReservationDecision:
    """Reserve one canonical user's cloud quota for a future enforced write."""
    return svc.entitlements.reserve_quota(
        user_id=current_entitlement_user_id(svc),
        resource=resource,
        request_id=request_id,
        resource_id=resource_id,
        ttl_seconds=ttl_seconds,
    )


def release_entitlement_quota(
    svc: Services,
    *,
    resource: QuotaResource,
    request_id: str,
) -> bool:
    """Release a failed future write's idempotent quota reservation."""
    return svc.entitlements.release_quota(
        user_id=current_entitlement_user_id(svc),
        resource=resource,
        request_id=request_id,
    )


def _visible_hike_locations(repository: HikeJournalRepository) -> list[dict[str, Any]]:
    context = _user_context()
    return [
        location
        for location in repository.list_hike_locations()
        if (
            not location.get("owner_subject") and not location.get("owner_email")
        ) or user_owns_record(location, context)
    ]


def _visible_hikes(repository: HikeJournalRepository) -> list[dict[str, Any]]:
    visible = filter_hikes_for_user(repository.list_hikes(), _user_context())
    return attach_location_tags_to_hikes(
        visible,
        _visible_hike_locations(repository),
        repository.list_hike_location_tags(),
    )


def _visible_standalone_photos(svc: Services) -> list[dict[str, Any]]:
    context = _user_context()
    return [
        photo
        for photo in svc.repository.list_standalone_photos()
        if record_visible_for_user(photo, set(), context)
    ]


def _standalone_hike_payload(svc: Services, *, include_details: bool = False) -> dict[str, Any]:
    photos = _visible_standalone_photos(svc)
    photo_ids = [str(photo["id"]) for photo in photos if photo.get("id")]
    context = _user_context()
    observations = [
        observation
        for observation in svc.repository.list_observations_for_photo_ids(photo_ids)
        if record_visible_for_user(observation, set(), context)
    ] if photo_ids else []
    observations_by_photo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    confirmed_species: set[str] = set()
    for observation in observations:
        photo_id = str(observation.get("photo_id") or "")
        if photo_id:
            observations_by_photo[photo_id].append(observation)
        if observation.get("status") == "confirmed":
            confirmed_species.add(_species_key(observation))
    latest_date = next(
        (
            str(photo.get("taken_at") or photo.get("created_at") or "")[:10]
            for photo in photos
            if photo.get("taken_at") or photo.get("created_at")
        ),
        date.today().isoformat(),
    )
    payload = _hike_payload(
        {
            "id": EVERYDAY_JOURNAL_ID,
            "title": "Everyday sightings",
            "hike_date": latest_date,
            "location_name": "",
            "notes": "Quick observations that are not tied to a hike.",
            "is_archived": False,
            "is_standalone": True,
        },
        photos=photos,
        species_count=len(confirmed_species),
    )
    if include_details:
        payload["photos"] = [
            _photo_payload(photo, observations_by_photo.get(str(photo.get("id")), []))
            for photo in photos
        ]
        payload["route_segments"] = []
    return payload


def _require_discovery_enabled() -> None:
    if not settings.species_discovery_enabled:
        raise HTTPException(status_code=404, detail="Species discovery is not enabled.")


def _discovery_collection_data(
    svc: Services,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    observations, photos_by_id, _ = _visible_species_data(svc)
    return observations, photos_by_id


def _quest_visible_for_context(quest: dict[str, Any], context: dict[str, Any]) -> bool:
    if context.get("mode") == "local-dev":
        return True
    return user_owns_record(quest, context)


def _get_visible_quest(svc: Services, quest_id: str) -> dict[str, Any]:
    quest = svc.repository.get_species_quest(quest_id)
    if not quest or not _quest_visible_for_context(quest, _user_context()):
        raise HTTPException(status_code=404, detail="Field Quest not found.")
    return quest


def _get_visible_hike(repository: HikeJournalRepository, hike_id: str) -> dict[str, Any]:
    hike = next((row for row in _visible_hikes(repository) if str(row.get("id")) == hike_id), None)
    if not hike:
        raise HTTPException(status_code=404, detail="Hike not found.")
    return hike


def _field_mark_payload(mark: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(mark.get("id") or ""),
        "hike_id": str(mark.get("hike_id") or ""),
        "recording_session_id": str(mark.get("recording_session_id") or "") or None,
        "marked_at": mark.get("marked_at"),
        "lat": mark.get("lat"),
        "lng": mark.get("lng"),
        "accuracy_meters": mark.get("accuracy_meters"),
        "mark_type": str(mark.get("mark_type") or "note"),
        "note": str(mark.get("note") or ""),
        "created_at": mark.get("created_at"),
        "updated_at": mark.get("updated_at"),
    }


def _field_mark_payloads(repository: HikeJournalRepository, hike_id: str) -> list[dict[str, Any]]:
    try:
        return [_field_mark_payload(mark) for mark in repository.list_field_marks(hike_id)]
    except (AttributeError, RuntimeError):
        return []


MOBILE_WEATHER_FIELDS = (
    "provider",
    "provider_dataset",
    "algorithm_version",
    "interval_started_at",
    "interval_ended_at",
    "temperature_min_c",
    "temperature_mean_c",
    "temperature_max_c",
    "apparent_temperature_mean_c",
    "precipitation_total_mm",
    "relative_humidity_mean_percent",
    "cloud_cover_mean_percent",
    "wind_speed_mean_kph",
    "condition_label",
)


def _mobile_weather_payload(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not snapshot:
        return None
    return {field: snapshot.get(field) for field in MOBILE_WEATHER_FIELDS}


def _weather_payload(repository: HikeJournalRepository, hike_id: str) -> dict[str, Any] | None:
    getter = getattr(repository, "get_hike_weather_snapshot", None)
    return _mobile_weather_payload(getter(hike_id)) if getter else None


def _weather_payloads(repository: HikeJournalRepository, hike_ids: list[str]) -> dict[str, dict[str, Any]]:
    getter = getattr(repository, "list_hike_weather_snapshots", None)
    if not getter or not hike_ids:
        return {}
    try:
        rows = getter()
    except Exception:
        return {}
    visible_ids = set(hike_ids)
    snapshots: dict[str, dict[str, Any]] = {}
    for row in rows:
        hike_id = str(row.get("hike_id") or "")
        if hike_id in visible_ids:
            # Repository ordering is newest-first, so retain the first row if
            # an older weather algorithm also exists for this hike.
            compact = _mobile_weather_payload(row)
            if compact is not None:
                snapshots.setdefault(hike_id, compact)
    return snapshots


def _primary_hike_location(
    repository: HikeJournalRepository,
    hike: dict[str, Any],
) -> dict[str, Any] | None:
    tags = hike.get("location_tags") or []
    primary = next((tag for tag in tags if tag.get("is_primary")), tags[0] if tags else None)
    location_id = str((primary or {}).get("id") or "")
    return repository.get_hike_location(location_id) if location_id else None


def _enrich_weather_for_hike(
    svc: Services,
    hike: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    if not settings.weather_enrichment_enabled:
        raise WeatherProviderError("Weather enrichment is disabled on the companion service.")
    hike_id = str(hike.get("id") or "")
    provider = OpenMeteoWeatherProvider(
        forecast_url=settings.open_meteo_forecast_url,
        archive_url=settings.open_meteo_archive_url,
        api_key=settings.open_meteo_api_key,
        timeout_seconds=settings.weather_request_timeout_seconds,
    )
    return enrich_hike_weather(
        repository=svc.repository,
        hike=hike,
        route_import=svc.repository.get_hike_route_import(hike_id),
        location=_primary_hike_location(svc.repository, hike),
        provider=provider,
        force=force,
    )


def _normalize_client_uuid(value: str | None, *, field_name: str) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a UUID.") from exc


def _photo_payload(photo: dict[str, Any], species: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": str(photo.get("id") or ""),
        "hike_id": str(photo.get("hike_id") or "") or None,
        "url": str(photo.get("public_url") or ""),
        "caption": str(photo.get("caption") or ""),
        "taken_at": photo.get("taken_at"),
        "created_at": photo.get("created_at"),
        "lat": photo.get("lat"),
        "lng": photo.get("lng"),
        "width": photo.get("width"),
        "height": photo.get("height"),
        "content_type": photo.get("content_type") or "image/jpeg",
        "processing_status": photo.get("processing_status") or "ready",
        "species": [
            {
                **(
                    {
                        "observation_id": str(observation.get("id") or ""),
                        "confidence": observation.get("identification_confidence") or (
                            "confident" if observation.get("status") == "confirmed" else "tentative"
                        ),
                        "provenance": observation.get("identification_provenance") or "legacy_import",
                        "observed_on": observation.get("observed_on"),
                        "occurrence_precision": observation.get("occurrence_precision") or "unknown",
                        "phenophases": observation.get("phenophases") or [],
                        "identification_history": observation.get("identification_history") or [],
                        "iconic_taxon_name": observation.get("iconic_taxon_name"),
                    }
                    if observation.get("id")
                    else {}
                ),
                "common_name": observation.get("common_name"),
                "scientific_name": observation.get("scientific_name"),
                "status": observation.get("status"),
                "is_primary": bool(observation.get("is_primary")),
                "taxon_id": observation.get("taxon_id"),
                "wikipedia_url": str(
                    (observation.get("raw_response_json") or {})
                    .get("taxon_enrichment", {})
                    .get("wikipedia_url")
                    or observation.get("wikipedia_url")
                    or ""
                ),
                "wikipedia_summary": plain_text(
                    (observation.get("raw_response_json") or {})
                    .get("taxon_enrichment", {})
                    .get("wikipedia_summary")
                    or observation.get("wikipedia_summary")
                ),
            }
            for observation in (species or [])
        ],
    }


def _hike_payload(
    hike: dict[str, Any],
    *,
    photos: list[dict[str, Any]],
    species_count: int = 0,
    cover_photo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cover_id = str(hike.get("cover_photo_id") or "")
    cover = cover_photo if cover_photo and (not cover_id or str(cover_photo.get("id") or "") == cover_id) else None
    if cover is None and cover_id:
        cover = next((photo for photo in photos if str(photo.get("id")) == cover_id), None)
    if cover is None and not cover_id and photos:
        cover = max(
            photos,
            key=lambda photo: (
                str(photo.get("taken_at") or ""),
                str(photo.get("created_at") or ""),
            ),
        )
    location_tags = hike.get("location_tags") or []
    primary_location = next(
        (item for item in location_tags if item.get("is_primary")),
        location_tags[0] if location_tags else None,
    )
    return {
        "id": str(hike.get("id") or ""),
        "title": str(hike.get("title") or "Untitled hike"),
        "hike_date": str(hike.get("hike_date") or ""),
        "distance_miles": hike.get("distance_miles"),
        "location_name": str(hike.get("location_name") or ""),
        "primary_location_id": str((primary_location or {}).get("id") or "") or None,
        "primary_location_name": str((primary_location or {}).get("name") or ""),
        "notes": str(hike.get("notes") or ""),
        "is_archived": bool(hike.get("is_archived")),
        "is_standalone": bool(hike.get("is_standalone")),
        "cover_photo_id": cover_id or None,
        "cover_url": str((cover or {}).get("public_url") or ""),
        "photo_count": len(photos),
        "species_count": species_count,
    }


def _species_key(observation: dict[str, Any]) -> str:
    taxon_id = observation.get("species_taxon_id") or observation.get("taxon_id")
    if taxon_id not in (None, ""):
        return f"taxon:{taxon_id}"
    scientific_name = str(observation.get("scientific_name") or "").strip().casefold()
    if scientific_name:
        return f"scientific:{scientific_name}"
    return f"common:{str(observation.get('common_name') or 'unknown').strip().casefold()}"


def _observed_on(photo: dict[str, Any], hike: dict[str, Any] | None) -> str | None:
    return (
        str(photo.get("taken_at") or "").strip()
        or str((hike or {}).get("hike_date") or "").strip()
        or str(photo.get("created_at") or "").strip()
        or None
    )


def _observed_sort_key(value: str | None) -> float:
    raw = str(value or "").strip()
    if not raw:
        return float("-inf")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return float("-inf")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).timestamp()


def _decorate_observation_history(
    repository: HikeJournalRepository,
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    observation_ids = [str(item.get("id") or "") for item in observations if item.get("id")]
    if not observation_ids:
        return observations
    try:
        annotations = repository.list_observation_annotations(observation_ids)
        events = repository.list_identification_events(observation_ids)
    except Exception:
        # The release can be installed before its additive Supabase migration.
        # Existing Journal and Field Guide reads must remain available in that window.
        annotations = []
        events = []
    annotations_by_observation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    events_by_observation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for annotation in annotations:
        annotations_by_observation[str(annotation.get("observation_id") or "")].append(
            {
                "category": str(annotation.get("category") or ""),
                "code": str(annotation.get("code") or ""),
                "metadata": annotation.get("metadata") or {},
            }
        )
    for event in events:
        events_by_observation[str(event.get("observation_id") or "")].append(
            {
                "id": str(event.get("id") or ""),
                "taxon_id": event.get("species_taxon_id") or event.get("taxon_id"),
                "scientific_name": str(event.get("scientific_name") or ""),
                "common_name": str(event.get("common_name") or ""),
                "source": str(event.get("source") or "legacy_import"),
                "confidence": str(event.get("confidence") or "tentative"),
                "actor": str(event.get("actor") or ""),
                "note": str(event.get("note") or ""),
                "became_current": bool(event.get("became_current")),
                "created_at": event.get("created_at"),
            }
        )
    return [
        {
            **item,
            "phenophases": [
                annotation
                for annotation in annotations_by_observation.get(str(item.get("id") or ""), [])
                if annotation["category"] == "phenophase"
            ],
            "identification_history": events_by_observation.get(str(item.get("id") or ""), []),
        }
        for item in observations
    ]


def _dated_visible_observations(svc: Services) -> list[dict[str, Any]]:
    observations, photos_by_id, hikes_by_id = _visible_species_data(svc)
    return [
        {
            **observation,
            "observed_on": observation.get("observed_on")
            or _observed_on(
                photos_by_id.get(str(observation.get("photo_id") or ""), {}),
                hikes_by_id.get(str(observation.get("hike_id") or "")),
            ),
            "hike_date": str(
                hikes_by_id.get(str(observation.get("hike_id") or ""), {}).get("hike_date") or ""
            ),
            "reference_photo_url": str(
                photos_by_id.get(str(observation.get("photo_id") or ""), {}).get("public_url") or ""
            ),
        }
        for observation in observations
    ]


def _visible_species_data(
    svc: Services,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    global _species_data_cache
    context = _user_context()
    cache_key = _species_data_cache_key(context)
    scoped_cache = _species_data_cache if isinstance(_species_data_cache, dict) else {}
    current_time = time.monotonic()
    scoped_cache = {
        key: value
        for key, value in scoped_cache.items()
        if current_time - value[0] < 90
    }
    cached = scoped_cache.get(cache_key)
    if cached:
        _species_data_cache = scoped_cache
        return cached[1]
    hikes = _visible_hikes(svc.repository)
    hikes_by_id = {str(hike["id"]): hike for hike in hikes}
    visible_hike_ids = set(hikes_by_id)
    observation_rows = svc.repository.list_lightweight_observations(status="confirmed")
    observations = [
        observation
        for observation in observation_rows
        if record_visible_for_user(observation, visible_hike_ids, context)
    ]
    photo_ids = list(
        dict.fromkeys(
            str(observation.get("photo_id"))
            for observation in observations
            if observation.get("photo_id")
        )
    )
    photos = svc.repository.list_photo_records_for_ids(photo_ids)
    photos_by_id = {
        str(photo["id"]): photo
        for photo in photos
        if record_visible_for_user(photo, visible_hike_ids, context)
    }
    observations = [
        observation
        for observation in observations
        if str(observation.get("photo_id") or "") in photos_by_id
    ]
    result = (observations, photos_by_id, hikes_by_id)
    if cache_key not in scoped_cache and len(scoped_cache) >= 256:
        oldest_key = min(scoped_cache, key=lambda key: scoped_cache[key][0])
        scoped_cache.pop(oldest_key, None)
    scoped_cache[cache_key] = (current_time, result)
    _species_data_cache = scoped_cache
    return result


def _visible_species_counts_by_hike(
    svc: Services,
    visible_hike_ids: set[str],
) -> dict[str, int]:
    """Count confirmed species for the journal list without signing media URLs."""
    list_observations = getattr(svc.repository, "list_lightweight_observations", None)
    if not callable(list_observations):
        observations, _, _ = _visible_species_data(svc)
        buckets: dict[str, set[str]] = defaultdict(set)
        for observation in observations:
            hike_id = str(observation.get("hike_id") or "")
            if hike_id in visible_hike_ids:
                buckets[hike_id].add(_species_key(observation))
        return {hike_id: len(keys) for hike_id, keys in buckets.items()}

    context = _user_context()
    observations = list_observations(status="confirmed")
    visible_observations = [
        observation
        for observation in observations
        if record_visible_for_user(observation, visible_hike_ids, context)
    ]
    photos_by_id: dict[str, dict[str, Any]] = {}
    unresolved_photo_ids = [
        str(observation.get("photo_id"))
        for observation in visible_observations
        if not observation.get("hike_id") and observation.get("photo_id")
    ]
    if unresolved_photo_ids:
        photos = svc.repository.list_photo_records_for_ids(unresolved_photo_ids)
        photos_by_id = {str(photo.get("id")): photo for photo in photos if photo.get("id")}

    buckets: dict[str, set[str]] = defaultdict(set)
    for observation in visible_observations:
        hike_id = str(observation.get("hike_id") or "")
        if not hike_id:
            hike_id = str(photos_by_id.get(str(observation.get("photo_id") or ""), {}).get("hike_id") or "")
        if hike_id in visible_hike_ids:
            buckets[hike_id].add(_species_key(observation))
    return {hike_id: len(keys) for hike_id, keys in buckets.items()}


def _build_species_payloads(
    observations: list[dict[str, Any]],
    photos_by_id: dict[str, dict[str, Any]],
    hikes_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        groups[_species_key(observation)].append(observation)

    payloads: list[dict[str, Any]] = []
    for key, grouped in groups.items():
        ordered = sorted(
            grouped,
            key=lambda item: _observed_sort_key(
                _observed_on(
                    photos_by_id.get(str(item.get("photo_id") or ""), {}),
                    hikes_by_id.get(str(item.get("hike_id") or "")),
                )
            ),
            reverse=True,
        )
        lead = ordered[0]
        enrichment_lead = next(
            (
                item
                for item in ordered
                if str(item.get("wikipedia_summary") or "").strip()
                or str(item.get("wikipedia_url") or "").strip()
            ),
            lead,
        )
        encounter_photo_ids = list(
            dict.fromkeys(
                str(item.get("photo_id"))
                for item in ordered
                if str(item.get("photo_id") or "") in photos_by_id
            )
        )
        hike_ids = {
            str(item.get("hike_id"))
            for item in ordered
            if item.get("hike_id") and str(item.get("hike_id")) in hikes_by_id
        }
        hike_encounter_counts: dict[str, set[str]] = defaultdict(set)
        hike_cover_urls: dict[str, str] = {}
        hike_latest_seen: dict[str, str] = {}
        hike_latest_seen_keys: dict[str, float] = {}
        for item in ordered:
            hike_id = str(item.get("hike_id") or "")
            photo_id = str(item.get("photo_id") or "")
            if hike_id in hikes_by_id and photo_id in photos_by_id:
                hike_encounter_counts[hike_id].add(photo_id)
                photo = photos_by_id[photo_id]
                photo_url = str(photo.get("public_url") or "")
                if photo_url:
                    hike_cover_urls.setdefault(hike_id, photo_url)
                observed_on = _observed_on(photo, hikes_by_id[hike_id])
                observed_key = _observed_sort_key(observed_on)
                if observed_on and observed_key > hike_latest_seen_keys.get(hike_id, float("-inf")):
                    hike_latest_seen[hike_id] = observed_on
                    hike_latest_seen_keys[hike_id] = observed_key
        cover_photo = photos_by_id.get(encounter_photo_ids[0], {}) if encounter_photo_ids else {}
        latest_seen = _observed_on(
            cover_photo,
            hikes_by_id.get(str(cover_photo.get("hike_id") or "")),
        )
        iconic_taxon_name = next(
            (
                str(item.get("iconic_taxon_name")).strip()
                for item in ordered
                if str(item.get("iconic_taxon_name") or "").strip()
                and str(item.get("iconic_taxon_name") or "").strip().casefold() != "other"
            ),
            "Other",
        )
        payloads.append(
            {
                "key": key,
                "taxon_id": lead.get("taxon_id"),
                "common_name": str(lead.get("common_name") or lead.get("scientific_name") or "Unknown species"),
                "scientific_name": str(lead.get("scientific_name") or ""),
                "rank": str(lead.get("rank") or ""),
                "iconic_taxon_name": iconic_taxon_name,
                "wikipedia_url": str(enrichment_lead.get("wikipedia_url") or ""),
                "wikipedia_summary": str(enrichment_lead.get("wikipedia_summary") or ""),
                "encounter_count": len(encounter_photo_ids),
                "hike_count": len(hike_ids),
                "hike_ids": sorted(hike_ids),
                "hike_encounter_counts": {
                    hike_id: len(photo_ids)
                    for hike_id, photo_ids in sorted(hike_encounter_counts.items())
                },
                "hike_cover_urls": dict(sorted(hike_cover_urls.items())),
                "hike_latest_seen": dict(sorted(hike_latest_seen.items())),
                "latest_seen": latest_seen,
                "cover_url": str(cover_photo.get("public_url") or ""),
            }
        )
    return sorted(
        payloads,
        key=lambda item: (
            str(item.get("common_name") or item.get("scientific_name") or "").casefold(),
            str(item.get("scientific_name") or "").casefold(),
        ),
    )


def _candidate_payload(
    *,
    taxon_id: int | None,
    common_name: str,
    scientific_name: str,
    confidence: float | None,
    iconic_taxon_name: str = "Other",
) -> dict[str, Any]:
    payload = {
        "taxon_id": taxon_id,
        "common_name": common_name or scientific_name or "Unknown species",
        "scientific_name": scientific_name,
        "confidence": confidence,
    }
    if iconic_taxon_name and iconic_taxon_name.casefold() != "other":
        payload["iconic_taxon_name"] = iconic_taxon_name
    return payload


def _review_candidates(observation: dict[str, Any]) -> list[dict[str, Any]]:
    current = _candidate_payload(
        taxon_id=observation.get("taxon_id"),
        common_name=str(observation.get("common_name") or ""),
        scientific_name=str(observation.get("scientific_name") or ""),
        confidence=observation.get("confidence"),
        iconic_taxon_name=str(observation.get("iconic_taxon_name") or "Other"),
    )
    candidates = [current]
    raw_payload = observation.get("raw_response_json")
    if not isinstance(raw_payload, dict) or raw_payload.get("manual_override"):
        return candidates

    parsed: list[SpeciesCandidate] = []
    if raw_payload.get("grouped_cv") and isinstance(raw_payload.get("aggregate_candidates"), list):
        for item in raw_payload.get("aggregate_candidates") or []:
            if not isinstance(item, dict):
                continue
            try:
                confidence = float(item.get("average_confidence") or item.get("confidence") or 0)
            except (TypeError, ValueError):
                confidence = 0.0
            parsed.append(
                SpeciesCandidate(
                    common_name=str(item.get("common_name") or item.get("scientific_name") or "Unknown species"),
                    scientific_name=str(item.get("scientific_name") or ""),
                    confidence=confidence,
                    taxon_id=item.get("taxon_id"),
                    raw_payload=raw_payload,
                )
            )
    else:
        try:
            parsed = parse_candidates(raw_payload, limit=5)
        except Exception:
            parsed = []

    seen = {
        (str(current.get("taxon_id") or ""), str(current.get("scientific_name") or "").casefold())
    }
    for candidate in parsed:
        identity = (str(candidate.taxon_id or ""), candidate.scientific_name.casefold())
        if identity in seen:
            continue
        seen.add(identity)
        candidates.append(
            _candidate_payload(
                taxon_id=candidate.taxon_id,
                common_name=candidate.common_name,
                scientific_name=candidate.scientific_name,
                confidence=candidate.confidence,
            )
        )
        if len(candidates) == 4:
            break
    return candidates


def _review_queue_payload(svc: Services) -> list[dict[str, Any]]:
    hikes = _visible_hikes(svc.repository)
    hikes_by_id = {str(hike["id"]): hike for hike in hikes}
    visible_hike_ids = set(hikes_by_id)
    context = _user_context()
    photos = [
        photo
        for photo in svc.repository.list_review_queue_photos()
        if record_visible_for_user(photo, visible_hike_ids, context)
    ]
    observations = svc.repository.list_observations_for_photo_ids(
        [str(photo["id"]) for photo in photos if photo.get("id")]
    )
    visible_observations = [
        observation
        for observation in observations
        if record_visible_for_user(observation, visible_hike_ids, context)
    ]
    observations_by_photo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in visible_observations:
        observations_by_photo[str(observation.get("photo_id") or "")].append(observation)

    payloads: list[dict[str, Any]] = []
    for photo in photos:
        photo_id = str(photo.get("id") or "")
        photo_observations = observations_by_photo.get(photo_id, [])
        primary = next(
            (item for item in photo_observations if item.get("is_primary")),
            photo_observations[0] if photo_observations else None,
        )
        hike = hikes_by_id.get(str(photo.get("hike_id") or ""))
        payloads.append(
            {
                "id": photo_id,
                "photo": _photo_payload(photo, photo_observations),
                "hike_id": str((hike or {}).get("id") or "") or None,
                "hike_title": str((hike or {}).get("title") or "Everyday sighting"),
                "hike_date": str((hike or {}).get("hike_date") or ""),
                "location_name": str((hike or {}).get("location_name") or ""),
                "state": str((primary or {}).get("status") or "waiting"),
                "observation_id": str((primary or {}).get("id") or "") or None,
                "candidates": _review_candidates(primary) if primary else [],
            }
        )
    priority = {"pending": 0, "waiting": 1, "confirmed": 2, "rejected": 3}
    return sorted(
        payloads,
        key=lambda item: (
            priority.get(str(item.get("state") or "waiting"), 4),
            str((item.get("photo") or {}).get("taken_at") or ""),
        ),
    )


def _photo_observed_at(photo: dict[str, Any]) -> datetime | None:
    raw = str(photo.get("taken_at") or photo.get("created_at") or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromisoformat(raw[:10])
        except ValueError:
            return None


def _download_photo_for_cv(svc: Services, photo: dict[str, Any]) -> bytes:
    storage_path = str(photo.get("storage_path") or "").strip()
    if storage_path:
        return svc.storage.download_file(storage_path)
    raise InatRequestError("This photo cannot be identified because its stored image is unavailable.")


def _mobile_inat_client() -> InatClient:
    owner = _user_context()
    email = owner.get("email")
    user_id = str(owner.get("user_id") or "").strip()
    provider = str(owner.get("identity_provider") or owner.get("mode") or "").strip().lower()
    mobile_token = (
        _load_mobile_inat_token_for_user(user_id)
        if user_id
        else _load_mobile_inat_token(email)
    )
    if not mobile_token and user_id and provider in {"", "google", "legacy"}:
        mobile_token = _load_mobile_inat_token(email)
    token_record = _mobile_inat_oauth_record(mobile_token)
    if token_record:
        oauth_access_token = str(token_record.get("oauth_access_token") or "")
        refresh_token = str(token_record.get("refresh_token") or "")
        try:
            mobile_token = fetch_api_token_for_oauth_access_token(oauth_access_token)
        except InatAuthError:
            if not refresh_token:
                raise
            refreshed = refresh_oauth_access_token(refresh_token=refresh_token)
            if not refreshed.get("refresh_token"):
                refreshed["refresh_token"] = refresh_token
            if user_id:
                try:
                    _save_mobile_inat_oauth_token_for_user(
                        get_services(), user_id=user_id, token_payload=refreshed
                    )
                except InatConfigurationError:
                    if provider not in {"", "google", "legacy"} or not email:
                        raise
                    _save_mobile_inat_oauth_token(
                        get_services(), email=email, token_payload=refreshed
                    )
            else:
                _save_mobile_inat_oauth_token(get_services(), email=email, token_payload=refreshed)
            mobile_token = fetch_api_token_for_oauth_access_token(str(refreshed.get("access_token") or ""))
    # Older Android builds saved the short-lived OAuth token directly. The v1
    # write API needs the JWT returned by /users/api_token; reads can still
    # succeed with the OAuth token, which made this look connected until post.
    if mobile_token and mobile_token.count(".") != 2:
        mobile_token = fetch_api_token_for_oauth_access_token(mobile_token)
        if user_id:
            try:
                _save_mobile_inat_token_for_user(
                    get_services(), user_id=user_id, access_token=mobile_token
                )
            except InatConfigurationError:
                if provider not in {"", "google", "legacy"} or not email:
                    raise
                _save_mobile_inat_token(
                    get_services(), email=email, access_token=mobile_token
                )
        elif email:
            _save_mobile_inat_token(get_services(), email=email, access_token=mobile_token)
    legacy_email = email if provider in {"", "google", "legacy"} else None
    access_token = mobile_token or resolve_access_token_for_user(
        subject=owner.get("subject"),
        email=legacy_email,
    ) or settings.inat_access_token
    return InatClient(access_token=access_token, base_url=settings.inat_base_url)


def _mobile_inat_account_connected() -> bool:
    """Whether this signed-in mobile account has its own iNaturalist credential.

    The server may have a fallback token for web/admin work, but that does not
    mean the current mobile account completed iNaturalist OAuth. The mobile
    connection indicator must describe the account-scoped credential only.
    """
    owner = _user_context()
    email = owner.get("email")
    user_id = str(owner.get("user_id") or "").strip()
    provider = str(owner.get("identity_provider") or owner.get("mode") or "").strip().lower()
    token = _load_mobile_inat_token_for_user(user_id) if user_id else _load_mobile_inat_token(email)
    if not token and user_id and provider in {"", "google", "legacy"}:
        token = _load_mobile_inat_token(email)
    return bool(str(token or "").strip())


def _candidate_identity_key(candidate: SpeciesCandidate) -> str:
    if candidate.taxon_id is not None:
        return f"taxon:{candidate.taxon_id}"
    scientific = (candidate.scientific_name or "").strip().casefold()
    common = (candidate.common_name or "").strip().casefold()
    return f"name:{scientific or common or 'unknown'}"


def _build_mobile_grouped_species_candidate(
    svc: Services,
    inat_client: InatClient,
    photos: list[dict[str, Any]],
    *,
    on_photo_start: Callable[[str], None] | None = None,
) -> tuple[SpeciesCandidate | None, list[dict[str, Any]], dict[str, SpeciesCandidate], list[str]]:
    aggregate: dict[str, dict[str, Any]] = {}
    processed_photos: list[dict[str, Any]] = []
    individual_candidates: dict[str, SpeciesCandidate] = {}
    warnings: list[str] = []

    for photo in photos:
        photo_id = str(photo.get("id") or "")
        if on_photo_start:
            on_photo_start(photo_id)
        try:
            candidates, _payload = inat_client.score_species_candidates(
                image_bytes=_download_photo_for_cv(svc, photo),
                filename=f"{photo_id}.jpg",
                lat=photo.get("lat"),
                lng=photo.get("lng"),
                observed_on=_photo_observed_at(photo),
                limit=5,
            )
        except (
            InatConfigurationError,
            InatAuthError,
            InatRateLimitError,
            InatComputerVisionBlockedError,
        ):
            raise
        except (InatRequestError, RuntimeError) as exc:
            warnings.append(f"{photo_id[:8]}: {exc}")
            continue

        processed_photos.append(photo)
        individual_candidates[photo_id] = candidates[0]
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
            confidence = float(candidate.confidence or 0)
            entry["support_count"] += 1
            entry["total_confidence"] += confidence
            entry["best_confidence"] = max(entry["best_confidence"], confidence)
            if rank == 1:
                entry["top1_count"] += 1

    if not processed_photos:
        return None, [], {}, warnings

    aggregate_candidates = sorted(
        (
            {
                **entry,
                "average_confidence": entry["total_confidence"] / entry["support_count"]
                if entry["support_count"]
                else 0.0,
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
    top_match = select_shared_candidate(aggregate_candidates, photo_count=len(processed_photos))
    raw_payload = {
        "grouped_cv": True,
        "group_size": len(processed_photos),
        "group_photo_ids": [str(photo.get("id") or "") for photo in processed_photos],
        "aggregate_candidates": aggregate_candidates,
    }
    grouped_candidate = None
    if top_match is not None:
        selected_confidence = (
            top_match.get("best_confidence")
            if len(processed_photos) == 2
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


def _mobile_inat_oauth_record(value: str) -> dict[str, str] | None:
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    oauth_access_token = str(payload.get("oauth_access_token") or "").strip()
    if not oauth_access_token:
        return None
    return {
        "oauth_access_token": oauth_access_token,
        "refresh_token": str(payload.get("refresh_token") or "").strip(),
    }


def _mobile_inat_token_key() -> str:
    return hashlib.sha256(f"{_mobile_server_secret()}:inat-token-v1".encode()).hexdigest()


def _load_mobile_inat_token(email: str | None) -> str:
    if not email or services is None:
        return ""
    try:
        response = services.client.rpc(
            "load_mobile_inat_token",
            {"p_owner_email": email, "p_encryption_key": _mobile_inat_token_key()},
        ).execute()
        return str(response.data or "").strip()
    except Exception:
        return ""


def _load_mobile_inat_token_for_user(user_id: str | None) -> str:
    if not user_id or services is None:
        return ""
    try:
        response = services.client.rpc(
            "load_mobile_inat_token_for_user",
            {"p_user_id": user_id, "p_encryption_key": _mobile_inat_token_key()},
        ).execute()
        return str(response.data or "").strip()
    except Exception:
        return ""


def _save_mobile_inat_token(svc: Services, *, email: str, access_token: str) -> None:
    try:
        svc.client.rpc(
            "save_mobile_inat_token",
            {
                "p_owner_email": email,
                "p_access_token": access_token,
                "p_encryption_key": _mobile_inat_token_key(),
            },
        ).execute()
    except Exception as exc:
        raise InatConfigurationError(
            "The mobile iNaturalist credentials table is not ready. Apply sql/mobile_inat_oauth_migration.sql, then try again."
        ) from exc


def _save_mobile_inat_token_for_user(
    svc: Services,
    *,
    user_id: str,
    access_token: str,
) -> None:
    try:
        svc.client.rpc(
            "save_mobile_inat_token_for_user",
            {
                "p_user_id": user_id,
                "p_access_token": access_token,
                "p_encryption_key": _mobile_inat_token_key(),
            },
        ).execute()
    except Exception as exc:
        raise InatConfigurationError(
            "The provider-neutral iNaturalist credential store is not ready. Apply sql/provider_neutral_identity_migration.sql."
        ) from exc


def _save_mobile_inat_oauth_token(svc: Services, *, email: str, token_payload: dict[str, Any]) -> None:
    oauth_access_token = str(token_payload.get("access_token") or "").strip()
    if not oauth_access_token:
        raise InatAuthError("iNaturalist OAuth did not return a usable access token.")
    # Store the renewable OAuth credential, not the short-lived v1 JWT. The
    # existing encrypted text column deliberately supports this JSON payload.
    _save_mobile_inat_token(
        svc,
        email=email,
        access_token=json.dumps(
            {
                "oauth_access_token": oauth_access_token,
                "refresh_token": str(token_payload.get("refresh_token") or "").strip(),
            },
            separators=(",", ":"),
        ),
    )


def _save_mobile_inat_oauth_token_for_user(
    svc: Services,
    *,
    user_id: str,
    token_payload: dict[str, Any],
) -> None:
    oauth_access_token = str(token_payload.get("access_token") or "").strip()
    if not oauth_access_token:
        raise InatAuthError("iNaturalist OAuth did not return a usable access token.")
    _save_mobile_inat_token_for_user(
        svc,
        user_id=user_id,
        access_token=json.dumps(
            {
                "oauth_access_token": oauth_access_token,
                "refresh_token": str(token_payload.get("refresh_token") or "").strip(),
            },
            separators=(",", ":"),
        ),
    )


def _mobile_oauth_redirect_uri() -> str:
    configured = os.getenv("MOBILE_INAT_OAUTH_REDIRECT_URI", "").strip()
    if configured:
        return configured
    public_url = os.getenv("MOBILE_PUBLIC_URL", "").strip().rstrip("/")
    return f"{public_url}/v1/inat/oauth/callback" if public_url else ""


def _mobile_oauth_state(
    email: str,
    *,
    user_id: str | None = None,
    identity_provider: str | None = None,
) -> str:
    expires_at = int(time.time()) + 600
    canonical_user_id = str(user_id or "").strip()
    if canonical_user_id:
        prefix = "hj-mobile-user"
        raw_payload = json.dumps(
            {
                "uid": canonical_user_id,
                "idp": str(identity_provider or "").strip().lower(),
                "email": email.lower(),
                "exp": expires_at,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    else:
        # Exact legacy state payload retained for old Google sessions.
        prefix = "hj-mobile"
        raw_payload = f"{email.lower()}|{expires_at}"
    payload = base64.urlsafe_b64encode(raw_payload.encode()).decode().rstrip("=")
    signed_value = f"{prefix}.{payload}" if canonical_user_id else payload
    signature = hmac.new(
        _mobile_server_secret().encode(), signed_value.encode(), hashlib.sha256
    ).hexdigest()
    return f"{prefix}.{payload}.{signature}"


def _verify_mobile_oauth_state(state: str) -> dict[str, str | None] | None:
    parts = state.split(".")
    if len(parts) != 3 or parts[0] not in {"hj-mobile", "hj-mobile-user"}:
        return None
    prefix, payload, signature = parts
    signed_value = f"{prefix}.{payload}" if prefix == "hj-mobile-user" else payload
    expected = hmac.new(
        _mobile_server_secret().encode(), signed_value.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
        if prefix == "hj-mobile-user":
            value = json.loads(decoded)
            user_id = str(value.get("uid") or "").strip()
            email = str(value.get("email") or "").strip().lower()
            expires_at = int(value.get("exp"))
            if str(UUID(user_id)) != user_id.lower():
                return None
            if expires_at < int(time.time()):
                return None
            return {
                "user_id": user_id,
                "identity_provider": str(value.get("idp") or "").strip().lower() or None,
                "email": email or None,
            }
        email, expires_at = decoded.rsplit("|", 1)
        if int(expires_at) < int(time.time()) or not email:
            return None
        return {"user_id": None, "identity_provider": "google", "email": email.lower()}
    except (AttributeError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _publish_item_payload(
    observation: dict[str, Any],
    photo: dict[str, Any],
    hike: dict[str, Any] | None,
    *,
    source_hike_id: str | None = None,
    related_observation_ids: list[str] | None = None,
) -> dict[str, Any]:
    posting = get_inat_posting(observation)
    hike_id = str((hike or {}).get("id") or source_hike_id or "").strip() or EVERYDAY_JOURNAL_ID
    is_everyday_sighting = hike_id == EVERYDAY_JOURNAL_ID
    return {
        "id": str(observation.get("id") or ""),
        "photo": _photo_payload(photo, [observation]),
        "hike_id": hike_id,
        "hike_title": str((hike or {}).get("title") or ("Everyday sightings" if is_everyday_sighting else "Everyday sighting")),
        "hike_date": str((hike or {}).get("hike_date") or _observed_on(photo, None) or ""),
        "location_name": str((hike or {}).get("location_name") or ""),
        "taxon_id": observation.get("taxon_id"),
        "common_name": str(observation.get("common_name") or observation.get("scientific_name") or "Unknown species"),
        "scientific_name": str(observation.get("scientific_name") or ""),
        "state": get_publish_state(observation),
        "inat_observation_id": posting.get("observation_id"),
        "inat_url": str(posting.get("observation_url") or ""),
        "posted_at": posting.get("posted_at"),
        "photo_attached": posting.get("photo_attached"),
        "related_observation_ids": related_observation_ids or [str(observation.get("id") or "")],
        "related_photo_count": len(related_observation_ids or [observation]),
    }


def _publish_queue_payload(svc: Services) -> dict[str, Any]:
    observations, photos_by_id, hikes_by_id = _visible_species_data(svc)
    ready_rows: list[dict[str, Any]] = []
    for observation in observations:
        photo = photos_by_id.get(str(observation.get("photo_id") or ""))
        if not photo or get_publish_state(observation) != "ready":
            continue
        ready_rows.append(
            {
                "observation": observation,
                "photo": photo,
                "hike": hikes_by_id.get(str(photo.get("hike_id") or observation.get("hike_id") or "")),
            }
        )
    ready_groups_by_observation: dict[str, list[str]] = {}
    for group in build_publish_encounter_plan(ready_rows, max_photos=8):
        if group.get("oversized"):
            continue
        related_ids = [str(row.get("observation", {}).get("id") or "") for row in group.get("rows", [])]
        for row in group.get("rows", []):
            observation_id = str(row.get("observation", {}).get("id") or "")
            if observation_id:
                ready_groups_by_observation[observation_id] = related_ids
    items = []
    for observation in observations:
        photo = photos_by_id.get(str(observation.get("photo_id") or ""))
        if not photo:
            continue
        source_hike_id = str(photo.get("hike_id") or observation.get("hike_id") or "")
        hike = hikes_by_id.get(source_hike_id)
        observation_id = str(observation.get("id") or "")
        related_ids = ready_groups_by_observation.get(observation_id, [observation_id])
        items.append(
            _publish_item_payload(
                observation,
                photo,
                hike,
                source_hike_id=source_hike_id,
                related_observation_ids=related_ids[:8],
            )
        )
    priority = {"needs_attention": 0, "ready": 1, "posted": 2}
    items.sort(
        key=lambda item: (
            priority.get(str(item.get("state") or "ready"), 3),
            str((item.get("photo") or {}).get("taken_at") or ""),
        )
    )
    counts = {
        state: len([item for item in items if item.get("state") == state])
        for state in ("ready", "needs_attention", "posted")
    }
    return {
        "connected": _mobile_inat_account_connected(),
        "counts": counts,
        "items": items,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "hikejournal-mobile", "version": MOBILE_API_VERSION}


@app.get("/health/live")
def health_live() -> dict[str, str]:
    """Process liveness only; dependency failures must not trigger a restart loop."""
    return health()


def _dependency_health_payload() -> tuple[dict[str, Any], bool]:
    global _dependency_health_cache
    svc = services
    if svc is None:
        configuration_ok = not _hosted_mobile_configuration_errors()
        dependencies = {
            name: {"status": "starting"}
            for name in ("database", "storage", "job_store")
        }
        dependencies["configuration"] = {
            "status": "ok" if configuration_ok else "error"
        }
        return dependencies, False

    try:
        cache_seconds = max(
            1,
            min(float(os.getenv("MOBILE_HEALTH_CACHE_SECONDS", "10")), 60),
        )
    except ValueError:
        cache_seconds = 10
    with _dependency_health_lock:
        now = time.monotonic()
        cached = _dependency_health_cache
        if cached and cached[0] is svc and now - cached[1] <= cache_seconds:
            return cached[2], cached[3]
        probes = run_dependency_probes(
            {
                "configuration": _validate_hosted_mobile_configuration,
                "database": lambda: svc.client.table("hikes").select("id").limit(1).execute(),
                "storage": svc.storage.check_health,
                "job_store": svc.mobile_job_store.verify,
            },
            timeout_seconds=3,
        )
        dependencies = {name: result.payload() for name, result in probes.items()}
        ready = all(
            dependency["status"] == "ok" for dependency in dependencies.values()
        )
        _dependency_health_cache = (svc, now, dependencies, ready)
        return dependencies, ready


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    """Dependency-aware readiness with no credential or exception disclosure."""
    dependencies, ready = _dependency_health_payload()
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ok" if ready else "unavailable",
            "service": "hikejournal-mobile",
            "version": MOBILE_API_VERSION,
            "dependencies": dependencies,
        },
    )


@app.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
def public_privacy_policy() -> str:
    return privacy_page()


@app.get("/support", response_class=HTMLResponse, include_in_schema=False)
def public_support() -> str:
    return support_page()


@app.get("/account-deletion", response_class=HTMLResponse, include_in_schema=False)
def public_account_deletion() -> str:
    return account_deletion_page(google_web_client_id())


@app.post("/v1/auth/google")
def authenticate_google(payload: GoogleAuthInput) -> dict[str, Any]:
    if mobile_auth_mode() != "google":
        raise HTTPException(status_code=404, detail="Google sign-in is not enabled.")
    try:
        return create_google_session(
            get_services().client,
            credential=payload.credential,
            device_id=payload.device_id,
            nonce=payload.nonce,
        ).payload()
    except MobileAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@app.post("/v1/auth/apple")
def authenticate_apple(payload: AppleAuthInput) -> dict[str, Any]:
    if mobile_auth_mode() != "google":
        raise HTTPException(status_code=404, detail="Account sign-in is not enabled.")
    configuration_errors = apple_auth_configuration_errors()
    if configuration_errors:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign in with Apple server configuration is incomplete: "
            + "; ".join(configuration_errors),
        )
    try:
        return create_apple_session(
            get_services().client,
            identity_token=payload.identity_token,
            device_id=payload.device_id,
            nonce=payload.nonce,
            display_name=payload.display_name,
        ).payload()
    except MobileAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@app.post("/v1/auth/refresh")
def refresh_session(payload: RefreshSessionInput) -> dict[str, Any]:
    if mobile_auth_mode() != "google":
        raise HTTPException(status_code=404, detail="Google sign-in is not enabled.")
    try:
        return refresh_mobile_session(
            get_services().client,
            refresh_token=payload.refresh_token,
            device_id=payload.device_id,
        ).payload()
    except MobileAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@app.post("/v1/auth/logout", dependencies=[Depends(require_mobile_key)])
def logout_session(payload: LogoutInput) -> dict[str, bool]:
    revoke_mobile_session(get_services().client, refresh_token=payload.refresh_token)
    return {"signed_out": True}


def _account_asset_paths(svc: Services, context: dict[str, Any]) -> list[str]:
    owned_hikes = [
        hike
        for hike in svc.repository.list_hikes()
        if user_owns_record(hike, context)
    ]
    hike_ids = {str(hike.get("id") or "") for hike in owned_hikes if hike.get("id")}
    photos = [
        photo
        for hike_id in hike_ids
        for photo in svc.repository.list_photos(hike_id)
    ]
    photos.extend(
        photo
        for photo in svc.repository.list_standalone_photos()
        if user_owns_record(photo, context)
    )
    paths = {
        str(photo.get("storage_path") or "").strip()
        for photo in photos
        if str(photo.get("storage_path") or "").strip()
    }
    paths.update(
        str(route.get("source_storage_path") or "").strip()
        for route in svc.repository.list_hike_route_imports()
        if str(route.get("hike_id") or "") in hike_ids
        and str(route.get("source_storage_path") or "").strip()
    )
    return sorted(paths)


@app.delete("/v1/account", dependencies=[Depends(require_mobile_key)])
def delete_account() -> dict[str, bool]:
    context = _user_context()
    subject = str(context.get("subject") or "").strip()
    user_id = str(context.get("user_id") or "").strip()
    if not user_id and not subject:
        raise HTTPException(status_code=409, detail="A signed-in HikeJournal account is required.")
    svc = get_services()
    try:
        for storage_path in _account_asset_paths(svc, context):
            svc.storage.delete_file(storage_path)
    except Exception as exc:
        owner_key = user_id or subject
        logger.exception("Account media cleanup failed owner_hash=%s", hashlib.sha256(owner_key.encode()).hexdigest()[:12])
        raise HTTPException(
            status_code=503,
            detail="Account deletion paused before database cleanup because stored media could not be removed. Try again.",
        ) from exc
    try:
        delete_mobile_account(svc.client, user_id=user_id, google_subject=subject)
    except MobileAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"deleted": True}


@app.get("/v1/me/entitlement", dependencies=[Depends(require_mobile_key)])
def get_my_entitlement() -> dict[str, Any]:
    """Return server-authoritative plan, feature, limit, and usage state."""
    svc = get_services()
    try:
        user_id = current_entitlement_user_id(svc)
        return svc.entitlements.snapshot(user_id).to_payload()
    except HTTPException:
        raise
    except EntitlementStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post(
    "/v1/storekit/transactions/sync",
    dependencies=[Depends(require_mobile_key)],
)
def sync_storekit_transaction(
    payload: StoreKitTransactionSyncInput,
) -> dict[str, Any]:
    """Verify, link, and idempotently project one signed StoreKit transaction."""

    svc = get_services()
    verifier = _require_app_store_server_verifier()
    try:
        user_id = current_entitlement_user_id(svc)
        projection = verifier.verify_and_project_transaction_for_account(
            payload.signedTransaction,
            authenticated_user_id=user_id,
            signed_renewal_info=payload.signedRenewalInfo,
        )
        svc.entitlements.apply_projection(projection)
        return svc.entitlements.snapshot(user_id).to_payload()
    except HTTPException:
        raise
    except AppStoreAccountLinkError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The verified App Store transaction is not linked to this account.",
        ) from exc
    except AppStoreVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The App Store transaction could not be verified.",
        ) from exc
    except EntitlementStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def _entitlement_event_outcome(result: dict[str, Any]) -> str:
    if bool(result.get("duplicate")):
        return "duplicate"
    if bool(result.get("stale")):
        return "stale"
    if bool(result.get("applied")):
        return "applied"
    return "recorded"


@app.post("/v1/app-store/notifications/v2")
def receive_app_store_notification(
    payload: AppStoreNotificationInput,
) -> dict[str, Any]:
    """Verify Notification V2 and apply it only through a durable Apple link."""

    svc = get_services()
    verifier = _require_app_store_server_verifier()
    try:
        resolved = verifier.verify_resolve_and_project_notification(
            payload.signedPayload,
            resolver=svc.entitlement_store,
        )
        if resolved.projection is None:
            outcome = "none"
        else:
            result = svc.entitlements.apply_projection(resolved.projection)
            outcome = _entitlement_event_outcome(result)
        return {
            "accepted": True,
            "notification_uuid": resolved.envelope.notification_uuid,
            "entitlement_event": outcome,
        }
    except AppStoreNotificationNotLinked as exc:
        # Initial account linkage and Apple's notification can race. A non-2xx
        # response with Retry-After lets Apple safely redeliver after sync.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Subscription linkage is not ready; retry this notification later.",
            headers={"Retry-After": "60"},
        ) from exc
    except AppStoreAccountLinkError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The App Store notification conflicts with an existing account link.",
        ) from exc
    except AppStoreVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The App Store notification could not be verified.",
        ) from exc
    except EntitlementStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Entitlement storage is temporarily unavailable.",
            headers={"Retry-After": "60"},
        ) from exc


@app.post(
    "/v1/storekit/app-transaction/verify",
    dependencies=[Depends(require_mobile_key)],
)
def verify_storekit_app_transaction(
    payload: AppTransactionVerificationInput,
) -> dict[str, Any]:
    """Return bounded iOS app evidence without granting any entitlement."""

    svc = get_services()
    verifier = _require_app_store_server_verifier()
    try:
        # A valid HikeJournal session remains mandatory. AppTransaction proves
        # the signed app receipt, not the person's account or paid plan.
        current_entitlement_user_id(svc)
        evidence = verifier.verify_app_transaction(payload.signedAppTransaction)
    except HTTPException:
        raise
    except AppStoreVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The signed AppTransaction could not be verified.",
        ) from exc
    except EntitlementStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return {
        "verified": True,
        "app_transaction_id": evidence.app_transaction_id,
        "app_apple_id": evidence.app_apple_id,
        "bundle_id": evidence.bundle_id,
        "environment": evidence.environment,
        "application_version": evidence.application_version,
        "original_application_version": evidence.original_application_version,
        "receipt_created_at": evidence.receipt_created_at.isoformat(),
        "original_purchased_at": evidence.original_purchased_at.isoformat(),
        "original_platform": evidence.original_platform,
    }


@app.get("/v1/operations/health", dependencies=[Depends(require_mobile_key)])
def operations_health() -> JSONResponse:
    dependencies, ready = _dependency_health_payload()
    store = _mobile_job_store()
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ok" if ready else "unavailable",
            "version": MOBILE_API_VERSION,
            "contract_version": MOBILE_CONTRACT_VERSION,
            "durable_job_store": not isinstance(store, InMemoryMobileJobStore),
            "dependencies": dependencies,
        },
    )


@app.get("/v1/operations/metrics", dependencies=[Depends(require_mobile_key)])
def operations_metrics() -> dict[str, Any]:
    store = _mobile_job_store()
    return {
        "version": MOBILE_API_VERSION,
        "contract_version": MOBILE_CONTRACT_VERSION,
        "requests": request_metrics.snapshot(),
        "jobs": store.operational_metrics(),
    }


@app.get("/v1/config", dependencies=[Depends(require_mobile_key)])
def app_config() -> dict[str, Any]:
    store = _mobile_job_store()
    capabilities = ["api_contract_v1", "operational_health", "gzip_responses", *_auth_capabilities()]
    if not isinstance(store, InMemoryMobileJobStore):
        capabilities.append("durable_background_jobs")
    return {
        **build_mobile_config(
        web_url=os.getenv("MOBILE_WEB_URL", "http://192.168.0.157:8505"),
        api_version=MOBILE_API_VERSION,
        additional_capabilities=capabilities,
        ),
        "authentication": {
            "mode": mobile_auth_mode(),
            "google_client_id": google_web_client_id() if mobile_auth_mode() == "google" else None,
        },
    }


@app.get("/v1/inat/oauth/start", dependencies=[Depends(require_mobile_key)])
def start_mobile_inat_oauth() -> dict[str, str]:
    owner = _user_context()
    email = str(owner.get("email") or "").strip().lower()
    user_id = str(owner.get("user_id") or "").strip()
    identity_provider = str(
        owner.get("identity_provider") or owner.get("mode") or ""
    ).strip().lower()
    redirect_uri = _mobile_oauth_redirect_uri()
    if not user_id and not email:
        raise HTTPException(status_code=409, detail="Set MOBILE_OWNER_EMAIL before connecting iNaturalist on Android.")
    if not settings.inat_oauth_configured:
        raise HTTPException(status_code=409, detail="Configure the iNaturalist OAuth client ID and secret on the mobile companion service.")
    if not redirect_uri:
        raise HTTPException(status_code=409, detail="Configure MOBILE_INAT_OAUTH_REDIRECT_URI for the mobile companion service.")
    try:
        return {
            "authorize_url": build_oauth_authorize_url(
                state=_mobile_oauth_state(
                    email,
                    user_id=user_id or None,
                    identity_provider=identity_provider or None,
                ),
                redirect_uri=redirect_uri,
            )
        }
    except InatConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/v1/inat/oauth/callback")
def finish_mobile_inat_oauth(code: str | None = None, state: str | None = None, error: str | None = None):
    owner = _verify_mobile_oauth_state(state or "")
    if not owner:
        return RedirectResponse("hikejournal://inat?status=error&message=expired")
    if error:
        return RedirectResponse("hikejournal://inat?status=error&message=cancelled")
    if not code:
        return RedirectResponse("hikejournal://inat?status=error&message=missing_code")
    try:
        token_payload = exchange_oauth_code(code=code, redirect_uri=_mobile_oauth_redirect_uri())
        user_id = str(owner.get("user_id") or "").strip()
        email = str(owner.get("email") or "").strip().lower()
        identity_provider = str(owner.get("identity_provider") or "").strip().lower()
        if user_id:
            try:
                _save_mobile_inat_oauth_token_for_user(
                    get_services(), user_id=user_id, token_payload=token_payload
                )
            except InatConfigurationError:
                if identity_provider != "google" or not email:
                    raise
                _save_mobile_inat_oauth_token(
                    get_services(), email=email, token_payload=token_payload
                )
        elif email:
            _save_mobile_inat_oauth_token(
                get_services(), email=email, token_payload=token_payload
            )
        else:
            raise InatConfigurationError("The HikeJournal account identity is incomplete.")
    except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
        return RedirectResponse("hikejournal://inat?status=error&message=authorization_failed")
    return RedirectResponse("hikejournal://inat?status=connected")


@app.get("/v1/hikes", dependencies=[Depends(require_mobile_key)])
def list_hikes() -> list[dict[str, Any]]:
    svc = get_services()
    hikes = _visible_hikes(svc.repository)
    hike_ids = [str(hike["id"]) for hike in hikes]
    weather_by_hike = _weather_payloads(svc.repository, hike_ids)
    if hike_ids:
        list_photo_index = getattr(svc.repository, "list_photo_index_for_hikes", None)
        if callable(list_photo_index):
            photo_rows = list_photo_index(hike_ids)
        else:
            # Keep lightweight test doubles and older repository adapters working.
            photo_rows = svc.repository._select_all_rows(
                lambda: (
                    svc.client.table("photos")
                    .select("id,hike_id,public_url,storage_path,taken_at,created_at")
                    .in_("hike_id", hike_ids)
                    .order("id")
                )
            )
    else:
        photo_rows = []
    photos_by_hike: dict[str, list[dict[str, Any]]] = defaultdict(list)
    photos_by_id: dict[str, dict[str, Any]] = {}
    for photo in photo_rows:
        photo_id = str(photo.get("id") or "")
        if photo_id:
            photos_by_id[photo_id] = photo
        if photo.get("hike_id"):
            photos_by_hike[str(photo["hike_id"])].append(photo)
    cover_photo_ids = {
        str(hike.get("cover_photo_id") or "")
        for hike in hikes
        if hike.get("cover_photo_id")
    }
    missing_cover_photo_ids = sorted(cover_photo_ids - photos_by_id.keys())
    if missing_cover_photo_ids:
        for photo in svc.repository.list_photo_records_for_ids(missing_cover_photo_ids):
            photo_id = str(photo.get("id") or "")
            if photo_id:
                photos_by_id[photo_id] = photo
    species_count_by_hike = _visible_species_counts_by_hike(svc, set(hike_ids))
    outing_payloads = []
    for hike in hikes:
        hike_id = str(hike["id"])
        cover_id = str(hike.get("cover_photo_id") or "")
        selected_cover = photos_by_id.get(cover_id)
        if str((selected_cover or {}).get("hike_id") or "") != hike_id:
            selected_cover = None
        if selected_cover is None and not cover_id:
            selected_cover = max(
                photos_by_hike.get(hike_id, []),
                key=lambda photo: (
                    str(photo.get("taken_at") or ""),
                    str(photo.get("created_at") or ""),
                ),
                default=None,
            )
        decorate_media_row = getattr(svc.repository, "decorate_media_row", None)
        if selected_cover is not None and callable(decorate_media_row):
            selected_cover = decorate_media_row(selected_cover)
        payload = _hike_payload(
            hike,
            photos=photos_by_hike.get(hike_id, []),
            species_count=species_count_by_hike.get(hike_id, 0),
            cover_photo=selected_cover,
        )
        payload["weather"] = weather_by_hike.get(hike_id)
        outing_payloads.append(payload)
    return outing_payloads + [_standalone_hike_payload(svc)]


@app.get("/v1/hike-locations", dependencies=[Depends(require_mobile_key)])
def list_hike_locations(
    state: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
) -> list[dict[str, Any]]:
    """Return one state pack plus the signed-in user's personal places."""
    explicit_state = bool(str(state or "").strip())
    state_code = str(state or "FL").strip().upper()
    if state_code not in US_STATE_CODES:
        raise HTTPException(status_code=422, detail="Use a two-letter U.S. state code.")
    visible_locations = _visible_hike_locations(get_services().repository)
    visible_locations = [
        location
        for location in visible_locations
        if (
            location.get("owner_subject")
            or location.get("owner_email")
            or str(location.get("state") or "").upper() == state_code
            # Existing Florida rows gain their state on the first nationwide
            # seed import. A request without the new state parameter comes from
            # an older client, so preserve its legacy Florida-sized response.
            or (
                state_code == "FL"
                and not location.get("state")
                and (
                    not explicit_state
                    or str(location.get("source") or "").startswith("cfl_")
                )
            )
        )
    ]
    return [
        {
            "id": str(location.get("id") or ""),
            "name": str(location.get("name") or ""),
            "lat": _library_coordinate(location.get("lat"), minimum=-90.0, maximum=90.0),
            "lng": _library_coordinate(location.get("lng"), minimum=-180.0, maximum=180.0),
            **(
                {"state": str(location.get("state") or "").upper()}
                if location.get("state")
                else {}
            ),
            **(
                {"is_user_place": True}
                if location.get("owner_subject") or location.get("owner_email")
                else {}
            ),
        }
        for location in canonicalize_hike_locations(
            visible_locations
        )
        if location.get("id") and str(location.get("name") or "").strip()
    ]


@app.post("/v1/hike-locations", dependencies=[Depends(require_mobile_key)], status_code=201)
def create_hike_location(payload: HikeLocationInput) -> dict[str, Any]:
    owner = _user_context()
    subject = str(owner.get("subject") or "").strip()
    if not subject:
        raise HTTPException(status_code=409, detail="Sign in before adding a place.")
    if (payload.lat is None) != (payload.lng is None):
        raise HTTPException(status_code=422, detail="Add both latitude and longitude, or leave both blank.")
    try:
        location = get_services().repository.create_user_hike_location(
            payload.name,
            owner_subject=subject,
            owner_email=str(owner.get("email") or "").strip().lower() or None,
            lat=payload.lat,
            lng=payload.lng,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="HikeJournal could not save that place.") from exc
    return {
        "id": str(location.get("id") or ""),
        "name": str(location.get("name") or payload.name.strip()),
        "lat": _library_coordinate(location.get("lat"), minimum=-90.0, maximum=90.0),
        "lng": _library_coordinate(location.get("lng"), minimum=-180.0, maximum=180.0),
        "is_user_place": True,
    }


def _library_coordinate(value: Any, *, minimum: float, maximum: float) -> float | None:
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        return None
    return coordinate if math.isfinite(coordinate) and minimum <= coordinate <= maximum else None


def _analytics_hikes(svc: Services) -> list[dict[str, Any]]:
    route_by_hike = {
        str(item.get("hike_id") or ""): item
        for item in svc.repository.list_hike_route_imports()
        if item.get("hike_id")
    }
    results = []
    for hike in _visible_hikes(svc.repository):
        hike_id = str(hike.get("id") or "")
        photos = svc.repository.list_photos(hike_id)
        cover_url = _hike_payload(hike, photos=photos).get("cover_url")
        results.append(
            {
                **hike,
                "duration_seconds": route_by_hike.get(hike_id, {}).get("duration_seconds"),
                "cover_url": str(cover_url or ""),
            }
        )
    return results


@app.get("/v1/places/{location_id}/profile", dependencies=[Depends(require_mobile_key)])
def get_place_profile(location_id: str) -> dict[str, Any]:
    svc = get_services()
    locations = _visible_hike_locations(svc.repository)
    canonical_id = canonical_location_id_map(locations).get(location_id, location_id)
    location = next(
        (
            item
            for item in canonicalize_hike_locations(locations)
            if str(item.get("id") or "") == canonical_id
        ),
        None,
    )
    if location is None:
        raise HTTPException(status_code=404, detail="Place not found.")
    hikes = [
        hike
        for hike in _analytics_hikes(svc)
        if any(str(tag.get("id") or "") == canonical_id for tag in hike.get("location_tags") or [])
    ]
    return build_place_profile(location, hikes, _dated_visible_observations(svc))


@app.get(
    "/v1/places/{location_id}/conditions",
    dependencies=[Depends(require_mobile_key)],
)
def get_place_conditions(
    location_id: str,
    river_days: int = Query(default=7),
    followed_gauge_id: list[str] = Query(default=[]),
) -> dict[str, Any]:
    """Return shared, short-lived forecast and USGS planning conditions."""
    svc = get_services()
    locations = _visible_hike_locations(svc.repository)
    canonical_id = canonical_location_id_map(locations).get(location_id, location_id)
    location = next(
        (
            item
            for item in canonicalize_hike_locations(locations)
            if str(item.get("id") or "") == canonical_id
        ),
        None,
    )
    if location is None:
        raise HTTPException(status_code=404, detail="Place not found.")
    latitude = _validate_picker_coordinate(
        location.get("lat"), minimum=-90, maximum=90, label="latitude"
    )
    longitude = _validate_picker_coordinate(
        location.get("lng"), minimum=-180, maximum=180, label="longitude"
    )
    if latitude is None or longitude is None:
        raise HTTPException(
            status_code=422,
            detail="Add coordinates to this place before loading live conditions.",
        )
    return OutdoorConditionsService(svc.repository).place_conditions(
        latitude,
        longitude,
        period_days=30 if river_days >= 30 else 7,
        followed_site_ids=followed_gauge_id[:20],
    )


@app.get("/v1/field-briefing", dependencies=[Depends(require_mobile_key)])
def get_field_briefing(
    location_id: str = Query(min_length=1, max_length=64),
    target_date: date = Query(alias="date"),
    radius_km: int = Query(default=10),
    iconic_taxon: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=18, ge=1, le=50),
) -> dict[str, Any]:
    _require_discovery_enabled()
    svc = get_services()
    try:
        normalized_radius = normalize_radius(radius_km)
        area = SpeciesDiscoveryService.resolve_area(
            svc.repository,
            location_id,
            locations=_visible_hike_locations(svc.repository),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    observations, photos_by_id = _discovery_collection_data(svc)
    try:
        nearby = SpeciesDiscoveryService(svc.repository).nearby(
            area=area,
            target_date=target_date,
            radius_km=normalized_radius,
            iconic_taxon=iconic_taxon,
            observations=observations,
            photos_by_id=photos_by_id,
            limit=50,
        )
    except (ValueError, InatRequestError, InatRateLimitError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    place_hike_ids = {
        str(hike.get("id") or "")
        for hike in _visible_hikes(svc.repository)
        if any(str(tag.get("id") or "") == location_id for tag in hike.get("location_tags") or [])
    }
    context = _user_context()
    quests = svc.repository.list_species_quests(
        owner_subject=context.get("subject"),
        owner_email=context.get("email"),
    )
    active_quest_taxon_ids = _active_quest_focus_taxon_ids(quests)
    briefing = build_field_briefing(
        target_date=target_date,
        nearby_taxa=nearby.get("taxa") or [],
        observations=_dated_visible_observations(svc),
        place_hike_ids=place_hike_ids,
        active_quest_taxon_ids=active_quest_taxon_ids,
        limit=limit,
    )
    briefing_items = [
        item
        for section in briefing.get("sections") or []
        for item in section.get("items") or []
    ]
    enriched_by_key = {
        str(item.get("key") or ""): item
        for item in enrich_missing_wikipedia_summaries(briefing_items)
    }
    for section in briefing.get("sections") or []:
        section["items"] = [
            enriched_by_key.get(str(item.get("key") or ""), item)
            for item in section.get("items") or []
        ]
    return {
        **briefing,
        "area": nearby.get("area") or area,
        "period": nearby.get("period") or {},
        "source": nearby.get("source") or {},
    }


def _active_quest_focus_taxon_ids(quests: list[dict[str, Any]]) -> set[int]:
    """Return only the deliberately selected targets in visible active quests."""
    result: set[int] = set()
    for quest in quests:
        if str(quest.get("status") or "").casefold() != "active":
            continue
        for taxon in quest.get("taxa") or []:
            if taxon.get("focus_order") in (None, ""):
                continue
            try:
                result.add(int(taxon["taxon_id"]))
            except (KeyError, TypeError, ValueError):
                continue
    return result


@app.get("/v1/species", dependencies=[Depends(require_mobile_key)])
def list_species() -> list[dict[str, Any]]:
    svc = get_services()
    observations, photos_by_id, hikes_by_id = _visible_species_data(svc)
    return _build_species_payloads(observations, photos_by_id, hikes_by_id)


@app.get("/v1/discovery/areas", dependencies=[Depends(require_mobile_key)])
def list_discovery_areas(q: str = Query(default="", max_length=160)) -> list[dict[str, Any]]:
    _require_discovery_enabled()
    svc = get_services()
    return SpeciesDiscoveryService.list_areas(
        svc.repository,
        q,
        locations=_visible_hike_locations(svc.repository),
    )


@app.get("/v1/discovery/nearby", dependencies=[Depends(require_mobile_key)])
def get_nearby_species(
    area_id: str | None = Query(default=None, max_length=64),
    target_date: date = Query(alias="date"),
    radius_km: int = Query(default=10),
    iconic_taxon: str | None = Query(default=None, max_length=160),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    area_name: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50),
) -> dict[str, Any]:
    _require_discovery_enabled()
    try:
        normalized_radius = normalize_radius(radius_km)
        normalized_limit = normalize_discovery_limit(limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    svc = get_services()
    service = SpeciesDiscoveryService(svc.repository)
    if area_id:
        try:
            area = service.resolve_area(
                svc.repository,
                area_id,
                locations=_visible_hike_locations(svc.repository),
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    else:
        if lat is None or lng is None:
            raise HTTPException(status_code=400, detail="Choose an area or provide a current location.")
        area = {
            "id": "",
            "name": (area_name or "Current area").strip() or "Current area",
            "lat": round(float(lat), 2),
            "lng": round(float(lng), 2),
        }
    observations, photos_by_id = _discovery_collection_data(svc)
    try:
        return service.nearby(
            area=area,
            target_date=target_date,
            radius_km=normalized_radius,
            iconic_taxon=iconic_taxon,
            observations=observations,
            photos_by_id=photos_by_id,
            limit=normalized_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (InatRequestError, InatRateLimitError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/discovery/nearby/sightings", dependencies=[Depends(require_mobile_key)])
def get_nearby_species_sightings(
    taxon_id: int = Query(gt=0),
    area_id: str | None = Query(default=None, max_length=64),
    target_date: date = Query(alias="date"),
    radius_km: int = Query(default=10),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    area_name: str | None = Query(default=None, max_length=160),
) -> dict[str, Any]:
    _require_discovery_enabled()
    try:
        normalized_radius = normalize_radius(radius_km)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    svc = get_services()
    service = SpeciesDiscoveryService(svc.repository)
    if area_id:
        try:
            area = service.resolve_area(
                svc.repository,
                area_id,
                locations=_visible_hike_locations(svc.repository),
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    else:
        if lat is None or lng is None:
            raise HTTPException(status_code=400, detail="Choose an area or provide a current location.")
        area = {
            "id": "",
            "name": (area_name or "Current area").strip() or "Current area",
            "lat": round(float(lat), 2),
            "lng": round(float(lng), 2),
        }
    try:
        return service.nearby_sightings_payload(
            area=area,
            target_date=target_date,
            radius_km=normalized_radius,
            taxon_id=taxon_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (InatRequestError, InatRateLimitError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/discovery/quests", dependencies=[Depends(require_mobile_key)])
def list_species_quests() -> list[dict[str, Any]]:
    _require_discovery_enabled()
    svc = get_services()
    context = _user_context()
    observations, photos_by_id = _discovery_collection_data(svc)
    service = SpeciesDiscoveryService(svc.repository)
    return [
        service.quest_payload(quest, observations=observations, photos_by_id=photos_by_id)
        for quest in svc.repository.list_species_quests(
            owner_subject=context.get("subject"),
            owner_email=context.get("email"),
        )
        if _quest_visible_for_context(quest, context)
    ]


@app.post("/v1/discovery/quests", dependencies=[Depends(require_mobile_key)])
def create_species_quest(payload: SpeciesQuestInput) -> dict[str, Any]:
    _require_discovery_enabled()
    svc = get_services()
    context = _user_context()
    service = SpeciesDiscoveryService(svc.repository)
    try:
        area = service.resolve_area(
            svc.repository,
            payload.area_id,
            locations=_visible_hike_locations(svc.repository),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    linked_hike_id = _normalize_client_uuid(payload.linked_hike_id, field_name="linked_hike_id")
    if linked_hike_id:
        _get_visible_hike(svc.repository, linked_hike_id)
    observations, photos_by_id = _discovery_collection_data(svc)
    try:
        nearby = service.nearby(
            area=area,
            target_date=payload.target_date,
            radius_km=payload.radius_km,
            iconic_taxon=payload.iconic_taxon,
            observations=observations,
            photos_by_id=photos_by_id,
            limit=payload.result_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (InatRequestError, InatRateLimitError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    title = payload.title.strip() or f"{area['name']} · {nearby['period']['label']}"
    try:
        quest = svc.repository.create_species_quest(
            {
                "owner_subject": context.get("subject"),
                "owner_email": str(context.get("email") or "").strip().lower() or None,
                "location_id": area["id"],
                "linked_hike_id": linked_hike_id,
                "title": title,
                "status": "active",
                "area_name": area["name"],
                "lat": round(float(area["lat"]), 3),
                "lng": round(float(area["lng"]), 3),
                "radius_km": payload.radius_km,
                "target_date": payload.target_date.isoformat(),
                "months": nearby["period"]["months"],
                "iconic_taxon": nearby["filters"]["iconic_taxon"],
                "algorithm_version": DISCOVERY_ALGORITHM_VERSION,
                "target_count": len(nearby["taxa"]),
            },
            nearby["taxa"],
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return service.quest_payload(quest, observations=observations, photos_by_id=photos_by_id)


@app.get("/v1/discovery/quests/{quest_id}", dependencies=[Depends(require_mobile_key)])
def get_species_quest(quest_id: str) -> dict[str, Any]:
    _require_discovery_enabled()
    svc = get_services()
    quest = _get_visible_quest(svc, quest_id)
    observations, photos_by_id = _discovery_collection_data(svc)
    return SpeciesDiscoveryService(svc.repository).quest_payload(
        quest,
        observations=observations,
        photos_by_id=photos_by_id,
    )


@app.get("/v1/discovery/quests/{quest_id}/sightings", dependencies=[Depends(require_mobile_key)])
def get_species_quest_sightings(
    quest_id: str,
    taxon_id: int = Query(gt=0),
) -> dict[str, Any]:
    _require_discovery_enabled()
    svc = get_services()
    quest = _get_visible_quest(svc, quest_id)
    try:
        return SpeciesDiscoveryService(svc.repository).quest_sightings_payload(
            quest,
            taxon_id=taxon_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (InatRequestError, InatRateLimitError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.patch("/v1/discovery/quests/{quest_id}", dependencies=[Depends(require_mobile_key)])
def update_species_quest(quest_id: str, payload: SpeciesQuestPatchInput) -> dict[str, Any]:
    _require_discovery_enabled()
    svc = get_services()
    quest = _get_visible_quest(svc, quest_id)
    target_ids = {int(item["taxon_id"]) for item in quest.get("taxa") or []}
    focus_ids = payload.focus_taxon_ids
    if focus_ids is not None:
        deduped_focus = list(dict.fromkeys(int(taxon_id) for taxon_id in focus_ids))
        if not deduped_focus or len(deduped_focus) > 10 or any(taxon_id not in target_ids for taxon_id in deduped_focus):
            raise HTTPException(
                status_code=400,
                detail="Choose between one and ten focus finds that belong to this quest.",
            )
        focus_ids = deduped_focus
    linked_hike_id = payload.linked_hike_id
    if payload.set_linked_hike and linked_hike_id:
        linked_hike_id = _normalize_client_uuid(linked_hike_id, field_name="linked_hike_id")
        _get_visible_hike(svc.repository, linked_hike_id)
    updated = svc.repository.update_species_quest(
        quest_id,
        title=payload.title,
        status=payload.status,
        linked_hike_id=linked_hike_id,
        set_linked_hike=payload.set_linked_hike,
        focus_taxon_ids=focus_ids,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Field Quest not found.")
    observations, photos_by_id = _discovery_collection_data(svc)
    return SpeciesDiscoveryService(svc.repository).quest_payload(
        updated,
        observations=observations,
        photos_by_id=photos_by_id,
    )


@app.delete("/v1/discovery/quests/{quest_id}", dependencies=[Depends(require_mobile_key)])
def delete_species_quest(quest_id: str) -> dict[str, Any]:
    _require_discovery_enabled()
    svc = get_services()
    quest = _get_visible_quest(svc, quest_id)
    svc.repository.delete_species_quest(str(quest["id"]))
    return {"deleted": True, "id": str(quest["id"])}


@app.get("/v1/species/review", dependencies=[Depends(require_mobile_key)])
def list_species_review() -> list[dict[str, Any]]:
    return _review_queue_payload(get_services())


def _prepare_species_batch_submission(
    payload: ReviewBatchInput,
) -> tuple[Services, list[ReviewBatchGroupInput], dict[str, dict[str, Any]], InatClient, list[str]]:
    svc = get_services()
    queue = _review_queue_payload(svc)
    queue_by_id = {str(item.get("id") or ""): item for item in queue}
    requested_ids: list[str] = []
    seen_ids: set[str] = set()
    for group in payload.groups:
        if len(group.photo_ids) > 8:
            raise HTTPException(status_code=400, detail="A grouped ID request can include at most 8 photos.")
        for raw_photo_id in group.photo_ids:
            photo_id = str(raw_photo_id).strip()
            if not photo_id:
                raise HTTPException(status_code=400, detail="Every grouped ID photo must have an ID.")
            if photo_id in seen_ids:
                raise HTTPException(status_code=400, detail="A photo can only appear once in a grouped ID request.")
            seen_ids.add(photo_id)
            requested_ids.append(photo_id)

    missing_ids = [photo_id for photo_id in requested_ids if photo_id not in queue_by_id]
    if missing_ids:
        raise HTTPException(status_code=404, detail="One or more selected photos are no longer in species review.")
    not_waiting = [
        photo_id
        for photo_id in requested_ids
        if queue_by_id[photo_id].get("candidates")
    ]
    if not_waiting:
        raise HTTPException(status_code=409, detail="Only photos waiting for their first suggestion can be submitted for grouped identification.")

    # The review queue is a display contract and deliberately omits private
    # storage details. Resolve the selected IDs back to server-side photo
    # records before asking CV to download their originals.
    full_photo_rows = svc.repository.list_photo_records_for_ids(requested_ids)
    full_photos_by_id = {
        str(photo.get("id") or ""): photo
        for photo in full_photo_rows
        if photo.get("id")
    }
    if any(photo_id not in full_photos_by_id for photo_id in requested_ids):
        raise HTTPException(status_code=404, detail="One or more selected photo files are no longer available.")

    inat_client = _mobile_inat_client()
    try:
        inat_client.validate_credentials()
    except InatConfigurationError as exc:
        raise HTTPException(status_code=409, detail="Connect iNaturalist in HikeJournal before requesting recommendations.") from exc
    except InatAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except InatRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return svc, payload.groups, full_photos_by_id, inat_client, requested_ids


def _process_species_batch_submission(
    svc: Services,
    groups: list[ReviewBatchGroupInput],
    full_photos_by_id: dict[str, dict[str, Any]],
    inat_client: InatClient,
    *,
    on_group_start: Callable[[int], None] | None = None,
    on_photo_start: Callable[[str], None] | None = None,
    on_photo_complete: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    global _species_data_cache
    processed_ids: list[str] = []
    warnings: list[str] = []
    grouped_count = 0
    individual_count = 0
    for group_index, group in enumerate(groups, start=1):
        if on_group_start:
            on_group_start(group_index)
        group_photos = [full_photos_by_id[photo_id] for photo_id in group.photo_ids]
        if len(group_photos) == 1:
            photo = group_photos[0]
            if on_photo_start:
                on_photo_start(str(photo["id"]))
            try:
                candidate = inat_client.identify_species(
                    image_bytes=_download_photo_for_cv(svc, photo),
                    filename=f"{photo['id']}.jpg",
                    lat=photo.get("lat"),
                    lng=photo.get("lng"),
                    observed_on=_photo_observed_at(photo),
                )
            except (
                InatConfigurationError,
                InatAuthError,
                InatRateLimitError,
                InatComputerVisionBlockedError,
            ):
                raise
            except (InatRequestError, RuntimeError) as exc:
                warnings.append(f"{str(photo['id'])[:8]}: {exc}")
                continue
            observation = svc.repository.upsert_observation(
                photo.get("hike_id"),
                photo["id"],
                candidate,
                owner_subject=photo.get("owner_subject"),
                owner_email=photo.get("owner_email"),
            )
            ensure_observation_taxonomy(svc.repository, inat_client, observation)
            processed_ids.append(str(photo["id"]))
            individual_count += 1
            if on_photo_complete:
                on_photo_complete(str(photo["id"]))
            continue

        grouped_candidate, processed_photos, individual_candidates, group_warnings = _build_mobile_grouped_species_candidate(
            svc,
            inat_client,
            group_photos,
            on_photo_start=on_photo_start,
        )
        warnings.extend(group_warnings)
        if not processed_photos:
            continue
        if grouped_candidate is not None:
            grouped_count += 1
        else:
            individual_count += len(processed_photos)
            warnings.append(
                f"The {len(group_photos)}-photo group did not reach consensus; saved individual suggestions instead."
            )
        for photo in processed_photos:
            candidate = grouped_candidate or individual_candidates[str(photo["id"])]
            observation = svc.repository.upsert_observation(
                photo.get("hike_id"),
                photo["id"],
                candidate,
                owner_subject=photo.get("owner_subject"),
                owner_email=photo.get("owner_email"),
            )
            ensure_observation_taxonomy(svc.repository, inat_client, observation)
            processed_ids.append(str(photo["id"]))
            if on_photo_complete:
                on_photo_complete(str(photo["id"]))

    _species_data_cache = None
    refreshed_queue = _review_queue_payload(svc)
    processed_set = set(processed_ids)
    return {
        "items": [item for item in refreshed_queue if str(item.get("id") or "") in processed_set],
        "processed_photo_ids": processed_ids,
        "grouped_count": grouped_count,
        "individual_count": individual_count,
        "warnings": warnings,
    }


def _http_error_for_species_batch(error: Exception) -> HTTPException:
    if isinstance(error, InatConfigurationError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, InatAuthError):
        return HTTPException(status_code=401, detail=str(error))
    if isinstance(error, InatRateLimitError):
        return HTTPException(status_code=429, detail=str(error))
    if isinstance(error, InatComputerVisionBlockedError):
        return HTTPException(status_code=503, detail=str(error))
    if isinstance(error, InatRequestError):
        return HTTPException(status_code=502, detail=str(error))
    return HTTPException(status_code=500, detail="Species identification could not complete.")


def _species_review_retry_delay(error: Exception, *, attempt_count: int) -> int | None:
    if isinstance(error, (InatAuthError, InatConfigurationError)):
        return None
    if isinstance(error, InatRateLimitError):
        retry_after = getattr(error, "retry_after", None)
        return max(15, min(int(retry_after or 60), 900))
    if isinstance(error, InatComputerVisionBlockedError):
        return 300
    if isinstance(error, InatRequestError):
        return min(30 * (2 ** max(0, attempt_count - 1)), 300)
    if isinstance(error, HTTPException):
        if error.status_code == 429:
            return 60
        if error.status_code in {408, 425} or error.status_code >= 500:
            return min(30 * (2 ** max(0, attempt_count - 1)), 300)
    if _is_transient_transport_error(error):
        return min(15 * (2 ** max(0, attempt_count - 1)), 300)
    return None


def _exception_chain(error: BaseException):
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _is_transient_transport_error(error: BaseException) -> bool:
    transient_modules = ("requests", "urllib3", "httpx", "httpcore", "h2")
    transient_names = {
        "ConnectionError",
        "ConnectError",
        "ConnectTimeout",
        "ConnectionTerminated",
        "ProtocolError",
        "ReadError",
        "ReadTimeout",
        "RemoteProtocolError",
        "SSLError",
        "Timeout",
    }
    message_markers = (
        "connection reset",
        "connection terminated",
        "connectionterminated",
        "max retries exceeded",
        "remote protocol error",
        "server disconnected",
        "temporarily unavailable",
        "unexpected eof",
        "unexpected_eof",
    )
    for cause in _exception_chain(error):
        module_name = cause.__class__.__module__.lower()
        class_name = cause.__class__.__name__
        message = str(cause).lower()
        if class_name in transient_names and module_name.startswith(transient_modules):
            return True
        if any(marker in message for marker in message_markers):
            return True
    return False


def _species_review_error_message(error: Exception, *, retrying: bool) -> str:
    if isinstance(error, InatRequestError):
        return str(error)
    if isinstance(error, HTTPException):
        if error.status_code in {408, 425, 429} or error.status_code >= 500:
            if retrying:
                return "The connection was interrupted. HikeJournal is retrying this batch automatically."
            return "The connection was interrupted repeatedly. Refresh and retry the remaining photos."
        return str(error.detail)
    if _is_transient_transport_error(error):
        if retrying:
            return "The connection was interrupted. HikeJournal is retrying this batch automatically."
        return "The connection was interrupted repeatedly. Refresh and retry the remaining photos."
    if isinstance(error, (InatAuthError, InatConfigurationError)):
        return str(error)
    return "Species identification could not complete. Refresh and retry the remaining photos."


def _review_batch_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in job.items()
        if key not in {
            "owner_context",
            "client_request_id",
            MOBILE_JOB_CACHE_FINGERPRINT_KEY,
        }
    }


def _get_review_batch_job(job_id: str) -> dict[str, Any]:
    record = _get_mobile_job(job_id, job_type=SPECIES_REVIEW_JOB_TYPE)
    snapshot = dict(record.payload) if record else None
    if snapshot is None:
        with _species_batch_jobs_lock:
            job = _species_batch_jobs.get(job_id)
            snapshot = dict(job) if job else None
    if snapshot:
        snapshot["processed_photo_ids"] = list(snapshot.get("processed_photo_ids") or [])
        snapshot["warnings"] = list(snapshot.get("warnings") or [])
        snapshot["items"] = list(snapshot.get("items") or [])
    if (
        not snapshot
        or mobile_job_owner_key(snapshot.get("owner_context") or {})
        != mobile_job_owner_key(_user_context())
    ):
        raise HTTPException(status_code=404, detail="Species identification batch not found.")
    return _review_batch_job_payload(snapshot)


def _update_review_batch_job(job_id: str, **updates: Any) -> None:
    _persist_mobile_job_update(job_id, **updates)
    with _species_batch_jobs_lock:
        job = _species_batch_jobs.get(job_id)
        if job:
            job.update(updates)


def _run_species_batch_job(
    job_id: str,
    svc: Services,
    groups: list[ReviewBatchGroupInput],
    full_photos_by_id: dict[str, dict[str, Any]],
    inat_client: InatClient,
    total_photos: int,
    *,
    lease_already_claimed: bool = False,
) -> None:
    if lease_already_claimed:
        if not _current_mobile_job_lease_owner():
            raise MobileJobLeaseLost(job_id)
    elif not _claim_mobile_job(job_id, job_type=SPECIES_REVIEW_JOB_TYPE):
        return
    claimed_record = _get_mobile_job(job_id, job_type=SPECIES_REVIEW_JOB_TYPE)
    existing_payload = dict(claimed_record.payload) if claimed_record else {}
    baseline_processed_ids = list(existing_payload.get("processed_photo_ids") or [])
    baseline_grouped_count = int(existing_payload.get("grouped_count") or 0)
    baseline_individual_count = int(existing_payload.get("individual_count") or 0)
    baseline_warnings = list(existing_payload.get("warnings") or [])
    baseline_items = list(existing_payload.get("items") or [])
    _update_review_batch_job(job_id, state="running")
    next_photo_number = len(baseline_processed_ids) + 1

    def on_group_start(group_number: int) -> None:
        previous_group = int(existing_payload.get("current_group") or 0)
        _update_review_batch_job(job_id, current_group=max(previous_group, group_number))

    def on_photo_start(photo_id: str) -> None:
        nonlocal next_photo_number
        _update_review_batch_job(
            job_id,
            current_photo_id=photo_id,
            current_photo_number=min(next_photo_number, total_photos),
        )
        next_photo_number += 1

    def on_photo_complete(photo_id: str) -> None:
        with _species_batch_jobs_lock:
            cached = _species_batch_jobs.get(job_id)
            processed_ids = list((cached or {}).get("processed_photo_ids") or [])
        if cached is None:
            record = _get_mobile_job(job_id, job_type=SPECIES_REVIEW_JOB_TYPE)
            processed_ids = list((record.payload if record else {}).get("processed_photo_ids") or [])
        if photo_id not in processed_ids:
            processed_ids.append(photo_id)
        _update_review_batch_job(
            job_id,
            processed_photo_ids=processed_ids,
            processed_count=len(processed_ids),
        )

    try:
        result = _process_species_batch_submission(
            svc,
            groups,
            full_photos_by_id,
            inat_client,
            on_group_start=on_group_start,
            on_photo_start=on_photo_start,
            on_photo_complete=on_photo_complete,
        )
    except MobileJobLeaseLost:
        return
    except Exception as error:
        processed_ids = _get_review_batch_job(job_id).get("processed_photo_ids") or []
        refreshed_queue = _review_queue_payload(svc)
        processed_set = set(processed_ids)
        record = _get_mobile_job(job_id, job_type=SPECIES_REVIEW_JOB_TYPE)
        retry_delay = _species_review_retry_delay(
            error,
            attempt_count=record.attempt_count if record else 1,
        )
        if record and retry_delay is not None and record.attempt_count < record.max_attempts:
            retryable = _mobile_job_store().mark_retryable(
                job_id,
                error=_species_review_error_message(error, retrying=True),
                retry_after_seconds=retry_delay,
                expected_lease_owner=_current_mobile_job_lease_owner(),
            )
            if retryable:
                _clear_mobile_job_lease_owner()
                _cache_mobile_job(retryable)
                _update_review_batch_job(
                    job_id,
                    current_photo_id=None,
                    items=[
                        item
                        for item in refreshed_queue
                        if str(item.get("id") or "") in processed_set
                    ],
                )
                return
            if _current_mobile_job_lease_owner():
                _clear_mobile_job_lease_owner()
                return
        _update_review_batch_job(
            job_id,
            state="failed",
            error=_species_review_error_message(error, retrying=False),
            current_photo_id=None,
            items=[item for item in refreshed_queue if str(item.get("id") or "") in processed_set],
        )
        return

    processed_ids = list(dict.fromkeys([*baseline_processed_ids, *result["processed_photo_ids"]]))
    items_by_id = {
        str(item.get("id") or ""): item
        for item in [*baseline_items, *result["items"]]
        if item.get("id")
    }
    _update_review_batch_job(
        job_id,
        state="completed",
        processed_photo_ids=processed_ids,
        processed_count=len(processed_ids),
        current_photo_id=None,
        current_photo_number=total_photos,
        grouped_count=baseline_grouped_count + result["grouped_count"],
        individual_count=baseline_individual_count + result["individual_count"],
        warnings=list(dict.fromkeys([*baseline_warnings, *result["warnings"]])),
        items=list(items_by_id.values()),
        error=None,
    )


@app.post("/v1/species/review/batch-recommendation", dependencies=[Depends(require_mobile_key)])
def request_species_batch_recommendation(payload: ReviewBatchInput) -> dict[str, Any]:
    """Compatibility endpoint for clients that still expect a synchronous response."""
    svc, groups, full_photos_by_id, inat_client, _requested_ids = _prepare_species_batch_submission(payload)
    try:
        return _process_species_batch_submission(svc, groups, full_photos_by_id, inat_client)
    except Exception as error:
        raise _http_error_for_species_batch(error) from error


@app.post("/v1/species/review/batch-recommendation/start", dependencies=[Depends(require_mobile_key)])
def start_species_batch_recommendation(
    payload: ReviewBatchInput,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    owner_context = _user_context()
    if payload.client_request_id:
        # Check the durable ledger first even when this process has a cached
        # copy. The ledger owns the request fingerprint, so a reused request ID
        # with different work must not bypass the conflict check via the cache.
        persisted = _find_mobile_job_by_request(
            job_type=SPECIES_REVIEW_JOB_TYPE,
            owner_context=owner_context,
            client_request_id=payload.client_request_id,
            request_payload=payload.model_dump(mode="json"),
        )
        if persisted:
            return _review_batch_job_payload(persisted.payload)

        with _species_batch_jobs_lock:
            existing = next(
                (
                    existing
                    for existing in _species_batch_jobs.values()
                    if existing.get("owner_context") == owner_context
                    and existing.get("client_request_id") == payload.client_request_id
                ),
                None,
            )
            if existing:
                _validate_cached_mobile_job_request(
                    existing,
                    payload.model_dump(mode="json"),
                )
                # Fingerprinted cache entries were validated above. An older
                # entry with no hash remains reusable for local compatibility.
                return _review_batch_job_payload(dict(existing))

    svc, groups, full_photos_by_id, inat_client, requested_ids = _prepare_species_batch_submission(payload)
    job_id = str(uuid4())
    job = {
        "job_id": job_id,
        "state": "queued",
        "total_photos": len(requested_ids),
        "processed_count": 0,
        "processed_photo_ids": [],
        "current_photo_number": 0,
        "current_photo_id": None,
        "total_groups": len(groups),
        "current_group": 0,
        "grouped_count": 0,
        "individual_count": 0,
        "warnings": [],
        "error": None,
        "items": [],
        "owner_context": owner_context,
        "client_request_id": payload.client_request_id,
    }
    persisted_job, created = _create_mobile_job(
        job_type=SPECIES_REVIEW_JOB_TYPE,
        owner_context=owner_context,
        client_request_id=payload.client_request_id,
        job=job,
        request_payload=payload.model_dump(mode="json"),
    )
    if not created:
        return _review_batch_job_payload(persisted_job.payload)
    job = persisted_job.payload
    with _species_batch_jobs_lock:
        finished_ids = [
            existing_id
            for existing_id, existing in _species_batch_jobs.items()
            if existing.get("state") in {"completed", "failed"}
        ]
        for existing_id in finished_ids[:-50]:
            _species_batch_jobs.pop(existing_id, None)
        cached_job = dict(job)
        if persisted_job.request_fingerprint:
            cached_job[MOBILE_JOB_CACHE_FINGERPRINT_KEY] = persisted_job.request_fingerprint
        _species_batch_jobs[job_id] = cached_job
    background_tasks.add_task(
        _run_species_batch_job,
        job_id,
        svc,
        groups,
        full_photos_by_id,
        inat_client,
        len(requested_ids),
    )
    return _review_batch_job_payload(job)


@app.get("/v1/species/review/batch-recommendation/{job_id}", dependencies=[Depends(require_mobile_key)])
def get_species_batch_recommendation_status(job_id: str) -> dict[str, Any]:
    _dispatch_recoverable_mobile_jobs(job_id=job_id)
    return _get_review_batch_job(job_id)


@app.post("/v1/species/review/{photo_id}/recommendation", dependencies=[Depends(require_mobile_key)])
def request_species_recommendation(photo_id: str) -> dict[str, Any]:
    """Get fresh iNaturalist CV candidates for one photo and save them for review."""
    global _species_data_cache
    svc, photo = _get_visible_photo(photo_id)
    # A recommendation is itself a request for review.  Marking the photo here
    # lets the mobile photo viewer begin identification directly, without a
    # separate queueing step.
    if str(photo.get("processing_status") or "") != "in_review":
        svc.repository.update_photo_processing_status(photo_id, "in_review")
        photo["processing_status"] = "in_review"

    try:
        inat_client = _mobile_inat_client()
        candidates, _ = inat_client.score_species_candidates(
            image_bytes=_download_photo_for_cv(svc, photo),
            filename=f"{photo_id}.jpg",
            lat=photo.get("lat"),
            lng=photo.get("lng"),
            observed_on=_photo_observed_at(photo),
            limit=5,
        )
        primary = candidates[0]
        observation = svc.repository.upsert_observation(
            photo.get("hike_id"),
            photo_id,
            primary,
            owner_subject=photo.get("owner_subject"),
            owner_email=photo.get("owner_email"),
        )
        if isinstance(observation, dict):
            ensure_observation_taxonomy(svc.repository, inat_client, observation)
    except InatConfigurationError as exc:
        raise HTTPException(status_code=409, detail="Connect iNaturalist in HikeJournal before requesting a recommendation.") from exc
    except InatAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except InatRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except InatComputerVisionBlockedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InatRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    _species_data_cache = None
    item = next((row for row in _review_queue_payload(svc) if str(row.get("id")) == photo_id), None)
    if not item:
        raise HTTPException(status_code=500, detail="iNaturalist returned a suggestion, but HikeJournal could not reload it.")
    return item


@app.post("/v1/species/review/{photo_id}/decision", dependencies=[Depends(require_mobile_key)])
def decide_species_review(photo_id: str, payload: ReviewDecisionInput) -> dict[str, Any]:
    global _species_data_cache
    svc = get_services()
    queue = _review_queue_payload(svc)
    item = next((row for row in queue if str(row.get("id")) == photo_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Review photo not found.")
    observation_id = payload.observation_id or item.get("observation_id")
    if not observation_id:
        raise HTTPException(status_code=409, detail="This photo does not have a species suggestion yet.")
    observations = svc.repository.list_observations_by_ids([str(observation_id)])
    observation = next(
        (
            row
            for row in observations
            if str(row.get("photo_id") or "") == photo_id
        ),
        None,
    )
    if not observation:
        raise HTTPException(status_code=404, detail="Species suggestion not found.")

    if payload.action == "reject":
        svc.repository.delete_observations([str(observation_id)])
        svc.repository.update_photo_processing_status(photo_id, "in_review")
    else:
        inat_client = _mobile_inat_client()
        if payload.candidate:
            candidate = SpeciesCandidate(
                taxon_id=payload.candidate.taxon_id,
                common_name=payload.candidate.common_name,
                scientific_name=payload.candidate.scientific_name,
                confidence=float(payload.candidate.confidence or 0),
                raw_payload=(
                    observation.get("raw_response_json")
                    if isinstance(observation.get("raw_response_json"), dict)
                    else {}
                ),
            )
            updated = svc.repository.apply_candidate_to_observation(
                str(observation_id),
                photo_id=photo_id,
                candidate=candidate,
                status="confirmed",
                is_primary=True,
            )
        else:
            updated = svc.repository.update_observation_status(str(observation_id), "confirmed")
        if isinstance(updated, dict):
            ensure_observation_taxonomy(svc.repository, inat_client, updated)
        svc.repository.update_photo_processing_status(photo_id, "ready")

    _species_data_cache = None
    return {"ok": True, "photo_id": photo_id, "action": payload.action}


@app.get("/v1/species/publish", dependencies=[Depends(require_mobile_key)])
def list_species_publish() -> dict[str, Any]:
    return _publish_queue_payload(get_services())


def _prepare_species_publish_batch(
    payload: PublishBatchInput,
) -> tuple[
    Services,
    list[list[tuple[dict[str, Any], dict[str, Any]]]],
    InatClient,
    dict[str, Any],
]:
    if not payload.acknowledged_public:
        raise HTTPException(
            status_code=400,
            detail="Confirm that these observations will become public on iNaturalist.",
        )
    svc = get_services()
    visible_observations, photos_by_id, _hikes_by_id = _visible_species_data(svc)
    visible_by_id = {str(item.get("id") or ""): item for item in visible_observations}
    normalized_groups: list[list[str]] = []
    requested_ids: list[str] = []
    for group in payload.groups:
        normalized_group = [str(observation_id).strip() for observation_id in group.observation_ids]
        if any(not observation_id for observation_id in normalized_group):
            raise HTTPException(status_code=400, detail="Every grouped observation must have an ID.")
        if len(set(normalized_group)) != len(normalized_group):
            raise HTTPException(status_code=400, detail="A grouped observation cannot include the same sighting twice.")
        normalized_groups.append(normalized_group)
        requested_ids.extend(normalized_group)
    if len(set(requested_ids)) != len(requested_ids):
        raise HTTPException(status_code=400, detail="Each confirmed sighting can appear in only one planned observation.")
    if any(observation_id not in visible_by_id for observation_id in requested_ids):
        raise HTTPException(status_code=404, detail="Confirmed observation not found.")

    full_rows = svc.repository.list_observations_by_ids(requested_ids)
    full_by_id = {
        str(item.get("id") or ""): item
        for item in full_rows
    }
    if any(observation_id not in full_by_id for observation_id in requested_ids):
        raise HTTPException(status_code=404, detail="Confirmed observation not found.")

    records_by_group: list[list[tuple[dict[str, Any], dict[str, Any]]]] = []
    for normalized_group in normalized_groups:
        records: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for observation_id in normalized_group:
            observation = full_by_id[observation_id]
            if observation.get("status") != "confirmed":
                raise HTTPException(status_code=409, detail="Confirm every species identification before publishing.")
            if get_publish_state(observation) != "ready":
                raise HTTPException(status_code=409, detail="One of these sightings has already been published to iNaturalist.")
            photo = photos_by_id.get(str(observation.get("photo_id") or ""))
            if not photo:
                raise HTTPException(status_code=404, detail="The observation photo could not be found.")
            records.append((observation, photo))
        records_by_group.append(records)

    inat_client = _mobile_inat_client()
    if not inat_client.is_configured:
        raise HTTPException(
            status_code=409,
            detail="Connect iNaturalist in HikeJournal before publishing.",
        )
    return svc, records_by_group, inat_client, _user_context()


def _stored_media_image_loader(
    svc: Services,
    records: list[tuple[dict[str, Any], dict[str, Any]]],
) -> Callable[[str], bytes] | None:
    """Load publishing images inside the API instead of through a public URL."""
    storage = getattr(svc, "storage", None)
    if storage is None or not callable(getattr(storage, "download_file", None)):
        return None
    paths_by_url: dict[str, str] = {}
    for _observation, photo in records:
        public_url = str(photo.get("public_url") or "").strip()
        storage_path = str(photo.get("storage_path") or "").strip()
        if not public_url or not storage_path:
            return None
        paths_by_url[public_url] = storage_path

    def load(public_url: str) -> bytes:
        storage_path = paths_by_url.get(public_url)
        if not storage_path:
            raise InatRequestError("This field photo is no longer available for publishing.")
        image_bytes = storage.download_file(storage_path)
        if not image_bytes:
            raise RuntimeError("The field photo was empty.")
        if len(image_bytes) > MAX_PUBLISH_IMAGE_BYTES:
            raise RuntimeError("The field photo is too large to publish from HikeJournal.")
        return image_bytes

    return load


def _publish_batch_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in job.items()
        if key not in {
            "owner_context",
            "created_at",
            "client_request_id",
            MOBILE_JOB_CACHE_FINGERPRINT_KEY,
        }
    }


def _get_species_publish_batch_job(job_id: str) -> dict[str, Any]:
    record = _get_mobile_job(job_id, job_type=SPECIES_PUBLISH_JOB_TYPE)
    job = dict(record.payload) if record else {}
    if not job:
        with _species_publish_jobs_lock:
            job = dict(_species_publish_jobs.get(job_id) or {})
    if (
        not job
        or mobile_job_owner_key(job.get("owner_context") or {})
        != mobile_job_owner_key(_user_context())
    ):
        raise HTTPException(status_code=404, detail="iNaturalist publish batch not found.")
    return _publish_batch_job_payload(job)


def _update_species_publish_batch_job(job_id: str, **updates: Any) -> None:
    _persist_mobile_job_update(job_id, **updates)
    with _species_publish_jobs_lock:
        if job_id in _species_publish_jobs:
            _species_publish_jobs[job_id].update(updates)


def _run_species_publish_batch_job(
    job_id: str,
    svc: Services,
    records_by_group: list[list[tuple[dict[str, Any], dict[str, Any]]]],
    inat_client: InatClient,
    owner: dict[str, Any],
    *,
    description: str,
    tags: list[str],
    geoprivacy: str,
    captive: bool,
    lease_already_claimed: bool = False,
) -> None:
    global _species_data_cache
    if lease_already_claimed:
        if not _current_mobile_job_lease_owner():
            raise MobileJobLeaseLost(job_id)
    elif not _claim_mobile_job(job_id, job_type=SPECIES_PUBLISH_JOB_TYPE):
        return
    _update_species_publish_batch_job(job_id, state="running")
    processed_observation_ids: list[str] = []
    processed_photo_ids: list[str] = []
    errors: list[str] = []
    posted_group_count = 0
    failed_group_count = 0
    partial_group_count = 0
    processed_photo_count = 0
    attempted_group_count = 0
    try:
        hikes_by_id = _visible_hikes(svc.repository)
        for group_number, records in enumerate(records_by_group, start=1):
            attempted_group_count = group_number
            lead_observation, lead_photo = records[0]
            hike_id = str(lead_photo.get("hike_id") or lead_observation.get("hike_id") or "")
            hike = next((item for item in hikes_by_id if str(item.get("id") or "") == hike_id), None)
            _update_species_publish_batch_job(
                job_id,
                current_group=group_number,
                current_group_photo_count=len(records),
            )
            try:
                publish_options: dict[str, Any] = {}
                image_loader = _stored_media_image_loader(svc, records)
                if image_loader is not None:
                    publish_options["image_loader"] = image_loader
                posting = publish_observation_group(
                    svc.repository,
                    inat_client,
                    records,
                    place_guess=str((hike or {}).get("location_name") or "") or None,
                    owner_subject=owner.get("subject"),
                    owner_email=owner.get("email"),
                    description=description,
                    tags=tags,
                    geoprivacy=geoprivacy,
                    captive=captive,
                    **publish_options,
                )
            except (InatAuthError, InatConfigurationError, InatRequestError, RuntimeError) as exc:
                failed_group_count += 1
                errors.append(
                    f"{lead_observation.get('common_name') or lead_observation.get('scientific_name') or lead_observation.get('id')}: {exc}"
                )
            except Exception as exc:  # pragma: no cover - depends on remote service state
                failed_group_count += 1
                logger.exception("Mobile grouped iNaturalist publish failed")
                errors.append(
                    f"{lead_observation.get('common_name') or lead_observation.get('scientific_name') or lead_observation.get('id')}: HikeJournal could not finish this post."
                )
            else:
                posted_group_count += 1
                observation_ids = [str(observation.get("id") or "") for observation, _photo in records]
                photo_ids = [str(photo.get("id") or "") for _observation, photo in records]
                processed_observation_ids.extend(observation_ids)
                processed_photo_ids.extend(photo_ids)
                processed_photo_count += len(photo_ids)
                if posting.get("photo_attached") is False:
                    partial_group_count += 1
            _update_species_publish_batch_job(
                job_id,
                processed_group_count=group_number,
                posted_group_count=posted_group_count,
                failed_group_count=failed_group_count,
                partial_group_count=partial_group_count,
                processed_photo_count=processed_photo_count,
                processed_observation_ids=list(processed_observation_ids),
                processed_photo_ids=list(processed_photo_ids),
                errors=list(errors),
            )
        _species_data_cache = None
        _update_species_publish_batch_job(
            job_id,
            state="completed",
            current_group=len(records_by_group),
            current_group_photo_count=0,
            processed_group_count=len(records_by_group),
            posted_group_count=posted_group_count,
            failed_group_count=failed_group_count,
            partial_group_count=partial_group_count,
            processed_photo_count=processed_photo_count,
            processed_observation_ids=list(processed_observation_ids),
            processed_photo_ids=list(processed_photo_ids),
            errors=list(errors),
        )
    except MobileJobLeaseLost:
        logger.warning("Stopped stale iNaturalist publishing worker for job %s", job_id)
        return
    except Exception as exc:  # pragma: no cover - defensive background-job guard
        logger.exception("Mobile grouped iNaturalist publish batch failed")
        _update_species_publish_batch_job(
            job_id,
            state="failed",
            current_group_photo_count=0,
            error=str(exc),
            processed_group_count=attempted_group_count,
            processed_photo_count=processed_photo_count,
            processed_observation_ids=list(processed_observation_ids),
            processed_photo_ids=list(processed_photo_ids),
            errors=list(errors),
        )


@app.post("/v1/species/publish/batch/start", dependencies=[Depends(require_mobile_key)])
def start_species_publish_batch(
    payload: PublishBatchInput,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    owner_context = _user_context()
    if payload.client_request_id:
        persisted = _find_mobile_job_by_request(
            job_type=SPECIES_PUBLISH_JOB_TYPE,
            owner_context=owner_context,
            client_request_id=payload.client_request_id,
            request_payload=payload.model_dump(mode="json"),
        )
        if persisted:
            return _publish_batch_job_payload(persisted.payload)

        with _species_publish_jobs_lock:
            existing = next(
                (
                    existing
                    for existing in _species_publish_jobs.values()
                    if existing.get("owner_context") == owner_context
                    and existing.get("client_request_id") == payload.client_request_id
                ),
                None,
            )
            if existing:
                _validate_cached_mobile_job_request(
                    existing,
                    payload.model_dump(mode="json"),
                )
                # Fingerprinted cache entries were validated above. An older
                # entry with no hash remains reusable for local compatibility.
                return _publish_batch_job_payload(dict(existing))
    svc, records_by_group, inat_client, owner = _prepare_species_publish_batch(payload)
    job_id = str(uuid4())
    total_photos = sum(len(records) for records in records_by_group)
    job = {
        "job_id": job_id,
        "state": "queued",
        "total_groups": len(records_by_group),
        "processed_group_count": 0,
        "posted_group_count": 0,
        "failed_group_count": 0,
        "partial_group_count": 0,
        "total_photos": total_photos,
        "processed_photo_count": 0,
        "processed_observation_ids": [],
        "processed_photo_ids": [],
        "current_group": 0,
        "current_group_photo_count": 0,
        "errors": [],
        "error": None,
        "owner_context": owner,
        "client_request_id": payload.client_request_id,
    }
    persisted_job, created = _create_mobile_job(
        job_type=SPECIES_PUBLISH_JOB_TYPE,
        owner_context=owner_context,
        client_request_id=payload.client_request_id,
        job=job,
        request_payload=payload.model_dump(mode="json"),
    )
    if not created:
        return _publish_batch_job_payload(persisted_job.payload)
    job = persisted_job.payload
    with _species_publish_jobs_lock:
        finished_ids = [
            existing_id
            for existing_id, existing in _species_publish_jobs.items()
            if existing.get("state") in {"completed", "failed"}
        ]
        for existing_id in finished_ids[:-50]:
            _species_publish_jobs.pop(existing_id, None)
        cached_job = dict(job)
        if persisted_job.request_fingerprint:
            cached_job[MOBILE_JOB_CACHE_FINGERPRINT_KEY] = persisted_job.request_fingerprint
        _species_publish_jobs[job_id] = cached_job
    background_tasks.add_task(
        _run_species_publish_batch_job,
        job_id,
        svc,
        records_by_group,
        inat_client,
        owner,
        description=payload.description,
        tags=payload.tags,
        geoprivacy=payload.geoprivacy,
        captive=payload.captive,
    )
    return _publish_batch_job_payload(job)


@app.get("/v1/species/publish/batch/{job_id}", dependencies=[Depends(require_mobile_key)])
def get_species_publish_batch_status(job_id: str) -> dict[str, Any]:
    _dispatch_recoverable_mobile_jobs(job_id=job_id)
    return _get_species_publish_batch_job(job_id)


@app.post("/v1/species/publish/{observation_id}", dependencies=[Depends(require_mobile_key)])
def publish_species_observation(observation_id: str, payload: PublishInput) -> dict[str, Any]:
    global _species_data_cache
    if not payload.acknowledged_public:
        raise HTTPException(
            status_code=400,
            detail="Confirm that this observation will become public on iNaturalist.",
        )
    svc = get_services()
    visible_observations, photos_by_id, hikes_by_id = _visible_species_data(svc)
    requested_ids = list(dict.fromkeys([observation_id, *payload.observation_ids]))[:10]
    visible_by_id = {str(item.get("id") or ""): item for item in visible_observations}
    if any(requested_id not in visible_by_id for requested_id in requested_ids):
        raise HTTPException(status_code=404, detail="Confirmed observation not found.")
    full_rows = svc.repository.list_observations_by_ids(requested_ids)
    full_by_id = {
        str(item.get("id") or ""): item
        for item in full_rows
        if item.get("status") == "confirmed"
    }
    if any(requested_id not in full_by_id for requested_id in requested_ids):
        raise HTTPException(status_code=409, detail="Confirm this identification before publishing.")
    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for requested_id in requested_ids:
        requested_observation = full_by_id[requested_id]
        requested_photo = photos_by_id.get(str(requested_observation.get("photo_id") or ""))
        if requested_photo:
            records.append((requested_observation, requested_photo))
    if len(records) != len(requested_ids):
        raise HTTPException(status_code=404, detail="The observation photo could not be found.")
    inat_client = _mobile_inat_client()
    if not inat_client.is_configured:
        raise HTTPException(
            status_code=409,
            detail="Connect iNaturalist in HikeJournal before publishing.",
        )
    owner = _user_context()
    observation, photo = records[0]
    hike = hikes_by_id.get(str(photo.get("hike_id") or observation.get("hike_id") or ""))
    try:
        publish_options: dict[str, Any] = {}
        image_loader = _stored_media_image_loader(svc, records)
        if image_loader is not None:
            publish_options["image_loader"] = image_loader
        posting = publish_observation_group(
            svc.repository,
            inat_client,
            records,
            place_guess=str((hike or {}).get("location_name") or "") or None,
            owner_subject=owner.get("subject"),
            owner_email=owner.get("email"),
            description=payload.description,
            tags=payload.tags,
            geoprivacy=payload.geoprivacy,
            captive=payload.captive,
            **publish_options,
        )
    except InatAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except (InatConfigurationError, InatRequestError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Mobile iNaturalist publish failed")
        raise HTTPException(
            status_code=502,
            detail="HikeJournal could not finish this iNaturalist post. Please try again.",
        ) from exc

    _species_data_cache = None
    raw_payload = observation.get("raw_response_json")
    raw_payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
    updated = {
        **observation,
        "inat_observation_id": posting.get("observation_id"),
        "inat_observation_url": posting.get("observation_url"),
        "inat_posted_at": posting.get("posted_at"),
        "inat_photo_attached": posting.get("photo_attached"),
        "raw_response_json": {**raw_payload, "inat_posting": posting},
    }
    return _publish_item_payload(
        updated,
        photo,
        hike,
        source_hike_id=str(photo.get("hike_id") or observation.get("hike_id") or ""),
        related_observation_ids=requested_ids,
    )


@app.get("/v1/species/detail", dependencies=[Depends(require_mobile_key)])
def get_species_detail(key: str) -> dict[str, Any]:
    svc = get_services()
    observations, photos_by_id, hikes_by_id = _visible_species_data(svc)
    matching = _decorate_observation_history(
        svc.repository,
        [observation for observation in observations if _species_key(observation) == key],
    )
    summaries = _build_species_payloads(matching, photos_by_id, hikes_by_id)
    if not summaries:
        raise HTTPException(status_code=404, detail="Species not found.")
    summary_enrichment = {
        "wikipedia_url": str(summaries[0].get("wikipedia_url") or ""),
        "wikipedia_summary": str(summaries[0].get("wikipedia_summary") or ""),
    }

    observations_by_photo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in matching:
        if observation.get("photo_id"):
            observations_by_photo[str(observation["photo_id"])].append(observation)

    encounters: list[dict[str, Any]] = []
    for photo_id, photo_observations in observations_by_photo.items():
        photo = photos_by_id.get(photo_id)
        if not photo:
            continue
        hike = hikes_by_id.get(str(photo.get("hike_id") or ""))
        encounters.append(
            {
                # The Field Guide is organized by species rather than a single
                # observation.  Give every encounter the species' shared wiki
                # context, even when this particular photo predates enrichment.
                "photo": _photo_payload(
                    photo,
                    [
                        {
                            **observation,
                            "wikipedia_url": observation.get("wikipedia_url") or summary_enrichment["wikipedia_url"],
                            "wikipedia_summary": observation.get("wikipedia_summary") or summary_enrichment["wikipedia_summary"],
                        }
                        for observation in photo_observations
                    ],
                ),
                "hike_id": str((hike or {}).get("id") or "") or None,
                "hike_title": str((hike or {}).get("title") or "Everyday sighting"),
                "hike_date": str((hike or {}).get("hike_date") or ""),
                "location_name": str((hike or {}).get("location_name") or ""),
                "observed_on": _observed_on(photo, hike),
            }
        )
    encounters.sort(key=lambda item: str(item.get("observed_on") or ""), reverse=True)
    dated_matching = []
    for observation in matching:
        photo = photos_by_id.get(str(observation.get("photo_id") or ""), {})
        hike = hikes_by_id.get(str(photo.get("hike_id") or observation.get("hike_id") or ""))
        dated_matching.append(
            {**observation, "observed_on": observation.get("observed_on") or _observed_on(photo, hike)}
        )
    return {
        **summaries[0],
        "encounters": encounters,
        "seasonal_history": build_seasonal_history(dated_matching),
    }


@app.get("/v1/sightings", dependencies=[Depends(require_mobile_key)])
def list_sightings() -> list[dict[str, Any]]:
    svc = get_services()
    hikes = _visible_hikes(svc.repository)
    hikes_by_id = {str(hike["id"]): hike for hike in hikes}
    visible_hike_ids = set(hikes_by_id)
    context = _user_context()
    photos = [
        photo
        for photo in svc.repository.list_map_photos()
        if record_visible_for_user(photo, visible_hike_ids, context)
    ]
    observations, _, _ = _visible_species_data(svc)
    observations_by_photo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        if observation.get("photo_id"):
            observations_by_photo[str(observation["photo_id"])].append(observation)

    sightings: list[dict[str, Any]] = []
    for photo in photos:
        photo_observations = observations_by_photo.get(str(photo.get("id") or ""), [])
        primary = next(
            (observation for observation in photo_observations if observation.get("is_primary")),
            photo_observations[0] if photo_observations else None,
        )
        hike = hikes_by_id.get(str(photo.get("hike_id") or ""))
        sightings.append(
            {
                "id": str(photo.get("id") or ""),
                "hike_id": str((hike or {}).get("id") or "") or None,
                "hike_title": str((hike or {}).get("title") or "Everyday sighting"),
                "hike_date": str((hike or {}).get("hike_date") or ""),
                "location_name": str((hike or {}).get("location_name") or ""),
                "url": str(photo.get("public_url") or ""),
                "caption": str(photo.get("caption") or ""),
                "taken_at": photo.get("taken_at"),
                "lat": photo.get("lat"),
                "lng": photo.get("lng"),
                "species_name": str(
                    (primary or {}).get("common_name")
                    or (primary or {}).get("scientific_name")
                    or ""
                ),
                "scientific_name": str((primary or {}).get("scientific_name") or ""),
                "confirmed": bool(photo_observations),
            }
        )
    return sorted(
        sightings,
        key=lambda item: str(item.get("taken_at") or item.get("hike_date") or ""),
        reverse=True,
    )


@app.get("/v1/routes", dependencies=[Depends(require_mobile_key)])
def list_map_routes() -> list[dict[str, Any]]:
    """Return the visible hike tracks for the all-sightings map."""
    svc = get_services()
    route_imports_by_hike: dict[str, dict[str, Any]] = {}
    for route_import in svc.repository.list_hike_route_imports():
        hike_id = str(route_import.get("hike_id") or "")
        if hike_id:
            # Imports are newest-first, so preserve the first record if legacy data
            # contains more than one row for an outing.
            route_imports_by_hike.setdefault(hike_id, route_import)
    return [
        {
            "hike_id": str(hike["id"]),
            "route_segments": route_import_to_route_groups(
                route_imports_by_hike.get(str(hike["id"]))
            ),
        }
        for hike in _visible_hikes(svc.repository)
    ]


@app.get("/v1/hikes/{hike_id}", dependencies=[Depends(require_mobile_key)])
def get_hike(
    hike_id: str,
    include_photos: bool = True,
    include_route: bool = True,
) -> dict[str, Any]:
    svc = get_services()
    if hike_id == EVERYDAY_JOURNAL_ID:
        return _standalone_hike_payload(svc, include_details=True)
    hike = _get_visible_hike(svc.repository, hike_id)
    if not include_photos:
        # The Android client loads photos separately in small pages. Do not scan
        # the complete photo/observation history just to render this header. Resolve
        # an explicitly selected cover directly so pagination can never substitute a
        # different photo while the journal is opening.
        cover_id = str(hike.get("cover_photo_id") or "")
        selected_cover = next(
            (
                photo
                for photo in svc.repository.list_photo_records_for_ids([cover_id])
                if str(photo.get("hike_id") or "") == hike_id
            ),
            None,
        ) if cover_id else None
        payload = _hike_payload(hike, photos=[], cover_photo=selected_cover)
        if include_route:
            payload["route_segments"] = route_import_to_route_groups(
                svc.repository.get_hike_route_import(hike_id)
            )
        payload["field_marks"] = _field_mark_payloads(svc.repository, hike_id)
        payload["weather"] = _weather_payload(svc.repository, hike_id)
        return payload
    photos = svc.repository.list_photos(hike_id)
    observations = _decorate_observation_history(
        svc.repository,
        svc.repository.list_observations(hike_id),
    )
    observations_by_photo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    confirmed_species: set[str] = set()
    for observation in observations:
        if observation.get("photo_id"):
            observations_by_photo[str(observation["photo_id"])].append(observation)
        if observation.get("status") == "confirmed":
            confirmed_species.add(_species_key(observation))
    payload = _hike_payload(hike, photos=photos, species_count=len(confirmed_species))
    if include_photos:
        payload["photos"] = [
            _photo_payload(photo, observations_by_photo.get(str(photo.get("id")), []))
            for photo in photos
        ]
    if include_route:
        payload["route_segments"] = route_import_to_route_groups(
            svc.repository.get_hike_route_import(hike_id)
        )
    payload["field_marks"] = _field_mark_payloads(svc.repository, hike_id)
    payload["weather"] = _weather_payload(svc.repository, hike_id)
    return payload


@app.get("/v1/hikes/{hike_id}/photos", dependencies=[Depends(require_mobile_key)])
def get_hike_photos(
    hike_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    """Return a bounded page so photo-heavy hikes do not exceed proxy response limits."""
    svc = get_services()
    if hike_id == EVERYDAY_JOURNAL_ID:
        page = _visible_standalone_photos(svc)[offset : offset + limit]
    else:
        _get_visible_hike(svc.repository, hike_id)
        page = svc.repository.list_photos_page(hike_id, offset=offset, limit=limit)
    observations_by_photo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    page_observations = _decorate_observation_history(
        svc.repository,
        svc.repository.list_observations_for_photo_ids(
            [str(photo.get("id") or "") for photo in page]
        ),
    )
    for observation in page_observations:
        if observation.get("photo_id"):
            observations_by_photo[str(observation["photo_id"])].append(observation)
    next_offset = offset + len(page)
    return {
        "photos": [
            _photo_payload(photo, observations_by_photo.get(str(photo.get("id")), []))
            for photo in page
        ],
        "next_offset": next_offset if len(page) == limit else None,
    }


@app.get("/v1/hikes/{hike_id}/route", dependencies=[Depends(require_mobile_key)])
def get_hike_route(hike_id: str) -> dict[str, Any]:
    if hike_id == EVERYDAY_JOURNAL_ID:
        route_import = None
    else:
        svc = get_services()
        _get_visible_hike(svc.repository, hike_id)
        route_import = svc.repository.get_hike_route_import(hike_id)
    route_import = route_import or {}
    return {
        "route_segments": route_import_to_route_groups(route_import),
        "started_at": route_import.get("started_at"),
        "duration_seconds": route_import.get("duration_seconds"),
        "distance_miles": route_import.get("distance_miles"),
        "track_point_count": route_import.get("track_point_count") or 0,
    }


@app.get("/v1/hikes/{hike_id}/comparison", dependencies=[Depends(require_mobile_key)])
def compare_hikes(
    hike_id: str,
    other_hike_id: str = Query(min_length=36, max_length=36),
) -> dict[str, Any]:
    svc = get_services()
    hike_a = _get_visible_hike(svc.repository, hike_id)
    hike_b = _get_visible_hike(svc.repository, other_hike_id)
    observations = _dated_visible_observations(svc)
    route_by_hike = {
        str(item.get("hike_id") or ""): item
        for item in svc.repository.list_hike_route_imports()
        if str(item.get("hike_id") or "") in {hike_id, other_hike_id}
    }
    for hike in (hike_a, hike_b):
        route = route_by_hike.get(str(hike.get("id") or ""), {})
        hike["duration_seconds"] = route.get("duration_seconds")
        hike["photo_count"] = len(svc.repository.list_photos(str(hike.get("id") or "")))
    comparison = build_hike_comparison(hike_a, hike_b, observations)
    comparison["weather"] = {
        "hike_a": _weather_payload(svc.repository, hike_id),
        "hike_b": _weather_payload(svc.repository, other_hike_id),
    }
    return comparison


@app.post(
    "/v1/hikes/{hike_id}/field-marks",
    dependencies=[Depends(require_mobile_key)],
    status_code=201,
)
def create_field_mark(hike_id: str, payload: FieldMarkInput) -> dict[str, Any]:
    svc = get_services()
    hike = _get_visible_hike(svc.repository, hike_id)
    mark_id = _normalize_client_uuid(payload.id, field_name="Field mark ID")
    session_id = _normalize_client_uuid(payload.recording_session_id, field_name="Recording session ID")
    try:
        existing = svc.repository.get_field_mark(str(mark_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if existing and str(existing.get("hike_id") or "") != hike_id:
        raise HTTPException(status_code=409, detail="That Field Mark ID belongs to another hike.")
    context = _user_context()
    try:
        saved = svc.repository.upsert_field_mark(
            {
                "id": mark_id,
                "hike_id": hike_id,
                "recording_session_id": session_id,
                "owner_subject": hike.get("owner_subject") or context.get("subject"),
                "owner_email": hike.get("owner_email") or context.get("email"),
                "marked_at": payload.marked_at.isoformat(),
                "lat": payload.lat,
                "lng": payload.lng,
                "accuracy_meters": payload.accuracy_meters,
                "mark_type": payload.mark_type,
                "note": payload.note.strip() or None,
            }
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _field_mark_payload(saved)


@app.put(
    "/v1/observations/{observation_id}/natural-history",
    dependencies=[Depends(require_mobile_key)],
)
def update_observation_natural_history(
    observation_id: str,
    payload: ObservationNaturalHistoryInput,
) -> dict[str, Any]:
    svc = get_services()
    matches = svc.repository.list_observations_by_ids([observation_id])
    if not matches:
        raise HTTPException(status_code=404, detail="Observation not found.")
    observation = matches[0]
    visible_hike_ids = {str(hike.get("id") or "") for hike in _visible_hikes(svc.repository)}
    if not record_visible_for_user(observation, visible_hike_ids, _user_context()):
        raise HTTPException(status_code=404, detail="Observation not found.")
    try:
        updated = svc.repository.set_observation_natural_history(
            observation_id,
            confidence=payload.confidence,
            provenance=payload.provenance,
            phenophases=[item.model_dump() for item in payload.phenophases],
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _decorate_observation_history(svc.repository, [updated])[0]


def _sync_hike_location_tags(
    repository: HikeJournalRepository,
    hike: dict[str, Any],
    payload: HikeInput,
) -> None:
    locations = _visible_hike_locations(repository)
    canonical_ids = canonical_location_id_map(locations)
    location_ids = (
        [canonical_ids[payload.location_id]]
        if payload.location_id and payload.location_id in canonical_ids
        else suggest_location_ids_for_hike(hike, locations)
    )
    repository.set_hike_location_tags(str(hike["id"]), location_ids)


@app.post("/v1/hikes", dependencies=[Depends(require_mobile_key)], status_code=201)
def create_hike(payload: HikeInput) -> dict[str, Any]:
    svc = get_services()
    client_hike_id = _normalize_client_uuid(payload.id, field_name="Hike ID")
    if client_hike_id:
        existing = next(
            (hike for hike in _visible_hikes(svc.repository) if str(hike.get("id") or "") == client_hike_id),
            None,
        )
        if existing:
            _sync_hike_location_tags(svc.repository, existing, payload)
            return _hike_payload(existing, photos=svc.repository.list_photos(client_hike_id))
    owner = _user_context()
    created = svc.repository.create_hike(
        HikeDraft(
            title=payload.title,
            hike_date=payload.hike_date,
            distance_miles=payload.distance_miles,
            location_name=payload.location_name,
            notes=payload.notes,
            owner_subject=owner.get("subject"),
            owner_email=owner.get("email"),
            owner_user_id=owner.get("user_id"),
        ),
        hike_id=client_hike_id,
    )
    _sync_hike_location_tags(svc.repository, created, payload)
    _invalidate_species_data_cache()
    return _hike_payload(created, photos=[])


@app.put("/v1/hikes/{hike_id}", dependencies=[Depends(require_mobile_key)])
def update_hike(hike_id: str, payload: HikeInput) -> dict[str, Any]:
    svc = get_services()
    _get_visible_hike(svc.repository, hike_id)
    updated = svc.repository.update_hike(
        hike_id,
        title=payload.title,
        hike_date=payload.hike_date,
        distance_miles=payload.distance_miles,
        location_name=payload.location_name,
        notes=payload.notes,
    )
    _sync_hike_location_tags(svc.repository, updated, payload)
    _invalidate_species_data_cache()
    return _hike_payload(updated, photos=svc.repository.list_photos(hike_id))


@app.post("/v1/hikes/{hike_id}/route", dependencies=[Depends(require_mobile_key)], status_code=201)
async def upload_hike_route(
    hike_id: str,
    file: Annotated[UploadFile, File()],
    source_type: Annotated[
        Literal["hikejournal_android_gps", "hikejournal_ios_gps"] | None,
        Form(),
    ] = None,
) -> dict[str, Any]:
    """Save a TCX track for a hike so the native map can render its route."""
    svc = get_services()
    hike = _get_visible_hike(svc.repository, hike_id)
    filename = (file.filename or "route.tcx").strip() or "route.tcx"
    if not filename.lower().endswith((".tcx", ".tcx.txt", ".xml")):
        raise HTTPException(status_code=400, detail="Choose a TCX file.")
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="TCX files must be 30 MB or smaller.")
    route_file = SimpleNamespace(name=filename, getvalue=lambda: contents)
    route_import, error = sync_hike_route_import(
        repository=svc.repository,
        storage=svc.storage,
        hike_id=hike_id,
        uploaded_file=route_file,
        existing_route_import=svc.repository.get_hike_route_import(hike_id),
        remove_existing=False,
        source_type=source_type,
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    try:
        await asyncio.to_thread(_enrich_weather_for_hike, svc, hike)
    except Exception as exc:
        # Route persistence is the completion boundary. Weather is best-effort
        # enrichment and can always be retried from the Journal.
        logger.info("weather_enrichment hike_id=%s deferred=%s", hike_id, exc)
    return {
        "route_segments": route_import_to_route_groups(route_import),
        "track_point_count": (route_import or {}).get("track_point_count", 0),
    }


@app.post("/v1/hikes/{hike_id}/weather", dependencies=[Depends(require_mobile_key)])
async def enrich_hike_weather_endpoint(
    hike_id: str,
    force: bool = Query(default=False),
) -> dict[str, Any]:
    svc = get_services()
    hike = _get_visible_hike(svc.repository, hike_id)
    try:
        return await asyncio.to_thread(_enrich_weather_for_hike, svc, hike, force=force)
    except WeatherProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.put("/v1/hikes/{hike_id}/archive", dependencies=[Depends(require_mobile_key)])
def update_archive(hike_id: str, payload: ArchiveInput) -> dict[str, Any]:
    svc = get_services()
    _get_visible_hike(svc.repository, hike_id)
    updated = svc.repository.update_hike_archive(hike_id, payload.is_archived)
    _invalidate_species_data_cache()
    return _hike_payload(updated, photos=svc.repository.list_photos(hike_id))


@app.delete("/v1/hikes/{hike_id}", dependencies=[Depends(require_mobile_key)])
def delete_hike(hike_id: str) -> dict[str, Any]:
    """Permanently remove an owned hike and every asset stored with it."""
    if hike_id == EVERYDAY_JOURNAL_ID:
        raise HTTPException(status_code=409, detail="Everyday sightings is a permanent journal and cannot be deleted.")

    svc = get_services()
    hike = next(
        (row for row in svc.repository.list_hikes() if str(row.get("id") or "") == hike_id),
        None,
    )
    # Treat missing and non-owned hikes alike. This prevents ownership disclosure and
    # makes a retry after a successful deletion safe.
    if not hike or not user_owns_record(hike, _user_context()):
        return {"deleted": True, "id": hike_id}

    try:
        delete_hike_and_assets(svc.repository, svc.storage, hike_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _invalidate_species_data_cache()
    return {"deleted": True, "id": hike_id}


@app.put("/v1/hikes/{hike_id}/cover", dependencies=[Depends(require_mobile_key)])
def update_hike_cover(hike_id: str, payload: CoverPhotoInput) -> dict[str, Any]:
    svc = get_services()
    _get_visible_hike(svc.repository, hike_id)
    photo_id = _normalize_client_uuid(payload.photo_id, field_name="Cover photo ID")
    if photo_id:
        _, photo = _get_visible_photo(photo_id)
        if str(photo.get("hike_id") or "") != hike_id:
            raise HTTPException(status_code=409, detail="Choose a cover photo from this hike.")
        if str(photo.get("content_type") or "").lower().startswith("video/"):
            raise HTTPException(status_code=409, detail="Choose a photo for the hike cover.")
    updated = svc.repository.update_hike_cover_photo(hike_id, photo_id)
    _invalidate_species_data_cache()
    return _hike_payload(updated, photos=svc.repository.list_photos(hike_id))


@app.post("/v1/hikes/{hike_id}/photos", dependencies=[Depends(require_mobile_key)], status_code=201)
async def upload_photo(
    hike_id: str,
    file: Annotated[UploadFile, File()],
    caption: Annotated[str, Form()] = "",
    queue_for_review: Annotated[bool, Form()] = False,
    photo_id: Annotated[str, Form()] = "",
    taken_at: Annotated[str, Form()] = "",
    lat: Annotated[float | None, Form()] = None,
    lng: Annotated[float | None, Form()] = None,
) -> dict[str, Any]:
    svc = get_services()
    is_standalone = hike_id == EVERYDAY_JOURNAL_ID
    if not is_standalone:
        _get_visible_hike(svc.repository, hike_id)
    normalized_photo_id = _normalize_client_uuid(photo_id.strip() or None, field_name="Photo ID") or ""
    if normalized_photo_id:
        existing = (
            svc.client.table("photos")
            .select("*")
            .eq("id", normalized_photo_id)
            .limit(1)
            .execute()
        ).data or []
        existing = svc.repository.decorate_media_rows(existing)
        if existing:
            existing_scope = str(existing[0].get("hike_id") or EVERYDAY_JOURNAL_ID)
            if existing_scope != hike_id or (
                is_standalone and not user_owns_record(existing[0], _user_context())
            ):
                raise HTTPException(status_code=409, detail="This photo ID belongs to another hike.")
            return _photo_payload(existing[0])
    original = await file.read(MAX_UPLOAD_BYTES + 1)
    if not original:
        raise HTTPException(status_code=400, detail="The selected photo was empty.")
    if len(original) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Photos and videos must be 30 MB or smaller.")
    picker_taken_at = _parse_picker_taken_at(taken_at)
    picker_lat = _validate_picker_coordinate(lat, minimum=-90, maximum=90, label="latitude")
    picker_lng = _validate_picker_coordinate(lng, minimum=-180, maximum=180, label="longitude")
    is_video = is_supported_video_upload(file.filename or "", file.content_type)
    if is_video:
        content_type = video_content_type(file.filename or "", file.content_type)
        metadata = None
        processed = None
    else:
        try:
            metadata = extract_metadata(original)
            processed = optimize_image(original)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="This image could not be processed.") from exc

    storage_path = ""
    try:
        if is_video:
            storage_path, public_url = svc.storage.upload_hike_video(
                hike_id,
                original,
                content_type,
                filename=file.filename or "hike-video.mp4",
                object_id=normalized_photo_id or None,
            )
        elif is_standalone:
            storage_path, public_url = svc.storage.upload_standalone_photo(
                processed.bytes_data,
                processed.content_type,
                object_id=normalized_photo_id or None,
            )
        else:
            storage_path, public_url = svc.storage.upload_hike_photo(
                hike_id, processed.bytes_data, processed.content_type, object_id=normalized_photo_id or None
            )
        owner = _user_context()
        effective_taken_at = metadata.taken_at if metadata and metadata.taken_at else picker_taken_at
        effective_lat = metadata.lat if metadata and metadata.lat is not None else picker_lat
        effective_lng = metadata.lng if metadata and metadata.lng is not None else picker_lng
        exif_json = dict(metadata.exif_json) if metadata else {}
        if picker_taken_at and not exif_json.get("datetime_original"):
            exif_json["picker_taken_at"] = picker_taken_at.isoformat()
        if picker_lat is not None and exif_json.get("gps_latitude") is None:
            exif_json["gps_latitude"] = picker_lat
        if picker_lng is not None and exif_json.get("gps_longitude") is None:
            exif_json["gps_longitude"] = picker_lng
        created = svc.repository.create_photo(
            {
                **({"id": normalized_photo_id} if normalized_photo_id else {}),
                "hike_id": None if is_standalone else hike_id,
                "owner_user_id": owner.get("user_id"),
                "owner_subject": owner.get("subject"),
                "owner_email": owner.get("email"),
                "storage_path": storage_path,
                "public_url": public_url,
                "caption": caption.strip() or None,
                "taken_at": effective_taken_at.isoformat() if effective_taken_at else None,
                "lat": effective_lat,
                "lng": effective_lng,
                "width": processed.width if processed else None,
                "height": processed.height if processed else None,
                "file_size": len(processed.bytes_data) if processed else len(original),
                "content_type": processed.content_type if processed else content_type,
                "processing_status": "in_review" if queue_for_review and not is_video else "ready",
                "exif_json": exif_json,
            }
        )
    except Exception:
        if storage_path:
            try:
                svc.storage.delete_file(storage_path)
            except Exception:
                pass
        raise
    _invalidate_species_data_cache()
    return _photo_payload(created)


def _get_visible_photo(photo_id: str) -> tuple[Services, dict[str, Any]]:
    svc = get_services()
    response = svc.client.table("photos").select("*").eq("id", photo_id).limit(1).execute()
    rows = response.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Photo not found.")
    photo = svc.repository.decorate_media_row(rows[0])
    if photo.get("hike_id"):
        _get_visible_hike(svc.repository, str(photo["hike_id"]))
    elif not user_owns_record(photo, _user_context()):
        raise HTTPException(status_code=404, detail="Photo not found.")
    return svc, photo


def _matches_known_species(observation: dict[str, Any], species: KnownSpeciesInput) -> bool:
    if species.taxon_id is not None:
        return observation.get("taxon_id") == species.taxon_id
    scientific_name = species.scientific_name.strip().casefold()
    common_name = species.common_name.strip().casefold()
    return bool(
        (scientific_name and str(observation.get("scientific_name") or "").strip().casefold() == scientific_name)
        or (common_name and str(observation.get("common_name") or "").strip().casefold() == common_name)
    )


@app.put("/v1/photos/{photo_id}/species", dependencies=[Depends(require_mobile_key)])
def assign_known_species_to_photo(photo_id: str, payload: KnownSpeciesInput) -> dict[str, Any]:
    svc, photo = _get_visible_photo(photo_id)
    if str(photo.get("content_type") or "").lower().startswith("video/"):
        raise HTTPException(status_code=409, detail="Videos cannot be assigned a species.")
    if payload.taxon_id is None and not payload.common_name.strip() and not payload.scientific_name.strip():
        raise HTTPException(status_code=400, detail="Choose a known species.")

    existing = svc.repository.list_observations_for_photo_ids([photo_id])
    primary = next((observation for observation in existing if observation.get("is_primary")), None)
    if primary is not None:
        if primary.get("status") == "confirmed" and _matches_known_species(primary, payload):
            svc.repository.update_photo_processing_status(photo_id, "ready")
            return _photo_payload(photo, existing)
        raise HTTPException(status_code=409, detail="This photo already has a primary species.")

    confirmed_observations, _, _ = _visible_species_data(svc)
    known_species = next(
        (observation for observation in confirmed_observations if _matches_known_species(observation, payload)),
        None,
    )
    if known_species is None:
        raise HTTPException(status_code=404, detail="That species is no longer available in your Field Guide.")

    source_observation_id = str(known_species.get("id") or "")
    source_rows = svc.repository.list_observations_by_ids([source_observation_id]) if source_observation_id else []
    source_raw_payload = dict(source_rows[0].get("raw_response_json") or {}) if source_rows else {}
    taxon_enrichment = source_raw_payload.get("taxon_enrichment")
    raw_payload = {
        "known_species_assignment": {
            "source_observation_id": source_observation_id or None,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        },
        **({"taxon_enrichment": taxon_enrichment} if isinstance(taxon_enrichment, dict) else {}),
    }
    created = svc.repository.create_manual_observation(
        hike_id=photo.get("hike_id"),
        photo_id=photo_id,
        taxon_id=known_species.get("taxon_id"),
        common_name=str(known_species.get("common_name") or payload.common_name or ""),
        scientific_name=str(known_species.get("scientific_name") or payload.scientific_name or ""),
        source="known_species",
        raw_payload=raw_payload,
        is_primary=True,
        status="confirmed",
        owner_subject=photo.get("owner_subject"),
        owner_email=photo.get("owner_email"),
    )
    if not str((taxon_enrichment or {}).get("wikipedia_summary") or "").strip():
        try:
            ensure_observation_taxonomy(svc.repository, _mobile_inat_client(), created)
        except (InatConfigurationError, InatRequestError):
            # A known-species assignment remains useful if an optional enrichment lookup fails.
            pass
    svc.repository.update_photo_processing_status(photo_id, "ready")
    _invalidate_species_data_cache()
    refreshed = svc.repository.list_observations_by_ids([str(created["id"])])
    return _photo_payload(photo, refreshed or [created])


@app.put("/v1/photos/{photo_id}/review", dependencies=[Depends(require_mobile_key)])
def set_photo_species_review(photo_id: str, payload: ReviewQueueInput) -> dict[str, bool]:
    svc, photo = _get_visible_photo(photo_id)
    if payload.queued and str(photo.get("content_type") or "").lower().startswith("video/"):
        raise HTTPException(status_code=409, detail="Videos cannot be added to species review.")
    svc.repository.update_photo_processing_status(photo_id, "in_review" if payload.queued else "ready")
    _invalidate_species_data_cache()
    return {"queued": payload.queued}


@app.post("/v1/photos/{photo_id}/review", dependencies=[Depends(require_mobile_key)])
def queue_photo_for_species_review(photo_id: str) -> dict[str, bool]:
    """Keep older Android builds compatible with the original queue-only action."""
    return set_photo_species_review(photo_id, ReviewQueueInput(queued=True))


@app.put("/v1/photos/{photo_id}/caption", dependencies=[Depends(require_mobile_key)])
def update_photo_caption(photo_id: str, payload: CaptionInput) -> dict[str, Any]:
    svc, _ = _get_visible_photo(photo_id)
    updated = svc.repository.update_photo_caption(photo_id, payload.caption)
    _invalidate_species_data_cache()
    return _photo_payload(updated)


@app.delete("/v1/photos/{photo_id}", dependencies=[Depends(require_mobile_key)])
def delete_photo(photo_id: str) -> dict[str, bool]:
    try:
        svc, photo = _get_visible_photo(photo_id)
    except HTTPException as exc:
        # Missing and non-visible resources remain indistinguishable, while a
        # retry after a committed delete returns the original logical success.
        if exc.status_code == 404:
            return {"deleted": True}
        raise
    storage_path = str(photo.get("storage_path") or "")
    if storage_path:
        try:
            svc.storage.delete_file(storage_path)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="The photo is still in your journal because its stored file could not be removed.",
            ) from exc
    svc.repository.delete_photo(photo_id)
    _invalidate_species_data_cache()
    return {"deleted": True}
