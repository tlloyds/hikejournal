from __future__ import annotations

import streamlit as st


THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Manrope:wght@400;500;600;700;800&display=swap');

:root {
  --shell: #F3EDE3;
  --paper: rgba(250, 246, 238, 0.9);
  --paper-strong: #F8F3EA;
  --palmetto: #244232;
  --palmetto-deep: #173225;
  --sawgrass: #5F6D63;
  --river-silt: #BD6B2F;
  --gold: #D9AA59;
  --spring-water: #E4DDD0;
  --charcoal: #17231B;
  --mist: rgba(255,255,255,0.52);
  --line: rgba(32, 44, 36, 0.12);
  --shadow: 0 30px 80px rgba(23, 35, 27, 0.12);
}

html, body, [class*="css"] {
  font-family: 'Manrope', sans-serif;
}

body, .stApp {
  background:
    linear-gradient(180deg, #f8f3ea 0%, #efe5d5 100%);
  color: var(--charcoal);
}

a {
  color: inherit;
  text-decoration: none;
}

.stApp > header {
  background: transparent;
}

[data-testid="stSidebar"] {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(17,35,25,0.99) 0%, rgba(24,48,37,0.99) 48%, rgba(22,42,33,1) 100%);
  border-right: 1px solid rgba(248,243,234,0.08);
  box-shadow: none;
}

[data-testid="stSidebar"] .block-container {
  padding-top: 1.5rem;
  padding-bottom: 10.5rem;
  position: relative;
  z-index: 2;
}

[data-testid="stSidebar"]::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 82% 16%, rgba(217,170,89,0.9) 0 8%, transparent 8.5%),
    radial-gradient(circle at 30% 20%, rgba(255,255,255,0.08) 0 0.4%, transparent 0.45%),
    radial-gradient(circle at 58% 24%, rgba(255,255,255,0.08) 0 0.45%, transparent 0.5%),
    radial-gradient(circle at 72% 31%, rgba(255,255,255,0.08) 0 0.45%, transparent 0.5%),
    radial-gradient(circle at 40% 34%, rgba(255,255,255,0.08) 0 0.45%, transparent 0.5%),
    linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0));
  pointer-events: none;
}

[data-testid="stSidebar"]::after {
  content: "";
  position: absolute;
  inset: auto 0 0 0;
  height: 172px;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 600 220' preserveAspectRatio='none'%3E%3Cpath fill='%23284537' d='M0 122 72 158 150 124 232 168 326 98 430 150 540 80 600 110V220H0Z'/%3E%3Cpath fill='%23203A2E' d='M0 150 84 132 158 168 250 118 356 162 470 108 600 156V220H0Z'/%3E%3Cpath fill='%23335244' d='M0 186 110 158 214 182 330 150 448 184 600 164V220H0Z'/%3E%3Cpath fill='%23577463' d='M0 204 110 180 214 190 330 174 448 198 600 184V220H0Z'/%3E%3Cg stroke='%23112119' stroke-width='10' stroke-linecap='round'%3E%3Cpath d='M52 176 86 206'/%3E%3Cpath d='M86 164 58 214'/%3E%3Cpath d='M474 170 506 202'/%3E%3Cpath d='M506 158 478 214'/%3E%3Cpath d='M554 176 584 206'/%3E%3Cpath d='M584 164 560 214'/%3E%3C/g%3E%3Cpath fill='%23D8994F' d='M126 220 170 178 214 220Z'/%3E%3Cpath fill='%23E7BB72' d='M148 220 170 178 192 220Z'/%3E%3Cpath fill='%23D8994F' d='M318 220 336 194 354 220Z'/%3E%3Ccircle cx='336' cy='207' r='8' fill='%23F0B04E'/%3E%3Ccircle cx='327' cy='214' r='4' fill='%23F6D8A4'/%3E%3Ccircle cx='345' cy='214' r='4' fill='%23F6D8A4'/%3E%3Cpath fill='%23D8994F' d='M430 220 470 182 510 220Z'/%3E%3Cpath fill='%23E4C17F' d='M450 220 470 182 490 220Z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-size: 100% 100%;
  background-position: bottom center;
  opacity: 0.82;
  pointer-events: none;
}

[data-testid="stSidebar"] [data-testid="stSidebarUserContent"],
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] label,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] p,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] h1,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] h2,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] h3,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] h4,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] h5,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] h6,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] span,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] small,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] a,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div:not([data-baseweb]) {
  color: #F8F3EA;
}

[data-testid="stSidebar"] a {
  color: inherit !important;
  text-decoration: none !important;
}

[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] .stTextArea textarea,
[data-testid="stSidebar"] .stDateInput input,
[data-testid="stSidebar"] .stNumberInput input {
  color: var(--charcoal) !important;
  -webkit-text-fill-color: var(--charcoal) !important;
  background: rgba(255, 252, 247, 0.96);
  border: 1px solid rgba(48, 71, 58, 0.14);
}

[data-testid="stSidebar"] .stTextInput input::placeholder,
[data-testid="stSidebar"] .stTextArea textarea::placeholder,
[data-testid="stSidebar"] .stDateInput input::placeholder,
[data-testid="stSidebar"] .stNumberInput input::placeholder {
  color: rgba(31, 42, 38, 0.48) !important;
  -webkit-text-fill-color: rgba(31, 42, 38, 0.48) !important;
}

[data-testid="stSidebar"] .stTextInput label,
[data-testid="stSidebar"] .stTextArea label,
[data-testid="stSidebar"] .stDateInput label,
[data-testid="stSidebar"] .stNumberInput label {
  color: #fff7ec !important;
}

[data-testid="stSidebar"] .stButton button,
[data-testid="stSidebar"] .stDownloadButton button,
[data-testid="stSidebar"] .stFormSubmitButton button {
  min-height: 2.8rem;
  border-radius: 10px;
  background: rgba(255,255,255,0.06);
  color: #F8F3EA;
  border: 1px solid rgba(248,243,234,0.14);
  box-shadow: none;
  font-weight: 700;
  letter-spacing: 0.015em;
  backdrop-filter: blur(8px);
}

