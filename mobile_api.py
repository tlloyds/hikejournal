from __future__ import annotations

from collections import defaultdict
import base64
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
import hashlib
import hmac
import logging
import json
import math
import os
import time
from threading import Lock
from typing import Any, Annotated, Callable, Literal
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from supabase import Client, create_client

from hike_journal.config import settings
from hike_journal.domain.discovery import (
    DISCOVERY_ALGORITHM_VERSION,
    normalize_discovery_limit,
    normalize_radius,
    plain_text,
)
from hike_journal.domain.library import filter_hikes_for_user, record_visible_for_user, user_owns_record
from hike_journal.domain.locations import suggest_location_ids_for_hike
from hike_journal.domain.routes import (
    delete_hike_and_assets,
    route_import_to_route_groups,
    sync_hike_route_import,
)
from hike_journal.models import HikeDraft, SpeciesCandidate
from hike_journal.services.exif import extract_metadata
from hike_journal.services.image_processing import optimize_image
from hike_journal.media import is_supported_video_upload, video_content_type
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
    get_inat_posting,
    get_publish_state,
    publish_observation_group,
    publish_single_observation,
)
from hike_journal.services.encounters import build_publish_encounter_plan
from hike_journal.services.species_identification import select_shared_candidate
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.discovery import SpeciesDiscoveryService
from hike_journal.services.storage import StorageService
from hike_journal.services.taxonomy import ensure_observation_taxonomy


MAX_UPLOAD_BYTES = 30 * 1024 * 1024
EVERYDAY_JOURNAL_ID = "everyday"
MOBILE_API_VERSION = "0.6.21"
logger = logging.getLogger(__name__)


def _parse_picker_taken_at(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
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
    iconic_taxon: str | None = Field(default=None, max_length=40)
    title: str = Field(default="", max_length=160)
    linked_hike_id: str | None = Field(default=None, max_length=36)
    result_limit: Literal[50, 100] = 50


class SpeciesQuestPatchInput(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    status: Literal["active", "archived"] | None = None
    linked_hike_id: str | None = Field(default=None, max_length=36)
    set_linked_hike: bool = False
    focus_taxon_ids: list[int] | None = Field(default=None, min_length=1, max_length=10)


class Services:
    def __init__(self) -> None:
        if not settings.supabase_configured:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required.")
        self.client: Client = create_client(settings.supabase_url, settings.supabase_key)
        self.repository = HikeJournalRepository(self.client)
        self.storage = StorageService(self.client)


services: Services | None = None
_species_data_cache: tuple[
    float,
    tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]],
] | None = None
_species_batch_jobs: dict[str, dict[str, Any]] = {}
_species_batch_jobs_lock = Lock()
_species_publish_jobs: dict[str, dict[str, Any]] = {}
_species_publish_jobs_lock = Lock()


def _invalidate_species_data_cache() -> None:
    global _species_data_cache
    _species_data_cache = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global services
    services = Services()
    yield
    services = None


