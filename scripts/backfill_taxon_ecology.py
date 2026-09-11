#!/usr/bin/env python3
"""Backfill place-aware ecological status into existing confirmed observations."""

from __future__ import annotations

import argparse
from collections import Counter
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _bootstrap_project_python() -> None:
    """Re-run with the repository virtualenv when plain python3 lacks deps."""
    project_python = REPOSITORY_ROOT / ".venv" / "bin" / "python"
    if not project_python.is_file() or Path(sys.executable).resolve() == project_python.resolve():
        return
    try:
        import supabase  # noqa: F401
    except ModuleNotFoundError as exc:
        if exc.name != "supabase":
            raise
        os.execv(
            str(project_python),
            [str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        )


_bootstrap_project_python()

# Allow the script to be run directly from the repository root or from any
# working directory without requiring callers to set PYTHONPATH manually.
sys.path.insert(0, str(REPOSITORY_ROOT))

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
    observations = repository.list_observations_for_taxonomy_reconciliation(
        status=args.status,
        page_size=25,
    )
    taxon_ids = sorted({int(row["taxon_id"]) for row in observations if row.get("taxon_id")})
    if not taxon_ids:
        print("No observations need ecological backfill.")
        return 0

    enrichments = inat_client.fetch_taxon_enrichments(taxon_ids)
    canonical_count = repository.upsert_taxon_ecology_statuses(list(enrichments.values()))
    updated = 0
    skipped = 0
    labels: Counter[str] = Counter()
    for observation in observations:
        taxon_id = observation.get("taxon_id")
        enrichment = enrichments.get(int(taxon_id)) if taxon_id else None
        if not isinstance(enrichment, dict):
            continue
        raw_payload = dict(observation.get("raw_response_json") or {})
        existing_enrichment = raw_payload.get("taxon_enrichment")
        existing_ecology = (
            existing_enrichment.get("ecology")
            if isinstance(existing_enrichment, dict)
            else None
        )
        existing_label = (
            str(existing_ecology.get("label") or "unknown").strip().casefold()
            if isinstance(existing_ecology, dict)
            else "unknown"
        )
        if (
            isinstance(existing_ecology, dict)
            and str(existing_ecology.get("region_code") or "")
            == settings.inat_ecology_region
            and existing_label != "unknown"
        ):
            label = existing_label
            labels[label] += 1
            skipped += 1
            continue
        raw_payload["taxon_enrichment"] = enrichment
        repository.update_observation_raw_payload(str(observation["id"]), raw_payload)
        label = str((enrichment.get("ecology") or {}).get("label") or "unknown")
        labels[label] += 1
        updated += 1

    print(
        f"Persisted {canonical_count} canonical taxa; updated {updated} observations "
        f"and skipped {skipped} current snapshots "
        f"for {settings.inat_ecology_region}: {dict(labels)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InatRequestError as exc:
        raise SystemExit(f"iNaturalist ecology backfill failed: {exc}") from exc
