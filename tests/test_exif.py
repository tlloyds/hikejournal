from hike_journal.services.exif import _dms_to_decimal, extract_metadata


def test_dms_to_decimal_for_north_west() -> None:
    lat = _dms_to_decimal(((28, 1), (30, 1), (0, 1)), "N")
    lng = _dms_to_decimal(((81, 1), (15, 1), (0, 1)), "W")

    assert lat == 28.5
    assert lng == -81.25


def test_dms_to_decimal_returns_none_for_malformed_gps() -> None:
    assert _dms_to_decimal(((28, 1), (30, 0), (0, 1)), "N") is None


def test_extract_metadata_returns_empty_metadata_for_unreadable_image() -> None:
    metadata = extract_metadata(b"not an image")

    assert metadata.lat is None
    assert metadata.lng is None
    assert metadata.taken_at is None
    assert metadata.exif_json["gps_latitude"] is None
