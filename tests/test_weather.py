from datetime import UTC, datetime

import pytest
import requests

from hike_journal.services.weather import (
    OpenMeteoWeatherProvider,
    WeatherProviderError,
    build_weather_context,
    enrich_hike_weather,
)


class FakeResponse:
    def __init__(self, payload, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def recorded_context():
    return build_weather_context(
        {"id": "hike-1", "hike_date": "2026-08-09"},
        {
            "started_at": "2026-08-09T12:30:00Z",
            "duration_seconds": 7200,
            "track_geojson": {
                "type": "LineString",
                "coordinates": [[-82.2, 28.0], [-82.0, 28.2]],
            },
        },
    )


def hourly_payload():
    return {
        "latitude": 28.1,
        "longitude": -82.1,
        "elevation": 18,
        "utc_offset_seconds": 0,
        "hourly": {
            "time": ["2026-08-09T12:00", "2026-08-09T13:00", "2026-08-09T14:00", "2026-08-09T15:00"],
            "temperature_2m": [25, 27, 29, 31],
            "apparent_temperature": [27, 30, 33, 35],
            "relative_humidity_2m": [80, 74, 68, 64],
            "precipitation": [0.2, 0.0, 0.4, 1.0],
            "cloud_cover": [90, 75, 60, 40],
            "wind_speed_10m": [6, 8, 10, 12],
            "weather_code": [61, 3, 61, 2],
        },
    }


def test_route_weather_context_uses_centroid_and_actual_interval():
    context = recorded_context()

    assert context.latitude == 28.1
    assert context.longitude == -82.1
    assert context.ended_at.isoformat() == "2026-08-09T14:30:00+00:00"
    assert context.location_basis == "route centroid from 2 track points"
    assert context.time_basis == "recorded hike interval"


def test_open_meteo_summarizes_only_overlapping_hours_and_attributes_source():
    calls = []

    def request_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(hourly_payload())

    provider = OpenMeteoWeatherProvider(
        now=lambda: datetime(2026, 8, 10, tzinfo=UTC),
        request_get=request_get,
    )
    summary = provider.summarize(recorded_context())

    assert calls[0][0] == "https://api.open-meteo.com/v1/forecast"
    assert calls[0][1]["params"]["timezone"] == "UTC"
    assert summary["temperature_min_c"] == 25
    assert summary["temperature_mean_c"] == 27
    assert summary["temperature_max_c"] == 29
    assert summary["precipitation_total_mm"] == 0.6
    assert summary["condition_label"] == "Rain"
    assert len(summary["raw_response_json"]["samples"]) == 3
    assert summary["raw_response_json"]["attribution"]["license"] == "CC BY 4.0"


def test_open_meteo_uses_historical_endpoint_for_older_hikes():
    calls = []

    def request_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(hourly_payload())

    provider = OpenMeteoWeatherProvider(
        now=lambda: datetime(2026, 9, 1, tzinfo=UTC),
        request_get=request_get,
    )
    provider.summarize(recorded_context())

    assert calls == ["https://archive-api.open-meteo.com/v1/archive"]


def test_saved_place_fallback_uses_provider_local_day_and_stores_utc_interval():
    payload = hourly_payload()
    payload["utc_offset_seconds"] = -14_400
    payload["timezone"] = "America/New_York"
    context = build_weather_context(
        {"id": "hike-1", "hike_date": "2026-08-09"},
        None,
        {"lat": 28.1, "lng": -82.1},
    )
    calls = []

    def request_get(_url, **kwargs):
        calls.append(kwargs)
        return FakeResponse(payload)

    summary = OpenMeteoWeatherProvider(
        now=lambda: datetime(2026, 8, 10, tzinfo=UTC),
        request_get=request_get,
    ).summarize(context)

    assert calls[0]["params"]["timezone"] == "auto"
    assert summary["interval_started_at"] == "2026-08-09T04:00:00+00:00"
    assert summary["interval_ended_at"].startswith("2026-08-10T03:59:59")
    assert summary["raw_response_json"]["timezone"] == "America/New_York"


def test_weather_provider_failure_is_clear_and_retryable():
    provider = OpenMeteoWeatherProvider(
        request_get=lambda *_args, **_kwargs: FakeResponse({}, requests.ConnectionError("offline")),
    )

    with pytest.raises(WeatherProviderError, match="temporarily unavailable"):
        provider.summarize(recorded_context())


def test_weather_enrichment_is_idempotent_until_forced():
    class Repository:
        existing = {"hike_id": "hike-1", "condition_label": "Clear"}
        saved = []

        def get_hike_weather_snapshot(self, _hike_id):
            return self.existing

        def upsert_hike_weather_snapshot(self, payload):
            self.saved.append(payload)
            return payload

    class Provider:
        provider_name = "fake"

        def summarize(self, _context):
            return {"provider": "fake", "algorithm_version": "v1"}

    repository = Repository()
    existing = enrich_hike_weather(
        repository=repository,
        hike={"id": "hike-1"},
        route_import=None,
        location=None,
        provider=Provider(),
    )

    assert existing["condition_label"] == "Clear"
    assert repository.saved == []
