from __future__ import annotations

from typing import Any


SPECIES_TYPE_OPTIONS = (
    "All types",
    "Plants",
    "Animals",
    "Birds",
    "Mammals",
    "Insects",
    "Reptiles",
    "Amphibians",
    "Arachnids",
    "Fungi",
    "Fish",
    "Mollusks",
    "Other life",
)

_ANIMAL_ICONIC_TAXA = {
    "animalia",
    "aves",
    "mammalia",
    "insecta",
    "reptilia",
    "amphibia",
    "arachnida",
    "actinopterygii",
    "mollusca",
}

_SPECIES_TYPE_TAXA = {
    "Plants": {"plantae"},
    "Animals": _ANIMAL_ICONIC_TAXA,
    "Birds": {"aves"},
    "Mammals": {"mammalia"},
    "Insects": {"insecta"},
    "Reptiles": {"reptilia"},
    "Amphibians": {"amphibia"},
    "Arachnids": {"arachnida"},
    "Fungi": {"fungi"},
    "Fish": {"actinopterygii"},
    "Mollusks": {"mollusca"},
}

_KNOWN_ICONIC_TAXA = {
    "plantae",
    "fungi",
    *_ANIMAL_ICONIC_TAXA,
}


def observation_matches_species_type(
    observation: dict[str, Any],
    species_type: str,
) -> bool:
    """Return whether an observation belongs in a Species Log type filter."""
    if species_type == "All types":
        return True
    iconic_taxon = str(observation.get("iconic_taxon_name") or "").strip().casefold()
    if species_type == "Other life":
        return iconic_taxon not in _KNOWN_ICONIC_TAXA
    return iconic_taxon in _SPECIES_TYPE_TAXA.get(species_type, set())
