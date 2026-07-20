from __future__ import annotations

from hike_journal.services.inat import InatRequestError
from hike_journal.services.inat_publishing import (
    get_publish_state,
    publish_observation_group,
    publish_single_observation,
)


class FakeRepository:
    def __init__(self) -> None:
        self.raw_payload = None
        self.posting = None
        self.raw_payloads = {}
        self.postings = {}

    def update_observation_raw_payload(self, _observation_id, raw_payload):
        self.raw_payload = raw_payload
        self.raw_payloads[_observation_id] = raw_payload

    def update_observation_inat_posting(self, _observation_id, **posting):
        self.posting = posting
        self.postings[_observation_id] = posting


class FakeInatClient:
    def __init__(self, *, photo_fails: bool = False) -> None:
        self.photo_fails = photo_fails
        self.created = None
        self.attached = None
        self.attached_all = []

    def validate_credentials(self) -> None:
        return None

    def create_observation(self, **payload):
        self.created = payload
        return {"id": 987654, "uri": "https://www.inaturalist.org/observations/987654"}

    def attach_photo_to_observation(self, **payload):
        if self.photo_fails:
            raise InatRequestError("photo failed")
        self.attached = payload
        self.attached_all.append(payload)


def observation(**overrides):
    return {
        "id": "observation-1",
        "photo_id": "photo-1",
        "status": "confirmed",
        "taxon_id": 123,
        "common_name": "Swamp lily",
        "scientific_name": "Crinum americanum",
        "raw_response_json": {"source": "cv"},
        **overrides,
    }


def photo(**overrides):
    return {
        "id": "photo-1",
        "public_url": "https://images.example/photo.jpg",
        "caption": "Wet prairie margin",
        "taken_at": "2026-07-12T08:30:00-04:00",
        "lat": 28.6,
        "lng": -81.1,
        **overrides,
    }


def test_publish_single_observation_creates_photo_backed_record() -> None:
    repository = FakeRepository()
    client = FakeInatClient()

    posting = publish_single_observation(
        repository,
        client,
        observation(),
        photo(),
        place_guess="Test Preserve",
        owner_subject="user-1",
        owner_email="user@example.com",
        image_loader=lambda _url: b"image-bytes",
    )

    assert posting["observation_id"] == 987654
    assert posting["photo_attached"] is True
    assert client.created["taxon_id"] == 123
    assert client.created["place_guess"] == "Test Preserve"
    assert client.created["description"].startswith("Wet prairie margin")
    assert client.attached["image_bytes"] == b"image-bytes"
    assert repository.raw_payload["source"] == "cv"
    assert repository.raw_payload["inat_posting"]["observation_id"] == 987654
    assert repository.posting["inat_photo_attached"] is True


def test_partial_photo_failure_is_persisted_as_needs_attention() -> None:
    repository = FakeRepository()
    client = FakeInatClient(photo_fails=True)

    posting = publish_single_observation(
        repository,
        client,
        observation(),
        photo(),
        place_guess=None,
        owner_subject=None,
        owner_email=None,
        image_loader=lambda _url: b"image-bytes",
    )

    assert posting["photo_attached"] is False
    assert posting["attached_photo_count"] == 0
    assert repository.posting["inat_photo_attached"] is False
    assert get_publish_state({"inat_observation_id": 987654, "inat_photo_attached": False}) == "needs_attention"


def test_already_posted_observation_cannot_duplicate() -> None:
    repository = FakeRepository()
    client = FakeInatClient()

    try:
        publish_single_observation(
            repository,
            client,
            observation(inat_observation_id=55),
            photo(),
            place_guess=None,
            owner_subject=None,
            owner_email=None,
            image_loader=lambda _url: b"image-bytes",
        )
    except RuntimeError as exc:
        assert "already been published" in str(exc)
    else:
        raise AssertionError("Expected duplicate publish protection")


def test_publish_group_creates_one_observation_with_multiple_photos_and_options() -> None:
    repository = FakeRepository()
    client = FakeInatClient()
    records = [
        (observation(), photo()),
        (
            observation(id="observation-2", photo_id="photo-2"),
            photo(id="photo-2", public_url="https://images.example/photo-2.jpg"),
        ),
    ]

    posting = publish_observation_group(
        repository,
        client,
        records,
        place_guess="Test Preserve",
        owner_subject="user-1",
        owner_email="user@example.com",
        image_loader=lambda url: url.encode(),
        description="Two angles from the wet prairie.",
        tags=["wetland", "summer"],
        geoprivacy="obscured",
        captive=True,
    )

    assert posting["grouped"] is True
    assert posting["photo_count"] == 2
    assert posting["attached_photo_count"] == 2
    assert client.created["geoprivacy"] == "obscured"
    assert client.created["captive"] is True
    assert client.created["tags"] == ["HikeJournal", "wetland", "summer"]
    assert len(client.attached_all) == 2
    assert set(repository.postings) == {"observation-1", "observation-2"}
