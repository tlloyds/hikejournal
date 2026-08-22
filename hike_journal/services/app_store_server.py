from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
import os
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from appstoreserverlibrary.models.AutoRenewStatus import AutoRenewStatus
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.models.Type import Type as AppStoreProductType
from appstoreserverlibrary.signed_data_verifier import (
    SignedDataVerifier,
    VerificationException,
)
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import ExtensionOID

from hike_journal.services.entitlements import (
    AppleRevocationKind,
    EntitlementProjection,
    EntitlementProjectionError,
    VerifiedAppleNotification,
    VerifiedAppleTransaction,
    project_verified_apple_notification,
    project_verified_apple_transaction,
    utc_now,
)


APP_STORE_BUNDLE_ID_ENV = "APPLE_APP_STORE_BUNDLE_ID"
APP_STORE_ENVIRONMENT_ENV = "APPLE_APP_STORE_ENVIRONMENT"
APP_STORE_APP_ID_ENV = "APPLE_APP_STORE_APP_ID"
APP_STORE_ROOT_CA_PATHS_ENV = "APPLE_APP_STORE_ROOT_CA_PATHS"
APP_STORE_ONLINE_CHECKS_ENV = "APPLE_APP_STORE_ONLINE_CHECKS"

MAX_SIGNED_DATA_LENGTH = 1_000_000
MAX_CLOCK_SKEW = timedelta(minutes=5)


class AppStoreServerError(RuntimeError):
    """Base error for App Store server configuration and verification."""


class AppStoreConfigurationError(AppStoreServerError):
    """Raised when the backend cannot construct a secure Apple verifier."""


class AppStoreVerificationError(AppStoreServerError):
    """Raised when signed Apple data is missing, invalid, or inconsistent."""


class AppStoreAccountLinkError(AppStoreVerificationError):
    """Raised when verified Apple state cannot be linked to the signed-in account."""


class AppStoreNotificationNotLinked(AppStoreAccountLinkError):
    """Raised when a later notification has no previously linked transaction."""


class SignedDataVerifierProtocol(Protocol):
    def verify_and_decode_signed_transaction(self, signed_transaction: str) -> Any: ...

    def verify_and_decode_renewal_info(self, signed_renewal_info: str) -> Any: ...

    def verify_and_decode_notification(self, signed_payload: str) -> Any: ...

    def verify_and_decode_app_transaction(self, signed_app_transaction: str) -> Any: ...


class OriginalTransactionAccountResolver(Protocol):
    def resolve_apple_original_transaction_user_id(
        self,
        original_transaction_id: str,
    ) -> str | None: ...


@dataclass(frozen=True)
class AppStoreServerConfiguration:
    bundle_id: str
    environment: Environment
    app_apple_id: int | None
    root_certificates: tuple[bytes, ...]
    enable_online_checks: bool

    def __post_init__(self) -> None:
        if not self.bundle_id.strip():
            raise AppStoreConfigurationError(
                f"{APP_STORE_BUNDLE_ID_ENV} is required."
            )
        if self.environment not in {Environment.SANDBOX, Environment.PRODUCTION}:
            raise AppStoreConfigurationError(
                "The backend accepts only cryptographically signed Sandbox or Production "
                "App Store data. Xcode and LocalTesting payloads are not server evidence."
            )
        if not self.root_certificates or any(not value for value in self.root_certificates):
            raise AppStoreConfigurationError(
                f"{APP_STORE_ROOT_CA_PATHS_ENV} must provide at least one Apple Root CA."
            )
        if self.environment is Environment.PRODUCTION:
            if self.app_apple_id is None or self.app_apple_id <= 0:
                raise AppStoreConfigurationError(
                    f"{APP_STORE_APP_ID_ENV} is required for Production verification."
                )
            if not self.enable_online_checks:
                raise AppStoreConfigurationError(
                    "Production App Store verification requires online certificate checks."
                )

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        root_certificate_loader: Callable[[Sequence[Path]], tuple[bytes, ...]] | None = None,
    ) -> AppStoreServerConfiguration:
        values = os.environ if environment is None else environment
        bundle_id = str(values.get(APP_STORE_BUNDLE_ID_ENV) or "").strip()
        app_store_environment = _parse_environment(
            str(values.get(APP_STORE_ENVIRONMENT_ENV) or "")
        )
        app_apple_id = _parse_app_apple_id(values.get(APP_STORE_APP_ID_ENV))
        root_paths = _parse_root_certificate_paths(
            str(values.get(APP_STORE_ROOT_CA_PATHS_ENV) or "")
        )
        loader = root_certificate_loader or load_apple_root_certificates
        root_certificates = loader(root_paths)
        online_checks = _parse_boolean(
            values.get(APP_STORE_ONLINE_CHECKS_ENV),
            name=APP_STORE_ONLINE_CHECKS_ENV,
            default=True,
        )
        return cls(
            bundle_id=bundle_id,
            environment=app_store_environment,
            app_apple_id=app_apple_id,
            root_certificates=root_certificates,
            enable_online_checks=online_checks,
        )


