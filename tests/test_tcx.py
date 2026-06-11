from hike_journal.services.tcx import parse_tcx_bytes


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
