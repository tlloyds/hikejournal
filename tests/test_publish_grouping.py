from __future__ import annotations

from types import SimpleNamespace

import app


class FakeInatClient:
    def __init__(self) -> None:
        self.created = []
        self.attached = []

    def validate_credentials(self) -> None:
        return None

    def create_observation(self, **payload):
        self.created.append(payload)
        return {"id": 987654, "uri": "https://www.inaturalist.org/observations/987654"}

    def attach_photo_to_observation(self, **payload) -> None:
        self.attached.append(payload)


class FakeRepository:
    def __init__(self) -> None:
        self.raw_updates = {}
        self.posting_updates = {}

    def update_observation_raw_payload(self, observation_id, raw_payload):
        self.raw_updates[str(observation_id)] = raw_payload
        return {"id": observation_id, "raw_response_json": raw_payload}

    def update_observation_inat_posting(self, observation_id, **payload):
        self.posting_updates[str(observation_id)] = payload
        return {"id": observation_id, **payload}


def test_grouped_post_links_every_local_observation(monkeypatch) -> None:
    lead_observation = {
        "id": "observation-1",
        "taxon_id": 123,
        "common_name": "Test flower",
        "scientific_name": "Flora testus",
        "raw_response_json": {"lead_metadata": True},
    }
    member_observation = {
        "id": "observation-2",
        "taxon_id": 123,
        "common_name": "Test flower",
        "scientific_name": "Flora testus",
        "raw_response_json": {"member_metadata": True},
    }
    lead_photo = {
        "id": "photo-1",
        "public_url": "https://example.com/photo-1.jpg",
        "content_type": "image/jpeg",
        "taken_at": "2026-06-21T14:00:00-04:00",
        "lat": 28.6,
        "lng": -81.1,
    }
    member_photo = {
        "id": "photo-2",
        "public_url": "https://example.com/photo-2.jpg",
        "content_type": "image/jpeg",
        "taken_at": "2026-06-21T14:05:00-04:00",
        "lat": 28.6001,
        "lng": -81.1001,
    }
    repository = FakeRepository()
    inat_client = FakeInatClient()

    monkeypatch.setattr(app, "fetch_observations_by_ids", lambda _ids: [lead_observation, member_observation])
    monkeypatch.setattr(app, "_download_public_image", lambda _url: b"image-bytes")
    monkeypatch.setattr(app, "invalidate_data_cache", lambda: None)
    monkeypatch.setattr(
        app.st,
        "session_state",
        SimpleNamespace(current_user_context={"subject": "user-1", "email": "user@example.com"}),
    )

    posting = app.post_observation_to_inaturalist(
        repository,
        inat_client,
        lead_observation,
        lead_photo,
        place_guess="Test Preserve",
        related_records=[{"observation": member_observation, "photo": member_photo}],
    )

    assert len(inat_client.created) == 1
    assert len(inat_client.attached) == 2
    assert posting["observation_id"] == 987654
    assert posting["grouped"] is True
    assert posting["local_observation_ids"] == ["observation-1", "observation-2"]
    assert set(repository.posting_updates) == {"observation-1", "observation-2"}
    assert all(update["inat_observation_id"] == 987654 for update in repository.posting_updates.values())
    assert repository.raw_updates["observation-1"]["lead_metadata"] is True
    assert repository.raw_updates["observation-2"]["member_metadata"] is True
    assert repository.raw_updates["observation-1"]["inat_posting"]["group_role"] == "lead"
    assert repository.raw_updates["observation-2"]["inat_posting"]["group_role"] == "member"