[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stFormSubmitButton > button[kind="primary"] {
  min-height: 3rem;
  border-radius: 999px;
  background: linear-gradient(135deg, #C36E31, #E19A56) !important;
  color: white !important;
  border: 0 !important;
  text-shadow: none;
  box-shadow: 0 20px 42px rgba(189, 107, 47, 0.32) !important;
}

[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover,
[data-testid="stSidebar"] .stFormSubmitButton > button[kind="primary"]:hover {
  background: linear-gradient(135deg, #D57D3C, #E9A968) !important;
  color: white !important;
}

[data-testid="stSidebar"] .stButton button:hover,
[data-testid="stSidebar"] .stFormSubmitButton button:hover {
  border-color: rgba(248,243,234,0.24);
  background: rgba(255,255,255,0.12);
}

[data-testid="stSidebar"] [data-testid="stButton"]:last-of-type button {
  background: transparent;
  border-color: rgba(248,243,234,0.1);
  color: rgba(248,243,234,0.74);
  margin-top: 0.2rem;
}

[data-testid="stSidebar"] [data-testid="stButton"]:last-of-type button:hover {
  background: rgba(255,255,255,0.08);
  color: #F8F3EA;
}

[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(248,243,234,0.14);
  border-radius: 10px;
  min-height: 2.85rem;
  backdrop-filter: blur(8px);
}

[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] svg {
  color: #F8F3EA !important;
}

.sidebar-brand-shell {
  margin: 0.15rem 0 1.9rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid rgba(248,243,234,0.12);
}

.sidebar-brand-kicker {
  color: rgba(248,243,234,0.5);
  font-size: 0.64rem;
  font-weight: 800;
  letter-spacing: 0.28em;
  text-transform: uppercase;
}

.sidebar-brand-wordmark {
  margin-top: 0.5rem;
  color: #F8F3EA;
  font-family: 'Fraunces', serif;
  font-size: 2.25rem;
  line-height: 0.94;
  letter-spacing: -0.05em;
}

.sidebar-brand-meta {
  margin-top: 0.65rem;
  color: rgba(248,243,234,0.72);
  font-size: 0.84rem;
  line-height: 1.6;
}

.sidebar-section-label {
  margin: 1.05rem 0 0.55rem;
  color: rgba(248,243,234,0.38);
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.26em;
  text-transform: uppercase;
  opacity: 0.8;
}

.sidebar-nav-shell {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
  margin-top: 0.15rem;
  padding: 0.25rem 0 0.55rem;
}

.sidebar-nav-link {
  display: flex;
  align-items: center;
  min-height: 2.65rem;
  padding: 0.7rem 0.9rem;
  border-radius: 999px;
  color: rgba(248,243,234,0.8);
  font-size: 0.93rem;
  font-weight: 700;
  text-decoration: none;
  border: 1px solid transparent;
  transition: color 160ms ease, background 160ms ease, border-color 160ms ease, transform 160ms ease;
}

.sidebar-nav-link:hover {
  color: #F8F3EA;
  background: rgba(255,255,255,0.08);
  border-color: rgba(248,243,234,0.1);
  transform: translateX(2px);
}

.sidebar-nav-link.active {
  color: #F8F3EA;
  background: rgba(255,255,255,0.12);
  border-color: rgba(248,243,234,0.14);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
}

.sidebar-nav-link.disabled {
  color: rgba(248,243,234,0.34);
  cursor: default;
  background: transparent;
  border-color: transparent;
  transform: none;
}

.sidebar-control-label {
  margin: 0.55rem 0 0.5rem;
  color: rgba(248,243,234,0.72);
  font-size: 0.76rem;
  font-weight: 700;
}

.sidebar-current-hike {
  margin: 0.15rem 0 1.15rem;
  padding: 0.95rem 1rem 1rem;
  border-radius: 18px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(248,243,234,0.12);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
  backdrop-filter: blur(12px);
}

.sidebar-current-label {
  color: rgba(248,243,234,0.5);
  font-size: 0.64rem;
  font-weight: 800;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  opacity: 0.84;
}

.sidebar-current-title {
  margin-top: 0.48rem;
  color: #F8F3EA;
  font-family: 'Fraunces', serif;
  font-size: 1.05rem;
  line-height: 1.24;
}

.sidebar-current-meta {
  margin-top: 0.4rem;
  color: rgba(248,243,234,0.72);
  font-size: 0.82rem;
  line-height: 1.6;
}

.sidebar-current-actions {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
  margin-top: 0.8rem;
}

.sidebar-current-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.1rem;
  padding: 0.45rem 0.8rem;
  border-radius: 999px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(248,243,234,0.14);
  color: #F8F3EA;
  font-size: 0.82rem;
  font-weight: 800;
  letter-spacing: 0.01em;
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
}

.sidebar-current-action:hover {
  background: rgba(255,255,255,0.14);
  border-color: rgba(248,243,234,0.24);
  color: #FFFFFF;
  transform: translateY(-1px);
}

.sidebar-current-action.active {
  background: rgba(217,170,89,0.18);
  border-color: rgba(217,170,89,0.34);
  color: #FFF1D3;
}

.sidebar-current-action.subtle {
  color: rgba(248,243,234,0.72);
}

.sidebar-utility-link-shell {
  margin-top: 0.65rem;
}

.sidebar-utility-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: #F8F3EA;
  font-size: 0.88rem;
  font-weight: 700;
  text-decoration: none;
  border-bottom: 1px solid rgba(248,243,234,0.18);
}

.sidebar-utility-link:hover {
  color: #FFFFFF;
  border-bottom-color: rgba(248,243,234,0.34);
}

.sidebar-storage-shell {
  margin-top: 0.15rem;
  padding: 0.95rem 1rem 1rem;
  border-radius: 18px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(248,243,234,0.12);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
  backdrop-filter: blur(12px);
}

.sidebar-storage-line {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
  color: rgba(248,243,234,0.78);
  font-size: 0.82rem;
  line-height: 1.5;
}

.sidebar-storage-line strong {
  color: #F8F3EA;
  font-size: 1rem;
  font-weight: 800;
}

.sidebar-storage-bar {
  margin-top: 0.7rem;
  height: 0.48rem;
  border-radius: 999px;
  background: rgba(255,255,255,0.1);
  overflow: hidden;
}

.sidebar-storage-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(135deg, #C36E31, #E19A56);
}

.sidebar-storage-meta {
  margin-top: 0.65rem;
  display: flex;
  justify-content: space-between;
  gap: 0.6rem;
  color: rgba(248,243,234,0.66);
  font-size: 0.76rem;
  font-weight: 700;
}

.block-container {
  padding-top: calc(2.75rem + env(safe-area-inset-top, 0px));
  padding-bottom: 4rem;
  max-width: 1280px;
}

.workspace-rail {
  position: sticky;
  top: calc(0.85rem + env(safe-area-inset-top, 0px));
  z-index: 40;
  margin: 1rem 0 1.2rem;
  padding: 0.45rem;
  border: 1px solid rgba(255,255,255,0.48);
  border-radius: 24px;
  background: rgba(248, 242, 232, 0.78);
  backdrop-filter: blur(14px);
  box-shadow: 0 18px 38px rgba(26, 43, 36, 0.08);
}

.workspace-rail [data-baseweb="tab-list"] {
  background: transparent !important;
  gap: 0.15rem;
}

.workspace-rail button[role="tab"] {
  min-height: 2.85rem;
  border-radius: 16px !important;
}

.app-footer {
  margin: 3.2rem 0 0.75rem;
  padding: 1.25rem 0 0;
  border-top: 1px solid rgba(48, 71, 58, 0.12);
  color: rgba(31, 42, 38, 0.62);
  font-size: 0.92rem;
  text-align: center;
}

.app-footer a {
  color: var(--palmetto);
  font-weight: 700;
  text-decoration: none;
}

.app-footer a:hover {
  color: var(--charcoal);
  text-decoration: underline;
}

h1, h2, h3 {
  font-family: 'Fraunces', serif;
  color: var(--charcoal);
  letter-spacing: -0.03em;
}

.hero-shell {
  position: relative;
  overflow: hidden;
  padding: 2rem 2.2rem 2.3rem;
  border: 1px solid var(--line);
  border-radius: 32px;
  background:
    radial-gradient(circle at top right, rgba(217,170,89,0.16), transparent 28%),
    linear-gradient(180deg, rgba(250,246,238,0.96) 0%, rgba(244,236,224,0.92) 100%);
  box-shadow: var(--shadow);
  backdrop-filter: blur(8px);
}

.hero-shell::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, rgba(255,255,255,0.1) 0%, transparent 38%, rgba(36,66,50,0.02) 100%);
  pointer-events: none;
}

