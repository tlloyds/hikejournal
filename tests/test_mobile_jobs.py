from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import BackgroundTasks, HTTPException

from hike_journal.services import mobile_jobs
from hike_journal.services.mobile_jobs import (
    InMemoryMobileJobStore,
    MobileJobRecord,
    MobileJobStoreError,
    build_mobile_job_store,
    mobile_job_owner_key,
    mobile_job_persistence_required,
)
from hike_journal.services.inat import InatRequestError
import mobile_api
from mobile_api import ReviewBatchGroupInput, ReviewBatchInput


OWNER_SCOPE = "single-owner"
OWNER_KEY = "a" * 64


def create_job(
    store: InMemoryMobileJobStore,
    *,
    job_type: str = "species-review-batch",
    request_id: str | None = "request-1",
    job_id: str = "00000000-0000-0000-0000-000000000001",
) -> tuple[MobileJobRecord, bool]:
    return store.create(
        job_type=job_type,
        owner_scope=OWNER_SCOPE,
        owner_key=OWNER_KEY,
        client_request_id=request_id,
        payload={"job_id": job_id, "state": "queued", "items": []},
        request_payload={"groups": [{"photo_ids": ["photo-1"]}]},
        job_id=job_id,
    )


def test_job_payloads_are_copied_at_the_store_boundary() -> None:
    store = InMemoryMobileJobStore()
    record, created = create_job(store)

    assert created is True
    record.payload["items"].append("local-mutation")
    reloaded = store.get(record.job_id)

    assert reloaded is not None
    assert reloaded.payload["items"] == []


def test_duplicate_client_request_is_idempotent_but_other_job_types_are_independent() -> None:
    store = InMemoryMobileJobStore()
    first, first_created = create_job(store)
    duplicate, duplicate_created = store.create(
        job_type="species-review-batch",
        owner_scope=OWNER_SCOPE,
        owner_key=OWNER_KEY,
        client_request_id="request-1",
        payload={"job_id": "different", "state": "queued"},
        request_payload={"groups": [{"photo_ids": ["photo-1"]}]},
    )
    publish, publish_created = create_job(
        store,
        job_type="species-publish-batch",
        job_id="00000000-0000-0000-0000-000000000002",
    )

    assert first_created is True
    assert duplicate_created is False
    assert duplicate.job_id == first.job_id
    assert duplicate.request_payload == first.request_payload
    assert publish_created is True
    assert publish.job_id != first.job_id


def test_same_client_request_id_rejects_different_work() -> None:
    store = InMemoryMobileJobStore()
    create_job(store)

    with pytest.raises(MobileJobStoreError, match="already used for different"):
        store.create(
            job_type="species-review-batch",
            owner_scope=OWNER_SCOPE,
            owner_key=OWNER_KEY,
            client_request_id="request-1",
            payload={"job_id": "different", "state": "queued"},
            request_payload={"groups": [{"photo_ids": ["photo-2"]}]},
        )


def test_same_request_id_is_independent_across_owner_scopes() -> None:
    store = InMemoryMobileJobStore()
    first, _ = create_job(store)
    second, created = store.create(
        job_type=first.job_type,
        owner_scope="future-user-account",
        owner_key=OWNER_KEY,
        client_request_id=first.client_request_id,
        payload={"job_id": "00000000-0000-0000-0000-000000000003", "state": "queued"},
        request_payload={},
        job_id="00000000-0000-0000-0000-000000000003",
    )

    assert created is True
    assert second.job_id != first.job_id


def test_persisted_record_supports_status_lookup_after_process_restart() -> None:
    first_process = InMemoryMobileJobStore()
    record, _ = create_job(first_process)
    first_process.update(record.job_id, state="completed", items=[{"id": "photo-1"}])

    durable_snapshot = first_process.get(record.job_id)
    assert durable_snapshot is not None
    second_process = InMemoryMobileJobStore(records=[durable_snapshot])

    recovered = second_process.get(record.job_id)
    assert recovered is not None
    assert recovered.state == "completed"
    assert recovered.payload["items"] == [{"id": "photo-1"}]
    assert recovered.request_payload["groups"][0]["photo_ids"] == ["photo-1"]


