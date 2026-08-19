from __future__ import annotations

from hike_journal import queries


def test_cached_photo_rows_receive_a_fresh_delivery_url_after_each_read(monkeypatch) -> None:
    raw_row = {
        "id": "photo-1",
        "storage_path": "hikes/hike-1/photo-1.jpg",
        "public_url": "https://legacy.example/photo-1.jpg",
    }
    issued = []

    class Repository:
        def decorate_media_rows(self, rows):
            token = len(issued) + 1
            issued.append(token)
            return [
                {
                    **row,
                    "public_url": f"https://signed.example/{row['storage_path']}?token={token}",
                }
                for row in rows
            ]

    monkeypatch.setattr(queries, "_repository", lambda: Repository())
    monkeypatch.setattr(
        queries,
        "_fetch_photo_records_for_ids_raw",
        lambda _photo_ids: [raw_row],
    )

    first = queries.fetch_photo_records_for_ids(("photo-1",))
    second = queries.fetch_photo_records_for_ids(("photo-1",))

    assert first[0]["public_url"].endswith("token=1")
    assert second[0]["public_url"].endswith("token=2")
    assert raw_row["public_url"] == "https://legacy.example/photo-1.jpg"


def test_cached_hike_covers_receive_a_fresh_delivery_url_after_each_read(monkeypatch) -> None:
    raw_hike = {
        "id": "hike-1",
        "storage_path": "hikes/hike-1/cover.jpg",
        "public_url": "https://legacy.example/cover.jpg",
    }
    issued = []

    class Repository:
        def decorate_media_rows(self, rows):
            token = len(issued) + 1
            issued.append(token)
            return [
                {
                    **row,
                    "public_url": f"https://signed.example/{row['storage_path']}?token={token}",
                }
                for row in rows
            ]

    monkeypatch.setattr(queries, "_repository", lambda: Repository())
    monkeypatch.setattr(queries, "_fetch_hikes_raw", lambda: [raw_hike])

    first = queries.fetch_hikes()
    second = queries.fetch_hikes()

    assert first[0]["public_url"].endswith("token=1")
    assert second[0]["public_url"].endswith("token=2")
    assert raw_hike["public_url"] == "https://legacy.example/cover.jpg"


def test_cached_route_import_is_resolved_after_cache_read(monkeypatch) -> None:
    raw_row = {
        "hike_id": "hike-1",
        "source_storage_path": "hikes/hike-1/imports/route.tcx",
        "source_public_url": "https://legacy.example/route.tcx",
    }

    class Repository:
        def decorate_media_row(self, row):
            return {
                **row,
                "source_public_url": "https://signed.example/route.tcx?token=fresh",
            }

    monkeypatch.setattr(queries, "_repository", lambda: Repository())
    monkeypatch.setattr(queries, "_fetch_hike_route_import_raw", lambda _hike_id: raw_row)

    resolved = queries.fetch_hike_route_import("hike-1")

    assert resolved is not None
    assert resolved["source_public_url"].endswith("token=fresh")
    assert raw_row["source_public_url"] == "https://legacy.example/route.tcx"
