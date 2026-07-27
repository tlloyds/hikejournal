from __future__ import annotations

import re
from typing import Any, Callable

from hike_journal.domain.discovery import INFRASPECIES_RANKS
from hike_journal.services.inat import InatClient, InatRequestError
from hike_journal.services.repositories import HikeJournalRepository


def normalize_taxon_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def observation_matches_taxon_enrichment(
    observation: dict[str, Any],
    enrichment: dict[str, Any],
) -> bool:
    """Require the stored identity to agree with iNaturalist before trusting an old ID."""
    local_scientific = normalize_taxon_name(observation.get("scientific_name"))
    remote_scientific = normalize_taxon_name(enrichment.get("scientific_name"))
    if local_scientific and remote_scientific and local_scientific == remote_scientific:
        return True

    local_common = normalize_taxon_name(observation.get("common_name"))
    remote_common_names = {
        normalize_taxon_name(enrichment.get("preferred_common_name")),
        normalize_taxon_name(enrichment.get("english_common_name")),
        *{
            normalize_taxon_name(value)
            for value in enrichment.get("alias_names") or []
        },
    }
    remote_common_names.discard("")
    return bool(local_common and local_common in remote_common_names)


def taxon_enrichment_is_complete(enrichment: Any) -> bool:
    if not isinstance(enrichment, dict):
        return False
    taxon_id = enrichment.get("taxon_id")
    rank = normalize_taxon_name(enrichment.get("rank"))
    if taxon_id in (None, "") or not rank:
        return False
    if rank in INFRASPECIES_RANKS:
        return enrichment.get("species_taxon_id") not in (None, "")
    return True


def preferred_current_enrichment(
    enrichment: dict[str, Any],
    enrichments_by_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Follow an inactive taxon only when iNaturalist supplies a current taxon at the same rank."""
    if enrichment.get("is_active") is not False:
        return enrichment
    rank = normalize_taxon_name(enrichment.get("rank"))
    current = [
        enrichments_by_id.get(int(taxon_id))
        for taxon_id in enrichment.get("current_synonymous_taxon_ids") or []
        if str(taxon_id).isdigit()
    ]
    same_rank = [
        item
        for item in current
        if isinstance(item, dict)
        and item.get("is_active") is not False
        and normalize_taxon_name(item.get("rank")) == rank
    ]
    return same_rank[0] if len(same_rank) == 1 else enrichment


def resolve_observation_enrichment(
    observation: dict[str, Any],
    *,
    enrichment_for_taxon_id: dict[str, Any] | None,
    exact_name_lookup: Callable[[str], dict[str, Any] | None],
    current_enrichments_by_id: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    candidate = enrichment_for_taxon_id
    if candidate and current_enrichments_by_id:
        candidate = preferred_current_enrichment(candidate, current_enrichments_by_id)
    if (
        candidate
        and taxon_enrichment_is_complete(candidate)
        and observation_matches_taxon_enrichment(observation, candidate)
    ):
        return candidate

    searched: set[str] = set()
    for value in (observation.get("scientific_name"), observation.get("common_name")):
        query = str(value or "").strip()
        normalized = normalize_taxon_name(query)
        if not normalized or normalized in searched:
            continue
        searched.add(normalized)
        resolved = exact_name_lookup(query)
        if (
            resolved
            and taxon_enrichment_is_complete(resolved)
            and observation_matches_taxon_enrichment(observation, resolved)
        ):
            return resolved
    return None


def taxonomy_resolution_fields(enrichment: dict[str, Any]) -> dict[str, Any]:
    rank = normalize_taxon_name(enrichment.get("rank")) or None
    taxon_id = int(enrichment["taxon_id"])
    species_taxon_id = enrichment.get("species_taxon_id")
    if rank == "species":
        species_taxon_id = taxon_id
    elif rank not in INFRASPECIES_RANKS:
        species_taxon_id = None
    return {
        "taxon_id": taxon_id,
        "rank": rank,
        "iconic_taxon_name": str(enrichment.get("iconic_taxon_name") or "").strip() or None,
        "species_taxon_id": int(species_taxon_id) if species_taxon_id not in (None, "") else None,
    }


def ensure_observation_taxonomy(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    observation: dict[str, Any],
) -> bool:
    taxon_id = observation.get("taxon_id")
    raw_payload = dict(observation.get("raw_response_json") or {})
    cached = raw_payload.get("taxon_enrichment")
    enrichment: dict[str, Any] | None = None

    try:
        if (
            taxon_enrichment_is_complete(cached)
            and observation_matches_taxon_enrichment(observation, cached)
            and (
                taxon_id in (None, "")
                or str(cached.get("taxon_id")) == str(taxon_id)
            )
        ):
            enrichment = cached
        elif taxon_id not in (None, ""):
            fetched = inat_client.fetch_taxon_enrichment(int(taxon_id))
            current_by_id: dict[int, dict[str, Any]] = {}
            synonym_ids = [
                int(value)
                for value in fetched.get("current_synonymous_taxon_ids") or []
                if str(value).isdigit()
            ]
            if fetched.get("is_active") is False and synonym_ids:
                current_by_id = inat_client.fetch_taxon_enrichments(synonym_ids)
            enrichment = resolve_observation_enrichment(
                observation,
                enrichment_for_taxon_id=fetched,
                exact_name_lookup=inat_client.fetch_exact_taxon_enrichment,
                current_enrichments_by_id=current_by_id,
            )
        else:
            enrichment = resolve_observation_enrichment(
                observation,
                enrichment_for_taxon_id=None,
                exact_name_lookup=inat_client.fetch_exact_taxon_enrichment,
            )
    except (InatRequestError, TypeError, ValueError):
        return False

    if not enrichment:
        return False
    resolution = taxonomy_resolution_fields(enrichment)
    updated = repository.update_observation_taxon_resolution(
        str(observation["id"]),
        taxon_id=resolution["taxon_id"],
        rank=resolution["rank"],
        iconic_taxon_name=resolution["iconic_taxon_name"],
        species_taxon_id=resolution["species_taxon_id"],
    )
    if updated is None:
        return False
    raw_payload["taxon_enrichment"] = enrichment
    repository.update_observation_raw_payload(str(observation["id"]), raw_payload)
    return True
