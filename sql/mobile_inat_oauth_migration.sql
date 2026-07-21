-- Durable, encrypted iNaturalist tokens for the stateless Android companion.
-- The encryption key is supplied only by the trusted mobile API at runtime.
create extension if not exists pgcrypto;

create table if not exists public.mobile_inat_credentials (
    owner_email text primary key,
    encrypted_access_token bytea not null,
    updated_at timestamptz not null default timezone('utc', now())
);

alter table public.mobile_inat_credentials enable row level security;

create or replace function public.save_mobile_inat_token(
    p_owner_email text,
    p_access_token text,
    p_encryption_key text
) returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into mobile_inat_credentials (owner_email, encrypted_access_token, updated_at)
    values (lower(trim(p_owner_email)), pgp_sym_encrypt(p_access_token, p_encryption_key), timezone('utc', now()))
    on conflict (owner_email) do update set
        encrypted_access_token = excluded.encrypted_access_token,
        updated_at = excluded.updated_at;
end;
$$;

create or replace function public.load_mobile_inat_token(
    p_owner_email text,
    p_encryption_key text
) returns text
language sql
security definer
set search_path = public
as $$
    select pgp_sym_decrypt(encrypted_access_token, p_encryption_key)
    from mobile_inat_credentials
    where owner_email = lower(trim(p_owner_email))
    limit 1;
$$;

revoke all on table public.mobile_inat_credentials from anon, authenticated;
revoke all on function public.save_mobile_inat_token(text, text, text) from public;
revoke all on function public.load_mobile_inat_token(text, text) from public;
grant execute on function public.save_mobile_inat_token(text, text, text) to service_role;
grant execute on function public.load_mobile_inat_token(text, text) to service_role;
