from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
import hashlib
import hmac
import json
from typing import Any, Iterable, Mapping


APPLE_PLUS_MONTHLY_PRODUCT_ID = "com.hikejournal.app.plus.monthly"
APPLE_PLUS_ANNUAL_PRODUCT_ID = "com.hikejournal.app.plus.annual"
GOOGLE_PLAY_PACKAGE_NAME = "com.hikejournal.app"

ENTITLEMENT_TABLE = "app_entitlements"
ENTITLEMENT_POLICY_TABLE = "app_entitlement_policies"
ENTITLEMENT_PROJECTION_RPC = "apply_app_entitlement_event"
ENTITLEMENT_USAGE_RPC = "app_quota_usage"
ENTITLEMENT_RESERVATION_RPC = "reserve_app_quota"
ENTITLEMENT_RELEASE_RPC = "release_app_quota_reservation"


class Plan(str, Enum):
    FREE = "free"
    PLUS = "plus"
    LIFETIME = "lifetime"


class EntitlementSource(str, Enum):
    FREE = "free"
    APPLE_SUBSCRIPTION = "apple_subscription"
    GOOGLE_PLAY_SUBSCRIPTION = "google_play_subscription"
    GOOGLE_PLAY_LEGACY = "google_play_legacy"
    ADMIN = "admin"


