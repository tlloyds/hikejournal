from __future__ import annotations

import asyncio
from datetime import date
import logging

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient

import mobile_api
from hike_journal.models import PhotoMetadata, ProcessedImage, SpeciesCandidate
from hike_journal.services.inat import InatRequestError
from mobile_api import (
    CoverPhotoInput,
    HikeInput,
    KnownSpeciesInput,
    ReviewCandidateInput,
    ReviewDecisionInput,
    ReviewQueueInput,
    SpeciesQuestInput,
    _build_species_payloads,
    _active_quest_focus_taxon_ids,
    _hike_payload,
    _photo_payload,
    _mobile_inat_client,
    _publish_item_payload,
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
    get_place_profile,
    list_discovery_areas,
    list_hikes,
    list_hike_locations,
    list_map_routes,
    decide_species_review,
    derive_mobile_api_token,
    queue_photo_for_species_review,
    require_mobile_key,
    request_species_recommendation,
    request_species_batch_recommendation,
    start_species_batch_recommendation,
    get_species_batch_recommendation_status,
    PublishBatchInput,
    PublishBatchGroupInput,
    start_species_publish_batch,
    get_species_publish_batch_status,
    set_photo_species_review,
    update_hike_cover,
    ReviewBatchInput,
    ReviewBatchGroupInput,
)


def test_field_briefing_uses_only_focused_targets_from_active_quests():
    quests = [
        {
            "status": "active",
            "taxa": [
                {"taxon_id": 1, "focus_order": 1},
                {"taxon_id": 2, "focus_order": None},
            ],
        },
        {"status": "archived", "taxa": [{"taxon_id": 3, "focus_order": 1}]},
        {"status": "active", "taxa": [{"taxon_id": "4", "focus_order": 2}]},
    ]

    assert _active_quest_focus_taxon_ids(quests) == {1, 4}


