from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import mobile_api
from hike_journal.services.app_store_server import (
    AppStoreAccountLinkError,
    AppStoreConfigurationError,
    AppStoreNotificationNotLinked,
    AppStoreVerificationError,
    VerifiedAppleAppTransaction,
)
from hike_journal.services.entitlements import (
    APPLE_PLUS_MONTHLY_PRODUCT_ID,
    BillingPeriod,
    EntitlementProjection,
    EntitlementSource,
    EntitlementStatus,
    Plan,
)


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
USER_ID = "11111111-1111-4111-8111-111111111111"
TRANSACTION_JWS = "transaction.payload.signature"
RENEWAL_JWS = "renewal.payload.signature"
NOTIFICATION_JWS = "notification.payload.signature"
APP_TRANSACTION_JWS = "app-transaction.payload.signature"


class Snapshot:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def to_payload(self) -> dict[str, object]:
        return self.payload


class Entitlements:
    def __init__(
        self,
        *,
        snapshot: dict[str, object] | None = None,
        apply_results: list[dict[str, object]] | None = None,
    ) -> None:
        self.snapshot_payload = snapshot or {
            "plan": "plus",
            "source": "apple_subscription",
            "status": "active",
        }
        self.apply_results = list(apply_results or [{"applied": True}])
        self.applied: list[EntitlementProjection] = []
        self.snapshot_user_ids: list[str] = []

    def apply_projection(self, projection: EntitlementProjection) -> dict[str, object]:
        self.applied.append(projection)
        if self.apply_results:
            return self.apply_results.pop(0)
        return {"applied": True}

    def snapshot(self, user_id: str) -> Snapshot:
        self.snapshot_user_ids.append(user_id)
        return Snapshot(self.snapshot_payload)


def projection(
    status: EntitlementStatus = EntitlementStatus.ACTIVE,
    *,
    event_id: str = "notification-1",
) -> EntitlementProjection:
    return EntitlementProjection(
        user_id=USER_ID,
        source=EntitlementSource.APPLE_SUBSCRIPTION,
        external_event_id=event_id,
        external_entitlement_id="1000000000000001",
        event_type="DID_RENEW",
        occurred_at=NOW,
        plan=Plan.PLUS,
        status=status,
        product_id=APPLE_PLUS_MONTHLY_PRODUCT_ID,
        billing_period=BillingPeriod.MONTHLY,
        started_at=NOW - timedelta(days=30),
        expires_at=NOW + timedelta(days=30),
        grace_expires_at=(
            NOW + timedelta(days=3) if status is EntitlementStatus.GRACE else None
        ),
        refunded_at=(NOW if status is EntitlementStatus.REFUNDED else None),
        original_transaction_id="1000000000000001",
        environment="sandbox",
    )


class Verifier:
    def __init__(self) -> None:
        self.sync_projection = projection(event_id="transaction-sync-1")
        self.notification_projection: EntitlementProjection | None = projection()
        self.sync_error: Exception | None = None
        self.notification_error: Exception | None = None
        self.app_transaction_error: Exception | None = None
        self.calls: list[tuple[str, object]] = []

    def verify_and_project_transaction_for_account(
        self,
        signed_transaction: str,
        *,
        authenticated_user_id: str,
        signed_renewal_info: str | None = None,
    ) -> EntitlementProjection:
        self.calls.append(
            (
                "sync",
                (signed_transaction, authenticated_user_id, signed_renewal_info),
            )
        )
        if self.sync_error:
            raise self.sync_error
        return self.sync_projection

    def verify_resolve_and_project_notification(self, signed_payload: str, *, resolver):
        self.calls.append(("notification", (signed_payload, resolver)))
        if self.notification_error:
            raise self.notification_error
        return SimpleNamespace(
            envelope=SimpleNamespace(
                notification_uuid="10000000-0000-4000-8000-000000000001"
            ),
            projection=self.notification_projection,
        )

    def verify_app_transaction(self, signed_app_transaction: str):
        self.calls.append(("app_transaction", signed_app_transaction))
        if self.app_transaction_error:
            raise self.app_transaction_error
        return VerifiedAppleAppTransaction(
            app_transaction_id="app-transaction-1",
            app_apple_id=123456789,
            bundle_id="com.hikejournal.app",
            environment="Sandbox",
            application_version="42",
            original_application_version="1",
            receipt_created_at=NOW,
            original_purchased_at=NOW - timedelta(days=365),
            original_platform="iOS",
        )


