from datetime import UTC, date, datetime, timedelta

from hike_journal.domain.discovery import normalize_iconic_taxon
from hike_journal.services.discovery import InatDiscoveryClient, SpeciesDiscoveryService


class Repository:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot
        self.saved_snapshot = None

    def get_species_discovery_snapshot(self, _cache_key):
        return self.snapshot

    def upsert_species_discovery_snapshot(self, payload):
        self.saved_snapshot = payload
        return payload

    def list_hike_locations(self):
        return [
            {"id": "area-1", "name": "Alafia Scrub Preserve", "lat": 27.86, "lng": -82.34},
            {"id": "missing", "name": "Unknown", "lat": None, "lng": None},
        ]


class InatClient:
    calls = 0

    def fetch_species_counts(self, **_kwargs):
        self.calls += 1
        return {
            "results": [
                {
                    "count": 88,
                    "taxon": {
                        "id": 3751,
                        "rank": "species",
                        "name": "Eudocimus albus",
                        "preferred_common_name": "White Ibis",
                    },
                }
            ]
        }


def test_normalize_iconic_taxon_accepts_multiple_groups() -> None:
    assert normalize_iconic_taxon("Birds,Plantae,Birds") == "Plantae,Aves"
    assert normalize_iconic_taxon("Plantae,Aves") == "Plantae,Aves"


def test_list_areas_requires_coordinates_and_supports_search() -> None:
    areas = SpeciesDiscoveryService.list_areas(Repository(), "scrub")

    assert [area["id"] for area in areas] == ["area-1"]


def test_nearby_fetches_saves_and_attaches_collection_progress() -> None:
    repository = Repository()
    inat = InatClient()
    now = datetime(2026, 7, 26, tzinfo=UTC)
    service = SpeciesDiscoveryService(repository, inat_client=inat, now=now)

    result = service.nearby(
        area={"id": "area-1", "name": "Alafia", "lat": 27.86, "lng": -82.34},
        target_date=date(2026, 7, 26),
        radius_km=10,
        iconic_taxon="Birds",
        observations=[
            {
                "taxon_id": 3751,
                "species_taxon_id": 3751,
                "rank": "species",
                "photo_id": "photo-1",
            }
        ],
        photos_by_id={"photo-1": {"public_url": "mine.jpg", "taken_at": "2026-07-20"}},
    )

    assert inat.calls == 1
    assert repository.saved_snapshot["expires_at"] == (now + timedelta(hours=24)).isoformat()
    assert result["progress"]["collected_count"] == 1
    assert result["taxa"][0]["collection_photo_url"] == "mine.jpg"
    assert result["source"]["guidance"].startswith("Reporting frequency")
    assert "Both the location and date window are applied." in result["taxa"][0]["match_reason"]


def test_fresh_snapshot_avoids_network() -> None:
    now = datetime(2026, 7, 26, tzinfo=UTC)
    repository = Repository(
        {
            "taxa": [
                {
                    "taxon_id": 2,
                    "common_name": "Live Oak",
                    "observation_count": 50,
                    "frequency_band": "Often reported",
                }
            ],
            "fetched_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
        }
    )
    inat = InatClient()

    result = SpeciesDiscoveryService(repository, inat_client=inat, now=now).nearby(
        area={"id": "area-1", "name": "Alafia", "lat": 27.86, "lng": -82.34},
        target_date=date(2026, 7, 26),
        radius_km=10,
        iconic_taxon=None,
        observations=[],
        photos_by_id={},
    )

    assert inat.calls == 0
    assert result["source"]["from_cache"] is True


def test_quest_progress_keeps_the_frozen_target_denominator() -> None:
    payload = SpeciesDiscoveryService(Repository(), now=datetime(2026, 7, 26, tzinfo=UTC)).quest_payload(
        {
            "id": "quest-1",
            "title": "Wetland birds",
            "status": "active",
            "target_count": 50,
            "taxa": [{"taxon_id": 3751, "common_name": "White Ibis"}],
        },
        observations=[],
        photos_by_id={},
    )

    assert payload["progress"] == {
        "collected_count": 0,
        "total_count": 50,
        "remaining_count": 50,
    }
    assert payload["focus_progress"] == {
        "collected_count": 0,
        "total_count": 0,
        "remaining_count": 0,
    }


def test_quest_payload_exposes_only_ordered_focus_targets_for_the_quest_view() -> None:
    payload = SpeciesDiscoveryService(Repository(), now=datetime(2026, 7, 26, tzinfo=UTC)).quest_payload(
        {
            "id": "quest-1",
            "target_count": 50,
            "taxa": [
                {"taxon_id": 1, "common_name": "One", "focus_order": 2},
                {"taxon_id": 2, "common_name": "Two", "focus_order": None},
                {"taxon_id": 3, "common_name": "Three", "focus_order": 1},
            ],
        },
        observations=[{"taxon_id": 3, "rank": "species", "photo_id": "photo-3"}],
        photos_by_id={"photo-3": {"public_url": "three.jpg", "taken_at": "2026-07-20"}},
    )

    assert [item["taxon_id"] for item in payload["focus_taxa"]] == [3, 1]
    assert payload["focus_progress"] == {
        "collected_count": 1,
        "total_count": 2,
        "remaining_count": 1,
    }