def test_request_log_message_contains_correlation_and_timing_fields(
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(mobile_api, "services", None)
    caplog.set_level(logging.INFO, logger="mobile_api")

    response = TestClient(app).get(
        "/health",
        headers={"X-Request-ID": "personal-apk-request-1"},
    )

    assert response.status_code == 200
    message = next(
        record.getMessage()
        for record in caplog.records
        if record.name == "mobile_api" and "request completed" in record.getMessage()
    )
    assert "request_id=personal-apk-request-1" in message
    assert "method=GET" in message
    assert "route=/health" in message
    assert "status=200" in message
    assert "latency_ms=" in message


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


def test_hosted_mobile_api_rejects_weak_or_unscoped_configuration(monkeypatch):
    monkeypatch.setenv("MOBILE_REQUIRE_EXPLICIT_TOKEN", "true")
    monkeypatch.setenv("MOBILE_API_TOKEN", "too-short")
    monkeypatch.delenv("MOBILE_OWNER_EMAIL", raising=False)
    monkeypatch.delenv("MOBILE_OWNER_SUBJECT", raising=False)

    with pytest.raises(RuntimeError, match="MOBILE_API_TOKEN") as failure:
        mobile_api._validate_hosted_mobile_configuration()

    assert "MOBILE_OWNER_EMAIL" in str(failure.value)
    assert "MOBILE_OWNER_SUBJECT" in str(failure.value)
    assert "too-short" not in str(failure.value)


def test_hosted_mobile_api_accepts_strong_owner_scoped_configuration(monkeypatch):
    monkeypatch.setenv("MOBILE_REQUIRE_EXPLICIT_TOKEN", "true")
    monkeypatch.setenv(
        "MOBILE_API_TOKEN",
        "qA7-random-personal-pairing-key_92vX5mN3z",
    )
    monkeypatch.setenv("MOBILE_OWNER_EMAIL", "owner@example.com")
    monkeypatch.setenv("MOBILE_OWNER_SUBJECT", "personal-owner-2026")

    mobile_api._validate_hosted_mobile_configuration()


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


def test_publish_payload_assigns_standalone_items_to_everyday_sightings():
    payload = _publish_item_payload(
        {"id": "observation-1", "common_name": "Eastern gray squirrel"},
        {"id": "photo-1", "taken_at": "2026-08-04T10:00:00"},
        None,
    )

    assert payload["hike_id"] == "everyday"
    assert payload["hike_title"] == "Everyday sightings"
    assert payload["hike_date"] == "2026-08-04T10:00:00"


def test_mobile_publishing_upgrades_legacy_oauth_token_to_an_api_jwt(monkeypatch):
    saved = {}
    monkeypatch.setattr("mobile_api._user_context", lambda: {"subject": "user-1", "email": "hiker@example.com"})
    monkeypatch.setattr("mobile_api._load_mobile_inat_token", lambda _email: "legacy-oauth-token")
    monkeypatch.setattr("mobile_api.fetch_api_token_for_oauth_access_token", lambda token: f"jwt.for.{token}")
    monkeypatch.setattr("mobile_api.get_services", lambda: object())
    monkeypatch.setattr(
        "mobile_api._save_mobile_inat_token",
        lambda _service, *, email, access_token: saved.update(email=email, access_token=access_token),
    )

    client = _mobile_inat_client()

    assert client.access_token == "jwt.for.legacy-oauth-token"
    assert saved == {"email": "hiker@example.com", "access_token": "jwt.for.legacy-oauth-token"}


def test_mobile_publishing_uses_a_fresh_jwt_from_stored_oauth_credentials(monkeypatch):
    monkeypatch.setattr("mobile_api._user_context", lambda: {"subject": "user-1", "email": "hiker@example.com"})
    monkeypatch.setattr(
        "mobile_api._load_mobile_inat_token",
        lambda _email: '{"oauth_access_token":"renewable-oauth-token","refresh_token":"refresh-token"}',
    )
    monkeypatch.setattr("mobile_api.fetch_api_token_for_oauth_access_token", lambda token: f"jwt.for.{token}")

    client = _mobile_inat_client()

    assert client.access_token == "jwt.for.renewable-oauth-token"


def test_photo_payload_includes_stored_species_wikipedia_info():
    payload = _photo_payload(
        {"id": "photo-1"},
        species=[
            {
                "taxon_id": 47126,
                "common_name": "Eastern gray squirrel",
                "scientific_name": "Sciurus carolinensis",
                "status": "confirmed",
                "is_primary": True,
                "raw_response_json": {
                    "taxon_enrichment": {
                        "wikipedia_url": "https://en.wikipedia.org/wiki/Eastern_gray_squirrel",
                        "wikipedia_summary": "<i><b>The eastern gray squirrel</b></i> is a tree squirrel.",
                    }
                },
            }
        ],
    )

    assert payload["species"] == [
        {
            "common_name": "Eastern gray squirrel",
            "scientific_name": "Sciurus carolinensis",
            "status": "confirmed",
            "is_primary": True,
            "taxon_id": 47126,
            "wikipedia_url": "https://en.wikipedia.org/wiki/Eastern_gray_squirrel",
            "wikipedia_summary": "The eastern gray squirrel is a tree squirrel.",
        }
    ]


def test_photo_payload_includes_wikipedia_info_from_field_guide_records():
    payload = _photo_payload(
        {"id": "photo-1"},
        species=[
            {
                "common_name": "Eastern gray squirrel",
                "scientific_name": "Sciurus carolinensis",
                "status": "confirmed",
                "is_primary": True,
                "wikipedia_url": "https://en.wikipedia.org/wiki/Eastern_gray_squirrel",
                "wikipedia_summary": "The eastern gray squirrel is a tree squirrel.",
            }
        ],
    )

    assert payload["species"][0]["wikipedia_summary"] == "The eastern gray squirrel is a tree squirrel."
    assert payload["species"][0]["wikipedia_url"] == "https://en.wikipedia.org/wiki/Eastern_gray_squirrel"


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


def test_hike_list_hydrates_saved_weather_in_one_batch(monkeypatch):
    class Repository:
        def _select_all_rows(self, _query_factory):
            return []

        def list_hike_weather_snapshots(self):
            return [
                {
                    "hike_id": "hike-1",
                    "provider": "open-meteo",
                    "condition_label": "Partly cloudy",
                    "enriched_at": "2026-08-10T03:00:00Z",
                }
            ]

    service = type("Service", (), {"repository": Repository(), "client": object()})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr(
        "mobile_api._visible_hikes",
        lambda _repository: [{"id": "hike-1", "title": "Pine Loop"}],
    )
    monkeypatch.setattr("mobile_api._visible_species_data", lambda _service: ([], {}, {}))
    monkeypatch.setattr(
        "mobile_api._standalone_hike_payload",
        lambda _service: {"id": "everyday", "title": "Everyday sightings"},
    )

    payload = list_hikes()

    assert payload[0]["weather"]["condition_label"] == "Partly cloudy"
    assert "owner_email" not in payload[0]["weather"]
    assert payload[1]["id"] == "everyday"


def test_hike_list_resolves_selected_cover_missing_from_bulk_photo_scan(monkeypatch):
    hike_id = "11111111-1111-4111-8111-111111111111"
    photo_id = "22222222-2222-4222-8222-222222222222"

    class Repository:
        def _select_all_rows(self, _query_factory):
            return []

        def list_photo_records_for_ids(self, photo_ids):
            assert photo_ids == [photo_id]
            return [{
                "id": photo_id,
                "hike_id": hike_id,
                "public_url": "https://img/selected.jpg",
            }]

        def list_hike_weather_snapshots(self):
            return []

    service = type("Service", (), {"repository": Repository(), "client": object()})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr(
        "mobile_api._visible_hikes",
        lambda _repository: [{
            "id": hike_id,
            "title": "Pine Loop",
            "cover_photo_id": photo_id,
        }],
    )
    monkeypatch.setattr("mobile_api._visible_species_data", lambda _service: ([], {}, {}))
    monkeypatch.setattr(
        "mobile_api._standalone_hike_payload",
        lambda _service: {"id": "everyday", "title": "Everyday sightings"},
    )

    payload = list_hikes()

    assert payload[0]["cover_photo_id"] == photo_id
    assert payload[0]["cover_url"] == "https://img/selected.jpg"


def test_hike_list_only_decorates_selected_cover_from_lightweight_photo_index(monkeypatch):
    hike_id = "11111111-1111-4111-8111-111111111111"
    cover_id = "22222222-2222-4222-8222-222222222222"
    photo_rows = [
        {
            "id": cover_id,
            "hike_id": hike_id,
            "public_url": "r2://photos/cover.jpg",
            "storage_path": "photos/cover.jpg",
            "taken_at": "2026-08-01T10:00:00Z",
            "created_at": "2026-08-01T10:00:00Z",
        },
        {
            "id": "33333333-3333-4333-8333-333333333333",
            "hike_id": hike_id,
            "public_url": "r2://photos/other.jpg",
            "storage_path": "photos/other.jpg",
            "taken_at": "2026-08-01T10:01:00Z",
            "created_at": "2026-08-01T10:01:00Z",
        },
    ]

    class Repository:
        def list_photo_index_for_hikes(self, hike_ids):
            assert hike_ids == [hike_id]
            return photo_rows

        def decorate_media_row(self, photo):
            return {**photo, "public_url": f"https://signed.example/{photo['id']}"}

        def list_hike_weather_snapshots(self):
            return []

    service = type("Service", (), {"repository": Repository(), "client": object()})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr(
        "mobile_api._visible_hikes",
        lambda _repository: [{"id": hike_id, "title": "Pine Loop", "cover_photo_id": cover_id}],
    )
    monkeypatch.setattr("mobile_api._visible_species_data", lambda _service: ([], {}, {}))
    monkeypatch.setattr(
        "mobile_api._standalone_hike_payload",
        lambda _service: {"id": "everyday", "title": "Everyday sightings"},
    )

    payload = list_hikes()

    assert payload[0]["cover_url"] == f"https://signed.example/{cover_id}"


def test_main_map_routes_include_visible_hike_tracks(monkeypatch):
    class Repository:
        def list_hike_route_imports(self):
            return [{
                "hike_id": "hike-1",
                "track_geojson": {
                    "type": "LineString",
                    "coordinates": [[-82.1, 28.1], [-82.2, 28.2]],
                }
            }]

    service = type("Service", (), {"repository": Repository()})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._visible_hikes", lambda _repository: [{"id": "hike-1"}])

    assert list_map_routes() == [{
        "hike_id": "hike-1",
        "route_segments": [[{"lat": 28.1, "lng": -82.1}, {"lat": 28.2, "lng": -82.2}]],
    }]


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
    assert get_hike_route("everyday") == {
        "route_segments": [],
        "started_at": None,
        "duration_seconds": None,
        "distance_miles": None,
        "track_point_count": 0,
    }


def test_hike_route_includes_recording_metadata(monkeypatch):
    class Repository:
        def get_hike_route_import(self, hike_id):
            assert hike_id == "hike-1"
            return {
                "started_at": "2026-07-31T13:00:00+00:00",
                "duration_seconds": 3723,
                "distance_miles": 4.625,
                "track_point_count": 42,
                "track_geojson": {
                    "type": "MultiLineString",
                    "coordinates": [
                        [[-82.1, 28.1], [-82.2, 28.2]],
                        [[-82.3, 28.3], [-82.4, 28.4]],
                    ],
                },
            }

    service = type("Service", (), {"repository": Repository()})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._get_visible_hike", lambda *_args: {"id": "hike-1"})

    assert get_hike_route("hike-1") == {
        "route_segments": [
            [{"lat": 28.1, "lng": -82.1}, {"lat": 28.2, "lng": -82.2}],
            [{"lat": 28.3, "lng": -82.3}, {"lat": 28.4, "lng": -82.4}],
        ],
        "started_at": "2026-07-31T13:00:00+00:00",
        "duration_seconds": 3723,
        "distance_miles": 4.625,
        "track_point_count": 42,
    }


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
        captured["source_type"] = kwargs["source_type"]
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
    assert captured == {
        "name": "pine-loop.tcx.txt",
        "contents": b"<TrainingCenterDatabase/>",
        "source_type": None,
    }
    assert response.json() == {
        "route_segments": [[{"lat": 28.1, "lng": -82.1}, {"lat": 28.2, "lng": -82.2}]],
        "track_point_count": 2,
    }


def test_mobile_route_upload_accepts_native_android_and_ios_gps_sources(monkeypatch):
    class Repository:
        def get_hike_route_import(self, _hike_id):
            return None

    service = type("Service", (), {"repository": Repository(), "storage": object()})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._get_visible_hike", lambda *_args: {"id": "hike-1"})
    captured = {}

    def sync(**kwargs):
        captured["source_type"] = kwargs["source_type"]
        return {"track_point_count": 0, "track_geojson": {}}, None

    monkeypatch.setattr("mobile_api.sync_hike_route_import", sync)
    app.dependency_overrides[require_mobile_key] = lambda: None
    try:
        native_response = TestClient(app).post(
            "/v1/hikes/hike-1/route",
            files={"file": ("recording.tcx", b"<TrainingCenterDatabase/>", "application/xml")},
            data={"source_type": "hikejournal_android_gps"},
        )
        ios_response = TestClient(app).post(
            "/v1/hikes/hike-1/route",
            files={"file": ("recording.tcx", b"<TrainingCenterDatabase/>", "application/xml")},
            data={"source_type": "hikejournal_ios_gps"},
        )
        invalid_response = TestClient(app).post(
            "/v1/hikes/hike-1/route",
            files={"file": ("recording.tcx", b"<TrainingCenterDatabase/>", "application/xml")},
            data={"source_type": "other_gps_app"},
        )
    finally:
        app.dependency_overrides.pop(require_mobile_key, None)

    assert native_response.status_code == 201
    assert ios_response.status_code == 201
    assert captured == {"source_type": "hikejournal_ios_gps"}
    assert invalid_response.status_code == 422


def test_mobile_weather_endpoint_returns_persisted_summary(monkeypatch):
    service = type("Service", (), {"repository": object()})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr(
        "mobile_api._get_visible_hike",
        lambda *_args: {"id": "hike-1", "hike_date": "2026-08-09"},
    )
    monkeypatch.setattr(
        "mobile_api._enrich_weather_for_hike",
        lambda _service, hike, force=False: {
            "hike_id": hike["id"],
            "provider": "open-meteo",
            "condition_label": "Rain",
            "temperature_min_c": 25.0,
            "temperature_max_c": 29.0,
            "force": force,
        },
    )
    app.dependency_overrides[require_mobile_key] = lambda: None
    try:
        response = TestClient(app).post("/v1/hikes/hike-1/weather?force=true")
    finally:
        app.dependency_overrides.pop(require_mobile_key, None)

    assert response.status_code == 200
    assert response.json()["provider"] == "open-meteo"
    assert response.json()["force"] is True


def test_picker_metadata_fallback_parses_capture_time_and_coordinates():
    taken_at = _parse_picker_taken_at("2026-07-19T14:32:10Z")

    assert taken_at is not None
    assert taken_at.isoformat() == "2026-07-19T14:32:10+00:00"
    assert _validate_picker_coordinate(28.5, minimum=-90, maximum=90, label="latitude") == 28.5
    assert _validate_picker_coordinate(-81.25, minimum=-180, maximum=180, label="longitude") == -81.25


def test_picker_metadata_treats_missing_android_capture_time_as_absent():
    assert _parse_picker_taken_at("") is None
    assert _parse_picker_taken_at("null") is None


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
    monkeypatch.setattr(
        "mobile_api._user_context",
        lambda: {
            "mode": "google",
            "user_id": "11111111-1111-4111-8111-111111111111",
            "subject": "google-subject-1",
            "email": "hiker@example.com",
        },
    )
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
    assert repository.created["owner_user_id"] == "11111111-1111-4111-8111-111111111111"
    assert repository.created["owner_subject"] == "google-subject-1"
    assert repository.created["owner_email"] == "hiker@example.com"
    assert repository.created["exif_json"]["picker_taken_at"] == "2026-07-19T14:32:10+00:00"


def test_photo_upload_without_capture_time_or_gps_can_enter_review(monkeypatch):
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
            files={"file": ("trail.jpg", b"image-without-metadata", "image/jpeg")},
            data={"taken_at": "null", "queue_for_review": "true"},
        )
    finally:
        app.dependency_overrides.pop(require_mobile_key, None)

    assert response.status_code == 201
    assert repository.created["taken_at"] is None
    assert repository.created["lat"] is None
    assert repository.created["lng"] is None
    assert repository.created["processing_status"] == "in_review"


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
            "wikipedia_url": "https://en.wikipedia.org/wiki/Asclepias_humistrata",
            "wikipedia_summary": "Pinewoods milkweed is a flowering plant.",
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
    assert payload["wikipedia_summary"] == "Pinewoods milkweed is a flowering plant."


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


