from datetime import date

import pytest

from hike_journal.domain.map_data import MapViewport
from hike_journal.models import HikeDraft
from hike_journal.services.repositories import HikeJournalRepository, LIGHTWEIGHT_OBSERVATION_COLUMNS


def test_lightweight_observations_include_species_log_photo_preference() -> None:
    assert "species_log_main_photo:raw_response_json->species_log_main_photo" in LIGHTWEIGHT_OBSERVATION_COLUMNS
    assert "species_taxon_id,rank," in LIGHTWEIGHT_OBSERVATION_COLUMNS
    assert "rank,iconic_taxon_name," in LIGHTWEIGHT_OBSERVATION_COLUMNS
    assert "wikipedia_url:raw_response_json->taxon_enrichment->>wikipedia_url" in LIGHTWEIGHT_OBSERVATION_COLUMNS
    assert "wikipedia_summary:raw_response_json->taxon_enrichment->>wikipedia_summary" in LIGHTWEIGHT_OBSERVATION_COLUMNS


def test_species_log_preferences_use_large_query_batches() -> None:
    repository = HikeJournalRepository(client=None)
    observed_sizes: list[int] = []

    def no_chunks(values, size):
        observed_sizes.append(size)
        return iter(())

    repository._chunks = no_chunks

    assert repository.list_species_log_photo_preferences(["observation-1"]) == []
    assert observed_sizes == [200]


def test_large_batch_size_reduces_species_log_round_trips() -> None:
    repository = HikeJournalRepository(client=None)

    chunks = list(repository._chunks([str(index) for index in range(1473)], size=200))

    assert len(chunks) == 8
    assert len(chunks[0]) == 200
    assert len(chunks[-1]) == 73


def test_selected_hike_marker_query_disables_clustering_without_changing_master_zoom() -> None:
    class RpcCall:
        def execute(self):
            return type("Response", (), {"data": {"type": "FeatureCollection", "features": []}})()

    class Client:
        calls = []

        def rpc(self, name, params):
            self.calls.append((name, params))
            return RpcCall()

    client = Client()
    repository = HikeJournalRepository(client=client)
    viewport = MapViewport(west=-82, south=27, east=-80, north=29, zoom=8)
    common = {
        "visible_hike_ids": ["hike-1"],
        "viewport": viewport,
        "layer_mode": "Both",
        "species_filter": "All confirmed species",
        "range_start": 1,
        "range_end": 10,
    }

    repository.get_map_viewport(hike_id="hike-1", **common)
    repository.get_map_viewport(hike_id=None, **common)

    assert client.calls[0][0] == "map_viewport"
    assert client.calls[0][1]["p_zoom"] == 14.0
    assert client.calls[1][1]["p_zoom"] == 8


def test_quest_save_retries_without_wikipedia_fields_for_legacy_schema() -> None:
    class Table:
        def __init__(self, name):
            self.name = name
            self.payload = None

        def insert(self, payload):
            self.payload = payload
            return self

        def execute(self):
            if self.name == "species_quests":
                return type("Response", (), {"data": [{"id": "quest-1"}]})()
            if "wikipedia_url" in self.payload[0]:
                raise RuntimeError("column species_quest_taxa.wikipedia_url does not exist")
            saved_taxa.extend(self.payload)
            return type("Response", (), {"data": self.payload})()

    class Client:
        def table(self, name):
            return Table(name)

    saved_taxa = []
    repository = HikeJournalRepository(client=Client())
    repository.get_species_quest = lambda _quest_id: {"id": "quest-1", "taxa": saved_taxa}

    result = repository.create_species_quest(
        {"title": "Wetland birds"},
        [{"taxon_id": 123, "common_name": "Heron", "wikipedia_url": "https://example.com/heron"}],
    )

    assert result["id"] == "quest-1"
    assert saved_taxa[0]["taxon_id"] == 123
    assert "wikipedia_url" not in saved_taxa[0]
    assert "wikipedia_summary" not in saved_taxa[0]


def test_media_rows_use_signed_delivery_urls_without_changing_stored_values() -> None:
    original = {
        "id": "photo-1",
        "storage_path": "hikes/hike-1/photo-1.jpg",
        "public_url": "https://public.example/photo-1.jpg",
    }
    repository = HikeJournalRepository(
        client=None,
        media_url_resolver=lambda path: f"https://signed.example/{path}?token=test",
    )

    decorated = repository.decorate_media_row(original)

    assert decorated["public_url"] == (
        "https://signed.example/hikes/hike-1/photo-1.jpg?token=test"
    )
    assert original["public_url"] == "https://public.example/photo-1.jpg"


def test_media_rows_add_a_signed_thumbnail_without_discarding_exif() -> None:
    original = {
        "id": "photo-1",
        "storage_path": "hikes/hike-1/photo-1.jpg",
        "public_url": "https://public.example/photo-1.jpg",
        "exif_json": {
            "gps_latitude": 28.6,
            "hikejournal_thumbnail_storage_path": "hikes/hike-1/thumbs/photo-1.jpg",
        },
    }
    repository = HikeJournalRepository(
        client=None,
        media_url_resolver=lambda path: f"https://signed.example/{path}?token=test",
    )

    decorated = repository.decorate_media_row(original)

    assert decorated["thumbnail_url"].endswith("thumbs/photo-1.jpg?token=test")
    assert decorated["exif_json"] == original["exif_json"]
    assert "thumbnail_url" not in original


