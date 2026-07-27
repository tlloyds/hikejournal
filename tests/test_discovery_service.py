from datetime import UTC, date, datetime, timedelta

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