def test_mobile_review_batch_saves_one_shared_suggestion_for_a_group(monkeypatch):
    class Repository:
        def __init__(self):
            self.saved = []

        def list_photo_records_for_ids(self, photo_ids):
            return [photo for photo in photos if photo["id"] in photo_ids]

        def upsert_observation(self, _hike_id, photo_id, candidate, **_kwargs):
            self.saved.append((photo_id, candidate))
            return {"id": f"obs-{photo_id}", "photo_id": photo_id}

    class InatClient:
        def validate_credentials(self):
            return None

        def score_species_candidates(self, *, filename, **_kwargs):
            if filename == "photo-a.jpg":
                return [
                    SpeciesCandidate("Species 10", "Species testus 10", 0.76, 10, {}),
                    SpeciesCandidate("Species 20", "Species testus 20", 0.40, 20, {}),
                ], {}
            return [
                SpeciesCandidate("Species 20", "Species testus 20", 0.91, 20, {}),
                SpeciesCandidate("Species 10", "Species testus 10", 0.30, 10, {}),
            ], {}

    repository = Repository()

    class Storage:
        def __init__(self):
            self.downloaded = []

        def download_file(self, storage_path):
            self.downloaded.append(storage_path)
            return b"image"

    storage = Storage()
    service = type("Service", (), {"repository": repository, "storage": storage})()
    photos = [
        {"id": "photo-a", "hike_id": "hike-1", "storage_path": "photos/photo-a.jpg", "lat": 28.6, "lng": -81.1, "taken_at": "2026-08-05T10:00:00Z"},
        {"id": "photo-b", "hike_id": "hike-1", "storage_path": "photos/photo-b.jpg", "lat": 28.60001, "lng": -81.10001, "taken_at": "2026-08-05T10:01:00Z"},
    ]
    queue = [
        {"id": photo["id"], "photo": photo, "candidates": []}
        for photo in photos
    ]
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._mobile_inat_client", lambda: InatClient())
    monkeypatch.setattr("mobile_api._review_queue_payload", lambda _service: queue)
    monkeypatch.setattr("mobile_api.ensure_observation_taxonomy", lambda *_args: None)

    result = request_species_batch_recommendation(
        ReviewBatchInput(
            groups=[ReviewBatchGroupInput(photo_ids=["photo-a", "photo-b"])]
        )
    )

    assert result["processed_photo_ids"] == ["photo-a", "photo-b"]
    assert result["grouped_count"] == 1
    assert result["individual_count"] == 0
    assert [candidate.taxon_id for _photo_id, candidate in repository.saved] == [20, 20]
    assert all(candidate.raw_payload["grouped_cv"] for _photo_id, candidate in repository.saved)
    assert storage.downloaded == ["photos/photo-a.jpg", "photos/photo-b.jpg"]


