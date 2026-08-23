from __future__ import annotations

import streamlit as st
from supabase import Client

from hike_journal.config import settings
from hike_journal.services.supabase_transport import build_supabase_client


@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    if not settings.supabase_configured:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required.")
    return build_supabase_client(settings.supabase_url, settings.supabase_key)