def _parse_environment(value: str) -> Environment:
    normalized = value.strip().casefold().replace("-", "_")
    matches = {
        "sandbox": Environment.SANDBOX,
        "production": Environment.PRODUCTION,
        "xcode": Environment.XCODE,
        "localtesting": Environment.LOCAL_TESTING,
        "local_testing": Environment.LOCAL_TESTING,
    }
    try:
        return matches[normalized]
    except KeyError as exc:
        raise AppStoreConfigurationError(
            f"{APP_STORE_ENVIRONMENT_ENV} must be Sandbox or Production."
        ) from exc


def _parse_app_apple_id(value: str | None) -> int | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        parsed = int(normalized)
    except ValueError as exc:
        raise AppStoreConfigurationError(
            f"{APP_STORE_APP_ID_ENV} must be the numeric App Store Connect Apple ID."
        ) from exc
    if parsed <= 0:
        raise AppStoreConfigurationError(
            f"{APP_STORE_APP_ID_ENV} must be a positive integer."
        )
    return parsed


def _parse_root_certificate_paths(value: str) -> tuple[Path, ...]:
    paths = tuple(Path(item.strip()).expanduser() for item in value.split(",") if item.strip())
    if not paths:
        raise AppStoreConfigurationError(
            f"{APP_STORE_ROOT_CA_PATHS_ENV} is required."
        )
    return paths


def _parse_boolean(value: str | None, *, name: str, default: bool) -> bool:
    normalized = str(value or "").strip().casefold()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise AppStoreConfigurationError(f"{name} must be true or false.")


def load_apple_root_certificates(paths: Sequence[Path]) -> tuple[bytes, ...]:
    """Load DER Apple Root CAs and reject missing, malformed, or non-CA files."""

    loaded: list[bytes] = []
    fingerprints: set[bytes] = set()
    for path in paths:
        try:
            if not path.is_file():
                raise OSError("not a file")
            certificate_bytes = path.read_bytes()
            if not certificate_bytes or len(certificate_bytes) > 64 * 1024:
                raise ValueError("invalid certificate size")
            certificate = x509.load_der_x509_certificate(certificate_bytes)
            constraints = certificate.extensions.get_extension_for_oid(
                ExtensionOID.BASIC_CONSTRAINTS
            ).value
            if not constraints.ca:
                raise ValueError("certificate is not a CA")
            fingerprint = certificate.fingerprint(hashes.SHA256())
        except (OSError, ValueError, x509.ExtensionNotFound) as exc:
            raise AppStoreConfigurationError(
                f"Could not load a DER Apple Root CA from {path}."
            ) from exc
        if fingerprint not in fingerprints:
            fingerprints.add(fingerprint)
            loaded.append(certificate_bytes)
    if not loaded:
        raise AppStoreConfigurationError("At least one valid Apple Root CA is required.")
    return tuple(loaded)


