from __future__ import annotations

from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date
import hashlib
import hmac
import os
import time
from typing import Any, Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from supabase import Client, create_client

from hike_journal.config import settings
from hike_journal.domain.library import filter_hikes_for_user, record_visible_for_user
from hike_journal.models import HikeDraft, SpeciesCandidate
from hike_journal.services.exif import extract_metadata
from hike_journal.services.image_processing import optimize_image
from hike_journal.services.inat import (
    InatAuthError,
    InatClient,
    InatConfigurationError,
    InatRequestError,
    parse_candidates,
    resolve_access_token_for_user,
)
from hike_journal.services.inat_publishing import (
    get_inat_posting,
    get_publish_state,
    publish_observation_group,
    publish_single_observation,
)
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.storage import StorageService


MAX_UPLOAD_BYTES = 30 * 1024 * 1024


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


class CaptionInput(BaseModel):
    caption: str = Field(default="", max_length=5_000)


class ArchiveInput(BaseModel):
    is_archived: bool


class ReviewCandidateInput(BaseModel):
    taxon_id: int | None = None
    common_name: str = Field(default="", max_length=240)
    scientific_name: str = Field(default="", max_length=240)
    confidence: float | None = Field(default=None, ge=0, le=1)


class ReviewDecisionInput(BaseModel):
    action: Literal["confirm", "reject"]
    observation_id: str | None = None
    candidate: ReviewCandidateInput | None = None


