from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import mobile_api
from hike_journal.domain.routes import delete_hike_and_assets


class DeletionRepository:
    def __init__(self) -> None:
        self.deleted_hike_id: str | None = None

    def list_photos(self, hike_id: str) -> list[dict[str, str]]:
        assert hike_id == "hike-1"
        return [
            {"storage_path": "hikes/hike-1/photo.jpg"},
            {"storage_path": "hikes/hike-1/video.mp4"},
            {"storage_path": "hikes/hike-1/photo.jpg"},
            {"storage_path": ""},
        ]

    def get_hike_route_import(self, hike_id: str, *, raise_errors: bool = False) -> dict[str, str]:
        assert hike_id == "hike-1"
        assert raise_errors is True
        return {"source_storage_path": "hikes/hike-1/imports/route.tcx"}

    def delete_hike(self, hike_id: str) -> None:
        self.deleted_hike_id = hike_id


class DeletionStorage:
    def __init__(self, failing_path: str | None = None) -> None:
        self.deleted_paths: list[str] = []
        self.failing_path = failing_path

    def delete_file(self, storage_path: str) -> None:
        self.deleted_paths.append(storage_path)
        if storage_path == self.failing_path:
            raise OSError("storage unavailable")


def test_hike_deletion_removes_every_unique_asset_before_database_rows() -> None:
    repository = DeletionRepository()
    storage = DeletionStorage()

    delete_hike_and_assets(repository, storage, "hike-1")

    assert storage.deleted_paths == [
        "hikes/hike-1/imports/route.tcx",
        "hikes/hike-1/photo.jpg",
        "hikes/hike-1/video.mp4",
    ]
    assert repository.deleted_hike_id == "hike-1"


def test_hike_deletion_keeps_database_rows_when_an_asset_cannot_be_removed() -> None:
    repository = DeletionRepository()
    storage = DeletionStorage(failing_path="hikes/hike-1/photo.jpg")

    with pytest.raises(RuntimeError, match="Deletion is not complete"):
        delete_hike_and_assets(repository, storage, "hike-1")

    assert storage.deleted_paths == [
        "hikes/hike-1/imports/route.tcx",
        "hikes/hike-1/photo.jpg",
        "hikes/hike-1/video.mp4",
    ]
    assert repository.deleted_hike_id is None


def test_hike_deletion_retry_finishes_after_a_partial_storage_failure() -> None:
    repository = DeletionRepository()

    class RetryStorage(DeletionStorage):
        failed_once = False

        def delete_file(self, storage_path: str) -> None:
            self.deleted_paths.append(storage_path)
            if storage_path.endswith("photo.jpg") and not self.failed_once:
                self.failed_once = True
                raise OSError("temporary storage failure")

    storage = RetryStorage()
    with pytest.raises(RuntimeError, match="retry"):
        delete_hike_and_assets(repository, storage, "hike-1")

    delete_hike_and_assets(repository, storage, "hike-1")

    assert repository.deleted_hike_id == "hike-1"
    assert storage.deleted_paths.count("hikes/hike-1/photo.jpg") == 2


def test_hike_deletion_stops_when_route_metadata_cannot_be_verified() -> None:
    repository = DeletionRepository()
    storage = DeletionStorage()

    def fail_route_lookup(_hike_id: str, *, raise_errors: bool = False):
        assert raise_errors is True
        raise ConnectionError("route metadata unavailable")

    repository.get_hike_route_import = fail_route_lookup  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="Nothing was removed"):
        delete_hike_and_assets(repository, storage, "hike-1")

    assert storage.deleted_paths == []
    assert repository.deleted_hike_id is None


def test_mobile_hike_delete_is_owner_only_and_invalidates_species_cache(monkeypatch) -> None:
    class Repository:
        def list_hikes(self) -> list[dict[str, str]]:
            return [{"id": "hike-1", "owner_email": "owner@example.com"}]

    service = SimpleNamespace(repository=Repository(), storage=object())
    captured: list[str] = []
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(
        mobile_api,
        "_user_context",
        lambda: {
            "mode": "google",
            "email": "owner@example.com",
            "subject": None,
            "auth_configured": True,
        },
    )
    monkeypatch.setattr(
        mobile_api,
        "delete_hike_and_assets",
        lambda repository, storage, hike_id: captured.append(hike_id),
    )
    mobile_api._species_data_cache = (0.0, ([], {}, {}))

    assert mobile_api.delete_hike("hike-1") == {"deleted": True, "id": "hike-1"}
    assert captured == ["hike-1"]
    assert mobile_api._species_data_cache is None


def test_mobile_hike_delete_is_idempotent_without_disclosing_other_owners(monkeypatch) -> None:
    class Repository:
        def list_hikes(self) -> list[dict[str, str]]:
            return [{"id": "hike-1", "owner_email": "someone-else@example.com"}]

    service = SimpleNamespace(repository=Repository(), storage=object())
    monkeypatch.setattr(mobile_api, "get_services", lambda: service)
    monkeypatch.setattr(
        mobile_api,
        "_user_context",
        lambda: {
            "mode": "google",
            "email": "owner@example.com",
            "subject": None,
            "auth_configured": True,
        },
    )
    monkeypatch.setattr(
        mobile_api,
        "delete_hike_and_assets",
        lambda *_args: pytest.fail("another owner's hike must not be deleted"),
    )

    assert mobile_api.delete_hike("hike-1") == {"deleted": True, "id": "hike-1"}
    assert mobile_api.delete_hike("missing") == {"deleted": True, "id": "missing"}


def test_everyday_journal_cannot_be_deleted() -> None:
    with pytest.raises(HTTPException) as raised:
        mobile_api.delete_hike(mobile_api.EVERYDAY_JOURNAL_ID)

    assert raised.value.status_code == 409
