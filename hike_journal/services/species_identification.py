from __future__ import annotations

from typing import Any


SPECIES_LOG_MAIN_PHOTO_KEY = "species_log_main_photo"


def is_species_log_main_photo(observation: dict[str, Any]) -> bool:
    raw_payload = observation.get("raw_response_json") or {}
    return isinstance(raw_payload, dict) and raw_payload.get(SPECIES_LOG_MAIN_PHOTO_KEY) is True


def update_species_log_main_photo_payload(
    raw_payload: dict[str, Any] | None,
    *,
    selected: bool,
) -> dict[str, Any]:
    updated_payload = dict(raw_payload or {})
    if selected:
        updated_payload[SPECIES_LOG_MAIN_PHOTO_KEY] = True
    else:
        updated_payload.pop(SPECIES_LOG_MAIN_PHOTO_KEY, None)
    return updated_payload


def build_known_species_catalog(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for observation in observations:
        common_name = str(observation.get("common_name") or "").strip()
        scientific_name = str(observation.get("scientific_name") or "").strip()
        taxon_id = observation.get("taxon_id")
        if not common_name and not scientific_name:
            continue
        identity = (
            f"taxon:{taxon_id}"
            if taxon_id not in (None, "")
            else f"name:{(scientific_name or common_name).casefold()}"
        )
        entry = catalog.setdefault(
            identity,
            {
                "taxon_id": int(taxon_id) if taxon_id not in (None, "") else None,
                "common_name": common_name or scientific_name,
                "scientific_name": scientific_name or common_name,
                "source_observation_id": observation.get("id"),
                "seen_count": 0,
            },
        )
        entry["seen_count"] += 1
        if not entry.get("common_name") and common_name:
            entry["common_name"] = common_name
        if not entry.get("scientific_name") and scientific_name:
            entry["scientific_name"] = scientific_name

    return sorted(
        catalog.values(),
        key=lambda entry: (
            str(entry.get("common_name") or entry.get("scientific_name") or "").casefold(),
            str(entry.get("scientific_name") or "").casefold(),
        ),
    )


def select_shared_candidate(
    aggregate_candidates: list[dict[str, Any]],
    *,
    photo_count: int,
) -> dict[str, Any] | None:
    if photo_count < 2:
        return None
    if photo_count == 2:
        top_choices = [
            candidate
            for candidate in aggregate_candidates
            if int(candidate.get("top1_count") or 0) > 0
        ]
        if not top_choices:
            return None
        return max(
            top_choices,
            key=lambda candidate: (
                float(candidate.get("best_confidence") or 0),
                float(candidate.get("average_confidence") or 0),
                float(candidate.get("total_confidence") or 0),
                int(candidate.get("support_count") or 0),
            ),
        )
    for candidate in aggregate_candidates:
        support_count = int(candidate.get("support_count") or 0)
        top1_count = int(candidate.get("top1_count") or 0)
        if support_count == photo_count and top1_count > photo_count / 2:
            return candidate
    return None
