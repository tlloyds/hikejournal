from __future__ import annotations

import httpx
from supabase import Client, create_client
from supabase.client import ClientOptions


def build_supabase_client(url: str, key: str) -> Client:
    """Create a Supabase client with a resilient Cloud Run transport.

    supabase-py enables HTTP/2 for PostgREST by default. Supabase's gateway
    can terminate an idle HTTP/2 connection, which leaves the pooled client
    raising ``ConnectionTerminated`` on the next request. A shared HTTP/1.1
    client keeps connection reuse while avoiding that stale HTTP/2 state.
    """
    http_client = httpx.Client(
        http2=False,
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, connect=10.0),
    )
    return create_client(
        url,
        key,
        options=ClientOptions(
            schema="public",
            postgrest_client_timeout=15,
            storage_client_timeout=30,
            httpx_client=http_client,
        ),
    )
