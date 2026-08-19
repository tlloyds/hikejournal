from pathlib import Path


MIGRATION = Path("sql/nationwide_hike_locations_migration.sql").read_text(encoding="utf-8").lower()


def test_nationwide_location_migration_adds_state_metadata_and_search_index():
    assert "add column if not exists state text" in MIGRATION
    assert "add column if not exists region text" in MIGRATION
    assert "add column if not exists county text" in MIGRATION
    assert "add column if not exists manager_name text" in MIGRATION
    assert "add column if not exists manager_type text" in MIGRATION
    assert "hike_locations_state_lower_name_idx" in MIGRATION
