from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any, Iterable


MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
BRIEFING_ALGORITHM_VERSION = "personal-season-v2"


def species_key(observation: dict[str, Any]) -> str:
    taxon_id = observation.get("species_taxon_id") or observation.get("taxon_id")
    if taxon_id not in (None, ""):
        return f"taxon:{taxon_id}"
    scientific_name = str(observation.get("scientific_name") or "").strip().casefold()
    if scientific_name:
        return f"scientific:{scientific_name}"
    return f"common:{str(observation.get('common_name') or 'unknown').strip().casefold()}"


def observation_date(observation: dict[str, Any]) -> date | None:
    for field in ("observed_on", "taken_at", "hike_date", "identified_at", "created_at"):
        raw = observation.get(field)
        if not raw:
            continue
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(str(raw)[:10])
            except ValueError:
                continue
    return None


def _species_snapshot(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": species_key(observation),
        "taxon_id": observation.get("species_taxon_id") or observation.get("taxon_id"),
        "common_name": str(observation.get("common_name") or "Unknown species"),
        "scientific_name": str(observation.get("scientific_name") or ""),
        "iconic_taxon_name": str(observation.get("iconic_taxon_name") or "Other"),
        "reference_photo_url": str(
            observation.get("reference_photo_url")
            or observation.get("collection_photo_url")
            or ""
        ),
        "observation_count": int(observation.get("observation_count") or 0),
        "nearby_rank": int(observation.get("nearby_rank") or 0),
        "frequency_band": str(observation.get("frequency_band") or ""),
        "collected": bool(observation.get("collected")),
        "collected_at": observation.get("collected_at"),
        "collection_photo_url": observation.get("collection_photo_url"),
        "wikipedia_url": str(observation.get("wikipedia_url") or ""),
        "wikipedia_summary": str(observation.get("wikipedia_summary") or ""),
        "pending_credit": bool(observation.get("pending_credit")),
    }


def build_seasonal_history(observations: Iterable[dict[str, Any]]) -> dict[str, Any]:
    dated = [(item, observation_date(item)) for item in observations]
    dated = [(item, observed) for item, observed in dated if observed is not None]
    month_counts = Counter(observed.month for _, observed in dated)
    year_ranges: dict[int, list[date]] = defaultdict(list)
    phenophases: Counter[str] = Counter()
    for item, observed in dated:
        year_ranges[observed.year].append(observed)
        values = item.get("phenophases") or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            code = value.get("code") if isinstance(value, dict) else value
            if code:
                phenophases[str(code)] += 1
    dates = sorted(observed for _, observed in dated)
    peak = max(month_counts.values(), default=0)
    return {
        "observation_count": len(dated),
        "first_observed_on": dates[0].isoformat() if dates else None,
        "latest_observed_on": dates[-1].isoformat() if dates else None,
        "months": [
            {
                "month": month,
                "label": MONTH_LABELS[month - 1],
                "count": month_counts[month],
                "relative_intensity": round(month_counts[month] / peak, 3) if peak else 0.0,
            }
            for month in range(1, 13)
        ],
        "years": [
            {
                "year": year,
                "first_observed_on": min(values).isoformat(),
                "last_observed_on": max(values).isoformat(),
                "observation_count": len(values),
            }
            for year, values in sorted(year_ranges.items(), reverse=True)
        ],
        "phenophases": [
            {"code": code, "count": count}
            for code, count in sorted(phenophases.items(), key=lambda item: (-item[1], item[0]))
        ],
        "guidance": "This summarizes your own dated observations, not the species' biological range.",
    }


