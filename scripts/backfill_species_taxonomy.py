from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hike_journal.config import settings
from hike_journal.services.inat import InatClient
from hike_journal.services.repositories import HikeJournalRepository
from hike_journal.services.supabase_transport import build_supabase_client
from hike_journal.services.taxonomy import (
    normalize_taxon_name,
    resolve_observation_enrichment,
    taxonomy_resolution_fields,
)
from hike_journal.services.wikipedia import fill_missing_wikipedia_summary


def build_wikipedia_backfill_plan(observations: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any], bool]]:
    """Prepare only confirmed observations with iNaturalist taxonomy but no blurb."""
    def prepare(observation: dict[str, Any]) -> tuple[str, dict[str, Any], bool] | None:
        raw_payload = dict(observation.get("raw_response_json") or {})
        enrichment = raw_payload.get("taxon_enrichment")
        if not isinstance(enrichment, dict):
            return None
        updated_enrichment, changed = fill_missing_wikipedia_summary(enrichment)
        if changed:
            raw_payload["taxon_enrichment"] = updated_enrichment
            return (
                str(observation["id"]),
                raw_payload,
                bool(str(updated_enrichment.get("wikipedia_summary") or "").strip()),
            )
        return None

    # Wikipedia lookups are independent; modest parallelism keeps a large archive
    # practical without putting a burst of traffic on the public endpoint.
    with ThreadPoolExecutor(max_workers=6) as executor:
        return [item for item in executor.map(prepare, observations) if item is not None]


def build_reconciliation_plan(
    observations: list[dict[str, Any]],
    inat_client: InatClient,
) -> dict[str, Any]:
    requested_ids = sorted(
        {
            int(observation["taxon_id"])
            for observation in observations
            if observation.get("taxon_id") not in (None, "")
        }
    )
    enrichments_by_id = inat_client.fetch_taxon_enrichments(requested_ids)
    synonym_ids = sorted(
        {
            int(value)
            for enrichment in enrichments_by_id.values()
            for value in enrichment.get("current_synonymous_taxon_ids") or []
            if str(value).isdigit()
        }
    )
    if synonym_ids:
        enrichments_by_id.update(inat_client.fetch_taxon_enrichments(synonym_ids))

    exact_name_cache: dict[str, dict[str, Any] | None] = {}

    def exact_name_lookup(query: str) -> dict[str, Any] | None:
        key = normalize_taxon_name(query)
        if key not in exact_name_cache:
            exact_name_cache[key] = inat_client.fetch_exact_taxon_enrichment(query)
        return exact_name_cache[key]

    groups: dict[tuple[int, str | None, str | None, int | None], list[str]] = defaultdict(list)
    enrichment_backfills: list[tuple[str, dict[str, Any]]] = []
    unresolved: list[dict[str, Any]] = []
    corrections: list[dict[str, Any]] = []
    already_current = 0

    for observation in observations:
        original_taxon_id = int(observation["taxon_id"])
        enrichment = resolve_observation_enrichment(
            observation,
            enrichment_for_taxon_id=enrichments_by_id.get(original_taxon_id),
            exact_name_lookup=exact_name_lookup,
            current_enrichments_by_id=enrichments_by_id,
        )
        if not enrichment:
            unresolved.append(observation)
            continue
        raw_payload = dict(observation.get("raw_response_json") or {})
        stored_enrichment = raw_payload.get("taxon_enrichment")
        if not isinstance(stored_enrichment, dict) or not {
            "wikipedia_url",
            "wikipedia_summary",
        }.issubset(stored_enrichment):
            raw_payload["taxon_enrichment"] = enrichment
            enrichment_backfills.append((str(observation["id"]), raw_payload))
        fields = taxonomy_resolution_fields(enrichment)
        existing_fields = {
            "taxon_id": original_taxon_id,
            "rank": normalize_taxon_name(observation.get("rank")) or None,
            "iconic_taxon_name": str(observation.get("iconic_taxon_name") or "").strip() or None,
            "species_taxon_id": (
                int(observation["species_taxon_id"])
                if observation.get("species_taxon_id") not in (None, "")
                else None
            ),
        }
        if fields == existing_fields:
            already_current += 1
            continue
        group_key = (
            fields["taxon_id"],
            fields["rank"],
            fields["iconic_taxon_name"],
            fields["species_taxon_id"],
        )
        groups[group_key].append(str(observation["id"]))
        if fields["taxon_id"] != original_taxon_id:
            corrections.append(
                {
                    "from_taxon_id": original_taxon_id,
                    "to_taxon_id": fields["taxon_id"],
                    "scientific_name": observation.get("scientific_name"),
                    "common_name": observation.get("common_name"),
                }
            )

    return {
        "groups": groups,
        "enrichment_backfills": enrichment_backfills,
        "requested_taxa": len(requested_ids),
        "resolved_taxa": len({key[0] for key in groups}),
        "changed": sum(len(ids) for ids in groups.values()),
        "already_current": already_current,
        "unresolved": unresolved,
        "corrections": corrections,
    }


