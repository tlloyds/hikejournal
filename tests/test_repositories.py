from hike_journal.domain.map_data import MapViewport
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
