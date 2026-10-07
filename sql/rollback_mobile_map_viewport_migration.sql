-- Roll back sql/mobile_map_viewport_migration.sql.
-- The migration only adds these owner-scoped RPCs; it does not alter user data.

begin;

drop function if exists public.mobile_map_viewport(
    double precision, double precision, double precision, double precision,
    double precision, integer, text, text, text, text, boolean, boolean
);
drop function if exists public.mobile_map_summary(
    text, text, text, text, boolean, boolean
);

notify pgrst, 'reload schema';

commit;
