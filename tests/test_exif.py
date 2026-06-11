from hike_journal.services.exif import _dms_to_decimal


def test_dms_to_decimal_for_north_west() -> None:
    lat = _dms_to_decimal(((28, 1), (30, 1), (0, 1)), "N")
    lng = _dms_to_decimal(((81, 1), (15, 1), (0, 1)), "W")

    assert lat == 28.5
    assert lng == -81.25
