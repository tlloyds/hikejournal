from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import mobile_api
from hike_journal.mobile_contract import MOBILE_CONTRACT_VERSION
from hike_journal.services.api_runtime import RequestMetrics
from hike_journal.services.mobile_jobs import InMemoryMobileJobStore


class _DatabaseProbe:
    def select(self, _fields: str):
        return self

    def limit(self, _limit: int):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class _Client:
    def table(self, name: str):
        assert name == "hikes"
        return _DatabaseProbe()


class _Storage:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def check_health(self) -> None:
        if self.error:
            raise self.error


def _service(*, storage_error: Exception | None = None):
    return SimpleNamespace(
        client=_Client(),
        storage=_Storage(storage_error),
        mobile_job_store=InMemoryMobileJobStore(),
    )


def test_liveness_preserves_the_existing_health_contract(monkeypatch) -> None:
    monkeypatch.setattr(mobile_api, "services", None)
    client = TestClient(mobile_api.app)

    original = client.get("/health")
    live = client.get("/health/live")

    assert original.status_code == 200
    assert original.json() == {
        "status": "ok",
        "service": "hikejournal-mobile",
        "version": mobile_api.MOBILE_API_VERSION,
    }
    assert live.json() == original.json()
    assert original.headers["x-hikejournal-contract-version"] == MOBILE_CONTRACT_VERSION
    assert original.headers["x-request-id"]


def test_readiness_reports_dependencies_without_exposing_error_details(monkeypatch) -> None:
    monkeypatch.setattr(
        mobile_api,
        "services",
        _service(storage_error=RuntimeError("secret storage host failed")),
    )
    response = TestClient(mobile_api.app).get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["dependencies"]["database"]["status"] == "ok"
    assert response.json()["dependencies"]["storage"]["status"] == "error"
    assert "secret storage host" not in response.text


def test_readiness_fails_closed_for_invalid_hosted_identity(monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_REQUIRE_EXPLICIT_TOKEN", "true")
    monkeypatch.setenv("MOBILE_API_TOKEN", "weak")
    monkeypatch.delenv("MOBILE_OWNER_EMAIL", raising=False)
    monkeypatch.delenv("MOBILE_OWNER_SUBJECT", raising=False)
    monkeypatch.setattr(mobile_api, "services", _service())
    monkeypatch.setattr(mobile_api, "_dependency_health_cache", None)

    response = TestClient(mobile_api.app).get("/health/ready")

    assert response.status_code == 503
    assert response.json()["dependencies"]["configuration"]["status"] == "error"
    assert "MOBILE_API_TOKEN" not in response.text


def test_authenticated_operational_metrics_are_bounded_and_contract_versioned(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MOBILE_API_TOKEN", "operator-key")
    monkeypatch.setattr(mobile_api, "services", _service())
    monkeypatch.setattr(mobile_api, "request_metrics", RequestMetrics())
    client = TestClient(mobile_api.app)
    client.get("/health")

    unauthorized = client.get("/v1/operations/metrics")
    response = client.get(
        "/v1/operations/metrics",
        headers={"X-HikeJournal-Key": "operator-key"},
    )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == MOBILE_CONTRACT_VERSION
    assert payload["requests"]["request_count"] >= 2
    assert "GET /health" in payload["requests"]["routes"]
    assert "GET /v1/operations/metrics" in payload["requests"]["routes"]
    assert payload["jobs"] == {
        "durable": False,
        "sampled_job_count": 0,
        "sample_truncated": False,
        "state_counts": {},
        "job_type_counts": {},
        "retry_wait_count": 0,
        "needs_attention_count": 0,
        "retry_attempt_count": 0,
        "oldest_active_age_seconds": None,
    }


def test_large_api_responses_support_gzip(monkeypatch) -> None:
    monkeypatch.setattr(mobile_api, "services", None)
    response = TestClient(mobile_api.app).get(
        "/openapi.json",
        headers={"Accept-Encoding": "gzip"},
    )

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"


def test_photo_delete_keeps_database_record_when_storage_delete_fails(monkeypatch) -> None:
    deleted: list[str] = []

    class Repository:
        def delete_photo(self, photo_id: str) -> None:
            deleted.append(photo_id)

    class Storage:
        def delete_file(self, _path: str) -> None:
            raise RuntimeError("object store unavailable")

    service = SimpleNamespace(repository=Repository(), storage=Storage())
    monkeypatch.setattr(
        mobile_api,
        "_get_visible_photo",
        lambda _photo_id: (service, {"id": "photo-1", "storage_path": "hikes/photo-1.jpg"}),
    )

    with pytest.raises(HTTPException) as error:
        mobile_api.delete_photo("photo-1")

    assert error.value.status_code == 503
    assert deleted == []


def test_photo_delete_removes_storage_before_database(monkeypatch) -> None:
    events: list[str] = []

    class Repository:
        def delete_photo(self, _photo_id: str) -> None:
            events.append("database")

    class Storage:
        def delete_file(self, _path: str) -> None:
            events.append("storage")

    service = SimpleNamespace(repository=Repository(), storage=Storage())
    monkeypatch.setattr(
        mobile_api,
        "_get_visible_photo",
        lambda _photo_id: (service, {"id": "photo-1", "storage_path": "hikes/photo-1.jpg"}),
    )

    assert mobile_api.delete_photo("photo-1") == {"deleted": True}
    assert events == ["storage", "database"]


def test_photo_delete_retry_is_idempotent_when_record_is_already_gone(monkeypatch) -> None:
    def missing(_photo_id: str):
        raise HTTPException(status_code=404, detail="Photo not found.")

    monkeypatch.setattr(mobile_api, "_get_visible_photo", missing)

    assert mobile_api.delete_photo("photo-1") == {"deleted": True}