def test_lease_is_exclusive_until_it_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now)
    store = InMemoryMobileJobStore()
    record, _ = create_job(store)

    first_claim = store.acquire_lease(record.job_id, lease_owner="worker-a", lease_seconds=60)
    competing_claim = store.acquire_lease(record.job_id, lease_owner="worker-b", lease_seconds=60)

    assert first_claim is not None
    assert first_claim.attempt_count == 1
    assert first_claim.lease_owner == "worker-a"
    assert competing_claim is None

    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now + timedelta(seconds=61))
    recovered_claim = store.acquire_lease(record.job_id, lease_owner="worker-b", lease_seconds=60)

    assert recovered_claim is not None
    assert recovered_claim.attempt_count == 2
    assert recovered_claim.lease_owner == "worker-b"


def test_retry_metadata_only_becomes_recoverable_when_due(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now)
    store = InMemoryMobileJobStore()
    record, _ = create_job(store)
    store.acquire_lease(record.job_id, lease_owner="worker-a")
    failed = store.mark_retryable(
        record.job_id,
        error="iNaturalist is temporarily unavailable",
        retry_after_seconds=30,
    )

    assert failed is not None
    assert failed.state == "failed"
    assert failed.payload["state"] == "queued"
    assert failed.last_error == "iNaturalist is temporarily unavailable"
    assert failed.next_attempt_at == now + timedelta(seconds=30)
    assert store.list_recoverable() == []

    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now + timedelta(seconds=31))
    recoverable = store.list_recoverable()

    assert [item.job_id for item in recoverable] == [record.job_id]


def test_completed_job_cannot_be_reclaimed() -> None:
    store = InMemoryMobileJobStore()
    record, _ = create_job(store)
    store.acquire_lease(record.job_id, lease_owner="worker-a")
    completed = store.update(record.job_id, state="completed", error=None)

    assert completed is not None
    assert completed.completed_at is not None
    assert completed.lease_owner is None
    assert store.acquire_lease(record.job_id, lease_owner="worker-b") is None
    assert store.list_recoverable() == []


class BrokenSupabaseClient:
    def table(self, _name: str):
        raise RuntimeError("relation does not exist")


def test_local_store_falls_back_when_migration_is_unavailable() -> None:
    store = build_mobile_job_store(BrokenSupabaseClient(), require_persistence=False)

    assert isinstance(store, InMemoryMobileJobStore)


def test_hosted_store_refuses_to_start_without_persistence() -> None:
    with pytest.raises(MobileJobStoreError, match="mobile_jobs_migration.sql"):
        build_mobile_job_store(BrokenSupabaseClient(), require_persistence=True)


def test_hosted_environment_requires_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOBILE_JOB_STORE_REQUIRED", raising=False)
    monkeypatch.setenv("MOBILE_REQUIRE_EXPLICIT_TOKEN", "true")

    assert mobile_job_persistence_required() is True

    monkeypatch.setenv("MOBILE_JOB_STORE_REQUIRED", "false")
    assert mobile_job_persistence_required() is True

    monkeypatch.setenv("MOBILE_REQUIRE_EXPLICIT_TOKEN", "false")
    assert mobile_job_persistence_required() is False


def test_owner_key_is_stable_and_does_not_expose_owner_identity() -> None:
    first = mobile_job_owner_key(
        {"mode": "google", "email": " HIKER@Example.com ", "subject": "subject-1"}
    )
    second = mobile_job_owner_key(
        {"mode": "google", "email": "hiker@example.com", "subject": "subject-1"}
    )

    assert first == second
    assert len(first) == 64
    assert "hiker" not in first


def test_owner_subject_survives_email_and_mode_changes() -> None:
    first = mobile_job_owner_key(
        {"subject": "personal-owner-1", "email": "old@example.com", "mode": "local"}
    )
    changed = mobile_job_owner_key(
        {"subject": "personal-owner-1", "email": "new@example.com", "mode": "google"}
    )

    assert first == changed


