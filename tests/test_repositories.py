from datetime import date

import pytest

from hike_journal.domain.map_data import MapViewport
from hike_journal.models import HikeDraft
from hike_journal.services.repositories import (
    HikeJournalRepository,
    LIGHTWEIGHT_OBSERVATION_COLUMNS,
    MOBILE_DETAIL_OBSERVATION_COLUMNS,
    MOBILE_HIKE_LOCATION_COLUMNS,
    MOBILE_SPECIES_OBSERVATION_COLUMNS,
    MOBILE_SUMMARY_OBSERVATION_COLUMNS,
)


def test_mobile_hike_location_queries_are_scoped_and_projected() -> None:
    calls = []

    class Query:
        def select(self, columns):
            calls.append(("select", columns))
            return self

        def in_(self, column, values):
            calls.append(("in", column, values))
            return self

        def eq(self, column, value):
            calls.append(("eq", column, value))
            return self

        def is_(self, column, value):
            calls.append(("is", column, value))
            return self

        def order(self, column):
            return self

        def range(self, start, end):
            calls.append(("range", start, end))
            return self

        def execute(self):
            return type("Response", (), {"data": []})()

    class Client:
        def table(self, name):
            calls.append(("table", name))
            return Query()

    repository = HikeJournalRepository(client=Client())
    repository.list_hike_locations_by_ids(["place-1"])
    repository.list_hike_locations_by_slugs(["canonical-place"])
    repository.list_hike_location_tags_for_hike_ids(["hike-1"])
    repository.list_mobile_hike_locations_for_state(
        "ME", owner_subject="person-1", owner_email="hiker@example.com"
    )

    assert ("in", "id", ["place-1"]) in calls
    assert ("in", "slug", ["canonical-place"]) in calls
    assert ("in", "hike_id", ["hike-1"]) in calls
    assert ("eq", "state", "ME") in calls
    assert ("eq", "owner_subject", "person-1") in calls
    assert ("eq", "owner_email", "hiker@example.com") in calls
    assert ("select", MOBILE_HIKE_LOCATION_COLUMNS) in calls
    assert ("select", "*") not in calls


def test_mobile_observation_projections_use_columns_in_schema() -> None:
    for projection in (
        MOBILE_DETAIL_OBSERVATION_COLUMNS,
        MOBILE_SUMMARY_OBSERVATION_COLUMNS,
        MOBILE_SPECIES_OBSERVATION_COLUMNS,
    ):
        assert "owner_user_id" not in projection

    calls = []

    class Query:
        def select(self, columns):
            calls.append(columns)
            if "owner_user_id" in columns:
                raise AssertionError("species_observations has no owner_user_id column")
            return self

        def eq(self, *_args):
            return self

        def is_(self, *_args):
            return self

        def range(self, *_args):
            return self

        def execute(self):
            return type("Response", (), {"data": []})()

    class Client:
        def table(self, name):
            assert name == "species_observations"
            return Query()

    repository = HikeJournalRepository(client=Client())
    assert repository.list_mobile_species_observations(unlinked_only=True) == []
    assert calls == [MOBILE_SPECIES_OBSERVATION_COLUMNS]


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


def test_lightweight_observations_can_limit_reads_to_unlinked_rows() -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []

    class Query:
        def select(self, columns):
            calls.append(("select", (columns,)))
            return self

        def is_(self, column, value):
            calls.append(("is", (column, value)))
            return self

        def eq(self, column, value):
            calls.append(("eq", (column, value)))
            return self

        def range(self, start, end):
            calls.append(("range", (start, end)))
            return self

        def execute(self):
            calls.append(("execute", ()))
            return type("Response", (), {"data": []})()

    class Client:
        def table(self, name):
            calls.append(("table", (name,)))
            return Query()

    repository = HikeJournalRepository(client=Client())

    assert repository.list_lightweight_observations(
        status="confirmed",
        unlinked_only=True,
    ) == []
    assert ("is", ("hike_id", "null")) in calls
    assert ("eq", ("status", "confirmed")) in calls


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


def test_route_index_status_preserves_saved_routes_before_spatial_migration() -> None:
    class Query:
        def __init__(self, *, indexed: bool = False):
            self.indexed = indexed

        def select(self, _columns, count=None):
            return self

        def in_(self, _column, _values):
            return self

        @property
        def not_(self):
            return self

        def is_(self, _column, _value):
            self.indexed = True
            return self

        def limit(self, _value):
            return self

        def execute(self):
            if self.indexed:
                raise RuntimeError("column hike_route_imports.track_geom does not exist")
            return type("Response", (), {"count": 1, "data": []})()

    class Client:
        def table(self, _name):
            return Query()

    repository = HikeJournalRepository(client=Client())

    assert repository.get_map_route_index_status(
        visible_hike_ids=["hike-1"],
        hike_id="hike-1",
    ) == (1, 0)