def test_mobile_review_batch_status_reports_completion_after_background_work(monkeypatch):
    class Repository:
        def list_photo_records_for_ids(self, photo_ids):
            return [
                {
                    "id": photo_id,
                    "hike_id": "hike-1",
                    "storage_path": f"photos/{photo_id}.jpg",
                    "lat": 28.6,
                    "lng": -81.1,
                    "taken_at": "2026-08-05T10:00:00Z",
                }
                for photo_id in photo_ids
            ]

        def upsert_observation(self, _hike_id, photo_id, _candidate, **_kwargs):
            return {"id": f"obs-{photo_id}", "photo_id": photo_id}

    class Storage:
        def download_file(self, _storage_path):
            return b"image"

    class InatClient:
        def validate_credentials(self):
            return None

        def identify_species(self, **_kwargs):
            return SpeciesCandidate("Species", "Species testus", 0.8, 10, {})

    repository = Repository()
    service = type("Service", (), {"repository": repository, "storage": Storage()})()
    queue = [
        {"id": "photo-a", "photo": {"id": "photo-a"}, "candidates": []},
        {"id": "photo-b", "photo": {"id": "photo-b"}, "candidates": []},
    ]
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._mobile_inat_client", lambda: InatClient())
    monkeypatch.setattr("mobile_api._review_queue_payload", lambda _service: queue)
    monkeypatch.setattr("mobile_api.ensure_observation_taxonomy", lambda *_args: None)

    tasks = BackgroundTasks()
    job = start_species_batch_recommendation(
        ReviewBatchInput(
            groups=[
                ReviewBatchGroupInput(photo_ids=["photo-a"]),
                ReviewBatchGroupInput(photo_ids=["photo-b"]),
            ]
        ),
        tasks,
    )

    assert job["state"] == "queued"
    assert job["total_photos"] == 2
    asyncio.run(tasks())

    status = get_species_batch_recommendation_status(job["job_id"])
    assert status["state"] == "completed"
    assert status["processed_photo_ids"] == ["photo-a", "photo-b"]
    assert status["current_photo_number"] == 2


