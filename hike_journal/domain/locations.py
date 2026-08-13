from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
from typing import Any

from hike_journal.services.repositories import HikeJournalRepository


LOCATION_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "hike_locations_seed.json"

# Route imports and destination imports occasionally describe the same physical
# place with different slugs. Place Profiles need one stable identity, while the
# route names remain useful as aliases for matching historical hike text.
LOCATION_SLUG_REDIRECTS = {
    "black-bear-wilderness-loop": "black-bear-wilderness-area",
    "black-bear-wilderness-loop-trail": "black-bear-wilderness-area",
    "black-bear-wilderness-walk": "black-bear-wilderness-area",
    "econ-river-wilderness-area": "econ-river-wilderness",
    "florida-trail-little-big-econ-state-forest": "little-big-econ-state-forest",
    "florida-trail-mills-creek-woodlands": "mills-creek-woodlands",
    "florida-trail-seminole-ranch": "seminole-ranch-conservation-area",
    "hal-scott-preserve-loop": "hal-scott-preserve",
    "little-manatee-river-trail": "little-manatee-river-state-park",
    "lower-wekiva-river-preserve": "lower-wekiva-river-preserve-state-park",
    "st-sebastian-river-preserve-yellow-trail": "fellsmere-trailhead-preserve",
    "werner-boyce-salt-springs-trail": "werner-boyce-salt-springs-state-park",
    "wuesthoff-trail": "wuesthoff-park",
}


def slugify_location_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower().strip())
    return re.sub(r"-+", "-", slug).strip("-") or "location"


def normalize_location_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def canonical_location_slug(location: dict[str, Any]) -> str:
    slug = str(location.get("slug") or slugify_location_name(str(location.get("name") or "")))
    seen: set[str] = set()
    while slug in LOCATION_SLUG_REDIRECTS and slug not in seen:
        seen.add(slug)
        slug = LOCATION_SLUG_REDIRECTS[slug]
    return slug