def test_mobile_job_migration_is_generic_and_service_role_only() -> None:
    migration = (
        Path(__file__).resolve().parents[1] / "sql" / "mobile_jobs_migration.sql"
    ).read_text(encoding="utf-8")

    assert "job_type text" in migration
    assert "owner_scope text" in migration
    assert "request_payload jsonb" in migration
    assert "payload jsonb" in migration
    assert "attempt_count integer" in migration
    assert "lease_expires_at timestamptz" in migration
    assert "claim_mobile_api_job" in migration
    assert "fail_expired_mobile_api_job" in migration
    assert "job.lease_expires_at <= timezone('utc', now())" in migration
    assert "revoke all privileges on table public.mobile_api_jobs from anon, authenticated" in migration
    assert "grant all privileges on table public.mobile_api_jobs to service_role" in migration
    assert "update_mobile_api_job" in migration
    assert "request_fingerprint" in migration
    assert "p_expected_lease_owner" in migration


def test_review_status_comes_from_durable_store_after_process_cache_is_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = {
        "mode": "google",
        "email": "owner@example.com",
        "subject": "subject-1",
        "auth_configured": True,
    }
    job = {
        "job_id": "00000000-0000-0000-0000-000000000010",
        "state": "completed",
        "total_photos": 1,
        "processed_count": 1,
        "processed_photo_ids": ["photo-1"],
        "current_photo_number": 1,
        "current_photo_id": None,
        "total_groups": 1,
        "current_group": 1,
        "grouped_count": 0,
        "individual_count": 1,
        "warnings": [],
        "error": None,
        "items": [{"id": "photo-1"}],
        "owner_context": owner,
        "client_request_id": "request-restart",
    }
    first_store = InMemoryMobileJobStore()
    persisted, _ = first_store.create(
        job_type=mobile_api.SPECIES_REVIEW_JOB_TYPE,
        owner_scope=mobile_api.MOBILE_JOB_OWNER_SCOPE,
        owner_key=mobile_job_owner_key(owner),
        client_request_id="request-restart",
        payload=job,
        request_payload={"groups": [{"photo_ids": ["photo-1"]}]},
        job_id=job["job_id"],
    )
    restarted_store = InMemoryMobileJobStore(records=[persisted])
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", restarted_store)
    monkeypatch.setattr(mobile_api, "_species_batch_jobs", {})
    monkeypatch.setattr(mobile_api, "_user_context", lambda: owner)

    status = mobile_api.get_species_batch_recommendation_status(job["job_id"])

    assert status["state"] == "completed"
    assert status["processed_photo_ids"] == ["photo-1"]
    assert "owner_context" not in status
    assert "client_request_id" not in status


def test_duplicate_review_start_is_reused_from_durable_store_before_revalidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = {"mode": "google", "email": "owner@example.com", "subject": "subject-1"}
    job = {
        "job_id": "00000000-0000-0000-0000-000000000011",
        "state": "running",
        "total_photos": 1,
        "processed_count": 0,
        "processed_photo_ids": [],
        "current_photo_number": 1,
        "current_photo_id": "photo-1",
        "total_groups": 1,
        "current_group": 1,
        "grouped_count": 0,
        "individual_count": 0,
        "warnings": [],
        "error": None,
        "items": [],
        "owner_context": owner,
        "client_request_id": "lost-response-request",
    }
    store = InMemoryMobileJobStore()
    store.create(
        job_type=mobile_api.SPECIES_REVIEW_JOB_TYPE,
        owner_scope=mobile_api.MOBILE_JOB_OWNER_SCOPE,
        owner_key=mobile_job_owner_key(owner),
        client_request_id="lost-response-request",
        payload=job,
        request_payload={"groups": [{"photo_ids": ["photo-1"]}]},
        job_id=job["job_id"],
    )
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)
    monkeypatch.setattr(mobile_api, "_species_batch_jobs", {})
    monkeypatch.setattr(mobile_api, "_user_context", lambda: owner)
    monkeypatch.setattr(
        mobile_api,
        "_prepare_species_batch_submission",
        lambda _payload: pytest.fail("an idempotent retry must not revalidate or repeat work"),
    )
    tasks = BackgroundTasks()

    response = mobile_api.start_species_batch_recommendation(
        ReviewBatchInput(
            groups=[ReviewBatchGroupInput(photo_ids=["photo-1"])],
            client_request_id="lost-response-request",
        ),
        tasks,
    )

    assert response["job_id"] == job["job_id"]
    assert response["state"] == "running"
    assert tasks.tasks == []