def test_mobile_review_batch_skips_one_bad_photo_and_continues(monkeypatch):
    class Repository:
        def __init__(self):
            self.saved = []

        def list_photo_records_for_ids(self, photo_ids):
            return [
                {
                    "id": photo_id,
                    "hike_id": "hike-1",
                    "storage_path": f"photos/{photo_id}.jpg",
                }
                for photo_id in photo_ids
            ]

        def upsert_observation(self, _hike_id, photo_id, candidate, **_kwargs):
            self.saved.append((photo_id, candidate))
            return {"id": f"obs-{photo_id}", "photo_id": photo_id}

    class Storage:
        def download_file(self, _storage_path):
            return b"image"

    class InatClient:
        def validate_credentials(self):
            return None

        def identify_species(self, *, filename, **_kwargs):
            if filename == "photo-a.jpg":
                raise InatRequestError("no usable suggestion")
            return SpeciesCandidate("Species", "Species testus", 0.8, 10, {})

    repository = Repository()
    service = type("Service", (), {"repository": repository, "storage": Storage()})()
    queue = [
        {"id": photo_id, "photo": {"id": photo_id}, "candidates": []}
        for photo_id in ("photo-a", "photo-b")
    ]
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._mobile_inat_client", lambda: InatClient())
    monkeypatch.setattr("mobile_api._review_queue_payload", lambda _service: queue)
    monkeypatch.setattr("mobile_api.ensure_observation_taxonomy", lambda *_args: None)

    result = request_species_batch_recommendation(
        ReviewBatchInput(
            groups=[
                ReviewBatchGroupInput(photo_ids=["photo-a"]),
                ReviewBatchGroupInput(photo_ids=["photo-b"]),
            ]
        )
    )

    assert result["processed_photo_ids"] == ["photo-b"]
    assert [photo_id for photo_id, _candidate in repository.saved] == ["photo-b"]
    assert result["warnings"] == ["photo-a: no usable suggestion"]


@pytest.mark.parametrize(
    ("path", "expected_detail"),
    [
        (
            "/v1/species/review/batch-recommendation/not-a-uuid",
            "Species identification batch not found.",
        ),
        (
            "/v1/species/publish/batch/not-a-uuid",
            "iNaturalist publish batch not found.",
        ),
    ],
)
def test_malformed_job_status_id_returns_404_without_querying_durable_uuid_store(
    monkeypatch,
    path,
    expected_detail,
):
    class GuardStore(mobile_api.InMemoryMobileJobStore):
        def get(self, _job_id):
            raise AssertionError("a malformed UUID must not reach durable lookup")

        def list_recoverable(self, *, job_types=None):
            raise AssertionError("a single status lookup must not scan the queue")

    monkeypatch.setattr(mobile_api, "services", None)
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", GuardStore())
    monkeypatch.setattr(mobile_api, "_species_batch_jobs", {})
    monkeypatch.setattr(mobile_api, "_species_publish_jobs", {})
    app.dependency_overrides[require_mobile_key] = lambda: None
    try:
        response = TestClient(app).get(path)
    finally:
        app.dependency_overrides.pop(require_mobile_key, None)

    assert response.status_code == 404
    assert response.json() == {"detail": expected_detail}


