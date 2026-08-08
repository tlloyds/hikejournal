from __future__ import annotations

import time
import threading

from hike_journal.services.api_runtime import (
    RequestMetrics,
    run_dependency_probe,
    run_dependency_probes,
)


def test_dependency_probe_reports_success_without_detail() -> None:
    result = run_dependency_probe(lambda: None)

    assert result.status == "ok"
    assert result.latency_ms >= 0
    assert result.payload() == {
        "status": "ok",
        "latency_ms": round(result.latency_ms, 2),
    }


def test_dependency_probe_converts_failure_to_safe_payload() -> None:
    def fail() -> None:
        raise RuntimeError("database unavailable")

    result = run_dependency_probe(fail)

    assert result.status == "error"
    assert "detail" not in result.payload()
    assert result.payload(include_detail=True)["detail"] == "RuntimeError: database unavailable"


def test_dependency_probes_share_one_bounded_timeout() -> None:
    blocker = threading.Event()
    started = time.perf_counter()

    results = run_dependency_probes(
        {"database": blocker.wait, "storage": blocker.wait},
        timeout_seconds=0.02,
    )
    elapsed = time.perf_counter() - started
    blocker.set()

    assert elapsed < 0.15
    assert results["database"].status == "timeout"
    assert results["storage"].status == "timeout"


def test_request_metrics_track_latency_errors_and_route_templates() -> None:
    metrics = RequestMetrics()
    successful = metrics.start_request()
    time.sleep(0.001)
    metrics.finish_request(
        started=successful,
        method="get",
        route="/v1/hikes/{hike_id}",
        status_code=200,
    )
    failed = metrics.start_request()
    metrics.finish_request(
        started=failed,
        method="GET",
        route="/v1/hikes/{hike_id}",
        status_code=503,
    )

    snapshot = metrics.snapshot()

    assert snapshot["in_flight"] == 0
    assert snapshot["request_count"] == 2
    assert snapshot["server_error_count"] == 1
    assert snapshot["status_classes"] == {"2xx": 1, "5xx": 1}
    assert snapshot["maximum_latency_ms"] >= snapshot["average_latency_ms"] >= 0
    assert snapshot["routes"]["GET /v1/hikes/{hike_id}"]["count"] == 2
    assert snapshot["routes"]["GET /v1/hikes/{hike_id}"]["errors"] == 1