def authenticated_context() -> dict[str, object]:
    return {
        "mode": "google",
        "identity_provider": "google",
        "user_id": USER_ID,
        "subject": "google-subject-1",
        "email": "hiker@example.com",
        "auth_configured": True,
    }


def service_container(
    entitlements: Entitlements | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        client=object(),
        entitlement_store=object(),
        entitlements=entitlements or Entitlements(),
    )


@pytest.fixture(autouse=True)
def clean_app_store_api_state():
    mobile_api.get_app_store_server_verifier.cache_clear()
    mobile_api.app.dependency_overrides.pop(mobile_api.require_mobile_key, None)
    yield
    mobile_api.get_app_store_server_verifier.cache_clear()
    mobile_api.app.dependency_overrides.pop(mobile_api.require_mobile_key, None)


def enable_authenticated_request(monkeypatch, service: SimpleNamespace) -> None:
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(mobile_api, "_user_context", authenticated_context)
    mobile_api.app.dependency_overrides[mobile_api.require_mobile_key] = lambda: None


def test_app_store_verifier_is_lazy_and_successfully_cached(monkeypatch) -> None:
    built = object()
    calls = []

    def build():
        calls.append("build")
        return built

    monkeypatch.setattr(
        mobile_api,
        "build_app_store_server_verifier_from_environment",
        build,
    )

    assert TestClient(mobile_api.app).get("/health/live").status_code == 200
    assert calls == []
    assert mobile_api.get_app_store_server_verifier() is built
    assert mobile_api.get_app_store_server_verifier() is built
    assert calls == ["build"]


@pytest.mark.parametrize(
    ("path", "body", "authenticated"),
    [
        (
            "/v1/storekit/transactions/sync",
            {"signedTransaction": TRANSACTION_JWS},
            True,
        ),
        (
            "/v1/app-store/notifications/v2",
            {"signedPayload": NOTIFICATION_JWS},
            False,
        ),
        (
            "/v1/storekit/app-transaction/verify",
            {"signedAppTransaction": APP_TRANSACTION_JWS},
            True,
        ),
    ],
)
def test_apple_endpoints_fail_closed_when_server_configuration_is_missing(
    monkeypatch,
    path: str,
    body: dict[str, str],
    authenticated: bool,
) -> None:
    service = service_container()
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(mobile_api, "_user_context", authenticated_context)
    if authenticated:
        mobile_api.app.dependency_overrides[mobile_api.require_mobile_key] = lambda: None

    def missing_configuration():
        raise AppStoreConfigurationError("missing backend secret")

    monkeypatch.setattr(
        mobile_api,
        "build_app_store_server_verifier_from_environment",
        missing_configuration,
    )

    response = TestClient(mobile_api.app).post(path, json=body)

    assert response.status_code == 503
    assert response.json() == {
        "detail": "App Store server verification is not configured."
    }
    assert "secret" not in response.text