def test_mobile_route_projections_scope_and_skip_duplicate_indexed_geometry() -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    route = {"hike_id": "hike-1", "track_geojson": {"type": "LineString"}}

    class Query:
        def select(self, columns):
            calls.append(("select", (columns,)))
            return self

        def in_(self, column, values):
            calls.append(("in", (column, values)))
            return self

        def eq(self, column, value):
            calls.append(("eq", (column, value)))
            return self

        def order(self, column, desc=False):
            calls.append(("order", (column, desc)))
            return self

        def limit(self, value):
            calls.append(("limit", (value,)))
            return self

        def execute(self):
            return type("Response", (), {"data": [route]})()

    class Client:
        def table(self, name):
            calls.append(("table", (name,)))
            return Query()

    repository = HikeJournalRepository(client=Client())

    assert repository.list_mobile_map_route_imports(["hike-1", "hike-2"]) == [route]
    assert ("select", ("hike_id,track_geojson",)) in calls
    assert ("in", ("hike_id", ["hike-1", "hike-2"])) in calls
    assert not any("track_geom" in str(args) for name, args in calls if name == "select")

    calls.clear()
    replay_route = {
        "track_geojson": {"type": "LineString"},
        "started_at": "2026-09-28T14:00:00Z",
        "duration_seconds": 120,
        "distance_miles": 1.2,
        "track_point_count": 14,
    }

    class ReplayQuery(Query):
        def execute(self):
            return type("Response", (), {"data": [replay_route]})()

    class ReplayClient:
        def table(self, name):
            calls.append(("table", (name,)))
            return ReplayQuery()

    replay_repository = HikeJournalRepository(client=ReplayClient())
    assert replay_repository.get_mobile_hike_route_import("hike-1") == replay_route
    assert ("select", (
        "track_geojson,started_at,duration_seconds,distance_miles,track_point_count",
    )) in calls
    assert ("eq", ("hike_id", "hike-1")) in calls


def test_mobile_map_sightings_rpc_is_scoped_to_visible_hikes_and_owner() -> None:
    calls = []
    expected = [{"id": "photo-1", "lat": 28.1, "lng": -82.1}]

    class RpcCall:
        def execute(self):
            return type("Response", (), {"data": expected})()

    class Client:
        def rpc(self, name, params):
            calls.append((name, params))
            return RpcCall()

    repository = HikeJournalRepository(client=Client())
    context = {
        "mode": "google",
        "user_id": "user-1",
        "subject": "google-1",
        "email": "hiker@example.com",
        "identity_provider": "google",
    }

    assert repository.list_mobile_map_sightings(["hike-1"], context) == expected
    assert calls == [(
        "mobile_map_sightings",
        {
            "p_hike_ids": ["hike-1"],
            "p_owner_user_id": "user-1",
            "p_owner_subject": "google-1",
            "p_owner_email": "hiker@example.com",
            "p_identity_provider": "google",
            "p_include_all": False,
            "p_allow_legacy_email": True,
        },
    )]


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


def test_resolve_google_user_id_prefers_provider_neutral_identity() -> None:
    calls: list[str] = []

    class Query:
        def __init__(self, table_name):
            self.table_name = table_name

        def select(self, _columns):
            return self

        def eq(self, _column, _value):
            return self

        def limit(self, _count):
            return self

        def execute(self):
            calls.append(self.table_name)
            return type("Response", (), {"data": [{"user_id": "canonical-user"}]})()

    class Client:
        def table(self, name):
            return Query(name)

    repository = HikeJournalRepository(client=Client())

    assert repository.resolve_google_user_id("google-subject") == "canonical-user"
    assert calls == ["user_identities"]


def test_resolve_google_user_id_falls_back_to_legacy_app_user() -> None:
    calls: list[str] = []

    class Query:
        def __init__(self, table_name):
            self.table_name = table_name

        def select(self, _columns):
            return self

        def eq(self, _column, _value):
            return self

        def limit(self, _count):
            return self

        def execute(self):
            calls.append(self.table_name)
            if self.table_name == "user_identities":
                raise RuntimeError("relation user_identities does not exist")
            return type("Response", (), {"data": [{"id": "legacy-user"}]})()

    class Client:
        def table(self, name):
            return Query(name)

    repository = HikeJournalRepository(client=Client())

    assert repository.resolve_google_user_id("google-subject") == "legacy-user"
    assert calls == ["user_identities", "app_users"]


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