class PublishInput(BaseModel):
    acknowledged_public: bool
    observation_ids: list[str] = Field(default_factory=list, max_length=10)
    description: str = Field(default="", max_length=5_000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    geoprivacy: Literal["open", "obscured", "private"] = "open"
    captive: bool = False


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


@asynccontextmanager
async def lifespan(_: FastAPI):
    global services
    services = Services()
    yield
    services = None


app = FastAPI(
    title="HikeJournal Mobile Companion API",
    version="0.5.2",
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
        "processing_status": photo.get("processing_status") or "ready",
        "species": [
            {
                "common_name": observation.get("common_name"),
                "scientific_name": observation.get("scientific_name"),
                "status": observation.get("status"),
                "is_primary": bool(observation.get("is_primary")),
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
        "cover_url": str((cover or {}).get("public_url") or ""),
        "photo_count": len(photos),
        "species_count": species_count,
    }


def _species_key(observation: dict[str, Any]) -> str:
    taxon_id = observation.get("taxon_id")
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
            key=lambda item: (
                _observed_on(
                    photos_by_id.get(str(item.get("photo_id") or ""), {}),
                    hikes_by_id.get(str(item.get("hike_id") or "")),
                )
                or ""
            ),
            reverse=True,
        )
        lead = ordered[0]
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
        for item in ordered:
            hike_id = str(item.get("hike_id") or "")
            photo_id = str(item.get("photo_id") or "")
            if hike_id in hikes_by_id and photo_id in photos_by_id:
                hike_encounter_counts[hike_id].add(photo_id)
                photo_url = str(photos_by_id[photo_id].get("public_url") or "")
                if photo_url:
                    hike_cover_urls.setdefault(hike_id, photo_url)
        cover_photo = photos_by_id.get(encounter_photo_ids[0], {}) if encounter_photo_ids else {}
        latest_seen = _observed_on(
            cover_photo,
            hikes_by_id.get(str(cover_photo.get("hike_id") or "")),
        )
        payloads.append(
            {
                "key": key,
                "taxon_id": lead.get("taxon_id"),
                "common_name": str(lead.get("common_name") or lead.get("scientific_name") or "Unknown species"),
                "scientific_name": str(lead.get("scientific_name") or ""),
                "rank": str(lead.get("rank") or ""),
                "iconic_taxon_name": str(lead.get("iconic_taxon_name") or "Other"),
                "wikipedia_url": str(lead.get("wikipedia_url") or ""),
                "wikipedia_summary": str(lead.get("wikipedia_summary") or ""),
                "encounter_count": len(encounter_photo_ids),
                "hike_count": len(hike_ids),
                "hike_ids": sorted(hike_ids),
                "hike_encounter_counts": {
                    hike_id: len(photo_ids)
                    for hike_id, photo_ids in sorted(hike_encounter_counts.items())
                },
                "hike_cover_urls": dict(sorted(hike_cover_urls.items())),
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


def _mobile_inat_client() -> InatClient:
    owner = _user_context()
    access_token = resolve_access_token_for_user(
        subject=owner.get("subject"),
        email=owner.get("email"),
    ) or settings.inat_access_token
    return InatClient(access_token=access_token, base_url=settings.inat_base_url)


def _publish_item_payload(
    observation: dict[str, Any],
    photo: dict[str, Any],
    hike: dict[str, Any] | None,
    *,
    related_observation_ids: list[str] | None = None,
) -> dict[str, Any]:
    posting = get_inat_posting(observation)
    return {
        "id": str(observation.get("id") or ""),
        "photo": _photo_payload(photo, [observation]),
        "hike_id": str((hike or {}).get("id") or "") or None,
        "hike_title": str((hike or {}).get("title") or "Everyday sighting"),
        "hike_date": str((hike or {}).get("hike_date") or ""),
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
    ready_groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for observation in observations:
        photo = photos_by_id.get(str(observation.get("photo_id") or ""))
        if not photo or get_publish_state(observation) != "ready":
            continue
        hike_id = str(photo.get("hike_id") or observation.get("hike_id") or "")
        observed_day = str(_observed_on(photo, hikes_by_id.get(hike_id)) or "")[:10]
        ready_groups[(_species_key(observation), hike_id, observed_day)].append(
            str(observation.get("id") or "")
        )
    items = []
    for observation in observations:
        photo = photos_by_id.get(str(observation.get("photo_id") or ""))
        if not photo:
            continue
        hike = hikes_by_id.get(str(photo.get("hike_id") or observation.get("hike_id") or ""))
        related_ids = [str(observation.get("id") or "")]
        if get_publish_state(observation) == "ready":
            hike_id = str(photo.get("hike_id") or observation.get("hike_id") or "")
            observed_day = str(_observed_on(photo, hikes_by_id.get(hike_id)) or "")[:10]
            related_ids = ready_groups.get((_species_key(observation), hike_id, observed_day), related_ids)
        items.append(
            _publish_item_payload(
                observation,
                photo,
                hike,
                related_observation_ids=related_ids[:10],
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
    return {"status": "ok", "service": "hikejournal-mobile", "version": "0.5.2"}


@app.get("/v1/config", dependencies=[Depends(require_mobile_key)])
def app_config() -> dict[str, Any]:
    return {
        "web_url": os.getenv("MOBILE_WEB_URL", "http://192.168.0.157:8505").rstrip("/"),
        "api_version": "0.5.2",
        "capabilities": ["offline_sync", "grouped_inat_publish", "map_packs"],
    }


@app.get("/v1/hikes", dependencies=[Depends(require_mobile_key)])
def list_hikes() -> list[dict[str, Any]]:
    svc = get_services()
    hikes = _visible_hikes(svc.repository)
    if not hikes:
        return []
    hike_ids = [str(hike["id"]) for hike in hikes]
    photo_rows = svc.repository._select_all_rows(
        lambda: (
            svc.client.table("photos")
            .select("id,hike_id,public_url,taken_at,created_at")
            .in_("hike_id", hike_ids)
        )
    )
    photos_by_hike: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for photo in photo_rows:
        if photo.get("hike_id"):
            photos_by_hike[str(photo["hike_id"])].append(photo)
    return [
        _hike_payload(hike, photos=photos_by_hike.get(str(hike["id"]), []))
        for hike in hikes
    ]


@app.get("/v1/species", dependencies=[Depends(require_mobile_key)])
def list_species() -> list[dict[str, Any]]:
    svc = get_services()
    observations, photos_by_id, hikes_by_id = _visible_species_data(svc)
    return _build_species_payloads(observations, photos_by_id, hikes_by_id)


@app.get("/v1/species/review", dependencies=[Depends(require_mobile_key)])
def list_species_review() -> list[dict[str, Any]]:
    return _review_queue_payload(get_services())


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
            svc.repository.apply_candidate_to_observation(
                str(observation_id),
                photo_id=photo_id,
                candidate=candidate,
                status="confirmed",
                is_primary=True,
            )
        else:
            svc.repository.update_observation_status(str(observation_id), "confirmed")
        svc.repository.update_photo_processing_status(photo_id, "ready")

    _species_data_cache = None
    return {"ok": True, "photo_id": photo_id, "action": payload.action}


@app.get("/v1/species/publish", dependencies=[Depends(require_mobile_key)])
def list_species_publish() -> dict[str, Any]:
    return _publish_queue_payload(get_services())


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
            detail="Connect iNaturalist from the Streamlit workspace before publishing on Android.",
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
    return _publish_item_payload(updated, photo, hike, related_observation_ids=requested_ids)


@app.get("/v1/species/detail", dependencies=[Depends(require_mobile_key)])
def get_species_detail(key: str) -> dict[str, Any]:
    svc = get_services()
    observations, photos_by_id, hikes_by_id = _visible_species_data(svc)
    matching = [observation for observation in observations if _species_key(observation) == key]
    summaries = _build_species_payloads(matching, photos_by_id, hikes_by_id)
    if not summaries:
        raise HTTPException(status_code=404, detail="Species not found.")

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
                "photo": _photo_payload(photo, photo_observations),
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


@app.get("/v1/hikes/{hike_id}", dependencies=[Depends(require_mobile_key)])
def get_hike(hike_id: str) -> dict[str, Any]:
    svc = get_services()
    hike = _get_visible_hike(svc.repository, hike_id)
    photos = svc.repository.list_photos(hike_id)
    observations = svc.repository.list_observations(hike_id)
    observations_by_photo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    confirmed_species: set[str] = set()
    for observation in observations:
        if observation.get("photo_id"):
            observations_by_photo[str(observation["photo_id"])].append(observation)
        if observation.get("status") == "confirmed":
            identity = str(
                observation.get("taxon_id")
                or observation.get("scientific_name")
                or observation.get("common_name")
                or ""
            )
            if identity:
                confirmed_species.add(identity)
    payload = _hike_payload(hike, photos=photos, species_count=len(confirmed_species))
    payload["photos"] = [
        _photo_payload(photo, observations_by_photo.get(str(photo.get("id")), []))
        for photo in photos
    ]
    return payload


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
    return _hike_payload(updated, photos=svc.repository.list_photos(hike_id))


@app.put("/v1/hikes/{hike_id}/archive", dependencies=[Depends(require_mobile_key)])
def update_archive(hike_id: str, payload: ArchiveInput) -> dict[str, Any]:
    svc = get_services()
    _get_visible_hike(svc.repository, hike_id)
    updated = svc.repository.update_hike_archive(hike_id, payload.is_archived)
    return _hike_payload(updated, photos=svc.repository.list_photos(hike_id))


@app.post("/v1/hikes/{hike_id}/photos", dependencies=[Depends(require_mobile_key)], status_code=201)
async def upload_photo(
    hike_id: str,
    file: Annotated[UploadFile, File()],
    caption: Annotated[str, Form()] = "",
    queue_for_review: Annotated[bool, Form()] = False,
    photo_id: Annotated[str, Form()] = "",
) -> dict[str, Any]:
    svc = get_services()
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
            if str(existing[0].get("hike_id") or "") != hike_id:
                raise HTTPException(status_code=409, detail="This photo ID belongs to another hike.")
            return _photo_payload(existing[0])
    original = await file.read(MAX_UPLOAD_BYTES + 1)
    if not original:
        raise HTTPException(status_code=400, detail="The selected photo was empty.")
    if len(original) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Photos must be 30 MB or smaller.")
    try:
        metadata = extract_metadata(original)
        processed = optimize_image(original)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="This image could not be processed.") from exc

    storage_path = ""
    try:
        storage_path, public_url = svc.storage.upload_hike_photo(
            hike_id,
            processed.bytes_data,
            processed.content_type,
            object_id=normalized_photo_id or None,
        )
        owner = _user_context()
        created = svc.repository.create_photo(
            {
                **({"id": normalized_photo_id} if normalized_photo_id else {}),
                "hike_id": hike_id,
                "owner_subject": owner.get("subject"),
                "owner_email": owner.get("email"),
                "storage_path": storage_path,
                "public_url": public_url,
                "caption": caption.strip() or None,
                "taken_at": metadata.taken_at.isoformat() if metadata.taken_at else None,
                "lat": metadata.lat,
                "lng": metadata.lng,
                "width": processed.width,
                "height": processed.height,
                "file_size": len(processed.bytes_data),
                "content_type": processed.content_type,
                "processing_status": "in_review" if queue_for_review else "ready",
                "exif_json": metadata.exif_json,
            }
        )
    except Exception:
        if storage_path:
            try:
                svc.storage.delete_file(storage_path)
            except Exception:
                pass
        raise
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


@app.post("/v1/photos/{photo_id}/review", dependencies=[Depends(require_mobile_key)])
def queue_photo_for_species_review(photo_id: str) -> dict[str, bool]:
    svc, _ = _get_visible_photo(photo_id)
    svc.repository.update_photo_processing_status(photo_id, "in_review")
    return {"queued": True}


@app.put("/v1/photos/{photo_id}/caption", dependencies=[Depends(require_mobile_key)])
def update_photo_caption(photo_id: str, payload: CaptionInput) -> dict[str, Any]:
    svc, _ = _get_visible_photo(photo_id)
    return _photo_payload(svc.repository.update_photo_caption(photo_id, payload.caption))


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
    return {"deleted": True}
