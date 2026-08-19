from collections import Counter
import json
import math
from pathlib import Path


SEED = json.loads(Path("data/hike_locations_seed.json").read_text(encoding="utf-8"))
COVERAGE = json.loads(Path("data/hike_location_coverage.json").read_text(encoding="utf-8"))
STATE_CODES = set(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS "
    "MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
GENERATED_SOURCES = {"usgs_national_digital_trails", "usgs_pad_us"}


def test_seed_has_a_robust_pack_for_all_50_states():
    counts = Counter(str(item.get("state") or "") for item in SEED)

    assert set(counts) == STATE_CODES
    assert min(counts.values()) >= 90
    assert COVERAGE["state_count"] == 50
    assert COVERAGE["minimum_state_locations"] == min(counts.values())
    assert COVERAGE["total_locations"] == len(SEED)
    assert all(
        state["non_federal_public_lands"] >= 1
        for state in COVERAGE["states"].values()
    )


def test_seed_records_have_unique_slugs_valid_coordinates_and_provenance():
    slugs = [str(item.get("slug") or "") for item in SEED]
    assert all(slugs)
    assert len(slugs) == len(set(slugs))

    generated = [item for item in SEED if item.get("source") in GENERATED_SOURCES]
    assert generated
    for item in generated:
        latitude = float(item["lat"])
        longitude = float(item["lng"])
        assert math.isfinite(latitude) and -90 <= latitude <= 90
        assert math.isfinite(longitude) and -180 <= longitude <= 180
        assert item["state"] in STATE_CODES
        assert str(item.get("source_slug") or "").strip()
        assert str(item.get("source_url") or "").startswith("https://")


def test_historical_florida_layer_is_retained_until_license_decision():
    historical = [
        item
        for item in SEED
        if str(item.get("source") or "").startswith("cfl_hike_planner_")
    ]

    assert len(historical) == 446
    assert {item.get("state") for item in historical} == {"FL"}
