"""Read and derive exact-taxon educational reference profiles."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from hike_journal.services.taxonomy import normalize_taxon_name

logger = logging.getLogger(__name__)
PUBLISHABLE_RANKS = frozenset({"species", "subspecies", "variety", "form"})
INAT_VASCULAR_PLANTS = 211194
_PART_REFERENCE_PATH = Path(__file__).with_name("edibility_parts.json")
_PART_REFERENCE_BYTES = _PART_REFERENCE_PATH.read_bytes()
_PART_REFERENCE = json.loads(_PART_REFERENCE_BYTES)
_PART_REFERENCE_REVISION = hashlib.sha256(_PART_REFERENCE_BYTES).hexdigest()[:16]


def taxon_id(value: Any) -> int | None:
    raw = str(value)
    if len(raw) > 19 or not raw.isascii() or not raw.isdigit():
        return None
    result = int(raw)
    return result if 0 < result < 2**63 else None


def eligible_identity(identity: dict[str, Any]) -> bool:
    return (
        taxon_id(identity.get("taxon_id")) is not None
        and identity.get("is_active") is True
        and normalize_taxon_name(identity.get("rank")) in PUBLISHABLE_RANKS
        and normalize_taxon_name(identity.get("iconic_taxon_name")) == "plantae"
        and INAT_VASCULAR_PLANTS in (identity.get("ancestor_ids") or [])
        and bool(identity.get("scientific_name"))
    )


def assess_evidence(
    row: dict[str, Any],
    identity: dict[str, Any],
    exact_ids: set[int] | None,
    *,
    reviewed: dict[str, Any] | None = None,
    synonym: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess one candidate without fuzzy names or rank inheritance."""
    accepted_name = str(identity.get("scientific_name") or "")
    rank = normalize_taxon_name(identity.get("rank"))
    source_name = normalize_taxon_name(row["scientific_name"])
    method = "exact_accepted_name" if reviewed is None else reviewed["method"]
    reason = ""
    if not eligible_identity(identity) or row["rank"] != rank:
        reason = "unsupported_identity_or_rank"
    elif normalize_taxon_name(row["family"]) != normalize_taxon_name(identity.get("family")):
        reason = "family_mismatch"
    elif reviewed is not None and (
        reviewed.get("record_key") != row["record_key"]
        or reviewed.get("authority") != (row.get("authority") or "")
        or normalize_taxon_name(reviewed.get("accepted_name")) != normalize_taxon_name(accepted_name)
        or reviewed.get("taxon_id") != identity["taxon_id"]
    ):
        reason = "reviewed_identity_changed"
    elif identity.get("authority") and method != "verified_synonym" and (
        normalize_taxon_name(row.get("authority")) != normalize_taxon_name(identity["authority"])
    ):
        reason = "authority_mismatch"
    elif method == "verified_synonym":
        if not (
            synonym
            and synonym.get("taxon_id") == reviewed.get("synonym_taxon_id")
            and synonym.get("is_active") is False
            and normalize_taxon_name(synonym.get("scientific_name")) == source_name
            and normalize_taxon_name(synonym.get("rank")) == rank
            and normalize_taxon_name(synonym.get("family")) == normalize_taxon_name(row["family"])
            and set(synonym.get("current_synonymous_taxon_ids") or []) == {identity["taxon_id"]}
        ):
            reason = "unverified_synonym"
    elif method == "verified_identifier":
        if not row.get("source_taxon_id") or reviewed.get("source_taxon_id") != row["source_taxon_id"]:
            reason = "crosswalk_mismatch"
    elif method == "exact_accepted_name":
        if source_name != normalize_taxon_name(accepted_name) or exact_ids != {identity["taxon_id"]}:
            reason = "ambiguous_or_unverified_name"
    elif method != "manual_review":
        raise ValueError("Unknown match method")

    return {
        "record_key": row["record_key"],
        "accepted_name": accepted_name,
        "rank": rank,
        "match_method": method if not reason else None,
        "review_status": (
            "needs_review" if reason else "reviewed" if reviewed is not None else "source_matched"
        ),
        "reason": reason or "validated",
        "review_basis": reviewed,
    }


def derive_profile(
    identity: dict[str, Any], rows: list[dict[str, Any]], matches: list[dict[str, Any]]
) -> dict[str, Any] | None:
    accepted = {
        item["record_key"]: item["review_status"]
        for item in matches
        if item["review_status"] in {"source_matched", "reviewed"}
    }
    evidence = [row for row in rows if row["record_key"] in accepted]
    if not evidence or any(match["review_status"] == "needs_review" for match in matches):
        # A pending identity conflict can include evidence that would change the warning.
        return None
    types = {kind for row in evidence for kind in row["evidence_types"]}
    documented = bool(types & {"food_documented", "food_conditional"})
    disputed = "food_disputed" in types
    food = "disputed" if disputed else (
        "conditional" if "food_conditional" in types else "documented" if documented else "unknown"
    )
    return {
        "scientific_name": identity["scientific_name"],
        "rank": identity["rank"],
        "food_use_status": food,
        "has_documented_food_use": documented,
        "toxicity_status": (
            "documented_concern" if "toxicity_concern" in types else "unknown"
        ),
        "checklist_poison_use": "poison_use" in types,
        "evidence_conflict": documented and disputed,
        "documented_parts": sorted({part for row in evidence for part in row.get("parts") or []}),
        "food_use_notes": _combine_notes(evidence, "food_use_notes"),
        "toxicity_notes": _combine_notes(evidence, "toxicity_notes"),
        "record_keys": sorted(accepted),
        "review_status": "reviewed" if set(accepted.values()) == {"reviewed"} else "source_matched",
    }


