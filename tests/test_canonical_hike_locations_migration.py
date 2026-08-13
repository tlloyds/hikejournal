from pathlib import Path


MIGRATION = Path("sql/canonical_hike_locations_migration.sql").read_text(encoding="utf-8").lower()


def test_location_migration_merges_tags_before_deleting_duplicate_places():
    insert_position = MIGRATION.index("insert into public.hike_location_tags")
    update_quest_position = MIGRATION.index("update public.species_quests")
    delete_tag_position = MIGRATION.index("delete from public.hike_location_tags")
    delete_location_position = MIGRATION.index("delete from public.hike_locations")

    assert insert_position < update_quest_position < delete_tag_position < delete_location_position
    assert "on conflict (hike_id, location_id) do update" in MIGRATION
    assert "bool_or(tags.is_primary)" in MIGRATION


def test_location_migration_is_transactional_and_keeps_historical_aliases():
    assert MIGRATION.startswith("begin;")
    assert MIGRATION.rstrip().endswith("commit;")
    assert "econ-river-wilderness-area" in MIGRATION
    assert "pine lilly preserve" in MIGRATION
    assert "tosohatchee wma" in MIGRATION