def test_recovery_dispatch_uses_the_persisted_request_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TrackingStore(InMemoryMobileJobStore):
        def __init__(self) -> None:
            super().__init__()
            self.list_calls = 0
            self.get_calls = 0

        def get(self, job_id: str) -> MobileJobRecord | None:
            self.get_calls += 1
            return super().get(job_id)

        def list_recoverable(self, *, job_types=None):
            self.list_calls += 1
            return super().list_recoverable(job_types=job_types)

    store = TrackingStore()
    record, _ = create_job(store)
    dispatched: list[MobileJobRecord] = []
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)
    monkeypatch.setattr(
        mobile_api,
        "_start_mobile_job_dispatch",
        lambda candidate: dispatched.append(candidate) or True,
    )

    count = mobile_api._dispatch_recoverable_mobile_jobs(job_id=record.job_id)

    assert count == 1
    assert store.list_calls == 0
    assert store.get_calls == 1
    assert dispatched[0].job_id == record.job_id
    assert dispatched[0].request_payload == {
        "groups": [{"photo_ids": ["photo-1"]}]
    }


def test_cached_review_request_cannot_bypass_durable_fingerprint_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = {"subject": "subject-1", "email": "owner@example.com"}
    job_id = "00000000-0000-0000-0000-000000000012"
    original = ReviewBatchInput(
        groups=[ReviewBatchGroupInput(photo_ids=["photo-1"])],
        client_request_id="cached-conflict",
    )
    job = {
        "job_id": job_id,
        "state": "running",
        "owner_context": owner,
        "client_request_id": "cached-conflict",
        mobile_api.MOBILE_JOB_CACHE_FINGERPRINT_KEY: (
            mobile_jobs.mobile_job_request_fingerprint(original.model_dump(mode="json"))
        ),
    }
    store = InMemoryMobileJobStore()
    monkeypatch.setattr(mobile_api, "services", None)
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)
    monkeypatch.setattr(mobile_api, "_species_batch_jobs", {job_id: dict(job)})
    monkeypatch.setattr(mobile_api, "_user_context", lambda: owner)

    with pytest.raises(HTTPException) as error:
        mobile_api.start_species_batch_recommendation(
            ReviewBatchInput(
                groups=[ReviewBatchGroupInput(photo_ids=["photo-2"])],
                client_request_id="cached-conflict",
            ),
            BackgroundTasks(),
        )

    assert error.value.status_code == 409
    assert "different background work" in str(error.value.detail)
    assert (
        mobile_api.MOBILE_JOB_CACHE_FINGERPRINT_KEY
        not in mobile_api._review_batch_job_payload(job)
    )


def test_cached_publish_request_cannot_bypass_durable_fingerprint_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = {"subject": "subject-1", "email": "owner@example.com"}
    job_id = "00000000-0000-0000-0000-000000000013"
    original = mobile_api.PublishBatchInput(
        acknowledged_public=True,
        groups=[mobile_api.PublishBatchGroupInput(observation_ids=["observation-1"])],
        client_request_id="cached-publish-conflict",
    )
    job = {
        "job_id": job_id,
        "state": "running",
        "owner_context": owner,
        "client_request_id": "cached-publish-conflict",
        mobile_api.MOBILE_JOB_CACHE_FINGERPRINT_KEY: (
            mobile_jobs.mobile_job_request_fingerprint(original.model_dump(mode="json"))
        ),
    }
    store = InMemoryMobileJobStore()
    monkeypatch.setattr(mobile_api, "services", None)
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)
    monkeypatch.setattr(mobile_api, "_species_publish_jobs", {job_id: dict(job)})
    monkeypatch.setattr(mobile_api, "_user_context", lambda: owner)

    with pytest.raises(HTTPException) as error:
        mobile_api.start_species_publish_batch(
            mobile_api.PublishBatchInput(
                acknowledged_public=True,
                groups=[
                    mobile_api.PublishBatchGroupInput(
                        observation_ids=["observation-2"]
                    )
                ],
                client_request_id="cached-publish-conflict",
            ),
            BackgroundTasks(),
        )

    assert error.value.status_code == 409
    assert "different background work" in str(error.value.detail)
    assert (
        mobile_api.MOBILE_JOB_CACHE_FINGERPRINT_KEY
        not in mobile_api._publish_batch_job_payload(job)
    )


