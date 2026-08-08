from __future__ import annotations

import json
import hashlib
from pathlib import Path

from fastapi.routing import APIRoute

from mobile_api import app


def test_mobile_v1_does_not_remove_existing_methods_or_paths() -> None:
    contract = json.loads(
        Path("tests/contracts/mobile_v1_routes.json").read_text(encoding="utf-8")
    )
    required = set(contract["routes"])
    actual = {
        f"{method} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    }

    assert required <= actual, f"Removed mobile API contract routes: {sorted(required - actual)}"


def test_mobile_contract_manifest_has_no_duplicates() -> None:
    contract = json.loads(
        Path("tests/contracts/mobile_v1_routes.json").read_text(encoding="utf-8")
    )

    assert len(contract["routes"]) == len(set(contract["routes"]))


def test_supported_mobile_openapi_operations_change_only_after_contract_review() -> None:
    """Pin modeled inputs/errors while allowing entirely new routes to be additive."""
    contract = json.loads(
        Path("tests/contracts/mobile_v1_routes.json").read_text(encoding="utf-8")
    )
    openapi = app.openapi()
    protected_paths: dict[str, dict[str, object]] = {}
    for operation in contract["routes"]:
        method, path = operation.split(" ", 1)
        protected_paths.setdefault(path, {})[method.lower()] = openapi["paths"][path][
            method.lower()
        ]
    normalized = {
        "paths": protected_paths,
        "components": {
            "schemas": openapi.get("components", {}).get("schemas", {}),
        },
    }
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    actual = hashlib.sha256(encoded).hexdigest()
    expected = Path("tests/contracts/mobile_v1_openapi.sha256").read_text(
        encoding="utf-8"
    ).strip()

    assert actual == expected, (
        "The protected mobile OpenAPI surface changed. Review the normalized operation, "
        "request, parameter, response, and error schemas for backward compatibility before "
        f"accepting the new fingerprint. Expected {expected}; found {actual}."
    )
