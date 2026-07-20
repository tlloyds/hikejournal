from __future__ import annotations

from mobile_api import (
    ReviewCandidateInput,
    ReviewDecisionInput,
    _build_species_payloads,
    _photo_payload,
    _review_candidates,
    _species_key,
    decide_species_review,
    derive_mobile_api_token,
    queue_photo_for_species_review,
)


def test_mobile_token_is_deterministic_without_exposing_source(monkeypatch):
    monkeypatch.delenv("MOBILE_API_TOKEN", raising=False)
    source = "server-secret-value"
    token = derive_mobile_api_token(source)

    assert token == derive_mobile_api_token(source)
    assert source not in token
    assert len(token) == 64


def test_explicit_mobile_token_wins(monkeypatch):
    monkeypatch.setenv("MOBILE_API_TOKEN", "paired-device-token")

    assert derive_mobile_api_token("ignored") == "paired-device-token"


def test_hosted_mobile_api_requires_an_explicit_pairing_token(monkeypatch):
    monkeypatch.delenv("MOBILE_API_TOKEN", raising=False)
    monkeypatch.setenv("MOBILE_REQUIRE_EXPLICIT_TOKEN", "true")

    assert derive_mobile_api_token("must-not-be-derived-in-production") == ""


def test_photo_payload_uses_mobile_contract_names():
    payload = _photo_payload(
        {
            "id": "photo-1",
            "hike_id": "hike-1",
            "public_url": "https://images.example/photo.jpg",
            "caption": "Boardwalk at dusk",
            "processing_status": "ready",
        }
    )

    assert payload["url"] == "https://images.example/photo.jpg"
    assert payload["caption"] == "Boardwalk at dusk"
    assert payload["species"] == []


def test_species_key_prefers_stable_taxon_id():
    assert _species_key(
        {"taxon_id": 1234, "scientific_name": "Liatris gracilis", "common_name": "Blazing star"}
    ) == "taxon:1234"


def test_species_key_falls_back_to_normalized_scientific_name():
    assert _species_key(
        {"taxon_id": None, "scientific_name": "  Liatris Gracilis ", "common_name": "Blazing star"}
    ) == "scientific:liatris gracilis"


def test_species_payload_counts_unique_photo_encounters_and_hikes():
    observations = [
        {
            "taxon_id": 42,
            "photo_id": "photo-a",
            "hike_id": "hike-a",
            "common_name": "Pinewoods milkweed",
            "scientific_name": "Asclepias humistrata",
        },
        {
            "taxon_id": 42,
            "photo_id": "photo-a",
            "hike_id": "hike-a",
            "common_name": "Pinewoods milkweed",
            "scientific_name": "Asclepias humistrata",
        },
        {
            "taxon_id": 42,
            "photo_id": "photo-b",
            "hike_id": "hike-b",
            "common_name": "Pinewoods milkweed",
            "scientific_name": "Asclepias humistrata",
        },
    ]
    photos = {
        "photo-a": {"id": "photo-a", "hike_id": "hike-a", "public_url": "https://img/a.jpg", "taken_at": "2026-01-01"},
        "photo-b": {"id": "photo-b", "hike_id": "hike-b", "public_url": "https://img/b.jpg", "taken_at": "2026-02-01"},
    }
    hikes = {
        "hike-a": {"id": "hike-a", "hike_date": "2026-01-01"},
        "hike-b": {"id": "hike-b", "hike_date": "2026-02-01"},
    }

    payload = _build_species_payloads(observations, photos, hikes)[0]

    assert payload["encounter_count"] == 2
    assert payload["hike_count"] == 2
    assert payload["hike_ids"] == ["hike-a", "hike-b"]
    assert payload["hike_encounter_counts"] == {"hike-a": 1, "hike-b": 1}
    assert payload["hike_cover_urls"] == {
        "hike-a": "https://img/a.jpg",
        "hike-b": "https://img/b.jpg",
    }
    assert payload["cover_url"] == "https://img/b.jpg"


