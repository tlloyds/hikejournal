from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from hike_journal.models import PhotoMetadata, ProcessedImage, SpeciesCandidate
from mobile_api import (
    CoverPhotoInput,
    HikeInput,
    KnownSpeciesInput,
    ReviewCandidateInput,
    ReviewDecisionInput,
    ReviewQueueInput,
    SpeciesQuestInput,
    _build_species_payloads,
    _photo_payload,
    _parse_picker_taken_at,
    _standalone_hike_payload,
    _review_candidates,
    _species_key,
    _validate_picker_coordinate,
    app,
    assign_known_species_to_photo,
    create_hike,
    create_species_quest,
    delete_species_quest,
    get_nearby_species,
    get_nearby_species_sightings,
    get_species_quest_sightings,
    get_hike,
    get_hike_photos,
    get_hike_route,
    list_discovery_areas,
    list_hike_locations,
    decide_species_review,
    derive_mobile_api_token,
    queue_photo_for_species_review,
    require_mobile_key,
    request_species_recommendation,
    set_photo_species_review,
    update_hike_cover,
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


def test_hike_detail_includes_route_segments_for_native_map(monkeypatch):
    class Repository:
        def list_photos(self, _hike_id):
            return []

        def list_observations(self, _hike_id):
            return []

        def get_hike_route_import(self, hike_id):
            assert hike_id == "hike-1"
            return {
                "track_geojson": {
                    "type": "LineString",
                    "coordinates": [[-82.1, 28.1], [-82.2, 28.2]],
                }
            }

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr(
        "mobile_api._get_visible_hike",
        lambda _repository, _hike_id: {"id": "hike-1", "title": "Pine Loop"},
    )

    payload = get_hike("hike-1")

    assert payload["route_segments"] == [
        [{"lat": 28.1, "lng": -82.1}, {"lat": 28.2, "lng": -82.2}]
    ]


def test_hike_photo_page_is_bounded_for_large_hikes(monkeypatch):
    class Repository:
        def list_photos_page(self, _hike_id, *, offset, limit):
            return [
                {"id": f"photo-{index}", "hike_id": "hike-1", "public_url": "https://images.example/photo.jpg"}
                for index in range(offset, min(offset + limit, 256))
            ]

        def list_observations_for_photo_ids(self, _photo_ids):
            return []

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._get_visible_hike", lambda *_args: {"id": "hike-1"})

    first_page = get_hike_photos("hike-1", offset=0, limit=50)
    final_page = get_hike_photos("hike-1", offset=250, limit=50)

    assert len(first_page["photos"]) == 50
    assert first_page["next_offset"] == 50
    assert len(final_page["photos"]) == 6
    assert final_page["next_offset"] is None


def test_everyday_journal_photo_page_and_route_are_available_to_android(monkeypatch):
    class Repository:
        def list_observations_for_photo_ids(self, photo_ids):
            assert photo_ids == ["everyday-photo"]
            return []

    service = type("Service", (), {"repository": Repository()})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr(
        "mobile_api._visible_standalone_photos",
        lambda _service: [{"id": "everyday-photo", "public_url": "https://images.example/everyday.jpg"}],
    )

    page = get_hike_photos("everyday", offset=0, limit=50)

    assert [photo["id"] for photo in page["photos"]] == ["everyday-photo"]
    assert page["next_offset"] is None
    assert get_hike_route("everyday") == {"route_segments": []}


def test_mobile_route_upload_saves_tcx_and_returns_map_segments(monkeypatch):
    class Repository:
        def get_hike_route_import(self, hike_id):
            assert hike_id == "hike-1"
            return None

    route_import = {
        "track_point_count": 2,
        "track_geojson": {
            "type": "LineString",
            "coordinates": [[-82.1, 28.1], [-82.2, 28.2]],
        },
    }
    service = type("Service", (), {"repository": Repository(), "storage": object()})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._get_visible_hike", lambda *_args: {"id": "hike-1"})
    captured = {}

    def sync(**kwargs):
        captured["name"] = kwargs["uploaded_file"].name
        captured["contents"] = kwargs["uploaded_file"].getvalue()
        return route_import, None

    monkeypatch.setattr("mobile_api.sync_hike_route_import", sync)
    app.dependency_overrides[require_mobile_key] = lambda: None
    try:
        response = TestClient(app).post(
            "/v1/hikes/hike-1/route",
            files={"file": ("pine-loop.tcx.txt", b"<TrainingCenterDatabase/>", "text/plain")},
        )
    finally:
        app.dependency_overrides.pop(require_mobile_key, None)

    assert response.status_code == 201
    assert captured == {"name": "pine-loop.tcx.txt", "contents": b"<TrainingCenterDatabase/>"}
    assert response.json() == {
        "route_segments": [[{"lat": 28.1, "lng": -82.1}, {"lat": 28.2, "lng": -82.2}]],
        "track_point_count": 2,
    }


def test_picker_metadata_fallback_parses_capture_time_and_coordinates():
    taken_at = _parse_picker_taken_at("2026-07-19T14:32:10Z")

    assert taken_at is not None
    assert taken_at.isoformat() == "2026-07-19T14:32:10+00:00"
    assert _validate_picker_coordinate(28.5, minimum=-90, maximum=90, label="latitude") == 28.5
    assert _validate_picker_coordinate(-81.25, minimum=-180, maximum=180, label="longitude") == -81.25


def test_photo_upload_uses_picker_metadata_when_file_exif_is_redacted(monkeypatch):
    class Repository:
        created = None

        def create_photo(self, payload):
            self.created = payload
            return {"id": "photo-1", **payload}

    class Storage:
        def upload_hike_photo(self, *_args, **_kwargs):
            return "hikes/hike-1/photo-1.jpg", "https://images.example/photo-1.jpg"

        def delete_file(self, _path):
            raise AssertionError("Successful uploads must not be deleted.")

    repository = Repository()
    service = type("Service", (), {"repository": repository, "storage": Storage()})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._get_visible_hike", lambda _repository, _hike_id: {"id": "hike-1"})
    monkeypatch.setattr(
        "mobile_api.extract_metadata",
        lambda _bytes: PhotoMetadata(
            lat=None,
            lng=None,
            taken_at=None,
            exif_json={
                "datetime_original": None,
                "gps_latitude": None,
                "gps_longitude": None,
            },
        ),
    )
    monkeypatch.setattr(
        "mobile_api.optimize_image",
        lambda _bytes: ProcessedImage(
            bytes_data=b"optimized",
            width=1600,
            height=1200,
            format="JPEG",
            content_type="image/jpeg",
        ),
    )
    app.dependency_overrides[require_mobile_key] = lambda: None
    try:
        response = TestClient(app).post(
            "/v1/hikes/hike-1/photos",
            files={"file": ("trail.jpg", b"redacted-image", "image/jpeg")},
            data={
                "taken_at": "2026-07-19T14:32:10Z",
                "lat": "28.5",
                "lng": "-81.25",
            },
        )
    finally:
        app.dependency_overrides.pop(require_mobile_key, None)

    assert response.status_code == 201
    assert repository.created["taken_at"] == "2026-07-19T14:32:10+00:00"
    assert repository.created["lat"] == 28.5
    assert repository.created["lng"] == -81.25
    assert repository.created["exif_json"]["picker_taken_at"] == "2026-07-19T14:32:10+00:00"


def test_species_key_prefers_stable_taxon_id():
    assert _species_key(
        {"taxon_id": 1234, "scientific_name": "Liatris gracilis", "common_name": "Blazing star"}
    ) == "taxon:1234"


def test_species_key_credits_infraspecies_to_its_parent_species():
    assert _species_key(
        {
            "taxon_id": 5678,
            "species_taxon_id": 1234,
            "scientific_name": "Liatris gracilis var. gracilis",
        }
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
            "iconic_taxon_name": "Plantae",
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
    assert payload["hike_latest_seen"] == {
        "hike-a": "2026-01-01",
        "hike-b": "2026-02-01",
    }
    assert payload["latest_seen"] == "2026-02-01"
    assert payload["cover_url"] == "https://img/b.jpg"
    assert payload["iconic_taxon_name"] == "Plantae"


def test_species_payload_compares_observation_instants_across_timezones():
    observations = [
        {
            "taxon_id": 42,
            "photo_id": "photo-local-next-day",
            "hike_id": "hike-a",
            "common_name": "Pinewoods milkweed",
            "scientific_name": "Asclepias humistrata",
        },
        {
            "taxon_id": 42,
            "photo_id": "photo-later-utc",
            "hike_id": "hike-a",
            "common_name": "Pinewoods milkweed",
            "scientific_name": "Asclepias humistrata",
        },
    ]
    photos = {
        "photo-local-next-day": {
            "id": "photo-local-next-day",
            "hike_id": "hike-a",
            "public_url": "https://img/local-next-day.jpg",
            "taken_at": "2026-07-30T00:30:00+02:00",
        },
        "photo-later-utc": {
            "id": "photo-later-utc",
            "hike_id": "hike-a",
            "public_url": "https://img/later-utc.jpg",
            "taken_at": "2026-07-29T23:00:00Z",
        },
    }
    hikes = {"hike-a": {"id": "hike-a", "hike_date": "2026-07-29"}}

    payload = _build_species_payloads(observations, photos, hikes)[0]

    assert payload["latest_seen"] == "2026-07-29T23:00:00Z"
    assert payload["hike_latest_seen"] == {"hike-a": "2026-07-29T23:00:00Z"}
    assert payload["cover_url"] == "https://img/later-utc.jpg"


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


def test_existing_photo_can_be_removed_from_species_review(monkeypatch):
    class Repository:
        photo_status = None

        def update_photo_processing_status(self, photo_id, status):
            self.photo_status = (photo_id, status)

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr(
        "mobile_api._get_visible_photo",
        lambda photo_id: (service, {"id": photo_id, "content_type": "image/jpeg"}),
    )

    result = set_photo_species_review("photo-1", ReviewQueueInput(queued=False))

    assert result == {"queued": False}
    assert repository.photo_status == ("photo-1", "ready")


def test_known_species_can_be_assigned_to_an_untagged_photo(monkeypatch):
    class Repository:
        created = None
        photo_status = None

        def list_observations_for_photo_ids(self, _photo_ids):
            return []

        def list_observations_by_ids(self, observation_ids):
            assert observation_ids == ["observation-source"]
            return [{"raw_response_json": {"taxon_enrichment": {"rank": "species"}}}]

        def create_manual_observation(self, **kwargs):
            self.created = kwargs
            return {**kwargs, "id": "observation-new"}

        def update_photo_processing_status(self, photo_id, status):
            self.photo_status = (photo_id, status)

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    photo = {
        "id": "photo-1",
        "hike_id": "hike-1",
        "content_type": "image/jpeg",
        "owner_email": "hiker@example.com",
    }
    monkeypatch.setattr("mobile_api._get_visible_photo", lambda _photo_id: (service, photo))
    monkeypatch.setattr(
        "mobile_api._visible_species_data",
        lambda _service: (
            [
                {
                    "id": "observation-source",
                    "taxon_id": 123,
                    "common_name": "Gopher tortoise",
                    "scientific_name": "Gopherus polyphemus",
                    "status": "confirmed",
                }
            ],
            {},
            {},
        ),
    )

    result = assign_known_species_to_photo(
        "photo-1",
        KnownSpeciesInput(
            taxon_id=123,
            common_name="Gopher tortoise",
            scientific_name="Gopherus polyphemus",
        ),
    )

    assert repository.created["source"] == "known_species"
    assert repository.created["status"] == "confirmed"
    assert repository.created["is_primary"] is True
    assert repository.created["raw_payload"]["known_species_assignment"]["source_observation_id"] == "observation-source"
    assert repository.created["raw_payload"]["taxon_enrichment"] == {"rank": "species"}
    assert repository.photo_status == ("photo-1", "ready")
    assert result["species"][0]["common_name"] == "Gopher tortoise"


def test_known_species_assignment_is_idempotent_after_sync_retry(monkeypatch):
    existing = {
        "id": "observation-existing",
        "photo_id": "photo-1",
        "taxon_id": 123,
        "common_name": "Gopher tortoise",
        "scientific_name": "Gopherus polyphemus",
        "status": "confirmed",
        "is_primary": True,
    }

    class Repository:
        photo_status = None

        def list_observations_for_photo_ids(self, _photo_ids):
            return [existing]

        def update_photo_processing_status(self, photo_id, status):
            self.photo_status = (photo_id, status)

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr(
        "mobile_api._get_visible_photo",
        lambda _photo_id: (service, {"id": "photo-1", "content_type": "image/jpeg"}),
    )

    result = assign_known_species_to_photo(
        "photo-1",
        KnownSpeciesInput(taxon_id=123, common_name="Gopher tortoise"),
    )

    assert repository.photo_status == ("photo-1", "ready")
    assert result["species"][0]["common_name"] == "Gopher tortoise"


def test_hike_cover_can_be_selected_from_the_same_hike(monkeypatch):
    hike_id = "11111111-1111-4111-8111-111111111111"
    photo_id = "22222222-2222-4222-8222-222222222222"

    class Repository:
        selected_cover = None

        def update_hike_cover_photo(self, updated_hike_id, updated_photo_id):
            self.selected_cover = (updated_hike_id, updated_photo_id)
            return {"id": updated_hike_id, "title": "Pine Loop", "cover_photo_id": updated_photo_id}

        def list_photos(self, _hike_id):
            return [{"id": photo_id, "hike_id": hike_id, "public_url": "https://img/cover.jpg"}]

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._get_visible_hike", lambda _repository, _hike_id: {"id": hike_id})
    monkeypatch.setattr(
        "mobile_api._get_visible_photo",
        lambda _photo_id: (service, {"id": photo_id, "hike_id": hike_id}),
    )

    result = update_hike_cover(hike_id, CoverPhotoInput(photo_id=photo_id))

    assert repository.selected_cover == (hike_id, photo_id)
    assert result["cover_photo_id"] == photo_id
    assert result["cover_url"] == "https://img/cover.jpg"


def test_everyday_journal_includes_standalone_photos_and_species(monkeypatch):
    photo = {
        "id": "photo-1",
        "hike_id": None,
        "public_url": "https://img/everyday.jpg",
        "taken_at": "2026-07-30T14:00:00Z",
        "created_at": "2026-07-30T14:05:00Z",
    }

    class Repository:
        def list_observations_for_photo_ids(self, photo_ids):
            assert photo_ids == ["photo-1"]
            return [
                {
                    "photo_id": "photo-1",
                    "status": "confirmed",
                    "taxon_id": 123,
                    "common_name": "Gopher tortoise",
                }
            ]

    service = type("Service", (), {"repository": Repository()})()
    monkeypatch.setattr("mobile_api._visible_standalone_photos", lambda _service: [photo])
    monkeypatch.setattr(
        "mobile_api._user_context",
        lambda: {"mode": "local-dev", "email": None, "subject": None, "auth_configured": False},
    )

    payload = _standalone_hike_payload(service, include_details=True)

    assert payload["id"] == "everyday"
    assert payload["is_standalone"] is True
    assert payload["photo_count"] == 1
    assert payload["species_count"] == 1
    assert payload["cover_url"] == "https://img/everyday.jpg"
    assert payload["photos"][0]["species"][0]["common_name"] == "Gopher tortoise"


def test_discovery_area_endpoint_returns_coordinate_backed_locations(monkeypatch):
    repository = type(
        "Repository",
        (),
        {
            "list_hike_locations": lambda _self: [
                {"id": "area-1", "name": "Alafia Scrub Preserve", "lat": 27.86, "lng": -82.34}
            ]
        },
    )()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)

    result = list_discovery_areas("alafia")

    assert result[0]["id"] == "area-1"


def test_native_hike_locations_returns_imported_library(monkeypatch):
    repository = type(
        "Repository",
        (),
        {
            "list_hike_locations": lambda _self: [
                {"id": "location-1", "name": "Alafia Scrub Preserve"},
                {"id": "", "name": "Ignored"},
            ]
        },
    )()
    monkeypatch.setattr(
        "mobile_api.get_services",
        lambda: type("Service", (), {"repository": repository})(),
    )

    assert list_hike_locations() == [
        {"id": "location-1", "name": "Alafia Scrub Preserve"},
    ]


def test_create_hike_correlates_selected_imported_location(monkeypatch):
    location_id = "22222222-2222-4222-8222-222222222222"

    class Repository:
        location_tags = None

        def create_hike(self, draft, hike_id=None):
            assert draft.location_name == "Alafia Scrub Preserve"
            return {
                "id": "11111111-1111-4111-8111-111111111111",
                "title": draft.title,
                "hike_date": draft.hike_date,
                "distance_miles": draft.distance_miles,
                "location_name": draft.location_name,
                "notes": draft.notes,
            }

        def list_hike_locations(self):
            return [{"id": location_id, "name": "Alafia Scrub Preserve"}]

        def set_hike_location_tags(self, hike_id, location_ids):
            self.location_tags = (hike_id, location_ids)

    repository = Repository()
    monkeypatch.setattr(
        "mobile_api.get_services",
        lambda: type("Service", (), {"repository": repository})(),
    )
    monkeypatch.setattr(
        "mobile_api._user_context",
        lambda: {"subject": None, "email": None},
    )
    monkeypatch.setattr("mobile_api._invalidate_species_data_cache", lambda: None)

    result = create_hike(
        HikeInput(
            title="Scrub loop",
            hike_date="2026-07-31",
            location_name="Alafia Scrub Preserve",
            location_id=location_id,
        )
    )

    assert result["location_name"] == "Alafia Scrub Preserve"
    assert repository.location_tags == (result["id"], [location_id])


def test_current_location_discovery_rounds_coordinates_before_query(monkeypatch):
    captured = {}
    repository = object()
    service_container = type("Service", (), {"repository": repository})()

    class Discovery:
        def __init__(self, _repository):
            pass

        def nearby(self, **kwargs):
            captured.update(kwargs)
            return {"taxa": [], "progress": {"collected_count": 0, "total_count": 0}}

    monkeypatch.setattr("mobile_api.get_services", lambda: service_container)
    monkeypatch.setattr("mobile_api.SpeciesDiscoveryService", Discovery)
    monkeypatch.setattr("mobile_api._discovery_collection_data", lambda _service: ([], {}))

    get_nearby_species(
        area_id=None,
        target_date=__import__("datetime").date(2026, 7, 26),
        radius_km=10,
        iconic_taxon=None,
        lat=28.12345,
        lng=-82.67891,
        area_name="Current area",
        limit=50,
    )

    assert captured["area"]["lat"] == 28.12
    assert captured["area"]["lng"] == -82.68
    assert captured["limit"] == 50


def test_current_location_endpoint_parses_android_discovery_query(monkeypatch):
    captured = {}
    repository = object()
    service_container = type("Service", (), {"repository": repository})()

    class Discovery:
        def __init__(self, _repository):
            pass

        def nearby(self, **kwargs):
            captured.update(kwargs)
            return {"taxa": [], "progress": {"collected_count": 0, "total_count": 0}}

    monkeypatch.setattr("mobile_api.get_services", lambda: service_container)
    monkeypatch.setattr("mobile_api.SpeciesDiscoveryService", Discovery)
    monkeypatch.setattr("mobile_api._discovery_collection_data", lambda _service: ([], {}))
    app.dependency_overrides[require_mobile_key] = lambda: None
    try:
        for limit in ("50", "100"):
            response = TestClient(app).get(
                "/v1/discovery/nearby",
                params={
                    "date": "2026-07-27",
                    "radius_km": "10",
                    "lat": "28.12345",
                    "lng": "-82.67891",
                    "area_name": "Current area",
                    "limit": limit,
                },
            )

            assert response.status_code == 200
            assert captured["radius_km"] == 10
            assert captured["limit"] == int(limit)
            assert captured["area"]["lat"] == 28.12
            assert captured["area"]["lng"] == -82.68
    finally:
        app.dependency_overrides.pop(require_mobile_key, None)


def test_nearby_sightings_endpoint_accepts_the_current_result_context(monkeypatch):
    captured = {}
    repository = object()
    service_container = type("Service", (), {"repository": repository})()

    class Discovery:
        def __init__(self, received_repository):
            assert received_repository is repository

        def nearby_sightings_payload(self, **kwargs):
            captured.update(kwargs)
            return {"mapped_count": 1, "sightings": [{"id": "obs-1"}]}

    monkeypatch.setattr("mobile_api.get_services", lambda: service_container)
    monkeypatch.setattr("mobile_api.SpeciesDiscoveryService", Discovery)

    result = get_nearby_species_sightings(
        taxon_id=163916,
        area_id=None,
        target_date=__import__("datetime").date(2026, 7, 28),
        radius_km=10,
        lat=28.12345,
        lng=-82.67891,
        area_name="Current area",
    )

    assert result["mapped_count"] == 1
    assert captured["area"]["lat"] == 28.12
    assert captured["area"]["lng"] == -82.68
    assert captured["taxon_id"] == 163916

    app.dependency_overrides[require_mobile_key] = lambda: None
    try:
        response = TestClient(app).get(
            "/v1/discovery/nearby/sightings",
            params={
                "taxon_id": "163916",
                "date": "2026-07-28",
                "radius_km": "10",
                "lat": "28.12345",
                "lng": "-82.67891",
                "area_name": "Current area",
            },
        )
    finally:
        app.dependency_overrides.pop(require_mobile_key, None)

    assert response.status_code == 200
    assert response.json()["sightings"] == [{"id": "obs-1"}]


def test_nearby_endpoint_rejects_unsupported_radius_after_query_parsing():
    app.dependency_overrides[require_mobile_key] = lambda: None
    try:
        response = TestClient(app).get(
            "/v1/discovery/nearby",
            params={
                "date": "2026-07-27",
                "radius_km": "7",
                "lat": "28.12",
                "lng": "-82.68",
            },
        )
    finally:
        app.dependency_overrides.pop(require_mobile_key, None)

    assert response.status_code == 422
    assert response.json()["detail"] == "Radius must be one of (5, 10, 25)."


def test_nearby_endpoint_rejects_unsupported_limit_after_query_parsing():
    app.dependency_overrides[require_mobile_key] = lambda: None
    try:
        response = TestClient(app).get(
            "/v1/discovery/nearby",
            params={
                "date": "2026-07-27",
                "radius_km": "10",
                "lat": "28.12",
                "lng": "-82.68",
                "limit": "75",
            },
        )
    finally:
        app.dependency_overrides.pop(require_mobile_key, None)

    assert response.status_code == 422
    assert response.json()["detail"] == "Species limit must be one of (50, 100)."


def test_delete_species_quest_checks_visibility_then_deletes(monkeypatch):
    class Repository:
        deleted = None

        def delete_species_quest(self, quest_id):
            self.deleted = quest_id

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr(
        "mobile_api._get_visible_quest",
        lambda _service, quest_id: {"id": quest_id, "title": "Wetland birds"},
    )

    result = delete_species_quest("quest-1")

    assert result == {"deleted": True, "id": "quest-1"}
    assert repository.deleted == "quest-1"


def test_create_species_quest_converts_target_save_failure_to_service_error(monkeypatch):
    class Repository:
        def list_hike_locations(self):
            return [{"id": "area-1", "name": "Wetland", "lat": 28.1, "lng": -82.2}]

        def create_species_quest(self, _payload, _taxa):
            raise RuntimeError("Field Quest targets could not be saved.")

    repository = Repository()
    service_container = type("Service", (), {"repository": repository})()

    class Discovery:
        def __init__(self, received_repository):
            assert received_repository is repository

        def resolve_area(self, _repository, area_id):
            assert area_id == "area-1"
            return {"id": "area-1", "name": "Wetland", "lat": 28.1, "lng": -82.2}

        def nearby(self, **_kwargs):
            return {
                "period": {"label": "Late July", "months": [6, 7, 8]},
                "filters": {"iconic_taxon": None},
                "taxa": [{"taxon_id": 1}],
            }

    monkeypatch.setattr("mobile_api.get_services", lambda: service_container)
    monkeypatch.setattr("mobile_api._user_context", lambda: {"subject": None, "email": None})
    monkeypatch.setattr("mobile_api._discovery_collection_data", lambda _service: ([], {}))
    monkeypatch.setattr("mobile_api.SpeciesDiscoveryService", Discovery)

    with pytest.raises(HTTPException) as error:
        create_species_quest(SpeciesQuestInput(area_id="area-1", target_date=date(2026, 7, 31)))

    assert error.value.status_code == 503
    assert error.value.detail == "Field Quest targets could not be saved."


def test_quest_sightings_endpoint_checks_quest_visibility_and_species(monkeypatch):
    captured = {}
    repository = object()
    service = type("Service", (), {"repository": repository})()
    quest = {
        "id": "quest-1",
        "taxa": [{"taxon_id": 163916, "common_name": "Alligator lily"}],
    }

    class Discovery:
        def __init__(self, received_repository):
            assert received_repository is repository

        def quest_sightings_payload(self, received_quest, *, taxon_id):
            captured["quest"] = received_quest
            captured["taxon_id"] = taxon_id
            return {"mapped_count": 1, "sightings": [{"id": "obs-1"}]}

    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._get_visible_quest", lambda _service, _quest_id: quest)
    monkeypatch.setattr("mobile_api.SpeciesDiscoveryService", Discovery)

    result = get_species_quest_sightings("quest-1", taxon_id=163916)

    assert result["mapped_count"] == 1
    assert captured == {"quest": quest, "taxon_id": 163916}
    app.dependency_overrides[require_mobile_key] = lambda: None
    try:
        response = TestClient(app).get(
            "/v1/discovery/quests/quest-1/sightings",
            params={"taxon_id": "163916"},
        )
    finally:
        app.dependency_overrides.pop(require_mobile_key, None)

    assert response.status_code == 200
    assert response.json()["sightings"] == [{"id": "obs-1"}]


def test_mobile_review_can_request_and_save_an_inaturalist_recommendation(monkeypatch):
    class Repository:
        saved = None

        def upsert_observation(self, hike_id, photo_id, candidate, **kwargs):
            self.saved = (hike_id, photo_id, candidate, kwargs)

    repository = Repository()
    service = type("Service", (), {"repository": repository, "storage": object()})()
    photo = {
        "id": "photo-1",
        "hike_id": "hike-1",
        "processing_status": "in_review",
        "storage_path": "hikes/hike-1/photo-1.jpg",
        "lat": 28.7,
        "lng": -81.2,
        "taken_at": "2026-07-20T09:15:00",
        "owner_subject": "subject-1",
        "owner_email": "owner@example.com",
    }

    class InatClient:
        def score_species_candidates(self, **kwargs):
            assert kwargs["image_bytes"] == b"field-photo"
            assert kwargs["lat"] == 28.7
            assert kwargs["lng"] == -81.2
            assert kwargs["observed_on"].date().isoformat() == "2026-07-20"
            return [
                SpeciesCandidate(
                    taxon_id=42,
                    common_name="Gopher Tortoise",
                    scientific_name="Gopherus polyphemus",
                    confidence=0.91,
                    raw_payload={"results": []},
                )
            ], {"results": []}

    monkeypatch.setattr("mobile_api._get_visible_photo", lambda _photo_id: (service, photo))
    monkeypatch.setattr("mobile_api._download_photo_for_cv", lambda _svc, _photo: b"field-photo")
    monkeypatch.setattr("mobile_api._mobile_inat_client", InatClient)
    monkeypatch.setattr(
        "mobile_api._review_queue_payload",
        lambda _service: [{"id": "photo-1", "candidates": [{"taxon_id": 42}]}],
    )

    result = request_species_recommendation("photo-1")

    assert result["id"] == "photo-1"
    assert repository.saved[0:2] == ("hike-1", "photo-1")
    assert repository.saved[2].taxon_id == 42
    assert repository.saved[3] == {"owner_subject": "subject-1", "owner_email": "owner@example.com"}
