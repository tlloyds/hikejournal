from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from hike_journal.services.entitlements import (
    APPLE_PLUS_ANNUAL_PRODUCT_ID,
    APPLE_PLUS_MONTHLY_PRODUCT_ID,
    BASIC_FEATURES,
    BillingPeriod,
    ClientPlatform,
    DEFAULT_ENTITLEMENT_POLICY,
    EnforcementStage,
    EntitlementDecision,
    EntitlementPolicy,
    EntitlementProjectionError,
    EntitlementRecord,
    EntitlementService,
    EntitlementSnapshot,
    EntitlementSource,
    EntitlementStatus,
    EntitlementUsage,
    GooglePlayVerificationSource,
    Plan,
    PlanPolicy,
    QuotaResource,
    SupabaseEntitlementStore,
    VerifiedAppleNotification,
    VerifiedAppleTransaction,
    VerifiedGooglePlayLegacyPurchase,
    AppleRevocationKind,
    feature_access,
    policy_from_rows,
    project_verified_apple_notification,
    project_verified_apple_transaction,
    project_verified_google_play_legacy_purchase,
    resolve_entitlement,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
USER_ID = "00000000-0000-0000-0000-000000000001"


def entitlement_row(**overrides):
    row = {
        "id": "entitlement-1",
        "user_id": USER_ID,
        "plan": "plus",
        "source": "apple_subscription",
        "status": "active",
        "product_id": APPLE_PLUS_MONTHLY_PRODUCT_ID,
        "billing_period": "monthly",
        "started_at": (NOW - timedelta(days=2)).isoformat(),
        "expires_at": (NOW + timedelta(days=28)).isoformat(),
        "last_event_at": NOW.isoformat(),
        "original_transaction_id": "original-1",
    }
    row.update(overrides)
    return row


def apple_transaction(**overrides) -> VerifiedAppleTransaction:
    values = {
        "transaction_id": "transaction-1",
        "original_transaction_id": "original-1",
        "product_id": APPLE_PLUS_MONTHLY_PRODUCT_ID,
        "purchased_at": NOW - timedelta(days=2),
        "expires_at": NOW + timedelta(days=28),
        "verified_at": NOW,
        "environment": "Sandbox",
    }
    values.update(overrides)
    return VerifiedAppleTransaction(**values)


def test_free_account_has_real_product_value_and_configured_3_50_limits() -> None:
    decision = resolve_entitlement([], now=NOW)
    plan_policy = DEFAULT_ENTITLEMENT_POLICY.for_plan(decision.plan)
    snapshot = EntitlementSnapshot(
        decision=decision,
        plan_policy=plan_policy,
        policy=DEFAULT_ENTITLEMENT_POLICY,
        usage=EntitlementUsage(cloud_hikes=2, cloud_media=47),
    )

    payload = snapshot.to_payload()

    assert payload["plan"] == "free"
    assert payload["source"] == "free"
    assert payload["status"] == "active"
    assert payload["limits"] == {"cloud_hikes": 3, "cloud_media": 50}
    assert payload["usage"] == {"cloud_hikes": 2, "cloud_media": 47}
    assert payload["features"]["gps_recording"] is True
    assert payload["features"]["basic_maps"] is True
    assert payload["features"]["field_guide_basic"] is True
    assert payload["features"]["field_briefing"] is False


@pytest.mark.parametrize(
    ("product_id", "period"),
    [
        (APPLE_PLUS_MONTHLY_PRODUCT_ID, BillingPeriod.MONTHLY),
        (APPLE_PLUS_ANNUAL_PRODUCT_ID, BillingPeriod.ANNUAL),
    ],
)
def test_active_monthly_and_annual_plus_resolve(product_id, period) -> None:
    decision = resolve_entitlement(
        [entitlement_row(product_id=product_id, billing_period=period.value)],
        now=NOW,
    )

    assert decision.plan is Plan.PLUS
    assert decision.status is EntitlementStatus.ACTIVE
    assert decision.billing_period is period
    assert decision.source is EntitlementSource.APPLE_SUBSCRIPTION


def test_lifetime_wins_over_an_active_subscription_and_has_plus_features() -> None:
    lifetime = entitlement_row(
        id="lifetime-1",
        plan="lifetime",
        source="google_play_legacy",
        status="active",
        billing_period="lifetime",
        product_id="com.hikejournal.app.legacy_paid_app",
        expires_at=None,
        purchase_token_hash="a" * 64,
    )

    decision = resolve_entitlement([entitlement_row(), lifetime], now=NOW)

    assert decision.plan is Plan.LIFETIME
    assert decision.source is EntitlementSource.GOOGLE_PLAY_LEGACY
    assert DEFAULT_ENTITLEMENT_POLICY.for_plan(Plan.LIFETIME).features == (
        DEFAULT_ENTITLEMENT_POLICY.for_plan(Plan.PLUS).features
    )


def test_canceled_subscription_keeps_plus_until_its_expiration() -> None:
    decision = resolve_entitlement(
        [entitlement_row(status="canceled", expires_at=NOW + timedelta(days=4))],
        now=NOW,
    )

    assert decision.plan is Plan.PLUS
    assert decision.status is EntitlementStatus.CANCELED_BUT_UNEXPIRED


def test_billing_grace_keeps_plus_only_through_grace_horizon() -> None:
    record = EntitlementRecord.from_row(
        entitlement_row(
            status="grace",
            expires_at=NOW - timedelta(hours=1),
            grace_expires_at=NOW + timedelta(days=3),
        )
    )

    during_grace = resolve_entitlement([record], now=NOW)
    after_grace = resolve_entitlement([record], now=NOW + timedelta(days=4))

    assert during_grace.plan is Plan.PLUS
    assert during_grace.status is EntitlementStatus.GRACE
    assert after_grace.plan is Plan.FREE
    assert after_grace.status is EntitlementStatus.EXPIRED
    assert after_grace.source is EntitlementSource.APPLE_SUBSCRIPTION


@pytest.mark.parametrize(
    ("status", "timestamp_field"),
    [
        ("revoked", "revoked_at"),
        ("refunded", "refunded_at"),
    ],
)
def test_revoked_and_refunded_subscriptions_never_grant_access(status, timestamp_field) -> None:
    row = entitlement_row(status=status)
    row[timestamp_field] = NOW - timedelta(minutes=1)

    decision = resolve_entitlement([row], now=NOW)

    assert decision.plan is Plan.FREE
    assert decision.status.value == status
    assert decision.source is EntitlementSource.APPLE_SUBSCRIPTION


def test_an_active_row_with_a_past_expiration_resolves_as_expired_free() -> None:
    decision = resolve_entitlement(
        [entitlement_row(status="active", expires_at=NOW - timedelta(seconds=1))],
        now=NOW,
    )

    assert decision.plan is Plan.FREE
    assert decision.status is EntitlementStatus.EXPIRED


def test_configurable_policy_rows_override_limits_and_feature_flags() -> None:
    policy = policy_from_rows(
        [
            {
                "plan": "free",
                "cloud_hikes_limit": 5,
                "cloud_media_limit": 75,
                "features": {
                    "gps_recording": True,
                    "field_briefing": True,
                    "future_server_feature": False,
                },
                "policy_version": "operator-2",
            }
        ]
    )

    assert policy.version == "operator-2"
    assert policy.for_plan(Plan.FREE).cloud_hikes_limit == 5
    assert policy.for_plan(Plan.FREE).cloud_media_limit == 75
    assert "field_briefing" in policy.for_plan(Plan.FREE).features
    assert "future_server_feature" in policy.feature_catalog
    assert "future_server_feature" not in policy.for_plan(Plan.FREE).features
    assert policy.for_plan(Plan.PLUS) == DEFAULT_ENTITLEMENT_POLICY.for_plan(Plan.PLUS)


def test_android_observe_only_stage_requires_a_trusted_server_decision() -> None:
    decision = resolve_entitlement([], now=NOW)
    snapshot = EntitlementSnapshot(
        decision=decision,
        plan_policy=DEFAULT_ENTITLEMENT_POLICY.for_plan(Plan.FREE),
        policy=DEFAULT_ENTITLEMENT_POLICY,
        usage=EntitlementUsage(),
    )

    client_claim_only = feature_access(
        snapshot,
        "field_briefing",
        platform=ClientPlatform.ANDROID,
    )
    trusted_legacy_route = feature_access(
        snapshot,
        "field_briefing",
        platform=ClientPlatform.ANDROID,
        trusted_legacy_paid_android=True,
    )

    assert DEFAULT_ENTITLEMENT_POLICY.android_paid_stage is EnforcementStage.OBSERVE_ONLY
    assert client_claim_only.allowed is False
    assert client_claim_only.enforced is True
    assert trusted_legacy_route.allowed is True
    assert trusted_legacy_route.enforced is False
    assert trusted_legacy_route.reason == "legacy_android_paid_compatibility"
    assert snapshot.decision.plan is Plan.FREE  # compatibility is not a fake Lifetime grant


def test_verified_apple_transaction_projects_stable_monthly_plus_state() -> None:
    transaction = apple_transaction()

    first = project_verified_apple_transaction(USER_ID, transaction, now=NOW)
    retry = project_verified_apple_transaction(USER_ID, transaction, now=NOW)

    assert first == retry
    assert first.fingerprint == retry.fingerprint
    assert first.plan is Plan.PLUS
    assert first.status is EntitlementStatus.ACTIVE
    assert first.billing_period is BillingPeriod.MONTHLY
    assert first.external_entitlement_id == "original-1"
    assert first.to_rpc_params()["p_projection"]["event_fingerprint"] == first.fingerprint


def test_apple_cancellation_is_canceled_but_unexpired_when_resolved() -> None:
    projection = project_verified_apple_transaction(
        USER_ID,
        apple_transaction(auto_renew_enabled=False),
        now=NOW,
    )
    decision = resolve_entitlement(
        [
            {
                **projection.to_rpc_params()["p_projection"],
                "id": "entitlement-1",
            }
        ],
        now=NOW,
    )

    assert projection.status is EntitlementStatus.CANCELED
    assert decision.plan is Plan.PLUS
    assert decision.status is EntitlementStatus.CANCELED_BUT_UNEXPIRED


def test_apple_billing_retry_grace_and_expiration_are_projected() -> None:
    transaction = apple_transaction(
        expires_at=NOW - timedelta(hours=1),
        grace_expires_at=NOW + timedelta(days=2),
    )
    grace = project_verified_apple_notification(
        USER_ID,
        VerifiedAppleNotification(
            notification_uuid="notification-grace",
            notification_type="DID_FAIL_TO_RENEW",
            subtype="GRACE_PERIOD",
            signed_at=NOW,
            transaction=transaction,
        ),
    )
    expired = project_verified_apple_notification(
        USER_ID,
        VerifiedAppleNotification(
            notification_uuid="notification-expired",
            notification_type="GRACE_PERIOD_EXPIRED",
            subtype=None,
            signed_at=NOW + timedelta(days=3),
            transaction=transaction,
        ),
    )

    assert grace.status is EntitlementStatus.GRACE
    assert expired.status is EntitlementStatus.EXPIRED


@pytest.mark.parametrize(
    ("notification_type", "expected", "timestamp_field"),
    [
        ("REFUND", EntitlementStatus.REFUNDED, "refunded_at"),
        ("REVOKE", EntitlementStatus.REVOKED, "revoked_at"),
    ],
)
def test_apple_refund_and_revocation_remove_access(
    notification_type,
    expected,
    timestamp_field,
) -> None:
    projection = project_verified_apple_notification(
        USER_ID,
        VerifiedAppleNotification(
            notification_uuid=f"notification-{notification_type.lower()}",
            notification_type=notification_type,
            subtype=None,
            signed_at=NOW,
            transaction=apple_transaction(),
        ),
    )

    assert projection.status is expected
    assert getattr(projection, timestamp_field) == NOW


def test_apple_refund_reversal_clears_terminal_markers() -> None:
    projection = project_verified_apple_notification(
        USER_ID,
        VerifiedAppleNotification(
            notification_uuid="notification-refund-reversed",
            notification_type="REFUND_REVERSED",
            subtype=None,
            signed_at=NOW,
            transaction=apple_transaction(
                revoked_at=NOW - timedelta(hours=1),
                revocation_kind=AppleRevocationKind.REFUND,
            ),
        ),
    )

    assert projection.status is EntitlementStatus.ACTIVE
    assert projection.refunded_at is None
    assert projection.revoked_at is None


def test_raw_apple_client_payload_and_unknown_product_are_rejected() -> None:
    with pytest.raises(TypeError, match="VerifiedAppleTransaction"):
        project_verified_apple_transaction(USER_ID, {"transaction_id": "client-claim"})

    with pytest.raises(EntitlementProjectionError, match="Unsupported"):
        project_verified_apple_transaction(
            USER_ID,
            apple_transaction(product_id="client.supplied.lifetime"),
            now=NOW,
        )


def test_verified_google_legacy_proof_projects_lifetime_without_storing_raw_token() -> None:
    purchase = VerifiedGooglePlayLegacyPurchase(
        verification_id="verification-1",
        verification_source=GooglePlayVerificationSource.SIGNED_LICENSE,
        package_name="com.hikejournal.app",
        purchase_token="signed-license-or-provider-evidence",
        product_id="com.hikejournal.app.legacy_paid_app",
        order_id="GPA.1234-5678-9012-34567",
        purchased_at=NOW - timedelta(days=400),
        verified_at=NOW,
    )

    projection = project_verified_google_play_legacy_purchase(
        USER_ID,
        purchase,
        token_hash_secret="server-only-pepper",
    )
    rpc_payload = projection.to_rpc_params()["p_projection"]

    assert projection.plan is Plan.LIFETIME
    assert projection.source is EntitlementSource.GOOGLE_PLAY_LEGACY
    assert projection.billing_period is BillingPeriod.LIFETIME
    assert projection.expires_at is None
    assert len(projection.purchase_token_hash or "") == 64
    assert purchase.purchase_token not in str(rpc_payload)


def test_google_legacy_projection_rejects_client_boolean_shape_and_wrong_package() -> None:
    with pytest.raises(TypeError, match="VerifiedGooglePlayLegacyPurchase"):
        project_verified_google_play_legacy_purchase(
            USER_ID,
            {"is_legacy_owner": True},
            token_hash_secret="server-only-pepper",
        )

    wrong_package = VerifiedGooglePlayLegacyPurchase(
        verification_id="verification-1",
        verification_source=GooglePlayVerificationSource.DEVELOPER_API,
        package_name="example.attacker.app",
        purchase_token="verified-token",
        product_id="legacy",
        purchased_at=NOW,
        verified_at=NOW,
    )
    with pytest.raises(EntitlementProjectionError, match="different Android package"):
        project_verified_google_play_legacy_purchase(
            USER_ID,
            wrong_package,
            token_hash_secret="server-only-pepper",
        )


class RpcCall:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeRpcClient:
    def __init__(self):
        self.calls = []
        self.responses = {}

    def rpc(self, name, params):
        self.calls.append((name, params))
        return RpcCall(self.responses[name])


def test_store_uses_atomic_projection_rpc_and_quota_reservation_rpc() -> None:
    client = FakeRpcClient()
    client.responses["apply_app_entitlement_event"] = {
        "applied": True,
        "duplicate": False,
        "entitlement_id": "entitlement-1",
    }
    client.responses["reserve_app_quota"] = {
        "allowed": True,
        "idempotent": False,
        "reservation_id": "reservation-1",
        "resource": "cloud_hikes",
        "resource_id": "00000000-0000-0000-0000-000000000002",
        "plan": "free",
        "limit": 3,
        "used": 2,
        "reserved": 1,
        "remaining": 0,
        "reason": None,
    }
    store = SupabaseEntitlementStore(client)
    projection = project_verified_apple_transaction(USER_ID, apple_transaction(), now=NOW)

    applied = store.apply(projection)
    reservation = store.reserve(
        user_id=USER_ID,
        resource=QuotaResource.CLOUD_HIKES,
        request_id="request-1",
        resource_id="00000000-0000-0000-0000-000000000002",
    )

    assert applied["applied"] is True
    assert client.calls[0][0] == "apply_app_entitlement_event"
    assert set(client.calls[0][1]) == {"p_projection"}
    assert client.calls[1][0] == "reserve_app_quota"
    assert reservation.allowed is True
    assert reservation.limit == 3
    assert reservation.remaining == 0


class SnapshotStore:
    def load_policy(self):
        return DEFAULT_ENTITLEMENT_POLICY

    def list_entitlements(self, _user_id):
        return [EntitlementRecord.from_row(entitlement_row())]

    def usage(self, _user_id):
        return EntitlementUsage(cloud_hikes=17, cloud_media=438)


def test_service_builds_endpoint_ready_usage_payload() -> None:
    payload = EntitlementService(SnapshotStore()).snapshot(USER_ID, now=NOW).to_payload()

    assert payload["plan"] == "plus"
    assert payload["billing_period"] == "monthly"
    assert payload["limits"]["cloud_hikes"] is None
    assert payload["limits"]["cloud_media"] == 10_000
    assert payload["usage"] == {"cloud_hikes": 17, "cloud_media": 438}
    assert payload["features"]["historical_weather"] is True
