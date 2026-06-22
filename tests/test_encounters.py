from datetime import UTC, datetime, timedelta

from hike_journal.services.encounters import build_publish_encounter_plan


BASE_TIME = datetime(2026, 6, 21, 14, 0, tzinfo=UTC)


def publish_row(
    suffix: str,
    *,
    taxon_id: int = 100,
    hike_id: str | None = "hike-1",
    minutes: int = 0,
    lat: float | None = 28.6000,
    lng: float | None = -81.1000,
) -> dict:
    return {
        "observation": {
            "id": f"observation-{suffix}",
            "photo_id": f"photo-{suffix}",
            "hike_id": hike_id,
            "taxon_id": taxon_id,
            "common_name": "Test species",
            "scientific_name": "Species testus",
        },
        "photo": {
            "id": f"photo-{suffix}",
            "hike_id": hike_id,
            "taken_at": (BASE_TIME + timedelta(minutes=minutes)).isoformat(),
            "lat": lat,
            "lng": lng,
        },
        "hike": {"id": hike_id, "title": "Test outing"},
        "publish_state": "Ready to post",
    }


def test_groups_same_species_same_encounter() -> None:
    rows = [
        publish_row("a"),
        publish_row("b", minutes=8, lat=28.6002),
    ]

    groups = build_publish_encounter_plan(rows)

    assert len(groups) == 1
    assert groups[0]["photo_count"] == 2
    assert groups[0]["lead_row"]["photo"]["id"] == "photo-a"
    assert groups[0]["time_span_minutes"] == 8
    assert groups[0]["max_distance_meters"] < 50


def test_does_not_group_different_species_or_outings() -> None:
    rows = [
        publish_row("a"),
        publish_row("b", taxon_id=200),
        publish_row("c", hike_id="hike-2"),
    ]

    groups = build_publish_encounter_plan(rows)

    assert len(groups) == 3
    assert all(group["photo_count"] == 1 for group in groups)


def test_does_not_group_beyond_time_or_distance_thresholds() -> None:
    rows = [
        publish_row("a"),
        publish_row("late", minutes=16),
        publish_row("far", minutes=2, lat=28.6010),
    ]

    groups = build_publish_encounter_plan(rows)

    assert len(groups) == 3


def test_missing_gps_or_time_stays_separate() -> None:
    missing_time = publish_row("time")
    missing_time["photo"]["taken_at"] = None
    rows = [
        publish_row("a"),
        publish_row("gps", minutes=1, lat=None, lng=None),
        missing_time,
    ]

    groups = build_publish_encounter_plan(rows)

    assert len(groups) == 3


def test_group_uses_complete_link_distance() -> None:
    rows = [
        publish_row("a", lat=28.6000),
        publish_row("b", minutes=2, lat=28.6003),
        publish_row("c", minutes=4, lat=28.6006),
    ]

    groups = build_publish_encounter_plan(rows)

    assert sorted(group["photo_count"] for group in groups) == [1, 2]


def test_group_over_eight_photos_is_flagged() -> None:
    rows = [
        publish_row(str(index), minutes=index, lat=28.6000 + index * 0.00001)
        for index in range(9)
    ]

    groups = build_publish_encounter_plan(rows, max_photos=8)

    assert len(groups) == 1
    assert groups[0]["photo_count"] == 9
    assert groups[0]["oversized"] is True


def test_name_fallback_groups_records_without_taxon_ids() -> None:
    rows = [publish_row("a", taxon_id=None), publish_row("b", taxon_id=None, minutes=1)]

    groups = build_publish_encounter_plan(rows)

    assert len(groups) == 1
    assert groups[0]["photo_count"] == 2