.hero-kicker {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.85rem;
  border-radius: 999px;
  background: rgba(36,66,50,0.08);
  color: var(--sawgrass);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.hero-brand {
  margin: 1rem 0 0;
  font-size: clamp(2.8rem, 5vw, 5.8rem);
  line-height: 0.92;
}

.hero-subcopy {
  max-width: 48rem;
  margin-top: 1rem;
  font-size: 1.05rem;
  line-height: 1.75;
  color: rgba(31,42,38,0.78);
}

.section-shell {
  padding: 1.35rem 1.4rem 1.5rem;
  border: 1px solid var(--line);
  border-radius: 28px;
  background: var(--paper);
  box-shadow: var(--shadow);
  backdrop-filter: blur(8px);
}

.section-label {
  margin: 0 0 0.45rem;
  color: var(--river-silt);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.photo-meta {
  font-size: 0.8rem;
  color: rgba(31,42,38,0.72);
  line-height: 1.5;
}

.photo-meta-link {
  color: var(--palmetto);
  font-weight: 700;
  text-decoration: none;
  border-bottom: 1px solid rgba(48, 71, 58, 0.24);
}

.photo-meta-link:hover {
  color: var(--charcoal);
  border-bottom-color: rgba(31, 42, 38, 0.52);
}

.photo-link {
  display: block;
  border-radius: 22px;
  overflow: hidden;
  text-decoration: none;
}

.photo-link img {
  display: block;
  width: 100%;
  aspect-ratio: 4 / 5;
  height: auto;
  object-fit: cover;
  border-radius: 22px;
  transition: transform 160ms ease, filter 160ms ease;
  background: rgba(31,42,38,0.06);
}

.photo-link:hover img {
  transform: scale(1.015);
  filter: saturate(1.02);
}

.photo-link--species-log-lead img {
  aspect-ratio: 3 / 4;
  width: 100%;
  height: auto;
  border-radius: 18px;
}

.photo-link--species-log-encounter-lead img {
  aspect-ratio: 1 / 1;
  width: 100%;
  height: auto;
  border-radius: 18px;
}

.photo-link--species-log-thumb img {
  aspect-ratio: 1 / 1;
  width: 100%;
  height: auto;
  border-radius: 16px;
}

.photo-link--publish-thumb img {
  aspect-ratio: 1 / 1;
  width: 100%;
  height: auto;
  border-radius: 18px;
}

.photo-link--library-cover img {
  height: 16.5rem;
  border-radius: 26px;
  transition: transform 220ms ease, filter 220ms ease;
}

.library-cover-placeholder {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 0.55rem;
  min-height: 16.5rem;
  padding: 1.35rem;
  border-radius: 26px;
  background:
    linear-gradient(180deg, rgba(36,66,50,0.86) 0%, rgba(23,50,37,0.98) 100%);
  color: #F8F3EA;
  text-decoration: none;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
  transition: transform 220ms ease, filter 220ms ease;
}

.library-cover-mark {
  width: 3.1rem;
  height: 3.1rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(217,170,89,0.18);
  color: #F0E6D8;
  font-family: 'Fraunces', serif;
  font-size: 1.55rem;
  line-height: 1;
}

.library-cover-copy {
  max-width: 14rem;
  color: rgba(248,243,234,0.8);
  font-size: 0.84rem;
  line-height: 1.55;
  font-weight: 700;
}

.photo-link--library-cover:hover img,
.library-cover-placeholder:hover {
  transform: translateY(-3px);
  filter: saturate(1.04);
}

.library-hero {
  padding: 1.55rem 1.6rem 1.5rem;
  border-radius: 32px;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.82) 0%, rgba(249,243,232,0.94) 56%, rgba(244,237,224,0.98) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.7),
    0 20px 44px rgba(56, 43, 16, 0.06);
}

.library-hero-copy {
  max-width: 56rem;
}

