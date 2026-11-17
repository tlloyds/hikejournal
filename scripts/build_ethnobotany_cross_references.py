#!/usr/bin/env python3
"""Build a versioned, exact-taxon index of cited ethnobotany discovery records."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import gzip
from hashlib import file_digest
from io import TextIOWrapper
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hike_journal.services.edibility import eligible_identity, taxon_id
from hike_journal.services.ethnobotany import DUKE_SOURCE_KEY, KEW_CATEGORIES, KEW_SOURCE_KEY, match_cross_references
from hike_journal.services.inat import InatClient
from hike_journal.services.taxonomy import normalize_taxon_name


KEW_SHA256 = "626027154ce7d2a4a45bc6130f94becd6123f443aa2afa6d691f33c3ce239ecb"
DUKE_SHA256 = "ff325bc477c355799d12194e2d172c9e181ba44e59056c5ca97f41db595b7d19"
KEW_SOURCE = {
    "title": "World Checklist of Useful Plant Species",
    "url": "https://doi.org/10.5063/F1CV4G34",
    "publisher": "Royal Botanic Gardens, Kew",
    "attribution": "Mauricio Diazgranados, Bob Allkin, Nicholas Black, Rodrigo Cámara-Leret, Cátia Canteiro, "
    "Julia Carretero, Ruth Eastwood, Samantha Hargreaves, Alex Hudson, William Milliken, Mark Nesbitt, "
    "Ian Ondo, Kristina Patmore, Samuel Pironon, Robert Turner and Tiziana Ulian",
    "version": "2020 checklist",
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "modifications": "HikeJournal indexed selected checklist records and matched exact species.",
}

_FAMILY = re.compile(r"[A-Z][a-z]+aceae")
_SPECIES = re.compile(r"([A-Z][a-z-]+ [a-z][a-z-]+) (.+)")
_KEW_USE = re.compile(r"(\d+-\d+)\s*\|\s*([A-Z ]+)\s*(?:\|\s*\[([\d, ]+)\])?")
_INFRASPECIFIC = re.compile(r"(?:subsp|ssp|var|subvar|f|forma)\.|[×+]")


def _verify(path: Path, expected: str) -> None:
    with path.open("rb") as source:
        if file_digest(source, "sha256").hexdigest() != expected:
            raise ValueError(f"Source digest changed: {path.name}")


def _kew_records(pages, names: set[str] | None):
    family = None
    for number, page in enumerate(pages, 1):
        if number < 12:
            continue
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        for line, metadata in zip(lines, lines[1:]):
            if _FAMILY.fullmatch(line):
                family = line
            name_match = _SPECIES.fullmatch(line)
            use_match = _KEW_USE.fullmatch(metadata)
            if not family or not name_match or not use_match:
                continue
            name, authority = name_match.groups()
            key, codes, references = use_match.groups()
            if (names is not None and normalize_taxon_name(name) not in names) or _INFRASPECIFIC.match(authority):
                continue
            codes = codes.split()
            if set(codes) - KEW_CATEGORIES.keys():
                continue
            yield dict(
                scientific_name=name, authority=authority, rank="species", family=family,
                record_key=key, source=KEW_SOURCE_KEY, page=number, categories=codes,
                reference_ids=[int(value.strip()) for value in references.split(",")] if references else [],
            )


def _duke_records(rows, names: set[str] | None):
    for row in rows:
        name = row["TAXON"]
        if (
            (names is not None and normalize_taxon_name(name) not in names) or len(name.split()) != 2
            or any(row[key] for key in ("SPRANK", "SPXNAM"))
            or not row["FAMILY"] or not row["REFERENCE"] or not row["ETHNO"].isdigit()
        ):
            continue
        yield dict(
            scientific_name=name, authority=row["TAXAUTHOR"], rank="species", family=row["FAMILY"],
            record_key=row["ETHNO"], source=DUKE_SOURCE_KEY, reference_key=row["REFERENCE"],
        )




def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kew-pdf", type=Path, required=True)
    parser.add_argument("--duke-zip", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--taxa", type=Path, help="JSON array of taxon_id and scientific_name objects")
    mode.add_argument("--candidate-index", action="store_true", help="Write all sourced candidates as a gzip catalog")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _verify(args.kew_pdf, KEW_SHA256)
    _verify(args.duke_zip, DUKE_SHA256)
    targets = {}
    for row in json.loads(args.taxa.read_text()) if args.taxa else []:
        identity_id = taxon_id(row["taxon_id"])
        name = normalize_taxon_name(row["scientific_name"])
        if identity_id is None or not name or identity_id in targets:
            raise ValueError("Invalid or duplicate iNaturalist target")
        targets[identity_id] = name
    names = set(targets.values()) if args.taxa else None
    candidates = defaultdict(list)
    import pymupdf

    with pymupdf.open(args.kew_pdf) as pdf:
        for row in _kew_records((page.get_text() for page in pdf), names):
            candidates[normalize_taxon_name(row["scientific_name"])].append(row)
    with ZipFile(args.duke_zip) as archive, TextIOWrapper(archive.open("ETHNOBOT.csv"), encoding="latin1") as file:
        for row in _duke_records(csv.DictReader(file), names):
            candidates[normalize_taxon_name(row["scientific_name"])].append(row)
    if args.candidate_index:
        catalog = json.dumps(candidates, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        args.output.write_bytes(gzip.compress(catalog, mtime=0))
        print(f"Indexed cited source candidates for {len(candidates)} names")
        return
    inat = InatClient(access_token="")
    inat.request_interval_seconds = 1.0
    taxa = {}
    ids = sorted(key for key, name in targets.items() if name in candidates)
    print(f"Checking exact identities for {len(ids)} species-name candidates", flush=True)
    for offset in range(0, len(ids), 30):
        for identity_id, identity in inat.fetch_taxon_reference_identities(ids[offset:offset + 30]).items():
            name = targets[identity_id]
            if not eligible_identity(identity) or normalize_taxon_name(identity["scientific_name"]) != name:
                continue
            exact_ids = inat.find_active_scientific_taxon_ids(identity["scientific_name"])
            records = match_cross_references(candidates[name], identity, exact_ids)
            if records:
                taxa[str(identity_id)] = {
                    "scientific_name": identity["scientific_name"], "rank": identity["rank"],
                    "cross_references": records,
                }
        print(f"Validated {len(taxa)} species", flush=True)
    output = {"sources": {KEW_SOURCE_KEY: KEW_SOURCE}, "taxa": dict(sorted(taxa.items(), key=lambda item: int(item[0])))}
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(f"Indexed {sum(len(row['cross_references']) for row in taxa.values())} references across {len(taxa)} species")


if __name__ == "__main__":
    main()
