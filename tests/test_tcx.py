from types import SimpleNamespace

import pytest

from hike_journal.domain.routes import sync_hike_route_import
from hike_journal.services.tcx import combine_tcx_route_imports, parse_tcx_bytes


SAMPLE_TCX = b"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities>
    <Activity Sport="Running">
      <Id>2026-05-18T13:18:24+00:00</Id>
      <Lap StartTime="2026-05-18T13:18:24+00:00">
        <TotalTimeSeconds>22598.0</TotalTimeSeconds>
        <DistanceMeters>24857.122752</DistanceMeters>
        <Track>
          <Trackpoint>
            <Time>2026-05-18T13:18:28+00:00</Time>
            <Position>
              <LatitudeDegrees>28.5919045</LatitudeDegrees>
              <LongitudeDegrees>-81.0425506</LongitudeDegrees>
            </Position>
            <AltitudeMeters>10.0</AltitudeMeters>
          </Trackpoint>
          <Trackpoint>
            <Time>2026-05-18T13:20:28+00:00</Time>
            <Position>
              <LatitudeDegrees>28.5921045</LatitudeDegrees>
              <LongitudeDegrees>-81.0421506</LongitudeDegrees>
            </Position>
            <AltitudeMeters>20.0</AltitudeMeters>
          </Trackpoint>
          <Trackpoint>
            <Time>2026-05-18T19:35:01+00:00</Time>
            <Position>
              <LatitudeDegrees>28.5918804</LatitudeDegrees>
              <LongitudeDegrees>-81.0426768</LongitudeDegrees>
            </Position>
            <AltitudeMeters>16.0</AltitudeMeters>
          </Trackpoint>
        </Track>
      </Lap>
    </Activity>
  </Activities>
</TrainingCenterDatabase>
"""


SEGMENTED_TCX = b"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities>
    <Activity Sport="Other">
      <Id>2026-07-31T13:00:00+00:00</Id>
      <Lap StartTime="2026-07-31T13:00:00+00:00">
        <TotalTimeSeconds>3600.0</TotalTimeSeconds>
        <DistanceMeters>1609.344</DistanceMeters>
        <Track>
          <Trackpoint>
            <Position>
              <LatitudeDegrees>28.0</LatitudeDegrees>
              <LongitudeDegrees>-82.0</LongitudeDegrees>
            </Position>
            <AltitudeMeters>10.0</AltitudeMeters>
          </Trackpoint>
          <Trackpoint>
            <Position>
              <LatitudeDegrees>28.001</LatitudeDegrees>
              <LongitudeDegrees>-82.001</LongitudeDegrees>
            </Position>
            <AltitudeMeters>20.0</AltitudeMeters>
          </Trackpoint>
        </Track>
        <Track>
          <Trackpoint>
            <Position>
              <LatitudeDegrees>40.0</LatitudeDegrees>
              <LongitudeDegrees>-120.0</LongitudeDegrees>
            </Position>
            <AltitudeMeters>1000.0</AltitudeMeters>
          </Trackpoint>
          <Trackpoint>
            <Position>
              <LatitudeDegrees>40.001</LatitudeDegrees>
              <LongitudeDegrees>-120.001</LongitudeDegrees>
            </Position>
            <AltitudeMeters>990.0</AltitudeMeters>
          </Trackpoint>
        </Track>
      </Lap>
    </Activity>
  </Activities>
</TrainingCenterDatabase>
"""


def test_parse_tcx_extracts_route_summary() -> None:
    parsed = parse_tcx_bytes(SAMPLE_TCX)

    assert parsed.visited_on is not None
    assert parsed.visited_on.isoformat() == "2026-05-18"
    assert parsed.duration_seconds == 22598
    assert round(parsed.distance_miles or 0, 3) == 15.445
    assert parsed.track_point_count == 3
    assert parsed.elevation_gain_feet == 33
    assert parsed.elevation_loss_feet == 13
    assert parsed.start_latitude == 28.5919045
    assert parsed.end_longitude == -81.0426768
    assert parsed.track_geojson["type"] == "LineString"
    assert len(parsed.track_geojson["coordinates"]) == 3
    assert parsed.track_geojson["meta"]["elevation_gain_feet"] == 33


