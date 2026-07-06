from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


TCX_NS = {"tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
METERS_PER_MILE = 1609.344
EARTH_RADIUS_METERS = 6_371_000.0
ELEVATION_SMOOTHING_MILES = 0.25
ELEVATION_SAMPLING_MILES = 0.25


class TcxParseError(ValueError):
    pass


@dataclass(slots=True)
class ParsedTcxRouteImport:
    started_at: str | None
    visited_on: date | None
    distance_miles: float | None
    duration_seconds: int | None
    track_point_count: int
    elevation_gain_feet: int | None
    elevation_loss_feet: int | None
    start_latitude: float
    start_longitude: float
    end_latitude: float
    end_longitude: float
    track_geojson: dict[str, Any]


def _parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _downsample_coordinates(coordinates: list[list[float]], limit: int = 1500) -> list[list[float]]:
    if len(coordinates) <= limit:
        return coordinates
    step = max(1, math.ceil(len(coordinates) / limit))
    sampled = coordinates[::step]
    if sampled[-1] != coordinates[-1]:
        sampled.append(coordinates[-1])
    return sampled


def _meters_to_feet(value: float | None) -> int | None:
    if value is None:
        return None
    return int(round(value * 3.28084))


def _haversine_distance_meters(
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float,
) -> float:
    start_lat_rad = math.radians(start_latitude)
    end_lat_rad = math.radians(end_latitude)
    delta_lat = math.radians(end_latitude - start_latitude)
    delta_long = math.radians(end_longitude - start_longitude)
    a = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(start_lat_rad) * math.cos(end_lat_rad) * math.sin(delta_long / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_METERS * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _smooth_elevation_profile(values: list[float], window_size: int) -> list[float]:
    if window_size <= 1 or len(values) <= 2:
        return values[:]

    half_window = window_size // 2
    smoothed: list[float] = []
    for index in range(len(values)):
        window = values[max(0, index - half_window) : min(len(values), index + half_window + 1)]
        smoothed.append(sum(window) / len(window))
    return smoothed


def _sample_elevation_profile(
    cumulative_distances: list[float],
    altitudes: list[float],
    sample_interval_meters: float,
) -> list[float]:
    if not altitudes:
        return []

    sampled_altitudes: list[float] = [altitudes[0]]
    next_sample_distance = sample_interval_meters
    for distance, altitude in zip(cumulative_distances[1:], altitudes[1:]):
        while distance >= next_sample_distance:
            sampled_altitudes.append(altitude)
            next_sample_distance += sample_interval_meters

    if sampled_altitudes[-1] != altitudes[-1]:
        sampled_altitudes.append(altitudes[-1])
    return sampled_altitudes


def _estimate_elevation_change(track_points: list[tuple[float, float, float]]) -> tuple[float, float]:
    if len(track_points) < 2:
        return 0.0, 0.0
    if len(track_points) < 5:
        elevation_gain_m = 0.0
        elevation_loss_m = 0.0
        previous_altitude = track_points[0][2]
        for _, _, altitude in track_points[1:]:
            delta = altitude - previous_altitude
            if delta > 0:
                elevation_gain_m += delta
            elif delta < 0:
                elevation_loss_m += abs(delta)
            previous_altitude = altitude
        return elevation_gain_m, elevation_loss_m

    cumulative_distances = [0.0]
    total_distance_meters = 0.0
    for index in range(1, len(track_points)):
        previous_latitude, previous_longitude, _ = track_points[index - 1]
        latitude, longitude, _ = track_points[index]
        total_distance_meters += _haversine_distance_meters(
            previous_latitude,
            previous_longitude,
            latitude,
            longitude,
        )
        cumulative_distances.append(total_distance_meters)

    if total_distance_meters <= 0:
        return 0.0, 0.0

    altitudes = [altitude for _, _, altitude in track_points]
    points_per_mile = len(track_points) / max(total_distance_meters / METERS_PER_MILE, 0.01)
    smoothing_window = max(5, int(round(points_per_mile * ELEVATION_SMOOTHING_MILES)))
    if smoothing_window % 2 == 0:
        smoothing_window += 1

    smoothed_altitudes = _smooth_elevation_profile(altitudes, smoothing_window)
    sampled_altitudes = _sample_elevation_profile(
        cumulative_distances,
        smoothed_altitudes,
        ELEVATION_SAMPLING_MILES * METERS_PER_MILE,
    )

    elevation_gain_m = 0.0
    elevation_loss_m = 0.0
    previous_altitude = sampled_altitudes[0]
    for altitude in sampled_altitudes[1:]:
        delta = altitude - previous_altitude
        if delta > 0:
            elevation_gain_m += delta
        elif delta < 0:
            elevation_loss_m += abs(delta)
        previous_altitude = altitude

    return elevation_gain_m, elevation_loss_m


def estimate_elevation_meta_from_track_geojson(track_geojson: dict[str, Any] | None) -> dict[str, int | None]:
    if not isinstance(track_geojson, dict):
        return {}
    coordinates = track_geojson.get("coordinates")
    if not isinstance(coordinates, list):
        return {}

    coordinate_groups = coordinates
    if track_geojson.get("type") == "MultiLineString":
        coordinate_groups = [group for group in coordinates if isinstance(group, list)]
    else:
        coordinate_groups = [coordinates]

    total_gain_m = 0.0
    total_loss_m = 0.0
    for coordinate_group in coordinate_groups:
        elevation_track_points: list[tuple[float, float, float]] = []
        for coordinate in coordinate_group:
            if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 3:
                continue
            try:
                longitude = float(coordinate[0])
                latitude = float(coordinate[1])
                altitude = float(coordinate[2])
            except (TypeError, ValueError):
                continue
            elevation_track_points.append((latitude, longitude, altitude))

        if len(elevation_track_points) < 2:
            continue
        elevation_gain_m, elevation_loss_m = _estimate_elevation_change(elevation_track_points)
        total_gain_m += elevation_gain_m
        total_loss_m += elevation_loss_m

    if total_gain_m <= 0 and total_loss_m <= 0:
        return {}

    return {
        "elevation_gain_feet": _meters_to_feet(total_gain_m) if total_gain_m > 0 else None,
        "elevation_loss_feet": _meters_to_feet(total_loss_m) if total_loss_m > 0 else None,
    }


def parse_tcx_bytes(payload: bytes) -> ParsedTcxRouteImport:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise TcxParseError("Invalid TCX file.") from exc

    activity = root.find(".//tcx:Activity", TCX_NS)
    lap = root.find(".//tcx:Lap", TCX_NS)
    if activity is None or lap is None:
        raise TcxParseError("TCX file is missing activity data.")

    started_at = activity.findtext("tcx:Id", default="", namespaces=TCX_NS).strip() or lap.get("StartTime", "").strip() or None
    started_dt = _parse_iso_datetime(started_at)
    visited_on = started_dt.astimezone().date() if started_dt else None
    distance_meters = _parse_float(lap.findtext("tcx:DistanceMeters", default="", namespaces=TCX_NS))
    total_time_seconds = _parse_float(lap.findtext("tcx:TotalTimeSeconds", default="", namespaces=TCX_NS))

    coordinates: list[list[float]] = []
    elevation_track_points: list[tuple[float, float, float]] = []
    for trackpoint in root.findall(".//tcx:Trackpoint", TCX_NS):
        lat = _parse_float(trackpoint.findtext("tcx:Position/tcx:LatitudeDegrees", default="", namespaces=TCX_NS))
        lng = _parse_float(trackpoint.findtext("tcx:Position/tcx:LongitudeDegrees", default="", namespaces=TCX_NS))
        altitude = _parse_float(trackpoint.findtext("tcx:AltitudeMeters", default="", namespaces=TCX_NS))
        if lat is None or lng is None:
            continue
        if altitude is not None:
            elevation_track_points.append((lat, lng, altitude))
            coordinates.append([lng, lat, altitude])
        else:
            coordinates.append([lng, lat])

    if not coordinates:
        raise TcxParseError("TCX file does not include GPS points.")

    elevation_gain_m, elevation_loss_m = _estimate_elevation_change(elevation_track_points)

    simplified_coordinates = _downsample_coordinates(coordinates)
    start_lon, start_lat = coordinates[0][0], coordinates[0][1]
    end_lon, end_lat = coordinates[-1][0], coordinates[-1][1]

    return ParsedTcxRouteImport(
        started_at=started_at,
        visited_on=visited_on,
        distance_miles=(distance_meters / METERS_PER_MILE) if distance_meters is not None else None,
        duration_seconds=int(round(total_time_seconds)) if total_time_seconds is not None else None,
        track_point_count=len(coordinates),
        elevation_gain_feet=_meters_to_feet(elevation_gain_m) if elevation_gain_m > 0 else None,
        elevation_loss_feet=_meters_to_feet(elevation_loss_m) if elevation_loss_m > 0 else None,
        start_latitude=start_lat,
        start_longitude=start_lon,
        end_latitude=end_lat,
        end_longitude=end_lon,
        track_geojson={
            "type": "LineString",
            "coordinates": simplified_coordinates,
            "meta": {
                "elevation_gain_feet": _meters_to_feet(elevation_gain_m) if elevation_gain_m > 0 else None,
                "elevation_loss_feet": _meters_to_feet(elevation_loss_m) if elevation_loss_m > 0 else None,
            },
        },
    )


def _parsed_started_datetime(route_import: ParsedTcxRouteImport) -> datetime | None:
    return _parse_iso_datetime(route_import.started_at)


def _route_sort_key(route_import: ParsedTcxRouteImport) -> tuple[float, str]:
    started_dt = _parsed_started_datetime(route_import)
    return started_dt.timestamp() if started_dt else float("inf"), route_import.started_at or ""


def _sum_optional(values: list[float | int | None]) -> float | int | None:
    present_values = [value for value in values if value is not None]
    if not present_values:
        return None
    return sum(present_values)


def combine_tcx_route_imports(route_imports: list[ParsedTcxRouteImport]) -> ParsedTcxRouteImport | None:
    if not route_imports:
        return None
    if len(route_imports) == 1:
        return route_imports[0]

    ordered_imports = sorted(route_imports, key=_route_sort_key)
    coordinate_segments: list[list[list[float]]] = []
    for route_import in ordered_imports:
        track_geojson = route_import.track_geojson or {}
        coordinates = track_geojson.get("coordinates") if isinstance(track_geojson, dict) else None
        if not isinstance(coordinates, list):
            continue
        if track_geojson.get("type") == "MultiLineString":
            for segment in coordinates:
                if isinstance(segment, list) and len(segment) >= 2:
                    coordinate_segments.append(_downsample_coordinates(segment))
        elif len(coordinates) >= 2:
            coordinate_segments.append(_downsample_coordinates(coordinates))

    if not coordinate_segments:
        return ordered_imports[0]

    first_route = ordered_imports[0]
    last_route = ordered_imports[-1]
    total_distance = _sum_optional([route_import.distance_miles for route_import in ordered_imports])
    total_duration = _sum_optional([route_import.duration_seconds for route_import in ordered_imports])
    elevation_gain = _sum_optional([route_import.elevation_gain_feet for route_import in ordered_imports])
    elevation_loss = _sum_optional([route_import.elevation_loss_feet for route_import in ordered_imports])
    first_segment = coordinate_segments[0]
    last_segment = coordinate_segments[-1]
    start_lon, start_lat = first_segment[0][0], first_segment[0][1]
    end_lon, end_lat = last_segment[-1][0], last_segment[-1][1]

    return ParsedTcxRouteImport(
        started_at=first_route.started_at,
        visited_on=first_route.visited_on,
        distance_miles=float(total_distance) if total_distance is not None else None,
        duration_seconds=int(total_duration) if total_duration is not None else None,
        track_point_count=sum(route_import.track_point_count for route_import in ordered_imports),
        elevation_gain_feet=int(elevation_gain) if elevation_gain is not None else None,
        elevation_loss_feet=int(elevation_loss) if elevation_loss is not None else None,
        start_latitude=start_lat,
        start_longitude=start_lon,
        end_latitude=end_lat,
        end_longitude=end_lon,
        track_geojson={
            "type": "MultiLineString",
            "coordinates": coordinate_segments,
            "meta": {
                "segment_count": len(coordinate_segments),
                "elevation_gain_feet": int(elevation_gain) if elevation_gain is not None else None,
                "elevation_loss_feet": int(elevation_loss) if elevation_loss is not None else None,
            },
        },
    )
