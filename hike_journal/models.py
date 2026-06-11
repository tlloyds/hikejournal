from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(slots=True)
class HikeDraft:
    title: str
    hike_date: date
    distance_miles: float | None
    location_name: str
    notes: str
    owner_subject: str | None = None
    owner_email: str | None = None


@dataclass(slots=True)
class SpeciesCandidate:
    common_name: str
    scientific_name: str
    confidence: float
    taxon_id: int | None
    raw_payload: dict[str, Any]


@dataclass(slots=True)
class ProcessedImage:
    bytes_data: bytes
    width: int
    height: int
    format: str
    content_type: str


@dataclass(slots=True)
class PhotoMetadata:
    lat: float | None
    lng: float | None
    taken_at: datetime | None
    exif_json: dict[str, Any]
