-- Shared, provider-neutral cache for short-lived planning conditions. Payloads
-- contain only public forecast/gauge data and are deliberately not user-owned.
create table if not exists public.outdoor_condition_snapshots (
    cache_key text primary key,
    kind text not null check (kind in ('forecast', 'nearby_usgs', 'usgs_series')),
    algorithm_version text not null,
    payload jsonb not null,
    collected_at timestamptz not null,
    expires_at timestamptz not null,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists outdoor_condition_snapshots_expires_at_idx
on public.outdoor_condition_snapshots (expires_at);

create or replace function public.touch_outdoor_condition_snapshot()
returns trigger as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$ language plpgsql;

drop trigger if exists outdoor_condition_snapshots_touch_updated_at
on public.outdoor_condition_snapshots;
create trigger outdoor_condition_snapshots_touch_updated_at
before update on public.outdoor_condition_snapshots
for each row execute procedure public.touch_outdoor_condition_snapshot();

alter table public.outdoor_condition_snapshots enable row level security;
alter table public.outdoor_condition_snapshots force row level security;
revoke all privileges on table public.outdoor_condition_snapshots from anon, authenticated;
grant all privileges on table public.outdoor_condition_snapshots to service_role;
revoke execute on function public.touch_outdoor_condition_snapshot()
from public, anon, authenticated;
grant execute on function public.touch_outdoor_condition_snapshot() to service_role;