def test_expired_publish_lease_stops_for_review_instead_of_risking_a_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now)
    store = InMemoryMobileJobStore()
    record, _ = create_job(
        store,
        job_type=mobile_api.SPECIES_PUBLISH_JOB_TYPE,
        job_id="00000000-0000-0000-0000-000000000020",
    )
    store.acquire_lease(record.job_id, lease_owner="stopped-worker", lease_seconds=30)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now + timedelta(seconds=31))
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)
    monkeypatch.setattr(
        mobile_api,
        "_start_mobile_job_dispatch",
        lambda _candidate: pytest.fail("an ambiguous external publish must not be repeated"),
    )

    count = mobile_api._dispatch_recoverable_mobile_jobs(job_id=record.job_id)
    stopped = store.get(record.job_id)

    assert count == 0
    assert stopped is not None
    assert stopped.state == "failed"
    assert "may have been creating" in str(stopped.payload.get("error"))


def test_transient_review_failure_uses_durable_backoff_and_stays_pollable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now)
    owner = {"mode": "google", "email": "owner@example.com", "subject": "subject-1"}
    job_id = "00000000-0000-0000-0000-000000000021"
    job = {
        "job_id": job_id,
        "state": "queued",
        "total_photos": 1,
        "processed_count": 0,
        "processed_photo_ids": [],
        "current_photo_number": 0,
        "current_photo_id": None,
        "total_groups": 1,
        "current_group": 0,
        "grouped_count": 0,
        "individual_count": 0,
        "warnings": [],
        "error": None,
        "items": [],
        "owner_context": owner,
        "client_request_id": "transient-request",
    }
    store = InMemoryMobileJobStore()
    store.create(
        job_type=mobile_api.SPECIES_REVIEW_JOB_TYPE,
        owner_scope=mobile_api.MOBILE_JOB_OWNER_SCOPE,
        owner_key=mobile_job_owner_key(owner),
        client_request_id="transient-request",
        payload=job,
        request_payload={"groups": [{"photo_ids": ["photo-1"]}]},
        job_id=job_id,
    )
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)
    monkeypatch.setattr(mobile_api, "_species_batch_jobs", {job_id: dict(job)})
    monkeypatch.setattr(mobile_api, "_user_context", lambda: owner)
    monkeypatch.setattr(mobile_api, "_review_queue_payload", lambda _service: [])
    monkeypatch.setattr(
        mobile_api,
        "_process_species_batch_submission",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(InatRequestError("temporary outage")),
    )

    mobile_api._run_species_batch_job(
        job_id,
        object(),
        [ReviewBatchGroupInput(photo_ids=["photo-1"])],
        {"photo-1": {"id": "photo-1"}},
        object(),
        1,
    )
    retryable = store.get(job_id)

    assert retryable is not None
    assert retryable.state == "failed"
    assert retryable.payload["state"] == "queued"
    assert retryable.payload["error"] == "temporary outage"
    assert retryable.attempt_count == 1
    assert retryable.next_attempt_at == now + timedelta(seconds=30)


