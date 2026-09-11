"""Small USDA PLANTS client used as a conservative plant-status fallback."""

from __future__ import annotations

from html import unescape
import re
from typing import Any, Callable
from urllib.parse import urljoin

import requests

from hike_journal.config import settings


PLANT_STATUS_RANKS = {
    "species",
    "subspecies",
    "variety",
    "form",
    "hybrid",
    "infrahybrid",
}


class USDAPlantRequestError(RuntimeError):
    """Raised when USDA PLANTS returns an unusable response."""


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", str(value or "")))).strip()


def _tokens(value: Any) -> list[str]:
    return _text(value).casefold().split()


def _scientific_match(candidate: dict[str, Any], query: str) -> bool:
    query_tokens = _tokens(query)
    candidate_tokens = _tokens(candidate.get("ScientificName"))
    return bool(query_tokens) and candidate_tokens[: len(query_tokens)] == query_tokens


class USDAPlantsClient:
    """Resolve an exact plant name to its Florida nativity record."""

    def __init__(
        self,
        *,
        api_base_url: str | None = None,
        map_query_url: str | None = None,
        plants_base_url: str | None = None,
        state_name: str | None = None,
        request: Callable[..., requests.Response] | None = None,
    ) -> None:
        self.api_base_url = (api_base_url or settings.usda_plants_api_url).rstrip("/") + "/"
        self.map_query_url = map_query_url or settings.usda_plants_map_query_url
        self.plants_base_url = (plants_base_url or settings.usda_plants_base_url).rstrip("/") + "/"
        self.state_name = (state_name or settings.usda_plants_state_name).strip() or "Florida"
        self._request = request or requests.get
        self.user_agent = "HikeJournal/1.0 (plant ecology fallback)"

    def fetch_status(
        self,
        *,
        scientific_name: str,
        common_name: str | None = None,
        rank: str | None = None,
    ) -> dict[str, Any] | None:
        """Return a status only when USDA gives one clear answer for the region."""
        normalized_rank = _text(rank).casefold()
        if normalized_rank not in PLANT_STATUS_RANKS:
            return None
        plant = self._find_plant(scientific_name)
        if plant is None and common_name:
            plant = self._find_plant(common_name, common_name_query=True)
        if not plant or not plant.get("Symbol"):
            return None

        profile = self._get_json(
            "PlantProfile",
            params={"symbol": str(plant["Symbol"])},
        )
        plant_id = profile.get("Id")
        if plant_id in (None, ""):
            return None

        state_statuses = self._state_statuses(int(plant_id))
        status = state_statuses[0] if len(state_statuses) == 1 else None
        if status is None and not state_statuses:
            # Some current profiles do not have a Florida distribution row,
            # but do explicitly mark the plant as introduced throughout L48.
            # Native L48 status is not enough to claim Florida nativity.
            status = self._unambiguous_l48_introduction(profile)
        if status not in {"native", "introduced"}:
            return None

        return {
            "label": "native" if status == "native" else "non_native",
            "establishment_status": status,
            "invasive_status": "unknown",
            "establishment_means": status,
            "source": "usda_plants",
            "source_url": urljoin(self.plants_base_url, f"plant-profile/{plant['Symbol']}"),
            "place_name": self.state_name,
            "usda_plant_id": int(plant_id),
            "usda_symbol": str(plant["Symbol"]),
            "usda_state_status": status,
        }

    def _find_plant(
        self,
        query: str,
        *,
        common_name_query: bool = False,
    ) -> dict[str, Any] | None:
        if not _text(query):
            return None
        results = self._get_json("PlantSearch", params={"searchText": query})
        raw_results = results if isinstance(results, list) else []
        plants = [
            item.get("Plant")
            for item in raw_results
            if isinstance(item, dict) and isinstance(item.get("Plant"), dict)
        ]
        if not plants:
            return None
        if common_name_query:
            normalized_query = _text(query).casefold()
            exact_common = [
                plant
                for plant in plants
                if _text(plant.get("CommonName")).casefold() == normalized_query
            ]
            return exact_common[0] if len(exact_common) == 1 else None

        matches = [plant for plant in plants if _scientific_match(plant, query)]
        if not matches:
            return None
        # Search results can put a hybrid or a synonym before the exact
        # species. Prefer the shortest non-hybrid scientific name.
        return min(
            matches,
            key=lambda plant: (
                "×" in _text(plant.get("ScientificName"))
                or " x " in f" {_text(plant.get('ScientificName')).casefold()} ",
                len(_tokens(plant.get("ScientificName"))),
            ),
        )

    def _state_statuses(self, plant_id: int) -> list[str]:
        payload = self._get_json(
            self.map_query_url,
            params={
                "where": (
                    f"plant_master_id={plant_id} AND "
                    f"country_subdivision_name='{self.state_name.replace(chr(39), chr(39) * 2)}'"
                ),
                "outFields": "plant_nativity_id,country_subdivision_name,Symbol",
                "returnGeometry": "false",
                "resultRecordCount": "100",
                "f": "json",
            },
            absolute=True,
        )
        statuses = {
            _text((feature.get("attributes") or {}).get("Symbol")).casefold()
            for feature in (payload.get("features") or [])
            if isinstance(feature, dict)
        }
        return sorted(status for status in statuses if status in {"native", "introduced", "both"})

    @staticmethod
    def _unambiguous_l48_introduction(profile: dict[str, Any]) -> str | None:
        statuses = {
            _text(item.get("Type")).casefold()
            for item in profile.get("NativeStatuses") or []
            if isinstance(item, dict) and _text(item.get("Region")).casefold() == "l48"
        }
        return "introduced" if statuses == {"introduced"} else None

    def _get_json(
        self,
        endpoint: str,
        *,
        params: dict[str, Any],
        absolute: bool = False,
    ) -> Any:
        url = endpoint if absolute else urljoin(self.api_base_url, endpoint)
        try:
            response = self._request(
                url,
                params=params,
                headers={"Accept": "application/json", "User-Agent": self.user_agent},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, TypeError) as exc:
            raise USDAPlantRequestError(f"USDA PLANTS request failed: {exc}") from exc
        if not isinstance(payload, (dict, list)):
            raise USDAPlantRequestError("USDA PLANTS returned an unexpected response.")
        return payload
