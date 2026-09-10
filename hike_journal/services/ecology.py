"""Place-aware ecological status helpers.

Identification and ecological status are deliberately separate concerns. A
taxon can be confidently identified while its native or invasive status is
unknown for the place where it was observed.
"""

from __future__ import annotations

from typing import Any


ECOLOGY_LABELS = {"native", "non_native", "invasive", "unknown"}
ESTABLISHMENT_VALUES = {"native", "introduced", "endemic", "unknown"}
INVASIVE_VALUES = {"invasive", "unknown"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _raw_establishment_value(enrichment: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    record = enrichment.get("establishment_means")
    details = record if isinstance(record, dict) else {}
    value = _text(enrichment.get("preferred_establishment_means"))
    if not value:
        value = _text(details.get("establishment_means"))
    if not value and isinstance(record, str):
        value = record.strip()
    return value.casefold(), details


def build_ecology_snapshot(
    enrichment: dict[str, Any],
    *,
    region_code: str,
    place_id: int | None,
    source: str = "inaturalist",
    source_url: str | None = None,
) -> dict[str, Any]:
    """Convert iNaturalist's place-specific value into HikeJournal's contract."""
    value, details = _raw_establishment_value(enrichment)
    if value == "endemic":
        establishment = "endemic"
        label = "native"
        invasive = "unknown"
    elif value == "native":
        establishment = "native"
        label = "native"
        invasive = "unknown"
    elif value == "invasive":
        # Older or alternate iNaturalist responses can contain this value;
        # preserve it when present, while not deriving it from "introduced".
        establishment = "introduced"
        label = "invasive"
        invasive = "invasive"
    elif value in {"introduced", "naturalised", "naturalized", "managed"}:
        establishment = "introduced"
        label = "non_native"
        invasive = "unknown"
    else:
        establishment = "unknown"
        label = "unknown"
        invasive = "unknown"

    place = details.get("place") if isinstance(details.get("place"), dict) else {}
    normalized_region = _text(region_code) or _text(place.get("display_name")) or "unknown"
    taxon_id = enrichment.get("taxon_id")
    resolved_source_url = source_url
    if not resolved_source_url and taxon_id not in (None, ""):
        resolved_source_url = f"https://www.inaturalist.org/taxa/{taxon_id}"
    return {
        "label": label if label in ECOLOGY_LABELS else "unknown",
        "establishment_status": establishment if establishment in ESTABLISHMENT_VALUES else "unknown",
        "invasive_status": invasive if invasive in INVASIVE_VALUES else "unknown",
        "establishment_means": value or "unknown",
        "region_code": normalized_region,
        "place_id": place_id or place.get("id"),
        "place_name": _text(place.get("display_name")) or _text(place.get("name")),
        "source": source,
        "source_url": resolved_source_url or "",
    }


def ecology_display_label(snapshot: Any) -> str:
    if not isinstance(snapshot, dict):
        return "unknown"
    label = _text(snapshot.get("label")).casefold()
    return label if label in ECOLOGY_LABELS else "unknown"


def ecology_display_text(snapshot: Any) -> str:
    labels = {
        "native": "Native here",
        "non_native": "Non-native here",
        "invasive": "Invasive here",
        "unknown": "Status unknown",
    }
    return labels[ecology_display_label(snapshot)]
