from hike_journal.services.repositories import HikeJournalRepository, LIGHTWEIGHT_OBSERVATION_COLUMNS


def test_lightweight_observations_include_species_log_photo_preference() -> None:
    assert "species_log_main_photo:raw_response_json->species_log_main_photo" in LIGHTWEIGHT_OBSERVATION_COLUMNS


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
