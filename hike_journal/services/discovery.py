from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import logging
import time
from typing import Any

import requests

from hike_journal.config import settings
from hike_journal.domain.discovery import (
    DISCOVERY_ALGORITHM_VERSION,
    DISCOVERY_LIMIT,
    attach_discovery_reasons,
    attach_collection_progress,
    build_collection_index,
    classify_data_density,
    discovery_cache_key,
    normalize_iconic_taxon,
    normalize_discovery_limit,
    normalize_radius,
    normalize_species_counts,
    seasonal_months,
)
from hike_journal.services.inat import InatRateLimitError, InatRequestError
from hike_journal.services.repositories import HikeJournalRepository


DISCOVERY_FIELDS = (
    "(count:!t,taxon:(id:!t,name:!t,rank:!t,preferred_common_name:!t,"
    "english_common_name:!t,iconic_taxon_name:!t,wikipedia_url:!t,wikipedia_summary:!t,default_photo:"
    "(url:!t,medium_url:!t,attribution:!t,license_code:!t)))"
)
DISCOVERY_OBSERVATION_FIELDS = (
    "(id:!t,observed_on:!t,uri:!t,geojson:!t,obscured:!t,geoprivacy:!t,"
    "taxon_geoprivacy:!t,place_guess:!t,positional_accuracy:!t,photos:all,user:(login:!t))"
)
DISCOVERY_OBSERVATION_LIMIT = 200
logger = logging.getLogger(__name__)


class InatDiscoveryClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.inat_discovery_base_url).rstrip("/")
        self.user_agent = "HikeJournal/1.0 (personal field journal; contact: addlloyd@gmail.com)"

    def fetch_species_counts(
        self,
        *,
        lat: float,
        lng: float,
        radius_km: int,
        months: tuple[int, int, int],
        iconic_taxon: str | None,
        observed_after: str,
        limit: int = DISCOVERY_LIMIT,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "lat": round(float(lat), 4),
            "lng": round(float(lng), 4),
            "radius": int(radius_km),
            "month": ",".join(str(month) for month in months),
            "quality_grade": "research",
            "captive": "false",
            "taxon_is_active": "true",
            "photos": "true",
            "geo": "true",
            "rank": "species",
            "d1": observed_after,
            "order": "desc",
            "per_page": int(limit),
            "fields": DISCOVERY_FIELDS,
        }
        if iconic_taxon:
            params["iconic_taxa"] = iconic_taxon
        try:
            response = requests.get(
                f"{self.base_url}/observations/species_counts",
                params=params,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise InatRequestError(f"iNaturalist discovery request failed: {exc}") from exc
        if response.status_code == 429:
            retry_after: float | None = None
            try:
                retry_after = float(response.headers.get("Retry-After") or "")
            except (TypeError, ValueError):
                pass
            raise InatRateLimitError(
                "iNaturalist is asking HikeJournal to slow down.",
                retry_after=retry_after,
            )
        if response.status_code >= 400:
            raise InatRequestError(
                f"iNaturalist discovery returned {response.status_code}: {response.text[:200]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise InatRequestError("iNaturalist discovery returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise InatRequestError("iNaturalist discovery returned an unexpected response.")
        return payload

    def fetch_species_observations(
        self,
        *,
        taxon_id: int,
        lat: float,
        lng: float,
        radius_km: int,
        months: tuple[int, ...],
        observed_after: str,
        limit: int = DISCOVERY_OBSERVATION_LIMIT,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "taxon_id": int(taxon_id),
            "lat": round(float(lat), 4),
            "lng": round(float(lng), 4),
            "radius": int(radius_km),
            "month": ",".join(str(month) for month in months),
            "quality_grade": "research",
            "captive": "false",
            "geo": "true",
            "d1": observed_after,
            "order": "desc",
            "order_by": "observed_on",
            "per_page": min(max(int(limit), 1), DISCOVERY_OBSERVATION_LIMIT),
            "fields": DISCOVERY_OBSERVATION_FIELDS,
        }
        try:
            response = requests.get(
                f"{self.base_url}/observations",
                params=params,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise InatRequestError(f"iNaturalist sightings request failed: {exc}") from exc
        if response.status_code == 429:
            retry_after: float | None = None
            try:
                retry_after = float(response.headers.get("Retry-After") or "")
            except (TypeError, ValueError):
                pass
            raise InatRateLimitError(
                "iNaturalist is asking HikeJournal to slow down.",
                retry_after=retry_after,
            )
        if response.status_code >= 400:
            raise InatRequestError(
                f"iNaturalist sightings returned {response.status_code}: {response.text[:200]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise InatRequestError("iNaturalist sightings returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise InatRequestError("iNaturalist sightings returned an unexpected response.")
        return payload


class SpeciesDiscoveryService:
    def __init__(
        self,
        repository: HikeJournalRepository,
        *,
        inat_client: InatDiscoveryClient | None = None,
        now: datetime | None = None,
    ):
        self.repository = repository
        self.inat_client = inat_client or InatDiscoveryClient()
        self.now = now or datetime.now(UTC)

    @staticmethod
    def list_areas(
        repository: HikeJournalRepository,
        query: str = "",
        *,
        locations: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        normalized_query = query.strip().casefold()
        areas = []
        for location in (locations if locations is not None else repository.list_hike_locations()):
            try:
                lat = float(location.get("lat"))
                lng = float(location.get("lng"))
            except (TypeError, ValueError):
                continue
            name = str(location.get("name") or "").strip()
            aliases = " ".join(str(alias) for alias in (location.get("aliases") or []))
            if normalized_query and normalized_query not in f"{name} {aliases}".casefold():
                continue
            areas.append(
                {
                    "id": str(location.get("id") or ""),
                    "name": name or "Unnamed area",
                    "lat": lat,
                    "lng": lng,
                    "location_type": str(location.get("location_type") or ""),
                }
            )
        return sorted(areas, key=lambda area: area["name"].casefold())

    @staticmethod
    def resolve_area(
        repository: HikeJournalRepository,
        area_id: str,
        *,
        locations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        area = next(
            (
                item
                for item in SpeciesDiscoveryService.list_areas(repository, locations=locations)
                if str(item.get("id")) == str(area_id)
            ),
            None,
        )
        if area is None:
            raise ValueError("Choose a saved area with coordinates.")
        return area

    def nearby(
        self,
        *,
        area: dict[str, Any],
        target_date: date,
        radius_km: int | float,
        iconic_taxon: str | None,
        observations: list[dict[str, Any]],
        photos_by_id: dict[str, dict[str, Any]],
        limit: int = DISCOVERY_LIMIT,
    ) -> dict[str, Any]:
        started_at = time.monotonic()
        radius = normalize_radius(radius_km)
        result_limit = normalize_discovery_limit(limit)
        normalized_iconic_taxon = normalize_iconic_taxon(iconic_taxon)
        months = seasonal_months(target_date)
        observed_after = self._observed_after()
        cache_key = discovery_cache_key(
            lat=float(area["lat"]),
            lng=float(area["lng"]),
            radius_km=radius,
            months=months,
            iconic_taxon=normalized_iconic_taxon,
            observed_after=observed_after,
            limit=result_limit,
        )
        snapshot = self.repository.get_species_discovery_snapshot(cache_key)
        from_cache = False
        taxa: list[dict[str, Any]]
        fetched_at: str
        if snapshot and self._snapshot_is_fresh(snapshot):
            taxa = list(snapshot.get("taxa") or [])
            fetched_at = str(snapshot.get("fetched_at") or self.now.isoformat())
            from_cache = True
        else:
            try:
                raw_payload = self.inat_client.fetch_species_counts(
                    lat=float(area["lat"]),
                    lng=float(area["lng"]),
                    radius_km=radius,
                    months=months,
                    iconic_taxon=normalized_iconic_taxon,
                    observed_after=observed_after,
                    limit=result_limit,
                )
                taxa = normalize_species_counts(raw_payload, limit=result_limit)
                fetched_at = self.now.isoformat()
                self.repository.upsert_species_discovery_snapshot(
                    {
                        "cache_key": cache_key,
                        "algorithm_version": DISCOVERY_ALGORITHM_VERSION,
                        "lat": round(float(area["lat"]), 3),
                        "lng": round(float(area["lng"]), 3),
                        "radius_km": radius,
                        "months": list(months),
                        "iconic_taxon": normalized_iconic_taxon,
                        "observed_after": observed_after,
                        "taxa": taxa,
                        "fetched_at": fetched_at,
                        "expires_at": (self.now + timedelta(hours=24)).isoformat(),
                    }
                )
            except (InatRequestError, InatRateLimitError) as exc:
                logger.warning(
                    "species_discovery request_key=%s failure=%s stale_available=%s",
                    cache_key[:16],
                    type(exc).__name__,
                    bool(snapshot),
                )
                if not snapshot:
                    raise
                taxa = list(snapshot.get("taxa") or [])
                fetched_at = str(snapshot.get("fetched_at") or self.now.isoformat())
                from_cache = True
        collection = build_collection_index(observations, photos_by_id)
        progress = attach_collection_progress(taxa, collection)
        period_label = _period_label(months)
        progress["taxa"] = attach_discovery_reasons(
            progress["taxa"],
            area_name=str(area.get("name") or "Selected area"),
            radius_km=radius,
            period_label=period_label,
        )
        payload = {
            "area": {
                "id": str(area.get("id") or ""),
                "name": str(area.get("name") or "Selected area"),
                "lat": round(float(area["lat"]), 3),
                "lng": round(float(area["lng"]), 3),
                "radius_km": radius,
            },
            "period": {
                "target_date": target_date.isoformat(),
                "months": list(months),
                "label": period_label,
            },
            "filters": {
                "iconic_taxon": normalized_iconic_taxon,
                "observed_after": observed_after,
                "quality_grade": "research",
                "result_limit": result_limit,
            },
            "source": {
                "provider": "iNaturalist",
                "algorithm_version": DISCOVERY_ALGORITHM_VERSION,
                "fetched_at": fetched_at,
                "from_cache": from_cache,
                "guidance": "Reporting frequency is not a probability of encounter.",
            },
            "data_density": classify_data_density(taxa),
            **progress,
        }
        logger.info(
            "species_discovery request_key=%s cache_hit=%s response_taxa=%d latency_ms=%d",
            cache_key[:16],
            from_cache,
            len(taxa),
            round((time.monotonic() - started_at) * 1000),
        )
        return payload

    def quest_payload(
        self,
        quest: dict[str, Any],
        *,
        observations: list[dict[str, Any]],
        photos_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        taxa = list(quest.get("taxa") or [])
        focus_ids = [
            int(item["taxon_id"])
            for item in sorted(
                [item for item in taxa if item.get("focus_order")],
                key=lambda item: int(item.get("focus_order") or 0),
            )
        ]
        collection = build_collection_index(observations, photos_by_id)
        progress = attach_collection_progress(taxa, collection, focus_taxon_ids=focus_ids)
        period_label = _period_label(tuple(quest.get("months") or []))
        progress["taxa"] = attach_discovery_reasons(
            progress["taxa"],
            area_name=str(quest.get("area_name") or "Selected area"),
            radius_km=int(quest.get("radius_km") or 10),
            period_label=period_label,
        )
        frozen_target_count = int(quest.get("target_count") or len(taxa))
        progress["progress"]["total_count"] = frozen_target_count
        progress["progress"]["remaining_count"] = max(
            frozen_target_count - int(progress["progress"]["collected_count"]),
            0,
        )
        focus_taxa = sorted(
            [item for item in progress["taxa"] if item.get("focus_order")],
            key=lambda item: int(item.get("focus_order") or 0),
        )
        focus_collected_count = sum(1 for item in focus_taxa if item.get("collected"))
        focus_progress = {
            "collected_count": focus_collected_count,
            "total_count": len(focus_taxa),
            "remaining_count": max(len(focus_taxa) - focus_collected_count, 0),
        }
        return {
            "id": str(quest.get("id") or ""),
            "title": str(quest.get("title") or "Field Quest"),
            "status": str(quest.get("status") or "active"),
            "linked_hike_id": quest.get("linked_hike_id"),
            "area": {
                "id": str(quest.get("location_id") or ""),
                "name": str(quest.get("area_name") or "Selected area"),
                "lat": quest.get("lat"),
                "lng": quest.get("lng"),
                "radius_km": quest.get("radius_km"),
            },
            "period": {
                "target_date": str(quest.get("target_date") or ""),
                "months": quest.get("months") or [],
                "label": period_label,
            },
            "filters": {"iconic_taxon": quest.get("iconic_taxon")},
            "created_at": quest.get("created_at"),
            "focus_taxa": focus_taxa,
            "focus_progress": focus_progress,
            **progress,
        }

    def quest_sightings_payload(
        self,
        quest: dict[str, Any],
        *,
        taxon_id: int,
        limit: int = DISCOVERY_OBSERVATION_LIMIT,
    ) -> dict[str, Any]:
        taxon = next(
            (
                item
                for item in (quest.get("taxa") or [])
                if int(item.get("taxon_id") or 0) == int(taxon_id)
            ),
            None,
        )
        if taxon is None:
            raise ValueError("Choose a species that belongs to this Field Quest.")
        try:
            lat = float(quest["lat"])
            lng = float(quest["lng"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("This Field Quest does not have a mappable area.") from exc

        months = tuple(int(month) for month in (quest.get("months") or []))
        if not months:
            try:
                months = seasonal_months(date.fromisoformat(str(quest.get("target_date") or "")))
            except ValueError as exc:
                raise ValueError("This Field Quest does not have a valid seasonal window.") from exc
        radius = normalize_radius(quest.get("radius_km") or 10)
        raw_payload = self.inat_client.fetch_species_observations(
            taxon_id=int(taxon_id),
            lat=lat,
            lng=lng,
            radius_km=radius,
            months=months,
            observed_after=self._observed_after(),
            limit=limit,
        )
        raw_results = raw_payload.get("results")
        if not isinstance(raw_results, list):
            raise InatRequestError("iNaturalist sightings returned an unexpected response.")
        sightings = [
            normalized
            for item in raw_results
            if isinstance(item, dict)
            for normalized in [_normalize_public_sighting(item)]
            if normalized is not None
        ]
        try:
            total_results = max(int(raw_payload.get("total_results") or len(sightings)), 0)
        except (TypeError, ValueError):
            total_results = len(sightings)
        return {
            "quest": {
                "id": str(quest.get("id") or ""),
                "title": str(quest.get("title") or "Field Quest"),
                "area_name": str(quest.get("area_name") or "Selected area"),
                "lat": round(lat, 4),
                "lng": round(lng, 4),
                "radius_km": radius,
                "period_label": _period_label(months),
            },
            "taxon": {
                "taxon_id": int(taxon_id),
                "common_name": str(taxon.get("common_name") or "Unknown species"),
                "scientific_name": str(taxon.get("scientific_name") or ""),
            },
            "total_results": total_results,
            "mapped_count": len(sightings),
            "limited": total_results > len(sightings),
            "sightings": sightings,
            "source": {
                "provider": "iNaturalist",
                "guidance": (
                    "Markers use locations iNaturalist makes public. Obscured markers are approximate, "
                    "and private coordinates are never exposed."
                ),
            },
        }

    def nearby_sightings_payload(
        self,
        *,
        area: dict[str, Any],
        target_date: date,
        radius_km: int | float,
        taxon_id: int,
        limit: int = DISCOVERY_OBSERVATION_LIMIT,
    ) -> dict[str, Any]:
        months = seasonal_months(target_date)
        return self.quest_sightings_payload(
            {
                "id": "",
                "title": "Nearby field list",
                "area_name": str(area.get("name") or "Selected area"),
                "lat": area.get("lat"),
                "lng": area.get("lng"),
                "radius_km": normalize_radius(radius_km),
                "target_date": target_date.isoformat(),
                "months": list(months),
                "taxa": [
                    {
                        "taxon_id": int(taxon_id),
                        "common_name": "Nearby species",
                        "scientific_name": "",
                    }
                ],
            },
            taxon_id=taxon_id,
            limit=limit,
        )

    def _observed_after(self) -> str:
        try:
            return self.now.date().replace(year=self.now.year - 10).isoformat()
        except ValueError:
            return self.now.date().replace(year=self.now.year - 10, day=28).isoformat()

    def _snapshot_is_fresh(self, snapshot: dict[str, Any]) -> bool:
        raw_expiry = snapshot.get("expires_at")
        if not raw_expiry:
            return False
        try:
            expires_at = datetime.fromisoformat(str(raw_expiry).replace("Z", "+00:00"))
        except ValueError:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at > self.now


def _period_label(months: tuple[int, ...] | list[int]) -> str:
    names = [
        date(2000, int(month), 1).strftime("%b")
        for month in months
        if isinstance(month, int) and 1 <= month <= 12
    ]
    return " · ".join(names)


def _normalize_public_sighting(item: dict[str, Any]) -> dict[str, Any] | None:
    geojson = item.get("geojson")
    coordinates = geojson.get("coordinates") if isinstance(geojson, dict) else None
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None
    try:
        lng = float(coordinates[0])
        lat = float(coordinates[1])
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None

    photos = item.get("photos")
    photo = photos[0] if isinstance(photos, list) and photos and isinstance(photos[0], dict) else {}
    user = item.get("user") if isinstance(item.get("user"), dict) else {}
    obscured = bool(
        item.get("obscured")
        or str(item.get("geoprivacy") or "").lower() == "obscured"
        or str(item.get("taxon_geoprivacy") or "").lower() == "obscured"
    )
    accuracy = item.get("positional_accuracy")
    try:
        accuracy_m = round(float(accuracy)) if accuracy is not None else None
    except (TypeError, ValueError):
        accuracy_m = None
    photo_url = str(photo.get("url") or "")
    if "/square." in photo_url:
        photo_url = photo_url.replace("/square.", "/medium.")
    observation_id = str(item.get("id") or "")
    return {
        "id": observation_id,
        "lat": lat,
        "lng": lng,
        "observed_on": str(item.get("observed_on") or ""),
        "place_guess": str(item.get("place_guess") or ""),
        "observer": str(user.get("login") or ""),
        "uri": str(item.get("uri") or f"https://www.inaturalist.org/observations/{observation_id}"),
        "photo_url": photo_url,
        "photo_attribution": str(photo.get("attribution") or ""),
        "photo_license_code": str(photo.get("license_code") or ""),
        "positional_accuracy_m": accuracy_m,
        "obscured": obscured,
    }
