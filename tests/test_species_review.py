import app


class RecordingRepository:
    def __init__(self) -> None:
        self.deleted_observation_ids: list[str] = []
        self.status_updates: list[tuple[list[str], str]] = []
        self.created_observations: list[dict] = []
        self.source_observations: list[dict] = []

    def delete_observations(self, observation_ids: list[str]) -> None:
        self.deleted_observation_ids = observation_ids

    def update_photo_processing_statuses(self, photo_ids: list[str], status: str) -> None:
        self.status_updates.append((photo_ids, status))

    def create_manual_observation(self, **payload):
        self.created_observations.append(payload)
        return {"id": f"observation-{len(self.created_observations)}", **payload}

    def list_observations_by_ids(self, observation_ids: list[str]) -> list[dict]:
        return [observation for observation in self.source_observations if observation["id"] in observation_ids]


class RecordingInatClient:
    def __init__(self) -> None:
        self.enrichment_calls: list[int] = []

    def fetch_taxon_enrichment(self, taxon_id: int) -> dict:
        self.enrichment_calls.append(taxon_id)
        return {"rank": "species", "wikipedia_summary": "Copied taxon details"}


def test_reject_removes_suggestion_and_keeps_photo_in_review(monkeypatch) -> None:
    repository = RecordingRepository()
    monkeypatch.setattr(app, "invalidate_data_cache", lambda: None)

    app.reject_observations(
        repository,
        [{"id": "observation-1", "photo_id": "photo-1"}],
        [{"id": "photo-1"}],
    )

    assert repository.deleted_observation_ids == ["observation-1"]
    assert repository.status_updates == [(["photo-1"], app.REVIEW_QUEUE_STATUS)]


def test_assign_known_species_confirms_photos_without_cv_calls() -> None:
    repository = RecordingRepository()
    repository.source_observations = [
        {
            "id": "observation-source",
            "raw_response_json": {
                "taxon_enrichment": {"rank": "species", "wikipedia_summary": "Southern dewberry details"}
            },
        }
    ]
    inat_client = RecordingInatClient()
    photos = [
        {"id": "photo-1", "hike_id": "hike-1", "owner_subject": "owner", "owner_email": "owner@example.com"},
        {"id": "photo-2", "hike_id": "hike-1", "owner_subject": "owner", "owner_email": "owner@example.com"},
    ]
    species = {
        "taxon_id": 101,
        "common_name": "Southern dewberry",
        "scientific_name": "Rubus trivialis",
        "source_observation_id": "observation-source",
        "seen_count": 7,
    }

    assigned_count = app.assign_known_species_to_photos(repository, inat_client, photos, species)

    assert assigned_count == 2
    assert repository.status_updates == [(["photo-1", "photo-2"], "ready")]
    assert [record["status"] for record in repository.created_observations] == ["confirmed", "confirmed"]
    assert [record["source"] for record in repository.created_observations] == ["known_species", "known_species"]
    assert all(record["taxon_id"] == 101 for record in repository.created_observations)
    assert all(record["raw_payload"]["known_species_assignment"]["source_observation_id"] == "observation-source" for record in repository.created_observations)
    assert all(record["raw_payload"]["taxon_enrichment"]["wikipedia_summary"] == "Southern dewberry details" for record in repository.created_observations)
    assert inat_client.enrichment_calls == []


def test_known_species_assignment_fetches_missing_enrichment_once_per_batch() -> None:
    repository = RecordingRepository()
    repository.source_observations = [{"id": "observation-source", "raw_response_json": {}}]
    inat_client = RecordingInatClient()
    photos = [{"id": "photo-1"}, {"id": "photo-2"}]
    species = {
        "taxon_id": 101,
        "common_name": "Southern dewberry",
        "scientific_name": "Rubus trivialis",
        "source_observation_id": "observation-source",
        "seen_count": 7,
    }

    app.assign_known_species_to_photos(repository, inat_client, photos, species)

    assert inat_client.enrichment_calls == [101]
    assert all(record["raw_payload"]["taxon_enrichment"]["wikipedia_summary"] == "Copied taxon details" for record in repository.created_observations)
