from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

from hike_journal.services.outdoor_conditions import (
    OutdoorConditionsError,
    OutdoorConditionsService,
    parse_nearby_river_gauges,
    parse_place_forecast,
    parse_river_gauge_series,
)


NOW = datetime(2026, 8, 22, 12, tzinfo=UTC)


class CacheRepository:
    def __init__(self) -> None:
        self.snapshots = {}

    def get_outdoor_condition_snapshot(self, key):
        return self.snapshots.get(key)

    def upsert_outdoor_condition_snapshot(self, payload):
        self.snapshots[payload["cache_key"]] = dict(payload)
        return payload


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def forecast_payload():
    return {
        "timezone": "America/New_York",
        "current": {
            "time": "2026-08-22T08:00",
            "temperature_2m": 88,
            "apparent_temperature": 94,
            "relative_humidity_2m": 73,
            "precipitation": 0,
            "weather_code": 1,
            "cloud_cover": 31,
            "wind_speed_10m": 8,
            "wind_gusts_10m": 14,
        },
        "daily": {
            "time": ["2026-08-22"],
            "weather_code": [1],
            "temperature_2m_max": [92],
            "temperature_2m_min": [75],
            "apparent_temperature_max": [101],
            "precipitation_probability_max": [70],
            "precipitation_sum": [0.3],
            "wind_speed_10m_max": [11],
            "wind_gusts_10m_max": [27],
            "uv_index_max": [9],
            "sunrise": ["2026-08-22T06:58"],
            "sunset": ["2026-08-22T20:01"],
        },
    }


def test_forecast_parser_matches_mobile_contract_and_limits_planning_notes():
    value = parse_place_forecast(forecast_payload())

    assert value["condition_label"] == "Partly cloudy"
    assert value["days"][0]["temperature_max_f"] == 92
    assert len(value["planning_notes"]) == 3
    assert "cooler, earlier" in value["planning_notes"][0]
    assert "footing" in value["planning_notes"][1]


def test_nearby_gauge_parser_filters_age_units_and_radius():
    metadata = {
        "features": [
            {
                "properties": {
                    "id": "USGS-02300000",
                    "monitoring_location_name": "RIVER AT OAK FLAT, FL",
                }
            }
        ]
    }
    latest = {
        "features": [
            {
                "geometry": {"coordinates": [-81.21, 28.11]},
                "properties": {
                    "monitoring_location_id": "USGS-02300000",
                    "time": "2026-08-22T11:30:00Z",
                    "value": 3.25,
                    "unit_of_measure": "ft",
                    "approval_status": "Provisional",
                },
            },
            {
                "geometry": {"coordinates": [-81.22, 28.12]},
                "properties": {
                    "monitoring_location_id": "USGS-IGNORED",
                    "time": "2026-08-01T11:30:00Z",
                    "value": 9,
                    "unit_of_measure": "ft",
                },
            },
        ]
    }

    values = parse_nearby_river_gauges(
        latest,
        metadata,
        origin_latitude=28.1,
        origin_longitude=-81.2,
        now=NOW,
    )

    assert len(values) == 1
    assert values[0]["gauge"]["name"] == "River at Oak Flat"
    assert values[0]["provisional"] is True


def test_river_series_selects_largest_time_series_and_sorts_readings():
    payload = {
        "features": [
            {"properties": {"time_series_id": "small", "time": "2026-08-22T10:00Z", "value": 1}},
            {"properties": {"time_series_id": "main", "time": "2026-08-22T11:00Z", "value": 3.2}},
            {"properties": {"time_series_id": "main", "time": "2026-08-22T09:00Z", "value": 3.0, "approval_status": "Approved"}},
        ]
    }
    gauge = {"site_id": "USGS-1", "name": "Oak River", "lat": 28.1, "lng": -81.2}

    value = parse_river_gauge_series(
        payload,
        gauge=gauge,
        period_days=7,
        place_latitude=28.0,
        place_longitude=-81.1,
    )

    assert [item["height_feet"] for item in value["readings"]] == [3.0, 3.2]
    assert value["readings"][0]["provisional"] is False