class BillingPeriod(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"
    LIFETIME = "lifetime"


class EntitlementStatus(str, Enum):
    ACTIVE = "active"
    GRACE = "grace"
    CANCELED = "canceled"
    CANCELED_BUT_UNEXPIRED = "canceled_but_unexpired"
    EXPIRED = "expired"
    REVOKED = "revoked"
    REFUNDED = "refunded"


class QuotaResource(str, Enum):
    CLOUD_HIKES = "cloud_hikes"
    CLOUD_MEDIA = "cloud_media"


class ClientPlatform(str, Enum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"
    UNKNOWN = "unknown"


class EnforcementStage(str, Enum):
    ENFORCED = "enforced"
    OBSERVE_ONLY = "observe_only"


class AppleRevocationKind(str, Enum):
    REFUND = "refund"
    REVOKE = "revoke"


class GooglePlayVerificationSource(str, Enum):
    DEVELOPER_API = "google_play_developer_api"
    SIGNED_LICENSE = "google_play_signed_license"


class EntitlementError(RuntimeError):
    """Base error for invalid entitlement state or unavailable persistence."""


class EntitlementProjectionError(EntitlementError):
    """Raised when verified store state cannot be projected safely."""


class EntitlementStoreError(EntitlementError):
    """Raised when the durable entitlement store cannot complete an operation."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | str | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def _require_text(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise EntitlementProjectionError(f"{label} is required.")
    return normalized


def _canonical_fingerprint(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=lambda value: value.value if isinstance(value, Enum) else _iso(value),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


BASIC_FEATURES = frozenset(
    {
        "basic_maps",
        "cloud_journals",
        "cloud_media",
        "field_guide_basic",
        "gps_recording",
        "route_viewing",
    }
)

PLUS_FEATURES = BASIC_FEATURES | frozenset(
    {
        "field_briefing",
        "historical_weather",
        "hike_comparison",
        "offline_maps",
        "phenology_history",
        "place_profiles",
        "provenance_history",
        "species_intelligence",
    }
)


@dataclass(frozen=True)
class PlanPolicy:
    plan: Plan
    cloud_hikes_limit: int | None
    cloud_media_limit: int | None
    features: frozenset[str]

    def limit_for(self, resource: QuotaResource) -> int | None:
        if resource is QuotaResource.CLOUD_HIKES:
            return self.cloud_hikes_limit
        return self.cloud_media_limit

    def limits_payload(self) -> dict[str, int | None]:
        return {
            QuotaResource.CLOUD_HIKES.value: self.cloud_hikes_limit,
            QuotaResource.CLOUD_MEDIA.value: self.cloud_media_limit,
        }

    def features_payload(self, feature_catalog: Iterable[str]) -> dict[str, bool]:
        return {name: name in self.features for name in sorted(set(feature_catalog))}


@dataclass(frozen=True)
class EntitlementPolicy:
    version: str
    plans: Mapping[Plan, PlanPolicy]
    android_paid_stage: EnforcementStage = EnforcementStage.OBSERVE_ONLY
    known_feature_names: frozenset[str] = frozenset()

    def for_plan(self, plan: Plan) -> PlanPolicy:
        try:
            return self.plans[plan]
        except KeyError as exc:
            raise EntitlementError(f"No server entitlement policy is configured for {plan.value}.") from exc

    @property
    def feature_catalog(self) -> frozenset[str]:
        return self.known_feature_names | frozenset(
            feature
            for policy in self.plans.values()
            for feature in policy.features
        )

    def enforcement_stage(self, platform: ClientPlatform) -> EnforcementStage:
        if platform is ClientPlatform.ANDROID:
            return self.android_paid_stage
        return EnforcementStage.ENFORCED


DEFAULT_ENTITLEMENT_POLICY = EntitlementPolicy(
    version="2026-08-21",
    plans={
        Plan.FREE: PlanPolicy(
            plan=Plan.FREE,
            cloud_hikes_limit=3,
            cloud_media_limit=50,
            features=BASIC_FEATURES,
        ),
        Plan.PLUS: PlanPolicy(
            plan=Plan.PLUS,
            cloud_hikes_limit=None,
            cloud_media_limit=10_000,
            features=PLUS_FEATURES,
        ),
        Plan.LIFETIME: PlanPolicy(
            plan=Plan.LIFETIME,
            cloud_hikes_limit=None,
            cloud_media_limit=10_000,
            features=PLUS_FEATURES,
        ),
    },
    known_feature_names=PLUS_FEATURES,
)


def policy_from_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    fallback: EntitlementPolicy = DEFAULT_ENTITLEMENT_POLICY,
) -> EntitlementPolicy:
    """Build the runtime policy from server-owned database rows.

    Missing plans retain the safe checked-in defaults. This allows an additive
    migration to deploy before an operator customizes protective ceilings.
    """

    plans = dict(fallback.plans)
    versions: list[str] = []
    known_features = set(fallback.feature_catalog)
    for row in rows:
        try:
            plan = Plan(str(row["plan"]).strip().lower())
        except (KeyError, ValueError):
            continue
        default = fallback.for_plan(plan)
        raw_features = row.get("features")
        if isinstance(raw_features, Mapping):
            known_features.update(str(name) for name in raw_features)
            features = frozenset(
                str(name)
                for name, enabled in raw_features.items()
                if bool(enabled)
            )
        elif isinstance(raw_features, (list, tuple, set, frozenset)):
            known_features.update(str(name) for name in raw_features)
            features = frozenset(str(name) for name in raw_features)
        else:
            features = default.features
        plans[plan] = PlanPolicy(
            plan=plan,
            cloud_hikes_limit=(
                _policy_limit(row.get("cloud_hikes_limit"), default.cloud_hikes_limit)
                if "cloud_hikes_limit" in row
                else default.cloud_hikes_limit
            ),
            cloud_media_limit=(
                _policy_limit(row.get("cloud_media_limit"), default.cloud_media_limit)
                if "cloud_media_limit" in row
                else default.cloud_media_limit
            ),
            features=features,
        )
        if row.get("policy_version"):
            versions.append(str(row["policy_version"]))
    return EntitlementPolicy(
        version=max(versions) if versions else fallback.version,
        plans=plans,
        android_paid_stage=fallback.android_paid_stage,
        known_feature_names=frozenset(known_features),
    )


def _policy_limit(value: Any, default: int | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


@dataclass(frozen=True)
class EntitlementRecord:
    id: str
    user_id: str
    plan: Plan
    source: EntitlementSource
    status: EntitlementStatus
    product_id: str | None = None
    billing_period: BillingPeriod | None = None
    started_at: datetime | None = None
    expires_at: datetime | None = None
    grace_expires_at: datetime | None = None
    revoked_at: datetime | None = None
    refunded_at: datetime | None = None
    last_event_at: datetime | None = None
    original_transaction_id: str | None = None
    purchase_token_hash: str | None = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> EntitlementRecord:
        raw_period = row.get("billing_period")
        return cls(
            id=str(row.get("id") or ""),
            user_id=str(row.get("user_id") or ""),
            plan=Plan(str(row.get("plan") or Plan.FREE.value).lower()),
            source=EntitlementSource(
                str(row.get("source") or EntitlementSource.FREE.value).lower()
            ),
            status=EntitlementStatus(
                str(row.get("status") or EntitlementStatus.ACTIVE.value).lower()
            ),
            product_id=(str(row["product_id"]) if row.get("product_id") else None),
            billing_period=(BillingPeriod(str(raw_period).lower()) if raw_period else None),
            started_at=_as_utc(row.get("started_at")),
            expires_at=_as_utc(row.get("expires_at")),
            grace_expires_at=_as_utc(row.get("grace_expires_at")),
            revoked_at=_as_utc(row.get("revoked_at")),
            refunded_at=_as_utc(row.get("refunded_at")),
            last_event_at=_as_utc(row.get("last_event_at")),
            original_transaction_id=(
                str(row["original_transaction_id"])
                if row.get("original_transaction_id")
                else None
            ),
            purchase_token_hash=(
                str(row["purchase_token_hash"])
                if row.get("purchase_token_hash")
                else None
            ),
        )

    def resolved_status(self, *, now: datetime) -> EntitlementStatus:
        current = _as_utc(now)
        assert current is not None
        if self.refunded_at is not None or self.status is EntitlementStatus.REFUNDED:
            return EntitlementStatus.REFUNDED
        if self.revoked_at is not None or self.status is EntitlementStatus.REVOKED:
            return EntitlementStatus.REVOKED
        if self.status is EntitlementStatus.EXPIRED:
            return EntitlementStatus.EXPIRED
        if self.status is EntitlementStatus.GRACE:
            grace_horizon = self.grace_expires_at or self.expires_at
            if grace_horizon is None or grace_horizon > current:
                return EntitlementStatus.GRACE
            return EntitlementStatus.EXPIRED
        if self.expires_at is not None and self.expires_at <= current:
            return EntitlementStatus.EXPIRED
        if self.status in {
            EntitlementStatus.CANCELED,
            EntitlementStatus.CANCELED_BUT_UNEXPIRED,
        }:
            if self.expires_at is not None and self.expires_at > current:
                return EntitlementStatus.CANCELED_BUT_UNEXPIRED
            return EntitlementStatus.EXPIRED
        return EntitlementStatus.ACTIVE


GRANTING_STATUSES = frozenset(
    {
        EntitlementStatus.ACTIVE,
        EntitlementStatus.GRACE,
        EntitlementStatus.CANCELED_BUT_UNEXPIRED,
    }
)


@dataclass(frozen=True)
class EntitlementDecision:
    plan: Plan
    source: EntitlementSource
    status: EntitlementStatus
    billing_period: BillingPeriod | None
    product_id: str | None
    expires_at: datetime | None
    grace_expires_at: datetime | None
    record_id: str | None


def resolve_entitlement(
    records: Iterable[EntitlementRecord | Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> EntitlementDecision:
    """Resolve server records into one effective Free/Plus/Lifetime decision."""

    current = _as_utc(now or utc_now())
    assert current is not None
    parsed = [
        record if isinstance(record, EntitlementRecord) else EntitlementRecord.from_row(record)
        for record in records
    ]
    granting = [
        record
        for record in parsed
        if record.plan in {Plan.PLUS, Plan.LIFETIME}
        and record.resolved_status(now=current) in GRANTING_STATUSES
    ]
    if granting:
        selected = max(granting, key=lambda item: _granting_sort_key(item, current))
        return _decision_for_record(selected, now=current, effective_plan=selected.plan)

    paid_history = [record for record in parsed if record.plan is not Plan.FREE]
    if paid_history:
        selected = max(paid_history, key=_history_sort_key)
        return _decision_for_record(selected, now=current, effective_plan=Plan.FREE)

    return EntitlementDecision(
        plan=Plan.FREE,
        source=EntitlementSource.FREE,
        status=EntitlementStatus.ACTIVE,
        billing_period=None,
        product_id=None,
        expires_at=None,
        grace_expires_at=None,
        record_id=None,
    )


def _granting_sort_key(record: EntitlementRecord, now: datetime) -> tuple[int, int, float, str]:
    plan_rank = {Plan.FREE: 0, Plan.PLUS: 1, Plan.LIFETIME: 2}[record.plan]
    status_rank = {
        EntitlementStatus.CANCELED_BUT_UNEXPIRED: 1,
        EntitlementStatus.GRACE: 2,
        EntitlementStatus.ACTIVE: 3,
    }[record.resolved_status(now=now)]
    horizon = record.grace_expires_at or record.expires_at
    horizon_rank = horizon.timestamp() if horizon else float("inf")
    return plan_rank, status_rank, horizon_rank, record.id


def _history_sort_key(record: EntitlementRecord) -> tuple[float, str]:
    occurred_at = record.last_event_at or record.refunded_at or record.revoked_at or record.expires_at
    occurred_at = occurred_at or record.started_at or datetime.min.replace(tzinfo=UTC)
    return occurred_at.timestamp(), record.id


def _decision_for_record(
    record: EntitlementRecord,
    *,
    now: datetime,
    effective_plan: Plan,
) -> EntitlementDecision:
    return EntitlementDecision(
        plan=effective_plan,
        source=record.source,
        status=record.resolved_status(now=now),
        billing_period=record.billing_period,
        product_id=record.product_id,
        expires_at=record.expires_at,
        grace_expires_at=record.grace_expires_at,
        record_id=record.id or None,
    )


@dataclass(frozen=True)
class EntitlementUsage:
    cloud_hikes: int = 0
    cloud_media: int = 0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> EntitlementUsage:
        payload = payload or {}
        return cls(
            cloud_hikes=max(0, int(payload.get("cloud_hikes") or 0)),
            cloud_media=max(0, int(payload.get("cloud_media") or 0)),
        )

    def to_payload(self) -> dict[str, int]:
        return {
            QuotaResource.CLOUD_HIKES.value: self.cloud_hikes,
            QuotaResource.CLOUD_MEDIA.value: self.cloud_media,
        }


@dataclass(frozen=True)
class EntitlementSnapshot:
    decision: EntitlementDecision
    plan_policy: PlanPolicy
    policy: EntitlementPolicy
    usage: EntitlementUsage

    def to_payload(self) -> dict[str, Any]:
        return {
            "plan": self.decision.plan.value,
            "source": self.decision.source.value,
            "billing_period": (
                self.decision.billing_period.value if self.decision.billing_period else None
            ),
            "status": self.decision.status.value,
            "product_id": self.decision.product_id,
            "expires_at": _iso(self.decision.expires_at),
            "grace_expires_at": _iso(self.decision.grace_expires_at),
            "limits": self.plan_policy.limits_payload(),
            "usage": self.usage.to_payload(),
            "features": self.plan_policy.features_payload(self.policy.feature_catalog),
            "policy": {
                "version": self.policy.version,
                "android_paid_compatibility": self.policy.android_paid_stage.value,
            },
        }


@dataclass(frozen=True)
class FeatureAccessDecision:
    allowed: bool
    enforced: bool
    reason: str


def feature_access(
    snapshot: EntitlementSnapshot,
    feature: str,
    *,
    platform: ClientPlatform = ClientPlatform.UNKNOWN,
    trusted_legacy_paid_android: bool = False,
) -> FeatureAccessDecision:
    """Authorize a feature without turning an Android client claim into access.

    Existing paid Android routes can opt into the explicit observe-only bridge
    during their separately controlled commercial migration. The caller must
    supply a trusted server-side compatibility decision; merely declaring the
    platform as Android never bypasses entitlement enforcement.
    """

    entitled = feature in snapshot.plan_policy.features
    compatibility = (
        platform is ClientPlatform.ANDROID
        and trusted_legacy_paid_android
        and snapshot.policy.enforcement_stage(platform) is EnforcementStage.OBSERVE_ONLY
    )
    if compatibility:
        return FeatureAccessDecision(
            allowed=True,
            enforced=False,
            reason="legacy_android_paid_compatibility",
        )
    return FeatureAccessDecision(
        allowed=entitled,
        enforced=True,
        reason="entitled" if entitled else "plus_required",
    )


@dataclass(frozen=True)
class EntitlementProjection:
    user_id: str
    source: EntitlementSource
    external_event_id: str
    external_entitlement_id: str
    event_type: str
    occurred_at: datetime
    plan: Plan
    status: EntitlementStatus
    product_id: str | None
    billing_period: BillingPeriod | None
    started_at: datetime | None
    expires_at: datetime | None
    grace_expires_at: datetime | None = None
    revoked_at: datetime | None = None
    refunded_at: datetime | None = None
    original_transaction_id: str | None = None
    purchase_token_hash: str | None = None
    environment: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        return _canonical_fingerprint(self.fingerprint_payload())

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "source": self.source.value,
            "external_event_id": self.external_event_id,
            "external_entitlement_id": self.external_entitlement_id,
            "event_type": self.event_type,
            "occurred_at": _iso(self.occurred_at),
            "plan": self.plan.value,
            "status": self.status.value,
            "product_id": self.product_id,
            "billing_period": self.billing_period.value if self.billing_period else None,
            "started_at": _iso(self.started_at),
            "expires_at": _iso(self.expires_at),
            "grace_expires_at": _iso(self.grace_expires_at),
            "revoked_at": _iso(self.revoked_at),
            "refunded_at": _iso(self.refunded_at),
            "original_transaction_id": self.original_transaction_id,
            "purchase_token_hash": self.purchase_token_hash,
            "environment": self.environment,
            "metadata": dict(self.metadata),
        }

    def to_rpc_params(self) -> dict[str, Any]:
        if self.status is EntitlementStatus.CANCELED_BUT_UNEXPIRED:
            stored_status = EntitlementStatus.CANCELED
        else:
            stored_status = self.status
        return {
            "p_projection": {
                "user_id": self.user_id,
                "source": self.source.value,
                "external_event_id": self.external_event_id,
                "external_entitlement_id": self.external_entitlement_id,
                "event_type": self.event_type,
                "event_fingerprint": self.fingerprint,
                "occurred_at": _iso(self.occurred_at),
                "plan": self.plan.value,
                "status": stored_status.value,
                "product_id": self.product_id,
                "billing_period": self.billing_period.value if self.billing_period else None,
                "started_at": _iso(self.started_at),
                "expires_at": _iso(self.expires_at),
                "grace_expires_at": _iso(self.grace_expires_at),
                "revoked_at": _iso(self.revoked_at),
                "refunded_at": _iso(self.refunded_at),
                "original_transaction_id": self.original_transaction_id,
                "purchase_token_hash": self.purchase_token_hash,
                "environment": self.environment,
                "metadata": dict(self.metadata),
            }
        }


@dataclass(frozen=True)
class VerifiedAppleTransaction:
    """A transaction only after App Store JWS verification on the server."""

    transaction_id: str
    original_transaction_id: str
    product_id: str
    purchased_at: datetime
    expires_at: datetime
    verified_at: datetime
    environment: str
    auto_renew_enabled: bool | None = None
    grace_expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_kind: AppleRevocationKind | None = None

    def __post_init__(self) -> None:
        _require_text(self.transaction_id, "Apple transaction ID")
        _require_text(self.original_transaction_id, "Apple original transaction ID")
        _require_text(self.product_id, "Apple product ID")
        _require_text(self.environment, "Apple environment")
        if _as_utc(self.expires_at) is None:
            raise EntitlementProjectionError("Apple subscription expiration is required.")
        if self.revoked_at is not None and self.revocation_kind is None:
            raise EntitlementProjectionError("Apple revocation kind is required with revoked_at.")


APPLE_PRODUCT_BILLING_PERIODS: Mapping[str, BillingPeriod] = {
    APPLE_PLUS_MONTHLY_PRODUCT_ID: BillingPeriod.MONTHLY,
    APPLE_PLUS_ANNUAL_PRODUCT_ID: BillingPeriod.ANNUAL,
}


def project_verified_apple_transaction(
    user_id: str,
    transaction: VerifiedAppleTransaction,
    *,
    now: datetime | None = None,
    event_id: str | None = None,
    event_type: str = "transaction_sync",
) -> EntitlementProjection:
    """Convert cryptographically verified StoreKit state into a durable mutation."""

    if not isinstance(transaction, VerifiedAppleTransaction):
        raise TypeError("A VerifiedAppleTransaction is required; raw client purchase data is not accepted.")
    normalized_user_id = _require_text(user_id, "HikeJournal user ID")
    try:
        billing_period = APPLE_PRODUCT_BILLING_PERIODS[transaction.product_id]
    except KeyError as exc:
        raise EntitlementProjectionError(
            f"Unsupported HikeJournal Apple product: {transaction.product_id}"
        ) from exc
    current = _as_utc(now or transaction.verified_at)
    expires_at = _as_utc(transaction.expires_at)
    verified_at = _as_utc(transaction.verified_at)
    purchased_at = _as_utc(transaction.purchased_at)
    grace_expires_at = _as_utc(transaction.grace_expires_at)
    revoked_at = _as_utc(transaction.revoked_at)
    assert current and expires_at and verified_at and purchased_at

    refunded_at = None
    if revoked_at is not None:
        if transaction.revocation_kind is AppleRevocationKind.REFUND:
            status = EntitlementStatus.REFUNDED
            refunded_at = revoked_at
            revoked_at = None
        else:
            status = EntitlementStatus.REVOKED
    elif grace_expires_at is not None and grace_expires_at > current and expires_at <= current:
        status = EntitlementStatus.GRACE
    elif expires_at <= current:
        status = EntitlementStatus.EXPIRED
    elif transaction.auto_renew_enabled is False:
        status = EntitlementStatus.CANCELED
    else:
        status = EntitlementStatus.ACTIVE

    stable_event_id = event_id or (
        f"apple-transaction:{transaction.transaction_id}:"
        f"{status.value}:{int(verified_at.timestamp() * 1000)}"
    )
    return EntitlementProjection(
        user_id=normalized_user_id,
        source=EntitlementSource.APPLE_SUBSCRIPTION,
        external_event_id=stable_event_id,
        external_entitlement_id=transaction.original_transaction_id,
        event_type=event_type,
        occurred_at=verified_at,
        plan=Plan.PLUS,
        status=status,
        product_id=transaction.product_id,
        billing_period=billing_period,
        started_at=purchased_at,
        expires_at=expires_at,
        grace_expires_at=grace_expires_at,
        revoked_at=revoked_at,
        refunded_at=refunded_at,
        original_transaction_id=transaction.original_transaction_id,
        environment=transaction.environment.lower(),
        metadata={"transaction_id": transaction.transaction_id},
    )


@dataclass(frozen=True)
class VerifiedAppleNotification:
    """Decoded Notification V2 state after the signed payload was verified."""

    notification_uuid: str
    notification_type: str
    subtype: str | None
    signed_at: datetime
    transaction: VerifiedAppleTransaction

    def __post_init__(self) -> None:
        _require_text(self.notification_uuid, "Apple notification UUID")
        _require_text(self.notification_type, "Apple notification type")
        if not isinstance(self.transaction, VerifiedAppleTransaction):
            raise EntitlementProjectionError("Apple notification transaction must be verified.")


def project_verified_apple_notification(
    user_id: str,
    notification: VerifiedAppleNotification,
) -> EntitlementProjection:
    if not isinstance(notification, VerifiedAppleNotification):
        raise TypeError("A VerifiedAppleNotification is required; raw notification JSON is not accepted.")
    signed_at = _as_utc(notification.signed_at)
    assert signed_at is not None
    projection = project_verified_apple_transaction(
        user_id,
        notification.transaction,
        now=signed_at,
        event_id=notification.notification_uuid,
        event_type=notification.notification_type.upper(),
    )
    notification_type = notification.notification_type.upper()
    subtype = str(notification.subtype or "").upper()
    status = projection.status
    revoked_at = projection.revoked_at
    refunded_at = projection.refunded_at

    if notification_type == "REFUND":
        status = EntitlementStatus.REFUNDED
        refunded_at = signed_at
        revoked_at = None
    elif notification_type == "REVOKE":
        status = EntitlementStatus.REVOKED
        revoked_at = signed_at
        refunded_at = None
    elif notification_type in {"EXPIRED", "GRACE_PERIOD_EXPIRED"}:
        status = EntitlementStatus.EXPIRED
    elif notification_type == "DID_FAIL_TO_RENEW":
        status = (
            EntitlementStatus.GRACE
            if subtype == "GRACE_PERIOD" and projection.grace_expires_at
            else EntitlementStatus.EXPIRED
        )
    elif notification_type == "DID_CHANGE_RENEWAL_STATUS" and subtype == "AUTO_RENEW_DISABLED":
        status = EntitlementStatus.CANCELED
    elif notification_type in {
        "DID_RENEW",
        "DID_RECOVER",
        "OFFER_REDEEMED",
        "REFUND_REVERSED",
        "SUBSCRIBED",
    }:
        status = (
            EntitlementStatus.ACTIVE
            if projection.expires_at and projection.expires_at > signed_at
            else EntitlementStatus.EXPIRED
        )
        revoked_at = None
        refunded_at = None

    return EntitlementProjection(
        **{
            **projection.__dict__,
            "status": status,
            "revoked_at": revoked_at,
            "refunded_at": refunded_at,
            "metadata": {
                **projection.metadata,
                "notification_subtype": notification.subtype,
            },
        }
    )


@dataclass(frozen=True)
class VerifiedGooglePlayLegacyPurchase:
    """A legacy paid-app proof accepted only after a real Google verification."""

    verification_id: str
    verification_source: GooglePlayVerificationSource
    package_name: str
    purchase_token: str
    product_id: str
    purchased_at: datetime
    verified_at: datetime
    order_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.verification_id, "Google Play verification ID")
        _require_text(self.package_name, "Google Play package name")
        _require_text(self.purchase_token, "Google Play verified purchase evidence")
        _require_text(self.product_id, "Google Play product ID")


def project_verified_google_play_legacy_purchase(
    user_id: str,
    purchase: VerifiedGooglePlayLegacyPurchase,
    *,
    token_hash_secret: str,
    expected_package_name: str = GOOGLE_PLAY_PACKAGE_NAME,
) -> EntitlementProjection:
    """Prepare a Lifetime grant from verified evidence, never a client boolean."""

    if not isinstance(purchase, VerifiedGooglePlayLegacyPurchase):
        raise TypeError(
            "A VerifiedGooglePlayLegacyPurchase is required; client legacy-owner flags are not accepted."
        )
    normalized_user_id = _require_text(user_id, "HikeJournal user ID")
    secret = _require_text(token_hash_secret, "Legacy purchase token hash secret")
    if purchase.package_name != expected_package_name:
        raise EntitlementProjectionError("Google Play proof belongs to a different Android package.")
    purchase_token_hash = hmac.new(
        secret.encode("utf-8"),
        purchase.purchase_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    purchased_at = _as_utc(purchase.purchased_at)
    verified_at = _as_utc(purchase.verified_at)
    assert purchased_at and verified_at
    external_entitlement_id = purchase.order_id or purchase_token_hash
    return EntitlementProjection(
        user_id=normalized_user_id,
        source=EntitlementSource.GOOGLE_PLAY_LEGACY,
        external_event_id=f"google-play-legacy:{purchase.verification_id}",
        external_entitlement_id=external_entitlement_id,
        event_type="verified_legacy_paid_app",
        occurred_at=verified_at,
        plan=Plan.LIFETIME,
        status=EntitlementStatus.ACTIVE,
        product_id=purchase.product_id,
        billing_period=BillingPeriod.LIFETIME,
        started_at=purchased_at,
        expires_at=None,
        original_transaction_id=purchase.order_id,
        purchase_token_hash=purchase_token_hash,
        environment="production",
        metadata={
            "package_name": purchase.package_name,
            "verification_source": purchase.verification_source.value,
        },
    )


@dataclass(frozen=True)
class QuotaReservationDecision:
    allowed: bool
    idempotent: bool
    resource: QuotaResource
    resource_id: str
    plan: Plan
    limit: int | None
    used: int
    reserved: int
    remaining: int | None
    reservation_id: str | None = None
    reason: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> QuotaReservationDecision:
        raw_limit = payload.get("limit")
        raw_remaining = payload.get("remaining")
        return cls(
            allowed=bool(payload.get("allowed")),
            idempotent=bool(payload.get("idempotent")),
            resource=QuotaResource(str(payload["resource"])),
            resource_id=str(payload["resource_id"]),
            plan=Plan(str(payload.get("plan") or Plan.FREE.value)),
            limit=(int(raw_limit) if raw_limit is not None else None),
            used=max(0, int(payload.get("used") or 0)),
            reserved=max(0, int(payload.get("reserved") or 0)),
            remaining=(int(raw_remaining) if raw_remaining is not None else None),
            reservation_id=(
                str(payload["reservation_id"]) if payload.get("reservation_id") else None
            ),
            reason=(str(payload["reason"]) if payload.get("reason") else None),
        )


class SupabaseEntitlementStore:
    """Server-role persistence adapter for entitlement and quota RPCs."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def verify(self) -> None:
        try:
            self.client.table(ENTITLEMENT_TABLE).select("id").limit(1).execute()
            self.client.table(ENTITLEMENT_POLICY_TABLE).select("plan").limit(1).execute()
        except Exception as exc:
            raise EntitlementStoreError(
                "Entitlements need sql/entitlements_migration.sql before the mobile API can use them."
            ) from exc

    def list_entitlements(self, user_id: str) -> list[EntitlementRecord]:
        try:
            response = (
                self.client.table(ENTITLEMENT_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            raise EntitlementStoreError("Could not read the account entitlement.") from exc
        return [EntitlementRecord.from_row(row) for row in (response.data or [])]

    def load_policy(self) -> EntitlementPolicy:
        try:
            response = self.client.table(ENTITLEMENT_POLICY_TABLE).select("*").execute()
        except Exception as exc:
            raise EntitlementStoreError("Could not read the entitlement policy.") from exc
        return policy_from_rows(response.data or [])

    def usage(self, user_id: str) -> EntitlementUsage:
        counts: dict[str, int] = {}
        try:
            for resource in QuotaResource:
                response = self.client.rpc(
                    ENTITLEMENT_USAGE_RPC,
                    {"p_user_id": user_id, "p_resource_type": resource.value},
                ).execute()
                counts[resource.value] = _scalar_int(response.data)
        except Exception as exc:
            raise EntitlementStoreError("Could not read cloud quota usage.") from exc
        return EntitlementUsage.from_mapping(counts)

    def apply(self, projection: EntitlementProjection) -> dict[str, Any]:
        try:
            response = self.client.rpc(
                ENTITLEMENT_PROJECTION_RPC,
                projection.to_rpc_params(),
            ).execute()
        except Exception as exc:
            raise EntitlementStoreError("Could not apply the verified entitlement event.") from exc
        return _scalar_mapping(response.data)

    def resolve_apple_original_transaction_user_id(
        self,
        original_transaction_id: str,
    ) -> str | None:
        """Resolve a later Apple notification only through an existing link."""

        normalized = str(original_transaction_id or "").strip()
        if not normalized:
            raise EntitlementStoreError("An Apple original transaction ID is required.")
        try:
            response = (
                self.client.table(ENTITLEMENT_TABLE)
                .select("user_id")
                .eq("source", EntitlementSource.APPLE_SUBSCRIPTION.value)
                .eq("original_transaction_id", normalized)
                .limit(2)
                .execute()
            )
        except Exception as exc:
            raise EntitlementStoreError(
                "Could not resolve the Apple subscription account."
            ) from exc
        rows = response.data or []
        if not rows:
            return None
        if len(rows) != 1 or not rows[0].get("user_id"):
            raise EntitlementStoreError(
                "Apple original transaction linkage is not unique."
            )
        return str(rows[0]["user_id"])

    def reserve(
        self,
        *,
        user_id: str,
        resource: QuotaResource,
        request_id: str,
        resource_id: str,
        ttl_seconds: int = 900,
    ) -> QuotaReservationDecision:
        try:
            response = self.client.rpc(
                ENTITLEMENT_RESERVATION_RPC,
                {
                    "p_user_id": user_id,
                    "p_resource_type": resource.value,
                    "p_request_id": request_id,
                    "p_resource_id": resource_id,
                    "p_ttl_seconds": max(60, min(int(ttl_seconds), 3600)),
                },
            ).execute()
        except Exception as exc:
            raise EntitlementStoreError("Could not reserve cloud quota.") from exc
        return QuotaReservationDecision.from_payload(_scalar_mapping(response.data))

    def release(
        self,
        *,
        user_id: str,
        resource: QuotaResource,
        request_id: str,
    ) -> bool:
        try:
            response = self.client.rpc(
                ENTITLEMENT_RELEASE_RPC,
                {
                    "p_user_id": user_id,
                    "p_resource_type": resource.value,
                    "p_request_id": request_id,
                },
            ).execute()
        except Exception as exc:
            raise EntitlementStoreError("Could not release cloud quota.") from exc
        payload = _scalar_mapping(response.data)
        return bool(payload.get("released"))


def _scalar_int(value: Any) -> int:
    if isinstance(value, list):
        value = value[0] if value else 0
    if isinstance(value, Mapping):
        value = next(iter(value.values()), 0)
    return int(value or 0)


def _scalar_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        value = value[0] if value else {}
    if not isinstance(value, Mapping):
        raise EntitlementStoreError("The entitlement database returned an invalid payload.")
    return dict(value)


class EntitlementService:
    def __init__(self, store: SupabaseEntitlementStore) -> None:
        self.store = store

    def snapshot(self, user_id: str, *, now: datetime | None = None) -> EntitlementSnapshot:
        policy = self.store.load_policy()
        decision = resolve_entitlement(self.store.list_entitlements(user_id), now=now)
        return EntitlementSnapshot(
            decision=decision,
            plan_policy=policy.for_plan(decision.plan),
            policy=policy,
            usage=self.store.usage(user_id),
        )

    def apply_projection(self, projection: EntitlementProjection) -> dict[str, Any]:
        return self.store.apply(projection)

    def reserve_quota(
        self,
        *,
        user_id: str,
        resource: QuotaResource,
        request_id: str,
        resource_id: str,
        ttl_seconds: int = 900,
    ) -> QuotaReservationDecision:
        return self.store.reserve(
            user_id=user_id,
            resource=resource,
            request_id=request_id,
            resource_id=resource_id,
            ttl_seconds=ttl_seconds,
        )

    def release_quota(
        self,
        *,
        user_id: str,
        resource: QuotaResource,
        request_id: str,
    ) -> bool:
        return self.store.release(
            user_id=user_id,
            resource=resource,
            request_id=request_id,
        )
