from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
import threading
import time
from typing import Any, Callable


_probe_slots = threading.BoundedSemaphore(8)


@dataclass(frozen=True)
class ProbeResult:
    status: str
    latency_ms: float
    detail: str | None = None

    def payload(self, *, include_detail: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status,
            "latency_ms": round(self.latency_ms, 2),
        }
        if include_detail and self.detail:
            result["detail"] = self.detail
        return result


def run_dependency_probes(
    probes: dict[str, Callable[[], Any]],
    *,
    timeout_seconds: float = 3.0,
) -> dict[str, ProbeResult]:
    """Run bounded probes concurrently and convert failures/timeouts to data.

    Timed-out work is left on a daemon thread because Python cannot safely kill
    a blocking SDK call. A global slot limit prevents repeated public readiness
    requests from creating an unbounded number of stuck threads.
    """

    timeout_seconds = max(0.01, min(float(timeout_seconds), 30.0))
    results: dict[str, ProbeResult] = {}
    results_lock = threading.Lock()
    completed = threading.Event()
    pending = set(probes)
    overall_started = time.perf_counter()

    def finish(name: str, result: ProbeResult) -> None:
        with results_lock:
            results[name] = result
            pending.discard(name)
            if not pending:
                completed.set()

    def worker(name: str, probe: Callable[[], Any]) -> None:
        started = time.perf_counter()
        try:
            probe()
        except Exception as exc:  # Dependency errors become health data.
            result = ProbeResult(
                status="error",
                latency_ms=(time.perf_counter() - started) * 1000,
                detail=f"{type(exc).__name__}: {exc}",
            )
        else:
            result = ProbeResult(
                status="ok",
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        finally:
            _probe_slots.release()
        finish(name, result)

    for name, probe in probes.items():
        if not _probe_slots.acquire(blocking=False):
            finish(
                name,
                ProbeResult(
                    status="error",
                    latency_ms=0,
                    detail="Dependency probe capacity is exhausted.",
                ),
            )
            continue
        threading.Thread(
            target=worker,
            args=(name, probe),
            name=f"health-probe-{name}",
            daemon=True,
        ).start()

    completed.wait(timeout_seconds)
    elapsed_ms = (time.perf_counter() - overall_started) * 1000
    with results_lock:
        for name in pending:
            results[name] = ProbeResult(
                status="timeout",
                latency_ms=elapsed_ms,
                detail=f"Dependency probe exceeded {timeout_seconds:g} seconds.",
            )
        snapshot = {name: results[name] for name in probes}
    return snapshot


def run_dependency_probe(
    probe: Callable[[], Any],
    *,
    timeout_seconds: float = 3.0,
) -> ProbeResult:
    """Run one bounded dependency check without crashing health routes."""

    return run_dependency_probes(
        {"dependency": probe},
        timeout_seconds=timeout_seconds,
    )["dependency"]


class RequestMetrics:
    """Small in-process API telemetry with bounded, route-template cardinality.

    Cloud Run logs remain the durable source of request history. This snapshot is
    intentionally lightweight so operators can immediately inspect the current
    instance without adding work to every application endpoint.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = datetime.now(UTC)
        self._started_monotonic = time.monotonic()
        self._in_flight = 0
        self._request_count = 0
        self._error_count = 0
        self._latency_total_ms = 0.0
        self._latency_max_ms = 0.0
        self._status_classes: dict[str, int] = defaultdict(int)
        self._routes: dict[str, dict[str, float | int]] = {}

    def start_request(self) -> float:
        with self._lock:
            self._in_flight += 1
        return time.perf_counter()

    def finish_request(
        self,
        *,
        started: float,
        method: str,
        route: str,
        status_code: int,
    ) -> None:
        latency_ms = max(0.0, (time.perf_counter() - started) * 1000)
        route_key = f"{method.upper()} {route}"
        status_class = f"{max(0, status_code) // 100}xx"
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            self._request_count += 1
            if status_code >= 500:
                self._error_count += 1
            self._latency_total_ms += latency_ms
            self._latency_max_ms = max(self._latency_max_ms, latency_ms)
            self._status_classes[status_class] += 1
            route_metrics = self._routes.setdefault(
                route_key,
                {"count": 0, "errors": 0, "latency_total_ms": 0.0, "latency_max_ms": 0.0},
            )
            route_metrics["count"] = int(route_metrics["count"]) + 1
            if status_code >= 500:
                route_metrics["errors"] = int(route_metrics["errors"]) + 1
            route_metrics["latency_total_ms"] = float(route_metrics["latency_total_ms"]) + latency_ms
            route_metrics["latency_max_ms"] = max(float(route_metrics["latency_max_ms"]), latency_ms)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            request_count = self._request_count
            routes = {
                route: {
                    "count": int(values["count"]),
                    "errors": int(values["errors"]),
                    "average_latency_ms": round(
                        float(values["latency_total_ms"]) / max(1, int(values["count"])),
                        2,
                    ),
                    "maximum_latency_ms": round(float(values["latency_max_ms"]), 2),
                }
                for route, values in sorted(self._routes.items())
            }
            return {
                "started_at": self._started_at.isoformat(),
                "uptime_seconds": round(max(0.0, time.monotonic() - self._started_monotonic), 1),
                "in_flight": self._in_flight,
                "request_count": request_count,
                "server_error_count": self._error_count,
                "average_latency_ms": round(self._latency_total_ms / max(1, request_count), 2),
                "maximum_latency_ms": round(self._latency_max_ms, 2),
                "status_classes": dict(sorted(self._status_classes.items())),
                "routes": routes,
            }
