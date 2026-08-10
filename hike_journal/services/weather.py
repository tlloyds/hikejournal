from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from statistics import fmean
from typing import Any, Callable, Protocol

import requests


OPEN_METEO_PROVIDER = "open-meteo"
WEATHER_ALGORITHM_VERSION = "route-centroid-interval-v1"
OPEN_METEO_ATTRIBUTION_URL = "https://open-meteo.com/"
OPEN_METEO_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
HOURLY_VARIABLES = (
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "weather_code",
)


class WeatherProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class WeatherContext:
    latitude: float
    longitude: float
    started_at: datetime
    ended_at: datetime
    location_basis: str
    time_basis: str
    full_local_day: bool = False


class WeatherProvider(Protocol):
    provider_name: str

    def summarize(self, context: WeatherContext) -> dict[str, Any]: ...


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _route_points(route_import: dict[str, Any] | None) -> list[tuple[float, float]]:
    geojson = (route_import or {}).get("track_geojson") or {}
    coordinates = geojson.get("coordinates") if isinstance(geojson, dict) else None
    if not isinstance(coordinates, list):
        return []
    segments = coordinates if geojson.get("type") == "MultiLineString" else [coordinates]
    points: list[tuple[float, float]] = []
    for segment in segments:
        if not isinstance(segment, list):
            continue
        for coordinate in segment:
            if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
                continue
            try:
                longitude = float(coordinate[0])
                latitude = float(coordinate[1])
            except (TypeError, ValueError):
                continue
            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                points.append((latitude, longitude))
    return points


def build_weather_context(
    hike: dict[str, Any],
    route_import: dict[str, Any] | None,
    location: dict[str, Any] | None = None,
) -> WeatherContext:
    points = _route_points(route_import)
    if points:
        latitude = fmean(point[0] for point in points)
        longitude = fmean(point[1] for point in points)
        location_basis = f"route centroid from {len(points)} track points"
    else:
        try:
            latitude = float((location or {}).get("lat"))
            longitude = float((location or {}).get("lng"))
        except (TypeError, ValueError) as exc:
            raise WeatherProviderError("Weather needs a recorded route or a saved place with coordinates.") from exc
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise WeatherProviderError("The saved place does not have valid weather coordinates.")
        location_basis = "saved place coordinate"

    started_at = _parse_datetime((route_import or {}).get("started_at"))
    try:
        duration_seconds = int((route_import or {}).get("duration_seconds") or 0)
    except (TypeError, ValueError):
        duration_seconds = 0
    if started_at is not None and duration_seconds > 0:
        ended_at = started_at + timedelta(seconds=duration_seconds)
        time_basis = "recorded hike interval"
        full_local_day = False
    else:
        try:
            hike_date = date.fromisoformat(str(hike.get("hike_date") or "")[:10])
        except ValueError as exc:
            raise WeatherProviderError("Weather needs a recorded route time or hike date.") from exc
        started_at = datetime.combine(hike_date, time.min, tzinfo=UTC)
        ended_at = datetime.combine(hike_date, time.max, tzinfo=UTC)
        time_basis = "full hike date in the weather grid's local timezone"
        full_local_day = True

    return WeatherContext(
        latitude=round(latitude, 5),
        longitude=round(longitude, 5),
        started_at=started_at,
        ended_at=ended_at,
        location_basis=location_basis,
        time_basis=time_basis,
        full_local_day=full_local_day,
    )


def weather_condition_label(code: int | float | None) -> str:
    try:
        normalized = int(code) if code is not None else -1
    except (TypeError, ValueError):
        normalized = -1
    if normalized == 0:
        return "Clear"
    if normalized in {1, 2}:
        return "Partly cloudy"
    if normalized == 3:
        return "Overcast"
    if normalized in {45, 48}:
        return "Foggy"
    if normalized in {51, 53, 55, 56, 57}:
        return "Drizzle"
    if normalized in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "Rain"
    if normalized in {71, 73, 75, 77, 85, 86}:
        return "Snow"
    if normalized in {95, 96, 99}:
        return "Thunderstorms"
    return "Conditions recorded"


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _mean(values: list[float]) -> float | None:
    return round(fmean(values), 2) if values else None