def test_hike_create_persists_canonical_and_legacy_ownership_together() -> None:
    inserted: list[dict] = []

    class Table:
        def insert(self, payload):
            inserted.append(payload)
            return self

        def execute(self):
            return type("Response", (), {"data": [{"id": "hike-1", **inserted[-1]}]})()

    class Client:
        @staticmethod
        def table(name):
            assert name == "hikes"
            return Table()

    repository = HikeJournalRepository(client=Client())
    result = repository.create_hike(
        HikeDraft(
            title="Canonical hike",
            hike_date=date(2026, 8, 21),
            distance_miles=4.2,
            location_name="Pine Loop",
            notes="",
            owner_user_id="11111111-1111-4111-8111-111111111111",
            owner_subject="google-subject-1",
            owner_email="hiker@example.com",
        )
    )

    assert result["owner_user_id"] == "11111111-1111-4111-8111-111111111111"
    assert inserted == [
        {
            "title": "Canonical hike",
            "hike_date": "2026-08-21",
            "distance_miles": 4.2,
            "location_name": "Pine Loop",
            "notes": None,
            "owner_subject": "google-subject-1",
            "owner_email": "hiker@example.com",
            "owner_user_id": "11111111-1111-4111-8111-111111111111",
        }
    ]


def test_hike_and_photo_writes_retry_without_only_new_owner_column() -> None:
    attempts: list[tuple[str, dict]] = []

    class Table:
        def __init__(self, name):
            self.name = name

        def insert(self, payload):
            attempts.append((self.name, payload))
            return self

        def execute(self):
            payload = attempts[-1][1]
            if "owner_user_id" in payload:
                raise RuntimeError("column owner_user_id does not exist")
            return type("Response", (), {"data": [{"id": f"{self.name}-1", **payload}]})()

    class Client:
        @staticmethod
        def table(name):
            return Table(name)

    repository = HikeJournalRepository(client=Client())
    draft = HikeDraft(
        title="Rolling deploy",
        hike_date=date(2026, 8, 21),
        distance_miles=None,
        location_name="",
        notes="",
        owner_user_id="11111111-1111-4111-8111-111111111111",
        owner_subject="google-subject-1",
        owner_email="hiker@example.com",
    )
    hike = repository.create_hike(draft)
    photo = repository.create_photo(
        {
            "hike_id": "hikes-1",
            "owner_user_id": draft.owner_user_id,
            "owner_subject": draft.owner_subject,
            "owner_email": draft.owner_email,
        }
    )

    assert hike["owner_subject"] == "google-subject-1"
    assert photo["owner_email"] == "hiker@example.com"
    assert [name for name, _payload in attempts] == ["hikes", "hikes", "photos", "photos"]
    assert "owner_user_id" not in attempts[1][1]
    assert attempts[1][1]["owner_subject"] == "google-subject-1"
    assert "owner_user_id" not in attempts[3][1]
    assert attempts[3][1]["owner_email"] == "hiker@example.com"


@pytest.mark.parametrize(
    "failures",
    [
        ["database connection timed out"],
        ["column owner_user_id does not exist", "duplicate key violates unique constraint"],
    ],
)
def test_hike_create_never_retries_anonymous_after_non_schema_errors(failures) -> None:
    attempts: list[dict] = []

    class Table:
        def insert(self, payload):
            attempts.append(payload)
            return self

        def execute(self):
            raise RuntimeError(failures[len(attempts) - 1])

    class Client:
        @staticmethod
        def table(_name):
            return Table()

    draft = HikeDraft(
        title="Do not duplicate",
        hike_date=date(2026, 8, 21),
        distance_miles=None,
        location_name="",
        notes="",
        owner_user_id="11111111-1111-4111-8111-111111111111",
        owner_subject="google-subject-1",
        owner_email="hiker@example.com",
    )

    with pytest.raises(RuntimeError, match=failures[-1]):
        HikeJournalRepository(client=Client()).create_hike(draft)

    assert len(attempts) == len(failures)
    assert attempts[-1]["owner_subject"] == "google-subject-1"
    assert attempts[-1]["owner_email"] == "hiker@example.com"


def test_hike_create_strips_all_legacy_ownership_only_for_confirmed_old_schema() -> None:
    attempts: list[dict] = []

    class Table:
        def insert(self, payload):
            attempts.append(payload)
            return self

        def execute(self):
            if len(attempts) == 1:
                raise RuntimeError("column owner_user_id does not exist")
            if len(attempts) == 2:
                raise RuntimeError("column owner_subject does not exist")
            return type("Response", (), {"data": [{"id": "legacy-hike", **attempts[-1]}]})()

    class Client:
        @staticmethod
        def table(_name):
            return Table()

    result = HikeJournalRepository(client=Client()).create_hike(
        HikeDraft(
            title="Old schema",
            hike_date=date(2026, 8, 21),
            distance_miles=None,
            location_name="",
            notes="",
            owner_user_id="11111111-1111-4111-8111-111111111111",
            owner_subject="google-subject-1",
            owner_email="hiker@example.com",
        )
    )

    assert result["id"] == "legacy-hike"
    assert len(attempts) == 3
    assert {"owner_user_id", "owner_subject", "owner_email"}.isdisjoint(attempts[-1])
