from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any


DEFAULT_MAP_BOUNDS = (-82.2, 27.2, -79.8, 30.8)
MAX_VIEWPORT_FEATURES = 2_500


@dataclass(frozen=True)
class MapViewport:
    west: float
    south: float
    east: float
    north: float
    zoom: float

    def as_dict(self) -> dict[str, float]:
        return {
            "west": self.west,
            "south": self.south,
            "east": self.east,
            "north": self.north,
            "zoom": self.zoom,
        }


def viewport_from_value(value: Any, *, fallback_bounds: Any = None) -> MapViewport:
    fallback = normalize_bounds(fallback_bounds) or DEFAULT_MAP_BOUNDS
    if isinstance(value, dict):
        try:
            west = float(value["west"])
            south = float(value["south"])
            east = float(value["east"])
            north = float(value["north"])
            zoom = float(value.get("zoom", 8))
            numbers = (west, south, east, north, zoom)
            if all(isfinite(number) for number in numbers) and west < east and south < north:
                return MapViewport(
                    west=max(-180.0, west),
                    south=max(-85.051129, south),
                    east=min(180.0, east),
                    north=min(85.051129, north),
                    zoom=max(0.0, min(22.0, zoom)),
                )
        except (KeyError, TypeError, ValueError):
            pass
    west, south, east, north = fallback
    return MapViewport(west=west, south=south, east=east, north=north, zoom=8.0)


def normalize_bounds(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        west, south, east, north = (float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not all(isfinite(item) for item in (west, south, east, north)):
        return None
    if west > east:
        west, east = east, west
    if south > north:
        south, north = north, south
    if west == east or south == north:
        return None
    return west, south, east, north


def empty_feature_collection(**meta: Any) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": [], "meta": meta}


def route_geojson_to_2d_multiline(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    coordinates = value.get("coordinates")
    if not isinstance(coordinates, list):
        return None
    groups = coordinates if value.get("type") == "MultiLineString" else [coordinates]
    clean_groups: list[list[list[float]]] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        clean_group: list[list[float]] = []
        for point in group:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                lng, lat = float(point[0]), float(point[1])
            except (TypeError, ValueError):
                continue
            if isfinite(lng) and isfinite(lat):
                clean_group.append([lng, lat])
        if len(clean_group) >= 2:
            clean_groups.append(clean_group)
    if not clean_groups:
        return None
    return {"type": "MultiLineString", "coordinates": clean_groups}


def normalize_rpc_payload(value: Any, *, include_meta: bool = False) -> dict[str, Any]:
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        value = value[0]
    if not isinstance(value, dict):
        return empty_feature_collection()
    features = value.get("features")
    if not isinstance(features, list):
        return empty_feature_collection()
    payload = {"type": "FeatureCollection", "features": features}
    if include_meta and isinstance(value.get("meta"), dict):
        payload["meta"] = value["meta"]
    return payload


def bounds_from_point_features(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, dict) or not isinstance(value.get("features"), list):
        return None
    coordinates: list[tuple[float, float]] = []
    for feature in value["features"]:
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        point = geometry.get("coordinates") if isinstance(geometry, dict) and geometry.get("type") == "Point" else None
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            lng, lat = float(point[0]), float(point[1])
        except (TypeError, ValueError):
            continue
        if isfinite(lng) and isfinite(lat):
            coordinates.append((lng, lat))
    if not coordinates:
        return None
    west = min(point[0] for point in coordinates)
    east = max(point[0] for point in coordinates)
    south = min(point[1] for point in coordinates)
    north = max(point[1] for point in coordinates)
    # MapLibre cannot fit a zero-area extent. Give a lone cluster a useful local view.
    if west == east:
        west -= 0.01
        east += 0.01
    if south == north:
        south -= 0.01
        north += 0.01
    return west, south, east, north


def fallback_route_features(
    route_imports: list[dict[str, Any]],
    *,
    visible_hike_ids: set[str],
    selected_hike_id: str | None,
    viewport: MapViewport,
) -> dict[str, Any]:
    """Transitional route renderer used only before the PostGIS migration exists."""
    max_points = 2_000 if viewport.zoom >= 15 else 700 if viewport.zoom >= 11 else 250
    features: list[dict[str, Any]] = []
    for route_import in route_imports:
        hike_id = str(route_import.get("hike_id") or "")
        if hike_id not in visible_hike_ids or (selected_hike_id and hike_id != selected_hike_id):
            continue
        geojson = route_import.get("track_geojson") or {}
        coordinates = geojson.get("coordinates") if isinstance(geojson, dict) else None
        if not isinstance(coordinates, list):
            continue
        groups = coordinates if geojson.get("type") == "MultiLineString" else [coordinates]
        rendered_groups: list[list[list[float]]] = []
        for group in groups:
            if not isinstance(group, list) or len(group) < 2:
                continue
            valid = [
                [float(point[0]), float(point[1])]
                for point in group
                if isinstance(point, (list, tuple)) and len(point) >= 2
            ]
            if len(valid) < 2:
                continue
            if not any(
                viewport.west <= point[0] <= viewport.east and viewport.south <= point[1] <= viewport.north
                for point in valid
            ):
                continue
            if len(valid) > max_points:
                stride = (len(valid) - 1) / (max_points - 1)
                valid = [valid[round(index * stride)] for index in range(max_points)]
            rendered_groups.append(valid)
        if not rendered_groups:
            continue
        geometry = (
            {"type": "LineString", "coordinates": rendered_groups[0]}
            if len(rendered_groups) == 1
            else {"type": "MultiLineString", "coordinates": rendered_groups}
        )
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {"hike_id": hike_id, "title": "Hike path"},
        })
    return {"type": "FeatureCollection", "features": features, "meta": {"fallback": True}}