def test_inat_discovery_client_builds_public_frequency_query(monkeypatch) -> None:
    captured = {}

    class Response:
        status_code = 200
        text = ""
        headers = {}

        @staticmethod
        def json():
            return {"results": []}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("hike_journal.services.discovery.requests.get", fake_get)

    InatDiscoveryClient("https://api.example/v2").fetch_species_counts(
        lat=28.1,
        lng=-82.7,
        radius_km=10,
        months=(6, 7, 8),
        iconic_taxon="Plantae",
        observed_after="2016-07-26",
    )

    assert captured["url"].endswith("/observations/species_counts")
    assert captured["params"]["quality_grade"] == "research"
    assert captured["params"]["captive"] == "false"
    assert captured["params"]["rank"] == "species"
    assert captured["params"]["month"] == "6,7,8"
    assert captured["params"]["iconic_taxa"] == "Plantae"


def test_inat_discovery_client_can_request_the_expanded_field_list(monkeypatch) -> None:
    captured = {}

    class Response:
        status_code = 200
        text = ""
        headers = {}

        @staticmethod
        def json():
            return {"results": []}

    def fake_get(_url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("hike_journal.services.discovery.requests.get", fake_get)

    InatDiscoveryClient("https://api.example/v2").fetch_species_counts(
        lat=28.1,
        lng=-82.7,
        radius_km=10,
        months=(6, 7, 8),
        iconic_taxon=None,
        observed_after="2016-07-26",
        limit=100,
    )

    assert captured["params"]["per_page"] == 100


def test_inat_discovery_client_builds_quest_sightings_query(monkeypatch) -> None:
    captured = {}

    class Response:
        status_code = 200
        text = ""
        headers = {}

        @staticmethod
        def json():
            return {"total_results": 0, "results": []}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("hike_journal.services.discovery.requests.get", fake_get)

    InatDiscoveryClient("https://api.example/v2").fetch_species_observations(
        taxon_id=163916,
        lat=28.4985,
        lng=-80.99675,
        radius_km=10,
        months=(6, 7, 8),
        observed_after="2016-07-28",
    )

    assert captured["url"].endswith("/observations")
    assert captured["params"]["taxon_id"] == 163916
    assert captured["params"]["quality_grade"] == "research"
    assert captured["params"]["geo"] == "true"
    assert captured["params"]["month"] == "6,7,8"
    assert captured["params"]["per_page"] == 200


def test_quest_sightings_payload_maps_public_and_obscured_records() -> None:
    class SightingsClient:
        def fetch_species_observations(self, **kwargs):
            assert kwargs["taxon_id"] == 163916
            assert kwargs["months"] == (6, 7, 8)
            return {
                "total_results": 2,
                "results": [
                    {
                        "id": 384453204,
                        "observed_on": "2026-07-23",
                        "uri": "https://www.inaturalist.org/observations/384453204",
                        "geojson": {"type": "Point", "coordinates": [-80.9994, 28.5693]},
                        "obscured": False,
                        "positional_accuracy": 14,
                        "place_guess": "Christmas, FL",
                        "user": {"login": "csoliz"},
                        "photos": [
                            {
                                "url": "https://images.example/703755607/square.jpg",
                                "attribution": "© observer",
                                "license_code": "cc-by-nc",
                            }
                        ],
                    },
                    {
                        "id": 2,
                        "observed_on": "2025-07-01",
                        "geojson": {"type": "Point", "coordinates": [-80.97, 28.55]},
                        "obscured": True,
                        "photos": [],
                    },
                ],
            }

    quest = {
        "id": "quest-1",
        "title": "Summer lilies",
        "area_name": "Florida Trail, Tosohatchee",
        "lat": 28.4985,
        "lng": -80.99675,
        "radius_km": 10,
        "months": [6, 7, 8],
        "taxa": [
            {
                "taxon_id": 163916,
                "common_name": "Alligator lily",
                "scientific_name": "Hymenocallis palmeri",
            }
        ],
    }

    result = SpeciesDiscoveryService(
        Repository(),
        inat_client=SightingsClient(),
        now=datetime(2026, 7, 28, tzinfo=UTC),
    ).quest_sightings_payload(quest, taxon_id=163916)

    assert result["mapped_count"] == 2
    assert result["sightings"][0]["photo_url"].endswith("/medium.jpg")
    assert result["sightings"][0]["positional_accuracy_m"] == 14
    assert result["sightings"][1]["obscured"] is True
    assert "private coordinates are never exposed" in result["source"]["guidance"]


def test_quest_sightings_rejects_species_outside_the_quest() -> None:
    service = SpeciesDiscoveryService(Repository(), inat_client=object())

    try:
        service.quest_sightings_payload({"taxa": []}, taxon_id=163916)
        raise AssertionError("Expected a validation error")
    except ValueError as exc:
        assert "belongs to this Field Quest" in str(exc)


def test_nearby_sightings_reuses_the_seasonal_map_query() -> None:
    captured = {}

    class SightingsClient:
        def fetch_species_observations(self, **kwargs):
            captured.update(kwargs)
            return {"total_results": 0, "results": []}

    result = SpeciesDiscoveryService(
        Repository(),
        inat_client=SightingsClient(),
        now=datetime(2026, 7, 28, tzinfo=UTC),
    ).nearby_sightings_payload(
        area={"id": "", "name": "Current area", "lat": 28.5, "lng": -81.0},
        target_date=date(2026, 7, 28),
        radius_km=10,
        taxon_id=163916,
    )

    assert captured["taxon_id"] == 163916
    assert captured["months"] == (6, 7, 8)
    assert captured["lat"] == 28.5
    assert captured["lng"] == -81.0
    assert result["quest"]["title"] == "Nearby field list"
    assert result["mapped_count"] == 0
