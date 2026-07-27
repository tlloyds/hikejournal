from pathlib import Path


def test_discovery_migration_adds_legacy_columns_before_backfill() -> None:
    migration = Path("sql/species_discovery_migration.sql").read_text(encoding="utf-8").lower()

    rank_column = migration.index("add column if not exists rank text")
    iconic_column = migration.index("add column if not exists iconic_taxon_name text")
    backfill = migration.index("update public.species_observations")

    assert rank_column < backfill
    assert iconic_column < backfill
    assert "coalesce(trim(rank), '') = ''" in migration
    assert "scientific_name" in migration[backfill:]


def test_discovery_migration_defines_touch_function_before_trigger() -> None:
    migration = Path("sql/species_discovery_migration.sql").read_text(encoding="utf-8").lower()

    assert migration.index("create or replace function public.touch_updated_at") < migration.index(
        "create trigger species_quests_touch_updated_at"
    )
