from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _coordinates(photo: dict[str, Any]) -> tuple[float, float] | None:
    try:
        lat = float(photo.get("lat"))
        lng = float(photo.get("lng"))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def distance_meters(left: dict[str, Any], right: dict[str, Any]) -> float | None:
    left_coordinates = _coordinates(left)
    right_coordinates = _coordinates(right)
    if left_coordinates is None or right_coordinates is None:
        return None
    lat1, lng1 = map(radians, left_coordinates)
    lat2, lng2 = map(radians, right_coordinates)
    delta_lat = lat2 - lat1
    delta_lng = lng2 - lng1
    haversine = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lng / 2) ** 2
    return 6_371_000 * 2 * asin(sqrt(haversine))


def publish_species_key(observation: dict[str, Any]) -> str:
    taxon_id = observation.get("taxon_id")
    if taxon_id not in (None, ""):
        return f"taxon:{taxon_id}"
    scientific_name = str(observation.get("scientific_name") or "").strip().casefold()
    common_name = str(observation.get("common_name") or "").strip().casefold()
    return f"name:{scientific_name or common_name or observation.get('id') or 'unknown'}"


def _scope_key(row: dict[str, Any]) -> str:
    hike_id = row.get("photo", {}).get("hike_id") or row.get("observation", {}).get("hike_id")
    return f"hike:{hike_id}" if hike_id else "standalone"


def _row_datetime(row: dict[str, Any]) -> datetime | None:
    photo = row.get("photo", {})
    return _parse_datetime(photo.get("taken_at"))


def _row_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    observed_at = _row_datetime(row)
    return (
        observed_at.isoformat() if observed_at else "9999-12-31T23:59:59",
        str(row.get("photo", {}).get("id") or ""),
    )


def _fits_group(
    row: dict[str, Any],
    group_rows: list[dict[str, Any]],
    *,
    max_distance_meters: float,
    max_minutes: float,
) -> bool:
    row_time = _row_datetime(row)
    row_photo = row.get("photo", {})
    if row_time is None or _coordinates(row_photo) is None:
        return False
    candidate_rows = [*group_rows, row]
    candidate_times = [_row_datetime(candidate) for candidate in candidate_rows]
    if any(candidate_time is None for candidate_time in candidate_times):
        return False
    time_span = max(candidate_times) - min(candidate_times)  # type: ignore[arg-type]
    if time_span.total_seconds() > max_minutes * 60:
        return False
    for existing in group_rows:
        distance = distance_meters(row_photo, existing.get("photo", {}))
        if distance is None or distance > max_distance_meters:
            return False
    return True


def _summarize_group(rows: list[dict[str, Any]], *, max_photos: int) -> dict[str, Any]:
    ordered_rows = sorted(rows, key=_row_sort_key)
    times = [time for time in (_row_datetime(row) for row in ordered_rows) if time is not None]
    max_distance = 0.0
    for index, left in enumerate(ordered_rows):
        for right in ordered_rows[index + 1 :]:
            distance = distance_meters(left.get("photo", {}), right.get("photo", {}))
            if distance is not None:
                max_distance = max(max_distance, distance)
    return {
        "rows": ordered_rows,
        "lead_row": ordered_rows[0],
        "photo_count": len(ordered_rows),
        "time_span_minutes": ((max(times) - min(times)).total_seconds() / 60) if len(times) > 1 else 0.0,
        "max_distance_meters": max_distance,
        "oversized": len(ordered_rows) > max_photos,
    }


def build_publish_encounter_plan(
    rows: list[dict[str, Any]],
    *,
    max_distance_meters: float = 50,
    max_minutes: float = 15,
    max_photos: int = 8,
) -> list[dict[str, Any]]:
    partitions: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        partitions[(_scope_key(row), publish_species_key(row.get("observation", {})))].append(row)

    groups: list[dict[str, Any]] = []
    for partition_rows in partitions.values():
        compatible_groups: list[list[dict[str, Any]]] = []
        for row in sorted(partition_rows, key=_row_sort_key):
            if _row_datetime(row) is None or _coordinates(row.get("photo", {})) is None:
                compatible_groups.append([row])
                continue
            matched_group = next(
                (
                    group_rows
                    for group_rows in compatible_groups
                    if _fits_group(
                        row,
                        group_rows,
                        max_distance_meters=max_distance_meters,
                        max_minutes=max_minutes,
                    )
                ),
                None,
            )
            if matched_group is None:
                compatible_groups.append([row])
            else:
                matched_group.append(row)
        groups.extend(_summarize_group(group_rows, max_photos=max_photos) for group_rows in compatible_groups)

    groups.sort(key=lambda group: _row_sort_key(group["lead_row"]))
    return groups
