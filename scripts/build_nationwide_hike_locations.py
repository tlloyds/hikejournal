#!/usr/bin/env python3
"""Build state-scoped HikeJournal location packs from authoritative public data.

The existing FloridaHikes-derived records remain the high-detail Florida layer.
This script supplements them with named, pedestrian-compatible trails from the
public-domain USGS National Digital Trails and PAD-US services. Census state
boundaries are used to assign each place to a state and to choose an in-state
representative coordinate for place search and GPS suggestions.

The output is deterministic for a given upstream service snapshot. Re-running
the script replaces prior USGS-derived records while preserving curated and
user-maintained seed entries.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path
import re
import time
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "hike_locations_seed.json"
DEFAULT_OUTPUT = DEFAULT_INPUT
DEFAULT_COVERAGE_OUTPUT = ROOT / "data" / "hike_location_coverage.json"
DEFAULT_CACHE = ROOT / ".runtime" / "hike-location-pack-cache"

USGS_SOURCE = "usgs_national_digital_trails"
PAD_US_SOURCE = "usgs_pad_us"
GENERATED_SOURCES = {USGS_SOURCE, PAD_US_SOURCE}
PACK_VERSION = 5
USGS_TRAILS_URL = (
    "https://partnerships.nationalmap.gov/arcgis/rest/services/"
    "USGSTrails/MapServer/0"
)
USGS_SOURCE_URL = "https://www.usgs.gov/national-digital-trails/usgs-trails-explorer"
PAD_US_URL = (
    "https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/"
    "PADUS_Public_Access/FeatureServer/0"
)
PAD_US_SOURCE_URL = "https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview"
CENSUS_STATES_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/State_County/MapServer/0"
)

STATE_NAMES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}

TRAIL_FIELDS = ",".join(
    [
        "permanentidentifier",
        "objectid",
        "name",
        "namealternate",
        "sourceoriginator",
        "primarytrailmaintainer",
        "hikerpedestrian",
        "nationaltraildesignation",
        "lengthmiles",
        "trailtype",
    ]
)
TRAIL_WHERE = (
    "name IS NOT NULL AND name <> '-' AND trailtype = 'Terra Trail' AND "
    "hikerpedestrian IN ('Y','Yes')"
)
PAGE_SIZE = 2000
GEOMETRY_BATCH_SIZE = 100
PAD_US_LIMIT = 75
PAD_US_FIELDS = ",".join(
    [
        "OBJECTID",
        "Unit_Nm",
        "GIS_Acres",
        "DesTp_Desc",
        "MngNm_Desc",
        "MngTp_Desc",
    ]
)
PAD_US_WHERE = (
    "Pub_Access = 'OA' AND FeatClass = 'Fee' AND Unit_Nm IS NOT NULL "
    "AND GIS_Acres >= 20"
)
HIKING_PLACE_TERMS = (
    "park",
    "forest",
    "wilderness",
    "preserve",
    "natural area",
    "conservation area",
    "recreation",
    "wildlife",
    "refuge",
    "greenway",
    "trail",
    "open space",
    "scenic",
    "seashore",
    "lakeshore",
    "monument",
)
EXCLUDED_PLACE_TERMS = (
    "submerged land",
    "school",
    "cemetery",
    "airport",
    "sewage",
    "wastewater",
)


def request_json(url: str, params: dict[str, Any], *, attempts: int = 4) -> dict[str, Any]:
    payload = urlencode(params).encode("utf-8")
    request = Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Accept-Encoding": "gzip",
            "User-Agent": "HikeJournal location pack builder",
        },
    )
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=120) as response:
                content = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    content = gzip.decompress(content)
                result = json.loads(content)
            if result.get("error"):
                if attempt + 1 == attempts:
                    raise RuntimeError(f"ArcGIS request failed: {result['error']}")
                time.sleep(2**attempt)
                continue
            return result
        except (HTTPError, URLError, TimeoutError) as error:
            if attempt + 1 == attempts:
                raise RuntimeError(f"Could not read {url}: {error}") from error
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold().strip())
    return re.sub(r"-+", "-", slug).strip("-") or "location"


def normalize_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold())
    return re.sub(r"\s+", " ", normalized).strip()


def display_name(value: str) -> str:
    clean = re.sub(r"\s+", " ", value).strip()
    if clean.isupper() or clean.islower():
        clean = clean.title()
    return clean.replace(" Nrt", " NRT").replace(" Ohv", " OHV")


def valid_trail_name(value: str) -> bool:
    normalized = normalize_name(value)
    return (
        len(normalized) >= 4
        and not normalized.isdigit()
        and normalized not in {"none", "null", "unknown", "unnamed trail"}
    )


def valid_hiking_place(name: str, designation: str) -> bool:
    combined = normalize_name(f"{name} {designation}")
    return (
        valid_trail_name(name)
        and any(term in combined for term in HIKING_PLACE_TERMS)
        and not any(term in combined for term in EXCLUDED_PLACE_TERMS)
    )


def ring_contains(point: tuple[float, float], ring: list[list[float]]) -> bool:
    x, y = point
    inside = False
    if len(ring) < 3:
        return False
    previous_x, previous_y = ring[-1][:2]
    for raw in ring:
        current_x, current_y = raw[:2]
        crosses = (current_y > y) != (previous_y > y)
        if crosses:
            intersection_x = (
                (previous_x - current_x) * (y - current_y) / (previous_y - current_y)
                + current_x
            )
            if x < intersection_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def state_contains(point: tuple[float, float], rings: list[list[list[float]]]) -> bool:
    # ArcGIS polygon rings alternate outer boundaries and holes. Odd/even
    # containment works for multipart states as well as islands and enclaves.
    return sum(ring_contains(point, ring) for ring in rings) % 2 == 1


def geometry_point(
    geometry: dict[str, Any],
    rings: list[list[list[float]]],
) -> tuple[float, float] | None:
    paths = geometry.get("paths") or []
    for path in paths:
        for raw in path:
            if len(raw) < 2:
                continue
            point = (float(raw[0]), float(raw[1]))
            if all(math.isfinite(value) for value in point) and state_contains(point, rings):
                return point
    return None


def load_state_boundaries() -> dict[str, list[list[list[float]]]]:
    response = request_json(
        f"{CENSUS_STATES_URL}/query",
        {
            "where": "1=1",
            "outFields": "NAME,STUSAB",
            "returnGeometry": "true",
            "outSR": "4326",
            "maxAllowableOffset": "0.01",
            "f": "json",
        },
    )
    boundaries = {
        str(feature["attributes"]["STUSAB"]): feature["geometry"]["rings"]
        for feature in response.get("features") or []
        if str(feature.get("attributes", {}).get("STUSAB") or "") in STATE_NAMES
    }
    missing = sorted(set(STATE_NAMES) - set(boundaries))
    if missing:
        raise RuntimeError(f"Census response omitted states: {', '.join(missing)}")
    return boundaries


def trail_attributes_for_state(
    rings: list[list[list[float]]],
) -> Iterable[dict[str, Any]]:
    geometry = json.dumps(
        {"rings": rings, "spatialReference": {"wkid": 4326}},
        separators=(",", ":"),
    )
    offset = 0
    while True:
        response = request_json(
            f"{USGS_TRAILS_URL}/query",
            {
                "where": TRAIL_WHERE,
                "geometry": geometry,
                "geometryType": "esriGeometryPolygon",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": TRAIL_FIELDS,
                "returnGeometry": "false",
                "resultOffset": str(offset),
                "resultRecordCount": str(PAGE_SIZE),
                "orderByFields": "objectid",
                "f": "json",
            },
        )
        features = response.get("features") or []
        yield from features
        if len(features) < PAGE_SIZE and not response.get("exceededTransferLimit"):
            break
        offset += len(features)
        if not features:
            break


def pad_us_features_for_state(
    rings: list[list[list[float]]],
) -> Iterable[dict[str, Any]]:
    geometry = json.dumps(
        {"rings": rings, "spatialReference": {"wkid": 4326}},
        separators=(",", ":"),
    )
    offset = 0
    while True:
        response = request_json(
            f"{PAD_US_URL}/query",
            {
                "where": PAD_US_WHERE,
                "geometry": geometry,
                "geometryType": "esriGeometryPolygon",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": PAD_US_FIELDS,
                "returnGeometry": "false",
                "returnCentroid": "true",
                "outSR": "4326",
                "resultOffset": str(offset),
                "resultRecordCount": str(PAGE_SIZE),
                "orderByFields": "GIS_Acres DESC, OBJECTID",
                "f": "json",
            },
        )
        features = response.get("features") or []
        yield from features
        if len(features) < PAGE_SIZE and not response.get("exceededTransferLimit"):
            break
        offset += len(features)
        if not features:
            break


def trail_geometries(object_ids: list[int]) -> dict[int, dict[str, Any]]:
    results: dict[int, dict[str, Any]] = {}
    for start in range(0, len(object_ids), GEOMETRY_BATCH_SIZE):
        batch = object_ids[start : start + GEOMETRY_BATCH_SIZE]
        response = request_json(
            f"{USGS_TRAILS_URL}/query",
            {
                "objectIds": ",".join(str(value) for value in batch),
                "outFields": "objectid",
                "returnGeometry": "true",
                "outSR": "4326",
                "geometryPrecision": "5",
                "maxAllowableOffset": "0.0001",
                "f": "json",
            },
        )
        for feature in response.get("features") or []:
            attributes = feature.get("attributes") or {}
            try:
                object_id = int(attributes["objectid"])
            except (KeyError, TypeError, ValueError):
                continue
            results[object_id] = feature.get("geometry") or {}
    return results


def build_state_trail_records(
    state_code: str,
    rings: list[list[list[float]]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for feature in trail_attributes_for_state(rings):
        attributes = feature.get("attributes") or {}
        raw_name = str(attributes.get("name") or "").strip()
        if not valid_trail_name(raw_name):
            continue
        try:
            object_id = int(attributes["objectid"])
        except (KeyError, TypeError, ValueError):
            continue
        key = normalize_name(raw_name)
        record = grouped.setdefault(
            key,
            {
                "name": display_name(raw_name),
                "aliases": set(),
                "length_miles": 0.0,
                "national": False,
                "pedestrian": False,
                "object_ids": [],
                "source_ids": set(),
                "originators": set(),
            },
        )
        if len(record["object_ids"]) < 3:
            record["object_ids"].append(object_id)
        alternate = str(attributes.get("namealternate") or "").strip()
        if valid_trail_name(alternate) and normalize_name(alternate) != key:
            record["aliases"].add(display_name(alternate))
        try:
            record["length_miles"] += max(0.0, float(attributes.get("lengthmiles") or 0.0))
        except (TypeError, ValueError):
            pass
        designation = str(attributes.get("nationaltraildesignation") or "").strip()
        record["national"] = record["national"] or bool(designation)
        pedestrian = str(attributes.get("hikerpedestrian") or "").strip().casefold()
        record["pedestrian"] = record["pedestrian"] or pedestrian in {"y", "yes"}
        source_id = str(attributes.get("permanentidentifier") or "").strip()
        if source_id:
            record["source_ids"].add(source_id)
        originator = str(attributes.get("sourceoriginator") or "").strip()
        if originator:
            record["originators"].add(originator)

    ranked = sorted(
        grouped.values(),
        key=lambda item: (
            not bool(item["national"]),
            not bool(item["pedestrian"]),
            -float(item["length_miles"]),
            str(item["name"]).casefold(),
        ),
    )[: max(limit * 2, limit)]
    requested_ids = [
        int(object_id)
        for item in ranked
        for object_id in item["object_ids"][:1]
    ]
    geometries = trail_geometries(requested_ids)
    results = []
    for item in ranked:
        point = None
        for object_id in item["object_ids"]:
            point = geometry_point(geometries.get(int(object_id), {}), rings)
            if point is not None:
                break
        if point is None:
            continue
        name = str(item["name"])
        results.append(
            {
                "aliases": sorted(item["aliases"], key=str.casefold),
                "county": None,
                "lat": round(float(point[1]), 6),
                "lng": round(float(point[0]), 6),
                "location_type": (
                    "national_recreation_trail" if item["national"] else "trail"
                ),
                "name": name,
                "region": STATE_NAMES[state_code],
                "slug": f"{slugify(name)}-{state_code.casefold()}",
                "source": USGS_SOURCE,
                "source_slug": sorted(item["source_ids"])[0] if item["source_ids"] else None,
                "source_url": USGS_SOURCE_URL,
                "state": state_code,
            }
        )
        if len(results) >= limit:
            break
    return results


def build_state_public_land_records(
    state_code: str,
    rings: list[list[list[float]]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for feature in pad_us_features_for_state(rings):
        attributes = feature.get("attributes") or {}
        raw_name = str(attributes.get("Unit_Nm") or "").strip()
        designation = str(attributes.get("DesTp_Desc") or "").strip()
        if not valid_hiking_place(raw_name, designation):
            continue
        centroid = feature.get("centroid") or {}
        try:
            point = (float(centroid["x"]), float(centroid["y"]))
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in point) or not state_contains(point, rings):
            continue
        key = normalize_name(raw_name)
        acres = max(0, int(attributes.get("GIS_Acres") or 0))
        manager_type = str(attributes.get("MngTp_Desc") or "").strip()
        candidate = {
            "name": display_name(raw_name),
            "lat": point[1],
            "lng": point[0],
            "acres": acres,
            "designation": designation,
            "manager_name": str(attributes.get("MngNm_Desc") or "").strip(),
            "manager_type": manager_type,
            "source_id": str(attributes.get("OBJECTID") or "").strip(),
        }
        current = grouped.get(key)
        if current is None or acres > int(current["acres"]):
            grouped[key] = candidate

    # A deliberate non-federal preference makes every pack useful beyond the
    # federal system while still retaining large federal destinations.
    ranked = sorted(
        grouped.values(),
        key=lambda item: (
            str(item["manager_type"]).casefold() == "federal",
            -int(item["acres"]),
            str(item["name"]).casefold(),
        ),
    )[:limit]
    return [
        {
            "aliases": [],
            "county": None,
            "lat": round(float(item["lat"]), 6),
            "lng": round(float(item["lng"]), 6),
            "location_type": "public_land",
            "manager_name": item["manager_name"] or None,
            "manager_type": item["manager_type"] or None,
            "name": item["name"],
            "region": STATE_NAMES[state_code],
            "slug": f"{slugify(str(item['name']))}-{state_code.casefold()}-place",
            "source": PAD_US_SOURCE,
            "source_slug": item["source_id"] or None,
            "source_url": PAD_US_SOURCE_URL,
            "state": state_code,
        }
        for item in ranked
    ]


def build_state_records(
    state_code: str,
    rings: list[list[list[float]]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    place_limit = min(PAD_US_LIMIT, max(1, limit // 3))
    trails = build_state_trail_records(
        state_code,
        rings,
        limit=max(1, limit - place_limit),
    )
    places = build_state_public_land_records(state_code, rings, limit=limit)
    combined = places[:place_limit] + trails + places[place_limit:]
    seen: set[str] = set()
    results = []
    for item in combined:
        key = normalize_name(str(item.get("name") or ""))
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
    return results[:limit]


def read_seed(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [item for item in data if isinstance(item, dict)]


def build_seed(
    existing: list[dict[str, Any]],
    *,
    limit: int,
    cache_directory: Path,
    excluded_sources: set[str] | None = None,
) -> list[dict[str, Any]]:
    excluded_sources = excluded_sources or set()
    retained = [
        item
        for item in existing
        if item.get("source") not in GENERATED_SOURCES
        and item.get("source") not in excluded_sources
    ]
    existing_names: dict[str, set[str]] = defaultdict(set)
    for item in retained:
        state_code = str(item.get("state") or "").upper()
        if state_code in STATE_NAMES:
            existing_names[state_code].add(normalize_name(str(item.get("name") or "")))

    boundaries = load_state_boundaries()
    cache_directory.mkdir(parents=True, exist_ok=True)
    generated: list[dict[str, Any]] = []
    for index, state_code in enumerate(STATE_NAMES, start=1):
        print(f"[{index:02d}/50] {STATE_NAMES[state_code]}", flush=True)
        cache_path = cache_directory / f"v{PACK_VERSION}-{state_code}-{limit}.json"
        if cache_path.exists():
            candidates = read_seed(cache_path)
        else:
            candidates = build_state_records(state_code, boundaries[state_code], limit=limit)
            with cache_path.open("w", encoding="utf-8") as cache_file:
                json.dump(candidates, cache_file, ensure_ascii=False, indent=2, sort_keys=True)
                cache_file.write("\n")
        generated.extend(
            item
            for item in candidates
            if normalize_name(str(item.get("name") or "")) not in existing_names[state_code]
        )

    combined = retained + generated
    slugs: set[str] = set()
    for item in combined:
        slug = str(item.get("slug") or "")
        if not slug or slug in slugs:
            raise RuntimeError(f"Duplicate or missing location slug: {slug!r}")
        slugs.add(slug)
    return sorted(
        combined,
        key=lambda item: (
            str(item.get("state") or ""),
            str(item.get("name") or "").casefold(),
            str(item.get("slug") or ""),
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--coverage-output", type=Path, default=DEFAULT_COVERAGE_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument(
        "--exclude-source",
        action="append",
        default=[],
        help="Source key to omit from the output; may be repeated",
    )
    parser.add_argument(
        "--per-state",
        type=int,
        default=250,
        help="Maximum generated trails and public lands per state (default: 250)",
    )
    return parser.parse_args()


def coverage_report(seed: list[dict[str, Any]]) -> dict[str, Any]:
    state_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in seed:
        state_rows[str(item.get("state") or "")].append(item)
    states: dict[str, Any] = {}
    for state_code in STATE_NAMES:
        rows = state_rows[state_code]
        source_counts: dict[str, int] = defaultdict(int)
        for item in rows:
            source_counts[str(item.get("source") or "unknown")] += 1
        states[state_code] = {
            "non_federal_public_lands": sum(
                item.get("source") == PAD_US_SOURCE
                and str(item.get("manager_type") or "").casefold()
                not in {"", "federal", "unknown"}
                for item in rows
            ),
            "sources": dict(sorted(source_counts.items())),
            "total": len(rows),
        }
    return {
        "minimum_state_locations": min(item["total"] for item in states.values()),
        "state_count": len(states),
        "states": states,
        "total_locations": len(seed),
    }


def main() -> None:
    args = parse_args()
    if args.per_state < 1:
        raise SystemExit("--per-state must be positive")
    seed = build_seed(
        read_seed(args.input),
        limit=args.per_state,
        cache_directory=args.cache_dir,
        excluded_sources=set(args.exclude_source),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as destination:
        json.dump(seed, destination, ensure_ascii=False, indent=2, sort_keys=True)
        destination.write("\n")
    report = coverage_report(seed)
    args.coverage_output.parent.mkdir(parents=True, exist_ok=True)
    with args.coverage_output.open("w", encoding="utf-8") as destination:
        json.dump(report, destination, ensure_ascii=False, indent=2, sort_keys=True)
        destination.write("\n")
    counts: dict[str, int] = defaultdict(int)
    for item in seed:
        counts[str(item.get("state") or "")] += 1
    print(f"Wrote {len(seed)} locations to {args.output}")
    print(f"Wrote coverage report to {args.coverage_output}")
    print("State counts: " + ", ".join(f"{code}={counts[code]}" for code in STATE_NAMES))


if __name__ == "__main__":
    main()
