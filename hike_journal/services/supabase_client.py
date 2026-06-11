from __future__ import annotations

import streamlit as st
from supabase import Client, create_client
from supabase.client import ClientOptions

from hike_journal.config import settings


@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    if not settings.supabase_configured:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required.")
    return create_client(
        settings.supabase_url,
        settings.supabase_key,
        options=ClientOptions(schema="public", postgrest_client_timeout=15, storage_client_timeout=30),
    )
