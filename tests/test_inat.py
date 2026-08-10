from datetime import UTC, datetime, timedelta
import base64
import json

import pytest

from hike_journal.services import inat
from hike_journal.services.inat import (
    InatClient,
    InatRequestError,
    build_observation_sync_candidate,
    extract_observation_taxon_snapshot,
    extract_taxon_enrichment,
    parse_candidate,
    resolve_access_token_for_user,
)


def test_get_retries_temporary_transport_failures(monkeypatch) -> None:
    attempts = []

    class Response:
        status_code = 200

    def fake_request(*_args, **_kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise inat.requests.ConnectionError("server disconnected")
        return Response()

    monkeypatch.setattr(inat.requests, "request", fake_request)
    monkeypatch.setattr(inat.time, "sleep", lambda *_args: None)
    client = InatClient(access_token="token", base_url="https://api.example/v1")
    client.request_interval_seconds = 0

    response = client._request("get", "https://api.example/v1/taxa/1")

    assert response.status_code == 200
    assert len(attempts) == 3


def test_post_does_not_retry_unless_call_is_explicitly_safe(monkeypatch) -> None:
    attempts = []

    def fake_request(*_args, **_kwargs):
        attempts.append(1)
        raise inat.requests.ConnectionError("server disconnected")

    monkeypatch.setattr(inat.requests, "request", fake_request)
    monkeypatch.setattr(inat.time, "sleep", lambda *_args: None)
    client = InatClient(access_token="token", base_url="https://api.example/v1")
    client.request_interval_seconds = 0

    with pytest.raises(InatRequestError, match="connection to iNaturalist was interrupted"):
        client._request("post", "https://api.example/v1/observations")

    assert len(attempts) == 1


def test_computer_vision_post_retries_temporary_transport_failure(monkeypatch) -> None:
    attempts = []

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {
                "results": [
                    {
                        "score": 0.9,
                        "taxon": {
                            "id": 1,
                            "name": "Quercus virginiana",
                            "preferred_common_name": "Live Oak",
                        },
                    }
                ]
            }

    def fake_request(*_args, **_kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise inat.requests.ConnectionError("server disconnected")
        return Response()

    monkeypatch.setattr(inat.requests, "request", fake_request)
    monkeypatch.setattr(inat.time, "sleep", lambda *_args: None)
    client = InatClient(access_token="token", base_url="https://api.example/v1")
    client.cv_request_interval_seconds = 0

    candidates, _payload = client.score_species_candidates(
        image_bytes=b"image",
        filename="photo.jpg",
        lat=None,
        lng=None,
        observed_on=None,
    )

    assert candidates[0].taxon_id == 1
    assert len(attempts) == 2


def test_parse_candidate_prefers_highest_score() -> None:
    payload = {
        "results": [
            {"score": 0.32, "taxon": {"id": 1, "name": "Quercus virginiana", "preferred_common_name": "Live Oak"}},
            {"score": 0.91, "taxon": {"id": 2, "name": "Tillandsia usneoides", "preferred_common_name": "Spanish Moss"}},
        ]
    }

    result = parse_candidate(payload)

    assert result is not None
    assert result.common_name == "Spanish Moss"
    assert result.scientific_name == "Tillandsia usneoides"
    assert result.confidence == 0.91
    assert result.taxon_id == 2


def test_extract_taxon_enrichment_collects_aliases_and_summary() -> None:
    taxon = {
        "name": "Sagittaria lancifolia",
        "preferred_common_name": "lanceleaf arrowhead",
        "english_common_name": "duck potato",
        "rank": "species",
        "iconic_taxon_name": "Plantae",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Sagittaria_lancifolia",
        "wikipedia_summary": "<i><b>Sagittaria lancifolia</b></i>, the <b>bulltongue arrowhead</b>, is a wetland plant.",
    }

    enrichment = extract_taxon_enrichment(taxon)

    assert enrichment["preferred_common_name"] == "lanceleaf arrowhead"
    assert enrichment["english_common_name"] == "duck potato"
    assert enrichment["rank"] == "species"
    assert enrichment["iconic_taxon_name"] == "Plantae"
    assert enrichment["wikipedia_summary"] == "Sagittaria lancifolia, the bulltongue arrowhead, is a wetland plant."
    assert "lanceleaf arrowhead" in enrichment["alias_names"]
    assert "duck potato" in enrichment["alias_names"]
    assert "bulltongue arrowhead" in enrichment["alias_names"]


def test_extract_taxon_enrichment_resolves_subspecies_parent() -> None:
    enrichment = extract_taxon_enrichment(
        {
            "id": 456,
            "name": "Example species floridana",
            "rank": "subspecies",
            "ancestor_ids": [1, 2, 123],
        }
    )

    assert enrichment["species_taxon_id"] == 123
    assert enrichment["ancestor_ids"] == [1, 2, 123]


def test_extract_taxon_enrichment_ignores_v2_self_ancestor() -> None:
    enrichment = extract_taxon_enrichment(
        {
            "id": 559678,
            "name": "Dendrocygna autumnalis fulgens",
            "rank": "subspecies",
            "ancestor_ids": [1, 2, 6890, 6893, 559678],
        }
    )

    assert enrichment["taxon_id"] == 559678
    assert enrichment["species_taxon_id"] == 6893


def test_taxon_enrichment_is_available_without_an_inat_account(monkeypatch) -> None:
    captured = {}

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {
                "results": [
                    {
                        "id": 559678,
                        "name": "Dendrocygna autumnalis fulgens",
                        "rank": "subspecies",
                        "ancestor_ids": [1, 2, 6890, 6893],
                    }
                ]
            }

    client = InatClient(access_token="", base_url="https://api.example/v1")

    def fake_request(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return Response()

    monkeypatch.setattr(client, "_request", fake_request)

    enrichment = client.fetch_taxon_enrichment(559678)

    assert enrichment["species_taxon_id"] == 6893
    assert captured["headers"].get("Authorization") is None


def test_observation_creation_uses_inaturalist_web_publisher_request(monkeypatch) -> None:
    captured = {}

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"id": 123}

    client = InatClient(access_token="token", base_url="https://api.example/v1")

    def fake_request(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return Response()

    monkeypatch.setattr(client, "_request", fake_request)

    client.create_observation(
        taxon_id=42048,
        species_guess="White-tailed Deer",
        observed_on=datetime(2026, 8, 2, 9, 36),
        lat=28.6,
        lng=-81.1,
        description="Posted from HikeJournal.",
        tags=["HikeJournal"],
        geoprivacy="open",
        captive=True,
    )

    assert captured["url"] == "https://www.inaturalist.org/observations.json"
    assert captured["data"] == {
        "observation[taxon_id]": "42048",
        "observation[observed_on_string]": "2026-08-02 09:36:00",
        "observation[latitude]": "28.6",
        "observation[longitude]": "-81.1",
        "observation[description]": "Posted from HikeJournal.",
        "observation[tag_list]": "HikeJournal",
        "observation[geoprivacy]": "open",
        "observation[captive_flag]": "true",
    }


def test_batch_taxon_enrichment_uses_public_lookup(monkeypatch) -> None:
    captured = {}

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {
                "results": [
                    {"id": 11, "name": "Example alpha", "rank": "species"},
                    {
                        "id": 12,
                        "name": "Example alpha beta",
                        "rank": "subspecies",
                        "ancestor_ids": [1, 11],
                    },
                ]
            }

    client = InatClient(access_token="", base_url="https://api.example/v1")

    def fake_request(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return Response()

    monkeypatch.setattr(client, "_request", fake_request)

    result = client.fetch_taxon_enrichments([11, 12, 11])

    assert sorted(result) == [11, 12]
    assert result[12]["species_taxon_id"] == 11
    assert captured["headers"].get("Authorization") is None


def test_extract_observation_taxon_snapshot_reads_active_taxon() -> None:
    payload = {
        "results": [
            {
                "id": 371091929,
                "community_taxon_id": 123,
                "quality_grade": "needs_id",
                "updated_at": "2026-06-15T12:00:00Z",
                "taxon": {
                    "id": 456,
                    "name": "Phytolacca americana",
                    "preferred_common_name": "American pokeweed",
                    "rank": "species",
                    "iconic_taxon_name": "Plantae",
                },
                "identifications": [{"id": 1}, {"id": 2}],
            }
        ]
    }

    snapshot = extract_observation_taxon_snapshot(payload)

    assert snapshot is not None
    assert snapshot["observation_id"] == 371091929
    assert snapshot["taxon_id"] == 456
    assert snapshot["common_name"] == "American pokeweed"
    assert snapshot["scientific_name"] == "Phytolacca americana"
    assert snapshot["community_taxon_id"] == 123
    assert snapshot["identification_count"] == 2


def test_build_observation_sync_candidate_returns_none_when_taxon_matches() -> None:
    local = {"id": "local-1", "taxon_id": 456, "common_name": "American pokeweed", "scientific_name": "Phytolacca americana"}
    remote = {"id": 371091929, "taxon": {"id": 456, "name": "Phytolacca americana", "preferred_common_name": "American pokeweed"}}

    assert build_observation_sync_candidate(local, remote) is None


def test_build_observation_sync_candidate_detects_changed_taxon() -> None:
    local = {
        "id": "local-1",
        "taxon_id": 456,
        "common_name": "American pokeweed",
        "scientific_name": "Phytolacca americana",
        "inat_observation_id": 371091929,
        "inat_observation_url": "https://www.inaturalist.org/observations/371091929",
    }
    remote = {
        "id": 371091929,
        "taxon": {
            "id": 789,
            "name": "Phytolacca rigida",
            "preferred_common_name": "Maritime pokeweed",
        },
    }

    candidate = build_observation_sync_candidate(local, remote)

    assert candidate is not None
    assert candidate["reason"] == "changed_taxon"
    assert candidate["local"]["taxon_id"] == 456
    assert candidate["inat"]["taxon_id"] == 789
    assert candidate["inat"]["common_name"] == "Maritime pokeweed"


def test_build_observation_sync_candidate_ignores_missing_remote_taxon() -> None:
    local = {"id": "local-1", "taxon_id": 456, "common_name": "American pokeweed", "scientific_name": "Phytolacca americana"}
    remote = {"id": 371091929, "taxon": None}

    assert build_observation_sync_candidate(local, remote) is None


def test_build_observation_sync_candidate_offers_name_only_local_update() -> None:
    local = {
        "id": "local-1",
        "taxon_id": None,
        "common_name": "Maritime pokeweed",
        "scientific_name": "Phytolacca rigida",
        "inat_observation_id": 371091929,
    }
    remote = {
        "id": 371091929,
        "taxon": {
            "id": 789,
            "name": "Phytolacca rigida",
            "preferred_common_name": "Maritime pokeweed",
        },
    }

    candidate = build_observation_sync_candidate(local, remote)

    assert candidate is not None
    assert candidate["reason"] == "missing_local_taxon"
    assert candidate["inat"]["taxon_id"] == 789


def test_resolve_oauth_record_exchanges_legacy_access_token_for_api_token(monkeypatch) -> None:
    oauth_access_token = "oauth-token"
    api_token = _build_fake_jwt()
    saved_records = []

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"api_token": api_token}

    monkeypatch.setattr(
        inat,
        "load_inat_token_record_for_user",
        lambda **_kwargs: {
            "token_kind": "oauth",
            "access_token": oauth_access_token,
            "refresh_token": "refresh-token",
        },
    )
    monkeypatch.setattr(inat.requests, "get", lambda *_args, **_kwargs: FakeResponse())
    monkeypatch.setattr(inat, "save_inat_token_record_for_user", lambda **kwargs: saved_records.append(kwargs["record"]))

    resolved = resolve_access_token_for_user(subject="user-1", email="user@example.com")

    assert resolved == api_token
    assert saved_records[0]["api_token"] == api_token
    assert saved_records[0]["oauth_access_token"] == oauth_access_token
    assert "access_token" not in saved_records[0]


def _build_fake_jwt() -> str:
    header = _base64url_json({"alg": "none", "typ": "JWT"})
    payload = _base64url_json({"exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp())})
    return f"{header}.{payload}.signature"


def _base64url_json(payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    return encoded.rstrip("=")
