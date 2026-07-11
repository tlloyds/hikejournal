from __future__ import annotations

import math
from typing import Any

from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.storage import StorageService
from hike_journal.services.tcx import (
    ParsedTcxRouteImport,
    TcxParseError,
    combine_tcx_route_imports,
    estimate_elevation_meta_from_track_geojson,
    parse_tcx_bytes,
)


def format_duration_compact(value: int | float | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        total_seconds = max(0, int(round(float(value))))
    except (TypeError, ValueError):
        return None
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
    return f"{seconds}s"


def format_total_miles(value: float | int | None) -> str:
    if value in (None, ""):
        return "0 mi logged"
    try:
        miles = float(value)
    except (TypeError, ValueError):
        return "0 mi logged"
    if miles >= 100:
        return f"{miles:,.0f} mi logged"
    return f"{miles:,.1f} mi logged"


def route_import_meta(route_import: dict[str, Any] | None) -> dict[str, Any]:
    if not route_import:
        return {}
    track_geojson = route_import.get("track_geojson") or {}
    if not isinstance(track_geojson, dict):
        return {}
    meta = track_geojson.get("meta") or {}
    stored_meta = meta if isinstance(meta, dict) else {}
    computed_meta = estimate_elevation_meta_from_track_geojson(track_geojson)
    if not computed_meta:
        return stored_meta
    return {**stored_meta, **computed_meta}


def format_elevation_compact(feet: Any) -> str | None:
    if feet in (None, ""):
        return None
    try:
        value = int(round(float(feet)))
    except (TypeError, ValueError):
        return None
    return f"{value:,} ft gain"


def _normalize_uploaded_route_files(uploaded_files: Any) -> list[Any]:
    if not uploaded_files:
        return []
    if isinstance(uploaded_files, (list, tuple)):
        return [uploaded_file for uploaded_file in uploaded_files if uploaded_file]
    return [uploaded_files]


def _route_import_source_name(uploaded_files: Any) -> str | None:
    file_names = [
        str(getattr(uploaded_file, "name", "") or "").strip()
        for uploaded_file in _normalize_uploaded_route_files(uploaded_files)
    ]
    file_names = [file_name for file_name in file_names if file_name]
    if not file_names:
        return None
    return file_names[0] if len(file_names) == 1 else " + ".join(file_names)


def parse_uploaded_route_import(uploaded_files: Any) -> tuple[ParsedTcxRouteImport | None, bytes | None, str | None]:
    route_files = _normalize_uploaded_route_files(uploaded_files)
    if not route_files:
        return None, None, None
    parsed_imports: list[ParsedTcxRouteImport] = []
    file_payloads: list[bytes] = []
    for uploaded_file in route_files:
        file_name = str(getattr(uploaded_file, "name", "") or "").strip()
        if not file_name:
            continue
        try:
            file_bytes = uploaded_file.getvalue()
        except Exception:
            return None, None, f"Could not read {file_name}."
        try:
            parsed_imports.append(parse_tcx_bytes(file_bytes))
        except TcxParseError as exc:
            return None, None, f"{file_name}: {exc}"
        file_payloads.append(file_bytes)
    if not parsed_imports:
        return None, None, None
    combined = combine_tcx_route_imports(parsed_imports)
    if not combined:
        return None, None, None
    return combined, b"\n\n".join(file_payloads), None


def sync_hike_route_import(
    *,
    repository: HikeJournalRepository,
    storage: StorageService,
    hike_id: str,
    uploaded_file: Any,
    existing_route_import: dict[str, Any] | None,
    remove_existing: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    active_route_import = existing_route_import
    parsed: ParsedTcxRouteImport | None = None
    file_bytes: bytes | None = None
    if uploaded_file:
        parsed, file_bytes, error = parse_uploaded_route_import(uploaded_file)
        if error:
            return active_route_import, error

    if remove_existing and existing_route_import:
        try:
            deleted = repository.delete_hike_route_import(hike_id)
        except Exception:
            return active_route_import, "Run sql/hike_route_imports_migration.sql before deleting imported routes."
        if deleted and deleted.get("source_storage_path"):
            storage.delete_file(str(deleted["source_storage_path"]))
        active_route_import = None

    if not uploaded_file or parsed is None or file_bytes is None:
        return active_route_import, None

    storage_path, public_url = storage.upload_hike_route_import(hike_id, file_bytes)
    payload = {
        "source_type": "mapmyrun_tcx_collection" if len(_normalize_uploaded_route_files(uploaded_file)) > 1 else "mapmyrun_tcx",
        "source_file_name": _route_import_source_name(uploaded_file),
        "source_storage_path": storage_path,
        "source_public_url": public_url,
        "started_at": parsed.started_at,
        "distance_miles": round(parsed.distance_miles, 3) if parsed.distance_miles is not None else None,
        "duration_seconds": parsed.duration_seconds,
        "track_point_count": parsed.track_point_count,
        "start_lat": parsed.start_latitude,
        "start_lng": parsed.start_longitude,
        "end_lat": parsed.end_latitude,
        "end_lng": parsed.end_longitude,
        "track_geojson": parsed.track_geojson,
    }
    try:
        updated = repository.upsert_hike_route_import(hike_id, payload)
    except Exception:
        storage.delete_file(storage_path)
        return active_route_import, "Run sql/hike_route_imports_migration.sql before saving imported routes."
    old_storage_path = str((existing_route_import or {}).get("source_storage_path") or "").strip()
    if old_storage_path and old_storage_path != storage_path:
        storage.delete_file(old_storage_path)
    return updated, None


def delete_hike_and_assets(repository: HikeJournalRepository, storage: StorageService, hike_id: str) -> None:
    photos = repository.list_photos(hike_id)
    route_import = repository.get_hike_route_import(hike_id)
    storage_paths = [
        str(photo.get("storage_path") or "").strip()
        for photo in photos
        if str(photo.get("storage_path") or "").strip()
    ]
    route_storage_path = str((route_import or {}).get("source_storage_path") or "").strip()
    if route_storage_path:
        storage_paths.append(route_storage_path)
    repository.delete_hike(hike_id)
    for storage_path in storage_paths:
        try:
            storage.delete_file(storage_path)
        except Exception:
            pass


def _coordinates_to_route_points(coordinates: list[Any]) -> list[dict[str, float]]:
    points: list[dict[str, float]] = []
    for coordinate in coordinates:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
            continue
        try:
            lng = float(coordinate[0])
            lat = float(coordinate[1])
        except (TypeError, ValueError):
            continue
        points.append({"lat": lat, "lng": lng})
    return points


def route_import_to_route_groups(route_import: dict[str, Any] | None) -> list[list[dict[str, float]]]:
    if not route_import:
        return []
    geojson = route_import.get("track_geojson") or {}
    coordinates = geojson.get("coordinates") if isinstance(geojson, dict) else None
    if not isinstance(coordinates, list):
        return []
    if geojson.get("type") == "MultiLineString":
        return [
            points
            for points in (
                _coordinates_to_route_points(segment)
                for segment in coordinates
                if isinstance(segment, list)
            )
            if len(points) >= 2
        ]
    points = _coordinates_to_route_points(coordinates)
    return [points] if len(points) >= 2 else []


def route_import_to_route_points(route_import: dict[str, Any] | None) -> list[dict[str, float]]:
    return [point for route_group in route_import_to_route_groups(route_import) for point in route_group]


def compute_total_mileage(hikes: list[dict[str, Any]]) -> float:
    total = 0.0
    for hike in hikes:
        try:
            distance = float(hike.get("distance_miles"))
        except (TypeError, ValueError):
            continue
        total += distance
    return total


def _route_progress_label(progress: float) -> str:
    if progress <= 0.2:
        return "Start of hike"
    if progress <= 0.45:
        return "Early miles"
    if progress <= 0.7:
        return "Mid-hike"
    if progress <= 0.9:
        return "Late miles"
    return "Finish stretch"


def _haversine_distance_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_miles = 3958.7613
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    return 2 * radius_miles * math.asin(min(1.0, math.sqrt(a)))


def annotate_photos_with_route_context(
    photos: list[dict[str, Any]],
    *,
    route_import: dict[str, Any] | None,
    hike_distance_miles: float | None,
) -> list[dict[str, Any]]:
    route_points = route_import_to_route_points(route_import)
    if len(route_points) < 2 or not photos:
        return photos
    cumulative_miles = [0.0]
    total_line_distance = 0.0
    for index in range(1, len(route_points)):
        segment = _haversine_distance_miles(
            route_points[index - 1]["lat"],
            route_points[index - 1]["lng"],
            route_points[index]["lat"],
            route_points[index]["lng"],
        )
        total_line_distance += segment
        cumulative_miles.append(total_line_distance)
    reference_distance = float(hike_distance_miles or 0.0) or total_line_distance
    for photo in photos:
        photo.pop("route_context_label", None)
        lat = photo.get("lat")
        lng = photo.get("lng")
        if lat is None or lng is None:
            continue
        nearest_index = 0
        nearest_distance = None
        for index, point in enumerate(route_points):
            distance_to_point = (float(point["lat"]) - float(lat)) ** 2 + (float(point["lng"]) - float(lng)) ** 2
            if nearest_distance is None or distance_to_point < nearest_distance:
                nearest_distance = distance_to_point
                nearest_index = index
        progress = nearest_index / max(1, len(route_points) - 1)
        approx_mile = reference_distance * progress
        photo["route_context_label"] = f"{_route_progress_label(progress)} • approx mile {approx_mile:.1f}"
    return photos
