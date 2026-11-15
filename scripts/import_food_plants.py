#!/usr/bin/env python3
"""Verify and stage the pinned WCFP archive. The default dry run performs no writes."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from hashlib import file_digest
from io import BytesIO, TextIOWrapper
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hike_journal.services.edibility import PUBLISHABLE_RANKS
from hike_journal.services.taxonomy import normalize_taxon_name

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "data" / "wcfp-source-v2.json"
USE_FIELDS = (
    "animal_food", "environmental_uses", "fuels", "gene_sources", "human_food",
    "invertebrate_food", "materials", "medicines", "poisons", "social_uses",
)
WORKBOOK_FIELDS = set(USE_FIELDS) | {
    "WCFP_ID", "LSID_accepted", "taxon_name_accepted", "taxon_authors_accepted",
    "kingdom", "phylum", "family", "references_food", "references_uses", "Link", "cultivated_GRIN",
}
TAXONOMY_FIELDS = {
    "plant_name_id", "ipni_id", "taxon_status", "taxon_rank", "taxon_name",
    "taxon_authors", "family", "hybrid_formula", "genus_hybrid", "species_hybrid",
}
FILE_METADATA_FIELDS = {"metadata_url", "archive_url", "archive_md5", "workbook", "taxonomy"}


def read_verified_archive(path: Path, manifest: dict) -> tuple[list[dict], Counter]:
    from openpyxl import load_workbook

    for algorithm, key in (("sha256", "archive_sha256"), ("md5", "archive_md5")):
        with path.open("rb") as file:
            if file_digest(file, algorithm).hexdigest() != manifest[key]:
                raise ValueError(f"WCFP archive {algorithm} differs from the pinned release")
    if (manifest["license"], manifest["license_url"]) != (
        "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/",
    ):
        raise ValueError("Unverified WCFP license")
    with ZipFile(path) as archive:
        with BytesIO(archive.read(manifest["workbook"])) as data:
            workbook = load_workbook(data, read_only=True, data_only=True)
            try:
                rows = workbook["WCFP"].values
                headers = next(rows, ())
                if len(headers) != len(set(headers)) or not WORKBOOK_FIELDS <= set(headers):
                    raise ValueError("Unexpected WCFP workbook headers")
                plants = [dict(zip(headers, row)) for row in rows]
            finally:
                workbook.close()
        identifiers = {plant.get("LSID_accepted") for plant in plants} - {None, ""}
        taxonomy = defaultdict(list)
        with TextIOWrapper(archive.open(manifest["taxonomy"]), encoding="utf-8-sig") as data:
            rows = csv.DictReader(data, delimiter="|")
            if not TAXONOMY_FIELDS <= set(rows.fieldnames or []):
                raise ValueError("Unexpected WCVP snapshot headers")
            for row in rows:
                if row["ipni_id"] in identifiers:
                    taxonomy[row["ipni_id"]].append({key: row[key] for key in TAXONOMY_FIELDS})
    return normalize_evidence(plants, taxonomy)


def normalize_evidence(plants: list[dict], taxonomy: dict[str, list[dict]]) -> tuple[list[dict], Counter]:
    seen: set[str] = set()
    evidence: list[dict] = []
    counts: Counter = Counter()
    for plant in plants:
        counts["workbook_rows"] += 1
        number = plant["WCFP_ID"]
        if type(number) is not int or number <= 0 or str(number) in seen:
            raise ValueError("Invalid or duplicate WCFP_ID")
        key = str(number)
        seen.add(key)
        for column in (*USE_FIELDS, "cultivated_GRIN"):
            if type(plant[column]) is not int or plant[column] not in (0, 1):
                raise ValueError(f"Record {key} has an invalid {column} flag")
        for column in ("taxon_name_accepted", "kingdom", "phylum", "family"):
            if not isinstance(plant[column], str) or not plant[column].strip():
                raise ValueError(f"Record {key} is missing {column}")
        for column in ("LSID_accepted", "taxon_authors_accepted", "references_food", "references_uses", "Link"):
            if plant[column] is not None and not isinstance(plant[column], str):
                raise ValueError(f"Record {key} has an invalid {column}")
        if not plant["human_food"]:
            counts["non_human_food"] += 1
            continue
        if plant["kingdom"] != "Plantae" or plant["phylum"] != "Tracheophyta":
            counts["non_vascular"] += 1
            continue
        if not normalize_taxon_name(plant["references_food"]):
            raise ValueError(f"Human food record {key} has no food citation")

        name = normalize_taxon_name(plant["taxon_name_accepted"])
        lsid = plant["LSID_accepted"]
        identities = [
            row for row in taxonomy.get(lsid, [])
            if row["taxon_status"] == "Accepted"
            and normalize_taxon_name(row["taxon_name"]) == name
            and normalize_taxon_name(row["taxon_authors"]) == normalize_taxon_name(plant["taxon_authors_accepted"])
            and normalize_taxon_name(row["family"]) == normalize_taxon_name(plant["family"])
        ]
        identity = identities[0] if len(identities) == 1 else None
        rank = normalize_taxon_name(identity["taxon_rank"]) if identity else "unknown"
        if identity and (
            any(identity[key] for key in ("hybrid_formula", "genus_hybrid", "species_hybrid"))
            or "×" in name or "+" in name
        ):
            rank = "hybrid"
        if rank not in PUBLISHABLE_RANKS:
            counts["unsupported_rank_or_unverified_identity"] += 1
        poison = plant["poisons"] == 1
        counts["poison_use"] += int(poison)
        evidence.append({
            "record_key": key,
            "source_taxon_id": lsid or None,
            "scientific_name": plant["taxon_name_accepted"],
            "normalized_name": name,
            "authority": plant["taxon_authors_accepted"],
            "rank": rank,
            "family": plant["family"],
            "evidence_types": ["food_documented", "poison_use"] if poison else ["food_documented"],
            "food_use_notes": (
                "Also listed as cultivated in GRIN. The checklist gives no cultivar-specific food-use details."
                if plant["cultivated_GRIN"] else None
            ),
            "toxicity_notes": (
                "The checklist also records a poison use. That category does not specify the "
                "hazardous part, exposure, or circumstances."
                if poison else None
            ),
            "source_references": {
                "food": plant["references_food"],
                **({"other_uses": plant["references_uses"]} if poison else {}),
            },
            "provenance": {
                "sheet": "WCFP",
                "fields": {field: plant[field] for field in (*USE_FIELDS, "cultivated_GRIN", "kingdom", "phylum", "Link")},
                "wcvp_plant_name_id": identity["plant_name_id"] if identity else None,
            },
        })
    if not evidence:
        raise ValueError("No vascular human-food records")
    counts["evidence_rows"] = len(evidence)
    counts["matchable_rank"] = len(evidence) - counts["unsupported_rank_or_unverified_identity"]
    return evidence, counts


def staging_client(url: str):
    from supabase import create_client

    key = os.environ.get("EDIBILITY_IMPORT_SERVICE_KEY")
    if not key:
        raise ValueError("Set EDIBILITY_IMPORT_SERVICE_KEY for the explicitly selected development or staging database")
    return create_client(url, key)


def stage_release(client, manifest: dict, evidence: list[dict], batch_size: int) -> str:
    release = {key: value for key, value in manifest.items() if key not in FILE_METADATA_FIELDS}
    release["evidence_count"] = len(evidence)
    releases = client.table("edibility_source_releases")
    releases.upsert(release, on_conflict="source_key,version", ignore_duplicates=True).execute()
    stored = releases.select("*").eq("source_key", release["source_key"]).eq("version", release["version"]).single().execute().data
    if any(stored.get(key) != value for key, value in release.items()):
        raise ValueError("Stored release metadata differs from the verified manifest")
    release_id = stored["id"]
    for offset in range(0, len(evidence), batch_size):
        rows = [{"release_id": release_id, **row} for row in evidence[offset:offset + batch_size]]
        client.table("taxon_food_use_evidence").upsert(
            rows, on_conflict="release_id,record_key", ignore_duplicates=True,
        ).execute()
    count = (
        client.table("taxon_food_use_evidence").select("record_key", count="exact", head=True)
        .eq("release_id", release_id).execute().count
    )
    if count != len(evidence):
        raise ValueError("Staged row count differs from the validated archive")
    return release_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--stage", action="store_true")
    parser.add_argument("--supabase-url", help="Explicit development/staging URL (required to stage)")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 200 or (args.stage and not args.supabase_url):
        parser.error("Use --batch-size 1..200 and supply --supabase-url with --stage")
    manifest = json.loads(MANIFEST_PATH.read_text())
    evidence, counts = read_verified_archive(args.archive, manifest)
    print(json.dumps(counts, sort_keys=True))
    if args.stage:
        release_id = stage_release(staging_client(args.supabase_url), manifest, evidence, args.batch_size)
        print(f"Staged inactive-by-default release {release_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        raise SystemExit(str(error)) from None
    except Exception as error:
        raise SystemExit(f"WCFP import failed ({type(error).__name__})") from None
