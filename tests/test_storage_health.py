from __future__ import annotations

from types import SimpleNamespace

import pytest

from hike_journal.services.storage import StorageService


def _service(**values):
    service = StorageService.__new__(StorageService)
    service.backend = values.get("backend", "supabase")
    service.client = values.get("client")
    service.supabase_bucket = values.get("supabase_bucket", "journal")
    service.r2_bucket = values.get("r2_bucket", "journal-r2")
    service._r2_client = values.get("r2_client")
    return service


def test_supabase_storage_health_checks_the_configured_bucket() -> None:
    checked = []
    client = SimpleNamespace(
        storage=SimpleNamespace(get_bucket=lambda bucket: checked.append(bucket))
    )

    _service(client=client).check_health()

    assert checked == ["journal"]


def test_r2_storage_health_uses_a_read_only_bucket_head() -> None:
    checked = []
    r2_client = SimpleNamespace(
        head_bucket=lambda **kwargs: checked.append(kwargs["Bucket"])
    )

    _service(backend="r2", r2_client=r2_client).check_health()

    assert checked == ["journal-r2"]


def test_storage_health_rejects_an_unconfigured_client() -> None:
    with pytest.raises(RuntimeError, match="Supabase client"):
        _service().check_health()


def test_r2_download_url_is_short_lived_and_bucket_scoped() -> None:
    calls = []

    class R2Client:
        def generate_presigned_url(self, operation, **kwargs):
            calls.append((operation, kwargs))
            return "https://signed.example/photo.jpg?X-Amz-Signature=test"

    url = _service(backend="r2", r2_client=R2Client()).create_download_url(
        "/hikes/hike-1/photo.jpg",
        expires_in=900,
    )

    assert url.startswith("https://signed.example/")
    assert calls == [
        (
            "get_object",
            {
                "Params": {"Bucket": "journal-r2", "Key": "hikes/hike-1/photo.jpg"},
                "ExpiresIn": 900,
            },
        )
    ]


def test_supabase_download_url_uses_private_signed_url() -> None:
    calls = []

    class Bucket:
        def create_signed_url(self, path, expires_in):
            calls.append((path, expires_in))
            return {"signedURL": "https://supabase.example/signed/photo.jpg?token=test"}

    class Storage:
        def from_(self, bucket):
            assert bucket == "journal"
            return Bucket()

    client = SimpleNamespace(storage=Storage())
    url = _service(client=client).create_download_url("standalone/photo.jpg", expires_in=60)

    assert url == "https://supabase.example/signed/photo.jpg?token=test"
    assert calls == [("standalone/photo.jpg", 300)]


def test_download_url_cache_reuses_a_signed_url_for_the_same_object() -> None:
    calls = []

    class Bucket:
        def create_signed_url(self, path, expires_in):
            calls.append((path, expires_in))
            return {"signedURL": f"https://supabase.example/{len(calls)}"}

    class Storage:
        def from_(self, bucket):
            return Bucket()

    client = SimpleNamespace(storage=Storage())
    service = _service(client=client)

    first = service.create_download_url("hikes/hike-1/photo.jpg", expires_in=900)
    second = service.create_download_url("hikes/hike-1/photo.jpg", expires_in=900)

    assert first == second
    assert calls == [("hikes/hike-1/photo.jpg", 900)]


def test_thumbnail_path_is_kept_separate_from_the_original() -> None:
    assert StorageService.thumbnail_path("hikes/hike-1/photo.jpg") == (
        "hikes/hike-1/thumbs/photo.jpg"
    )