class OpenMeteoWeatherProvider:
    provider_name = OPEN_METEO_PROVIDER

    def __init__(
        self,
        *,
        forecast_url: str = "https://api.open-meteo.com/v1/forecast",
        archive_url: str = "https://archive-api.open-meteo.com/v1/archive",
        api_key: str = "",
        timeout_seconds: float = 20,
        now: Callable[[], datetime] | None = None,
        request_get: Callable[..., Any] = requests.get,
    ) -> None:
        self.forecast_url = forecast_url.rstrip("/")
        self.archive_url = archive_url.rstrip("/")
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.now = now or (lambda: datetime.now(UTC))
        self.request_get = request_get

    def summarize(self, context: WeatherContext) -> dict[str, Any]:
        recent_cutoff = self.now().astimezone(UTC) - timedelta(days=5)
        use_forecast_archive = context.ended_at >= recent_cutoff
        endpoint = self.forecast_url if use_forecast_archive else self.archive_url
        dataset = "forecast_best_match" if use_forecast_archive else "historical_archive_best_match"
        params: dict[str, Any] = {
            "latitude": context.latitude,
            "longitude": context.longitude,
            "start_date": context.started_at.date().isoformat(),
            "end_date": context.ended_at.date().isoformat(),
            "hourly": ",".join(HOURLY_VARIABLES),
            "timezone": "auto" if context.full_local_day else "UTC",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        }
        if self.api_key:
            params["apikey"] = self.api_key
        try:
            response = self.request_get(endpoint, params=params, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, TypeError) as exc:
            raise WeatherProviderError("Open-Meteo weather data is temporarily unavailable.") from exc
        if not isinstance(payload, dict):
            raise WeatherProviderError("Open-Meteo returned an unreadable weather response.")
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        if not isinstance(hourly, dict) or not isinstance(times, list) or not times:
            raise WeatherProviderError("Open-Meteo returned no hourly weather for this hike.")

        parsed_times = [_parse_datetime(value) for value in times]
        if context.full_local_day:
            selected = [
                index
                for index, value in enumerate(times)
                if str(value)[:10] == context.started_at.date().isoformat()
            ]
        else:
            selected = [
                index
                for index, observed_at in enumerate(parsed_times)
                if observed_at is not None
                and observed_at <= context.ended_at
                and observed_at + timedelta(hours=1) >= context.started_at
            ]
        if not selected:
            valid = [(index, observed_at) for index, observed_at in enumerate(parsed_times) if observed_at]
            if valid:
                selected = [min(valid, key=lambda pair: abs(pair[1] - context.started_at))[0]]
        if not selected:
            raise WeatherProviderError("Open-Meteo returned no usable hourly weather for this hike.")

        def values(name: str) -> list[float]:
            series = hourly.get(name) or []
            if not isinstance(series, list):
                return []
            return [number for index in selected if index < len(series) if (number := _number(series[index])) is not None]

        temperatures = values("temperature_2m")
        apparent = values("apparent_temperature")
        humidity = values("relative_humidity_2m")
        precipitation = values("precipitation")
        cloud_cover = values("cloud_cover")
        wind_speed = values("wind_speed_10m")
        weather_codes = [int(value) for value in values("weather_code")]
        if not any((temperatures, apparent, humidity, precipitation, cloud_cover, wind_speed, weather_codes)):
            raise WeatherProviderError("Open-Meteo returned empty weather measurements for this hike.")
        representative_code = Counter(weather_codes).most_common(1)[0][0] if weather_codes else None

        samples = []
        for index in selected:
            sample = {"time": times[index] if index < len(times) else None}
            for name in HOURLY_VARIABLES:
                series = hourly.get(name) or []
                sample[name] = series[index] if isinstance(series, list) and index < len(series) else None
            samples.append(sample)
        interval_started_at = context.started_at
        interval_ended_at = context.ended_at
        if context.full_local_day:
            try:
                offset_seconds = int(payload.get("utc_offset_seconds") or 0)
            except (TypeError, ValueError):
                offset_seconds = 0
            local_zone = timezone(timedelta(seconds=offset_seconds))
            interval_started_at = datetime.combine(
                context.started_at.date(),
                time.min,
                tzinfo=local_zone,
            ).astimezone(UTC)
            interval_ended_at = datetime.combine(
                context.started_at.date(),
                time.max,
                tzinfo=local_zone,
            ).astimezone(UTC)
        return {
            "provider": self.provider_name,
            "provider_dataset": dataset,
            "algorithm_version": WEATHER_ALGORITHM_VERSION,
            "anchor_lat": context.latitude,
            "anchor_lng": context.longitude,
            "interval_started_at": interval_started_at.isoformat(),
            "interval_ended_at": interval_ended_at.isoformat(),
            "temperature_min_c": round(min(temperatures), 2) if temperatures else None,
            "temperature_mean_c": _mean(temperatures),
            "temperature_max_c": round(max(temperatures), 2) if temperatures else None,
            "apparent_temperature_mean_c": _mean(apparent),
            "precipitation_total_mm": round(sum(precipitation), 2) if precipitation else None,
            "relative_humidity_mean_percent": _mean(humidity),
            "cloud_cover_mean_percent": _mean(cloud_cover),
            "wind_speed_mean_kph": _mean(wind_speed),
            "condition_label": weather_condition_label(representative_code),
            "raw_response_json": {
                "location_basis": context.location_basis,
                "time_basis": context.time_basis,
                "grid_latitude": payload.get("latitude"),
                "grid_longitude": payload.get("longitude"),
                "elevation_meters": payload.get("elevation"),
                "utc_offset_seconds": payload.get("utc_offset_seconds"),
                "timezone": payload.get("timezone"),
                "samples": samples,
                "attribution": {
                    "name": "Open-Meteo",
                    "url": OPEN_METEO_ATTRIBUTION_URL,
                    "license": "CC BY 4.0",
                    "license_url": OPEN_METEO_LICENSE_URL,
                    "modified": "Hourly values summarized over the documented hike interval.",
                },
            },
        }


def enrich_hike_weather(
    *,
    repository: Any,
    hike: dict[str, Any],
    route_import: dict[str, Any] | None,
    location: dict[str, Any] | None,
    provider: WeatherProvider,
    force: bool = False,
) -> dict[str, Any]:
    hike_id = str(hike.get("id") or "")
    if not hike_id:
        raise WeatherProviderError("Weather enrichment needs a saved hike.")
    existing = repository.get_hike_weather_snapshot(hike_id)
    if existing and not force:
        return existing
    context = build_weather_context(hike, route_import, location)
    snapshot = provider.summarize(context)
    return repository.upsert_hike_weather_snapshot(
        {
            **snapshot,
            "hike_id": hike_id,
            "owner_subject": hike.get("owner_subject"),
            "owner_email": hike.get("owner_email"),
        }
    )
