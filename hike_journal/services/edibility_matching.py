"""Assess verified taxon identities against the published food evidence."""

from collections import Counter

from hike_journal.services.edibility import (
    PUBLISHABLE_RANKS, assess_evidence, derive_profile, eligible_identity,
)
from hike_journal.services.inat import InatClient
from hike_journal.services.taxonomy import normalize_taxon_name


def assess_identity(identity_id, identity, inat, evidence_for, crosswalk, counts, exact_ids=None):
    if identity is None:
        counts["unresolved_identity"] += 1
        return {
            "taxon_id": identity_id,
            "profile": None,
            "matches": [{
                "record_key": item["record_key"], "accepted_name": item.get("accepted_name") or "",
                "rank": "", "match_method": None, "review_status": "needs_review",
                "reason": "unresolved_identity", "review_basis": item,
            } for item in crosswalk.values()],
        }
    name = normalize_taxon_name(identity.get("scientific_name"))
    rows = evidence_for(name, list(crosswalk))
    if crosswalk.keys() - {row["record_key"] for row in rows}:
        raise ValueError("A reviewed record is absent from this source release")

    same_name = [row for row in rows if row["normalized_name"] == name]
    exact = (
        (exact_ids or inat.find_active_scientific_taxon_ids)(identity["scientific_name"])
        if eligible_identity(identity) and len(same_name) == 1 and same_name[0]["rank"] in PUBLISHABLE_RANKS
        and same_name[0]["record_key"] not in crosswalk else None
    )
    matches = []
    for row in rows:
        review = crosswalk.get(row["record_key"])
        synonym = (
            inat.fetch_taxon_reference_identity(review["synonym_taxon_id"])
            if review and review["method"] == "verified_synonym" else None
        )
        if review and review["method"] == "rejected":
            match = {
                "record_key": row["record_key"], "accepted_name": identity["scientific_name"],
                "rank": identity["rank"], "match_method": None, "review_status": "rejected",
                "reason": "reviewed_rejection", "review_basis": review,
            }
        else:
            match = assess_evidence(row, identity, exact, reviewed=review, synonym=synonym)
        matches.append(match)
        counts["match_" + (match["reason"] or "validated")] += 1

    profile = derive_profile(identity, rows, matches)
    if profile:
        counts["matched"] += 1
        counts["conflicting_evidence"] += int(profile["evidence_conflict"])
        counts["toxicity_concerns"] += int(profile["toxicity_status"] == "documented_concern")
        counts["poison_use_reported"] += int(profile["checklist_poison_use"])
    elif not eligible_identity(identity) or (rows and all(row["rank"] not in PUBLISHABLE_RANKS for row in rows)):
        counts["unsupported_or_inactive"] += 1
    elif not rows:
        counts["missing_source_evidence"] += 1
    else:
        counts["ambiguous_or_rejected"] += 1
    return {"taxon_id": identity_id, "profile": profile, "matches": matches}


def assess_batch(
    targets: list[dict], inat: InatClient, evidence_for, reviewed: dict[int, list[dict]], counts: Counter,
) -> list[dict]:
    # Use cached identity only as a negative prefilter. Every positive decision
    # checks current iNaturalist identity, family, and accepted-name uniqueness.
    assessments = []
    for target in targets:
        identity_id = int(target["taxon_id"])
        crosswalk = {item["record_key"]: item for item in reviewed.get(identity_id, [])}
        cached = target.get("enrichment") or {}
        if cached.get("taxon_id") == identity_id and cached.get("scientific_name") and not crosswalk:
            cached_rows = evidence_for(normalize_taxon_name(cached["scientific_name"]), [])
            if not cached_rows:
                counts["missing_source_evidence"] += 1
                assessments.append({"taxon_id": identity_id, "profile": None, "matches": []})
                continue

        identity = inat.fetch_taxon_reference_identity(identity_id)
        assessments.append(assess_identity(
            identity_id, identity, inat, evidence_for, crosswalk, counts,
        ))
    counts["assessed"] += len(assessments)
    return assessments