def build_app_store_server_verifier(
    configuration: AppStoreServerConfiguration,
    *,
    verifier_factory: Callable[..., SignedDataVerifierProtocol] = SignedDataVerifier,
) -> AppStoreServerVerifier:
    try:
        verifier = verifier_factory(
            list(configuration.root_certificates),
            configuration.enable_online_checks,
            configuration.environment,
            configuration.bundle_id,
            configuration.app_apple_id,
        )
    except Exception as exc:
        raise AppStoreConfigurationError(
            "The App Store signed-data verifier could not be initialized."
        ) from exc
    return AppStoreServerVerifier(configuration, verifier=verifier)


def build_app_store_server_verifier_from_environment(
    environment: Mapping[str, str] | None = None,
    *,
    root_certificate_loader: Callable[[Sequence[Path]], tuple[bytes, ...]] | None = None,
    verifier_factory: Callable[..., SignedDataVerifierProtocol] = SignedDataVerifier,
) -> AppStoreServerVerifier:
    configuration = AppStoreServerConfiguration.from_environment(
        environment,
        root_certificate_loader=root_certificate_loader,
    )
    return build_app_store_server_verifier(
        configuration,
        verifier_factory=verifier_factory,
    )


@dataclass(frozen=True)
class VerifiedAppleAppTransaction:
    """Cryptographic evidence that the request carries this signed iOS app."""

    app_transaction_id: str
    app_apple_id: int | None
    bundle_id: str
    environment: str
    application_version: str
    original_application_version: str | None
    receipt_created_at: datetime
    original_purchased_at: datetime
    original_platform: str | None


@dataclass(frozen=True)
class VerifiedAppStoreNotificationEnvelope:
    notification_uuid: str
    notification_type: str
    subtype: str | None
    signed_at: datetime
    original_transaction_id: str | None
    app_account_token: str | None
    entitlement_notification: VerifiedAppleNotification | None

    @property
    def carries_entitlement(self) -> bool:
        return self.entitlement_notification is not None


@dataclass(frozen=True)
class ResolvedAppStoreNotification:
    envelope: VerifiedAppStoreNotificationEnvelope
    user_id: str | None
    projection: EntitlementProjection | None