def test_parse_tcx_preserves_tracks_without_bridging_paused_gap() -> None:
    parsed = parse_tcx_bytes(SEGMENTED_TCX)

    assert parsed.track_point_count == 4
    assert parsed.distance_miles == pytest.approx(1.0)
    assert parsed.elevation_gain_feet == 33
    assert parsed.elevation_loss_feet == 33
    assert parsed.start_latitude == 28.0
    assert parsed.end_longitude == -120.001
    assert parsed.track_geojson == {
        "type": "MultiLineString",
        "coordinates": [
            [[-82.0, 28.0, 10.0], [-82.001, 28.001, 20.0]],
            [[-120.0, 40.0, 1000.0], [-120.001, 40.001, 990.0]],
        ],
        "meta": {
            "segment_count": 2,
            "elevation_gain_feet": 33,
            "elevation_loss_feet": 33,
        },
    }


def test_combine_tcx_route_imports_keeps_separate_segments() -> None:
    first = parse_tcx_bytes(SAMPLE_TCX)
    second = parse_tcx_bytes(
        SAMPLE_TCX
        .replace(b"2026-05-18T13:18:24+00:00", b"2026-05-18T21:18:24+00:00")
        .replace(b"22598.0", b"3600.0")
        .replace(b"24857.122752", b"1609.344")
        .replace(b"28.591", b"28.700")
    )

    combined = combine_tcx_route_imports([second, first])

    assert combined is not None
    assert combined.visited_on is not None
    assert combined.visited_on.isoformat() == "2026-05-18"
    assert round(combined.distance_miles or 0, 3) == 16.445
    assert combined.duration_seconds == 26198
    assert combined.track_point_count == 6
    assert combined.track_geojson["type"] == "MultiLineString"
    assert combined.track_geojson["meta"]["segment_count"] == 2
    assert len(combined.track_geojson["coordinates"]) == 2
    assert all(len(segment) == 3 for segment in combined.track_geojson["coordinates"])


@pytest.mark.parametrize(
    ("upload_count", "source_type", "expected_source_type"),
    [
        (1, None, "mapmyrun_tcx"),
        (2, None, "mapmyrun_tcx_collection"),
        (1, "hikejournal_android_gps", "hikejournal_android_gps"),
    ],
)
def test_route_sync_sets_legacy_and_native_source_types(
    upload_count: int,
    source_type: str | None,
    expected_source_type: str,
) -> None:
    class Repository:
        payload = None

        def upsert_hike_route_import(self, hike_id, payload):
            self.payload = {"hike_id": hike_id, **payload}
            return self.payload

    class Storage:
        def upload_hike_route_import(self, hike_id, contents):
            assert hike_id == "hike-1"
            assert contents
            return "routes/hike-1.tcx", "https://files.example/hike-1.tcx"

        def delete_file(self, _path):
            raise AssertionError("A successful new upload should not be deleted.")

    repository = Repository()
    uploads = [
        SimpleNamespace(name=f"route-{index}.tcx", getvalue=lambda: SAMPLE_TCX)
        for index in range(upload_count)
    ]
    uploaded_file = uploads[0] if upload_count == 1 else uploads

    saved, error = sync_hike_route_import(
        repository=repository,
        storage=Storage(),
        hike_id="hike-1",
        uploaded_file=uploaded_file,
        existing_route_import=None,
        remove_existing=False,
        source_type=source_type,
    )

    assert error is None
    assert saved is not None
    assert saved["source_type"] == expected_source_type
    assert repository.payload["source_type"] == expected_source_type


def test_route_sync_rejects_unknown_source_type_before_upload() -> None:
    class Storage:
        def upload_hike_route_import(self, *_args):
            raise AssertionError("An invalid source must be rejected before upload.")

    saved, error = sync_hike_route_import(
        repository=object(),
        storage=Storage(),
        hike_id="hike-1",
        uploaded_file=SimpleNamespace(name="route.tcx", getvalue=lambda: SAMPLE_TCX),
        existing_route_import={"id": "existing"},
        remove_existing=False,
        source_type="unknown_recorder",
    )

    assert saved == {"id": "existing"}
    assert error == "Route source type is not supported."
