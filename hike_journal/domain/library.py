from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any


def build_species_group_key(observation: dict[str, Any]) -> str:
    scientific = (observation.get("scientific_name") or "").strip().lower()
    common = (observation.get("common_name") or "").strip().lower()
    if scientific:
        return f"scientific:{scientific}"
    if common:
        return f"common:{common}"
    taxon_id = observation.get("taxon_id")
    if taxon_id not in (None, ""):
        return f"taxon:{taxon_id}"
    return "unknown"


def count_unique_species(observations: list[dict[str, Any]]) -> int:
    return len({build_species_group_key(observation) for observation in observations})


def count_unique_species_by_key(observations: list[dict[str, Any]], key: str) -> dict[str, int]:
    buckets: dict[str, set[str]] = defaultdict(set)
    for observation in observations:
        record_key = observation.get(key)
        if record_key:
            buckets[str(record_key)].add(build_species_group_key(observation))
    return {bucket_key: len(values) for bucket_key, values in buckets.items()}


def normalize_email(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def filter_hikes_for_user(
    hikes: list[dict[str, Any]],
    user_context: dict[str, Any],
) -> list[dict[str, Any]]:
    if user_context["mode"] == "local-dev":
        return hikes
    email = normalize_email(user_context.get("email"))
    subject = user_context.get("subject")
    visible = []
    for hike in hikes:
        owner_email = normalize_email(hike.get("owner_email"))
        owner_subject = hike.get("owner_subject")
        if owner_subject and subject and owner_subject == subject:
            visible.append(hike)
            continue
        if owner_email and email and owner_email == email:
            visible.append(hike)
            continue
        if not owner_email and not owner_subject and not user_context["auth_configured"]:
            visible.append(hike)
    return visible


def user_owns_record(record: dict[str, Any], user_context: dict[str, Any]) -> bool:
    if user_context["mode"] == "local-dev":
        return True
    email = normalize_email(user_context.get("email"))
    subject = user_context.get("subject")
    owner_email = normalize_email(record.get("owner_email"))
    owner_subject = record.get("owner_subject")
    if owner_subject and subject and owner_subject == subject:
        return True
    if owner_email and email and owner_email == email:
        return True
    return False


def record_visible_for_user(
    record: dict[str, Any],
    visible_hike_ids: set[str],
    user_context: dict[str, Any],
) -> bool:
    hike_id = record.get("hike_id")
    if hike_id and hike_id in visible_hike_ids:
        return True
    if not hike_id:
        return user_owns_record(record, user_context)
    return False


def standalone_journal_is_active(
    *,
    active_view: str,
    requested_scope: str | None,
    selected_hike: dict[str, Any] | None,
) -> bool:
    return active_view == "Journal" and requested_scope == "standalone" and selected_hike is None


def filter_standalone_photos(
    photos: list[dict[str, Any]],
    visible_hike_ids: set[str],
    user_context: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        photo
        for photo in photos
        if not photo.get("hike_id") and record_visible_for_user(photo, visible_hike_ids, user_context)
    ]


def filter_standalone_observations(
    observations: list[dict[str, Any]],
    visible_hike_ids: set[str],
    user_context: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        observation
        for observation in observations
        if not observation.get("hike_id")
        and record_visible_for_user(observation, visible_hike_ids, user_context)
    ]


def filter_hike_library(
    hikes: list[dict[str, Any]],
    *,
    query: str,
    scope: str,
    sort_order: str,
) -> list[dict[str, Any]]:
    normalized_query = query.strip().lower()
    filtered = []
    for hike in hikes:
        is_archived = bool(hike.get("is_archived"))
        if scope == "Active" and is_archived:
            continue
        if scope == "Archived" and not is_archived:
            continue
        location_tag_text = " ".join(
            str(tag.get("name") or "") for tag in hike.get("location_tags") or []
        )
        haystack = " ".join(
            str(hike.get(field) or "") for field in ["title", "location_name", "notes", "hike_date"]
        )
        if normalized_query and normalized_query not in f"{haystack} {location_tag_text}".lower():
            continue
        filtered.append(hike)
    if sort_order == "Oldest first":
        filtered.sort(key=lambda hike: (str(hike.get("hike_date") or ""), str(hike.get("created_at") or "")))
    elif sort_order == "Title":
        filtered.sort(key=lambda hike: (str(hike.get("title") or "").lower(), str(hike.get("hike_date") or "")))
    else:
        filtered.sort(
            key=lambda hike: (str(hike.get("hike_date") or ""), str(hike.get("created_at") or "")),
            reverse=True,
        )
    return filtered


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def group_hikes_for_library(hikes: list[dict[str, Any]], group_by: str) -> list[tuple[str | None, list[dict[str, Any]]]]:
    if group_by == "None":
        return [(None, hikes)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for hike in hikes:
        hike_date = _parse_date(hike.get("hike_date"))
        label = hike_date.strftime("%Y") if group_by == "Year" else hike_date.strftime("%B %Y")
        grouped[label].append(hike)
    return list(grouped.items())


def count_records_by_key(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        record_key = record.get(key)
        if record_key:
            counts[record_key] += 1
    return counts


def group_records_by_key(records: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        record_key = record.get(key)
        if record_key:
            groups[str(record_key)].append(record)
    return groups


def build_standalone_library_item(
    *,
    photos: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    query: str,
    scope: str,
) -> dict[str, Any] | None:
    if not photos or scope == "Archived":
        return None
    latest_photo = max(
        photos,
        key=lambda photo: (photo.get("taken_at") or "", photo.get("created_at") or "", photo["id"]),
    )
    confirmed_count = count_unique_species([record for record in confirmed_observations if not record.get("hike_id")])
    title = "Everyday Sightings"
    location_name = "Photos and species notes not attached to a hike yet."
    notes = "A catch-all journal for quick uploads, neighborhood finds, and anything you want to identify outside a formal outing."
    search_haystack = " ".join(
        [title, location_name, notes, str(latest_photo.get("taken_at") or latest_photo.get("created_at") or "")]
    ).lower()
    if query.strip().lower() and query.strip().lower() not in search_haystack:
        return None
    date_value = latest_photo.get("taken_at") or latest_photo.get("created_at") or ""
    return {
        "id": "__standalone__",
        "title": title,
        "location_name": location_name,
        "notes": notes,
        "hike_date": str(date_value)[:10] if date_value else "Anytime",
        "created_at": latest_photo.get("created_at"),
        "is_archived": False,
        "_is_standalone": True,
        "_cover_photo": latest_photo,
        "_photo_count": len(photos),
        "_confirmed_count": confirmed_count,
    }


def entry_sort_datetime(entry: dict[str, Any]) -> datetime:
    photo = entry.get("photo") or {}
    hike = entry.get("hike") or {}
    parsed_taken = _parse_datetime(photo.get("taken_at"))
    if parsed_taken:
        return parsed_taken
    hike_date = hike.get("hike_date")
    if hike_date:
        return datetime.combine(_parse_date(hike_date), datetime.min.time())
    return datetime.min


def format_species_log_date_label(value: datetime) -> str:
    if value == datetime.min:
        return "Unknown date"
    return value.strftime("%b %d, %Y")


def photo_owner_subject(hike: dict[str, Any] | None, user_context: dict[str, Any]) -> str | None:
    return (hike or {}).get("owner_subject") or user_context.get("subject")


def photo_owner_email(hike: dict[str, Any] | None, user_context: dict[str, Any]) -> str | None:
    return normalize_email((hike or {}).get("owner_email")) or normalize_email(user_context.get("email"))