def test_forecast_service_uses_shared_snapshot_cache():
    repository = CacheRepository()
    calls = []

    def request_get(url, **kwargs):
        calls.append((url, kwargs["params"]))
        return Response(forecast_payload())

    service = OutdoorConditionsService(
        repository,
        now=lambda: NOW,
        request_get=request_get,
    )

    first = service.forecast(28.10004, -81.20004)
    second = service.forecast(28.10005, -81.20005)

    assert first == second
    assert len(calls) == 1
    assert len(repository.snapshots) == 1


def test_place_conditions_includes_followed_nearby_gauge_beyond_automatic_three():
    service = OutdoorConditionsService(CacheRepository())
    service.forecast = lambda _lat, _lng: {"condition_label": "Clear"}  # type: ignore[method-assign]
    nearby = [
        {
            "gauge": {
                "site_id": f"USGS-0000{index}",
                "name": f"Gauge {index}",
                "lat": 28.0 + index / 100,
                "lng": -81.0,
            },
            "distance_miles": float(index),
        }
        for index in range(1, 6)
    ]
    service.nearby_gauges = lambda _lat, _lng: nearby  # type: ignore[method-assign]
    service.gauge_series = lambda gauge, **_kwargs: {  # type: ignore[method-assign]
        "gauge": dict(gauge),
        "period_days": 7,
        "readings": [{"observed_at": "2026-08-22T00:00:00Z", "height_feet": 2.0}],
    }

    result = service.place_conditions(
        28.0,
        -81.0,
        followed_site_ids=["usgs-00005", "not-a-site"],
    )

    assert [item["gauge"]["site_id"] for item in result["river_gauges"]] == [
        "USGS-00001",
        "USGS-00002",
        "USGS-00003",
        "USGS-00005",
    ]


def test_place_conditions_fetches_weather_and_gauge_discovery_concurrently():
    service = OutdoorConditionsService(CacheRepository())
    both_requests_started = Barrier(2)

    def forecast(_lat, _lng):
        both_requests_started.wait(timeout=1)
        return {"condition_label": "Clear"}

    def nearby_gauges(_lat, _lng):
        both_requests_started.wait(timeout=1)
        return []

    service.forecast = forecast  # type: ignore[method-assign]
    service.nearby_gauges = nearby_gauges  # type: ignore[method-assign]

    result = service.place_conditions(28.0, -81.0)

    assert result["forecast"]["condition_label"] == "Clear"
    assert result["river_gauges"] == []


def test_place_conditions_keeps_current_gauge_height_when_history_fails():
    service = OutdoorConditionsService(CacheRepository())
    service.forecast = lambda _lat, _lng: {"condition_label": "Clear"}  # type: ignore[method-assign]
    service.nearby_gauges = lambda _lat, _lng: [  # type: ignore[method-assign]
        {
            "gauge": {
                "site_id": "USGS-02233500",
                "name": "Econlockhatchee River",
                "lat": 28.6778,
                "lng": -81.1142,
            },
            "distance_miles": 4.9,
            "current_height_feet": 6.91,
            "observed_at": "2026-08-28T14:45:00+00:00",
            "provisional": True,
        }
    ]
    service.gauge_series = lambda *_args, **_kwargs: (_ for _ in ()).throw(  # type: ignore[method-assign]
        OutdoorConditionsError("history unavailable")
    )

    result = service.place_conditions(28.623217, -81.063275)

    assert result["river_gauges"][0]["readings"][0]["height_feet"] == 6.91
    assert result["river_gauges"][0]["error_message"] == "history unavailable"


def test_outdoor_conditions_migration_is_service_role_only():
    migration = Path("sql/outdoor_conditions_cache_migration.sql").read_text(encoding="utf-8")

    assert "create table if not exists public.outdoor_condition_snapshots" in migration
    assert "force row level security" in migration
    assert "revoke all privileges" in migration
    assert "grant all privileges on table public.outdoor_condition_snapshots to service_role" in migration
