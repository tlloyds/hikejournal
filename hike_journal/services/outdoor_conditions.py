from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
from typing import Any, Callable, Mapping

import requests

from hike_journal.config import settings
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.weather import weather_condition_label


OUTDOOR_CONDITIONS_ALGORITHM_VERSION = "outdoor-conditions-v1"
USGS_GAGE_HEIGHT_PARAMETER_CODE = "00065"
NEARBY_WATER_GAUGE_RADIUS_MILES = 30.0
AUTOMATIC_WATER_GAUGE_LIMIT = 3


class OutdoorConditionsError(RuntimeError):
    pass


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _array_value(payload: Mapping[str, Any], name: str, index: int) -> Any:
    values = payload.get(name)
    return values[index] if isinstance(values, list) and index < len(values) else None


def _forecast_decimal(value: float | None) -> str:
    if value is None:
        return "0"
    return f"{value:.2f}" if value < 1 else f"{value:.1f}"


def build_weather_planning_notes(forecast: Mapping[str, Any]) -> list[str]:
    days = forecast.get("days") if isinstance(forecast.get("days"), list) else []
    today = days[0] if days and isinstance(days[0], Mapping) else {}
    notes: list[str] = []
    feels_like = _number(today.get("apparent_temperature_max_f")) or _number(
        forecast.get("apparent_temperature_f")
    )
    if feels_like is not None and feels_like >= 100:
        notes.append(
            f"Plan a cooler, earlier outing: the peak feels-like temperature is near {round(feels_like)}°F."
        )
    elif feels_like is not None and feels_like >= 90:
        notes.append(
            f"Hot trail conditions are likely; the peak feels-like temperature is near {round(feels_like)}°F."
        )
    rain_chance = _number(today.get("precipitation_probability_percent"))
    rain_total = _number(today.get("precipitation_total_inches"))
    if (rain_chance or 0) >= 50 or (rain_total or 0) >= 0.25:
        notes.append(
            "Rain may materially change footing and water crossings "
            f"({round(rain_chance or 0)}% chance, {_forecast_decimal(rain_total)} in forecast)."
        )
    gust = _number(today.get("wind_gust_max_mph"))
    if (gust or 0) >= 25:
        notes.append(f"Gusts near {round(gust or 0)} mph could affect exposed sections and tree cover.")
    uv_index = _number(today.get("uv_index_max"))
    if (uv_index or 0) >= 8:
        notes.append(
            f"Peak UV is very high near {_forecast_decimal(uv_index)}; plan sun protection and limit exposed midday time."
        )
    if not notes:
        notes.append("No major heat, rain, wind, or UV signal stands out in today’s forecast.")
    return notes[:3]


def parse_place_forecast(payload: Mapping[str, Any]) -> dict[str, Any]:
    current = payload.get("current") if isinstance(payload.get("current"), Mapping) else {}
    daily = payload.get("daily") if isinstance(payload.get("daily"), Mapping) else {}
    dates = daily.get("time") if isinstance(daily.get("time"), list) else []
    days = []
    for index, value in enumerate(dates):
        code = _number(_array_value(daily, "weather_code", index))
        days.append(
            {
                "date": str(value or ""),
                "condition_label": weather_condition_label(int(code) if code is not None else None),
                "temperature_max_f": _number(_array_value(daily, "temperature_2m_max", index)),
                "temperature_min_f": _number(_array_value(daily, "temperature_2m_min", index)),
                "apparent_temperature_max_f": _number(
                    _array_value(daily, "apparent_temperature_max", index)
                ),
                "precipitation_probability_percent": _number(
                    _array_value(daily, "precipitation_probability_max", index)
                ),
                "precipitation_total_inches": _number(
                    _array_value(daily, "precipitation_sum", index)
                ),
                "wind_speed_max_mph": _number(_array_value(daily, "wind_speed_10m_max", index)),
                "wind_gust_max_mph": _number(_array_value(daily, "wind_gusts_10m_max", index)),
                "uv_index_max": _number(_array_value(daily, "uv_index_max", index)),
                "sunrise": _array_value(daily, "sunrise", index),
                "sunset": _array_value(daily, "sunset", index),
            }
        )
    current_code = _number(current.get("weather_code"))
    forecast = {
        "observed_at": str(current.get("time") or "") or None,
        "timezone": str(payload.get("timezone") or ""),
        "temperature_f": _number(current.get("temperature_2m")),
        "apparent_temperature_f": _number(current.get("apparent_temperature")),
        "relative_humidity_percent": _number(current.get("relative_humidity_2m")),
        "precipitation_inches": _number(current.get("precipitation")),
        "cloud_cover_percent": _number(current.get("cloud_cover")),
        "wind_speed_mph": _number(current.get("wind_speed_10m")),
        "wind_gust_mph": _number(current.get("wind_gusts_10m")),
        "condition_label": weather_condition_label(
            int(current_code) if current_code is not None else None
        ),
        "days": days,
        "planning_notes": [],
    }
    forecast["planning_notes"] = build_weather_planning_notes(forecast)
    return forecast