class AppStoreServerVerifier:
    """Fail-closed adapter around Apple's official SignedDataVerifier."""

    def __init__(
        self,
        configuration: AppStoreServerConfiguration,
        *,
        verifier: SignedDataVerifierProtocol,
    ) -> None:
        self.configuration = configuration
        self.verifier = verifier

    def verify_app_transaction(
        self,
        signed_app_transaction: str,
        *,
        now: datetime | None = None,
    ) -> VerifiedAppleAppTransaction:
        decoded = self._verify(
            signed_app_transaction,
            self.verifier.verify_and_decode_app_transaction,
            label="AppTransaction",
        )
        self._validate_app_identity(
            bundle_id=getattr(decoded, "bundleId", None),
            environment=getattr(decoded, "receiptType", None),
            app_apple_id=getattr(decoded, "appAppleId", None),
        )
        receipt_created_at = _required_millis(
            getattr(decoded, "receiptCreationDate", None),
            "AppTransaction receiptCreationDate",
        )
        original_purchased_at = _required_millis(
            getattr(decoded, "originalPurchaseDate", None),
            "AppTransaction originalPurchaseDate",
        )
        _reject_future_timestamp(receipt_created_at, now=now, label="AppTransaction")
        return VerifiedAppleAppTransaction(
            app_transaction_id=_required_text(
                getattr(decoded, "appTransactionId", None),
                "AppTransaction appTransactionId",
            ),
            app_apple_id=_optional_positive_int(getattr(decoded, "appAppleId", None)),
            bundle_id=_required_text(getattr(decoded, "bundleId", None), "bundle ID"),
            environment=_enum_value(getattr(decoded, "receiptType", None)),
            application_version=_required_text(
                getattr(decoded, "applicationVersion", None),
                "AppTransaction applicationVersion",
            ),
            original_application_version=_optional_text(
                getattr(decoded, "originalApplicationVersion", None)
            ),
            receipt_created_at=receipt_created_at,
            original_purchased_at=original_purchased_at,
            original_platform=_optional_enum_value(
                getattr(decoded, "originalPlatform", None)
            ),
        )

    def verify_transaction_for_account(
        self,
        signed_transaction: str,
        *,
        authenticated_user_id: str,
        signed_renewal_info: str | None = None,
        now: datetime | None = None,
    ) -> VerifiedAppleTransaction:
        canonical_user_id = _canonical_uuid(
            authenticated_user_id,
            "Authenticated HikeJournal user ID",
        )
        decoded_transaction = self._verify(
            signed_transaction,
            self.verifier.verify_and_decode_signed_transaction,
            label="transaction",
        )
        decoded_renewal = self._verify_optional_renewal(signed_renewal_info)
        transaction, app_account_token = self._map_transaction(
            decoded_transaction,
            decoded_renewal,
            now=now,
        )
        if app_account_token is None:
            raise AppStoreAccountLinkError(
                "The verified transaction did not contain an appAccountToken."
            )
        if app_account_token != canonical_user_id:
            raise AppStoreAccountLinkError(
                "The verified transaction belongs to a different HikeJournal account."
            )
        return transaction

    def verify_and_project_transaction_for_account(
        self,
        signed_transaction: str,
        *,
        authenticated_user_id: str,
        signed_renewal_info: str | None = None,
        now: datetime | None = None,
    ) -> EntitlementProjection:
        current = _as_utc(now or utc_now())
        transaction = self.verify_transaction_for_account(
            signed_transaction,
            authenticated_user_id=authenticated_user_id,
            signed_renewal_info=signed_renewal_info,
            now=current,
        )
        try:
            return project_verified_apple_transaction(
                authenticated_user_id,
                transaction,
                now=current,
            )
        except EntitlementProjectionError as exc:
            raise AppStoreVerificationError(
                "The verified transaction is not a supported HikeJournal subscription."
            ) from exc

    def verify_notification(
        self,
        signed_payload: str,
        *,
        now: datetime | None = None,
    ) -> VerifiedAppStoreNotificationEnvelope:
        decoded_notification = self._verify(
            signed_payload,
            self.verifier.verify_and_decode_notification,
            label="notification",
        )
        data = getattr(decoded_notification, "data", None)
        if data is None:
            raise AppStoreVerificationError(
                "The verified notification did not contain app data."
            )
        self._validate_app_identity(
            bundle_id=getattr(data, "bundleId", None),
            environment=getattr(data, "environment", None),
            app_apple_id=getattr(data, "appAppleId", None),
        )
        notification_uuid = _canonical_uuid(
            getattr(decoded_notification, "notificationUUID", None),
            "Notification UUID",
        )
        notification_type = _required_enum_or_raw(
            getattr(decoded_notification, "notificationType", None),
            getattr(decoded_notification, "rawNotificationType", None),
            "notification type",
        )
        subtype = _optional_enum_or_raw(
            getattr(decoded_notification, "subtype", None),
            getattr(decoded_notification, "rawSubtype", None),
        )
        signed_at = _required_millis(
            getattr(decoded_notification, "signedDate", None),
            "notification signedDate",
        )
        _reject_future_timestamp(signed_at, now=now, label="notification")
        signed_transaction = _optional_text(getattr(data, "signedTransactionInfo", None))
        if signed_transaction is None:
            return VerifiedAppStoreNotificationEnvelope(
                notification_uuid=notification_uuid,
                notification_type=notification_type,
                subtype=subtype,
                signed_at=signed_at,
                original_transaction_id=None,
                app_account_token=None,
                entitlement_notification=None,
            )

        decoded_transaction = self._verify(
            signed_transaction,
            self.verifier.verify_and_decode_signed_transaction,
            label="notification transaction",
        )
        decoded_renewal = self._verify_optional_renewal(
            _optional_text(getattr(data, "signedRenewalInfo", None))
        )
        transaction, app_account_token = self._map_transaction(
            decoded_transaction,
            decoded_renewal,
            now=now,
        )
        verified_notification = VerifiedAppleNotification(
            notification_uuid=notification_uuid,
            notification_type=notification_type,
            subtype=subtype,
            signed_at=signed_at,
            transaction=transaction,
        )
        return VerifiedAppStoreNotificationEnvelope(
            notification_uuid=notification_uuid,
            notification_type=notification_type,
            subtype=subtype,
            signed_at=signed_at,
            original_transaction_id=transaction.original_transaction_id,
            app_account_token=app_account_token,
            entitlement_notification=verified_notification,
        )

    def resolve_notification(
        self,
        envelope: VerifiedAppStoreNotificationEnvelope,
        resolver: OriginalTransactionAccountResolver,
    ) -> ResolvedAppStoreNotification:
        if envelope.entitlement_notification is None:
            return ResolvedAppStoreNotification(
                envelope=envelope,
                user_id=None,
                projection=None,
            )
        original_transaction_id = _required_text(
            envelope.original_transaction_id,
            "Notification original transaction ID",
        )
        user_id = resolver.resolve_apple_original_transaction_user_id(
            original_transaction_id
        )
        if not user_id:
            raise AppStoreNotificationNotLinked(
                "The verified notification has no linked HikeJournal account."
            )
        canonical_user_id = _canonical_uuid(user_id, "Resolved HikeJournal user ID")
        if (
            envelope.app_account_token is not None
            and envelope.app_account_token != canonical_user_id
        ):
            raise AppStoreAccountLinkError(
                "The notification appAccountToken conflicts with the linked account."
            )
        try:
            projection = project_verified_apple_notification(
                canonical_user_id,
                envelope.entitlement_notification,
            )
        except EntitlementProjectionError as exc:
            raise AppStoreVerificationError(
                "The verified notification is not a supported HikeJournal subscription event."
            ) from exc
        return ResolvedAppStoreNotification(
            envelope=envelope,
            user_id=canonical_user_id,
            projection=projection,
        )

    def verify_resolve_and_project_notification(
        self,
        signed_payload: str,
        *,
        resolver: OriginalTransactionAccountResolver,
        now: datetime | None = None,
    ) -> ResolvedAppStoreNotification:
        envelope = self.verify_notification(signed_payload, now=now)
        return self.resolve_notification(envelope, resolver)

    def _verify_optional_renewal(self, signed_renewal_info: str | None) -> Any | None:
        if signed_renewal_info is None:
            return None
        return self._verify(
            signed_renewal_info,
            self.verifier.verify_and_decode_renewal_info,
            label="renewal info",
        )

    def _verify(
        self,
        signed_data: str,
        verifier: Callable[[str], Any],
        *,
        label: str,
    ) -> Any:
        normalized = _validate_compact_jws(signed_data, label=label)
        try:
            decoded = verifier(normalized)
        except VerificationException as exc:
            raise AppStoreVerificationError(
                f"Apple {label} verification failed."
            ) from exc
        except Exception as exc:
            raise AppStoreVerificationError(
                f"Apple {label} verification failed."
            ) from exc
        if decoded is None:
            raise AppStoreVerificationError(
                f"Apple {label} verification returned no payload."
            )
        return decoded

    def _validate_app_identity(
        self,
        *,
        bundle_id: Any,
        environment: Any,
        app_apple_id: Any,
    ) -> None:
        if str(bundle_id or "") != self.configuration.bundle_id:
            raise AppStoreVerificationError("Apple data has an unexpected bundle ID.")
        if _enum_value(environment) != self.configuration.environment.value:
            raise AppStoreVerificationError("Apple data has an unexpected environment.")
        if self.configuration.environment is Environment.PRODUCTION:
            try:
                decoded_app_id = int(app_apple_id)
            except (TypeError, ValueError) as exc:
                raise AppStoreVerificationError(
                    "Apple data did not contain the configured app Apple ID."
                ) from exc
            if decoded_app_id != self.configuration.app_apple_id:
                raise AppStoreVerificationError(
                    "Apple data has an unexpected app Apple ID."
                )

    def _map_transaction(
        self,
        decoded: Any,
        renewal: Any | None,
        *,
        now: datetime | None,
    ) -> tuple[VerifiedAppleTransaction, str | None]:
        self._validate_app_identity(
            bundle_id=getattr(decoded, "bundleId", None),
            environment=getattr(decoded, "environment", None),
            app_apple_id=self.configuration.app_apple_id,
        )
        product_type = getattr(decoded, "type", None)
        raw_product_type = getattr(decoded, "rawType", None)
        if _enum_or_raw(product_type, raw_product_type) != AppStoreProductType.AUTO_RENEWABLE_SUBSCRIPTION.value:
            raise AppStoreVerificationError(
                "The verified transaction is not an auto-renewable subscription."
            )

        transaction_id = _required_text(
            getattr(decoded, "transactionId", None),
            "transaction ID",
        )
        original_transaction_id = _required_text(
            getattr(decoded, "originalTransactionId", None),
            "original transaction ID",
        )
        product_id = _required_text(getattr(decoded, "productId", None), "product ID")
        purchased_at = _required_millis(
            getattr(decoded, "originalPurchaseDate", None)
            or getattr(decoded, "purchaseDate", None),
            "transaction purchase date",
        )
        expires_at = _required_millis(
            getattr(decoded, "expiresDate", None),
            "transaction expiration date",
        )
        verified_at = _required_millis(
            getattr(decoded, "signedDate", None),
            "transaction signedDate",
        )
        _reject_future_timestamp(verified_at, now=now, label="transaction")
        if expires_at <= purchased_at:
            raise AppStoreVerificationError(
                "The verified transaction has an invalid subscription interval."
            )

        app_account_token = _optional_uuid(
            getattr(decoded, "appAccountToken", None),
            "transaction appAccountToken",
        )
        auto_renew_enabled: bool | None = None
        grace_expires_at: datetime | None = None
        if renewal is not None:
            renewal_original_id = _required_text(
                getattr(renewal, "originalTransactionId", None),
                "renewal original transaction ID",
            )
            if renewal_original_id != original_transaction_id:
                raise AppStoreVerificationError(
                    "Renewal info belongs to a different original transaction."
                )
            renewal_product_id = _optional_text(getattr(renewal, "productId", None))
            if renewal_product_id and renewal_product_id != product_id:
                raise AppStoreVerificationError(
                    "Renewal info belongs to a different product."
                )
            renewal_environment = getattr(renewal, "environment", None)
            if _enum_value(renewal_environment) != self.configuration.environment.value:
                raise AppStoreVerificationError(
                    "Renewal info has an unexpected environment."
                )
            renewal_signed_at = _required_millis(
                getattr(renewal, "signedDate", None),
                "renewal signedDate",
            )
            _reject_future_timestamp(renewal_signed_at, now=now, label="renewal info")
            renewal_account_token = _optional_uuid(
                getattr(renewal, "appAccountToken", None),
                "renewal appAccountToken",
            )
            if (
                renewal_account_token is not None
                and app_account_token is not None
                and renewal_account_token != app_account_token
            ):
                raise AppStoreAccountLinkError(
                    "Renewal info belongs to a different HikeJournal account."
                )
            auto_renew_status = getattr(renewal, "autoRenewStatus", None)
            raw_auto_renew_status = getattr(renewal, "rawAutoRenewStatus", None)
            if auto_renew_status is not None or raw_auto_renew_status is not None:
                status_value = (
                    auto_renew_status.value
                    if isinstance(auto_renew_status, Enum)
                    else auto_renew_status
                )
                if status_value is None:
                    status_value = raw_auto_renew_status
                try:
                    normalized_status = int(status_value)
                except (TypeError, ValueError) as exc:
                    raise AppStoreVerificationError(
                        "Renewal info has an invalid auto-renew status."
                    ) from exc
                if normalized_status not in {
                    AutoRenewStatus.OFF.value,
                    AutoRenewStatus.ON.value,
                }:
                    raise AppStoreVerificationError(
                        "Renewal info has an invalid auto-renew status."
                    )
                auto_renew_enabled = normalized_status == AutoRenewStatus.ON.value
            grace_expires_at = _optional_millis(
                getattr(renewal, "gracePeriodExpiresDate", None),
                "renewal grace period expiration",
            )

        revoked_at = _optional_millis(
            getattr(decoded, "revocationDate", None),
            "transaction revocation date",
        )
        revocation_reason = getattr(decoded, "revocationReason", None)
        raw_revocation_reason = getattr(decoded, "rawRevocationReason", None)
        revocation_kind = None
        if revoked_at is not None:
            revocation_kind = (
                AppleRevocationKind.REFUND
                if revocation_reason is not None or raw_revocation_reason is not None
                else AppleRevocationKind.REVOKE
            )

        transaction = VerifiedAppleTransaction(
            transaction_id=transaction_id,
            original_transaction_id=original_transaction_id,
            product_id=product_id,
            purchased_at=purchased_at,
            expires_at=expires_at,
            verified_at=verified_at,
            environment=self.configuration.environment.value,
            auto_renew_enabled=auto_renew_enabled,
            grace_expires_at=grace_expires_at,
            revoked_at=revoked_at,
            revocation_kind=revocation_kind,
        )
        return transaction, app_account_token