def test_job_metrics_distinguish_retry_wait_from_needs_attention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now)
    store = InMemoryMobileJobStore()
    queued, _ = create_job(store)
    running, _ = create_job(
        store,
        job_id="00000000-0000-0000-0000-000000000030",
        request_id="metrics-running",
    )
    store.acquire_lease(running.job_id, lease_owner="worker", lease_seconds=60)
    retrying, _ = create_job(
        store,
        job_id="00000000-0000-0000-0000-000000000031",
        request_id="metrics-retry",
    )
    store.acquire_lease(retrying.job_id, lease_owner="worker", lease_seconds=60)
    store.mark_retryable(retrying.job_id, error="temporary", retry_after_seconds=30)
    attention, _ = create_job(
        store,
        job_id="00000000-0000-0000-0000-000000000032",
        request_id="metrics-attention",
    )
    store.update(attention.job_id, state="failed", error="operator review")

    metrics = store.operational_metrics()

    assert queued.job_id
    assert metrics["durable"] is False
    assert metrics["sampled_job_count"] == 4
    assert metrics["state_counts"] == {"failed": 2, "queued": 1, "running": 1}
    assert metrics["retry_wait_count"] == 1
    assert metrics["needs_attention_count"] == 1
    assert metrics["oldest_active_age_seconds"] == 0.0


def test_stale_worker_cannot_update_after_lease_reclamation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now)
    store = InMemoryMobileJobStore()
    record, _ = create_job(store)
    first = store.acquire_lease(record.job_id, lease_owner="worker-a", lease_seconds=30)
    assert first is not None

    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now + timedelta(seconds=31))
    second = store.acquire_lease(record.job_id, lease_owner="worker-b", lease_seconds=30)
    stale = store.update(
        record.job_id,
        expected_lease_owner="worker-a",
        state="completed",
    )
    current = store.get(record.job_id)

    assert second is not None
    assert stale is None
    assert current is not None
    assert current.state == "running"
    assert current.lease_owner == "worker-b"


@pytest.mark.parametrize(
    "job_type",
    [mobile_api.SPECIES_REVIEW_JOB_TYPE, mobile_api.SPECIES_PUBLISH_JOB_TYPE],
)
def test_expired_recovery_snapshot_cannot_clobber_a_replacement_worker(
    monkeypatch: pytest.MonkeyPatch,
    job_type: str,
) -> None:
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now)
    store = InMemoryMobileJobStore()
    record, _ = create_job(store, job_type=job_type)
    first = store.acquire_lease(record.job_id, lease_owner="worker-a", lease_seconds=30)
    assert first is not None

    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now + timedelta(seconds=31))
    expired_snapshot = store.list_recoverable()[0]
    replacement = store.acquire_lease(
        record.job_id,
        lease_owner="worker-b",
        lease_seconds=30,
    )
    monkeypatch.setattr(mobile_api, "services", None)
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)

    recovered = mobile_api._prepare_recoverable_mobile_job(expired_snapshot)
    if recovered is not None:
        monkeypatch.setattr(
            mobile_api,
            "_resume_species_review_job",
            lambda _record, **_kwargs: pytest.fail("a stale recovery snapshot must not run"),
        )
        mobile_api._resume_mobile_job(recovered)
    current = store.get(record.job_id)

    assert replacement is not None
    assert (recovered is not None) is (job_type == mobile_api.SPECIES_REVIEW_JOB_TYPE)
    assert current is not None
    assert current.state == "running"
    assert current.lease_owner == "worker-b"


@pytest.mark.parametrize(
    ("job_type", "max_attempts"),
    [
        (mobile_api.SPECIES_PUBLISH_JOB_TYPE, 3),
        (mobile_api.SPECIES_REVIEW_JOB_TYPE, 1),
    ],
)
def test_expired_attention_transition_rechecks_a_same_owner_renewal(
    monkeypatch: pytest.MonkeyPatch,
    job_type: str,
    max_attempts: int,
) -> None:
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now)
    store = InMemoryMobileJobStore()
    record, _ = store.create(
        job_type=job_type,
        owner_scope=OWNER_SCOPE,
        owner_key=OWNER_KEY,
        client_request_id="same-owner-renewal",
        payload={"job_id": "00000000-0000-0000-0000-000000000041", "state": "queued"},
        request_payload={"groups": [{"photo_ids": ["photo-1"]}]},
        job_id="00000000-0000-0000-0000-000000000041",
        max_attempts=max_attempts,
    )
    assert store.acquire_lease(record.job_id, lease_owner="worker-a", lease_seconds=30)

    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now + timedelta(seconds=31))
    expired_snapshot = store.list_recoverable()[0]
    renewed = store.update(
        record.job_id,
        expected_lease_owner="worker-a",
        lease_seconds=300,
        progress_marker="still-alive",
    )
    monkeypatch.setattr(mobile_api, "services", None)
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)

    assert renewed is not None
    assert mobile_api._prepare_recoverable_mobile_job(expired_snapshot) is None
    current = store.get(record.job_id)
    assert current is not None
    assert current.state == "running"
    assert current.lease_owner == "worker-a"
    assert current.payload["progress_marker"] == "still-alive"


