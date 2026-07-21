from __future__ import annotations

from datetime import UTC, datetime
import base64
import json
import re
import time
from typing import Any
from urllib.parse import urlencode

import requests

from hike_journal.config import (
    load_inat_token_record_for_user,
    save_inat_access_token,
    save_inat_access_token_for_user,
    save_inat_token_record_for_user,
    settings,
)
from hike_journal.models import SpeciesCandidate


class InatConfigurationError(RuntimeError):
    """Raised when iNaturalist is not configured."""


class InatRequestError(RuntimeError):
    """Raised when iNaturalist request fails."""


class InatAuthError(InatRequestError):
    """Raised when iNaturalist authentication fails."""


class InatComputerVisionBlockedError(InatRequestError):
    """Raised when iNaturalist refuses computer-vision suggestions."""


class InatRateLimitError(InatRequestError):
    """Raised when iNaturalist asks the client to slow down."""

    def __init__(self, message: str, *, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class InatClient:
    def __init__(self, access_token: str | None = None, base_url: str | None = None):
        self.access_token = access_token or settings.inat_access_token
        self.base_url = (base_url or settings.inat_base_url).rstrip("/")
        self.request_interval_seconds = 0.75
        self.cv_request_interval_seconds = max(self.request_interval_seconds, settings.inat_cv_request_interval_seconds)
        self._last_request_at = 0.0
        self.user_agent = "HikeJournal/1.0 (personal field journal; contact: addlloyd@gmail.com)"

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token)

    @property
    def token_expiry(self) -> datetime | None:
        return _extract_token_expiry(self.access_token)

    def validate_credentials(self) -> None:
        if not self.is_configured:
            raise InatConfigurationError("No iNaturalist token is configured yet. Paste one into the token panel below to keep species review running.")

        expiry = _extract_token_expiry(self.access_token)
        if expiry and expiry <= datetime.now(UTC):
            raise InatAuthError("Your iNaturalist token has expired. Visit /users/api_token, copy a fresh token, and paste it below before processing photos.")

        url = f"{self.base_url}/users/me"
        headers = self._headers(auth=True)
        response = self._request("get", url, headers=headers, timeout=15)
        if response.status_code == 401:
            raise InatAuthError("iNaturalist rejected this token. Visit /users/api_token, copy a fresh token, and paste it below before processing photos.")
        if response.status_code >= 400 and expiry is None:
            raise InatAuthError(f"iNaturalist credential check failed with {response.status_code}. Please refresh your token and try again.")

    def score_species_candidates(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        lat: float | None,
        lng: float | None,
        observed_on: datetime | None,
        limit: int | None = 5,
    ) -> tuple[list[SpeciesCandidate], dict[str, Any]]:
        if not self.is_configured:
            raise InatConfigurationError("INAT_ACCESS_TOKEN is not configured yet.")

        url = f"{self.base_url}/computervision/score_image"
        headers = self._headers(auth=True)
        data: dict[str, Any] = {}
        if lat is not None:
            data["lat"] = str(lat)
        if lng is not None:
            data["lng"] = str(lng)
        if observed_on is not None:
            data["observed_on"] = observed_on.date().isoformat()

        response = self._request(
            "post",
            url,
            headers=headers,
            data=data,
            files={"image": (filename, image_bytes, "image/jpeg")},
            min_interval=self.cv_request_interval_seconds,
            timeout=45,
        )
        if response.status_code == 401:
            raise InatAuthError("iNaturalist rejected this token while processing photos. Paste a fresh token below and try the batch again.")
        if response.status_code == 403:
            raise InatComputerVisionBlockedError(
                "iNaturalist is blocking computer-vision suggestions from this server right now. "
                "Your token can still be valid for posting observations; this only affects Process selected / image ID requests."
            )
        if response.status_code >= 400:
            raise InatRequestError(f"iNaturalist returned {response.status_code}: {response.text[:200]}")

        payload = response.json()
        candidates = parse_candidates(payload, limit=limit)
        if not candidates:
            raise InatRequestError("iNaturalist returned no usable species suggestions.")
        return candidates, payload

    def identify_species(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        lat: float | None,
        lng: float | None,
        observed_on: datetime | None,
    ) -> SpeciesCandidate:
        candidates, _ = self.score_species_candidates(
            image_bytes=image_bytes,
            filename=filename,
            lat=lat,
            lng=lng,
            observed_on=observed_on,
            limit=1,
        )
        return candidates[0]

    def fetch_taxon_enrichment(self, taxon_id: int) -> dict[str, Any]:
        if not self.is_configured:
            raise InatConfigurationError("INAT_ACCESS_TOKEN is not configured yet.")

        url = f"{self.base_url}/taxa/{taxon_id}"
        headers = self._headers(auth=True)
        response = self._request("get", url, headers=headers, timeout=30)
        if response.status_code == 401:
            raise InatAuthError("iNaturalist rejected this token during taxon lookup. Paste a fresh token below and try again.")
        if response.status_code >= 400:
            raise InatRequestError(f"iNaturalist taxon lookup returned {response.status_code}: {response.text[:200]}")
        payload = response.json()
        results = payload.get("results") or []
        if not results or not isinstance(results[0], dict):
            raise InatRequestError("iNaturalist taxon lookup returned no usable taxon details.")
        return extract_taxon_enrichment(results[0])

    def fetch_observation(self, observation_id: int | str) -> dict[str, Any]:
        observations = self.fetch_observations([observation_id])
        if not observations:
            raise InatRequestError(f"iNaturalist returned no observation for {observation_id}.")
        return observations[0]

    def fetch_observations(self, observation_ids: list[int | str]) -> list[dict[str, Any]]:
        normalized_ids = [str(observation_id).strip() for observation_id in observation_ids if str(observation_id).strip()]
        if not normalized_ids:
            return []
        url = f"{self.base_url}/observations/{','.join(normalized_ids)}"
        headers = self._headers(auth=bool(self.access_token))
        response = self._request("get", url, headers=headers, timeout=30)
        if response.status_code == 401:
            raise InatAuthError("iNaturalist rejected this token while checking posted observations. Paste a fresh token and try again.")
        if response.status_code >= 400:
            raise InatRequestError(f"iNaturalist observation lookup returned {response.status_code}: {response.text[:200]}")
        payload = response.json()
        if isinstance(payload, dict):
            results = payload.get("results")
            if isinstance(results, list):
                return [item for item in results if isinstance(item, dict)]
            return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        raise InatRequestError("iNaturalist returned an unexpected observation lookup response.")

    def autocomplete_taxa(self, query: str) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        url = f"{self.base_url}/taxa/autocomplete"
        headers = self._headers(auth=bool(self.access_token))
        response = self._request("get", url, headers=headers, params={"q": query.strip()}, timeout=20)
        if response.status_code == 401:
            raise InatAuthError("iNaturalist rejected this token during taxon search. Paste a fresh token below and try again.")
        if response.status_code >= 400:
            raise InatRequestError(f"iNaturalist taxon autocomplete returned {response.status_code}: {response.text[:200]}")
        payload = response.json()
        return payload.get("results") or []

    def create_observation(
        self,
        *,
        taxon_id: int | None,
        species_guess: str | None,
        observed_on: datetime | None,
        lat: float | None,
        lng: float | None,
        place_guess: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        geoprivacy: str | None = None,
        captive: bool = False,
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise InatConfigurationError("No iNaturalist token is configured yet.")

        url = f"{self.base_url}/observations"
        headers = self._headers(auth=True)
        observation_payload: dict[str, Any] = {}
        if taxon_id:
            observation_payload["taxon_id"] = int(taxon_id)
        elif species_guess:
            observation_payload["species_guess"] = species_guess.strip()
        else:
            raise InatConfigurationError("A species name or taxon is required before posting to iNaturalist.")
        if observed_on is not None:
            observation_payload["observed_on_string"] = observed_on.strftime("%Y-%m-%d %H:%M:%S")
        if lat is not None:
            observation_payload["latitude"] = float(lat)
        if lng is not None:
            observation_payload["longitude"] = float(lng)
        if place_guess:
            observation_payload["place_guess"] = place_guess.strip()
        if description:
            observation_payload["description"] = description.strip()
        if tags:
            observation_payload["tag_list"] = ",".join(tag.strip() for tag in tags if tag.strip())
        if geoprivacy in {"open", "obscured", "private"}:
            observation_payload["geoprivacy"] = geoprivacy
        if captive:
            observation_payload["captive"] = True

        response = self._request(
            "post",
            url,
            headers=headers,
            json={"observation": observation_payload},
            timeout=30,
        )
        if response.status_code == 401:
            raise InatAuthError("iNaturalist rejected this token while creating an observation. Paste a fresh token below and try again.")
        if response.status_code >= 400:
            raise InatRequestError(f"iNaturalist observation create returned {response.status_code}: {response.text[:250]}")
        payload = response.json()
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0]
        if isinstance(payload, dict):
            results = payload.get("results")
            if isinstance(results, list) and results:
                first = results[0]
                if isinstance(first, dict):
                    return first
            return payload
        raise InatRequestError("iNaturalist returned an unexpected observation response.")

    def attach_photo_to_observation(
        self,
        *,
        observation_id: int,
        image_bytes: bytes,
        filename: str,
        content_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise InatConfigurationError("No iNaturalist token is configured yet.")

        url = f"{self.base_url}/observation_photos"
        headers = self._headers(auth=True)
        response = self._request(
            "post",
            url,
            headers=headers,
            data={"observation_photo[observation_id]": str(observation_id)},
            files={"file": (filename, image_bytes, content_type)},
            timeout=45,
        )
        if response.status_code == 401:
            raise InatAuthError("iNaturalist rejected this token while uploading the photo. Paste a fresh token below and try again.")
        if response.status_code >= 400:
            raise InatRequestError(f"iNaturalist photo upload returned {response.status_code}: {response.text[:250]}")
        payload = response.json()
        if isinstance(payload, dict):
            results = payload.get("results")
            if isinstance(results, list) and results:
                first = results[0]
                if isinstance(first, dict):
                    return first
            return payload
        raise InatRequestError("iNaturalist returned an unexpected photo-upload response.")

    def _headers(self, *, auth: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        request_interval = float(kwargs.pop("min_interval", self.request_interval_seconds))
        elapsed = time.monotonic() - self._last_request_at
        if self._last_request_at and elapsed < request_interval:
            time.sleep(request_interval - elapsed)
        response = requests.request(method, url, **kwargs)
        self._last_request_at = time.monotonic()
        if response.status_code != 429:
            return response
        retry_after = _parse_retry_after(response.headers.get("Retry-After"))
        wait_seconds = retry_after if retry_after is not None else 5.0
        time.sleep(min(max(wait_seconds, request_interval), 20.0))
        response = requests.request(method, url, **kwargs)
        self._last_request_at = time.monotonic()
        if response.status_code == 429:
            raise InatRateLimitError(
                "iNaturalist is rate limiting these requests. Wait a minute, then continue processing.",
                retry_after=retry_after,
            )
        return response


def normalize_access_token(raw_value: str) -> str:
    raw_value = raw_value.strip()
    if not raw_value:
        return ""
    if raw_value.startswith("{"):
        try:
            payload = json.loads(raw_value)
            return str(payload.get("api_token") or "").strip()
        except (ValueError, TypeError, json.JSONDecodeError):
            return raw_value
    return raw_value


def persist_access_token(access_token: str) -> None:
    normalized = normalize_access_token(access_token)
    if not normalized:
        raise InatConfigurationError("Paste a token first.")
    save_inat_access_token(normalized)


def persist_access_token_for_user(access_token: str, *, subject: str | None, email: str | None) -> None:
    normalized = normalize_access_token(access_token)
    if not normalized:
        raise InatConfigurationError("Paste a token first.")
    save_inat_access_token_for_user(access_token=normalized, subject=subject, email=email)


def build_oauth_authorize_url(*, state: str, redirect_uri: str | None = None) -> str:
    if not settings.inat_oauth_configured:
        raise InatConfigurationError("iNaturalist OAuth is not configured yet. Add the iNaturalist OAuth client ID, secret, and redirect URI first.")
    resolved_redirect_uri = (redirect_uri or settings.inat_oauth_redirect_uri).strip()
    query = urlencode(
        {
            "client_id": settings.inat_oauth_client_id,
            "redirect_uri": resolved_redirect_uri,
            "response_type": "code",
            "scope": "write",
            "state": state,
        }
    )
    return f"{settings.inat_oauth_authorize_url}?{query}"


def exchange_oauth_code(*, code: str, redirect_uri: str | None = None) -> dict[str, Any]:
    if not settings.inat_oauth_configured:
        raise InatConfigurationError("iNaturalist OAuth is not configured yet.")
    resolved_redirect_uri = (redirect_uri or settings.inat_oauth_redirect_uri).strip()
    response = requests.post(
        settings.inat_oauth_token_url,
        data={
            "client_id": settings.inat_oauth_client_id,
            "client_secret": settings.inat_oauth_client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": resolved_redirect_uri,
            "code": code,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise InatAuthError(f"iNaturalist OAuth token exchange failed with {response.status_code}: {response.text[:250]}")
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise InatAuthError("iNaturalist OAuth did not return an access token.")
    return payload


def refresh_oauth_access_token(*, refresh_token: str) -> dict[str, Any]:
    if not settings.inat_oauth_configured:
        raise InatConfigurationError("iNaturalist OAuth is not configured yet.")
    response = requests.post(
        settings.inat_oauth_token_url,
        data={
            "client_id": settings.inat_oauth_client_id,
            "client_secret": settings.inat_oauth_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise InatAuthError(f"iNaturalist OAuth refresh failed with {response.status_code}: {response.text[:250]}")
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise InatAuthError("iNaturalist OAuth refresh did not return an access token.")
    return payload


def fetch_api_token_for_oauth_access_token(oauth_access_token: str) -> str:
    if not oauth_access_token.strip():
        raise InatAuthError("iNaturalist OAuth did not return a usable access token.")
    response = requests.get(
        settings.inat_api_token_url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {oauth_access_token.strip()}",
            "User-Agent": "HikeJournal/1.0 (personal field journal; contact: addlloyd@gmail.com)",
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise InatAuthError(f"iNaturalist API token exchange failed with {response.status_code}: {response.text[:250]}")
    payload = response.json()
    api_token = str(payload.get("api_token") or "").strip() if isinstance(payload, dict) else ""
    if not api_token:
        raise InatAuthError("iNaturalist did not return an API token for this OAuth session.")
    return api_token


def save_oauth_token_payload_for_user(
    token_payload: dict[str, Any],
    *,
    subject: str | None,
    email: str | None,
) -> None:
    oauth_access_token = str(token_payload.get("access_token") or "").strip()
    api_token = fetch_api_token_for_oauth_access_token(oauth_access_token)
    expires_at: str | None = None
    expires_in = token_payload.get("expires_in")
    try:
        if expires_in is not None:
            expires_at = datetime.fromtimestamp(
                datetime.now(UTC).timestamp() + int(expires_in),
                tz=UTC,
            ).isoformat()
    except (TypeError, ValueError):
        expires_at = None
    save_inat_token_record_for_user(
        record={
            "token_kind": "oauth",
            "api_token": api_token,
            "oauth_access_token": oauth_access_token,
            "refresh_token": str(token_payload.get("refresh_token") or "").strip(),
            "expires_at": expires_at,
        },
        subject=subject,
        email=email,
    )


def resolve_access_token_for_user(*, subject: str | None, email: str | None) -> str:
    record = load_inat_token_record_for_user(subject=subject, email=email)
    if not record:
        return ""
    token_kind = str(record.get("token_kind") or "").strip().lower()
    if token_kind != "oauth":
        return str(record.get("api_token") or record.get("access_token") or "").strip()
    api_token = str(record.get("api_token") or "").strip()
    legacy_access_token = str(record.get("access_token") or "").strip()
    oauth_access_token = str(record.get("oauth_access_token") or "").strip()
    if legacy_access_token:
        if _extract_token_expiry(legacy_access_token):
            api_token = api_token or legacy_access_token
        else:
            oauth_access_token = oauth_access_token or legacy_access_token
    refresh_token = str(record.get("refresh_token") or "").strip()
    expires_at_raw = str(record.get("expires_at") or "").strip()
    expires_at: datetime | None = None
    if expires_at_raw:
        try:
            expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
        except ValueError:
            expires_at = None
    api_token_expiry = _extract_token_expiry(api_token)
    if api_token and (api_token_expiry is None or api_token_expiry > datetime.now(UTC)):
        return api_token
    if oauth_access_token and (expires_at is None or expires_at > datetime.now(UTC)):
        api_token = fetch_api_token_for_oauth_access_token(oauth_access_token)
        refreshed_record = dict(record)
        refreshed_record.pop("access_token", None)
        refreshed_record["api_token"] = api_token
        refreshed_record["oauth_access_token"] = oauth_access_token
        save_inat_token_record_for_user(record=refreshed_record, subject=subject, email=email)
        return api_token
    if refresh_token:
        refreshed = refresh_oauth_access_token(refresh_token=refresh_token)
        if not refreshed.get("refresh_token"):
            refreshed["refresh_token"] = refresh_token
        save_oauth_token_payload_for_user(refreshed, subject=subject, email=email)
        return resolve_access_token_for_user(subject=subject, email=email)
    return api_token


def parse_candidates(payload: dict[str, Any], *, limit: int | None = None) -> list[SpeciesCandidate]:
    entries = payload.get("results") or payload.get("taxa") or payload.get("scores") or []
    candidates: list[SpeciesCandidate] = []
    seen_taxon_ids: set[int | None] = set()

    for entry in entries:
        taxon = entry.get("taxon") if isinstance(entry, dict) else None
        taxon = taxon or entry
        if not isinstance(taxon, dict):
            continue

        score_raw = entry.get("combined_score") or entry.get("score") or entry.get("vision_score") or 0
        try:
            confidence = float(score_raw)
        except (TypeError, ValueError):
            confidence = 0.0

        candidate = SpeciesCandidate(
            common_name=str(taxon.get("preferred_common_name") or taxon.get("english_common_name") or taxon.get("name") or "Unknown species"),
            scientific_name=str(taxon.get("name") or taxon.get("preferred_common_name") or "Unknown species"),
            confidence=confidence,
            taxon_id=_coerce_int(taxon.get("id")),
            raw_payload=payload,
        )
        if candidate.taxon_id in seen_taxon_ids:
            continue
        seen_taxon_ids.add(candidate.taxon_id)
        candidates.append(candidate)

    candidates.sort(key=lambda candidate: candidate.confidence, reverse=True)
    if limit is not None:
        return candidates[:limit]
    return candidates


def parse_candidate(payload: dict[str, Any]) -> SpeciesCandidate | None:
    candidates = parse_candidates(payload, limit=1)
    return candidates[0] if candidates else None


def extract_observation_taxon_snapshot(observation_payload: dict[str, Any]) -> dict[str, Any] | None:
    observation = _extract_observation_record(observation_payload)
    if not observation:
        return None
    taxon = observation.get("taxon")
    if not isinstance(taxon, dict):
        return None
    taxon_id = _coerce_int(taxon.get("id"))
    if taxon_id is None:
        return None
    common_name = _coerce_text(
        taxon.get("preferred_common_name")
        or taxon.get("english_common_name")
        or observation.get("species_guess")
        or taxon.get("name")
    )
    scientific_name = _coerce_text(taxon.get("name") or common_name)
    return {
        "taxon_id": taxon_id,
        "common_name": common_name or scientific_name or "Unknown species",
        "scientific_name": scientific_name or common_name or "Unknown species",
        "rank": _coerce_text(taxon.get("rank")),
        "iconic_taxon_name": _coerce_text(taxon.get("iconic_taxon_name")),
        "community_taxon_id": _coerce_int(observation.get("community_taxon_id")),
        "quality_grade": _coerce_text(observation.get("quality_grade")),
        "observation_updated_at": _coerce_text(observation.get("updated_at")),
        "observation_id": _coerce_int(observation.get("id")),
        "uri": _coerce_text(observation.get("uri")),
        "identification_count": len(observation.get("identifications") or []),
        "raw_observation": observation,
    }


def build_observation_sync_candidate(
    local_observation: dict[str, Any],
    inat_observation: dict[str, Any],
) -> dict[str, Any] | None:
    snapshot = extract_observation_taxon_snapshot(inat_observation)
    if not snapshot:
        return None
    local_taxon_id = _coerce_int(local_observation.get("taxon_id"))
    if local_taxon_id is not None and local_taxon_id == snapshot["taxon_id"]:
        return None
    local_common = _normalize_name(local_observation.get("common_name"))
    local_scientific = _normalize_name(local_observation.get("scientific_name"))
    remote_common = _normalize_name(snapshot.get("common_name"))
    remote_scientific = _normalize_name(snapshot.get("scientific_name"))
    names_match = bool(({local_common, local_scientific} & {remote_common, remote_scientific}) - {""})
    if local_taxon_id is None and not snapshot.get("taxon_id"):
        return None
    if local_taxon_id is not None and names_match and snapshot.get("taxon_id") is None:
        return None
    return {
        "observation_id": str(local_observation.get("id") or ""),
        "inat_observation_id": snapshot.get("observation_id") or _coerce_int(local_observation.get("inat_observation_id")),
        "inat_observation_url": _coerce_text(local_observation.get("inat_observation_url")) or snapshot.get("uri"),
        "local": {
            "taxon_id": local_taxon_id,
            "common_name": _coerce_text(local_observation.get("common_name")),
            "scientific_name": _coerce_text(local_observation.get("scientific_name")),
        },
        "inat": snapshot,
        "reason": "missing_local_taxon" if local_taxon_id is None else "changed_taxon",
    }


def _extract_observation_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    if isinstance(results, list) and results and isinstance(results[0], dict):
        return results[0]
    return payload


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def extract_taxon_enrichment(taxon: dict[str, Any]) -> dict[str, Any]:
    preferred_common_name = _coerce_text(taxon.get("preferred_common_name"))
    english_common_name = _coerce_text(taxon.get("english_common_name"))
    scientific_name = _coerce_text(taxon.get("name"))
    wikipedia_summary = _coerce_text(taxon.get("wikipedia_summary"))
    alias_names = sorted(
        {
            alias
            for alias in [
                preferred_common_name,
                english_common_name,
                *_extract_common_names_from_summary(wikipedia_summary),
            ]
            if alias
        }
    )
    return {
        "preferred_common_name": preferred_common_name,
        "english_common_name": english_common_name,
        "rank": _coerce_text(taxon.get("rank")),
        "iconic_taxon_name": _coerce_text(taxon.get("iconic_taxon_name")),
        "wikipedia_url": _coerce_text(taxon.get("wikipedia_url")),
        "wikipedia_summary": wikipedia_summary,
        "alias_names": alias_names,
        "scientific_name": scientific_name,
    }


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return None


def _normalize_name(value: Any) -> str:
    text = _coerce_text(value) or ""
    return re.sub(r"\s+", " ", text).strip().lower()


def _extract_common_names_from_summary(summary: str | None) -> list[str]:
    if not summary:
        return []
    matches = re.findall(r"<b>([^<]+)</b>", summary)
    aliases = []
    for match in matches:
        cleaned = re.sub(r"\s+", " ", match).strip()
        if cleaned:
            aliases.append(cleaned)
    return aliases


def _extract_token_expiry(access_token: str | None) -> datetime | None:
    if not access_token or access_token.count(".") < 2:
        return None
    try:
        payload_segment = access_token.split(".")[1]
        padded = payload_segment + "=" * (-len(payload_segment) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
        expiry = payload.get("exp")
        if expiry is None:
            return None
        return datetime.fromtimestamp(int(expiry), tz=UTC)
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
