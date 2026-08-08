from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import logging
import os
from threading import RLock
from typing import Any
from uuid import UUID, uuid4


logger = logging.getLogger(__name__)

MOBILE_JOB_TABLE = "mobile_api_jobs"
MOBILE_JOB_RECOVERY_PAGE_SIZE = 250
TERMINAL_JOB_STATES = frozenset({"completed", "failed", "cancelled"})


class MobileJobStoreError(RuntimeError):
    """Raised when durable mobile job state cannot be read or written."""


class MobileJobIdempotencyConflict(MobileJobStoreError):
    """Raised when one request ID is reused for different logical work."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def is_durable_mobile_job_id(value: str) -> bool:
    """Return whether *value* is a canonical UUID used by durable job rows."""
    try:
        return str(UUID(value)) == value.lower()
    except (AttributeError, TypeError, ValueError):
        return False


def mobile_job_owner_key(owner_context: dict[str, Any]) -> str:
    """Return a stable, non-identifying lookup key for the current owner."""
    subject = str(owner_context.get("subject") or "").strip()
    email = str(owner_context.get("email") or "").strip().lower()
    mode = str(owner_context.get("mode") or "").strip()
    # A configured immutable subject survives email and auth-mode changes. The
    # email is the legacy single-owner fallback until Track B introduces users.
    normalized = {"subject": subject} if subject else {"email": email or None, "mode": mode or None}
    serialized = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def mobile_job_request_fingerprint(request_payload: dict[str, Any]) -> str:
    normalized = deepcopy(request_payload)
    # The request ID selects the ledger row; it is not part of the work itself,
    # and older persisted payloads did not duplicate it inside request_payload.
    normalized.pop("client_request_id", None)
    serialized = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def mobile_job_persistence_required() -> bool:
    """Require Supabase persistence on hosted deployments, allow local fallback."""
    explicit = os.getenv("MOBILE_JOB_STORE_REQUIRED", "").strip().lower()
    hosted_token_policy = os.getenv("MOBILE_REQUIRE_EXPLICIT_TOKEN", "").strip().lower()
    hosted = hosted_token_policy in {"1", "true", "yes", "on"} or bool(
        os.getenv("K_SERVICE", "").strip()
    )
    if hosted:
        return True
    return explicit in {"1", "true", "yes", "on"} if explicit else False


@dataclass(frozen=True)
class MobileJobRecord:
    job_id: str
    job_type: str
    owner_scope: str
    owner_key: str
    client_request_id: str | None
    payload: dict[str, Any]
    request_payload: dict[str, Any]
    request_fingerprint: str | None = None
    state: str = "queued"
    attempt_count: int = 0
    max_attempts: int = 3
    next_attempt_at: datetime | None = None
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None

    def snapshot(self) -> MobileJobRecord:
        return MobileJobRecord(
            job_id=self.job_id,
            job_type=self.job_type,
            owner_scope=self.owner_scope,
            owner_key=self.owner_key,
            client_request_id=self.client_request_id,
            payload=deepcopy(self.payload),
            request_payload=deepcopy(self.request_payload),
            request_fingerprint=self.request_fingerprint,
            state=self.state,
            attempt_count=self.attempt_count,
            max_attempts=self.max_attempts,
            next_attempt_at=self.next_attempt_at,
            lease_owner=self.lease_owner,
            lease_expires_at=self.lease_expires_at,
            last_error=self.last_error,
            created_at=self.created_at,
            updated_at=self.updated_at,
            completed_at=self.completed_at,
        )


def is_mobile_job_recoverable(
    record: MobileJobRecord,
    *,
    now: datetime | None = None,
) -> bool:
    """Apply the recovery-state rules shared by point lookups and queue scans."""
    current_time = now or utc_now()
    if record.state == "queued":
        return record.attempt_count < record.max_attempts
    if record.state == "failed":
        return (
            record.attempt_count < record.max_attempts
            and record.next_attempt_at is not None
            and record.next_attempt_at <= current_time
        )
    if record.state == "running":
        # Include an expired final attempt so the dispatcher can turn the
        # abandoned running row into an operator-attention failure.
        return (
            record.lease_expires_at is not None
            and record.lease_expires_at <= current_time
        )
    return False


def validate_mobile_job_request(
    existing: MobileJobRecord,
    request_payload: dict[str, Any],
) -> None:
    expected = existing.request_fingerprint or mobile_job_request_fingerprint(
        existing.request_payload
    )
    actual = mobile_job_request_fingerprint(request_payload)
    if not hmac_compare_digest(expected, actual):
        raise MobileJobIdempotencyConflict(
            "This client request ID was already used for different background work."
        )


def hmac_compare_digest(left: str, right: str) -> bool:
    # Kept local to avoid comparing potentially malformed persisted values with
    # ordinary equality timing. Fingerprints themselves contain no user data.
    import hmac

    return hmac.compare_digest(left, right)


def _summarize_job_metrics(
    records: list[dict[str, Any]],
    *,
    durable: bool,
    sample_truncated: bool,
) -> dict[str, Any]:
    """Return bounded, non-identifying queue telemetry for operator endpoints."""
    now = utc_now()
    state_counts: dict[str, int] = {}
    job_type_counts: dict[str, int] = {}
    retry_wait_count = 0
    needs_attention_count = 0
    retry_attempt_count = 0
    active_created_at: list[datetime] = []
    for item in records:
        state = str(item.get("state") or "unknown")
        job_type = str(item.get("job_type") or "unknown")
        attempts = int(item.get("attempt_count") or 0)
        max_attempts = max(1, int(item.get("max_attempts") or 1))
        next_attempt_at = _parse_datetime(item.get("next_attempt_at"))
        created_at = _parse_datetime(item.get("created_at"))
        state_counts[state] = state_counts.get(state, 0) + 1
        job_type_counts[job_type] = job_type_counts.get(job_type, 0) + 1
        retry_attempt_count += max(0, attempts - 1)

        retry_wait = state == "failed" and next_attempt_at is not None and attempts < max_attempts
        needs_attention = state == "failed" and not retry_wait
        if retry_wait:
            retry_wait_count += 1
        if needs_attention:
            needs_attention_count += 1
        if state in {"queued", "running"} or retry_wait:
            if created_at:
                active_created_at.append(created_at)

    oldest_active_age_seconds = None
    if active_created_at:
        oldest_active_age_seconds = round(
            max(0.0, (now - min(active_created_at)).total_seconds()),
            1,
        )
    return {
        "durable": durable,
        "sampled_job_count": len(records),
        "sample_truncated": sample_truncated,
        "state_counts": dict(sorted(state_counts.items())),
        "job_type_counts": dict(sorted(job_type_counts.items())),
        "retry_wait_count": retry_wait_count,
        "needs_attention_count": needs_attention_count,
        "retry_attempt_count": retry_attempt_count,
        "oldest_active_age_seconds": oldest_active_age_seconds,
    }


class MobileJobStore(ABC):
    """Persistence boundary for asynchronous mobile API work."""

    @abstractmethod
    def verify(self) -> None:
        """Verify that the backing store is available and migrated."""

    @abstractmethod
    def create(
        self,
        *,
        job_type: str,
        owner_scope: str,
        owner_key: str,
        client_request_id: str | None,
        payload: dict[str, Any],
        request_payload: dict[str, Any],
        job_id: str | None = None,
        max_attempts: int = 3,
    ) -> tuple[MobileJobRecord, bool]:
        """Create a job, or return its idempotent predecessor."""

    @abstractmethod
    def get(self, job_id: str) -> MobileJobRecord | None:
        pass

    @abstractmethod
    def find_by_client_request(
        self,
        *,
        job_type: str,
        owner_scope: str,
        owner_key: str,
        client_request_id: str,
    ) -> MobileJobRecord | None:
        pass

    @abstractmethod
    def update(
        self,
        job_id: str,
        *,
        expected_lease_owner: str | None = None,
        lease_seconds: int = 1800,
        **payload_updates: Any,
    ) -> MobileJobRecord | None:
        pass

    @abstractmethod
    def acquire_lease(
        self,
        job_id: str,
        *,
        lease_owner: str,
        lease_seconds: int = 300,
    ) -> MobileJobRecord | None:
        """Atomically claim queued, retryable, or abandoned work."""

    @abstractmethod
    def mark_retryable(
        self,
        job_id: str,
        *,
        error: str,
        retry_after_seconds: int,
        expected_lease_owner: str | None = None,
    ) -> MobileJobRecord | None:
        pass

    @abstractmethod
    def fail_expired_lease(
        self,
        job_id: str,
        *,
        expected_lease_owner: str,
        error: str,
    ) -> MobileJobRecord | None:
        """Move an abandoned running job to attention only if its lease is still expired."""

    @abstractmethod
    def list_recoverable(self, *, job_types: set[str] | None = None) -> list[MobileJobRecord]:
        """Return queued/retryable jobs and jobs whose worker lease expired."""

    @abstractmethod
    def operational_metrics(self) -> dict[str, Any]:
        """Return bounded queue health data without request/result content."""


class InMemoryMobileJobStore(MobileJobStore):
    """Thread-safe local/test fallback; never selected silently in production."""

    def __init__(self, records: list[MobileJobRecord] | None = None) -> None:
        self._lock = RLock()
        self._records = {record.job_id: record.snapshot() for record in records or []}

    def verify(self) -> None:
        return None

    def create(
        self,
        *,
        job_type: str,
        owner_scope: str,
        owner_key: str,
        client_request_id: str | None,
        payload: dict[str, Any],
        request_payload: dict[str, Any],
        job_id: str | None = None,
        max_attempts: int = 3,
    ) -> tuple[MobileJobRecord, bool]:
        with self._lock:
            request_fingerprint = mobile_job_request_fingerprint(request_payload)
            if client_request_id:
                existing = self.find_by_client_request(
                    job_type=job_type,
                    owner_scope=owner_scope,
                    owner_key=owner_key,
                    client_request_id=client_request_id,
                )
                if existing:
                    validate_mobile_job_request(existing, request_payload)
                    return existing, False
            now = utc_now()
            record = MobileJobRecord(
                job_id=job_id or str(uuid4()),
                job_type=job_type,
                owner_scope=owner_scope,
                owner_key=owner_key,
                client_request_id=client_request_id,
                payload=deepcopy(payload),
                request_payload=deepcopy(request_payload),
                request_fingerprint=request_fingerprint,
                state=str(payload.get("state") or "queued"),
                max_attempts=max(1, int(max_attempts)),
                created_at=now,
                updated_at=now,
            )
            self._records[record.job_id] = record
            return record.snapshot(), True

    def get(self, job_id: str) -> MobileJobRecord | None:
        with self._lock:
            record = self._records.get(job_id)
            return record.snapshot() if record else None

    def find_by_client_request(
        self,
        *,
        job_type: str,
        owner_scope: str,
        owner_key: str,
        client_request_id: str,
    ) -> MobileJobRecord | None:
        with self._lock:
            record = next(
                (
                    item
                    for item in self._records.values()
                    if item.job_type == job_type
                    and item.owner_scope == owner_scope
                    and item.owner_key == owner_key
                    and item.client_request_id == client_request_id
                ),
                None,
            )
            return record.snapshot() if record else None

    def update(
        self,
        job_id: str,
        *,
        expected_lease_owner: str | None = None,
        lease_seconds: int = 1800,
        **payload_updates: Any,
    ) -> MobileJobRecord | None:
        with self._lock:
            current = self._records.get(job_id)
            if not current:
                return None
            if expected_lease_owner and (
                current.state != "running" or current.lease_owner != expected_lease_owner
            ):
                return None
            payload = deepcopy(current.payload)
            payload.update(deepcopy(payload_updates))
            state = (
                str(payload_updates.get("state") or current.state)
                if "state" in payload_updates
                else current.state
            )
            terminal_transition = "state" in payload_updates and state in TERMINAL_JOB_STATES
            now = utc_now()
            updated = MobileJobRecord(
                **{
                    **current.__dict__,
                    "payload": payload,
                    "state": state,
                    "last_error": (
                        str(payload_updates.get("error") or "").strip() or None
                        if "error" in payload_updates
                        else current.last_error
                    ),
                    "lease_owner": None if terminal_transition else current.lease_owner,
                    "lease_expires_at": (
                        None
                        if terminal_transition
                        else (
                            now + timedelta(seconds=max(1, lease_seconds))
                            if expected_lease_owner
                            else current.lease_expires_at
                        )
                    ),
                    "next_attempt_at": None if terminal_transition else current.next_attempt_at,
                    "completed_at": now if terminal_transition else current.completed_at,
                    "updated_at": now,
                }
            )
            self._records[job_id] = updated
            return updated.snapshot()

    def acquire_lease(
        self,
        job_id: str,
        *,
        lease_owner: str,
        lease_seconds: int = 300,
    ) -> MobileJobRecord | None:
        with self._lock:
            current = self._records.get(job_id)
            if not current or current.attempt_count >= current.max_attempts:
                return None
            now = utc_now()
            claimable = current.state == "queued"
            claimable = claimable or (
                current.state == "failed"
                and current.next_attempt_at is not None
                and current.next_attempt_at <= now
            )
            claimable = claimable or (
                current.state == "running"
                and current.lease_expires_at is not None
                and current.lease_expires_at <= now
            )
            if not claimable:
                return None
            payload = deepcopy(current.payload)
            payload["state"] = "running"
            updated = MobileJobRecord(
                **{
                    **current.__dict__,
                    "payload": payload,
                    "state": "running",
                    "attempt_count": current.attempt_count + 1,
                    "next_attempt_at": None,
                    "lease_owner": lease_owner,
                    "lease_expires_at": now + timedelta(seconds=max(1, lease_seconds)),
                    "updated_at": now,
                }
            )
            self._records[job_id] = updated
            return updated.snapshot()

    def mark_retryable(
        self,
        job_id: str,
        *,
        error: str,
        retry_after_seconds: int,
        expected_lease_owner: str | None = None,
    ) -> MobileJobRecord | None:
        with self._lock:
            current = self._records.get(job_id)
            if not current:
                return None
            if expected_lease_owner and (
                current.state != "running" or current.lease_owner != expected_lease_owner
            ):
                return None
            now = utc_now()
            payload = deepcopy(current.payload)
            # Keep the established mobile contract polling while the durable
            # row records the internal failed/backoff state.
            payload.update(state="queued", error=error)
            updated = MobileJobRecord(
                **{
                    **current.__dict__,
                    "payload": payload,
                    "state": "failed",
                    "last_error": error,
                    "next_attempt_at": now + timedelta(seconds=max(0, retry_after_seconds)),
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "completed_at": None,
                    "updated_at": now,
                }
            )
            self._records[job_id] = updated
            return updated.snapshot()

    def fail_expired_lease(
        self,
        job_id: str,
        *,
        expected_lease_owner: str,
        error: str,
    ) -> MobileJobRecord | None:
        with self._lock:
            current = self._records.get(job_id)
            now = utc_now()
            if (
                not current
                or current.state != "running"
                or current.lease_owner != expected_lease_owner
                or current.lease_expires_at is None
                or current.lease_expires_at > now
            ):
                return None
            return self.update(
                job_id,
                expected_lease_owner=expected_lease_owner,
                state="failed",
                error=error,
            )

    def list_recoverable(self, *, job_types: set[str] | None = None) -> list[MobileJobRecord]:
        with self._lock:
            records = [
                item.snapshot()
                for item in self._records.values()
                if (not job_types or item.job_type in job_types)
                and is_mobile_job_recoverable(item)
            ]
        return sorted(records, key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC))

    def operational_metrics(self) -> dict[str, Any]:
        with self._lock:
            records = [
                {
                    "job_type": item.job_type,
                    "state": item.state,
                    "attempt_count": item.attempt_count,
                    "max_attempts": item.max_attempts,
                    "next_attempt_at": item.next_attempt_at,
                    "created_at": item.created_at,
                }
                for item in self._records.values()
            ]
        return _summarize_job_metrics(
            records,
            durable=False,
            sample_truncated=False,
        )


class SupabaseMobileJobStore(MobileJobStore):
    """Supabase-backed durable job and idempotency repository."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def verify(self) -> None:
        try:
            self.client.table(MOBILE_JOB_TABLE).select("id").limit(1).execute()
            missing_job_id = "00000000-0000-0000-0000-000000000000"
            self.client.rpc(
                "update_mobile_api_job",
                {
                    "p_job_id": missing_job_id,
                    "p_payload_updates": {},
                    "p_expected_lease_owner": None,
                    "p_lease_seconds": 1,
                },
            ).execute()
            self.client.rpc(
                "claim_mobile_api_job",
                {
                    "p_job_id": missing_job_id,
                    "p_lease_owner": "startup-verification",
                    "p_lease_seconds": 1,
                },
            ).execute()
            self.client.rpc(
                "fail_expired_mobile_api_job",
                {
                    "p_job_id": missing_job_id,
                    "p_expected_lease_owner": "startup-verification",
                    "p_error": "startup verification",
                },
            ).execute()
        except Exception as exc:
            raise MobileJobStoreError(
                "Durable mobile jobs need sql/mobile_jobs_migration.sql before the mobile API can start."
            ) from exc

    @staticmethod
    def _from_row(row: dict[str, Any]) -> MobileJobRecord:
        return MobileJobRecord(
            job_id=str(row["id"]),
            job_type=str(row["job_type"]),
            owner_scope=str(row.get("owner_scope") or "single-owner"),
            owner_key=str(row["owner_key"]),
            client_request_id=(str(row["client_request_id"]) if row.get("client_request_id") else None),
            payload=deepcopy(row.get("payload") or {}),
            request_payload=deepcopy(row.get("request_payload") or {}),
            request_fingerprint=(
                str(row["request_fingerprint"])
                if row.get("request_fingerprint")
                else None
            ),
            state=str(row.get("state") or "queued"),
            attempt_count=int(row.get("attempt_count") or 0),
            max_attempts=int(row.get("max_attempts") or 3),
            next_attempt_at=_parse_datetime(row.get("next_attempt_at")),
            lease_owner=(str(row["lease_owner"]) if row.get("lease_owner") else None),
            lease_expires_at=_parse_datetime(row.get("lease_expires_at")),
            last_error=(str(row["last_error"]) if row.get("last_error") else None),
            created_at=_parse_datetime(row.get("created_at")),
            updated_at=_parse_datetime(row.get("updated_at")),
            completed_at=_parse_datetime(row.get("completed_at")),
        )

    def create(
        self,
        *,
        job_type: str,
        owner_scope: str,
        owner_key: str,
        client_request_id: str | None,
        payload: dict[str, Any],
        request_payload: dict[str, Any],
        job_id: str | None = None,
        max_attempts: int = 3,
    ) -> tuple[MobileJobRecord, bool]:
        request_fingerprint = mobile_job_request_fingerprint(request_payload)
        if client_request_id:
            existing = self.find_by_client_request(
                job_type=job_type,
                owner_scope=owner_scope,
                owner_key=owner_key,
                client_request_id=client_request_id,
            )
            if existing:
                validate_mobile_job_request(existing, request_payload)
                return existing, False
        row = {
            "id": job_id or str(uuid4()),
            "job_type": job_type,
            "owner_scope": owner_scope,
            "owner_key": owner_key,
            "client_request_id": client_request_id,
            "state": str(payload.get("state") or "queued"),
            "payload": deepcopy(payload),
            "request_payload": deepcopy(request_payload),
            "request_fingerprint": request_fingerprint,
            "max_attempts": max(1, int(max_attempts)),
        }
        try:
            response = self.client.table(MOBILE_JOB_TABLE).insert(row).execute()
        except Exception as exc:
            # The partial unique index is the final arbiter for concurrent
            # retries that both missed the optimistic lookup above.
            if client_request_id:
                existing = self.find_by_client_request(
                    job_type=job_type,
                    owner_scope=owner_scope,
                    owner_key=owner_key,
                    client_request_id=client_request_id,
                )
                if existing:
                    validate_mobile_job_request(existing, request_payload)
                    return existing, False
            raise MobileJobStoreError("Could not persist the mobile background job.") from exc
        rows = response.data or []
        if not rows:
            persisted = self.get(str(row["id"]))
            if persisted:
                return persisted, True
            raise MobileJobStoreError("The mobile background job was not returned after creation.")
        return self._from_row(rows[0]), True

    def get(self, job_id: str) -> MobileJobRecord | None:
        if not is_durable_mobile_job_id(job_id):
            return None
        try:
            response = (
                self.client.table(MOBILE_JOB_TABLE)
                .select("*")
                .eq("id", job_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise MobileJobStoreError("Could not read the mobile background job.") from exc
        rows = response.data or []
        return self._from_row(rows[0]) if rows else None

    def find_by_client_request(
        self,
        *,
        job_type: str,
        owner_scope: str,
        owner_key: str,
        client_request_id: str,
    ) -> MobileJobRecord | None:
        try:
            response = (
                self.client.table(MOBILE_JOB_TABLE)
                .select("*")
                .eq("job_type", job_type)
                .eq("owner_scope", owner_scope)
                .eq("owner_key", owner_key)
                .eq("client_request_id", client_request_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise MobileJobStoreError("Could not check the mobile request idempotency key.") from exc
        rows = response.data or []
        return self._from_row(rows[0]) if rows else None

    def update(
        self,
        job_id: str,
        *,
        expected_lease_owner: str | None = None,
        lease_seconds: int = 1800,
        **payload_updates: Any,
    ) -> MobileJobRecord | None:
        try:
            response = self.client.rpc(
                "update_mobile_api_job",
                {
                    "p_job_id": job_id,
                    "p_payload_updates": deepcopy(payload_updates),
                    "p_expected_lease_owner": expected_lease_owner,
                    "p_lease_seconds": max(1, int(lease_seconds)),
                },
            ).execute()
        except Exception as exc:
            raise MobileJobStoreError("Could not update the mobile background job.") from exc
        rows = response.data or []
        return self._from_row(rows[0]) if rows else None

    def acquire_lease(
        self,
        job_id: str,
        *,
        lease_owner: str,
        lease_seconds: int = 300,
    ) -> MobileJobRecord | None:
        try:
            response = self.client.rpc(
                "claim_mobile_api_job",
                {
                    "p_job_id": job_id,
                    "p_lease_owner": lease_owner,
                    "p_lease_seconds": max(1, int(lease_seconds)),
                },
            ).execute()
        except Exception as exc:
            raise MobileJobStoreError("Could not claim the durable mobile background job.") from exc
        rows = response.data or []
        return self._from_row(rows[0]) if rows else None

    def mark_retryable(
        self,
        job_id: str,
        *,
        error: str,
        retry_after_seconds: int,
        expected_lease_owner: str | None = None,
    ) -> MobileJobRecord | None:
        current = self.get(job_id)
        if not current:
            return None
        now = utc_now()
        payload = deepcopy(current.payload)
        # The APK already polls queued/running states; keep that public state
        # while the row-level state and next_attempt_at drive safe backoff.
        payload.update(state="queued", error=error)
        update_row = {
            "payload": payload,
            "state": "failed",
            "last_error": error,
            "next_attempt_at": _iso(now + timedelta(seconds=max(0, retry_after_seconds))),
            "lease_owner": None,
            "lease_expires_at": None,
            "completed_at": None,
            "updated_at": _iso(now),
        }
        try:
            query = self.client.table(MOBILE_JOB_TABLE).update(update_row).eq("id", job_id)
            if expected_lease_owner:
                query = query.eq("state", "running").eq("lease_owner", expected_lease_owner)
            response = query.execute()
        except Exception as exc:
            raise MobileJobStoreError("Could not schedule the mobile background job retry.") from exc
        rows = response.data or []
        if rows:
            return self._from_row(rows[0])
        return None if expected_lease_owner else self.get(job_id)

    def fail_expired_lease(
        self,
        job_id: str,
        *,
        expected_lease_owner: str,
        error: str,
    ) -> MobileJobRecord | None:
        try:
            response = self.client.rpc(
                "fail_expired_mobile_api_job",
                {
                    "p_job_id": job_id,
                    "p_expected_lease_owner": expected_lease_owner,
                    "p_error": error,
                },
            ).execute()
        except Exception as exc:
            raise MobileJobStoreError(
                "Could not move the expired mobile background job to attention."
            ) from exc
        rows = response.data or []
        return self._from_row(rows[0]) if rows else None

    def list_recoverable(self, *, job_types: set[str] | None = None) -> list[MobileJobRecord]:
        now = utc_now()
        due_before = now.astimezone(UTC).isoformat()
        rows: list[dict[str, Any]] = []
        try:
            for state, due_field in (
                ("queued", None),
                ("failed", "next_attempt_at"),
                ("running", "lease_expires_at"),
            ):
                query = (
                    self.client.table(MOBILE_JOB_TABLE)
                    .select("*")
                    .eq("state", state)
                )
                if job_types:
                    query = query.in_("job_type", sorted(job_types))
                if due_field:
                    query = query.lte(due_field, due_before)
                response = (
                    query.order("created_at")
                    .limit(MOBILE_JOB_RECOVERY_PAGE_SIZE)
                    .execute()
                )
                rows.extend(response.data or [])
        except Exception as exc:
            raise MobileJobStoreError("Could not list recoverable mobile background jobs.") from exc
        records = [self._from_row(row) for row in rows]
        recoverable = [
            item
            for item in records
            if (not job_types or item.job_type in job_types)
            and is_mobile_job_recoverable(item, now=now)
        ]
        return sorted(
            recoverable,
            key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC),
        )

    def operational_metrics(self) -> dict[str, Any]:
        sample_limit = 1000
        fields = (
            "job_type,state,attempt_count,max_attempts,"
            "next_attempt_at,created_at"
        )
        try:
            response = (
                self.client.table(MOBILE_JOB_TABLE)
                .select(fields)
                .limit(sample_limit)
                .execute()
            )
        except Exception as exc:
            raise MobileJobStoreError("Could not read mobile job operational metrics.") from exc
        records = list(response.data or [])
        return _summarize_job_metrics(
            records,
            durable=True,
            sample_truncated=len(records) >= sample_limit,
        )


def build_mobile_job_store(
    client: Any,
    *,
    require_persistence: bool | None = None,
) -> MobileJobStore:
    required = mobile_job_persistence_required() if require_persistence is None else require_persistence
    store = SupabaseMobileJobStore(client)
    try:
        store.verify()
    except MobileJobStoreError:
        if required:
            raise
        logger.warning(
            "Durable mobile job storage is unavailable; using the process-local fallback. "
            "Apply sql/mobile_jobs_migration.sql before relying on background work."
        )
        return InMemoryMobileJobStore()
    return store