def _validate_compact_jws(value: str, *, label: str) -> str:
    normalized = str(value or "").strip()
    if (
        not normalized
        or len(normalized) > MAX_SIGNED_DATA_LENGTH
        or len(normalized.split(".")) != 3
        or any(not part for part in normalized.split("."))
    ):
        raise AppStoreVerificationError(f"Apple {label} is not a compact JWS.")
    return normalized


def _required_text(value: Any, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise AppStoreVerificationError(f"Verified Apple data is missing {label}.")
    return normalized


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _canonical_uuid(value: Any, label: str) -> str:
    try:
        return str(UUID(str(value or "").strip()))
    except (ValueError, TypeError, AttributeError) as exc:
        raise AppStoreAccountLinkError(f"{label} must be a UUID.") from exc


def _optional_uuid(value: Any, label: str) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return _canonical_uuid(value, label)


def _required_millis(value: Any, label: str) -> datetime:
    parsed = _optional_millis(value, label)
    if parsed is None:
        raise AppStoreVerificationError(f"Verified Apple data is missing {label}.")
    return parsed


def _optional_millis(value: Any, label: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise AppStoreVerificationError(f"Verified Apple data has an invalid {label}.")
    try:
        milliseconds = int(value)
        if milliseconds <= 0:
            raise ValueError
        return datetime.fromtimestamp(milliseconds / 1000, tz=UTC)
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        raise AppStoreVerificationError(
            f"Verified Apple data has an invalid {label}."
        ) from exc


def _optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AppStoreVerificationError("Verified Apple data has an invalid app Apple ID.") from exc
    if parsed <= 0:
        raise AppStoreVerificationError("Verified Apple data has an invalid app Apple ID.")
    return parsed


def _enum_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value or "")


def _optional_enum_value(value: Any) -> str | None:
    normalized = _enum_value(value).strip()
    return normalized or None


def _enum_or_raw(value: Any, raw_value: Any) -> str:
    return _enum_value(value).strip() or str(raw_value or "").strip()


def _required_enum_or_raw(value: Any, raw_value: Any, label: str) -> str:
    normalized = _enum_or_raw(value, raw_value)
    if not normalized:
        raise AppStoreVerificationError(f"Verified Apple data is missing {label}.")
    return normalized


def _optional_enum_or_raw(value: Any, raw_value: Any) -> str | None:
    normalized = _enum_or_raw(value, raw_value)
    return normalized or None


def _reject_future_timestamp(
    value: datetime,
    *,
    now: datetime | None,
    label: str,
) -> None:
    current = _as_utc(now or utc_now())
    if value > current + MAX_CLOCK_SKEW:
        raise AppStoreVerificationError(
            f"Verified Apple {label} has a signed date too far in the future."
        )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
