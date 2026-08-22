from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import mobile_api
from hike_journal.services.entitlements import (
    ClientPlatform,
    DEFAULT_ENTITLEMENT_POLICY,
    EntitlementSnapshot,
    EntitlementStoreError,
    EntitlementUsage,
    Plan,
    QuotaResource,
    resolve_entitlement,
)


USER_ID = "11111111-1111-4111-8111-111111111111"


class _Snapshot:
    def __init__(self, payload):
        self.payload = payload

    def to_payload(self):
        return self.payload


def _authenticated_context(**overrides):
    context = {
        "mode": "google",
        "identity_provider": "google",
        "user_id": USER_ID,
        "subject": "google-subject-1",
        "email": "hiker@example.com",
        "auth_configured": True,
    }
    context.update(overrides)
    return context


def test_services_wires_entitlement_service_to_the_shared_server_client(monkeypatch) -> None:
    shared_client = object()
    store_calls = []
    entitlement_service = object()
    storage = SimpleNamespace(resolve_download_url=lambda path: path)

    monkeypatch.setattr(
        mobile_api,
        "settings",
        SimpleNamespace(
            supabase_configured=True,
            supabase_url="https://database.example",
            supabase_key="server-key",
        ),
    )
    monkeypatch.setattr(mobile_api, "create_client", lambda *_args: shared_client)
    monkeypatch.setattr(mobile_api, "StorageService", lambda client: storage)
    monkeypatch.setattr(mobile_api, "HikeJournalRepository", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(mobile_api, "build_mobile_job_store", lambda _client: object())
    monkeypatch.setattr(
        mobile_api,
        "SupabaseEntitlementStore",
        lambda client: store_calls.append(client) or "entitlement-store",
    )
    monkeypatch.setattr(
        mobile_api,
        "EntitlementService",
        lambda store: entitlement_service if store == "entitlement-store" else None,
    )

    services = mobile_api.Services()

    assert store_calls == [shared_client]
    assert services.entitlements is entitlement_service


def test_entitlement_endpoint_uses_canonical_account_and_ignores_platform_claims(monkeypatch) -> None:
    expected = {
        "plan": "free",
        "source": "free",
        "status": "active",
        "limits": {"cloud_hikes": 3, "cloud_media": 50},
        "usage": {"cloud_hikes": 1, "cloud_media": 2},
        "features": {"gps_recording": True, "field_briefing": False},
    }

    class Entitlements:
        seen_user_ids = []

        def snapshot(self, user_id):
            self.seen_user_ids.append(user_id)
            return _Snapshot(expected)

    entitlements = Entitlements()
    service = SimpleNamespace(entitlements=entitlements, client=object())
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(mobile_api, "_user_context", _authenticated_context)
    mobile_api.app.dependency_overrides[mobile_api.require_mobile_key] = lambda: None
    try:
        response = TestClient(mobile_api.app).get(
            "/v1/me/entitlement?platform=android",
            headers={"X-HikeJournal-Platform": "android"},
        )
    finally:
        mobile_api.app.dependency_overrides.pop(mobile_api.require_mobile_key, None)

    assert response.status_code == 200
    assert response.json() == expected
    assert entitlements.seen_user_ids == [USER_ID]


def test_entitlement_endpoint_keeps_old_google_tokens_compatible_by_subject(monkeypatch) -> None:
    class Query:
        def select(self, columns):
            assert columns == "id"
            return self

        def eq(self, column, value):
            assert (column, value) == ("google_subject", "legacy-google-subject")
            return self

        def limit(self, value):
            assert value == 1
            return self

        @staticmethod
        def execute():
            return SimpleNamespace(data=[{"id": USER_ID}])

    class Client:
        @staticmethod
        def table(name):
            assert name == "app_users"
            return Query()

    class Entitlements:
        seen_user_id = None

        def snapshot(self, user_id):
            self.seen_user_id = user_id
            return _Snapshot({"plan": "lifetime"})

    entitlements = Entitlements()
    service = SimpleNamespace(client=Client(), entitlements=entitlements)
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(
        mobile_api,
        "_user_context",
        lambda: {
            "mode": "google",
            "subject": "legacy-google-subject",
            "email": "legacy@example.com",
            "auth_configured": True,
        },
    )
    mobile_api.app.dependency_overrides[mobile_api.require_mobile_key] = lambda: None
    try:
        response = TestClient(mobile_api.app).get("/v1/me/entitlement")
    finally:
        mobile_api.app.dependency_overrides.pop(mobile_api.require_mobile_key, None)

    assert response.status_code == 200
    assert response.json() == {"plan": "lifetime"}
    assert entitlements.seen_user_id == USER_ID


def test_entitlement_identity_resolution_never_falls_back_from_apple_to_email() -> None:
    class Client:
        @staticmethod
        def table(_name):
            raise AssertionError("Apple must not query a Google shadow or email fallback")

    with pytest.raises(HTTPException) as error:
        mobile_api.current_entitlement_user_id(
            SimpleNamespace(client=Client()),
            context=_authenticated_context(
                mode="apple",
                identity_provider="apple",
                user_id=None,
                subject="apple:subject-1",
            ),
        )

    assert error.value.status_code == 409


def test_entitlement_endpoint_fails_closed_when_the_store_is_unavailable(monkeypatch) -> None:
    class Entitlements:
        @staticmethod
        def snapshot(_user_id):
            raise EntitlementStoreError("Entitlement migration is not installed.")

    monkeypatch.setattr(
        mobile_api,
        "get_services",
        lambda: SimpleNamespace(client=object(), entitlements=Entitlements()),
    )
    monkeypatch.setattr(mobile_api, "_user_context", _authenticated_context)
    mobile_api.app.dependency_overrides[mobile_api.require_mobile_key] = lambda: None
    try:
        response = TestClient(mobile_api.app).get("/v1/me/entitlement")
    finally:
        mobile_api.app.dependency_overrides.pop(mobile_api.require_mobile_key, None)

    assert response.status_code == 503
    assert response.json()["detail"] == "Entitlement migration is not installed."


def test_reusable_quota_helpers_always_scope_calls_to_canonical_user(monkeypatch) -> None:
    calls = []

    class Entitlements:
        def reserve_quota(self, **kwargs):
            calls.append(("reserve", kwargs))
            return "reservation"

        def release_quota(self, **kwargs):
            calls.append(("release", kwargs))
            return True

    service = SimpleNamespace(client=object(), entitlements=Entitlements())
    monkeypatch.setattr(mobile_api, "_user_context", _authenticated_context)

    reservation = mobile_api.reserve_entitlement_quota(
        service,
        resource=QuotaResource.CLOUD_HIKES,
        request_id="request-1",
        resource_id="22222222-2222-4222-8222-222222222222",
        ttl_seconds=600,
    )
    released = mobile_api.release_entitlement_quota(
        service,
        resource=QuotaResource.CLOUD_HIKES,
        request_id="request-1",
    )

    assert reservation == "reservation"
    assert released is True
    assert calls == [
        (
            "reserve",
            {
                "user_id": USER_ID,
                "resource": QuotaResource.CLOUD_HIKES,
                "request_id": "request-1",
                "resource_id": "22222222-2222-4222-8222-222222222222",
                "ttl_seconds": 600,
            },
        ),
        (
            "release",
            {
                "user_id": USER_ID,
                "resource": QuotaResource.CLOUD_HIKES,
                "request_id": "request-1",
            },
        ),
    ]


def test_android_platform_value_alone_cannot_bypass_feature_decision(monkeypatch) -> None:
    entitlement = resolve_entitlement([])
    snapshot = EntitlementSnapshot(
        decision=entitlement,
        plan_policy=DEFAULT_ENTITLEMENT_POLICY.for_plan(Plan.FREE),
        policy=DEFAULT_ENTITLEMENT_POLICY,
        usage=EntitlementUsage(),
    )
    service = SimpleNamespace(
        client=object(),
        entitlements=SimpleNamespace(snapshot=lambda _user_id: snapshot),
    )
    monkeypatch.setattr(mobile_api, "_user_context", _authenticated_context)

    decision = mobile_api.entitlement_feature_decision(
        service,
        "field_briefing",
        server_platform=ClientPlatform.ANDROID,
    )

    assert decision.allowed is False
    assert decision.enforced is True
    assert decision.reason == "plus_required"
    assert mobile_api.EXISTING_MOBILE_ENTITLEMENT_ENFORCEMENT_ENABLED is False


def test_apple_and_entitlement_routes_are_additive_openapi_operations() -> None:
    paths = mobile_api.app.openapi()["paths"]

    assert "post" in paths["/v1/auth/apple"]
    assert "get" in paths["/v1/me/entitlement"]