def test_transaction_sync_forwards_renewal_links_canonical_user_and_returns_snapshot(
    monkeypatch,
) -> None:
    verifier = Verifier()
    entitlements = Entitlements(
        snapshot={
            "plan": "plus",
            "source": "apple_subscription",
            "billing_period": "monthly",
            "status": "active",
            "features": {"field_briefing": True},
        }
    )
    service = service_container(entitlements)
    enable_authenticated_request(monkeypatch, service)
    monkeypatch.setattr(
        mobile_api,
        "get_app_store_server_verifier",
        lambda: verifier,
    )

    response = TestClient(mobile_api.app).post(
        "/v1/storekit/transactions/sync",
        json={
            "signedTransaction": TRANSACTION_JWS,
            "signedRenewalInfo": RENEWAL_JWS,
        },
    )

    assert response.status_code == 200
    assert response.json() == entitlements.snapshot_payload
    assert verifier.calls == [
        ("sync", (TRANSACTION_JWS, USER_ID, RENEWAL_JWS))
    ]
    assert entitlements.applied == [verifier.sync_projection]
    assert entitlements.snapshot_user_ids == [USER_ID]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (AppStoreAccountLinkError("different account"), 409),
        (AppStoreVerificationError("invalid JWS"), 400),
    ],
)
def test_transaction_sync_rejects_account_mismatch_or_invalid_jws(
    monkeypatch,
    error: Exception,
    expected_status: int,
) -> None:
    verifier = Verifier()
    verifier.sync_error = error
    entitlements = Entitlements()
    enable_authenticated_request(monkeypatch, service_container(entitlements))
    monkeypatch.setattr(
        mobile_api,
        "get_app_store_server_verifier",
        lambda: verifier,
    )

    response = TestClient(mobile_api.app).post(
        "/v1/storekit/transactions/sync",
        json={"signedTransaction": TRANSACTION_JWS},
    )

    assert response.status_code == expected_status
    assert entitlements.applied == []
    assert entitlements.snapshot_user_ids == []


def test_storekit_request_models_are_bounded_and_reject_unmodeled_claims(
    monkeypatch,
) -> None:
    verifier = Verifier()
    enable_authenticated_request(monkeypatch, service_container())
    monkeypatch.setattr(
        mobile_api,
        "get_app_store_server_verifier",
        lambda: verifier,
    )
    client = TestClient(mobile_api.app)

    too_large = client.post(
        "/v1/storekit/transactions/sync",
        json={"signedTransaction": "a" * (mobile_api.MAX_SIGNED_DATA_LENGTH + 1)},
    )
    extra_claim = client.post(
        "/v1/storekit/transactions/sync",
        json={
            "signedTransaction": TRANSACTION_JWS,
            "isLifetimeOwner": True,
        },
    )

    assert too_large.status_code == 422
    assert extra_claim.status_code == 422
    assert verifier.calls == []


@pytest.mark.parametrize(
    "entitlement_status",
    [EntitlementStatus.GRACE, EntitlementStatus.REFUNDED],
)
def test_notification_endpoint_applies_verified_grace_and_refund_projections_without_auth(
    monkeypatch,
    entitlement_status: EntitlementStatus,
) -> None:
    verifier = Verifier()
    verifier.notification_projection = projection(entitlement_status)
    entitlements = Entitlements()
    service = service_container(entitlements)
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(
        mobile_api,
        "get_app_store_server_verifier",
        lambda: verifier,
    )

    response = TestClient(mobile_api.app).post(
        "/v1/app-store/notifications/v2",
        json={"signedPayload": NOTIFICATION_JWS},
    )

    assert response.status_code == 200
    assert response.json() == {
        "accepted": True,
        "notification_uuid": "10000000-0000-4000-8000-000000000001",
        "entitlement_event": "applied",
    }
    assert verifier.calls == [
        ("notification", (NOTIFICATION_JWS, service.entitlement_store))
    ]
    assert entitlements.applied[0].status is entitlement_status


