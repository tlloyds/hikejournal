from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hike_journal.domain.discovery import build_collection_index, scientific_species_key


@dataclass(frozen=True)
class BadgeCategory:
    key: str
    label: str
    description: str


@dataclass(frozen=True)
class BadgeDefinition:
    id: str
    title: str
    requirement: str
    category: BadgeCategory
    metric: str
    target: float
    finish: str
    mark: str


@dataclass(frozen=True)
class TrailBadge:
    definition: BadgeDefinition
    current: float

    @property
    def earned(self) -> bool:
        return self.current >= self.definition.target

    @property
    def progress(self) -> float:
        return min(max(self.current / self.definition.target, 0.0), 1.0)


HIKING = BadgeCategory("hiking", "Hiking", "Milestones for showing up, season after season.")
DISTANCE = BadgeCategory("distance", "Distance", "Lifetime miles and the days that went farther.")
QUESTS = BadgeCategory("quests", "Field quests", "Completed targets and less-often-reported finds.")
FIELD_GUIDE = BadgeCategory("field-guide", "Field guide", "New species added to your personal archive.")
SPECIALTIES = BadgeCategory("specialties", "Specialties", "Deeper knowledge across the living world.")
BADGE_CATEGORIES = (HIKING, DISTANCE, QUESTS, FIELD_GUIDE, SPECIALTIES)


def _badge(
    id: str,
    title: str,
    requirement: str,
    category: BadgeCategory,
    metric: str,
    target: int | float,
    finish: str,
    mark: str,
) -> BadgeDefinition:
    return BadgeDefinition(
        id=id,
        title=title,
        requirement=requirement,
        category=category,
        metric=metric,
        target=float(target),
        finish=finish,
        mark=mark,
    )


TRAIL_BADGE_CATALOG = (
    _badge("hikes_1", "First Footfall", "Log your first hike.", HIKING, "hike_count", 1, "bronze", "H"),
    _badge("hikes_5", "Five Trails", "Log 5 hikes.", HIKING, "hike_count", 5, "bronze", "H"),
    _badge("hikes_10", "Trail Regular", "Log 10 hikes.", HIKING, "hike_count", 10, "silver", "H"),
    _badge("hikes_25", "Seasoned Trekker", "Log 25 hikes.", HIKING, "hike_count", 25, "gold", "H"),
    _badge("hikes_50", "Half-Century Hiker", "Log 50 hikes.", HIKING, "hike_count", 50, "gold", "H"),
    _badge("hikes_100", "Hundred Horizons", "Log 100 hikes.", HIKING, "hike_count", 100, "evergreen", "H"),

    _badge("miles_25", "First 25", "Record 25 lifetime miles.", DISTANCE, "total_miles", 25, "bronze", "MI"),
    _badge("miles_100", "Century Afoot", "Record 100 lifetime miles.", DISTANCE, "total_miles", 100, "silver", "MI"),
    _badge("miles_250", "Long Way Home", "Record 250 lifetime miles.", DISTANCE, "total_miles", 250, "gold", "MI"),
    _badge("miles_500", "Ridgeline 500", "Record 500 lifetime miles.", DISTANCE, "total_miles", 500, "gold", "MI"),
    _badge("miles_1000", "Thousand-Mile Journal", "Record 1,000 lifetime miles.", DISTANCE, "total_miles", 1000, "evergreen", "MI"),
    _badge("long_hike_10", "Double Digits", "Complete a hike of at least 10 miles.", DISTANCE, "longest_hike", 10, "silver", "10+"),
    _badge("long_hike_20", "Endurance Day", "Complete a hike of at least 20 miles.", DISTANCE, "longest_hike", 20, "evergreen", "20+"),

    _badge("quests_1", "Quest Complete", "Complete every focus find in 1 Field Quest.", QUESTS, "completed_quests", 1, "bronze", "Q"),
    _badge("quests_5", "Field Proven", "Complete 5 Field Quests.", QUESTS, "completed_quests", 5, "gold", "Q"),
    _badge("quests_10", "Quest Naturalist", "Complete 10 Field Quests.", QUESTS, "completed_quests", 10, "evergreen", "Q"),
    _badge("rare_1", "Rare Find", "Log 1 quest species marked less often reported.", QUESTS, "rare_finds", 1, "silver", "✦"),
    _badge("rare_5", "Rare Company", "Log 5 distinct less-often-reported quest species.", QUESTS, "rare_finds", 5, "gold", "✦"),

    _badge("species_1", "New Find", "Add your first species to the Field Guide.", FIELD_GUIDE, "species_count", 1, "bronze", "S"),
    _badge("species_25", "Curious Naturalist", "Log 25 distinct species.", FIELD_GUIDE, "species_count", 25, "bronze", "S"),
    _badge("species_50", "Field Naturalist", "Log 50 distinct species.", FIELD_GUIDE, "species_count", 50, "silver", "S"),
    _badge("species_100", "Century of Life", "Log 100 distinct species.", FIELD_GUIDE, "species_count", 100, "gold", "S"),
    _badge("species_250", "Living Archive", "Log 250 distinct species.", FIELD_GUIDE, "species_count", 250, "evergreen", "S"),

    _badge("plants_25", "Leaf Scout", "Log 25 distinct plants.", SPECIALTIES, "plants", 25, "bronze", "PL"),
    _badge("plants_50", "Field Botanist", "Log 50 distinct plants.", SPECIALTIES, "plants", 50, "silver", "PL"),
    _badge("plants_100", "Flora Authority", "Log 100 distinct plants.", SPECIALTIES, "plants", 100, "evergreen", "PL"),
    _badge("mammals_25", "Mammal Tracker", "Log 25 distinct mammals.", SPECIALTIES, "mammals", 25, "bronze", "MA"),
    _badge("mammals_50", "Wildlife Observer", "Log 50 distinct mammals.", SPECIALTIES, "mammals", 50, "silver", "MA"),
    _badge("mammals_100", "Mammal Steward", "Log 100 distinct mammals.", SPECIALTIES, "mammals", 100, "evergreen", "MA"),
    _badge("fungi_25", "Mycology Scout", "Log 25 distinct fungi.", SPECIALTIES, "fungi", 25, "bronze", "FU"),
    _badge("fungi_50", "Field Mycologist", "Log 50 distinct fungi.", SPECIALTIES, "fungi", 50, "silver", "FU"),
    _badge("fungi_100", "Fungi Authority", "Log 100 distinct fungi.", SPECIALTIES, "fungi", 100, "evergreen", "FU"),
    _badge("birds_25", "Bird Listener", "Log 25 distinct birds.", SPECIALTIES, "birds", 25, "bronze", "BI"),
    _badge("birds_50", "Avian Observer", "Log 50 distinct birds.", SPECIALTIES, "birds", 50, "gold", "BI"),
    _badge("insects_25", "Insect Eye", "Log 25 distinct insects.", SPECIALTIES, "insects", 25, "bronze", "IN"),
    _badge("insects_50", "Invertebrate Observer", "Log 50 distinct insects.", SPECIALTIES, "insects", 50, "gold", "IN"),
)


