from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1] / "sql" / "entitlements_migration.sql"
).read_text(encoding="utf-8").lower()


def test_entitlement_migration_is_additive_and_uses_canonical_user_ids() -> None:
    assert "drop table" not in MIGRATION
    assert "create table if not exists public.app_entitlements" in MIGRATION
    assert "create table if not exists public.app_entitlement_events" in MIGRATION
    assert "user_id uuid not null references public.app_users(id) on delete cascade" in MIGRATION
    assert "add column if not exists owner_user_id uuid" in MIGRATION
    assert "foreign key (owner_user_id) references public.app_users(id) on delete set null" in MIGRATION
    assert "hike.owner_subject = identity.google_subject" in MIGRATION
    assert "photo.owner_subject = identity.google_subject" in MIGRATION
    assert "owner_email =" not in MIGRATION
    assert "group by google_subject" in MIGRATION
    assert "having count(*) = 1" in MIGRATION
    assert "create or replace function public.fill_owner_user_id_from_legacy_subject" in MIGRATION
    assert "new.owner_user_id is not null" in MIGRATION
    assert "account.google_subject = new.owner_subject" in MIGRATION
    assert "hikes_fill_owner_user_id" in MIGRATION
    assert "photos_fill_owner_user_id" in MIGRATION


def test_free_limits_and_plus_lifetime_features_are_server_configurable() -> None:
    assert "create table if not exists public.app_entitlement_policies" in MIGRATION
    assert "cloud_hikes_limit" in MIGRATION
    assert "cloud_media_limit" in MIGRATION
    assert "'free',\n        3,\n        50" in MIGRATION
    assert "'plus',\n        null,\n        10000" in MIGRATION
    assert "'lifetime',\n        null,\n        10000" in MIGRATION
    for feature in (
        "gps_recording",
        "basic_maps",
        "field_guide_basic",
        "field_briefing",
        "historical_weather",
        "hike_comparison",
        "offline_maps",
        "place_profiles",
    ):
        assert f'"{feature}"' in MIGRATION
    assert "on conflict (plan) do nothing" in MIGRATION


def test_entitlement_states_sources_and_store_keys_are_constrained() -> None:
    for plan in ("free", "plus", "lifetime"):
        assert f"'{plan}'" in MIGRATION
    for source in (
        "free",
        "apple_subscription",
        "google_play_subscription",
        "google_play_legacy",
        "admin",
    ):
        assert f"'{source}'" in MIGRATION
    for status in ("active", "grace", "canceled", "expired", "revoked", "refunded"):
        assert f"'{status}'" in MIGRATION
    assert "unique (source, external_entitlement_id)" in MIGRATION
    assert "unique (source, original_transaction_id)" in MIGRATION
    assert "unique (source, purchase_token_hash)" in MIGRATION
    assert "source <> 'apple_subscription'" in MIGRATION


def test_google_legacy_lifetime_requires_hashed_verified_evidence() -> None:
    assert "source <> 'google_play_legacy'" in MIGRATION
    assert "plan = 'lifetime'" in MIGRATION
    assert "billing_period = 'lifetime'" in MIGRATION
    assert "purchase_token_hash is not null" in MIGRATION
    assert "purchase_token_hash ~ '^[0-9a-f]{64}$'" in MIGRATION
    assert "raw token or client ownership boolean" in MIGRATION
    assert "is_legacy_owner" not in MIGRATION


def test_provider_projection_is_atomic_idempotent_and_rejects_relinking() -> None:
    assert "create or replace function public.apply_app_entitlement_event" in MIGRATION
    assert "p_projection jsonb" in MIGRATION
    assert "app_entitlement_events_idempotency_key" in MIGRATION
    assert "event_fingerprint <> projection_fingerprint" in MIGRATION
    assert "event id was reused for different verified data" in MIGRATION
    assert "pg_advisory_xact_lock" in MIGRATION
    assert "already linked to another hikejournal account" in MIGRATION
    assert "projection_occurred_at > entitlement.last_event_at" in MIGRATION
    assert "'stale', not should_apply" in MIGRATION


def test_quota_reservations_serialize_concurrent_requests_and_are_idempotent() -> None:
    assert "create table if not exists public.app_quota_reservations" in MIGRATION
    assert "unique (user_id, resource_type, request_id)" in MIGRATION
    assert "app_quota_reservations_active_resource_idx" in MIGRATION
    assert "where state in ('reserved', 'committed')" in MIGRATION
    assert "create or replace function public.reserve_app_quota" in MIGRATION
    assert "hashtextextended(p_user_id::text || ':' || p_resource_type, 0)" in MIGRATION
    assert "quota request id was already used for a different resource" in MIGRATION
    assert "'idempotent', true" in MIGRATION
    assert "actual_usage + reserved_usage >= quota_limit" in MIGRATION
    assert "'reason', 'quota_exceeded'" in MIGRATION
    assert "greatest(60, least(coalesce(p_ttl_seconds, 900), 3600))" in MIGRATION


def test_usage_counts_actual_rows_and_deletion_frees_quota() -> None:
    assert "create or replace function public.app_quota_usage" in MIGRATION
    assert "from public.hikes as hike" in MIGRATION
    assert "where hike.owner_user_id = p_user_id" in MIGRATION
    assert "from public.photos as photo" in MIGRATION
    assert "where photo.owner_user_id = p_user_id" in MIGRATION
    assert "create or replace function public.sync_app_quota_reservation" in MIGRATION
    assert "if tg_op = 'delete'" in MIGRATION
    assert "set state = 'released'" in MIGRATION
    assert "hikes_sync_app_quota_reservation" in MIGRATION
    assert "photos_sync_app_quota_reservation" in MIGRATION


def test_entitlement_tables_and_rpcs_are_service_role_only() -> None:
    for table in (
        "app_entitlement_policies",
        "app_entitlements",
        "app_entitlement_events",
        "app_quota_reservations",
    ):
        assert f"alter table public.{table} force row level security" in MIGRATION
        assert f"revoke all privileges on table public.{table} from anon, authenticated" in MIGRATION
    for function in (
        "effective_app_entitlement_plan(uuid, timestamptz)",
        "app_quota_usage(uuid, text)",
        "reserve_app_quota(uuid, text, text, uuid, integer)",
        "release_app_quota_reservation(uuid, text, text)",
        "apply_app_entitlement_event(jsonb)",
    ):
        assert f"revoke execute on function public.{function}" in MIGRATION
        assert f"grant execute on function public.{function}" in MIGRATION


def test_android_paid_model_is_explicitly_staged_without_fake_entitlement() -> None:
    assert "existing android endpoints are intentionally not gated" in MIGRATION
    assert "paid-download experience remains in an observe-only migration" in MIGRATION
    assert "android_lifetime" not in MIGRATION