def test_notification_replay_returns_minimal_idempotent_acknowledgements(
    monkeypatch,
) -> None:
    verifier = Verifier()
    entitlements = Entitlements(
        apply_results=[
            {"applied": True, "duplicate": False, "stale": False},
            {"applied": False, "duplicate": True, "stale": False},
        ]
    )
    service = service_container(entitlements)
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(
        mobile_api,
        "get_app_store_server_verifier",
        lambda: verifier,
    )
    client = TestClient(mobile_api.app)

    first = client.post(
        "/v1/app-store/notifications/v2",
        json={"signedPayload": NOTIFICATION_JWS},
    )
    replay = client.post(
        "/v1/app-store/notifications/v2",
        json={"signedPayload": NOTIFICATION_JWS},
    )

    assert first.json()["entitlement_event"] == "applied"
    assert replay.json()["entitlement_event"] == "duplicate"
    assert len(entitlements.applied) == 2
    assert "user_id" not in replay.json()
    assert "original_transaction_id" not in replay.json()


def test_unlinked_notification_returns_retry_safe_status_without_applying(
    monkeypatch,
) -> None:
    verifier = Verifier()
    verifier.notification_error = AppStoreNotificationNotLinked("sync race")
    entitlements = Entitlements()
    service = service_container(entitlements)
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(
        mobile_api,
        "get_app_store_server_verifier",
        lambda: verifier,
    )

    response = TestClient(mobile_api.app).post(
        "/v1/app-store/notifications/v2",
        json={"signedPayload": NOTIFICATION_JWS},
    )

    assert response.status_code == 503
    assert response.headers["retry-after"] == "60"
    assert entitlements.applied == []


def test_notification_accepts_only_signed_payload_and_rejects_invalid_jws(
    monkeypatch,
) -> None:
    verifier = Verifier()
    verifier.notification_error = AppStoreVerificationError("invalid JWS")
    service = service_container()
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(
        mobile_api,
        "get_app_store_server_verifier",
        lambda: verifier,
    )
    client = TestClient(mobile_api.app)

    invalid = client.post(
        "/v1/app-store/notifications/v2",
        json={"signedPayload": NOTIFICATION_JWS},
    )
    extra = client.post(
        "/v1/app-store/notifications/v2",
        json={"signedPayload": NOTIFICATION_JWS, "userId": USER_ID},
    )
    wrong_name = client.post(
        "/v1/app-store/notifications/v2",
        json={"signed_payload": NOTIFICATION_JWS},
    )

    assert invalid.status_code == 400
    assert extra.status_code == 422
    assert wrong_name.status_code == 422


def test_signed_app_transaction_endpoint_returns_evidence_without_entitlement_mutation(
    monkeypatch,
) -> None:
    verifier = Verifier()
    entitlements = Entitlements()
    enable_authenticated_request(monkeypatch, service_container(entitlements))
    monkeypatch.setattr(
        mobile_api,
        "get_app_store_server_verifier",
        lambda: verifier,
    )

    response = TestClient(mobile_api.app).post(
        "/v1/storekit/app-transaction/verify",
        json={"signedAppTransaction": APP_TRANSACTION_JWS},
    )

    assert response.status_code == 200
    assert response.json() == {
        "verified": True,
        "app_transaction_id": "app-transaction-1",
        "app_apple_id": 123456789,
        "bundle_id": "com.hikejournal.app",
        "environment": "Sandbox",
        "application_version": "42",
        "original_application_version": "1",
        "receipt_created_at": "2026-08-22T12:00:00+00:00",
        "original_purchased_at": "2025-08-22T12:00:00+00:00",
        "original_platform": "iOS",
    }
    assert entitlements.applied == []
    assert entitlements.snapshot_user_ids == []


def test_app_store_routes_are_additive_and_keep_legacy_manifest_at_59() -> None:
    paths = mobile_api.app.openapi()["paths"]

    assert "post" in paths["/v1/storekit/transactions/sync"]
    assert "post" in paths["/v1/app-store/notifications/v2"]
    assert "post" in paths["/v1/storekit/app-transaction/verify"]

    contract = json.loads(
        Path("tests/contracts/mobile_v1_routes.json").read_text(encoding="utf-8")
    )
    assert len(contract["routes"]) == 59
    assert all("storekit" not in route for route in contract["routes"])
    assert all("app-store" not in route for route in contract["routes"])