def test_recovery_claims_lease_before_any_resume_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryMobileJobStore()
    record, _ = create_job(store, request_id="claim-before-resume")
    observed: list[MobileJobRecord] = []
    monkeypatch.setattr(mobile_api, "services", None)
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)

    def inspect_claim(candidate: MobileJobRecord, **_kwargs) -> None:
        current = store.get(candidate.job_id)
        assert current is not None
        assert current.state == "running"
        assert current.attempt_count == 1
        assert current.lease_owner == mobile_api._current_mobile_job_lease_owner()
        observed.append(candidate)

    monkeypatch.setattr(mobile_api, "_resume_species_review_job", inspect_claim)

    mobile_api._resume_mobile_job(record)

    assert len(observed) == 1
    assert observed[0].attempt_count == 1


def test_dispatch_rolls_back_slot_when_thread_start_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryMobileJobStore()
    record, _ = create_job(store, request_id="thread-start-failure")
    monkeypatch.setattr(mobile_api, "_mobile_jobs_dispatching", set())

    class BrokenThread:
        def __init__(self, **_kwargs) -> None:
            pass

        def start(self) -> None:
            raise RuntimeError("thread capacity unavailable")

    monkeypatch.setattr(mobile_api, "Thread", BrokenThread)

    assert mobile_api._start_mobile_job_dispatch(record) is False
    assert record.job_id not in mobile_api._mobile_jobs_dispatching


def test_recovery_scan_isolates_one_record_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryMobileJobStore()
    first, _ = create_job(store, request_id="isolate-1")
    second, _ = create_job(
        store,
        request_id="isolate-2",
        job_id="00000000-0000-0000-0000-000000000042",
    )
    started: list[str] = []
    monkeypatch.setattr(mobile_api, "services", None)
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)

    def prepare(record: MobileJobRecord) -> MobileJobRecord:
        if record.job_id == first.job_id:
            raise RuntimeError("transient recovery RPC failure")
        return record

    monkeypatch.setattr(mobile_api, "_prepare_recoverable_mobile_job", prepare)
    monkeypatch.setattr(
        mobile_api,
        "_start_mobile_job_dispatch",
        lambda record: started.append(record.job_id) or True,
    )

    assert mobile_api._dispatch_recoverable_mobile_jobs() == 1
    assert started == [second.job_id]


def test_recovery_loop_continues_after_transient_iteration_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def no_wait(_seconds: float) -> None:
        return None

    async def run_iteration(_function) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary database failure")
        raise asyncio.CancelledError

    monkeypatch.setattr(mobile_api.asyncio, "sleep", no_wait)
    monkeypatch.setattr(mobile_api.asyncio, "to_thread", run_iteration)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(mobile_api._mobile_job_recovery_loop())

    assert calls == 2


