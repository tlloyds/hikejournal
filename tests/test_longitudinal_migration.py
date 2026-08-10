from pathlib import Path


MIGRATION = Path("sql/longitudinal_intelligence_migration.sql").read_text(encoding="utf-8").lower()


def test_longitudinal_migration_is_additive_and_backfills_identification_history():
    assert "drop table" not in MIGRATION
    assert "create table if not exists public.identification_events" in MIGRATION
    assert "create table if not exists public.observation_annotations" in MIGRATION
    assert "create table if not exists public.field_marks" in MIGRATION
    assert "insert into public.identification_events" in MIGRATION
    assert "where observation.status = 'confirmed'" in MIGRATION
    assert "not exists" in MIGRATION


def test_longitudinal_mutations_are_owner_ready_and_service_only():
    for table in (
        "identification_events",
        "observation_annotations",
        "field_marks",
        "hike_weather_snapshots",
    ):
        assert f"alter table public.{table} force row level security" in MIGRATION
        assert f"revoke all privileges on table public.{table} from anon, authenticated" in MIGRATION
        assert f"grant all privileges on table public.{table} to service_role" in MIGRATION
    assert "security definer" in MIGRATION
    assert "set_observation_natural_history" in MIGRATION


def test_field_marks_and_weather_have_idempotent_storage_keys():
    assert "id uuid primary key" in MIGRATION
    assert "unique (hike_id, provider, algorithm_version)" in MIGRATION
    assert "recording_session_id uuid" in MIGRATION