def canonicalize_hike_locations(locations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse known route aliases into their stable Place Profile records."""
    by_slug = {
        str(location.get("slug") or slugify_location_name(str(location.get("name") or ""))): location
        for location in locations
        if str(location.get("name") or "").strip()
    }
    contributors: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for location in locations:
        slug = str(location.get("slug") or slugify_location_name(str(location.get("name") or "")))
        target_slug = canonical_location_slug(location)
        contributors[target_slug if target_slug in by_slug else slug].append(location)

    canonical_locations: list[dict[str, Any]] = []
    for target_slug, related in contributors.items():
        canonical_source = by_slug.get(target_slug) or related[0]
        canonical = dict(canonical_source)
        canonical_name = str(canonical.get("name") or "").strip()
        aliases: list[str] = []
        seen_aliases = {canonical_name.casefold()}
        for item in [canonical_source, *related]:
            candidates = [str(item.get("name") or ""), *[str(value) for value in item.get("aliases") or []]]
            for candidate in candidates:
                clean_candidate = candidate.strip()
                key = clean_candidate.casefold()
                if clean_candidate and key not in seen_aliases:
                    aliases.append(clean_candidate)
                    seen_aliases.add(key)
        canonical["aliases"] = aliases
        canonical_locations.append(canonical)
    return sorted(canonical_locations, key=lambda item: str(item.get("name") or "").casefold())


def canonical_location_id_map(locations: list[dict[str, Any]]) -> dict[str, str]:
    canonical_by_slug = {
        str(location.get("slug") or slugify_location_name(str(location.get("name") or ""))): location
        for location in canonicalize_hike_locations(locations)
    }
    result: dict[str, str] = {}
    for location in locations:
        location_id = str(location.get("id") or "")
        canonical = canonical_by_slug.get(canonical_location_slug(location), location)
        canonical_id = str(canonical.get("id") or "")
        if location_id and canonical_id:
            result[location_id] = canonical_id
    return result


def load_seed_hike_locations() -> list[dict[str, Any]]:
    try:
        with LOCATION_SEED_PATH.open("r", encoding="utf-8") as seed_file:
            data = json.load(seed_file)
    except (OSError, json.JSONDecodeError):
        return []
    return canonicalize_hike_locations(
        [item for item in data if isinstance(item, dict) and str(item.get("name") or "").strip()]
    )


def attach_location_tags_to_hikes(
    hikes: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    location_tags: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    canonical_locations = canonicalize_hike_locations(locations)
    location_by_id = {
        str(location.get("id")): location for location in canonical_locations if location.get("id")
    }
    canonical_ids = canonical_location_id_map(locations)
    grouped_tags: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for tag in location_tags:
        hike_id = str(tag.get("hike_id") or "")
        location_id = canonical_ids.get(
            str(tag.get("location_id") or ""),
            str(tag.get("location_id") or ""),
        )
        location = location_by_id.get(location_id)
        if hike_id and location:
            existing = grouped_tags[hike_id].get(location_id)
            grouped_tags[hike_id][location_id] = {
                **location,
                "is_primary": bool(tag.get("is_primary")) or bool((existing or {}).get("is_primary")),
            }
    enriched_hikes: list[dict[str, Any]] = []
    for hike in hikes:
        hike_copy = dict(hike)
        tags = list(grouped_tags.get(str(hike_copy.get("id") or ""), {}).values())
        hike_copy["location_tags"] = sorted(
            tags,
            key=lambda item: (not bool(item.get("is_primary")), str(item.get("name") or "").lower()),
        )
        enriched_hikes.append(hike_copy)
    return enriched_hikes


def format_hike_location_label(hike: dict[str, Any], fallback: str = "Unknown location") -> str:
    tags = [
        str(tag.get("name") or "").strip()
        for tag in hike.get("location_tags") or []
        if str(tag.get("name") or "").strip()
    ]
    if tags:
        return ", ".join(tags[:3]) + (" +" if len(tags) > 3 else "")
    return str(hike.get("location_name") or fallback)


def selected_location_defaults(hike: dict[str, Any]) -> list[str]:
    return [
        str(tag.get("name") or "").strip()
        for tag in hike.get("location_tags") or []
        if str(tag.get("name") or "").strip()
    ]


def location_library_options(locations: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(location.get("name") or "").strip()
            for location in canonicalize_hike_locations(locations)
            if str(location.get("name") or "").strip()
        },
        key=str.lower,
    )


def resolve_location_selection(
    repository: HikeJournalRepository,
    selected_names: list[str],
    locations: list[dict[str, Any]],
) -> list[str]:
    canonical_locations = canonicalize_hike_locations(locations)
    by_name: dict[str, dict[str, Any]] = {}
    for location in canonical_locations:
        for value in [location.get("name"), *(location.get("aliases") or [])]:
            name = str(value or "").strip().lower()
            if name:
                by_name.setdefault(name, location)
    location_ids: list[str] = []
    seen = set()
    for raw_name in selected_names:
        name = str(raw_name or "").strip()
        if not name:
            continue
        location = by_name.get(name.lower())
        if location and location.get("id"):
            location_id = str(location["id"])
        else:
            created = repository.upsert_hike_location(
                name,
                source="manual",
                location_type="manual",
                slug=slugify_location_name(name),
            )
            location_id = str(created.get("id")) if created and created.get("id") else ""
        if location_id and location_id not in seen:
            location_ids.append(location_id)
            seen.add(location_id)
    return location_ids


def maybe_store_hike_location_tags(
    repository: HikeJournalRepository,
    hike_id: str,
    selected_names: list[str],
    locations: list[dict[str, Any]],
) -> None:
    location_ids = resolve_location_selection(repository, selected_names, locations)
    repository.set_hike_location_tags(hike_id, location_ids)


def location_match_terms(location: dict[str, Any]) -> list[str]:
    terms = [str(location.get("name") or "")]
    aliases = location.get("aliases") or []
    if isinstance(aliases, list):
        terms.extend(str(alias) for alias in aliases)
    normalized_terms: list[str] = []
    for term in terms:
        normalized = normalize_location_text(term)
        if len(normalized) >= 4:
            normalized_terms.append(normalized)
    return normalized_terms


def suggest_location_ids_for_hike(hike: dict[str, Any], locations: list[dict[str, Any]]) -> list[str]:
    haystack = normalize_location_text(
        " ".join(str(hike.get(field) or "") for field in ["title", "location_name", "notes"])
    )
    if not haystack:
        return []
    matches: list[tuple[int, str]] = []
    padded_haystack = f" {haystack} "
    for location in canonicalize_hike_locations(locations):
        location_id = str(location.get("id") or "")
        if not location_id:
            continue
        best_score = 0
        for term in location_match_terms(location):
            if f" {term} " in padded_haystack:
                best_score = max(best_score, 100 + len(term))
            elif term in haystack and len(term) >= 10:
                best_score = max(best_score, 80 + len(term))
        if best_score:
            matches.append((best_score, location_id))
    matches.sort(reverse=True)
    return [location_id for _, location_id in matches[:4]]


def autotag_matching_hikes(
    repository: HikeJournalRepository,
    hikes: list[dict[str, Any]],
    locations: list[dict[str, Any]],
) -> int:
    tagged_count = 0
    for hike in hikes:
        if hike.get("location_tags"):
            continue
        matches = suggest_location_ids_for_hike(hike, locations)
        if matches:
            repository.set_hike_location_tags(str(hike["id"]), matches)
            tagged_count += 1
    return tagged_count
