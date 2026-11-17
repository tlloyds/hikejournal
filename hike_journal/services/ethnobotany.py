"""Exact matching for cited Kew and Duke ethnobotany records."""

from hike_journal.services.edibility import assess_evidence

DUKE_SOURCE_KEY = "duke"
KEW_SOURCE_KEY = "kew_useful_plants"
KEW_CATEGORIES = {
    "HF": "food",
    "ME": "medicine",
    "MA": "materials",
    "PO": "use as a poison",
    "SU": "social uses",
    "FU": "fuel",
    "EU": "environmental uses",
    "GS": "gene sources",
    "AF": "animal food",
    "IF": "invertebrate food",
}


def match_cross_references(candidates: list[dict], identity: dict, exact_ids: set[int] | None) -> list[dict]:
    accepted = [
        row for row in candidates if
        assess_evidence(row, identity, exact_ids)["review_status"] == "source_matched"
    ]
    output = []
    kew = [row for row in accepted if row["source"] == KEW_SOURCE_KEY]
    if len(kew) == 1:
        row = kew[0]
        fields = ", ".join(KEW_CATEGORIES[code] for code in row["categories"])
        output.append({
            "source": KEW_SOURCE_KEY, "summary": f"Checklist categories include {fields}.",
            "locator": f"Page {row['page']} · IPNI {row['record_key']}",
            "record_key": row["record_key"], "categories": row["categories"],
            "reference_ids": row["reference_ids"],
        })
    duke = [row for row in accepted if row["source"] == DUKE_SOURCE_KEY]
    if duke:
        record_keys = sorted({int(row["record_key"]) for row in duke})
        references = sorted({row["reference_key"] for row in duke})
        records = "1 cited use record" if len(record_keys) == 1 else f"{len(record_keys)} cited use records"
        bibliography = "1 reference" if len(references) == 1 else f"{len(references)} references"
        output.append({
            "source": DUKE_SOURCE_KEY,
            "summary": f"{records} from {bibliography}.",
            "locator": "ETHNOBOT.csv · " + (
                f"Record {record_keys[0]}" if len(record_keys) == 1 else f"First record {record_keys[0]}"
            ),
            "record_keys": record_keys,
            "reference_keys": references,
        })
    return output
