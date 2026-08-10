from hike_journal.services.inat import InatRequestError
from hike_journal.services.taxonomy import (
    ensure_observation_taxonomy,
    preferred_current_enrichment,
    resolve_observation_enrichment,
    taxon_enrichment_is_complete,
    taxonomy_resolution_fields,
)


def enrichment(
    taxon_id: int,
    scientific_name: str,
    *,
    rank: str = "species",
    common_name: str = "",
    species_taxon_id: int | None = None,
    is_active: bool = True,
    current_synonymous_taxon_ids: list[int] | None = None,
) -> dict:
    return {
        "taxon_id": taxon_id,
        "scientific_name": scientific_name,
        "preferred_common_name": common_name,
        "english_common_name": None,
        "alias_names": [common_name] if common_name else [],
        "rank": rank,
        "iconic_taxon_name": "Aves",
        "species_taxon_id": taxon_id if rank == "species" else species_taxon_id,
        "is_active": is_active,
        "current_synonymous_taxon_ids": current_synonymous_taxon_ids or [],
    }


def test_mismatched_legacy_taxon_is_resolved_by_exact_observation_name() -> None:
    wrong = enrichment(4765, "Coragyps atratus", common_name="Black Vulture")
    corrected = enrichment(42134, "Sus scrofa", common_name="Wild Boar")
    observation = {
        "taxon_id": 4765,
        "scientific_name": "Wild Boar",
        "common_name": "Wild Boar",
    }

    resolved = resolve_observation_enrichment(
        observation,
        enrichment_for_taxon_id=wrong,
        exact_name_lookup=lambda query: corrected if query == "Wild Boar" else None,
    )

    assert resolved == corrected
    assert taxonomy_resolution_fields(resolved)["taxon_id"] == 42134


def test_inactive_species_uses_single_current_species_synonym() -> None:
    old = enrichment(
        126335,
        "Callisia ornata",
        common_name="Scrub roseling",
        is_active=False,
        current_synonymous_taxon_ids=[1687501],
    )
    current = enrichment(
        1687501,
        "Cuthbertia ornata",
        common_name="Scrub Roseling",
    )

    assert preferred_current_enrichment(old, {1687501: current}) == current


def test_coarser_taxon_never_retains_species_credit() -> None:
    genus = enrichment(
        51575,
        "Laphria",
        rank="genus",
        common_name="Bee-like Robber Flies",
        species_taxon_id=999,
    )

    assert taxonomy_resolution_fields(genus) == {
        "taxon_id": 51575,
        "rank": "genus",
        "iconic_taxon_name": "Aves",
        "species_taxon_id": None,
    }


def test_enrichment_requires_iconic_group_for_badge_progress() -> None:
    incomplete = enrichment(42134, "Sus scrofa", common_name="Wild Boar")
    incomplete["iconic_taxon_name"] = None

    assert not taxon_enrichment_is_complete(incomplete)
    assert taxon_enrichment_is_complete(
        enrichment(42134, "Sus scrofa", common_name="Wild Boar")
    )


def test_ensure_taxonomy_corrects_id_and_persists_enrichment() -> None:
    class Repository:
        resolution = None
        raw_payload = None

        def update_observation_taxon_resolution(self, observation_id, **kwargs):
            self.resolution = (observation_id, kwargs)
            return {"id": observation_id}

        def update_observation_raw_payload(self, observation_id, raw_payload):
            self.raw_payload = (observation_id, raw_payload)
            return {"id": observation_id, "raw_response_json": raw_payload}

    class Client:
        def fetch_taxon_enrichment(self, _taxon_id):
            return enrichment(104251, "Lepisosteus platyrhincus", common_name="Florida Gar")

        def fetch_taxon_enrichments(self, _taxon_ids):
            return {}

        def fetch_exact_taxon_enrichment(self, query):
            if query == "Alligator mississippiensis":
                return enrichment(
                    26159,
                    "Alligator mississippiensis",
                    common_name="American Alligator",
                )
            return None

    repository = Repository()
    observation = {
        "id": "observation-1",
        "taxon_id": 104251,
        "scientific_name": "Alligator mississippiensis",
        "common_name": "American Alligator",
        "raw_response_json": {"manual_override": {"edited_at": "now"}},
    }

    assert ensure_observation_taxonomy(repository, Client(), observation)
    assert repository.resolution == (
        "observation-1",
        {
            "taxon_id": 26159,
            "rank": "species",
            "iconic_taxon_name": "Aves",
            "species_taxon_id": 26159,
        },
    )
    assert repository.raw_payload[1]["manual_override"] == {"edited_at": "now"}
    assert repository.raw_payload[1]["taxon_enrichment"]["taxon_id"] == 26159


def test_ensure_taxonomy_uses_wikipedia_when_inaturalist_has_no_summary(monkeypatch) -> None:
    class Repository:
        def update_observation_taxon_resolution(self, observation_id, **_kwargs):
            return {"id": observation_id}

        def update_observation_raw_payload(self, _observation_id, raw_payload):
            self.raw_payload = raw_payload
            return raw_payload

    class Client:
        def fetch_taxon_enrichment(self, _taxon_id):
            return enrichment(47126, "Sciurus carolinensis", common_name="Eastern gray squirrel")

        def fetch_exact_taxon_enrichment(self, _query):
            return None

    monkeypatch.setattr(
        "hike_journal.services.taxonomy.fill_missing_wikipedia_summary",
        lambda item: ({**item, "wikipedia_summary": "A tree squirrel.", "wikipedia_url": "https://example.test/squirrel"}, True),
    )
    repository = Repository()
    observation = {
        "id": "observation-1",
        "taxon_id": 47126,
        "scientific_name": "Sciurus carolinensis",
        "common_name": "Eastern gray squirrel",
    }

    assert ensure_observation_taxonomy(repository, Client(), observation)
    assert repository.raw_payload["taxon_enrichment"]["wikipedia_summary"] == "A tree squirrel."


def test_ensure_taxonomy_treats_transport_failure_as_optional_enrichment() -> None:
    class Repository:
        def update_observation_taxon_resolution(self, *_args, **_kwargs):
            raise AssertionError("taxonomy should not be updated after a failed lookup")

    class Client:
        def fetch_taxon_enrichment(self, _taxon_id):
            raise InatRequestError("The connection to iNaturalist was interrupted. Please try again.")

    observation = {
        "id": "observation-1",
        "taxon_id": 47126,
        "scientific_name": "Sciurus carolinensis",
        "common_name": "Eastern gray squirrel",
    }

    assert ensure_observation_taxonomy(Repository(), Client(), observation) is False
