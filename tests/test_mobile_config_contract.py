from __future__ import annotations

from hike_journal.mobile_contract import (
    BASE_MOBILE_CAPABILITIES,
    MOBILE_CONTRACT_VERSION,
    build_mobile_config,
)


def test_mobile_config_preserves_legacy_fields_and_adds_version_handshake(monkeypatch) -> None:
    monkeypatch.delenv("MOBILE_MIN_ANDROID_VERSION", raising=False)
    monkeypatch.delenv("MOBILE_RECOMMENDED_ANDROID_VERSION", raising=False)

    payload = build_mobile_config(
        web_url="https://journal.example/",
        api_version="0.6.28",
        additional_capabilities=("durable_background_jobs",),
    )

    assert payload["web_url"] == "https://journal.example"
    assert payload["api_version"] == "0.6.28"
    assert payload["capabilities"][: len(BASE_MOBILE_CAPABILITIES)] == list(
        BASE_MOBILE_CAPABILITIES
    )
    assert payload["capabilities"][-1] == "durable_background_jobs"
    assert payload["contract_version"] == MOBILE_CONTRACT_VERSION
    assert payload["compatibility"] == {
        "minimum_android_version": None,
        "recommended_android_version": "0.6.28",
    }


def test_mobile_config_supports_an_explicit_compatibility_window(monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_MIN_ANDROID_VERSION", "0.6.20")
    monkeypatch.setenv("MOBILE_RECOMMENDED_ANDROID_VERSION", "0.7.0")

    payload = build_mobile_config(
        web_url="https://journal.example",
        api_version="0.7.0",
        additional_capabilities=("offline_sync", "operational_health"),
    )

    assert payload["capabilities"].count("offline_sync") == 1
    assert payload["compatibility"] == {
        "minimum_android_version": "0.6.20",
        "recommended_android_version": "0.7.0",
    }