def _distance_miles(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    earth_radius_miles = 3958.8
    latitude_delta = math.radians(lat_b - lat_a)
    longitude_delta = math.radians(lng_b - lng_a)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(math.radians(lat_a))
        * math.cos(math.radians(lat_b))
        * math.sin(longitude_delta / 2) ** 2
    )
    return earth_radius_miles * 2 * math.asin(math.sqrt(min(1, max(0, haversine))))


def _friendly_gauge_name(value: str) -> str:
    text = value.rsplit(", ", 1)[0].strip().lower()
    small_words = {"at", "above", "below", "near", "of", "the"}
    words = []
    for index, word in enumerate(text.split()):
        words.append(word if index > 0 and word in small_words else word.capitalize())
    return " ".join(words)


def parse_nearby_river_gauges(
    latest_payload: Mapping[str, Any],
    metadata_payload: Mapping[str, Any],
    *,
    origin_latitude: float,
    origin_longitude: float,
    radius_miles: float = NEARBY_WATER_GAUGE_RADIUS_MILES,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    names: dict[str, str] = {}
    metadata = metadata_payload.get("features")
    for feature in metadata if isinstance(metadata, list) else []:
        properties = feature.get("properties") if isinstance(feature, Mapping) else None
        if not isinstance(properties, Mapping):
            continue
        site_id = str(properties.get("id") or "").upper()
        if site_id:
            names[site_id] = _friendly_gauge_name(
                str(properties.get("monitoring_location_name") or site_id)
            )

    instant = (now or datetime.now(UTC)).astimezone(UTC)
    latest_by_site: dict[str, dict[str, Any]] = {}
    features = latest_payload.get("features")
    for feature in features if isinstance(features, list) else []:
        if not isinstance(feature, Mapping):
            continue
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
            continue
        site_id = str(properties.get("monitoring_location_id") or "").upper()
        if not site_id.startswith("USGS-"):
            continue
        observed_at = str(properties.get("time") or "")
        try:
            observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            continue
        if observed < instant - timedelta(days=7) or observed > instant + timedelta(days=1):
            continue
        height = _number(properties.get("value"))
        coordinates = geometry.get("coordinates")
        if height is None or str(properties.get("unit_of_measure") or "").lower() != "ft":
            continue
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            continue
        longitude = _number(coordinates[0])
        latitude = _number(coordinates[1])
        if latitude is None or longitude is None:
            continue
        distance = _distance_miles(
            origin_latitude, origin_longitude, latitude, longitude
        )
        if distance > radius_miles:
            continue
        candidate = {
            "gauge": {
                "site_id": site_id,
                "name": names.get(site_id, site_id),
                "lat": latitude,
                "lng": longitude,
                "enabled": True,
                "suggested": True,
            },
            "distance_miles": distance,
            "current_height_feet": height,
            "observed_at": observed_at,
            "provisional": str(properties.get("approval_status") or "").lower() != "approved",
        }
        existing = latest_by_site.get(site_id)
        if existing is None or observed_at > str(existing.get("observed_at") or ""):
            latest_by_site[site_id] = candidate
    return sorted(
        latest_by_site.values(),
        key=lambda item: (float(item["distance_miles"]), str(item["gauge"]["name"])),
    )[:30]


def parse_river_gauge_series(
    payload: Mapping[str, Any],
    *,
    gauge: Mapping[str, Any],
    period_days: int,
    place_latitude: float,
    place_longitude: float,
) -> dict[str, Any]:
    by_series: dict[str, list[dict[str, Any]]] = {}
    features = payload.get("features")
    for feature in features if isinstance(features, list) else []:
        properties = feature.get("properties") if isinstance(feature, Mapping) else None
        if not isinstance(properties, Mapping):
            continue
        observed_at = str(properties.get("time") or "")
        height = _number(properties.get("value"))
        if not observed_at or height is None:
            continue
        series_id = str(properties.get("time_series_id") or "default")
        by_series.setdefault(series_id, []).append(
            {
                "observed_at": observed_at,
                "height_feet": height,
                "provisional": str(properties.get("approval_status") or "").lower()
                != "approved",
            }
        )
    readings = max(by_series.values(), key=len, default=[])
    readings_by_time = {str(item["observed_at"]): item for item in readings}
    readings = [readings_by_time[key] for key in sorted(readings_by_time)]
    if not readings:
        raise OutdoorConditionsError(
            f"No water-height readings were reported for {gauge.get('name') or 'this gauge'} in the last {period_days} days."
        )
    return {
        "gauge": dict(gauge),
        "period_days": period_days,
        "readings": readings,
        "distance_miles": _distance_miles(
            place_latitude,
            place_longitude,
            float(gauge["lat"]),
            float(gauge["lng"]),
        ),
        "error_message": None,
    }


class OutdoorConditionsService:
    def __init__(
        self,
        repository: HikeJournalRepository,
        *,
        now: Callable[[], datetime] | None = None,
        request_get: Callable[..., Any] = requests.get,
    ) -> None:
        self.repository = repository
        self.now = now or (lambda: datetime.now(UTC))
        self.request_get = request_get

    def forecast(self, latitude: float, longitude: float) -> dict[str, Any]:
        key = self._cache_key("forecast", round(latitude, 3), round(longitude, 3))
        cached = self._fresh_or_stale(key)
        if cached[0] is not None:
            return cached[0]
        params: dict[str, Any] = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "timezone": "auto",
            "forecast_days": 7,
            "temperature_unit": "fahrenheit",
            "precipitation_unit": "inch",
            "wind_speed_unit": "mph",
            "current": (
                "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,"
                "weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
                "apparent_temperature_min,sunrise,sunset,uv_index_max,precipitation_sum,"
                "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max"
            ),
        }
        if settings.open_meteo_api_key:
            params["apikey"] = settings.open_meteo_api_key
        try:
            payload = self._request_json(
                settings.open_meteo_forecast_url,
                params=params,
                provider="Open-Meteo",
            )
            value = parse_place_forecast(payload)
            self._store(key, "forecast", value, timedelta(minutes=settings.outdoor_forecast_cache_minutes))
            return value
        except OutdoorConditionsError:
            if cached[1] is not None:
                return cached[1]
            raise

    def nearby_gauges(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float = NEARBY_WATER_GAUGE_RADIUS_MILES,
    ) -> list[dict[str, Any]]:
        key = self._cache_key(
            "nearby-usgs", round(latitude, 3), round(longitude, 3), round(radius_miles, 1)
        )
        cached = self._fresh_or_stale(key)
        if cached[0] is not None:
            return list(cached[0])
        latitude_delta = radius_miles / 69
        longitude_delta = radius_miles / (69 * max(0.2, math.cos(math.radians(latitude))))
        bbox = ",".join(
            f"{value:.5f}"
            for value in (
                longitude - longitude_delta,
                latitude - latitude_delta,
                longitude + longitude_delta,
                latitude + latitude_delta,
            )
        )
        root = settings.usgs_water_api_root.rstrip("/")
        try:
            latest = self._request_json(
                f"{root}/latest-continuous/items",
                params={
                    "f": "json",
                    "bbox": bbox,
                    "parameter_code": USGS_GAGE_HEIGHT_PARAMETER_CODE,
                    "limit": 1000,
                },
                provider="USGS",
            )
            metadata = self._request_json(
                f"{root}/monitoring-locations/items",
                params={
                    "f": "json",
                    "bbox": bbox,
                    "agency_code": "USGS",
                    "limit": 10000,
                    "properties": "id,monitoring_location_name",
                },
                provider="USGS",
            )
            value = parse_nearby_river_gauges(
                latest,
                metadata,
                origin_latitude=latitude,
                origin_longitude=longitude,
                radius_miles=radius_miles,
                now=self.now(),
            )
            self._store(
                key,
                "nearby_usgs",
                value,
                timedelta(minutes=settings.outdoor_usgs_cache_minutes),
            )
            return value
        except OutdoorConditionsError:
            if cached[1] is not None:
                return list(cached[1])
            raise

    def gauge_series(
        self,
        gauge: Mapping[str, Any],
        *,
        period_days: int,
        place_latitude: float,
        place_longitude: float,
    ) -> dict[str, Any]:
        days = 30 if period_days >= 30 else 7
        site_id = str(gauge.get("site_id") or "").upper()
        key = self._cache_key("usgs-series", site_id, days)
        cached = self._fresh_or_stale(key)
        if cached[0] is not None:
            value = dict(cached[0])
            value["distance_miles"] = _distance_miles(
                place_latitude,
                place_longitude,
                float(gauge["lat"]),
                float(gauge["lng"]),
            )
            return value
        started_at = (self.now().astimezone(UTC) - timedelta(days=days)).isoformat()
        root = settings.usgs_water_api_root.rstrip("/")
        try:
            payload = self._request_json(
                f"{root}/continuous/items",
                params={
                    "f": "json",
                    "monitoring_location_id": site_id,
                    "parameter_code": USGS_GAGE_HEIGHT_PARAMETER_CODE,
                    "datetime": f"{started_at}/..",
                    "limit": 10000,
                    "properties": (
                        "time_series_id,monitoring_location_id,time,value,unit_of_measure,"
                        "approval_status,qualifier"
                    ),
                },
                provider="USGS",
            )
            value = parse_river_gauge_series(
                payload,
                gauge=gauge,
                period_days=days,
                place_latitude=place_latitude,
                place_longitude=place_longitude,
            )
            self._store(
                key,
                "usgs_series",
                value,
                timedelta(minutes=settings.outdoor_usgs_cache_minutes),
            )
            return value
        except OutdoorConditionsError:
            if cached[1] is not None:
                return dict(cached[1])
            raise

    def place_conditions(
        self,
        latitude: float,
        longitude: float,
        *,
        period_days: int = 7,
        followed_site_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        forecast: dict[str, Any] | None = None
        forecast_error: str | None = None
        try:
            forecast = self.forecast(latitude, longitude)
        except OutdoorConditionsError as exc:
            forecast_error = str(exc)
        gauges: list[dict[str, Any]] = []
        try:
            nearby = self.nearby_gauges(latitude, longitude)
            followed = {
                str(value or "").strip().upper()
                for value in (followed_site_ids or [])
                if str(value or "").strip().upper().startswith("USGS-")
            }
            selected: list[dict[str, Any]] = list(nearby[:AUTOMATIC_WATER_GAUGE_LIMIT])
            selected_ids = {
                str((item.get("gauge") or {}).get("site_id") or "").upper()
                for item in selected
                if isinstance(item, Mapping) and isinstance(item.get("gauge"), Mapping)
            }
            selected.extend(
                item
                for item in nearby
                if isinstance(item, Mapping)
                and isinstance(item.get("gauge"), Mapping)
                and str(item["gauge"].get("site_id") or "").upper() in followed
                and str(item["gauge"].get("site_id") or "").upper() not in selected_ids
            )
            for item in selected[:10]:
                gauge = item.get("gauge") if isinstance(item, Mapping) else None
                if not isinstance(gauge, Mapping):
                    continue
                try:
                    gauges.append(
                        self.gauge_series(
                            gauge,
                            period_days=period_days,
                            place_latitude=latitude,
                            place_longitude=longitude,
                        )
                    )
                except OutdoorConditionsError as exc:
                    gauges.append(
                        {
                            "gauge": dict(gauge),
                            "period_days": 30 if period_days >= 30 else 7,
                            "readings": [],
                            "distance_miles": item.get("distance_miles"),
                            "error_message": str(exc),
                        }
                    )
        except OutdoorConditionsError:
            pass
        return {
            "forecast": forecast,
            "river_gauges": gauges,
            "live_conditions_notice": forecast_error,
        }

    def _request_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        provider: str,
    ) -> dict[str, Any]:
        try:
            response = self.request_get(
                url,
                params=dict(params),
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HikeJournal/1.0 (outdoor planning)",
                },
                timeout=settings.weather_request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            raise OutdoorConditionsError(
                f"{provider} conditions are temporarily unavailable."
            ) from exc
        if not isinstance(payload, dict):
            raise OutdoorConditionsError(f"{provider} returned an unreadable response.")
        return payload

    def _fresh_or_stale(self, key: str) -> tuple[Any | None, Any | None]:
        getter = getattr(self.repository, "get_outdoor_condition_snapshot", None)
        snapshot = getter(key) if callable(getter) else None
        if not snapshot:
            return None, None
        payload = snapshot.get("payload")
        expires_at = str(snapshot.get("expires_at") or "")
        try:
            expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            expires = datetime.min.replace(tzinfo=UTC)
        return (payload if expires > self.now().astimezone(UTC) else None, payload)

    def _store(self, key: str, kind: str, payload: Any, lifetime: timedelta) -> None:
        collected_at = self.now().astimezone(UTC)
        writer = getattr(self.repository, "upsert_outdoor_condition_snapshot", None)
        if not callable(writer):
            return
        writer(
            {
                "cache_key": key,
                "kind": kind,
                "algorithm_version": OUTDOOR_CONDITIONS_ALGORITHM_VERSION,
                "payload": payload,
                "collected_at": collected_at.isoformat(),
                "expires_at": (collected_at + lifetime).isoformat(),
            }
        )

    @staticmethod
    def _cache_key(kind: str, *parts: Any) -> str:
        serialized = json.dumps(
            [OUTDOOR_CONDITIONS_ALGORITHM_VERSION, kind, *parts],
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
