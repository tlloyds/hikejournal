-- Lock the database API to HikeJournal's trusted server.
--
-- The Streamlit and mobile API processes use a Supabase secret/service-role
-- key. Browser and mobile clients must never receive that key. The service
-- role bypasses RLS; anon and authenticated API roles receive no direct data
-- access.

begin;

do $$
declare
    table_name text;
    policy_record record;
    function_record record;
begin
    foreach table_name in array array[
        'hikes',
        'photos',
        'species_observations',
        'hike_collaborators',
        'hike_route_imports',
        'hike_locations',
        'hike_location_tags',
        'mobile_inat_credentials'
    ]
    loop
        if to_regclass(format('public.%I', table_name)) is null then
            continue;
        end if;

        execute format('alter table public.%I enable row level security', table_name);
        execute format('alter table public.%I force row level security', table_name);

        for policy_record in
            select policyname
            from pg_policies
            where schemaname = 'public'
              and tablename = table_name
        loop
            execute format(
                'drop policy if exists %I on public.%I',
                policy_record.policyname,
                table_name
            );
        end loop;

        execute format(
            'revoke all privileges on table public.%I from anon, authenticated',
            table_name
        );
        execute format(
            'grant all privileges on table public.%I to service_role',
            table_name
        );
    end loop;

    -- App RPCs are server-only too. Scoping this to HikeJournal functions
    -- avoids trying to change Supabase-managed PostGIS functions.
    for function_record in
        select p.oid::regprocedure as signature
        from pg_proc p
        join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public'
          and p.proname = any(array[
              'touch_updated_at',
              'sync_photo_geom',
              'sync_hike_route_geom',
              'map_summary',
              'map_viewport',
              'map_routes_viewport',
              'map_photo_detail',
              'save_mobile_inat_token',
              'load_mobile_inat_token'
          ])
    loop
        execute format(
            'revoke execute on function %s from public, anon, authenticated',
            function_record.signature
        );
        execute format(
            'grant execute on function %s to service_role',
            function_record.signature
        );
    end loop;
end
$$;

-- Prevent later tables/functions created by the migration owner from becoming
-- API-accessible through PostgreSQL's permissive default function grants.
alter default privileges in schema public
revoke all privileges on tables from anon, authenticated;
alter default privileges in schema public
revoke execute on functions from public, anon, authenticated;
alter default privileges in schema public
grant all privileges on tables to service_role;
alter default privileges in schema public
grant execute on functions to service_role;

-- Photos intentionally remain publicly readable because the app stores and
-- renders public URLs. Only the trusted server may mutate bucket objects.
drop policy if exists "App key can insert hike journal objects" on storage.objects;
drop policy if exists "App key can update hike journal objects" on storage.objects;
drop policy if exists "App key can delete hike journal objects" on storage.objects;

commit;

-- Supabase's Security Advisor may separately flag public.spatial_ref_sys.
-- Do not add it above: PostGIS creates that system lookup table under the
-- managed supabase_admin role, so project migrations cannot alter it. It holds
-- public coordinate-reference definitions, not HikeJournal data. Supabase is
-- tracking the warning as a linter false positive for managed PostGIS tables.