@pytest.mark.parametrize("failure_holds_stale_lease", [False, True])
def test_generic_recovery_failure_cannot_overwrite_a_replacement_worker(
    monkeypatch: pytest.MonkeyPatch,
    failure_holds_stale_lease: bool,
) -> None:
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now)
    store = InMemoryMobileJobStore()
    record, _ = create_job(store, request_id="recovery-fence")
    first = store.acquire_lease(record.job_id, lease_owner="worker-a", lease_seconds=30)
    assert first is not None

    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now + timedelta(seconds=31))
    replacement = store.acquire_lease(
        record.job_id,
        lease_owner="worker-b",
        lease_seconds=30,
    )
    monkeypatch.setattr(mobile_api, "services", None)
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)
    def fail_recovery(_record: MobileJobRecord, **_kwargs) -> None:
        if failure_holds_stale_lease:
            mobile_api._mobile_job_worker.lease_owner = "worker-a"
        raise RuntimeError("recovery failed")

    monkeypatch.setattr(mobile_api, "_resume_species_review_job", fail_recovery)
    monkeypatch.setattr(mobile_api, "_mobile_jobs_dispatching", {record.job_id})

    mobile_api._resume_mobile_job(record)
    current = store.get(record.job_id)

    assert replacement is not None
    assert current is not None
    assert current.state == "running"
    assert current.lease_owner == "worker-b"
    assert record.job_id not in mobile_api._mobile_jobs_dispatching


def test_supabase_recovery_scan_is_server_filtered_and_bounded() -> None:
    queries = []

    class Query:
        def __init__(self) -> None:
            self.filters = []
            self.limit_value = None
            self.order_field = None

        def select(self, fields):
            self.fields = fields
            return self

        def eq(self, field, value):
            self.filters.append(("eq", field, value))
            return self

        def in_(self, field, values):
            self.filters.append(("in", field, values))
            return self

        def lte(self, field, value):
            self.filters.append(("lte", field, value))
            return self

        def order(self, field):
            self.order_field = field
            return self

        def limit(self, value):
            self.limit_value = value
            return self

        def execute(self):
            return type("Response", (), {"data": []})()

    class Client:
        def table(self, name):
            assert name == mobile_jobs.MOBILE_JOB_TABLE
            query = Query()
            queries.append(query)
            return query

    store = mobile_jobs.SupabaseMobileJobStore(Client())

    assert store.list_recoverable(job_types={"species-review-batch"}) == []
    assert len(queries) == 3
    assert [query.filters[0] for query in queries] == [
        ("eq", "state", "queued"),
        ("eq", "state", "failed"),
        ("eq", "state", "running"),
    ]
    assert all(
        ("in", "job_type", ["species-review-batch"]) in query.filters
        for query in queries
    )
    assert not any(filter_[0] == "lte" for filter_ in queries[0].filters)
    assert any(filter_[:2] == ("lte", "next_attempt_at") for filter_ in queries[1].filters)
    assert any(filter_[:2] == ("lte", "lease_expires_at") for filter_ in queries[2].filters)
    assert all(
        query.limit_value == mobile_jobs.MOBILE_JOB_RECOVERY_PAGE_SIZE
        and query.order_field == "created_at"
        for query in queries
    )


def test_expired_final_attempt_is_visible_for_attention_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now)
    store = InMemoryMobileJobStore()
    record, _ = store.create(
        job_type=mobile_api.SPECIES_REVIEW_JOB_TYPE,
        owner_scope=OWNER_SCOPE,
        owner_key=OWNER_KEY,
        client_request_id="final-attempt",
        payload={"job_id": "00000000-0000-0000-0000-000000000040", "state": "queued"},
        request_payload={"groups": [{"photo_ids": ["photo-1"]}]},
        job_id="00000000-0000-0000-0000-000000000040",
        max_attempts=1,
    )
    store.acquire_lease(record.job_id, lease_owner="stopped", lease_seconds=30)
    monkeypatch.setattr(mobile_jobs, "utc_now", lambda: now + timedelta(seconds=31))

    recoverable = store.list_recoverable()

    assert [item.job_id for item in recoverable] == [record.job_id]
    assert recoverable[0].attempt_count == recoverable[0].max_attempts == 1
    monkeypatch.setattr(mobile_api, "_local_mobile_job_store", store)
    monkeypatch.setattr(
        mobile_api,
        "_start_mobile_job_dispatch",
        lambda _candidate: pytest.fail("an exhausted job must not be dispatched again"),
    )

    assert mobile_api._dispatch_recoverable_mobile_jobs(job_id=record.job_id) == 0
    stopped = store.get(record.job_id)
    assert stopped is not None
    assert stopped.state == "failed"
    assert "final attempt" in str(stopped.payload.get("error"))
