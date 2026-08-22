from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from appstoreserverlibrary.models.AutoRenewStatus import AutoRenewStatus
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.models.NotificationTypeV2 import NotificationTypeV2
from appstoreserverlibrary.models.Subtype import Subtype
from appstoreserverlibrary.models.Type import Type as AppStoreProductType
from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier

from hike_journal.services.app_store_server import (
    APP_STORE_APP_ID_ENV,
    APP_STORE_BUNDLE_ID_ENV,
    APP_STORE_ENVIRONMENT_ENV,
    APP_STORE_ONLINE_CHECKS_ENV,
    APP_STORE_ROOT_CA_PATHS_ENV,
    AppStoreAccountLinkError,
    AppStoreConfigurationError,
    AppStoreNotificationNotLinked,
    AppStoreServerConfiguration,
    AppStoreServerVerifier,
    AppStoreVerificationError,
    build_app_store_server_verifier_from_environment,
    load_apple_root_certificates,
)
from hike_journal.services.entitlements import (
    APPLE_PLUS_ANNUAL_PRODUCT_ID,
    APPLE_PLUS_MONTHLY_PRODUCT_ID,
    EntitlementSource,
    EntitlementStatus,
    Plan,
    SupabaseEntitlementStore,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000002"
TRANSACTION_JWS = "transaction.payload.signature"
RENEWAL_JWS = "renewal.payload.signature"
NOTIFICATION_JWS = "notification.payload.signature"
APP_TRANSACTION_JWS = "app-transaction.payload.signature"
NOTIFICATION_UUID = "10000000-0000-0000-0000-000000000001"


def millis(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def sandbox_configuration() -> AppStoreServerConfiguration:
    return AppStoreServerConfiguration(
        bundle_id="com.hikejournal.app",
        environment=Environment.SANDBOX,
        app_apple_id=None,
        root_certificates=(b"injected-test-root",),
        enable_online_checks=True,
    )


def decoded_transaction(**overrides):
    values = {
        "transactionId": "2000000000000001",
        "originalTransactionId": "1000000000000001",
        "bundleId": "com.hikejournal.app",
        "productId": APPLE_PLUS_MONTHLY_PRODUCT_ID,
        "purchaseDate": millis(NOW - timedelta(days=2)),
        "originalPurchaseDate": millis(NOW - timedelta(days=2)),
        "expiresDate": millis(NOW + timedelta(days=28)),
        "signedDate": millis(NOW),
        "appAccountToken": USER_ID,
        "environment": Environment.SANDBOX,
        "type": AppStoreProductType.AUTO_RENEWABLE_SUBSCRIPTION,
        "rawType": None,
        "revocationDate": None,
        "revocationReason": None,
        "rawRevocationReason": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def decoded_renewal(**overrides):
    values = {
        "originalTransactionId": "1000000000000001",
        "productId": APPLE_PLUS_MONTHLY_PRODUCT_ID,
        "environment": Environment.SANDBOX,
        "appAccountToken": USER_ID,
        "autoRenewStatus": AutoRenewStatus.ON,
        "rawAutoRenewStatus": None,
        "gracePeriodExpiresDate": None,
        "signedDate": millis(NOW),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def decoded_notification(**overrides):
    data = SimpleNamespace(
        bundleId="com.hikejournal.app",
        appAppleId=None,
        environment=Environment.SANDBOX,
        signedTransactionInfo=TRANSACTION_JWS,
        signedRenewalInfo=RENEWAL_JWS,
    )
    values = {
        "notificationUUID": NOTIFICATION_UUID,
        "notificationType": NotificationTypeV2.DID_RENEW,
        "rawNotificationType": None,
        "subtype": None,
        "rawSubtype": None,
        "signedDate": millis(NOW),
        "data": data,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def decoded_app_transaction(**overrides):
    values = {
        "receiptType": Environment.SANDBOX,
        "appAppleId": 1234567890,
        "bundleId": "com.hikejournal.app",
        "applicationVersion": "42",
        "originalApplicationVersion": "1",
        "receiptCreationDate": millis(NOW),
        "originalPurchaseDate": millis(NOW - timedelta(days=3)),
        "appTransactionId": "app-transaction-1",
        "originalPlatform": "iOS",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeSignedDataVerifier:
    def __init__(self):
        self.transaction = decoded_transaction()
        self.renewal = decoded_renewal()
        self.notification = decoded_notification()
        self.app_transaction = decoded_app_transaction()
        self.failures: set[str] = set()
        self.calls: list[tuple[str, str]] = []

    def _result(self, name, value, payload):
        self.calls.append((name, value))
        if name in self.failures:
            raise RuntimeError("untrusted fixture")
        return payload

    def verify_and_decode_signed_transaction(self, value):
        return self._result("transaction", value, self.transaction)

    def verify_and_decode_renewal_info(self, value):
        return self._result("renewal", value, self.renewal)

    def verify_and_decode_notification(self, value):
        return self._result("notification", value, self.notification)

    def verify_and_decode_app_transaction(self, value):
        return self._result("app_transaction", value, self.app_transaction)


def service(fake: FakeSignedDataVerifier | None = None) -> AppStoreServerVerifier:
    return AppStoreServerVerifier(
        sandbox_configuration(),
        verifier=fake or FakeSignedDataVerifier(),
    )


def test_official_library_is_security_patch_pinned_in_both_deployments() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("requirements.txt", "requirements-mobile.txt"):
        requirements = (root / name).read_text(encoding="utf-8")
        assert "app-store-server-library==3.1.2" in requirements
    assert hasattr(SignedDataVerifier, "verify_and_decode_app_transaction")


def test_environment_configuration_builds_official_verifier_with_root_cas() -> None:
    seen = {}
    fake = FakeSignedDataVerifier()

    def root_loader(paths):
        seen["paths"] = tuple(paths)
        return (b"root-one", b"root-two")

    def verifier_factory(*args):
        seen["factory_args"] = args
        return fake

    built = build_app_store_server_verifier_from_environment(
        {
            APP_STORE_BUNDLE_ID_ENV: "com.hikejournal.app",
            APP_STORE_ENVIRONMENT_ENV: "Sandbox",
            APP_STORE_APP_ID_ENV: "",
            APP_STORE_ROOT_CA_PATHS_ENV: "/secrets/apple-g3.cer,/secrets/apple-g2.cer",
            APP_STORE_ONLINE_CHECKS_ENV: "true",
        },
        root_certificate_loader=root_loader,
        verifier_factory=verifier_factory,
    )

    assert seen["paths"] == (
        Path("/secrets/apple-g3.cer"),
        Path("/secrets/apple-g2.cer"),
    )
    assert seen["factory_args"] == (
        [b"root-one", b"root-two"],
        True,
        Environment.SANDBOX,
        "com.hikejournal.app",
        None,
    )
    assert built.verifier is fake


@pytest.mark.parametrize(
    "values",
    [
        {},
        {
            APP_STORE_BUNDLE_ID_ENV: "com.hikejournal.app",
            APP_STORE_ENVIRONMENT_ENV: "Xcode",
            APP_STORE_ROOT_CA_PATHS_ENV: "/root.cer",
        },
        {
            APP_STORE_BUNDLE_ID_ENV: "com.hikejournal.app",
            APP_STORE_ENVIRONMENT_ENV: "Production",
            APP_STORE_ROOT_CA_PATHS_ENV: "/root.cer",
            APP_STORE_APP_ID_ENV: "",
        },
        {
            APP_STORE_BUNDLE_ID_ENV: "com.hikejournal.app",
            APP_STORE_ENVIRONMENT_ENV: "Production",
            APP_STORE_ROOT_CA_PATHS_ENV: "/root.cer",
            APP_STORE_APP_ID_ENV: "123456789",
            APP_STORE_ONLINE_CHECKS_ENV: "false",
        },
    ],
)
def test_configuration_fails_closed_for_missing_or_unsigned_modes(values) -> None:
    with pytest.raises(AppStoreConfigurationError):
        AppStoreServerConfiguration.from_environment(
            values,
            root_certificate_loader=lambda _paths: (b"root",),
        )


def test_root_loader_rejects_missing_or_non_der_certificate(tmp_path: Path) -> None:
    missing = tmp_path / "missing.cer"
    with pytest.raises(AppStoreConfigurationError, match="DER Apple Root CA"):
        load_apple_root_certificates([missing])

    invalid = tmp_path / "invalid.cer"
    invalid.write_text("not a certificate", encoding="utf-8")
    with pytest.raises(AppStoreConfigurationError, match="DER Apple Root CA"):
        load_apple_root_certificates([invalid])


def test_initial_transaction_requires_matching_authenticated_app_account_token() -> None:
    fake = FakeSignedDataVerifier()
    verifier = service(fake)

    verified = verifier.verify_transaction_for_account(
        TRANSACTION_JWS,
        authenticated_user_id=USER_ID,
        signed_renewal_info=RENEWAL_JWS,
        now=NOW,
    )

    assert verified.transaction_id == "2000000000000001"
    assert verified.original_transaction_id == "1000000000000001"
    assert verified.auto_renew_enabled is True
    assert verified.environment == "Sandbox"
    assert fake.calls == [
        ("transaction", TRANSACTION_JWS),
        ("renewal", RENEWAL_JWS),
    ]


@pytest.mark.parametrize("account_token", [None, "", OTHER_USER_ID])
def test_initial_transaction_rejects_missing_or_mismatched_account_token(account_token) -> None:
    fake = FakeSignedDataVerifier()
    fake.transaction = decoded_transaction(appAccountToken=account_token)

    with pytest.raises(AppStoreAccountLinkError):
        service(fake).verify_transaction_for_account(
            TRANSACTION_JWS,
            authenticated_user_id=USER_ID,
            now=NOW,
        )


def test_initial_transaction_projection_uses_only_supported_products() -> None:
    verifier = service()

    projection = verifier.verify_and_project_transaction_for_account(
        TRANSACTION_JWS,
        authenticated_user_id=USER_ID,
        signed_renewal_info=RENEWAL_JWS,
        now=NOW,
    )

    assert projection.user_id == USER_ID
    assert projection.plan is Plan.PLUS
    assert projection.source is EntitlementSource.APPLE_SUBSCRIPTION
    assert projection.product_id == APPLE_PLUS_MONTHLY_PRODUCT_ID
    assert projection.external_entitlement_id == "1000000000000001"

    fake = FakeSignedDataVerifier()
    fake.transaction = decoded_transaction(productId="attacker.supplied.lifetime")
    with pytest.raises(AppStoreVerificationError, match="supported HikeJournal"):
        service(fake).verify_and_project_transaction_for_account(
            TRANSACTION_JWS,
            authenticated_user_id=USER_ID,
            now=NOW,
        )


def test_renewal_info_maps_cancellation_and_grace_period() -> None:
    fake = FakeSignedDataVerifier()
    fake.transaction = decoded_transaction(
        productId=APPLE_PLUS_ANNUAL_PRODUCT_ID,
        expiresDate=millis(NOW - timedelta(hours=1)),
    )
    fake.renewal = decoded_renewal(
        productId=APPLE_PLUS_ANNUAL_PRODUCT_ID,
        autoRenewStatus=AutoRenewStatus.OFF,
        gracePeriodExpiresDate=millis(NOW + timedelta(days=3)),
    )

    verified = service(fake).verify_transaction_for_account(
        TRANSACTION_JWS,
        authenticated_user_id=USER_ID,
        signed_renewal_info=RENEWAL_JWS,
        now=NOW,
    )

    assert verified.auto_renew_enabled is False
    assert verified.grace_expires_at == NOW + timedelta(days=3)


def test_transaction_and_renewal_identity_mismatches_fail_closed() -> None:
    fake = FakeSignedDataVerifier()
    fake.transaction = decoded_transaction(bundleId="example.attacker")
    with pytest.raises(AppStoreVerificationError, match="bundle ID"):
        service(fake).verify_transaction_for_account(
            TRANSACTION_JWS,
            authenticated_user_id=USER_ID,
            now=NOW,
        )

    fake = FakeSignedDataVerifier()
    fake.renewal = decoded_renewal(originalTransactionId="different-original")
    with pytest.raises(AppStoreVerificationError, match="different original"):
        service(fake).verify_transaction_for_account(
            TRANSACTION_JWS,
            authenticated_user_id=USER_ID,
            signed_renewal_info=RENEWAL_JWS,
            now=NOW,
        )


def test_invalid_jws_and_verifier_failure_never_fall_back_to_decoding() -> None:
    with pytest.raises(AppStoreVerificationError, match="compact JWS"):
        service().verify_transaction_for_account(
            "not-a-jws",
            authenticated_user_id=USER_ID,
            now=NOW,
        )

    fake = FakeSignedDataVerifier()
    fake.failures.add("transaction")
    with pytest.raises(AppStoreVerificationError, match="verification failed"):
        service(fake).verify_transaction_for_account(
            TRANSACTION_JWS,
            authenticated_user_id=USER_ID,
            now=NOW,
        )


def test_signed_app_transaction_returns_bounded_cryptographic_client_evidence() -> None:
    verified = service().verify_app_transaction(APP_TRANSACTION_JWS, now=NOW)

    assert verified.app_transaction_id == "app-transaction-1"
    assert verified.bundle_id == "com.hikejournal.app"
    assert verified.environment == "Sandbox"
    assert verified.application_version == "42"
    assert verified.original_application_version == "1"
    assert verified.receipt_created_at == NOW
    assert verified.original_purchased_at == NOW - timedelta(days=3)
    assert verified.original_platform == "iOS"
    assert not hasattr(verified, "deviceVerification")


def test_signed_app_transaction_rejects_wrong_app_and_future_signed_date() -> None:
    fake = FakeSignedDataVerifier()
    fake.app_transaction = decoded_app_transaction(bundleId="example.attacker")
    with pytest.raises(AppStoreVerificationError, match="bundle ID"):
        service(fake).verify_app_transaction(APP_TRANSACTION_JWS, now=NOW)

    fake.app_transaction = decoded_app_transaction(
        receiptCreationDate=millis(NOW + timedelta(minutes=6))
    )
    with pytest.raises(AppStoreVerificationError, match="too far in the future"):
        service(fake).verify_app_transaction(APP_TRANSACTION_JWS, now=NOW)


class Resolver:
    def __init__(self, user_id=USER_ID):
        self.user_id = user_id
        self.calls = []

    def resolve_apple_original_transaction_user_id(self, original_transaction_id):
        self.calls.append(original_transaction_id)
        return self.user_id


def test_notification_verifies_outer_and_nested_jws_then_resolves_original_transaction() -> None:
    fake = FakeSignedDataVerifier()
    fake.notification = decoded_notification(
        notificationType=NotificationTypeV2.DID_CHANGE_RENEWAL_STATUS,
        subtype=Subtype.AUTO_RENEW_DISABLED,
    )
    fake.renewal = decoded_renewal(autoRenewStatus=AutoRenewStatus.OFF)
    verifier = service(fake)
    resolver = Resolver()

    resolved = verifier.verify_resolve_and_project_notification(
        NOTIFICATION_JWS,
        resolver=resolver,
        now=NOW,
    )

    assert fake.calls == [
        ("notification", NOTIFICATION_JWS),
        ("transaction", TRANSACTION_JWS),
        ("renewal", RENEWAL_JWS),
    ]
    assert resolver.calls == ["1000000000000001"]
    assert resolved.user_id == USER_ID
    assert resolved.projection is not None
    assert resolved.projection.external_event_id == NOTIFICATION_UUID
    assert resolved.projection.status is EntitlementStatus.CANCELED


def test_later_notification_never_links_an_unknown_original_transaction() -> None:
    verifier = service()
    envelope = verifier.verify_notification(NOTIFICATION_JWS, now=NOW)

    with pytest.raises(AppStoreNotificationNotLinked):
        verifier.resolve_notification(envelope, Resolver(user_id=None))


def test_notification_rejects_app_account_token_conflicting_with_existing_link() -> None:
    fake = FakeSignedDataVerifier()
    fake.transaction = decoded_transaction(appAccountToken=OTHER_USER_ID)
    fake.renewal = decoded_renewal(appAccountToken=OTHER_USER_ID)
    verifier = service(fake)
    envelope = verifier.verify_notification(NOTIFICATION_JWS, now=NOW)

    with pytest.raises(AppStoreAccountLinkError, match="conflicts"):
        verifier.resolve_notification(envelope, Resolver(user_id=USER_ID))


def test_verified_non_transaction_notification_is_acknowledgeable_without_projection() -> None:
    fake = FakeSignedDataVerifier()
    fake.notification = decoded_notification(
        notificationType=NotificationTypeV2.TEST,
        data=SimpleNamespace(
            bundleId="com.hikejournal.app",
            appAppleId=None,
            environment=Environment.SANDBOX,
            signedTransactionInfo=None,
            signedRenewalInfo=None,
        ),
    )
    resolver = Resolver()

    resolved = service(fake).verify_resolve_and_project_notification(
        NOTIFICATION_JWS,
        resolver=resolver,
        now=NOW,
    )

    assert resolved.envelope.carries_entitlement is False
    assert resolved.user_id is None
    assert resolved.projection is None
    assert resolver.calls == []


def test_notification_with_invalid_nested_transaction_fails_closed() -> None:
    fake = FakeSignedDataVerifier()
    fake.failures.add("transaction")

    with pytest.raises(AppStoreVerificationError, match="verification failed"):
        service(fake).verify_notification(NOTIFICATION_JWS, now=NOW)


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.operations = []

    def select(self, value):
        self.operations.append(("select", value))
        return self

    def eq(self, key, value):
        self.operations.append(("eq", key, value))
        return self

    def limit(self, value):
        self.operations.append(("limit", value))
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class TableClient:
    def __init__(self, rows):
        self.query = Query(rows)
        self.table_name = None

    def table(self, name):
        self.table_name = name
        return self.query


def test_supabase_resolver_uses_only_prelinked_apple_original_transaction() -> None:
    client = TableClient([{"user_id": USER_ID}])

    resolved = SupabaseEntitlementStore(
        client
    ).resolve_apple_original_transaction_user_id("1000000000000001")

    assert resolved == USER_ID
    assert client.table_name == "app_entitlements"
    assert ("eq", "source", "apple_subscription") in client.query.operations
    assert (
        "eq",
        "original_transaction_id",
        "1000000000000001",
    ) in client.query.operations


def test_supabase_resolver_returns_none_instead_of_using_notification_token() -> None:
    client = TableClient([])

    assert (
        SupabaseEntitlementStore(client).resolve_apple_original_transaction_user_id(
            "unknown-original"
        )
        is None
    )
