#!/usr/bin/env python3
"""Backfill place-aware ecological status into existing confirmed observations."""

from __future__ import annotations

import argparse
from collections import Counter
import sys
from pathlib import Path

# Allow the script to be run directly from the repository root or from any
# working directory without requiring callers to set PYTHONPATH manually.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supabase import create_client
from hike_journal.config import settings
from hike_journal.services.inat import InatClient, InatRequestError
from hike_journal.services.repositories import HikeJournalRepository


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--status",
        default="confirmed",
        choices=("confirmed", "pending"),
        help="Observation status to refresh (default: confirmed).",
    )
    args = parser.parse_args()

    if not settings.supabase_configured:
        raise SystemExit("SUPABASE_URL and SUPABASE_KEY are required for the ecology backfill.")
    supabase_client = create_client(settings.supabase_url, settings.supabase_key)
    repository = HikeJournalRepository(supabase_client)
    inat_client = InatClient(access_token="", base_url=settings.inat_base_url)
    observations = repository.list_observations_for_taxonomy_reconciliation(status=args.status)
    taxon_ids = sorted({int(row["taxon_id"]) for row in observations if row.get("taxon_id")})
    if not taxon_ids:
        print("No observations need ecological backfill.")
        return 0

    enrichments = inat_client.fetch_taxon_enrichments(taxon_ids)
    updated = 0
    labels: Counter[str] = Counter()
    for observation in observations:
        taxon_id = observation.get("taxon_id")
        enrichment = enrichments.get(int(taxon_id)) if taxon_id else None
        if not isinstance(enrichment, dict):
            continue
        raw_payload = dict(observation.get("raw_response_json") or {})
        raw_payload["taxon_enrichment"] = enrichment
        repository.upsert_taxon_ecology_status(enrichment)
        repository.update_observation_raw_payload(str(observation["id"]), raw_payload)
        label = str((enrichment.get("ecology") or {}).get("label") or "unknown")
        labels[label] += 1
        updated += 1

    print(
        f"Updated {updated} observations across {len(enrichments)} taxa "
        f"for {settings.inat_ecology_region}: {dict(labels)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InatRequestError as exc:
        raise SystemExit(f"iNaturalist ecology backfill failed: {exc}") from exc