.library-hero-label {
  margin: 0 0 0.75rem;
  color: var(--river-silt);
  font-size: 0.9rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.library-hero-title {
  margin: 0;
  color: var(--charcoal);
  font-family: 'Fraunces', serif;
  font-size: clamp(2.15rem, 3.2vw, 3.35rem);
  line-height: 0.96;
  letter-spacing: -0.055em;
}

.library-hero-body {
  max-width: 46rem;
  margin: 0.9rem 0 0;
  color: rgba(31,42,38,0.74);
  font-size: 1rem;
  line-height: 1.7;
}

.library-hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.9rem 1.35rem;
  margin-top: 1.05rem;
  color: rgba(31,42,38,0.66);
  font-size: 0.83rem;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.library-rail-note {
  padding-top: 0.65rem;
  color: rgba(31,42,38,0.66);
  font-size: 0.9rem;
  line-height: 1.55;
  font-weight: 600;
}

.library-section-label {
  margin: 1.2rem 0 0.55rem;
  color: var(--river-silt);
  font-size: 0.76rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.species-log-toolbar {
  margin: 0.65rem 0 1rem;
}

.species-log-results {
  margin-top: 0.55rem;
  color: rgba(31,42,38,0.72);
  font-size: 0.92rem;
  font-weight: 600;
}

.species-log-index-head,
.species-log-detail-head {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}

.species-log-index-head--after-record {
  margin: 1.6rem 0 0.8rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(32,44,36,0.1);
}

.species-log-detail-head {
  margin: 1.1rem 0 0.7rem;
}

.species-log-focus-rail {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
  margin: 0.2rem 0 0.75rem;
}

.species-log-focus-caption {
  margin: 0;
  color: rgba(31,42,38,0.62);
  font-size: 0.88rem;
  font-weight: 600;
  line-height: 1.45;
}

.species-log-index-caption {
  margin: 0;
  color: rgba(31,42,38,0.62);
  font-size: 0.88rem;
  font-weight: 600;
  line-height: 1.45;
}

.species-log-index-card {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  padding: 0.75rem;
  border: 1px solid rgba(31,42,38,0.08);
  border-radius: 22px;
  background: rgba(255,255,255,0.38);
}

.species-log-index-card--active {
  border-color: rgba(196,128,61,0.34);
  background: linear-gradient(180deg, rgba(255,255,255,0.48) 0%, rgba(244,229,206,0.56) 100%);
}

.species-log-index-card--open {
  border-color: rgba(196,128,61,0.52);
  box-shadow: 0 16px 30px rgba(193,121,51,0.12);
}

.species-log-index-thumb {
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  border-radius: 18px;
  display: block;
}

.species-log-index-card-body {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}

.species-log-index-card-state {
  color: var(--river-silt);
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.species-log-index-card-title {
  color: var(--charcoal);
  font-size: 0.98rem;
  line-height: 1.25;
  font-weight: 800;
}

.species-log-index-card-subtitle {
  color: rgba(31,42,38,0.84);
  font-size: 0.84rem;
  line-height: 1.35;
  font-style: italic;
}

.species-log-index-card-meta {
  color: rgba(31,42,38,0.58);
  font-size: 0.78rem;
  line-height: 1.35;
  font-weight: 700;
}

.library-group-label {
  margin: 1.55rem 0 0.45rem;
  color: var(--river-silt);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.species-log-shell {
  padding: 1.25rem 0 0.55rem;
}

.species-log-shell--focused {
  padding-top: 0.1rem;
}

.species-log-shell details {
  margin-top: 0;
  border: none;
  border-radius: 0;
  background: transparent;
  overflow: visible;
}

.species-log-shell details summary {
  display: none;
}

.species-log-row {
  padding: 0.9rem 1rem 0.8rem;
}

.species-log-header {
  display: flex;
  flex-direction: column;
  gap: 0.42rem;
}

.species-log-guide-links {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 0.65rem;
}

.species-log-guide-links a {
  color: var(--palmetto);
  font-size: 0.84rem;
  font-weight: 800;
  text-decoration: none;
  border-bottom: 1px solid rgba(48,71,58,0.18);
}

.species-log-guide-links a:hover {
  color: var(--charcoal);
  border-bottom-color: rgba(31,42,38,0.44);
}

.species-log-guide-summary {
  margin-top: 0.85rem;
  max-width: 60ch;
  color: rgba(31,42,38,0.76);
  font-size: 0.96rem;
  line-height: 1.68;
}

.species-log-summary {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.species-log-title {
  margin: 0;
  color: var(--charcoal);
  font-size: 1.18rem;
  line-height: 1.2;
  font-weight: 800;
}

.species-log-subtitle {
  margin: 0;
  color: rgba(31,42,38,0.88);
  font-size: 0.98rem;
  line-height: 1.45;
  font-style: italic;
}

.species-log-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  margin-top: 0.3rem;
  color: rgba(31,42,38,0.66);
  font-size: 0.84rem;
  font-weight: 700;
}

.species-log-kicker {
  color: var(--river-silt);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.species-record-dialog-shell {
  margin-top: 0.55rem;
  padding-top: 0.85rem;
  border-top: 1px solid rgba(32,44,36,0.08);
}

.species-log-encounter {
  margin: 0 !important;
  padding: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
}

.species-log-encounter:first-of-type {
  margin-top: 0 !important;
}

.species-log-encounter:empty {
  display: none !important;
  margin: 0 !important;
  padding: 0 !important;
  min-height: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}

.species-log-entry-card {
  padding: 1rem 0 1rem;
  border-top: 1px solid rgba(32,44,36,0.08);
}

.species-log-encounter-head {
  display: flex;
  flex-direction: column;
  gap: 0.28rem;
}

.species-log-encounter-title {
  margin: 0;
  color: var(--charcoal);
  font-size: 1rem;
  line-height: 1.35;
  font-weight: 800;
}

.species-log-encounter-meta {
  margin: 0.18rem 0 0;
  color: rgba(31,42,38,0.68);
  font-size: 0.86rem;
  line-height: 1.5;
}

.species-log-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 0.62rem;
}

.species-log-actions a {
  color: var(--palmetto);
  font-size: 0.84rem;
  font-weight: 800;
  text-decoration: none;
  border-bottom: 1px solid rgba(48,71,58,0.18);
}

.species-log-actions a:hover {
  color: var(--charcoal);
  border-bottom-color: rgba(31,42,38,0.44);
}

.species-log-more {
  margin-top: 0.7rem;
  color: rgba(31,42,38,0.58);
  font-size: 0.82rem;
  font-weight: 700;
}

.species-log-thumb-strip {
  margin-top: 0.35rem;
}

.species-log-thumb-label {
  margin: 0.55rem 0 0;
  color: rgba(31,42,38,0.54);
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.species-log-single-note {
  display: inline-flex;
  align-items: center;
  margin-top: 0.55rem;
  color: rgba(31,42,38,0.58);
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.species-log-divider {
  margin: 0.9rem 0 0;
}

.library-row-shell {
  padding: 1.3rem 0 0.7rem;
}

.library-row-shell--standalone {
  padding-top: 0.55rem;
}

.library-row-copy {
  display: flex;
  flex-direction: column;
  gap: 0.34rem;
  padding-top: 0.55rem;
}

.library-row-kicker {
  color: var(--river-silt);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.55rem;
}

.library-row-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 1.55rem;
  padding: 0.18rem 0.55rem;
  border-radius: 999px;
  background: rgba(36,66,50,0.08);
  color: rgba(31,42,38,0.7);
  font-size: 0.66rem;
  font-weight: 900;
  letter-spacing: 0.12em;
}

.library-row-title {
  margin: 0;
  color: var(--charcoal);
  font-family: 'Fraunces', serif;
  font-size: clamp(1.52rem, 2vw, 1.85rem);
  line-height: 1.02;
  letter-spacing: -0.035em;
}

.library-row-subtitle {
  margin: 0.1rem 0 0;
  color: rgba(31,42,38,0.8);
  font-size: 0.98rem;
  line-height: 1.6;
  font-weight: 600;
}

.library-row-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem 1rem;
  margin-top: 0.45rem;
  color: rgba(31,42,38,0.64);
  font-size: 0.85rem;
  line-height: 1.5;
  font-weight: 700;
}

.library-row-notes {
  max-width: 42rem;
  margin: 0.45rem 0 0;
  color: rgba(31,42,38,0.68);
  font-size: 0.92rem;
  line-height: 1.68;
}

.library-action-intro {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  margin: 0.45rem 0 0.55rem;
  padding-left: 0.35rem;
  color: rgba(31,42,38,0.6);
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.library-action-count {
  color: var(--charcoal);
}

.library-action-separator {
  opacity: 0.45;
}

.library-row-utility {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 0.55rem;
}

.library-row-action-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.55rem;
  width: 100%;
}

.library-row-utility a {
  text-decoration: none;
}

.library-inline-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.35rem;
  min-width: 7.75rem;
  padding: 0.5rem 0.92rem;
  border-radius: 999px;
  background: rgba(36,66,50,0.08);
  border: 1px solid rgba(36,66,50,0.15);
  color: var(--palmetto) !important;
  font-size: 0.82rem;
  font-weight: 800;
  letter-spacing: 0.01em;
  transition: background 160ms ease, border-color 160ms ease, transform 160ms ease, color 160ms ease;
}

.library-inline-action:hover {
  background: rgba(36,66,50,0.14);
  border-color: rgba(36,66,50,0.22);
  color: var(--charcoal) !important;
  transform: translateY(-1px);
}

[data-testid="stButton"] button[kind="primary"] {
  min-height: 2.95rem;
}

[data-testid="stButton"] button[kind="primary"][data-testid="baseButton-secondary"] {
  min-height: 2.95rem;
}

.workspace-lane-label {
  margin: 0 0 0.7rem;
  color: var(--river-silt);
  font-size: 0.82rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.workspace-compact-strip {
  padding: 0.25rem 0 0.55rem;
  border-bottom: 1px solid rgba(31,42,38,0.08);
}

.workspace-compact-head {
  display: flex;
  flex-direction: column;
  gap: 0.12rem;
}

.workspace-compact-head .workspace-lane-label {
  margin-bottom: 0.2rem;
}

.workspace-compact-title {
  margin: 0;
  color: var(--charcoal);
  font-family: 'Fraunces', serif;
  font-size: clamp(1.45rem, 2vw, 1.95rem);
  line-height: 1.02;
  letter-spacing: -0.04em;
}

.workspace-compact-meta,
.publish-lane-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem 1.25rem;
  margin-top: 0.75rem;
  color: rgba(31,42,38,0.65);
  font-size: 0.82rem;
  font-weight: 800;
}

.workspace-mode-note {
  padding-top: 0.55rem;
  color: rgba(31,42,38,0.62);
  font-size: 0.84rem;
  font-weight: 700;
}

.workspace-mode-strip {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.95rem;
}

.workspace-mode-copy {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}

.workspace-mode-caption {
  margin: 0;
  color: rgba(31,42,38,0.62);
  font-size: 0.9rem;
  font-weight: 600;
}

.review-filter-strip,
.alternate-suggestions-shell,
.publish-filter-strip {
  margin-top: 0.95rem;
}

.review-filter-copy,
.publish-filter-copy {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}

.review-filter-caption,
.alternate-suggestions-caption,
.publish-filter-caption {
  margin: 0;
  color: rgba(31,42,38,0.62);
  font-size: 0.88rem;
  font-weight: 600;
}

.alternate-suggestion-meta {
  margin: 0.35rem 0 0.15rem;
  color: rgba(31,42,38,0.82);
  font-size: 0.92rem;
  font-weight: 700;
}

.alternate-suggestion-meta em {
  color: rgba(31,42,38,0.66);
  font-weight: 500;
  margin-left: 0.2rem;
}

.publish-queue-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem 1.15rem;
  margin: 0.95rem 0 0.35rem;
  color: rgba(31,42,38,0.62);
  font-size: 0.82rem;
  font-weight: 800;
}

.alternate-suggestion-row {
  padding: 0.78rem 0.95rem;
  border: 1px solid rgba(31,42,38,0.08);
  border-radius: 18px;
  background: rgba(255,255,255,0.5);
  color: var(--charcoal);
}

.alternate-suggestion-confidence {
  padding-top: 0.92rem;
  color: rgba(31,42,38,0.62);
  font-size: 0.82rem;
  font-weight: 800;
  text-align: center;
}

.workspace-lane-heading {
  margin: 0.7rem 0 0.75rem;
}

.workspace-lane-title {
  margin: 0;
  color: var(--charcoal);
  font-family: 'Fraunces', serif;
  font-size: clamp(1.45rem, 2vw, 2rem);
  line-height: 1.02;
  letter-spacing: -0.04em;
}

.publish-lane-heading {
  margin-top: 1rem;
}

.species-review-entry-shell {
  margin-top: 1rem;
  padding: 1.05rem 0 1.05rem;
  border-top: 1px solid rgba(31,42,38,0.08);
}

.species-review-entry-shell:first-of-type {
  margin-top: 0.45rem;
}

.species-review-entry-head {
  margin-bottom: 0.7rem;
}

.species-review-entry-kicker {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.55rem;
  color: rgba(31,42,38,0.62);
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.viewer-context {
  margin-bottom: 0.65rem;
  color: rgba(31,42,38,0.66);
  font-size: 0.85rem;
  font-weight: 700;
}

.publish-row-shell {
  display: flex;
  flex-direction: column;
  gap: 0.34rem;
}

.publish-row-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-bottom: 0.2rem;
}

.publish-queue-entry {
  display: block;
  margin-top: 0.85rem;
  padding: 0.95rem 0 1rem;
  border-top: 1px solid rgba(31,42,38,0.08);
}

.publish-posted-note {
  color: rgba(31,42,38,0.56);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.publish-state-line {
  margin-top: 0.5rem;
}

.publish-photo-meta {
  margin-top: 0.35rem !important;
  margin-bottom: 0 !important;
}

.publish-action-link {
  margin-top: 0.05rem;
}

.publish-select-block {
  padding-top: 0.2rem;
}

.viewer-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  margin-top: 0.3rem;
  min-height: 2.8rem;
  padding: 0.72rem 1rem;
  border-radius: 999px;
  background: rgba(36,66,50,0.08);
  border: 1px solid rgba(36,66,50,0.14);
  color: var(--palmetto);
  font-weight: 700;
  text-decoration: none;
}

.viewer-link:hover {
  background: rgba(36,66,50,0.12);
  border-color: rgba(36,66,50,0.2);
}

.species-detail {
  margin-top: 0.6rem;
  color: rgba(31,42,38,0.78);
  line-height: 1.65;
  font-size: 0.94rem;
}

.species-summary-block {
  min-height: 7.2rem;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
}

.species-summary-name {
  font-size: 1.08rem;
  line-height: 1.28;
  font-weight: 800;
  color: var(--charcoal);
}

.species-summary-scientific {
  margin-top: 0.2rem;
  min-height: 1.55rem;
  font-size: 0.95rem;
  line-height: 1.4;
  font-style: italic;
  color: rgba(31,42,38,0.92);
}

.species-summary-confidence {
  margin-top: 0.35rem;
  font-size: 0.95rem;
  line-height: 1.4;
  color: rgba(31,42,38,0.9);
}

.species-summary-meta {
  margin-top: 0.48rem;
  min-height: 1.15rem;
  font-size: 0.84rem;
  line-height: 1.35;
  color: rgba(31,42,38,0.56);
}

.utility-rail-status {
  padding-top: 2.1rem;
  color: rgba(31,42,38,0.68);
  font-size: 0.92rem;
  line-height: 1.5;
  font-weight: 600;
}

.review-page-status {
  text-align: right;
}

.review-action-note {
  padding-top: 0.55rem;
  color: rgba(31,42,38,0.58);
  font-size: 0.82rem;
  line-height: 1.45;
  text-align: right;
}

.back-to-top-shell {
  display: flex;
  justify-content: flex-end;
  margin-top: 1.35rem;
}

.journal-handoff-shell {
  margin-top: 1.1rem;
}

.journal-footer-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 0.7rem;
  margin-top: 1.05rem;
  flex-wrap: wrap;
}

.journal-footer-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.5rem;
  padding: 0.66rem 0.95rem;
  border-radius: 999px;
  border: 1px solid rgba(48,71,58,0.14);
  background: rgba(255,255,255,0.68);
  color: var(--palmetto);
  font-size: 0.88rem;
  font-weight: 800;
  letter-spacing: 0.01em;
  text-decoration: none;
  transition: transform 140ms ease, border-color 140ms ease, background 140ms ease, color 140ms ease;
}