def test_review_candidates_put_current_suggestion_first_and_deduplicate():
    candidates = _review_candidates(
        {
            "taxon_id": 42,
            "common_name": "Pinewoods milkweed",
            "scientific_name": "Asclepias humistrata",
            "confidence": 0.87,
            "raw_response_json": {
                "grouped_cv": True,
                "aggregate_candidates": [
                    {
                        "taxon_id": 42,
                        "common_name": "Pinewoods milkweed",
                        "scientific_name": "Asclepias humistrata",
                        "average_confidence": 0.87,
                    },
                    {
                        "taxon_id": 43,
                        "common_name": "Curtiss' milkweed",
                        "scientific_name": "Asclepias curtissii",
                        "average_confidence": 0.22,
                    },
                ],
            },
        }
    )

    assert [candidate["taxon_id"] for candidate in candidates] == [42, 43]
    assert candidates[0]["confidence"] == 0.87


def test_review_candidates_keep_manual_suggestion_without_alternates():
    candidates = _review_candidates(
        {
            "taxon_id": None,
            "common_name": "Local morph",
            "scientific_name": "Species example",
            "confidence": None,
            "raw_response_json": {"manual_override": True},
        }
    )

    assert candidates == [
        {
            "taxon_id": None,
            "common_name": "Local morph",
            "scientific_name": "Species example",
            "confidence": None,
        }
    ]


def test_mobile_review_can_confirm_an_alternate_candidate(monkeypatch):
    class Repository:
        applied = None
        photo_status = None

        def list_observations_by_ids(self, _ids):
            return [{"id": "obs-1", "photo_id": "photo-1", "raw_response_json": {"source": "cv"}}]

        def apply_candidate_to_observation(self, observation_id, **kwargs):
            self.applied = (observation_id, kwargs)

        def update_photo_processing_status(self, photo_id, status):
            self.photo_status = (photo_id, status)

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr(
        "mobile_api._review_queue_payload",
        lambda _service: [{"id": "photo-1", "observation_id": "obs-1"}],
    )

    result = decide_species_review(
        "photo-1",
        ReviewDecisionInput(
            action="confirm",
            observation_id="obs-1",
            candidate=ReviewCandidateInput(
                taxon_id=43,
                common_name="Curtiss' milkweed",
                scientific_name="Asclepias curtissii",
                confidence=0.22,
            ),
        ),
    )

    assert result["ok"] is True
    assert repository.applied[0] == "obs-1"
    assert repository.applied[1]["candidate"].taxon_id == 43
    assert repository.applied[1]["status"] == "confirmed"
    assert repository.photo_status == ("photo-1", "ready")


def test_mobile_review_reject_keeps_photo_in_review(monkeypatch):
    class Repository:
        deleted = None
        photo_status = None

        def list_observations_by_ids(self, _ids):
            return [{"id": "obs-1", "photo_id": "photo-1"}]

        def delete_observations(self, ids):
            self.deleted = ids

        def update_photo_processing_status(self, photo_id, status):
            self.photo_status = (photo_id, status)

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr(
        "mobile_api._review_queue_payload",
        lambda _service: [{"id": "photo-1", "observation_id": "obs-1"}],
    )

    decide_species_review(
        "photo-1",
        ReviewDecisionInput(action="reject", observation_id="obs-1"),
    )

    assert repository.deleted == ["obs-1"]
    assert repository.photo_status == ("photo-1", "in_review")


def test_existing_photo_can_be_queued_for_species_review(monkeypatch):
    class Repository:
        photo_status = None

        def update_photo_processing_status(self, photo_id, status):
            self.photo_status = (photo_id, status)

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr(
        "mobile_api._get_visible_photo",
        lambda photo_id: (service, {"id": photo_id}),
    )

    result = queue_photo_for_species_review("photo-1")

    assert result == {"queued": True}
    assert repository.photo_status == ("photo-1", "in_review")
