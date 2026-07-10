import app


class RecordingRepository:
    def __init__(self) -> None:
        self.deleted_observation_ids: list[str] = []
        self.status_updates: list[tuple[list[str], str]] = []

    def delete_observations(self, observation_ids: list[str]) -> None:
        self.deleted_observation_ids = observation_ids

    def update_photo_processing_statuses(self, photo_ids: list[str], status: str) -> None:
        self.status_updates.append((photo_ids, status))


def test_reject_removes_suggestion_and_keeps_photo_in_review(monkeypatch) -> None:
    repository = RecordingRepository()
    monkeypatch.setattr(app, "invalidate_data_cache", lambda: None)

    app.reject_observations(
        repository,
        [{"id": "observation-1", "photo_id": "photo-1"}],
        [{"id": "photo-1"}],
    )

    assert repository.deleted_observation_ids == ["observation-1"]
    assert repository.status_updates == [(["photo-1"], app.REVIEW_QUEUE_STATUS)]
