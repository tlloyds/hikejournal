from __future__ import annotations

from datetime import date
import hashlib
import json
import re
from typing import Any


DISCOVERY_ALGORITHM_VERSION = "inat-frequency-v1"
DISCOVERY_LIMIT = 50
DISCOVERY_RADII_KM = (5, 10, 25)
DISCOVERY_GROUPS: dict[str, str | None] = {
    "All Life": None,
    "Plants": "Plantae",
    "Birds": "Aves",
    "Mammals": "Mammalia",
    "Reptiles": "Reptilia",
    "Amphibians": "Amphibia",
    "Insects": "Insecta",
    "Arachnids": "Arachnida",
    "Fungi": "Fungi",
    "Fish": "Actinopterygii",
    "Mollusks": "Mollusca",
}
COARSER_THAN_SPECIES_RANKS = {
    "stateofmatter",
    "kingdom",
    "phylum",
    "subphylum",
    "superclass",
    "class",
    "subclass",
    "infraclass",
    "subterclass",
    "superorder",
    "order",
    "suborder",
    "infraorder",
    "parvorder",
    "zoosection",
    "zoosubsection",
    "superfamily",
    "epifamily",
    "family",
    "subfamily",
    "supertribe",
    "tribe",
    "subtribe",
    "genus",
    "genushybrid",
    "subgenus",
    "section",
    "subsection",
    "complex",
}
INFRASPECIES_RANKS = {
    "subspecies",
    "variety",
    "form",
    "infrahybrid",
    "hybrid",
}


def seasonal_months(value: date) -> tuple[int, int, int]:
    return (
        12 if value.month == 1 else value.month - 1,
        value.month,
        1 if value.month == 12 else value.month + 1,
    )


def normalize_radius(value: int | float) -> int:
    radius = int(value)
    if radius not in DISCOVERY_RADII_KM:
        raise ValueError(f"Radius must be one of {DISCOVERY_RADII_KM}.")
    return radius


def normalize_iconic_taxon(value: str | None) -> str | None:
    if not value or value == "All Life":
        return None
    if value in DISCOVERY_GROUPS:
        return DISCOVERY_GROUPS[value]
    if value in {item for item in DISCOVERY_GROUPS.values() if item}:
        return value
    raise ValueError("Unknown species group.")