def test_legacy_process_local_status_id_remains_pollable(monkeypatch):
    owner = {"subject": "subject-1", "email": "owner@example.com"}
    cached = {
        "job_id": "legacy-job-1",
        "state": "running",
        "processed_photo_ids": [],
        "warnings": [],
        "items": [],
        "owner_context": owner,
    }
    monkeypatch.setattr(mobile_api, "services", None)
    monkeypatch.setattr(mobile_api, "_species_batch_jobs", {"legacy-job-1": cached})
    monkeypatch.setattr(mobile_api, "_user_context", lambda: owner)

    status = get_species_batch_recommendation_status("legacy-job-1")

    assert status["job_id"] == "legacy-job-1"
    assert status["state"] == "running"


def test_mobile_review_batch_start_reuses_a_client_request_after_a_lost_response(monkeypatch):
    owner = {"subject": "subject-1", "email": "owner@example.com"}
    existing = {
        "job_id": "job-1",
        "state": "running",
        "total_photos": 2,
        "processed_count": 1,
        "processed_photo_ids": ["photo-a"],
        "current_photo_number": 2,
        "current_photo_id": "photo-b",
        "total_groups": 2,
        "current_group": 2,
        "grouped_count": 0,
        "individual_count": 1,
        "warnings": [],
        "error": None,
        "items": [],
        "owner_context": owner,
        "client_request_id": "request-1",
    }
    monkeypatch.setattr("mobile_api._user_context", lambda: owner)
    monkeypatch.setattr("mobile_api._species_batch_jobs", {"job-1": existing})

    result = start_species_batch_recommendation(
        ReviewBatchInput(
            groups=[ReviewBatchGroupInput(photo_ids=["photo-a"])],
            client_request_id="request-1",
        ),
        BackgroundTasks(),
    )

    assert result["job_id"] == "job-1"
    assert result["state"] == "running"
    assert "owner_context" not in result
    assert "client_request_id" not in result


def test_mobile_publish_batch_status_reports_each_group_after_background_work(monkeypatch):
    observations = [
        {
            "id": "observation-a",
            "photo_id": "photo-a",
            "status": "confirmed",
            "taxon_id": 10,
            "common_name": "Species",
            "scientific_name": "Species testus",
        },
        {
            "id": "observation-b",
            "photo_id": "photo-b",
            "status": "confirmed",
            "taxon_id": 10,
            "common_name": "Species",
            "scientific_name": "Species testus",
        },
    ]
    photos = [
        {
            "id": "photo-a",
            "hike_id": "hike-1",
            "lat": 28.6,
            "lng": -81.1,
            "taken_at": "2026-08-05T10:00:00Z",
            "public_url": "https://images.example/a.jpg",
        },
        {
            "id": "photo-b",
            "hike_id": "hike-1",
            "lat": 28.60001,
            "lng": -81.10001,
            "taken_at": "2026-08-05T10:01:00Z",
            "public_url": "https://images.example/b.jpg",
        },
    ]

    class Repository:
        def list_observations_by_ids(self, observation_ids):
            return [observation for observation in observations if observation["id"] in observation_ids]

    class InatClient:
        is_configured = True

    service = type("Service", (), {"repository": Repository()})()
    calls = []

    def fake_publish(_repository, _inat_client, records, **_kwargs):
        calls.append([observation["id"] for observation, _photo in records])
        return {"observation_id": 123, "photo_attached": True}

    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._visible_species_data", lambda _service: (observations, {photo["id"]: photo for photo in photos}, {"hike-1": {"id": "hike-1", "location_name": "Pine Loop"}}))
    monkeypatch.setattr("mobile_api._visible_hikes", lambda _repository: [{"id": "hike-1", "location_name": "Pine Loop"}])
    monkeypatch.setattr("mobile_api._mobile_inat_client", lambda: InatClient())
    monkeypatch.setattr("mobile_api.publish_observation_group", fake_publish)

    payload = PublishBatchInput(
        acknowledged_public=True,
        groups=[
            PublishBatchGroupInput(observation_ids=["observation-a"]),
            PublishBatchGroupInput(observation_ids=["observation-b"]),
        ],
        client_request_id="publish-request-1",
    )
    tasks = BackgroundTasks()
    job = start_species_publish_batch(payload, tasks)

    assert job["state"] == "queued"
    assert job["total_groups"] == 2
    assert job["total_photos"] == 2
    retry_tasks = BackgroundTasks()
    retry_job = start_species_publish_batch(payload, retry_tasks)
    assert retry_job["job_id"] == job["job_id"]
    assert retry_tasks.tasks == []
    asyncio.run(tasks())

    status = get_species_publish_batch_status(job["job_id"])
    assert status["state"] == "completed"
    assert status["posted_group_count"] == 2
    assert status["processed_photo_count"] == 2
    assert status["processed_observation_ids"] == ["observation-a", "observation-b"]
    assert calls == [["observation-a"], ["observation-b"]]


