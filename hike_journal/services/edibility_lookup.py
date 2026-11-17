"""Find references for plant IDs the Field Guide has not checked recently."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from functools import cached_property, lru_cache
import gzip
from hashlib import sha256
import json
import logging
from pathlib import Path
from threading import BoundedSemaphore

from hike_journal.services.edibility import PUBLISHABLE_RANKS, eligible_identity, taxon_id
from hike_journal.services.edibility_matching import assess_identity
from hike_journal.services.ethnobotany import match_cross_references
from hike_journal.services.inat import InatClient, InatRequestError
from hike_journal.services.taxonomy import normalize_taxon_name

logger = logging.getLogger(__name__)
CATALOG = Path(__file__).with_name("ethnobotany_candidates.json.gz")
CATALOG_VERSION = sha256(CATALOG.read_bytes()).hexdigest()[:16]


def confirmed_plant_ids(observations: list[dict]) -> list[int]:
    # The next app refresh should prioritize the plants just identified on a hike.
    recent_first = sorted(observations, key=lambda row: str(row.get("identified_at") or ""), reverse=True)
    return list(dict.fromkeys(
        ident for row in recent_first
        if row.get("status") == "confirmed"
        and (ident := taxon_id(row.get("taxon_id"))) is not None
        and normalize_taxon_name(row.get("iconic_taxon_name")) in {"plantae", "other", ""}
        and normalize_taxon_name(row.get("rank")) in PUBLISHABLE_RANKS | {""}
    ))


class EdibilityLookup:
    def __init__(self, repository):
        self.repository = repository
        self.workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="edibility")
        self.slots = BoundedSemaphore(2)

    @cached_property
    def candidates(self) -> dict[str, list[dict]]:
        with gzip.open(CATALOG, "rt", encoding="utf-8") as catalog:
            return json.load(catalog)

    def close(self) -> None:
        self.workers.shutdown(wait=False, cancel_futures=True)

    def refresh(self, observations: list[dict], *, limit: int, wait: float) -> None:
        ids = confirmed_plant_ids(observations)
        if not ids or not self.slots.acquire(blocking=False):
            return
        try:
            future = self.workers.submit(self._refresh, ids, limit)
        except RuntimeError:
            self.slots.release()
            return
        future.add_done_callback(lambda _: self.slots.release())
        try:
            # Keep control of the request only briefly. Database claims make it
            # safe to retry on a later refresh if Cloud Run stops the worker.
            future.result(timeout=wait)
        except TimeoutError:
            pass

    def _refresh(self, ids: list[int], limit: int) -> None:
        try:
            claims = self.repository.claim_edibility_lookups(ids, CATALOG_VERSION, limit)
            if not claims:
                return
            inat = InatClient(access_token="", reference_timeout=3, reference_retry=False)
            identities = inat.fetch_taxon_reference_identities([claim["taxon_id"] for claim in claims])
            # A WCFP and supplemental candidate for the same species share
            # one current exact-name query. An incomplete search is retryable.
            @lru_cache(maxsize=16)
            def exact_ids(scientific_name: str) -> set[int]:
                ids_found = inat.find_active_scientific_taxon_ids(scientific_name)
                if ids_found is None:
                    raise InatRequestError("iNaturalist exact-name search was incomplete")
                return ids_found

            for claim in claims:
                identity = identities.get(claim["taxon_id"])
                self._finish_claim(claim, identity, inat, exact_ids)
        except Exception as error:
            # Leave unprocessed claims due after their cooldown. A provider or
            # migration failure must not interrupt reading the journal.
            logger.warning("Automatic edibility lookup unavailable (%s)", type(error).__name__)

    def _finish_claim(self, claim: dict, identity: dict | None, inat: InatClient, exact_ids) -> None:
        identity_id = claim["taxon_id"]
        release = claim["release_id"]
        assessment = None
        if release:
            assessment = assess_identity(
                identity_id, identity, inat,
                lambda name, keys: self.repository.edibility_evidence(release, name, keys),
                self.repository.edibility_reviews(release, identity_id), Counter(), exact_ids,
            )

        reference = None
        if identity and eligible_identity(identity):
            name = identity["scientific_name"]
            candidates = self.candidates.get(normalize_taxon_name(name), [])
            if candidates and identity["rank"] == "species":
                records = match_cross_references(candidates, identity, exact_ids(name))
                if records:
                    reference = {"scientific_name": name, "rank": identity["rank"], "cross_references": records}
        self.repository.finish_edibility_lookup(claim, CATALOG_VERSION, reference, assessment)
