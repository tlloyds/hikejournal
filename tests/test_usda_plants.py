from __future__ import annotations

from typing import Any

from hike_journal.services.usda_plants import USDAPlantsClient


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self.payload


def client_for(responses: dict[str, Any]) -> USDAPlantsClient:
    def request(url: str, **_kwargs: Any) -> FakeResponse:
        if "PlantSearch" in url:
            return FakeResponse(responses["search"])
        if "PlantProfile" in url:
            return FakeResponse(responses["profile"])
        return FakeResponse(responses["map"])

    return USDAPlantsClient(
        api_base_url="https://plants.example/api",
        map_query_url="https://plants.example/map/query",
        plants_base_url="https://plants.example",
        request=request,
    )


def test_fetch_status_uses_exact_florida_native_record() -> None:
    client = client_for(
        {
            "search": [{"Plant": {"ScientificName": "Aureolaria pectinata", "Symbol": "AUPE", "CommonName": ""}}],
            "profile": {"Id": 50273, "NativeStatuses": [{"Region": "L48", "Type": "Native"}]},
            "map": {"features": [{"attributes": {"Symbol": "Native"}}]},
        }
    )

    result = client.fetch_status(scientific_name="Aureolaria pectinata", rank="species")

    assert result is not None
    assert result["label"] == "native"
    assert result["establishment_status"] == "native"
    assert result["source"] == "usda_plants"
    assert result["source_url"] == "https://plants.example/plant-profile/AUPE"


def test_fetch_status_does_not_guess_when_state_record_is_both() -> None:
    client = client_for(
        {
            "search": [{"Plant": {"ScientificName": "Example plant", "Symbol": "EXPL", "CommonName": ""}}],
            "profile": {"Id": 10, "NativeStatuses": [{"Region": "L48", "Type": "Native"}]},
            "map": {"features": [{"attributes": {"Symbol": "Both"}}]},
        }
    )

    assert client.fetch_status(scientific_name="Example plant", rank="species") is None


def test_fetch_status_accepts_unambiguous_l48_introduced_fallback() -> None:
    client = client_for(
        {
            "search": [{"Plant": {"ScientificName": "Hemerocallis minor", "Symbol": "HEMI", "CommonName": ""}}],
            "profile": {"Id": 11, "NativeStatuses": [{"Region": "L48", "Type": "Introduced"}]},
            "map": {"features": []},
        }
    )

    result = client.fetch_status(scientific_name="Hemerocallis minor", rank="species")

    assert result is not None
    assert result["label"] == "non_native"
    assert result["establishment_status"] == "introduced"


def test_fetch_status_prefers_non_hybrid_exact_search_result() -> None:
    responses = {
        "search": [
            {"Plant": {"ScientificName": "Rubus pensilvanicus × ursinus", "Symbol": "HYBRID", "CommonName": ""}},
            {"Plant": {"ScientificName": "Rubus pensilvanicus", "Symbol": "RUPE3", "CommonName": ""}},
        ],
        "profile": {"Id": 12, "NativeStatuses": []},
        "map": {"features": [{"attributes": {"Symbol": "Native"}}]},
    }
    client = client_for(responses)

    result = client.fetch_status(scientific_name="Rubus pensilvanicus", rank="species")

    assert result is not None
    assert result["usda_symbol"] == "RUPE3"