def build_place_profile(
    location: dict[str, Any],
    hikes: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    hike_ids = {str(hike.get("id") or "") for hike in hikes}
    place_observations = [item for item in observations if str(item.get("hike_id") or "") in hike_ids]
    by_species: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in place_observations:
        by_species[species_key(item)].append(item)
    hike_dates = sorted(str(hike.get("hike_date") or "")[:10] for hike in hikes if hike.get("hike_date"))
    taxon_counts = Counter(
        str(items[0].get("iconic_taxon_name") or "Other")
        for items in by_species.values()
    )
    taxon_groups = []
    for group_name, count in sorted(taxon_counts.items(), key=lambda item: (-item[1], item[0])):
        species = [
            {**_species_snapshot(items[0]), "encounter_count": len(items)}
            for items in by_species.values()
            if str(items[0].get("iconic_taxon_name") or "Other") == group_name
        ]
        species.sort(key=lambda item: (item["common_name"].casefold(), item["scientific_name"].casefold()))
        taxon_groups.append({"name": group_name, "count": count, "species": species})
    seen: set[str] = set()
    visits = []
    for hike in sorted(hikes, key=lambda item: str(item.get("hike_date") or "")):
        hike_id = str(hike.get("id") or "")
        keys = {species_key(item) for item in place_observations if str(item.get("hike_id") or "") == hike_id}
        new_keys = keys - seen
        seen.update(keys)
        visits.append(
            {
                "hike_id": hike_id,
                "title": str(hike.get("title") or "Untitled hike"),
                "hike_date": str(hike.get("hike_date") or ""),
                "distance_miles": hike.get("distance_miles"),
                "duration_seconds": hike.get("duration_seconds"),
                "observation_count": sum(
                    1 for item in place_observations if str(item.get("hike_id") or "") == hike_id
                ),
                "species_count": len(keys),
                "new_species_count": len(new_keys),
                "cumulative_species_count": len(seen),
                "cover_url": str(hike.get("cover_url") or ""),
            }
        )
    visits.reverse()
    return {
        "location": {
            "id": str(location.get("id") or ""),
            "name": str(location.get("name") or "Unknown place"),
            "location_type": str(location.get("location_type") or ""),
            "lat": location.get("lat"),
            "lng": location.get("lng"),
        },
        "summary": {
            "first_visit": hike_dates[0] if hike_dates else None,
            "latest_visit": hike_dates[-1] if hike_dates else None,
            "outing_count": len(hikes),
            "total_distance_miles": round(sum(float(hike.get("distance_miles") or 0) for hike in hikes), 2),
            "total_duration_seconds": sum(int(hike.get("duration_seconds") or 0) for hike in hikes),
            "observation_count": len(place_observations),
            "species_count": len(by_species),
        },
        "taxon_counts": [
            {"name": name, "count": count}
            for name, count in sorted(taxon_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "taxon_groups": taxon_groups,
        "seasonal_history": build_seasonal_history(place_observations),
        "visits": visits,
        "frequent_species": [
            {**_species_snapshot(items[0]), "encounter_count": len(items)}
            for _, items in sorted(by_species.items(), key=lambda item: (-len(item[1]), item[0]))[:20]
        ],
        "guidance": (
            "This profile is derived from your own recorded visits and confirmed observations."
            if hikes
            else "Live planning information is available before your first recorded visit."
        ),
    }


def _hike_species(observations: list[dict[str, Any]], hike_id: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in observations:
        if str(item.get("hike_id") or "") == hike_id:
            result.setdefault(species_key(item), _species_snapshot(item))
    return result


def build_hike_comparison(
    hike_a: dict[str, Any],
    hike_b: dict[str, Any],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    a = _hike_species(observations, str(hike_a.get("id") or ""))
    b = _hike_species(observations, str(hike_b.get("id") or ""))
    shared = sorted(a.keys() & b.keys())
    only_a = sorted(a.keys() - b.keys())
    only_b = sorted(b.keys() - a.keys())

    def hike_summary(hike: dict[str, Any], species: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return {
            "id": str(hike.get("id") or ""),
            "title": str(hike.get("title") or "Untitled hike"),
            "hike_date": str(hike.get("hike_date") or ""),
            "location_name": str(hike.get("location_name") or ""),
            "distance_miles": hike.get("distance_miles"),
            "duration_seconds": hike.get("duration_seconds"),
            "photo_count": int(hike.get("photo_count") or 0),
            "observation_count": sum(
                1 for item in observations if str(item.get("hike_id") or "") == str(hike.get("id") or "")
            ),
            "species_count": len(species),
        }

    return {
        "hike_a": hike_summary(hike_a, a),
        "hike_b": hike_summary(hike_b, b),
        "species": {
            "shared": [a[key] for key in shared],
            "only_a": [a[key] for key in only_a],
            "only_b": [b[key] for key in only_b],
        },
        "guidance": "Species lists compare your confirmed records from each outing.",
    }


def build_field_briefing(
    *,
    target_date: date,
    nearby_taxa: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    place_hike_ids: set[str] | None = None,
    active_quest_taxon_ids: set[int] | None = None,
    limit: int = 18,
) -> dict[str, Any]:
    place_hike_ids = place_hike_ids or set()
    active_quest_taxon_ids = active_quest_taxon_ids or set()
    personal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in observations:
        personal[species_key(item)].append(item)

    ranked: list[tuple[int, int, str, dict[str, Any]]] = []
    seen_taxa: set[str] = set()
    for index, taxon in enumerate(nearby_taxa):
        key = species_key(taxon)
        if key in seen_taxa:
            continue
        seen_taxa.add(key)
        history = personal.get(key, [])
        dated = [(item, observation_date(item)) for item in history]
        dated = [(item, observed) for item, observed in dated if observed is not None]
        around_month = [pair for pair in dated if pair[1].month == target_date.month]
        at_place = [
            pair for pair in dated if str(pair[0].get("hike_id") or "") in place_hike_ids
        ]
        taxon_id = taxon.get("taxon_id") or taxon.get("species_taxon_id")
        reasons: list[str] = []
        section = "Worth watching for"
        score = max(0, 40 - index)
        if not history:
            section = "Missing from your Field Guide"
            reasons.append("Not yet in your confirmed Field Guide.")
            score += 80
        elif around_month:
            previous_years = sorted({observed.year for _, observed in around_month if observed.year < target_date.year})
            if previous_years and not any(observed.year == target_date.year for _, observed in around_month):
                section = "Seasonal returns"
                reasons.append(
                    "You recorded this around this time in "
                    + ", ".join(str(year) for year in previous_years[-3:])
                    + "."
                )
                score += 100
        if at_place:
            reasons.append(f"You recorded this at this place {len(at_place)} time{'s' if len(at_place) != 1 else ''}.")
            score += 45
        if taxon_id not in (None, "") and int(taxon_id) in active_quest_taxon_ids:
            reasons.append("This is an active Field Quest target.")
            score += 35
        if history and dated:
            latest = max(observed for _, observed in dated)
            days = (target_date - latest).days
            if days >= 180:
                if section == "Worth watching for":
                    section = "Old friends"
                reasons.append(f"Last recorded {days} days ago.")
                score += min(days // 30, 20)
        nearby_reason = str(taxon.get("match_reason") or "").strip()
        reasons.append(nearby_reason or "Reported nearby on iNaturalist during this part of the year.")
        ranked.append(
            (
                -score,
                index,
                key,
                {
                    **_species_snapshot(taxon),
                    "section": section,
                    "score": score,
                    "reasons": reasons,
                    "reference_photo": taxon.get("reference_photo"),
                    "nearby_rank": taxon.get("nearby_rank") or index + 1,
                },
            )
        )
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    recommendations = [item[3] for item in ranked[: max(1, min(limit, 50))]]
    sections = []
    for label in (
        "Seasonal returns",
        "Missing from your Field Guide",
        "Worth watching for",
        "Old friends",
    ):
        items = [item for item in recommendations if item["section"] == label]
        if items:
            sections.append({"title": label, "items": items})
    return {
        "target_date": target_date.isoformat(),
        "algorithm_version": BRIEFING_ALGORITHM_VERSION,
        "sections": sections,
        "recommendation_count": len(recommendations),
        "guidance": (
            "Nearby reporting frequency comes from iNaturalist and is not encounter probability. "
            "Personal-history reasons use only your HikeJournal records."
        ),
    }
