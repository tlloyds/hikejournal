from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

import pytest
from starlette.requests import Request

import mobile_api
from hike_journal.services.mobile_auth import (
    MobileAuthError,
    _access_token,
    delete_mobile_account,
    mobile_auth_configuration_errors,
    verify_access_token,
    verify_google_credential,
)


def test_google_credential_requires_verified_identity_and_matching_nonce(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_WEB_CLIENT_ID", "web-client.apps.googleusercontent.com")

    identity = verify_google_credential(
        "signed-google-id-token",
        expected_nonce="device-nonce",
        verifier=lambda credential, _request, audience: {
            "sub": "google-subject-1",
            "email": "Hiker@Example.com",
            "email_verified": True,
            "iss": "https://accounts.google.com",
            "aud": audience,
            "nonce": "device-nonce",
            "name": "Trail Hiker",
        },
    )

    assert identity == {
        "subject": "google-subject-1",
        "email": "hiker@example.com",
        "display_name": "Trail Hiker",
        "picture_url": "",
    }

    with pytest.raises(MobileAuthError, match="matched"):
        verify_google_credential(
            "signed-google-id-token",
            expected_nonce="different-nonce",
            verifier=lambda *_args: {
                "sub": "google-subject-1",
                "email": "hiker@example.com",
                "email_verified": True,
                "iss": "accounts.google.com",
                "nonce": "device-nonce",
            },
        )


def test_hikejournal_access_token_round_trips_owner_context(monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_SESSION_SECRET", "a-high-entropy-mobile-session-secret-0123456789")
    token, expires_in = _access_token(
        {
            "google_subject": "google-subject-1",
            "email": "hiker@example.com",
            "display_name": "Trail Hiker",
            "picture_url": None,
        },
        now=datetime.now(UTC),
    )

    assert expires_in == 1_200
    assert verify_access_token(token) == {
        "mode": "google",
        "email": "hiker@example.com",
        "subject": "google-subject-1",
        "display_name": "Trail Hiker",
        "picture_url": "",
        "auth_configured": True,
        "is_logged_in": True,
    }


def test_google_mode_rejects_weak_hosted_configuration(monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_AUTH_MODE", "google")
    monkeypatch.setenv("GOOGLE_WEB_CLIENT_ID", "not-a-google-client")
    monkeypatch.setenv("MOBILE_SESSION_SECRET", "short")

    assert mobile_auth_configuration_errors() == [
        "GOOGLE_WEB_CLIENT_ID must identify the Google OAuth web client",
        "MOBILE_SESSION_SECRET must be a high-entropy value of at least 32 characters",
    ]


def test_google_bearer_dependency_populates_request_owner(monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_AUTH_MODE", "google")
    monkeypatch.setenv("MOBILE_SESSION_SECRET", "a-high-entropy-mobile-session-secret-0123456789")
    token, _ = _access_token(
        {
            "google_subject": "google-subject-2",
            "email": "second@example.com",
            "display_name": "Second Hiker",
        },
        now=datetime.now(UTC),
    )
    request = Request({"type": "http", "method": "GET", "path": "/v1/hikes", "headers": []})

    async def authenticated_subject() -> str | None:
        await mobile_api.require_mobile_key(request, authorization=f"Bearer {token}")
        return mobile_api._user_context()["subject"]

    assert asyncio.run(authenticated_subject()) == "google-subject-2"


def test_account_deletion_uses_server_only_rpc() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    class Result:
        def execute(self):
            return self

    class Client:
        def rpc(self, name, payload):
            calls.append((name, payload))
            return Result()

    delete_mobile_account(Client(), google_subject=" google-subject-3 ")

    assert calls == [
        ("delete_hikejournal_account", {"p_google_subject": "google-subject-3"})
    ]


def test_place_library_includes_shared_and_current_users_places_only(monkeypatch) -> None:
    class Repository:
        def list_hike_locations(self):
            return [
                {"id": "florida", "name": "Shared Florida Place"},
                {"id": "mine", "name": "My Place", "owner_subject": "google-subject-1"},
                {"id": "theirs", "name": "Their Place", "owner_subject": "google-subject-2"},
            ]

    monkeypatch.setattr(
        mobile_api,
        "_user_context",
        lambda: {"mode": "google", "subject": "google-subject-1", "email": "hiker@example.com"},
    )

    assert [item["id"] for item in mobile_api._visible_hike_locations(Repository())] == [
        "florida",
        "mine",
    ]


def test_field_briefing_fetches_the_selected_life_group(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Repository:
        def list_hike_locations(self):
            return [{"id": "chuluota", "name": "Chuluota Wilderness Area", "lat": 28.63, "lng": -81.12}]

        def list_species_quests(self, **_kwargs):
            return []

    class Discovery:
        def __init__(self, _repository):
            pass

        @staticmethod
        def resolve_area(_repository, area_id, *, locations):
            assert area_id == "chuluota"
            return locations[0]

        def nearby(self, **kwargs):
            captured.update(kwargs)
            return {
                "area": kwargs["area"],
                "period": {"label": "August"},
                "source": {"provider": "iNaturalist"},
                "taxa": [{"taxon_id": 1, "iconic_taxon_name": "Plantae"}],
            }

    service = type("Services", (), {"repository": Repository()})()
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(mobile_api, "SpeciesDiscoveryService", Discovery)
    monkeypatch.setattr(mobile_api, "_require_discovery_enabled", lambda: None)
    monkeypatch.setattr(mobile_api, "_discovery_collection_data", lambda _svc: ([], {}))
    monkeypatch.setattr(mobile_api, "_visible_hikes", lambda _repository: [])
    monkeypatch.setattr(mobile_api, "_dated_visible_observations", lambda _svc: [])
    monkeypatch.setattr(mobile_api, "_user_context", lambda: {"subject": "google-subject-1", "email": "hiker@example.com"})
    monkeypatch.setattr(
        mobile_api,
        "build_field_briefing",
        lambda **_kwargs: {"sections": [{"title": "Plants", "items": []}]},
    )

    payload = mobile_api.get_field_briefing(
        location_id="chuluota",
        target_date=date(2026, 8, 18),
        radius_km=10,
        iconic_taxon="Plantae",
        limit=18,
    )

    assert captured["iconic_taxon"] == "Plantae"
    assert captured["limit"] == 50
    assert payload["sections"][0]["title"] == "Plants"
