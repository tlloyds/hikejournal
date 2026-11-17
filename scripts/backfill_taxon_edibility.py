#!/usr/bin/env python3
"""Audit and backfill shared food-use references for distinct accepted taxa."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hike_journal.config import settings
from hike_journal.services.edibility import taxon_id
from hike_journal.services.edibility_matching import assess_batch
from hike_journal.services.inat import InatClient
from hike_journal.services.taxonomy import normalize_taxon_name
from scripts.import_food_plants import MANIFEST_PATH, read_verified_archive, staging_client


def read_reviewed(path: Path | None) -> dict[int, list[dict]]:
    result = defaultdict(list)
    seen = set()
    for item in json.loads(path.read_text()) if path else []:
        identity_id = taxon_id(item.get("taxon_id"))
        method = item.get("method")
        key = item.get("record_key")
        pair = (identity_id, key)
        if (
            identity_id is None or item["taxon_id"] != identity_id or not isinstance(key, str)
            or not key.isascii() or not key.isdigit() or pair in seen
            or method not in {"manual_review", "verified_identifier", "verified_synonym", "rejected"}
            or (method == "verified_synonym" and taxon_id(item.get("synonym_taxon_id")) is None)
        ):
            raise ValueError("Invalid or duplicate reviewed mapping")
        seen.add(pair)
        result[identity_id].append({
            key: item[key] for key in (
                "record_key", "taxon_id", "method", "accepted_name", "authority",
                "source_taxon_id", "synonym_taxon_id",
            ) if key in item
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supabase-url", help="Explicit development/staging database URL")
    parser.add_argument("--version", default="2")
    parser.add_argument("--archive", type=Path, help="Audit the verified archive without a database")
    parser.add_argument("--taxon-ids", nargs="+", type=int, help="Audit specific iNaturalist IDs instead of journal IDs")
    parser.add_argument("--reviewed-mappings", type=Path)
    parser.add_argument("--after-taxon-id", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--limit", type=int, default=500)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--activate", action="store_true")
    mode.add_argument("--withdraw", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 100 or args.limit < 1 or args.after_taxon_id < 0:
        parser.error("Use batch size 1..100, a positive limit and a nonnegative cursor")
    if args.taxon_ids and any(taxon_id(value) is None for value in args.taxon_ids):
        parser.error("Taxon IDs must be positive integers")
    if args.archive and (args.write or args.activate or args.withdraw or not args.taxon_ids or args.supabase_url):
        parser.error("--archive requires --taxon-ids and supports dry-run only")
    if not args.archive and not args.supabase_url:
        parser.error("Supply an explicit development/staging URL or --archive")
    counts: Counter = Counter()
    if args.archive:
        manifest = json.loads(MANIFEST_PATH.read_text())
        if manifest["version"] != args.version:
            parser.error("The archive must match the selected version")
        rows, _ = read_verified_archive(args.archive, manifest)
        by_key = {row["record_key"]: row for row in rows}
        by_name = defaultdict(list)
        for row in rows:
            by_name[row["normalized_name"]].append(row)

        def evidence_for(name, keys):
            return list({row["record_key"]: row for row in
                         [*by_name[name], *(by_key[key] for key in keys if key in by_key)]}.values())
    else:
        client = staging_client(args.supabase_url)
        release = (
            client.table("edibility_source_releases").select("id")
            .eq("source_key", "wcfp").eq("version", args.version).single().execute().data
        )
        release_id = release["id"]
        if args.activate or args.withdraw:
            client.rpc("set_edibility_release", {
                "p_release_id": release_id, "p_active": args.activate,
            }).execute()
            print(f"Release {release_id} {'activated' if args.activate else 'withdrawn'}")
            return 0

        def evidence_for(name, keys):
            table = client.table("taxon_food_use_evidence")
            rows = table.select("*").eq("release_id", release_id).eq("normalized_name", name).execute().data
            if keys:
                rows.extend(table.select("*").eq("release_id", release_id).in_("record_key", keys).execute().data)
            return list({row["record_key"]: row for row in rows}.values())

    reviewed = read_reviewed(args.reviewed_mappings)
    inat = InatClient(access_token="", base_url=settings.inat_base_url)
    cursor = args.after_taxon_id
    explicit_ids = sorted({value for value in args.taxon_ids or [] if value > cursor})
    try:
        while counts["assessed"] < args.limit:
            size = min(args.batch_size, args.limit - counts["assessed"])
            targets = (
                [{"taxon_id": value} for value in explicit_ids if value > cursor][:size]
                if args.taxon_ids else
                client.rpc("edibility_observed_taxa", {"p_after": cursor, "p_limit": size}).execute().data
            )
            if not targets:
                break
            checked_at = datetime.now(timezone.utc).isoformat()
            batch_counts: Counter = Counter()
            batch_reviews = defaultdict(dict)
            target_ids = [target["taxon_id"] for target in targets]
            if not args.archive:
                prior_reviews = (
                    client.table("taxon_edibility_matches").select("taxon_id,record_key,review_basis")
                    .eq("release_id", release_id).in_("taxon_id", target_ids)
                    .not_.is_("review_basis", "null").execute().data
                )
                for row in prior_reviews:
                    batch_reviews[row["taxon_id"]][row["record_key"]] = row["review_basis"]
            for identity_id in target_ids:
                for item in reviewed.get(identity_id, []):
                    batch_reviews[identity_id][item["record_key"]] = item
            assessments = assess_batch(
                targets, inat, evidence_for,
                {identity_id: list(items.values()) for identity_id, items in batch_reviews.items()},
                batch_counts,
            )
            if args.write:
                client.rpc("save_edibility_assessments", {
                    "p_release_id": release_id, "p_validated_at": checked_at, "p_assessments": assessments,
                }).execute()
            counts.update(batch_counts)
            cursor = targets[-1]["taxon_id"]
    except Exception as error:
        counts["errors"] += 1
        print(f"Batch halted ({type(error).__name__}). Resume after the reported cursor.", file=sys.stderr)
    report_fields = (
        "assessed", "matched", "unsupported_or_inactive", "unresolved_identity",
        "missing_source_evidence", "ambiguous_or_rejected", "conflicting_evidence", "poison_use_reported",
        "toxicity_concerns", "errors",
    )
    report = {key: counts[key] for key in report_fields} | dict(counts)
    report["unmapped"] = counts["assessed"] - counts["matched"]
    print(json.dumps({"after_taxon_id": cursor, "dry_run": not args.write, **report}, sort_keys=True))
    return int(bool(counts["errors"]))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        raise SystemExit(f"Backfill failed ({type(error).__name__})") from None