def print_plan(plan: dict[str, Any]) -> None:
    print(
        {
            "requested_taxa": plan["requested_taxa"],
            "rows_to_update": plan["changed"],
            "rows_missing_enrichment": len(plan["enrichment_backfills"]),
            "already_current": plan["already_current"],
            "identity_corrections": len(plan["corrections"]),
            "unresolved": len(plan["unresolved"]),
        }
    )
    correction_counts: dict[tuple[Any, ...], int] = defaultdict(int)
    for item in plan["corrections"]:
        correction_counts[
            (
                item["from_taxon_id"],
                item["to_taxon_id"],
                item.get("scientific_name") or item.get("common_name") or "Unknown",
            )
        ] += 1
    for (old_id, new_id, name), count in sorted(correction_counts.items()):
        print(f"correct {count} × {name}: {old_id} -> {new_id}")
    for observation in plan["unresolved"]:
        print(
            "unresolved "
            f"{observation.get('id')}: "
            f"{observation.get('scientific_name') or observation.get('common_name') or 'Unknown'} "
            f"(taxon {observation.get('taxon_id')})"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconcile confirmed HikeJournal observations with iNaturalist taxonomy.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the planned taxonomy corrections and missing iNaturalist enrichment, including Wikipedia fields.",
    )
    parser.add_argument(
        "--enrichment-only",
        action="store_true",
        help="With --apply, write only missing iNaturalist enrichment and leave existing taxonomy fields unchanged.",
    )
    parser.add_argument(
        "--wikipedia-fallback",
        action="store_true",
        help="Fetch concise Wikipedia summaries for confirmed observations that iNaturalist did not populate.",
    )
    args = parser.parse_args()
    if not settings.supabase_configured:
        raise SystemExit("SUPABASE_URL and SUPABASE_KEY are required.")

    repository = HikeJournalRepository(
        build_supabase_client(settings.supabase_url, settings.supabase_key),
    )
    observations = repository.list_observations_for_taxonomy_reconciliation()
    if args.wikipedia_fallback:
        updates = build_wikipedia_backfill_plan(observations)
        summaries_added = sum(1 for _, _, added_summary in updates if added_summary)
        print(
            {
                "observations_missing_wikipedia": len(updates),
                "summaries_found": summaries_added,
                "no_unambiguous_article": len(updates) - summaries_added,
            }
        )
        if not args.apply:
            print("Dry run only. Re-run with --apply to write these Wikipedia summaries.")
            return
        for observation_id, raw_payload, _ in updates:
            repository.update_observation_raw_payload(observation_id, raw_payload)
        print(f"Added {summaries_added} Wikipedia summaries and recorded {len(updates) - summaries_added} unambiguous no-matches.")
        return
    plan = build_reconciliation_plan(
        observations,
        InatClient(access_token="", base_url=settings.inat_base_url),
    )
    print_plan(plan)
    if not args.apply:
        print("Dry run only. Re-run with --apply to write these changes.")
        return

    updated = 0
    if not args.enrichment_only:
        for (taxon_id, rank, iconic_taxon_name, species_taxon_id), observation_ids in plan["groups"].items():
            updated += repository.update_observation_taxon_resolutions(
                observation_ids,
                taxon_id=taxon_id,
                rank=rank,
                iconic_taxon_name=iconic_taxon_name,
                species_taxon_id=species_taxon_id,
            )
    enriched = 0
    for observation_id, raw_payload in plan["enrichment_backfills"]:
        repository.update_observation_raw_payload(observation_id, raw_payload)
        enriched += 1
    print(f"Updated taxonomy on {updated} confirmed observations and enriched {enriched} observations.")


if __name__ == "__main__":
    main()
