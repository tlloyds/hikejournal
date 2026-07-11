from __future__ import annotations

from pathlib import Path

import streamlit as st


THEME_PATH = Path(__file__).with_name("theme.css")


def apply_theme() -> None:
    css = THEME_PATH.read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")