def _combine_notes(evidence: list[dict[str, Any]], key: str) -> str | None:
    return "\n\n".join(sorted({row[key] for row in evidence if row.get(key)})) or None


@dataclass(frozen=True)
class EdibilityReference:
    release_id: str | None = None
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)

    def for_observation(self, observation: dict[str, Any]) -> dict[str, Any] | None:
        if observation.get("status") != "confirmed":
            return None
        identity_id = taxon_id(observation.get("taxon_id"))
        profile = self.profiles.get(str(identity_id))
        if not profile or not observation.get("scientific_name"):
            return None
        rank = normalize_taxon_name(observation.get("rank"))
        if rank and rank != profile["rank"]:
            return None
        iconic = normalize_taxon_name(observation.get("iconic_taxon_name"))
        if iconic and iconic not in {"plantae", "other"}:
            return None
        if normalize_taxon_name(observation["scientific_name"]) != normalize_taxon_name(profile["scientific_name"]):
            return None
        return profile


def load_edibility_reference(
    repository: Any, observations: Iterable[dict[str, Any]], *, enabled: bool
) -> EdibilityReference:
    if not enabled:
        return EdibilityReference()
    ids = sorted({
        identity_id for row in observations if row.get("status") == "confirmed"
        and (identity_id := taxon_id(row.get("taxon_id"))) is not None
    })
    try:
        release_id, stored_profiles = repository.read_edibility_profiles(ids)
    except Exception as error:
        # A missing migration or reference outage must not break journal reads.
        logger.warning("Food-use reference unavailable (%s)", type(error).__name__)
        return EdibilityReference()
    revision = f"{release_id or 'independent'}+parts-{_PART_REFERENCE_REVISION}"
    profiles = {}
    for key, profile in stored_profiles.items():
        # Older WCFP assessments encoded its broad poison-use category as a
        # toxicity concern. Preserve the historical flag on those stored rows.
        old_checklist_flag = (
            "checklist_poison_use" not in profile and profile.get("toxicity_status") == "documented_concern"
        )
        current_profile = {**profile, "dataset_version": revision}
        current_profile["checklist_poison_use"] = profile.get("checklist_poison_use", old_checklist_flag)
        if old_checklist_flag:
            current_profile["toxicity_status"] = "unknown"
        profiles[key] = current_profile
    now = datetime.now(UTC)
    for identity_id in ids:
        key = str(identity_id)
        entry = _PART_REFERENCE["taxa"].get(key)
        if not entry:
            continue
        baseline = profiles.get(key)
        if baseline and (
            normalize_taxon_name(baseline["scientific_name"]) != normalize_taxon_name(entry["scientific_name"])
            or baseline["rank"] != entry["rank"]
        ):
            profiles.pop(key)
            continue
        profiles[key] = _with_reviewed_evidence(identity_id, entry, baseline, revision, now)
    return EdibilityReference(revision, profiles)


def _with_reviewed_evidence(
    identity_id: int, entry: dict[str, Any], baseline: dict[str, Any] | None, revision: str, now: datetime
) -> dict[str, Any]:
    profile = baseline or {}
    part_claims = entry.get("claims", [])
    traditional_uses = entry.get("traditional_uses", [])
    source_keys = dict.fromkeys(claim["source"] for claim in (*part_claims, *traditional_uses))
    sources = {key: _PART_REFERENCE["sources"][key] for key in source_keys}
    claims = [
        {**claim, "source_url": sources[claim["source"]]["url"]}
        for claim in part_claims
    ]
    kinds = {claim["kind"] for claim in claims}
    food_status = profile.get("food_use_status", "unknown")
    if food_status != "disputed":
        if "edible" in kinds:
            food_status = "documented"
        elif "conditional" in kinds:
            food_status = "conditional"
    has_part_hazard = bool(kinds & {"toxic", "caution"})
    parts = {
        claim["part"] for claim in claims if claim["kind"] in {"edible", "conditional"}
    }
    return {
        **profile,
        "taxon_id": identity_id,
        "scientific_name": entry["scientific_name"],
        "rank": entry["rank"],
        "dataset_version": revision,
        "food_use_status": food_status,
        "has_documented_food_use": bool(parts) or profile.get("has_documented_food_use", False),
        "toxicity_status": "documented_concern" if has_part_hazard else profile.get("toxicity_status", "unknown"),
        "evidence_conflict": profile.get("evidence_conflict", False),
        "documented_parts": sorted(parts | set(profile.get("documented_parts") or [])),
        "part_evidence": claims,
        "traditional_uses": [
            {**use, "source_url": sources[use["source"]]["url"]}
            for use in traditional_uses
        ],
        "sources": [*sources.values(), *profile.get("sources", [])],
        "review_status": profile.get("review_status", "reviewed"),
        "expires_at": profile.get("expires_at") or (now + timedelta(hours=24)).isoformat(),
    }
