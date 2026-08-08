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