def test_inaturalist_publish_loader_reads_private_storage_directly() -> None:
    class Storage:
        def __init__(self):
            self.downloaded = []

        def download_file(self, storage_path):
            self.downloaded.append(storage_path)
            return b"private-image"

    storage = Storage()
    service = type("Service", (), {"storage": storage})()
    records = [
        (
            {"id": "observation-a"},
            {
                "id": "photo-a",
                "public_url": "https://signed.example/photo-a.jpg?token=test",
                "storage_path": "hikes/hike-1/photo-a.jpg",
            },
        )
    ]

    loader = mobile_api._stored_media_image_loader(service, records)

    assert loader is not None
    assert loader(records[0][1]["public_url"]) == b"private-image"
    assert storage.downloaded == ["hikes/hike-1/photo-a.jpg"]


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
            if observation_ids == ["observation-source"]:
                return [{"raw_response_json": {"taxon_enrichment": {"rank": "species"}}}]
            assert observation_ids == ["observation-new"]
            return [{**self.created, "id": "observation-new", "raw_response_json": self.created["raw_payload"]}]

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
    monkeypatch.setattr("mobile_api.ensure_observation_taxonomy", lambda *_args: True)
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


def test_explicit_hike_cover_never_falls_back_to_a_different_photo():
    payload = _hike_payload(
        {"id": "hike-1", "cover_photo_id": "selected-photo"},
        photos=[
            {
                "id": "latest-photo",
                "public_url": "https://img/latest.jpg",
                "taken_at": "2026-08-10T12:00:00Z",
            }
        ],
    )

    assert payload["cover_photo_id"] == "selected-photo"
    assert payload["cover_url"] == ""


def test_lightweight_hike_header_resolves_the_selected_cover(monkeypatch):
    hike_id = "11111111-1111-4111-8111-111111111111"
    photo_id = "22222222-2222-4222-8222-222222222222"

    class Repository:
        def list_photo_records_for_ids(self, photo_ids):
            assert photo_ids == [photo_id]
            return [{"id": photo_id, "hike_id": hike_id, "public_url": "https://img/selected.jpg"}]

        def get_hike_route_import(self, _hike_id):
            return None

        def list_field_marks(self, _hike_id):
            return []

        def get_hike_weather_snapshot(self, _hike_id):
            return None

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr(
        "mobile_api._get_visible_hike",
        lambda _repository, _hike_id: {"id": hike_id, "cover_photo_id": photo_id},
    )

    payload = get_hike(hike_id, include_photos=False, include_route=False)

    assert payload["cover_photo_id"] == photo_id
    assert payload["cover_url"] == "https://img/selected.jpg"


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


def test_place_profile_endpoint_allows_planning_before_a_recorded_visit(monkeypatch):
    repository = type(
        "Repository",
        (),
        {
            "get_hike_location": lambda _self, _location_id: {
                "id": "area-1",
                "name": "Unvisited Preserve",
                "lat": 28.1,
                "lng": -81.2,
            },
            "list_hike_locations": lambda _self: [
                {
                    "id": "area-1",
                    "name": "Unvisited Preserve",
                    "lat": 28.1,
                    "lng": -81.2,
                }
            ],
        },
    )()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr("mobile_api._place_profile_data", lambda _service, _location_id: ([], []))

    result = get_place_profile("area-1")

    assert result["summary"]["outing_count"] == 0
    assert result["location"]["lat"] == 28.1
    assert result["visits"] == []


def test_place_profile_keeps_archived_outings_in_the_historical_record(monkeypatch):
    class Repository:
        def get_hike_location(self, _location_id):
            return {
                "id": "area-1",
                "name": "Oak Flat",
                "lat": 28.1,
                "lng": -81.2,
            }

        def list_hike_locations(self):
            return [self.get_hike_location("area-1")]

        def list_hike_route_imports(self):
            return []

        def list_photos(self, _hike_id):
            return []

    repository = Repository()
    service = type("Service", (), {"repository": repository})()
    monkeypatch.setattr("mobile_api.get_services", lambda: service)
    monkeypatch.setattr(
        "mobile_api._visible_hikes",
        lambda _repository: [
            {
                "id": "hike-archived",
                "title": "Earlier visit",
                "hike_date": "2025-08-01",
                "distance_miles": 3.2,
                "is_archived": True,
                "location_tags": [{"id": "area-1"}],
            }
        ],
    )
    monkeypatch.setattr("mobile_api._dated_visible_observations", lambda _service: [])

    result = get_place_profile("area-1")

    assert result["summary"]["outing_count"] == 1
    assert result["visits"][0]["hike_id"] == "hike-archived"


def test_place_profile_data_scopes_reads_to_selected_place(monkeypatch):
    calls = []

    class Repository:
        def list_hike_location_tags_for_location(self, location_id):
            calls.append(("tags", location_id))
            return [{"hike_id": "hike-1"}]

        def list_hikes_by_ids(self, hike_ids):
            calls.append(("hikes", hike_ids))
            return [{"id": "hike-1", "title": "Oak Flat", "hike_date": "2026-08-16"}]

        def list_hike_route_imports(self):
            calls.append(("routes",))
            return []

        def list_photos_for_hike_ids(self, hike_ids):
            calls.append(("photos", hike_ids))
            return [{"id": "photo-1", "hike_id": "hike-1", "public_url": "cover.jpg"}]

        def list_lightweight_observations(self, *, hike_ids, status):
            calls.append(("observations", hike_ids, status))
            return [{
                "id": "observation-1",
                "hike_id": "hike-1",
                "photo_id": "photo-1",
                "status": "confirmed",
                "taxon_id": 1,
                "common_name": "Oak",
                "scientific_name": "Quercus alba",
                "iconic_taxon_name": "Plantae",
            }]

    monkeypatch.setattr(
        "mobile_api._user_context",
        lambda: {"mode": "local-dev", "subject": None, "email": None},
    )

    hikes, observations = mobile_api._place_profile_data(
        type("Service", (), {"repository": Repository()})(),
        "place-1",
    )

    assert [hike["id"] for hike in hikes] == ["hike-1"]
    assert observations[0]["reference_photo_url"] == "cover.jpg"
    assert calls == [
        ("tags", "place-1"),
        ("hikes", ["hike-1"]),
        ("routes",),
        ("photos", ["hike-1"]),
        ("observations", ["hike-1"], "confirmed"),
    ]