app = FastAPI(
    title="HikeJournal Mobile Companion API",
    version=MOBILE_API_VERSION,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


def require_mobile_key(
    x_hikejournal_key: Annotated[str | None, Header()] = None,
) -> None:
    expected = derive_mobile_api_token()
    if not expected or not x_hikejournal_key or not hmac.compare_digest(expected, x_hikejournal_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Pairing key is missing or invalid.")


def get_services() -> Services:
    if services is None:
        raise HTTPException(status_code=503, detail="Mobile services are starting.")
    return services


def _user_context() -> dict[str, Any]:
    email = mobile_owner_email()
    if not email:
        return {"mode": "local-dev", "email": None, "subject": None, "auth_configured": False}
    return {
        "mode": "google",
        "email": email,
        "subject": os.getenv("MOBILE_OWNER_SUBJECT", "").strip() or None,
        "auth_configured": True,
    }


def _visible_hikes(repository: HikeJournalRepository) -> list[dict[str, Any]]:
    return filter_hikes_for_user(repository.list_hikes(), _user_context())


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
    subject = str(context.get("subject") or "")
    email = str(context.get("email") or "").strip().lower()
    return bool(
        (subject and subject == str(quest.get("owner_subject") or ""))
        or (email and email == str(quest.get("owner_email") or "").strip().lower())
    )


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
) -> dict[str, Any]:
    cover_id = str(hike.get("cover_photo_id") or "")
    cover = next((photo for photo in photos if str(photo.get("id")) == cover_id), None)
    if cover is None and photos:
        cover = max(
            photos,
            key=lambda photo: (
                str(photo.get("taken_at") or ""),
                str(photo.get("created_at") or ""),
            ),
        )
    return {
        "id": str(hike.get("id") or ""),
        "title": str(hike.get("title") or "Untitled hike"),
        "hike_date": str(hike.get("hike_date") or ""),
        "distance_miles": hike.get("distance_miles"),
        "location_name": str(hike.get("location_name") or ""),
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


def _visible_species_data(
    svc: Services,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    global _species_data_cache
    if _species_data_cache and time.monotonic() - _species_data_cache[0] < 90:
        return _species_data_cache[1]
    hikes = _visible_hikes(svc.repository)
    hikes_by_id = {str(hike["id"]): hike for hike in hikes}
    visible_hike_ids = set(hikes_by_id)
    context = _user_context()
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
    _species_data_cache = (time.monotonic(), result)
    return result


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
) -> dict[str, Any]:
    return {
        "taxon_id": taxon_id,
        "common_name": common_name or scientific_name or "Unknown species",
        "scientific_name": scientific_name,
        "confidence": confidence,
    }


def _review_candidates(observation: dict[str, Any]) -> list[dict[str, Any]]:
    current = _candidate_payload(
        taxon_id=observation.get("taxon_id"),
        common_name=str(observation.get("common_name") or ""),
        scientific_name=str(observation.get("scientific_name") or ""),
        confidence=observation.get("confidence"),
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
            _save_mobile_inat_oauth_token(get_services(), email=email, token_payload=refreshed)
            mobile_token = fetch_api_token_for_oauth_access_token(str(refreshed.get("access_token") or ""))
    # Older Android builds saved the short-lived OAuth token directly. The v1
    # write API needs the JWT returned by /users/api_token; reads can still
    # succeed with the OAuth token, which made this look connected until post.
    if mobile_token and mobile_token.count(".") != 2:
        mobile_token = fetch_api_token_for_oauth_access_token(mobile_token)
        if email:
            _save_mobile_inat_token(get_services(), email=email, access_token=mobile_token)
    access_token = mobile_token or resolve_access_token_for_user(
        subject=owner.get("subject"),
        email=email,
    ) or settings.inat_access_token
    return InatClient(access_token=access_token, base_url=settings.inat_base_url)


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
        except (InatConfigurationError, InatAuthError):
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
    return hashlib.sha256(f"{derive_mobile_api_token()}:inat-token-v1".encode()).hexdigest()


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


def _mobile_oauth_redirect_uri() -> str:
    configured = os.getenv("MOBILE_INAT_OAUTH_REDIRECT_URI", "").strip()
    if configured:
        return configured
    public_url = os.getenv("MOBILE_PUBLIC_URL", "").strip().rstrip("/")
    return f"{public_url}/v1/inat/oauth/callback" if public_url else ""


def _mobile_oauth_state(email: str) -> str:
    payload = base64.urlsafe_b64encode(
        f"{email.lower()}|{int(time.time()) + 600}".encode()
    ).decode().rstrip("=")
    signature = hmac.new(derive_mobile_api_token().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"hj-mobile.{payload}.{signature}"


def _verify_mobile_oauth_state(state: str) -> str | None:
    parts = state.split(".")
    if len(parts) != 3 or parts[0] != "hj-mobile":
        return None
    payload, signature = parts[1], parts[2]
    expected = hmac.new(derive_mobile_api_token().encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
        email, expires_at = decoded.rsplit("|", 1)
        if int(expires_at) < int(time.time()) or not email:
            return None
        return email.lower()
    except (ValueError, UnicodeDecodeError):
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
        "connected": _mobile_inat_client().is_configured,
        "counts": counts,
        "items": items,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "hikejournal-mobile", "version": MOBILE_API_VERSION}


@app.get("/v1/config", dependencies=[Depends(require_mobile_key)])
def app_config() -> dict[str, Any]:
    return {
        "web_url": os.getenv("MOBILE_WEB_URL", "http://192.168.0.157:8505").rstrip("/"),
        "api_version": MOBILE_API_VERSION,
        "capabilities": [
            "offline_sync",
            "grouped_inat_publish",
            "map_packs",
            "live_inat_cv",
            "grouped_species_review",
            "mobile_inat_oauth",
            "species_discovery",
            "everyday_sightings",
            "hike_covers",
            "hike_deletion",
            "reversible_species_review",
        ],
    }


@app.get("/v1/inat/oauth/start", dependencies=[Depends(require_mobile_key)])
def start_mobile_inat_oauth() -> dict[str, str]:
    owner = _user_context()
    email = str(owner.get("email") or "").strip().lower()
    redirect_uri = _mobile_oauth_redirect_uri()
    if not email:
        raise HTTPException(status_code=409, detail="Set MOBILE_OWNER_EMAIL before connecting iNaturalist on Android.")
    if not settings.inat_oauth_configured:
        raise HTTPException(status_code=409, detail="Configure the iNaturalist OAuth client ID and secret on the mobile companion service.")
    if not redirect_uri:
        raise HTTPException(status_code=409, detail="Configure MOBILE_INAT_OAUTH_REDIRECT_URI for the mobile companion service.")
    try:
        return {"authorize_url": build_oauth_authorize_url(state=_mobile_oauth_state(email), redirect_uri=redirect_uri)}
    except InatConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/v1/inat/oauth/callback")
def finish_mobile_inat_oauth(code: str | None = None, state: str | None = None, error: str | None = None):
    email = _verify_mobile_oauth_state(state or "")
    if not email:
        return RedirectResponse("hikejournal://inat?status=error&message=expired")
    if error:
        return RedirectResponse("hikejournal://inat?status=error&message=cancelled")
    if not code:
        return RedirectResponse("hikejournal://inat?status=error&message=missing_code")
    try:
        token_payload = exchange_oauth_code(code=code, redirect_uri=_mobile_oauth_redirect_uri())
        _save_mobile_inat_oauth_token(get_services(), email=email, token_payload=token_payload)
    except (InatConfigurationError, InatAuthError, InatRequestError) as exc:
        return RedirectResponse("hikejournal://inat?status=error&message=authorization_failed")
    return RedirectResponse("hikejournal://inat?status=connected")


@app.get("/v1/hikes", dependencies=[Depends(require_mobile_key)])
def list_hikes() -> list[dict[str, Any]]:
    svc = get_services()
    hikes = _visible_hikes(svc.repository)
    hike_ids = [str(hike["id"]) for hike in hikes]
    photo_rows = (
        svc.repository._select_all_rows(
            lambda: (
                svc.client.table("photos")
                .select("id,hike_id,public_url,taken_at,created_at")
                .in_("hike_id", hike_ids)
            )
        )
        if hike_ids
        else []
    )
    photos_by_hike: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for photo in photo_rows:
        if photo.get("hike_id"):
            photos_by_hike[str(photo["hike_id"])].append(photo)
    confirmed_observations, species_photos_by_id, _ = _visible_species_data(svc)
    species_by_hike: dict[str, set[str]] = defaultdict(set)
    for observation in confirmed_observations:
        photo = species_photos_by_id.get(str(observation.get("photo_id") or ""))
        hike_id = str((photo or {}).get("hike_id") or observation.get("hike_id") or "")
        if hike_id:
            species_by_hike[hike_id].add(_species_key(observation))
    outing_payloads = [
        _hike_payload(
            hike,
            photos=photos_by_hike.get(str(hike["id"]), []),
            species_count=len(species_by_hike.get(str(hike["id"]), set())),
        )
        for hike in hikes
    ]
    return outing_payloads + [_standalone_hike_payload(svc)]


@app.get("/v1/hike-locations", dependencies=[Depends(require_mobile_key)])
def list_hike_locations() -> list[dict[str, Any]]:
    """Return the imported location library for native hike creation."""
    return [
        {
            "id": str(location.get("id") or ""),
            "name": str(location.get("name") or ""),
        }
        for location in get_services().repository.list_hike_locations()
        if location.get("id") and str(location.get("name") or "").strip()
    ]


@app.get("/v1/species", dependencies=[Depends(require_mobile_key)])
def list_species() -> list[dict[str, Any]]:
    svc = get_services()
    observations, photos_by_id, hikes_by_id = _visible_species_data(svc)
    return _build_species_payloads(observations, photos_by_id, hikes_by_id)


@app.get("/v1/discovery/areas", dependencies=[Depends(require_mobile_key)])
def list_discovery_areas(q: str = Query(default="", max_length=160)) -> list[dict[str, Any]]:
    _require_discovery_enabled()
    svc = get_services()
    return SpeciesDiscoveryService.list_areas(svc.repository, q)


@app.get("/v1/discovery/nearby", dependencies=[Depends(require_mobile_key)])
def get_nearby_species(
    area_id: str | None = Query(default=None, max_length=64),
    target_date: date = Query(alias="date"),
    radius_km: int = Query(default=10),
    iconic_taxon: str | None = Query(default=None, max_length=40),
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
            area = service.resolve_area(svc.repository, area_id)
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
            area = service.resolve_area(svc.repository, area_id)
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
        area = service.resolve_area(svc.repository, payload.area_id)
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
            candidate = inat_client.identify_species(
                image_bytes=_download_photo_for_cv(svc, photo),
                filename=f"{photo['id']}.jpg",
                lat=photo.get("lat"),
                lng=photo.get("lng"),
                observed_on=_photo_observed_at(photo),
            )
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


def _review_batch_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in job.items()
        if key not in {"owner_context", "client_request_id"}
    }


def _get_review_batch_job(job_id: str) -> dict[str, Any]:
    with _species_batch_jobs_lock:
        job = _species_batch_jobs.get(job_id)
        snapshot = dict(job) if job else None
        if snapshot:
            snapshot["processed_photo_ids"] = list(snapshot.get("processed_photo_ids") or [])
            snapshot["warnings"] = list(snapshot.get("warnings") or [])
            snapshot["items"] = list(snapshot.get("items") or [])
    if not snapshot or snapshot.get("owner_context") != _user_context():
        raise HTTPException(status_code=404, detail="Species identification batch not found.")
    return _review_batch_job_payload(snapshot)


def _update_review_batch_job(job_id: str, **updates: Any) -> None:
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
) -> None:
    _update_review_batch_job(job_id, state="running")
    next_photo_number = 1

    def on_group_start(group_number: int) -> None:
        _update_review_batch_job(job_id, current_group=group_number)

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
            job = _species_batch_jobs.get(job_id)
            if not job:
                return
            processed_ids = list(job.get("processed_photo_ids") or [])
            if photo_id not in processed_ids:
                processed_ids.append(photo_id)
            job["processed_photo_ids"] = processed_ids
            job["processed_count"] = len(processed_ids)

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
    except Exception as error:
        processed_ids = _get_review_batch_job(job_id).get("processed_photo_ids") or []
        refreshed_queue = _review_queue_payload(svc)
        processed_set = set(processed_ids)
        _update_review_batch_job(
            job_id,
            state="failed",
            error=str(error),
            current_photo_id=None,
            items=[item for item in refreshed_queue if str(item.get("id") or "") in processed_set],
        )
        return

    _update_review_batch_job(
        job_id,
        state="completed",
        processed_photo_ids=result["processed_photo_ids"],
        processed_count=len(result["processed_photo_ids"]),
        current_photo_id=None,
        current_photo_number=total_photos,
        grouped_count=result["grouped_count"],
        individual_count=result["individual_count"],
        warnings=result["warnings"],
        items=result["items"],
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
    with _species_batch_jobs_lock:
        if payload.client_request_id:
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
                return _review_batch_job_payload(dict(existing))
        finished_ids = [
            existing_id
            for existing_id, existing in _species_batch_jobs.items()
            if existing.get("state") in {"completed", "failed"}
        ]
        for existing_id in finished_ids[:-50]:
            _species_batch_jobs.pop(existing_id, None)
        _species_batch_jobs[job_id] = job
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


def _publish_batch_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in job.items()
        if key not in {"owner_context", "created_at", "client_request_id"}
    }


def _get_species_publish_batch_job(job_id: str) -> dict[str, Any]:
    with _species_publish_jobs_lock:
        job = dict(_species_publish_jobs.get(job_id) or {})
    if not job or job.get("owner_context") != _user_context():
        raise HTTPException(status_code=404, detail="iNaturalist publish batch not found.")
    return _publish_batch_job_payload(job)


def _update_species_publish_batch_job(job_id: str, **updates: Any) -> None:
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
) -> None:
    global _species_data_cache
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
    with _species_publish_jobs_lock:
        if payload.client_request_id:
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
                return _publish_batch_job_payload(dict(existing))
        finished_ids = [
            existing_id
            for existing_id, existing in _species_publish_jobs.items()
            if existing.get("state") in {"completed", "failed"}
        ]
        for existing_id in finished_ids[:-50]:
            _species_publish_jobs.pop(existing_id, None)
        _species_publish_jobs[job_id] = job
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
    matching = [observation for observation in observations if _species_key(observation) == key]
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
    return {**summaries[0], "encounters": encounters}


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
    return [
        {
            "hike_id": str(hike["id"]),
            "route_segments": route_import_to_route_groups(
                svc.repository.get_hike_route_import(str(hike["id"]))
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
        # the complete photo/observation history just to render this header.
        payload = _hike_payload(hike, photos=[])
        if include_route:
            payload["route_segments"] = route_import_to_route_groups(
                svc.repository.get_hike_route_import(hike_id)
            )
        return payload
    photos = svc.repository.list_photos(hike_id)
    observations = svc.repository.list_observations(hike_id)
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
    for observation in svc.repository.list_observations_for_photo_ids(
        [str(photo.get("id") or "") for photo in page]
    ):
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


def _sync_hike_location_tags(
    repository: HikeJournalRepository,
    hike: dict[str, Any],
    payload: HikeInput,
) -> None:
    locations = repository.list_hike_locations()
    known_location_ids = {str(location.get("id") or "") for location in locations}
    location_ids = (
        [payload.location_id]
        if payload.location_id and payload.location_id in known_location_ids
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
    source_type: Annotated[Literal["hikejournal_android_gps"] | None, Form()] = None,
) -> dict[str, Any]:
    """Save a TCX track for a hike so the native map can render its route."""
    svc = get_services()
    _get_visible_hike(svc.repository, hike_id)
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
    return {
        "route_segments": route_import_to_route_groups(route_import),
        "track_point_count": (route_import or {}).get("track_point_count", 0),
    }


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
        if existing:
            existing_scope = str(existing[0].get("hike_id") or EVERYDAY_JOURNAL_ID)
            if existing_scope != hike_id:
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
    photo = rows[0]
    if photo.get("hike_id"):
        _get_visible_hike(svc.repository, str(photo["hike_id"]))
    elif mobile_owner_email() and str(photo.get("owner_email") or "").lower() != mobile_owner_email():
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
    svc, photo = _get_visible_photo(photo_id)
    storage_path = str(photo.get("storage_path") or "")
    svc.repository.delete_photo(photo_id)
    if storage_path:
        try:
            svc.storage.delete_file(storage_path)
        except Exception:
            pass
    _invalidate_species_data_cache()
    return {"deleted": True}
