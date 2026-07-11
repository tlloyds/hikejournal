from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
from typing import Any

from hike_journal.services.repositories import HikeJournalRepository


LOCATION_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "hike_locations_seed.json"


def slugify_location_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower().strip())
    return re.sub(r"-+", "-", slug).strip("-") or "location"


def normalize_location_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def load_seed_hike_locations() -> list[dict[str, Any]]:
    try:
        with LOCATION_SEED_PATH.open("r", encoding="utf-8") as seed_file:
            data = json.load(seed_file)
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in data if isinstance(item, dict) and str(item.get("name") or "").strip()]


def attach_location_tags_to_hikes(
    hikes: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    location_tags: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    location_by_id = {str(location.get("id")): location for location in locations if location.get("id")}
    grouped_tags: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tag in location_tags:
        hike_id = str(tag.get("hike_id") or "")
        location = location_by_id.get(str(tag.get("location_id") or ""))
        if hike_id and location:
            grouped_tags[hike_id].append({**location, "is_primary": bool(tag.get("is_primary"))})
    enriched_hikes: list[dict[str, Any]] = []
    for hike in hikes:
        hike_copy = dict(hike)
        tags = grouped_tags.get(str(hike_copy.get("id") or ""), [])
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
        {str(location.get("name") or "").strip() for location in locations if str(location.get("name") or "").strip()},
        key=str.lower,
    )


def resolve_location_selection(
    repository: HikeJournalRepository,
    selected_names: list[str],
    locations: list[dict[str, Any]],
) -> list[str]:
    by_name = {str(location.get("name") or "").strip().lower(): location for location in locations}
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
    for location in locations:
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