def test_native_hike_locations_returns_imported_library(monkeypatch):
    repository = type(
        "Repository",
        (),
        {
            "list_hike_locations": lambda _self: [
                {
                    "id": "location-1",
                    "name": "Alafia Scrub Preserve",
                    "lat": 27.8609,
                    "lng": -82.3359,
                },
                {"id": "", "name": "Ignored"},
            ]
        },
    )()
    monkeypatch.setattr(
        "mobile_api.get_services",
        lambda: type("Service", (), {"repository": repository})(),
    )

    assert list_hike_locations() == [
        {
            "id": "location-1",
            "name": "Alafia Scrub Preserve",
            "lat": 27.8609,
            "lng": -82.3359,
        },
    ]


def test_native_hike_locations_returns_selected_state_and_personal_places(monkeypatch):
    repository = type(
        "Repository",
        (),
        {
            "list_hike_locations": lambda _self: [
                {
                    "id": "florida-1",
                    "name": "Florida Trail",
                    "state": "FL",
                    "lat": 28.0,
                    "lng": -82.0,
                },
                {
                    "id": "maine-1",
                    "name": "Acadia Loop",
                    "state": "ME",
                    "lat": 44.0,
                    "lng": -68.0,
                },
                {
                    "id": "personal-1",
                    "name": "Family Woods",
                    "owner_subject": "person-1",
                    "lat": 43.0,
                    "lng": -70.0,
                },
            ]
        },
    )()
    monkeypatch.setattr(
        "mobile_api.get_services",
        lambda: type("Service", (), {"repository": repository})(),
    )
    monkeypatch.setattr(
        "mobile_api._user_context",
        lambda: {"mode": "google", "subject": "person-1", "email": "hiker@example.com"},
    )

    assert list_hike_locations("me") == [
        {
            "id": "maine-1",
            "name": "Acadia Loop",
            "lat": 44.0,
            "lng": -68.0,
            "state": "ME",
        },
        {
            "id": "personal-1",
            "name": "Family Woods",
            "lat": 43.0,
            "lng": -70.0,
            "is_user_place": True,
        },
    ]


def test_native_hike_locations_rejects_non_state_code():
    with pytest.raises(HTTPException) as error:
        list_hike_locations("XX")

    assert error.value.status_code == 422


def test_create_hike_correlates_selected_imported_location(monkeypatch):
    location_id = "22222222-2222-4222-8222-222222222222"

    class Repository:
        location_tags = None
        created_draft = None

        def create_hike(self, draft, hike_id=None):
            assert draft.location_name == "Alafia Scrub Preserve"
            self.created_draft = draft
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
        lambda: {
            "mode": "google",
            "user_id": "11111111-1111-4111-8111-111111111111",
            "subject": "google-subject-1",
            "email": "hiker@example.com",
        },
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
    assert repository.created_draft.owner_user_id == "11111111-1111-4111-8111-111111111111"
    assert repository.created_draft.owner_subject == "google-subject-1"
    assert repository.created_draft.owner_email == "hiker@example.com"
    assert mobile_api.EXISTING_MOBILE_ENTITLEMENT_ENFORCEMENT_ENABLED is False


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

        def resolve_area(self, _repository, area_id, *, locations=None):
            assert area_id == "area-1"
            assert locations == [{"id": "area-1", "name": "Wetland", "lat": 28.1, "lng": -82.2}]
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


def test_mobile_recommendation_starts_review_for_an_unqueued_photo(monkeypatch):
    class Repository:
        def __init__(self):
            self.status_updates = []

        def update_photo_processing_status(self, photo_id, status):
            self.status_updates.append((photo_id, status))

        def upsert_observation(self, *_args, **_kwargs):
            return None

    repository = Repository()
    service = type("Service", (), {"repository": repository, "storage": object()})()
    photo = {"id": "photo-2", "hike_id": "everyday", "processing_status": "ready"}
    candidate = SpeciesCandidate(
        taxon_id=42,
        common_name="Gopher Tortoise",
        scientific_name="Gopherus polyphemus",
        confidence=0.91,
        raw_payload={},
    )

    class InatClient:
        def score_species_candidates(self, **_kwargs):
            return [candidate], {"results": []}

    monkeypatch.setattr("mobile_api._get_visible_photo", lambda _photo_id: (service, photo))
    monkeypatch.setattr("mobile_api._download_photo_for_cv", lambda _svc, _photo: b"field-photo")
    monkeypatch.setattr("mobile_api._mobile_inat_client", InatClient)
    monkeypatch.setattr("mobile_api._review_queue_payload", lambda _service: [{"id": "photo-2"}])

    assert request_species_recommendation("photo-2")["id"] == "photo-2"
    assert repository.status_updates == [("photo-2", "in_review")]