def discovery_cache_key(
    *,
    lat: float,
    lng: float,
    radius_km: int,
    months: tuple[int, int, int],
    iconic_taxon: str | None,
    observed_after: str,
) -> str:
    payload = {
        "algorithm": DISCOVERY_ALGORITHM_VERSION,
        "lat": round(float(lat), 3),
        "lng": round(float(lng), 3),
        "radius_km": int(radius_km),
        "months": sorted(months),
        "iconic_taxon": iconic_taxon,
        "observed_after": observed_after,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _photo_payload(photo: Any) -> dict[str, Any] | None:
    if not isinstance(photo, dict):
        return None
    url = str(
        photo.get("medium_url")
        or photo.get("url")
        or photo.get("small_url")
        or ""
    ).strip()
    if not url:
        return None
    return {
        "url": url,
        "attribution": str(photo.get("attribution") or "").strip(),
        "license_code": str(photo.get("license_code") or "").strip(),
    }


def normalize_species_counts(payload: dict[str, Any], *, limit: int = DISCOVERY_LIMIT) -> list[dict[str, Any]]:
    results = payload.get("results") or []
    normalized: list[dict[str, Any]] = []
    seen_taxon_ids: set[int] = set()
    for entry in results:
        if not isinstance(entry, dict) or not isinstance(entry.get("taxon"), dict):
            continue
        taxon = entry["taxon"]
        try:
            taxon_id = int(taxon.get("id"))
            count = int(entry.get("count") or 0)
        except (TypeError, ValueError):
            continue
        rank = str(taxon.get("rank") or "").strip().lower()
        if not taxon_id or taxon_id in seen_taxon_ids or (rank and rank != "species"):
            continue
        seen_taxon_ids.add(taxon_id)
        normalized.append(
            {
                "taxon_id": taxon_id,
                "common_name": str(
                    taxon.get("preferred_common_name")
                    or taxon.get("english_common_name")
                    or taxon.get("name")
                    or "Unknown species"
                ),
                "scientific_name": str(taxon.get("name") or ""),
                "rank": rank or "species",
                "iconic_taxon_name": str(taxon.get("iconic_taxon_name") or "Other"),
                "observation_count": max(count, 0),
                "reference_photo": _photo_payload(taxon.get("default_photo")),
            }
        )
        if len(normalized) >= limit:
            break
    normalized.sort(key=lambda item: (-item["observation_count"], item["common_name"].casefold()))
    return apply_frequency_bands(normalized)


def apply_frequency_bands(taxa: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = max(len(taxa), 1)
    banded: list[dict[str, Any]] = []
    for index, item in enumerate(taxa):
        percentile = index / total
        if percentile < 0.2:
            band = "Often reported"
        elif percentile < 0.5:
            band = "Regularly reported"
        else:
            band = "Less often reported"
        banded.append({**item, "nearby_rank": index + 1, "frequency_band": band})
    return banded


def credited_species_taxon_id(observation: dict[str, Any]) -> int | None:
    explicit = observation.get("species_taxon_id")
    if explicit not in (None, ""):
        try:
            return int(explicit)
        except (TypeError, ValueError):
            return None
    rank = str(observation.get("rank") or "").strip().lower()
    if rank in COARSER_THAN_SPECIES_RANKS:
        return None
    taxon_id = observation.get("taxon_id")
    if taxon_id in (None, ""):
        return None
    if rank and rank != "species":
        return None
    scientific_name = str(observation.get("scientific_name") or "").strip()
    if not rank and len(re.findall(r"[A-Za-z][A-Za-z.-]+", scientific_name)) < 2:
        return None
    try:
        return int(taxon_id)
    except (TypeError, ValueError):
        return None


def candidate_taxon_snapshot(
    *,
    taxon_id: int | None,
    scientific_name: str,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    if taxon_id is None:
        return {"rank": None, "iconic_taxon_name": None, "species_taxon_id": None}
    entries = raw_payload.get("results") or raw_payload.get("taxa") or raw_payload.get("scores") or []
    matched: dict[str, Any] | None = None
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        taxon = entry.get("taxon") if isinstance(entry.get("taxon"), dict) else entry
        try:
            matches = int(taxon.get("id")) == int(taxon_id)
        except (TypeError, ValueError):
            matches = False
        if matches:
            matched = taxon
            break
    if matched is None and isinstance(raw_payload.get("taxon_enrichment"), dict):
        matched = raw_payload["taxon_enrichment"]
    rank = str((matched or {}).get("rank") or "").strip().lower()
    species_taxon_id: int | None = None
    if rank == "species":
        species_taxon_id = int(taxon_id)
    elif rank in INFRASPECIES_RANKS:
        ancestor_ids = (matched or {}).get("ancestor_ids")
        if isinstance(ancestor_ids, list) and ancestor_ids:
            try:
                species_taxon_id = int(ancestor_ids[-1])
            except (TypeError, ValueError):
                pass
        if species_taxon_id is None:
            try:
                species_taxon_id = int((matched or {}).get("species_taxon_id"))
            except (TypeError, ValueError):
                pass
    elif not rank and len(re.findall(r"[A-Za-z][A-Za-z.-]+", scientific_name.strip())) == 2:
        species_taxon_id = int(taxon_id)
    return {
        "rank": rank or None,
        "iconic_taxon_name": str((matched or {}).get("iconic_taxon_name") or "").strip() or None,
        "species_taxon_id": species_taxon_id,
    }


def build_collection_index(
    observations: list[dict[str, Any]],
    photos_by_id: dict[str, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    collection: dict[int, dict[str, Any]] = {}
    for observation in observations:
        taxon_id = credited_species_taxon_id(observation)
        if taxon_id is None:
            continue
        photo = photos_by_id.get(str(observation.get("photo_id") or ""), {})
        current = collection.get(taxon_id)
        observed_at = str(photo.get("taken_at") or observation.get("identified_at") or "")
        current_observed_at = str((current or {}).get("collected_at") or "")
        if current is None or observed_at > current_observed_at:
            collection[taxon_id] = {
                "collected_at": observed_at or None,
                "collection_photo_url": str(photo.get("public_url") or "") or None,
            }
    return collection


def attach_collection_progress(
    taxa: list[dict[str, Any]],
    collection: dict[int, dict[str, Any]],
    *,
    focus_taxon_ids: list[int] | None = None,
) -> dict[str, Any]:
    focus_order = {int(taxon_id): index + 1 for index, taxon_id in enumerate(focus_taxon_ids or [])}
    enriched: list[dict[str, Any]] = []
    for item in taxa:
        taxon_id = int(item["taxon_id"])
        collected = collection.get(taxon_id)
        enriched.append(
            {
                **item,
                "collected": collected is not None,
                "collected_at": (collected or {}).get("collected_at"),
                "collection_photo_url": (collected or {}).get("collection_photo_url"),
                "focus_order": focus_order.get(taxon_id),
                "pending_credit": False,
            }
        )
    enriched.sort(
        key=lambda item: (
            bool(item["collected"]),
            int(item.get("nearby_rank") or 0),
        )
    )
    collected_count = sum(1 for item in enriched if item["collected"])
    return {
        "taxa": enriched,
        "progress": {
            "collected_count": collected_count,
            "total_count": len(enriched),
            "remaining_count": max(len(enriched) - collected_count, 0),
        },
    }


def classify_data_density(taxa: list[dict[str, Any]]) -> dict[str, Any]:
    observation_total = sum(int(item.get("observation_count") or 0) for item in taxa)
    sparse = len(taxa) < 20 or observation_total < 50
    return {
        "level": "sparse" if sparse else "normal",
        "message": (
            "Local iNaturalist coverage is limited. Try a 25 km radius or a broader species group."
            if sparse
            else ""
        ),
    }