.journal-footer-link:hover {
  transform: translateY(-1px);
  border-color: rgba(48,71,58,0.24);
  background: rgba(255,255,255,0.86);
}

.journal-footer-link--accent {
  border-color: rgba(193,121,51,0.2);
  background: rgba(193,121,51,0.12);
  color: var(--burnt-orange);
}

.journal-footer-link--accent:hover {
  border-color: rgba(193,121,51,0.34);
  background: rgba(193,121,51,0.18);
}

.back-to-top-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.6rem;
  padding: 0.72rem 1rem;
  border-radius: 999px;
  border: 1px solid rgba(48,71,58,0.14);
  background: rgba(255,255,255,0.68);
  color: var(--palmetto);
  font-size: 0.88rem;
  font-weight: 800;
  letter-spacing: 0.01em;
  text-decoration: none;
  transition: transform 140ms ease, border-color 140ms ease, background 140ms ease;
}

.back-to-top-link:hover {
  transform: translateY(-1px);
  border-color: rgba(48,71,58,0.24);
  background: rgba(255,255,255,0.86);
}

html, body, [data-testid="stAppViewContainer"] {
  scroll-behavior: smooth;
  -webkit-tap-highlight-color: transparent;
}

body {
  overscroll-behavior-y: contain;
}

.status-pill {
  display: inline-block;
  padding: 0.32rem 0.65rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.status-pill.pending { background: rgba(137,184,199,0.18); color: #295c69; }
.status-pill.confirmed { background: rgba(110,138,87,0.18); color: #456037; }
.status-pill.rejected { background: rgba(184,140,90,0.18); color: #8a5b2e; }
.status-pill.review-waiting-for-suggestion { background: rgba(137,184,199,0.16); color: #2f6170; }
.status-pill.review-ready-for-decision { background: rgba(217,170,89,0.22); color: #8c5d1f; }
.status-pill.review-confirmed { background: rgba(110,138,87,0.18); color: #456037; }
.status-pill.review-rejected { background: rgba(184,140,90,0.18); color: #8a5b2e; }
.status-pill.publish-ready-to-post { background: rgba(217,170,89,0.2); color: #94601e; }
.status-pill.publish-posted { background: rgba(110,138,87,0.18); color: #456037; }
.status-pill.publish-needs-attention { background: rgba(189,107,47,0.18); color: #9a4c1b; }

.metric-line {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 1rem;
  color: rgba(31,42,38,0.76);
  font-size: 0.92rem;
  font-weight: 600;
}

.stTabs [data-baseweb="tab-list"] {
  gap: 0.75rem;
}

.stTabs [data-baseweb="tab"] {
  height: 3rem;
  padding: 0 1rem;
  border-radius: 999px;
  background: rgba(255,255,255,0.58);
  border: 1px solid rgba(48,71,58,0.1);
}

.stTabs [aria-selected="true"] {
  background: var(--palmetto) !important;
  color: #fffaf4 !important;
}

.stButton button, .stFormSubmitButton button {
  min-height: 2.95rem;
  border-radius: 999px;
  border: 0;
  background: linear-gradient(135deg, var(--river-silt), #d58742);
  color: white;
  font-weight: 800;
  letter-spacing: 0.02em;
  box-shadow: 0 18px 40px rgba(189, 107, 47, 0.22);
}

[data-baseweb="popover"] button {
  min-height: 2.5rem;
  padding-inline: 0.8rem;
  white-space: nowrap;
}

[data-baseweb="popover"] [data-testid="InputInstructions"] {
  display: none !important;
}

[data-testid="stPopover"] .stButton button,
[data-testid="stPopover"] .stLinkButton a {
  min-height: 2.65rem;
}

[data-testid="stNumberInput"] button {
  min-height: 2.4rem;
}

.stButton button:hover, .stFormSubmitButton button:hover {
  filter: brightness(1.03);
  transform: translateY(-2px);
}

.stButton button:disabled,
.stFormSubmitButton button:disabled {
  background: rgba(95,109,99,0.12) !important;
  color: rgba(95,109,99,0.42) !important;
  border: 1px solid rgba(32,44,36,0.08) !important;
  opacity: 1 !important;
  filter: none !important;
  box-shadow: none !important;
  transform: none !important;
}

.stTextInput input, .stTextArea textarea, .stDateInput input, .stNumberInput input {
  background: rgba(255,255,255,0.82);
  border-radius: 18px;
}

[data-testid="stFileUploaderDropzone"] {
  background: rgba(255,255,255,0.62);
  border-radius: 24px;
  border: 1px dashed rgba(32,44,36,0.18);
}

[data-testid="stMetric"] {
  background: transparent;
}

.mobile-app-shell,
.mobile-current-shell,
.mobile-bottom-nav,
.st-key-mobile_quick_actions {
  display: none;
}

@media (max-width: 900px) {
  .workspace-rail,
  .stTabs [data-baseweb="tab-list"] {
    overflow-x: auto;
    flex-wrap: nowrap;
    scrollbar-width: none;
  }

  .workspace-rail button[role="tab"],
  .stTabs [data-baseweb="tab"] {
    flex: 0 0 auto;
    white-space: nowrap;
  }
}

@media (max-width: 768px) {
  .block-container {
    padding-top: calc(5.35rem + env(safe-area-inset-top, 0px));
    padding-left: 1rem;
    padding-right: 1rem;
    padding-bottom: calc(6.5rem + env(safe-area-inset-bottom, 0px));
  }

  [data-testid="stSidebar"],
  [data-testid="collapsedControl"] {
    display: none !important;
  }

  .st-key-mobile_quick_actions {
    display: block;
    margin: 0 0 0.45rem;
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
  }

  .st-key-mobile_quick_actions [data-testid="stHorizontalBlock"] {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 0.5rem !important;
  }

  .st-key-mobile_quick_actions [data-testid="stHorizontalBlock"] > [data-testid="column"] {
    width: 100% !important;
    min-width: 0 !important;
    flex: none !important;
  }

  .mobile-quick-actions-label {
    display: none;
  }

  .st-key-mobile_quick_actions [data-testid="stButton"] button {
    min-height: 2.7rem;
    border-radius: 18px !important;
  }

  .hero-shell {
    display: none;
  }

  .library-hero {
    padding: 0.35rem 0 0.45rem;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }

  .library-hero-label {
    color: #b86f3c;
    font-size: 0.62rem;
    letter-spacing: 0.14em;
    margin-bottom: 0.35rem;
  }

  .library-hero-title {
    font-size: clamp(1.28rem, 5.6vw, 1.72rem);
    line-height: 1.08;
  }

  .library-hero-body {
    display: none;
  }

  .library-hero-meta {
    gap: 0.35rem 0.55rem;
    margin-top: 0.48rem;
    font-size: 0.72rem;
    line-height: 1.25;
  }

  .mobile-app-shell {
    display: block;
  }

  .mobile-current-shell {
    position: fixed;
    z-index: 999998;
    top: env(safe-area-inset-top, 0px);
    left: 0;
    right: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.8rem;
    min-height: 4.8rem;
    padding: 0.65rem 1rem 0.7rem;
    background: rgba(245,239,228,0.96);
    border-bottom: 1px solid rgba(32,44,36,0.1);
    box-shadow: 0 14px 34px rgba(32,44,36,0.08);
    backdrop-filter: blur(16px);
  }

  .mobile-current-shell--quiet {
    min-height: 4.2rem;
  }

  .mobile-current-label {
    margin-bottom: 0.18rem;
    color: #b86f3c;
    font-family: "Inter", sans-serif;
    font-size: 0.64rem;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-transform: uppercase;
  }

  .mobile-current-title {
    max-width: min(68vw, 25rem);
    overflow: hidden;
    color: #17231d;
    font-family: "Fraunces", Georgia, serif;
    font-size: 1.2rem;
    font-weight: 800;
    line-height: 1.05;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-current-meta {
    max-width: min(68vw, 25rem);
    margin-top: 0.18rem;
    overflow: hidden;
    color: #647066;
    font-size: 0.78rem;
    font-weight: 700;
    line-height: 1.25;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-current-close {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.6rem;
    padding: 0 1rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.72);
    border: 1px solid rgba(32,44,36,0.12);
    color: #294233 !important;
    font-size: 0.82rem;
    font-weight: 800;
    text-decoration: none !important;
  }

  .mobile-bottom-nav {
    position: fixed;
    z-index: 999999;
    left: 0.75rem;
    right: 0.75rem;
    bottom: calc(0.65rem + env(safe-area-inset-bottom, 0px));
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: 1fr;
    gap: 0.35rem;
    padding: 0.45rem;
    border: 1px solid rgba(32,44,36,0.16);
    border-radius: 24px;
    background: rgba(246,240,229,0.96);
    box-shadow: 0 18px 46px rgba(32,44,36,0.22);
    backdrop-filter: blur(18px);
  }

  .mobile-bottom-nav-link {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 0;
    min-height: 3.05rem;
    padding: 0 0.35rem;
    border-radius: 18px;
    color: #4f5b52 !important;
    font-size: clamp(0.72rem, 2.8vw, 0.86rem);
    font-weight: 850;
    line-height: 1.05;
    text-align: center;
    text-decoration: none !important;
  }

  .mobile-bottom-nav-link.active {
    background: #c57c42;
    color: #fffaf0 !important;
    box-shadow: 0 8px 22px rgba(197,124,66,0.28);
  }

  .sidebar-brand-shell {
    margin-bottom: 1.2rem;
    padding-bottom: 0.95rem;
  }

  .sidebar-brand-wordmark {
    font-size: 2rem;
  }

  .section-shell {
    padding: 0.95rem 0.95rem 1rem;
    border-radius: 20px;
  }

  .hero-shell {
    display: none;
    padding: 0.9rem 0 0.95rem;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }

  .hero-brand {
    font-size: clamp(1.95rem, 9vw, 2.65rem);
  }

  .hero-kicker {
    font-size: 0.62rem;
    letter-spacing: 0.16em;
  }

  .hero-subcopy {
    margin-top: 0.35rem;
    font-size: 0.88rem;
    line-height: 1.45;
  }

  .hero-shell::after {
    display: none;
  }

  .photo-link img {
    aspect-ratio: 4 / 5;
    height: auto;
  }

  .photo-link--species-log-lead img {
    width: 100%;
    aspect-ratio: 3 / 4;
  }

  .photo-link--species-log-encounter-lead img {
    width: 100%;
    aspect-ratio: 1 / 1;
  }

  .photo-link--species-log-thumb img {
    width: 100%;
    aspect-ratio: 1 / 1;
  }

  .photo-link--publish-thumb img {
    width: 100%;
    aspect-ratio: 1 / 1;
  }

  .photo-link--library-cover img,
  .library-cover-placeholder {
    min-height: 7rem;
    height: 7rem;
  }

  .library-hero {
    display: none;
  }

  .species-workspace-hero {
    padding: 1.1rem 1rem 1.15rem;
    border-radius: 24px;
  }

  .workspace-compact-title {
    font-size: clamp(1.35rem, 6.5vw, 1.7rem);
  }

  .workspace-compact-meta,
  .publish-lane-meta {
    gap: 0.55rem 0.95rem;
    font-size: 0.76rem;
  }

  .workspace-lane-title {
    font-size: clamp(1.3rem, 6.5vw, 1.7rem);
  }

  .library-hero-title {
    font-size: clamp(1.28rem, 5.6vw, 1.72rem);
    line-height: 1.08;
  }

  .library-hero-body {
    display: none;
    margin-top: 0.45rem;
    font-size: 0.88rem;
    line-height: 1.5;
  }

  .library-hero-meta {
    gap: 0.35rem 0.55rem;
    margin-top: 0.48rem;
    font-size: 0.72rem;
    line-height: 1.25;
  }

  .library-rail-note {
    padding-top: 0.35rem;
    font-size: 0.84rem;
  }

  .library-section-label {
    margin-top: 1rem;
    margin-bottom: 0.45rem;
  }

  .st-key-library_action_rail {
    display: none;
  }

  .st-key-library_filters {
    margin: 0.35rem 0 0.65rem;
    padding: 0.72rem;
    border: 1px solid rgba(32,44,36,0.08);
    border-radius: 20px;
    background: rgba(255,255,255,0.34);
  }

  .st-key-library_filters [data-testid="stHorizontalBlock"],
  .st-key-library_toolbar [data-testid="stHorizontalBlock"] {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 0.52rem !important;
  }

  .st-key-library_filters [data-testid="stHorizontalBlock"] > [data-testid="column"],
  .st-key-library_toolbar [data-testid="stHorizontalBlock"] > [data-testid="column"] {
    width: 100% !important;
    min-width: 0 !important;
    flex: none !important;
  }

  .st-key-library_filters [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(1),
  .st-key-library_filters [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) {
    grid-column: 1 / -1;
  }

  .st-key-library_toolbar {
    margin: 0.25rem 0 0.45rem;
    padding: 0.5rem;
    border-radius: 18px;
    background: rgba(255,255,255,0.26);
  }

  .st-key-library_toolbar [data-testid="stHorizontalBlock"] {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.2fr);
  }

  .st-key-library_toolbar [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(3),
  .st-key-library_toolbar [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(4) {
    grid-column: auto;
  }

  .st-key-library_toolbar [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(3) {
    display: none;
  }

  .st-key-library_toolbar .utility-rail-status {
    display: none;
  }

  .library-row-shell {
    padding: 0;
  }

  [class*="st-key-library_card_"] {
    margin: 0.7rem 0;
    padding: 0.72rem;
    border: 1px solid rgba(32,44,36,0.08);
    border-radius: 22px;
    background: rgba(255,255,255,0.42);
    box-shadow: 0 12px 28px rgba(32,44,36,0.06);
  }

  [class*="st-key-library_card_"] [data-testid="stHorizontalBlock"] {
    gap: 0.62rem !important;
  }

  [class*="st-key-library_card_"] [data-testid="stHorizontalBlock"] > [data-testid="column"] {
    min-width: 0 !important;
  }

  .library-row-kicker,
  .library-group-label,
  .library-section-label {
    letter-spacing: 0.13em;
  }

  .library-row-title {
    margin-bottom: 0.25rem;
    font-size: clamp(1.28rem, 6.8vw, 1.72rem);
    line-height: 1.08;
  }

  .library-row-subtitle {
    font-size: 0.94rem;
    line-height: 1.35;
  }

  .library-row-stats {
    gap: 0.45rem 0.7rem;
    margin-top: 0.5rem;
    font-size: 0.8rem;
  }

  .library-action-intro {
    display: none;
  }

  .library-row-notes {
    display: none;
  }

  [class*="st-key-library_card_"] [data-testid="stButton"] button {
    min-height: 2.85rem;
    padding-left: 0.65rem;
    padding-right: 0.65rem;
    border-radius: 18px !important;
    font-size: 0.88rem;
  }

  [class*="st-key-library_card_"] [data-testid="stButton"] button p {
    line-height: 1.12;
  }

  .species-log-shell {
    padding-top: 1rem;
  }

  .species-log-guide-summary {
    font-size: 0.92rem;
    line-height: 1.62;
  }

  .species-log-index-head--after-record {
    margin-top: 1.2rem;
    padding-top: 0.85rem;
  }

  .species-log-focus-rail {
    margin-bottom: 0.55rem;
  }

  .species-log-index-card {
    padding: 0.62rem;
    border-radius: 18px;
  }

  .species-log-index-thumb {
    border-radius: 14px;
  }

  .species-log-shell details {
    margin-top: 0;
    border-radius: 0;
  }

  .species-log-shell details summary {
    display: none;
  }

  .species-log-row {
    padding: 0.8rem 0.8rem 0.7rem;
  }

  .species-log-encounter {
    padding: 0 !important;
    border-radius: 0 !important;
  }

  .species-log-entry-card {
    padding: 0.9rem 0 0.95rem;
  }

  .journal-handoff-shell {
    margin-top: 0.95rem;
  }

  .journal-footer-actions {
    justify-content: stretch;
    gap: 0.55rem;
  }

  .journal-footer-link {
    width: 100%;
  }

  .species-log-actions {
    gap: 0.8rem;
  }

  .species-review-entry-shell {
    padding: 0.85rem 0 0.9rem;
  }

  .publish-queue-entry {
    padding: 0.82rem 0 0.88rem;
  }

  .library-row-copy {
    padding-top: 0.2rem;
  }

  .library-row-utility {
    gap: 0.45rem;
  }

  .library-inline-action {
    min-width: 0;
    width: 100%;
  }

  .utility-rail-status,
  .review-page-status,
  .review-action-note {
    padding-top: 0.4rem;
    text-align: left;
  }

  .stButton button, .stFormSubmitButton button {
    min-height: 3.15rem;
  }

  [data-testid="stHorizontalBlock"] {
    gap: 0.85rem;
  }
}

html body .species-log-encounter,
html body [data-testid="stMarkdownContainer"] .species-log-encounter {
  padding-top: 0 !important;
}

html body [data-testid="stMarkdownContainer"]:has(> .species-log-encounter:empty),
html body .stMarkdown:has(> [data-testid="stMarkdownContainer"] > .species-log-encounter:empty),
html body [data-testid="stElementContainer"]:has(.species-log-encounter:empty) {
  display: none !important;
  margin: 0 !important;
  padding: 0 !important;
  min-height: 0 !important;
}
</style>
"""


def apply_theme() -> None:
    st.html(THEME_CSS)