def _species_identity(observation: dict[str, Any]) -> str:
    species_taxon_id = observation.get("species_taxon_id")
    if species_taxon_id not in (None, ""):
        return f"taxon:{species_taxon_id}"
    taxon_id = observation.get("taxon_id")
    if taxon_id not in (None, ""):
        return f"taxon:{taxon_id}"
    scientific_name = str(observation.get("scientific_name") or "").strip().casefold()
    if scientific_name:
        return f"scientific:{scientific_name}"
    return f"common:{str(observation.get('common_name') or 'unknown').strip().casefold()}"


def _distinct_species(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    distinct: dict[str, dict[str, Any]] = {}
    for observation in observations:
        key = _species_identity(observation)
        existing = distinct.get(key)
        if existing is None or (
            not str(existing.get("iconic_taxon_name") or "").strip()
            and str(observation.get("iconic_taxon_name") or "").strip()
        ):
            distinct[key] = observation
    return list(distinct.values())


def _target_collected(item: dict[str, Any], collection: dict[int | str, dict[str, Any]]) -> bool:
    try:
        taxon_id = int(item["taxon_id"])
    except (KeyError, TypeError, ValueError):
        taxon_id = None
    if taxon_id is not None and taxon_id in collection:
        return True
    scientific_key = scientific_species_key(str(item.get("scientific_name") or ""))
    return scientific_key is not None and scientific_key in collection


def calculate_trail_badges(
    hikes: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    quests: list[dict[str, Any]],
) -> list[TrailBadge]:
    species = _distinct_species(observations)
    collection = build_collection_index(observations, {})
    completed_quests = 0
    rare_find_keys: set[str] = set()
    for quest in quests:
        focus_taxa = [item for item in quest.get("taxa") or [] if item.get("focus_order")]
        if focus_taxa and all(_target_collected(item, collection) for item in focus_taxa):
            completed_quests += 1
        for item in quest.get("taxa") or []:
            if (
                _target_collected(item, collection)
                and "less often" in str(item.get("frequency_band") or "").casefold()
            ):
                rare_find_keys.add(
                    f"taxon:{item.get('taxon_id')}"
                    if item.get("taxon_id") not in (None, "")
                    else scientific_species_key(str(item.get("scientific_name") or "")) or "unknown"
                )

    def iconic_count(*names: str) -> int:
        accepted = {name.casefold() for name in names}
        return sum(
            1
            for observation in species
            if str(observation.get("iconic_taxon_name") or "").casefold() in accepted
        )

    distances = [
        max(float(hike.get("distance_miles") or 0.0), 0.0)
        for hike in hikes
    ]
    metrics = {
        "hike_count": float(len(hikes)),
        "total_miles": sum(distances),
        "longest_hike": max(distances, default=0.0),
        "completed_quests": float(completed_quests),
        "rare_finds": float(len(rare_find_keys)),
        "species_count": float(len(species)),
        "plants": float(iconic_count("Plantae", "Plant")),
        "mammals": float(iconic_count("Mammalia", "Mammal")),
        "fungi": float(iconic_count("Fungi", "Fungus")),
        "birds": float(iconic_count("Aves", "Bird")),
        "insects": float(iconic_count("Insecta", "Insect")),
    }
    return [
        TrailBadge(definition=definition, current=metrics[definition.metric])
        for definition in TRAIL_BADGE_CATALOG
    ]
