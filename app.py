# ─────────────────────────────────────────────────────────────────────────────
# УСТАНОВКА:
#   py -m pip install --upgrade streamlit demoparser2 plotly pandas
#
# ЗАПУСК:
#   py -m streamlit run app.py
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bisect
import gzip
import html
import json
import math
import os
import re
import tempfile
import time
import traceback
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit import config as streamlit_config

import advisor
import updater

try:
    from demoparser2 import DemoParser
except Exception:
    DemoParser = None


MAX_UPLOAD_MB = 500
DEMO_CACHE_VERSION = 2
APP_VERSION = os.environ.get("PARSY_APP_VERSION", "1.1.0")
IS_INSTALLED = os.environ.get("PARSY_INSTALLED") == "1"

try:
    streamlit_config.set_option("server.maxUploadSize", MAX_UPLOAD_MB)
except Exception:
    pass


st.set_page_config(
    page_title="Parsy",
    layout="wide",
    initial_sidebar_state="expanded",
)


EVENT_NAMES = [
    "player_death",
    "player_hurt",
    "player_blind",
    "flashbang_detonate",
    "round_start",
    "round_end",
    "player_team",
    "player_spawn",
    "bomb_planted",
    "bomb_defused",
    "bomb_exploded",
]

PALETTE = [
    "#C2A878",
    "#8FA2A6",
    "#A5B095",
    "#B47B67",
    "#7C8C9A",
    "#D6C8AE",
    "#8F8678",
]

TRADE_SECONDS = 5.0
PLOT_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
    "scrollZoom": False,
}

WEAPON_LABELS = {
    "ak47": "AK-47",
    "m4a1": "M4A4",
    "m4a1_silencer": "M4A1-S",
    "awp": "AWP",
    "deagle": "Desert Eagle",
    "usp_silencer": "USP-S",
    "glock": "Glock-18",
    "p250": "P250",
    "tec9": "Tec-9",
    "fiveseven": "Five-SeveN",
    "cz75a": "CZ75-Auto",
    "elite": "Dual Berettas",
    "mac10": "MAC-10",
    "mp9": "MP9",
    "mp7": "MP7",
    "mp5sd": "MP5-SD",
    "ump45": "UMP-45",
    "p90": "P90",
    "bizon": "PP-Bizon",
    "galilar": "Galil AR",
    "famas": "FAMAS",
    "aug": "AUG",
    "sg556": "SG 553",
    "ssg08": "SSG 08",
    "g3sg1": "G3SG1",
    "scar20": "SCAR-20",
    "nova": "Nova",
    "xm1014": "XM1014",
    "mag7": "MAG-7",
    "sawedoff": "Sawed-Off",
    "negev": "Negev",
    "m249": "M249",
    "knife": "Knife",
    "hegrenade": "HE Grenade",
    "molotov": "Molotov",
    "incendiary": "Incendiary",
    "inferno": "Inferno",
    "flashbang": "Flashbang",
    "decoy": "Decoy",
    "taser": "Zeus x27",
    "planted_c4": "C4",
}

LIQUIPEDIA_API = "https://liquipedia.net/counterstrike/api.php"
LIQUIPEDIA_USER_AGENT = "Parsy/1.0 (local Streamlit demo analyzer)"

ESPORTS_MARKERS = {
    "hltv": "HLTV",
    "ebot": "eBot",
    "esl": "ESL",
    "pgl": "PGL",
    "blast": "BLAST",
    "iem": "IEM",
    "fissure": "FISSURE",
    "cct": "CCT",
    "major": "Major",
    "esea": "ESEA",
    "faceit": "FACEIT",
    "winline": "Winline",
    "betboom": "BetBoom",
    "relog": "Relog",
    "storm": "Storm",
    "lan": "LAN",
}

COUNTRY_CODES = {
    "russia": "ru",
    "belarus": "by",
    "ukraine": "ua",
    "kazakhstan": "kz",
    "serbia": "rs",
    "armenia": "am",
    "poland": "pl",
    "germany": "de",
    "france": "fr",
    "denmark": "dk",
    "sweden": "se",
    "finland": "fi",
    "norway": "no",
    "united states": "us",
    "usa": "us",
    "canada": "ca",
    "brazil": "br",
    "australia": "au",
    "united kingdom": "gb",
    "england": "gb",
    "china": "cn",
    "south korea": "kr",
    "mongolia": "mn",
    "turkey": "tr",
    "israel": "il",
    "latvia": "lv",
    "lithuania": "lt",
    "estonia": "ee",
    "czech republic": "cz",
    "czechia": "cz",
    "slovakia": "sk",
    "hungary": "hu",
    "romania": "ro",
    "bulgaria": "bg",
    "bosnia and herzegovina": "ba",
    "croatia": "hr",
    "slovenia": "si",
    "north macedonia": "mk",
    "montenegro": "me",
    "moldova": "md",
    "georgia": "ge",
    "azerbaijan": "az",
    "uzbekistan": "uz",
    "kyrgyzstan": "kg",
    "india": "in",
    "indonesia": "id",
    "japan": "jp",
    "taiwan": "tw",
    "hong kong": "hk",
    "south africa": "za",
    "argentina": "ar",
    "chile": "cl",
    "uruguay": "uy",
    "peru": "pe",
    "mexico": "mx",
    "colombia": "co",
    "new zealand": "nz",
    "portugal": "pt",
    "spain": "es",
    "italy": "it",
    "netherlands": "nl",
    "belgium": "be",
    "austria": "at",
    "switzerland": "ch",
    "greece": "gr",
    "albania": "al",
    "kosovo": "xk",
}


CSS = """
<style>
:root {
    --bg: #0A0B0C;
    --surface: #131416;
    --surface-raised: #17181A;
    --card: #131416;
    --card-soft: #101113;
    --line: rgba(255, 255, 255, 0.075);
    --line-strong: rgba(194, 168, 120, 0.36);
    --text: #EDEAE3;
    --muted: #A5A29B;
    --muted-2: #6F6D68;
    --accent: #C2A878;
    --accent-soft: rgba(194, 168, 120, 0.08);
    --blue: #C2A878;
    --green: #A5B095;
    --peach: #C2A878;
    --rose: #B47B67;
    --violet: #C2A878;
    --indigo: #9C8258;
    --cyan: #8FA2A6;
    --mint: #A5B095;
    --gold: #C2A878;
    --coral: #B47B67;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text);
}

.stApp {
    background: var(--bg);
}

#MainMenu, footer {
    visibility: hidden !important;
    height: 0 !important;
}

[data-testid="stHeader"] {
    height: 0 !important;
    visibility: visible !important;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    pointer-events: none !important;
}

[data-testid="stToolbar"] {
    display: flex !important;
    height: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    pointer-events: none !important;
}

[data-testid="stToolbarActions"],
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
    display: none !important;
}

[data-testid="stExpandSidebarButton"] {
    position: fixed !important;
    top: 18px !important;
    left: 18px !important;
    z-index: 1000000 !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 0.32rem !important;
    width: auto !important;
    min-width: 36px !important;
    height: 36px !important;
    margin: 0 !important;
    padding: 0 12px 0 9px !important;
    border: 1px solid #2A2B2F !important;
    border-radius: 8px !important;
    background: #131416 !important;
    color: #C2A878 !important;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.34) !important;
    pointer-events: auto !important;
    transition: background 140ms ease, border-color 140ms ease !important;
}

[data-testid="stExpandSidebarButton"]::after {
    content: "ПАНЕЛЬ";
    color: #A5A29B;
    font-size: 0.58rem;
    font-weight: 650;
    letter-spacing: 0.11em;
}

[data-testid="stExpandSidebarButton"] span,
[data-testid="stExpandSidebarButton"] svg {
    color: #C2A878 !important;
    fill: #C2A878 !important;
}

[data-testid="stExpandSidebarButton"]:hover {
    border-color: #3A3B3F !important;
    background: #1A1B1E !important;
}

[data-testid="stExpandSidebarButton"]:focus-visible {
    outline: 1px solid #C2A878 !important;
    outline-offset: 2px !important;
}

html, body, [class*="css"], .stApp, button, input, textarea, select {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI",
        Inter, Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
}

.block-container {
    max-width: 1200px;
    padding-top: 2.8rem;
    padding-bottom: 4rem;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--text) !important;
    letter-spacing: -0.035em;
}

a {
    color: var(--accent) !important;
}

.hero {
    position: relative;
    margin: 0 0 2.2rem 0;
    padding: 0.25rem 0 0.1rem 0;
}

.eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
    color: #8C8982;
    font-size: 0.59rem;
    line-height: 1.3;
    font-weight: 650;
    letter-spacing: 0.16em;
    text-transform: uppercase;
}

.eyebrow::before {
    content: "";
    width: 4px;
    height: 4px;
    border-radius: 1px;
    background: var(--accent);
    box-shadow: none;
}

.hero h1 {
    margin: 0.8rem 0 0.75rem 0;
    font-size: clamp(2.6rem, 5.6vw, 4.6rem);
    line-height: 0.98;
    font-weight: 640;
    letter-spacing: -0.055em;
    background: none;
    -webkit-background-clip: border-box;
    background-clip: border-box;
    -webkit-text-fill-color: currentColor;
    color: var(--text) !important;
    text-wrap: balance;
    filter: none;
}

.hero p {
    max-width: 640px;
    margin: 0;
    color: var(--muted);
    font-size: 0.94rem;
    line-height: 1.7;
}

.hero-line {
    width: 48px;
    height: 1px;
    margin-top: 1.45rem;
    border-radius: 0;
    background: var(--accent);
    box-shadow: none;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 10px !important;
    box-shadow: none;
    backdrop-filter: none;
}

div[data-testid="stVerticalBlockBorderWrapper"] > div {
    border-radius: 10px !important;
}

.upload-copy {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 24px;
    padding: 0.15rem 0.1rem 0.55rem 0.1rem;
}

.upload-title {
    color: var(--text);
    font-size: 1rem;
    font-weight: 620;
    letter-spacing: -0.02em;
}

.upload-sub {
    color: #B7C1BE;
    font-size: 0.72rem;
    font-weight: 560;
    letter-spacing: 0.03em;
}

[data-testid="stFileUploaderDropzone"] {
    background: var(--surface) !important;
    border: 1px solid #292A2E !important;
    border-radius: 8px !important;
    padding: 1.1rem 0.9rem !important;
    box-shadow: none !important;
    transition: border-color 160ms ease, background 160ms ease;
}

[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #414247 !important;
    background: #161719 !important;
    box-shadow: none !important;
}

[data-testid="stFileUploaderDropzone"] button {
    background: #E9E4D8 !important;
    border: 1px solid transparent !important;
    border-radius: 6px !important;
    color: #111214 !important;
    font-size: 0.72rem !important;
    font-weight: 650 !important;
    box-shadow: none !important;
    transition: background 160ms ease, border-color 160ms ease;
}

[data-testid="stFileUploaderDropzone"] button:hover {
    background: #F5F0E5 !important;
    border-color: transparent !important;
    transform: none;
    box-shadow: none !important;
}

[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzoneInstructions"] span {
    color: var(--muted-2) !important;
    font-size: 0.72rem !important;
}

[data-testid="stFileUploaderFileName"] {
    color: #D9C9A8 !important;
    font-size: 0.8rem !important;
}

[data-testid="stFileUploaderDeleteBtn"] button {
    background: transparent !important;
    border: none !important;
}

[data-testid="stFileChip"] {
    background: #17181A !important;
    border: 1px solid #2A2B2E !important;
    border-radius: 6px !important;
    box-shadow: none !important;
    color: #6F6D68 !important;
}

[data-testid="stFileChipName"] {
    color: #D8D4CA !important;
}

[data-testid="stFileChipDeleteBtn"] button {
    background: transparent !important;
    border: 0 !important;
    color: #8C8982 !important;
    box-shadow: none !important;
}

[data-testid="stFileChipDeleteBtn"] button:hover {
    background: transparent !important;
    color: #EDEAE3 !important;
}

[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-borderlessIcon"] {
    width: 28px !important;
    height: 28px !important;
    min-height: 28px !important;
    padding: 0 !important;
    border: 1px solid #2F3034 !important;
    border-radius: 6px !important;
    background: transparent !important;
    color: #B8B3A8 !important;
    box-shadow: none !important;
}

[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-borderlessIcon"]:hover {
    border-color: #414247 !important;
    background: #17181A !important;
    color: #EDEAE3 !important;
}

.empty-state {
    position: relative;
    margin-top: 0.9rem;
    padding: 3rem 2rem;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--surface);
    box-shadow: none;
    text-align: center;
    overflow: hidden;
}

.empty-state::before {
    display: none;
}

.empty-state-title {
    color: var(--text);
    font-size: 1.12rem;
    font-weight: 620;
    letter-spacing: -0.025em;
}

.empty-state-sub {
    max-width: 540px;
    margin: 0.65rem auto 0 auto;
    color: var(--muted-2);
    font-size: 0.79rem;
    line-height: 1.7;
}

.match-strip {
    display: grid;
    grid-template-columns: 1.35fr 0.8fr 0.8fr 1fr;
    gap: 0;
    margin: 1.2rem 0 1.1rem 0;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--surface);
    box-shadow: none;
    overflow: hidden;
}

.match-item {
    padding: 0.92rem 1.05rem 0.96rem 1.05rem;
    border-right: 1px solid var(--line);
    min-width: 0;
    transition: background 160ms ease;
}

.match-item:hover {
    background: rgba(194, 168, 120, 0.03);
}

.match-item:last-child {
    border-right: none;
}

.match-item .label {
    display: block;
    color: #B7C1BE;
    font-size: 0.56rem;
    font-weight: 750;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}

.match-item .value {
    display: block;
    color: var(--text);
    font-size: 0.84rem;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.stSelectbox label p,
[data-testid="stSelectbox"] [data-testid="stWidgetLabel"] p {
    color: #8C8982 !important;
    font-size: 0.57rem !important;
    font-weight: 650 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}

[data-testid="stSelectbox"] [data-testid="stTooltipIcon"] button {
    background: transparent !important;
    border: 0 !important;
    color: #6F6D68 !important;
    box-shadow: none !important;
}

[data-testid="stSelectbox"] [data-testid="stTooltipIcon"] button:hover {
    color: #B8B3A8 !important;
}

[data-testid="stSelectbox"] .react-aria-ComboBox > [role="group"] {
    min-height: 42px !important;
    border: 1px solid #292A2E !important;
    border-radius: 8px !important;
    background: #111214 !important;
    box-shadow: none !important;
    transition: border-color 160ms ease;
}

[data-testid="stSelectbox"] .react-aria-ComboBox > [role="group"]:hover,
[data-testid="stSelectbox"] .react-aria-ComboBox > [role="group"]:focus-within {
    border-color: #4A4B50 !important;
}

[data-testid="stSelectbox"] input[role="combobox"] {
    padding-left: 0.7rem !important;
    background: transparent !important;
    color: #EDEAE3 !important;
    -webkit-text-fill-color: #EDEAE3 !important;
    caret-color: #C2A878 !important;
    font-size: 0.8rem !important;
}

[data-testid="stSelectbox"] input[role="combobox"]::placeholder {
    color: #6F6D68 !important;
    -webkit-text-fill-color: #6F6D68 !important;
}

[data-testid="stSelectbox"] button[aria-label="Open"] {
    background: transparent !important;
    border: 0 !important;
    color: #8C8982 !important;
    box-shadow: none !important;
}

[data-testid="stSelectboxVirtualDropdown"] {
    border: 1px solid #303136 !important;
    border-radius: 8px !important;
    background: #17181A !important;
    outline: none !important;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45) !important;
}

[data-testid="stSelectboxVirtualDropdown"] [role="listbox"] {
    border: 0 !important;
    border-radius: 7px !important;
    background: transparent !important;
    outline: none !important;
    box-shadow: none !important;
}

[role="option"] {
    color: #B8B3A8 !important;
}

[role="option"][data-focused],
[role="option"]:hover {
    background: rgba(255, 255, 255, 0.05) !important;
    color: #EDEAE3 !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 1.65rem;
    width: 100%;
    max-width: 100%;
    padding: 0;
    margin-bottom: 1.4rem;
    border: 0;
    border-bottom: 1px solid #242529;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
    backdrop-filter: none;
    overflow-x: auto;
}

.stTabs [data-baseweb="tab"] {
    height: auto;
    padding: 0.68rem 0 !important;
    border-radius: 0 !important;
    color: #7D7A74 !important;
    font-size: 0.8rem !important;
    font-weight: 560 !important;
    letter-spacing: -0.005em;
    background: transparent !important;
    transition: color 150ms ease;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #D8D4CA !important;
    background: transparent !important;
}

.stTabs [aria-selected="true"] {
    color: #EDEAE3 !important;
    background: transparent !important;
    box-shadow: inset 0 -1px 0 #C2A878 !important;
}

.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}

.section-head {
    margin: 1.35rem 0 0.65rem 0;
}

.section-title {
    color: var(--text);
    font-size: 0.92rem;
    font-weight: 650;
    letter-spacing: -0.018em;
}

.section-title::before {
    content: "";
    display: inline-block;
    width: 2px;
    height: 12px;
    margin-right: 9px;
    border-radius: 0;
    vertical-align: -2px;
    background: var(--accent);
    box-shadow: none;
}

.section-caption {
    margin-top: 0.2rem;
    color: var(--muted-2);
    font-size: 0.7rem;
    line-height: 1.5;
}

.metric-grid {
    display: grid;
    gap: 12px;
    margin: 0.65rem 0 1.35rem 0;
}

.metric-grid.big {
    grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-grid.small {
    grid-template-columns: repeat(4, minmax(0, 1fr));
}

@media (min-width: 901px) {
    .metric-grid.small:has(.metric-card:nth-child(6)):not(:has(.metric-card:nth-child(7))) {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
}

.metric-card {
    --accent: #C2A878;
    --accent-soft: rgba(194, 168, 120, 0.08);
    position: relative;
    min-height: 102px;
    padding: 0.92rem 1rem 0.82rem 1rem;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--surface);
    box-shadow: none;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: visible;
    z-index: 0;
    transition: border-color 160ms ease, background 160ms ease;
}

.metric-card::before {
    display: none;
}

.metric-card::after {
    display: none;
}

.metric-card:nth-child(4n+2),
.metric-card:nth-child(4n+3),
.metric-card:nth-child(4n+4) {
    --accent: #C2A878;
    --accent-soft: rgba(194, 168, 120, 0.07);
}

.metric-grid.big .metric-card {
    min-height: 136px;
    padding: 1.05rem 1.1rem 0.95rem 1.1rem;
    border-radius: 12px;
}

.metric-card:hover {
    transform: none;
    border-color: #3A3B40;
    background: #151619;
    z-index: 20;
    box-shadow: none;
}

.metric-label-row {
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 0.42rem;
}

.metric-help {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    flex: 0 0 14px;
    border: 1px solid #34353A;
    border-radius: 999px;
    color: #8C8982;
    background: transparent;
    font-size: 0.5rem;
    font-weight: 700;
    letter-spacing: 0;
    text-transform: none;
    cursor: help;
    position: relative;
    outline: none;
}

.metric-help::after {
    content: attr(data-tip);
    position: absolute;
    top: calc(100% + 8px);
    left: 50%;
    width: 238px;
    padding: 0.62rem 0.7rem;
    border: 1px solid #303136;
    border-radius: 8px;
    background: #17181A;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5);
    color: #CFCBC1;
    font-size: 0.67rem;
    font-weight: 500;
    line-height: 1.5;
    letter-spacing: 0;
    text-transform: none;
    white-space: normal;
    opacity: 0;
    transform: translate(-50%, 4px);
    pointer-events: none;
    transition: opacity 140ms ease, transform 140ms ease;
    z-index: 50;
}

.metric-help:hover::after,
.metric-help:focus::after {
    opacity: 1;
    transform: translate(-50%, 0);
}

.metric-label {
    position: relative;
    z-index: 1;
    color: #8C8982;
    font-size: 0.57rem;
    font-weight: 650;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    line-height: 1.4;
}

.metric-value {
    position: relative;
    z-index: 1;
    color: var(--text);
    font-size: 1.55rem;
    font-weight: 620;
    letter-spacing: -0.04em;
    line-height: 1.12;
    margin: 0.42rem 0 0.3rem 0;
    font-variant-numeric: tabular-nums;
}

.metric-grid.big .metric-value {
    font-size: 2.3rem;
    margin: 0.68rem 0 0.4rem 0;
}

.metric-grid.big .metric-card .metric-value {
    color: var(--text);
    text-shadow: none;
}

.metric-hint {
    position: relative;
    z-index: 1;
    color: #6C6A65;
    font-size: 0.65rem;
    line-height: 1.45;
    min-height: 0.95rem;
}

[data-testid="stSidebar"] {
    background: #0D0E10;
    border-right: 1px solid #1F2023;
}

[data-testid="stSidebar"] > div {
    background: transparent;
}

[data-testid="stSidebarContent"] {
    padding-top: 1.15rem;
}

[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    padding: 1rem 0.75rem !important;
}

[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] > div > span {
    font-size: 0.76rem;
}

[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] > div > small {
    font-size: 0.68rem;
    line-height: 1.45;
}

.sidebar-brand {
    display: flex;
    align-items: center;
    gap: 0.62rem;
    margin: 0.15rem 0 1.2rem 0;
}

.sidebar-label {
    margin: 0.3rem 0 0.45rem 0;
    color: #8C8982;
    font-size: 0.57rem;
    font-weight: 650;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.sidebar-rule {
    height: 1px;
    margin: 1.15rem 0;
    background: #1F2023;
}

.sidebar-match {
    padding: 0.68rem 0.72rem;
    border: 1px solid #242529;
    border-radius: 8px;
    background: #121315;
}

.sidebar-match-title {
    overflow: hidden;
    color: #D8D4CA;
    font-size: 0.76rem;
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.sidebar-match-meta {
    margin-top: 0.26rem;
    color: #6F6D68;
    font-size: 0.62rem;
    line-height: 1.5;
}

.sidebar-note {
    margin-top: 0.7rem;
    color: #5E5C57;
    font-size: 0.62rem;
    line-height: 1.55;
}

.workspace-name {
    display: flex;
    align-items: baseline;
    gap: 0.55rem;
    min-width: 0;
}

.workspace-kicker {
    color: #8C8982;
    font-size: 0.54rem;
    font-weight: 650;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.workspace-title {
    overflow: hidden;
    color: #D8D4CA;
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.appbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin: 0 0 1.5rem 0;
    padding-bottom: 0.9rem;
    border-bottom: 1px solid #222327;
}

.brand {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    min-width: 0;
}

.brand-mark {
    position: relative;
    width: 32px;
    height: 32px;
    flex: 0 0 32px;
    border-radius: 6px;
    border: 1px solid #33342F;
    background: #161719;
    box-shadow: none;
}

.brand-mark::after {
    content: "P";
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 5px;
    background: transparent;
    color: #C2A878;
    font-size: 0.72rem;
    font-weight: 750;
    letter-spacing: 0.04em;
}

.brand-name {
    color: var(--text);
    font-size: 0.84rem;
    font-weight: 650;
    letter-spacing: -0.015em;
    text-transform: none;
    white-space: nowrap;
}

.brand-sub {
    margin-top: 0.08rem;
    color: #5E5C57;
    font-size: 0.58rem;
    letter-spacing: 0.02em;
}

.appbar-meta {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 14px;
}

.meta-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.32rem;
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    color: #6F6D68;
    font-size: 0.61rem;
    font-weight: 500;
    line-height: 1.3;
}

.meta-pill strong {
    color: #B8B3A8;
    font-weight: 600;
}

.source-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0;
    border-radius: 0;
    border: 0;
    background: transparent;
    color: #8C8982;
    font-size: 0.57rem;
    font-weight: 650;
    letter-spacing: 0.11em;
    line-height: 1.3;
    text-transform: uppercase;
}

.source-pill::before {
    content: "";
    width: 4px;
    height: 4px;
    border-radius: 1px;
    background: #C2A878;
    box-shadow: none;
}

.source-pill.hltv {
    color: #B47B67;
}

.source-pill.hltv::before {
    background: #B47B67;
}

.source-pill.esports {
    color: #9C9992;
}

.source-pill.esports::before {
    background: #8FA2A6;
}

.source-pill.community {
    color: #77746E;
}

.source-pill.community::before {
    background: #77746E;
}

.match-banner {
    position: relative;
    overflow: hidden;
    margin: 0.2rem 0 1rem 0;
    padding: 1.15rem 1.25rem;
    border: 1px solid var(--line);
    border-radius: 12px;
    background: var(--surface);
    box-shadow: none;
}

.match-banner::after {
    display: none;
}

.match-banner-top {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.8rem;
    flex-wrap: wrap;
}

.match-kicker {
    color: #8C8982;
    font-size: 0.59rem;
    font-weight: 650;
    letter-spacing: 0.11em;
    text-transform: uppercase;
}

.match-file {
    max-width: 52%;
    overflow: hidden;
    color: #5F5D58;
    font-size: 0.6rem;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.match-scoreline {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    align-items: center;
    gap: 1rem;
    margin: 1.15rem 0 1rem 0;
}

.banner-team {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    min-width: 0;
}

.banner-team.right {
    flex-direction: row-reverse;
    text-align: right;
}

.banner-logo-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 46px;
    height: 46px;
    flex: 0 0 46px;
    border: 1px solid #2B2C30;
    border-radius: 8px;
    background: #0F1012;
    box-shadow: none;
    overflow: hidden;
}

.banner-logo {
    max-width: 82%;
    max-height: 82%;
    object-fit: contain;
}

.banner-monogram,
.team-monogram {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    color: #C2A878;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}

.banner-copy {
    min-width: 0;
}

.banner-name {
    overflow: hidden;
    color: var(--text);
    font-size: 1rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.banner-sub {
    margin-top: 0.18rem;
    color: #6F6D68;
    font-size: 0.62rem;
}

.banner-score {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    padding: 0 0.35rem;
    color: var(--text);
    font-size: 2.6rem;
    font-weight: 620;
    letter-spacing: -0.06em;
    line-height: 1;
    font-variant-numeric: tabular-nums;
}

.banner-score span {
    color: #4A4945;
    font-size: 1.25rem;
    font-weight: 500;
    letter-spacing: 0;
}

.match-facts {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.45rem 1.1rem;
    padding-top: 0.8rem;
    border-top: 1px solid #222327;
}

.match-fact {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    color: #6F6D68;
    font-size: 0.62rem;
}

.match-fact strong {
    color: #B8B3A8;
    font-weight: 600;
}

.teams-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    margin: 0.75rem 0 1.35rem 0;
}

.team-panel {
    position: relative;
    overflow: hidden;
    padding: 0.95rem;
    border: 1px solid var(--line);
    border-radius: 12px;
    background: var(--surface);
    box-shadow: none;
}

.team-panel:nth-child(2) {
    background: var(--surface);
}

.team-panel-head {
    display: flex;
    align-items: center;
    gap: 0.68rem;
    padding-bottom: 0.8rem;
    border-bottom: 1px solid #222327;
}

.team-logo-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    flex: 0 0 44px;
    overflow: hidden;
    border: 1px solid #2B2C30;
    border-radius: 8px;
    background: #0F1012;
}

.team-logo {
    max-width: 82%;
    max-height: 82%;
    object-fit: contain;
}

.team-copy {
    min-width: 0;
    flex: 1;
}

.team-name {
    overflow: hidden;
    color: var(--text);
    font-size: 0.92rem;
    font-weight: 600;
    letter-spacing: -0.015em;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.team-location {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    margin-top: 0.2rem;
    color: #6F6D68;
    font-size: 0.61rem;
}

.team-score-wrap {
    margin-left: auto;
    text-align: right;
}

.team-score {
    color: var(--text);
    font-size: 1.6rem;
    font-weight: 620;
    letter-spacing: -0.045em;
    line-height: 1;
    font-variant-numeric: tabular-nums;
}

.team-start-side {
    display: inline-flex;
    margin-top: 0.25rem;
    padding: 0;
    border: 0;
    border-radius: 0;
    color: #8C8982;
    font-size: 0.5rem;
    font-weight: 650;
    letter-spacing: 0.1em;
}

.roster-list {
    display: grid;
    gap: 0;
    margin-top: 0.5rem;
}

.player-card {
    position: relative;
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.62rem;
    padding: 0.5rem 0.1rem;
    border: 0;
    border-bottom: 1px solid #202125;
    border-radius: 0;
    background: transparent;
    transition: background 150ms ease;
}

.player-card:last-child {
    border-bottom: 0;
}

.player-card:hover {
    transform: none;
    border-color: #202125;
    background: rgba(255, 255, 255, 0.018);
}

.player-card.selected {
    border-color: #202125;
    background: rgba(194, 168, 120, 0.05);
    box-shadow: inset 2px 0 0 #C2A878;
}

.player-avatar {
    position: relative;
    width: 44px;
    height: 52px;
    overflow: hidden;
    border: 1px solid #2A2B2F;
    border-radius: 6px;
    background: #0F1012;
}

.player-avatar img {
    position: absolute;
    inset: 0;
    z-index: 1;
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center 18%;
    filter: grayscale(1) contrast(1.02);
}

.avatar-fallback {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    color: #4A4945;
}

.avatar-fallback svg {
    width: 82%;
    height: 82%;
}

.player-body {
    min-width: 0;
}

.player-top {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    min-width: 0;
}

.player-nick {
    overflow: hidden;
    color: #EDEAE3;
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: -0.015em;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.player-real {
    overflow: hidden;
    margin-top: 0.06rem;
    color: #6F6D68;
    font-size: 0.59rem;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.player-badges {
    display: flex;
    align-items: center;
    gap: 0.32rem;
    margin-top: 0.26rem;
}

.player-flag {
    display: inline-block;
    width: 16px;
    height: 11px;
    border-radius: 1px;
    object-fit: cover;
    box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.10);
}

.role-pill {
    display: inline-flex;
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    color: #8C8982;
    font-size: 0.48rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    white-space: nowrap;
}

.player-local-tag {
    color: #5E5C57;
    font-size: 0.48rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.player-stats {
    display: flex;
    align-items: center;
    gap: 0.55rem;
}

.player-stat {
    min-width: 35px;
    text-align: right;
}

.player-stat-value {
    color: #B8B3A8;
    font-size: 0.72rem;
    font-weight: 600;
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
}

.player-stat-label {
    margin-top: 0.1rem;
    color: #5E5C57;
    font-size: 0.44rem;
    font-weight: 650;
    letter-spacing: 0.07em;
}

.source-note {
    display: block;
    margin: 0.25rem 0 1rem 0;
    padding: 0.1rem 0 0.1rem 0.72rem;
    border: 0;
    border-left: 2px solid #33342F;
    border-radius: 0;
    background: transparent;
    color: #6F6D68;
    font-size: 0.65rem;
    line-height: 1.55;
}

.source-note strong {
    color: #B8B3A8;
    font-weight: 600;
}

.compare-card {
    padding: 0.95rem 1rem;
    border: 1px solid var(--line);
    border-radius: 12px;
    background: var(--surface);
    box-shadow: none;
}

.compare-list {
    display: grid;
    gap: 0.82rem;
}

.compare-head {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 0.6rem;
}

.compare-value {
    color: #B8B3A8;
    font-size: 0.78rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}

.compare-value.right {
    color: #B8B3A8;
    text-align: right;
}

.compare-label {
    color: #6F6D68;
    font-size: 0.55rem;
    font-weight: 650;
    letter-spacing: 0.08em;
    text-align: center;
    text-transform: uppercase;
}

.compare-track {
    display: flex;
    height: 3px;
    margin-top: 0.36rem;
    overflow: hidden;
    border-radius: 0;
    background: #202125;
}

.compare-left {
    margin-left: auto;
    border-radius: 0;
    background: #B99C6C;
    box-shadow: none;
}

.compare-right {
    border-radius: 0;
    background: #7F9498;
    box-shadow: none;
}

.glossary-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0 1.2rem;
}

.glossary-item {
    padding: 0.6rem 0;
    border: 0;
    border-top: 1px solid #202125;
    border-radius: 0;
    background: transparent;
}

.glossary-term {
    color: #D8D4CA;
    font-size: 0.66rem;
    font-weight: 600;
}

.glossary-text {
    margin-top: 0.16rem;
    color: #6F6D68;
    font-size: 0.6rem;
    line-height: 1.5;
}

.dock-note {
    padding-top: 0.45rem;
    color: #6F6D68;
    font-size: 0.66rem;
    line-height: 1.5;
}

.dock-note strong {
    color: #A7A49C;
    font-weight: 600;
}

.empty-panel {
    padding: 1.1rem;
    border: 1px solid #242529;
    border-radius: 8px;
    color: var(--muted-2);
    font-size: 0.74rem;
    text-align: center;
    background: #111214;
}

.section-gap {
    height: 0.55rem;
}

.plot-card-caption {
    padding: 0.15rem 0.2rem 0.05rem 0.2rem;
    color: var(--muted-2);
    font-size: 0.68rem;
    line-height: 1.5;
}

.footer-note {
    margin-top: 2.6rem;
    padding-top: 1.1rem;
    border-top: 1px solid #1F2023;
    background: none;
    color: #5E5C57;
    font-size: 0.65rem;
    letter-spacing: 0.03em;
    text-align: center;
}

.ai-summary {
    margin: 0.7rem 0 1.2rem 0;
    padding: 1.15rem 1.2rem;
    border: 1px solid rgba(194, 168, 120, 0.32);
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(194, 168, 120, 0.08), rgba(19, 20, 22, 0.96) 58%);
}

.ai-summary-label,
.ai-panel-title,
.ai-day-title {
    color: #C2A878;
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.ai-summary-text {
    margin-top: 0.45rem;
    color: #EDEAE3;
    font-size: 0.92rem;
    line-height: 1.65;
}

.ai-columns {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    margin: 0.65rem 0 1.35rem 0;
}

.ai-panel {
    padding: 1rem 1.05rem;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--surface);
}

.ai-list {
    display: grid;
    gap: 0.62rem;
    margin-top: 0.7rem;
}

.ai-item {
    padding-top: 0.6rem;
    border-top: 1px solid #202125;
}

.ai-item:first-child {
    padding-top: 0;
    border-top: 0;
}

.ai-item-title {
    color: #D8D4CA;
    font-size: 0.76rem;
    font-weight: 600;
}

.ai-item-text {
    margin-top: 0.22rem;
    color: #8F8C85;
    font-size: 0.68rem;
    line-height: 1.55;
}

.ai-tag {
    display: inline-block;
    margin-top: 0.38rem;
    padding: 0.16rem 0.42rem;
    border: 1px solid rgba(194, 168, 120, 0.25);
    border-radius: 4px;
    color: #C2A878;
    background: rgba(194, 168, 120, 0.06);
    font-size: 0.58rem;
    line-height: 1.35;
}

.ai-maps {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin: 0.65rem 0 1.35rem 0;
}

.ai-map {
    padding: 1rem;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--surface);
}

.ai-map-name {
    color: #EDEAE3;
    font-size: 0.95rem;
    font-weight: 650;
    letter-spacing: -0.02em;
}

.ai-map-why {
    margin-top: 0.35rem;
    color: #8F8C85;
    font-size: 0.68rem;
    line-height: 1.55;
}

.ai-map-drills {
    margin: 0.6rem 0 0 0;
    padding: 0;
    list-style: none;
    color: #B8B3A8;
    font-size: 0.66rem;
    line-height: 1.55;
}

.ai-map-drills li {
    position: relative;
    padding-left: 0.75rem;
    margin-top: 0.25rem;
}

.ai-map-drills li::before {
    content: "";
    position: absolute;
    top: 0.48rem;
    left: 0;
    width: 3px;
    height: 3px;
    border-radius: 1px;
    background: #C2A878;
}

.ai-week {
    display: grid;
    gap: 8px;
    margin: 0.65rem 0 1.35rem 0;
}

.ai-day {
    display: grid;
    grid-template-columns: 110px minmax(0, 1fr);
    gap: 1rem;
    padding: 0.85rem 1rem;
    border: 1px solid var(--line);
    border-radius: 9px;
    background: var(--surface);
}

.ai-day-head {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
}

.ai-day-meta {
    color: #6F6D68;
    font-size: 0.62rem;
}

.ai-tasks {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 1rem;
    margin: 0;
    padding: 0;
    list-style: none;
    color: #A5A29B;
    font-size: 0.68rem;
    line-height: 1.5;
}

.ai-tasks li {
    position: relative;
    padding-left: 0.65rem;
}

.ai-tasks li::before {
    content: "";
    position: absolute;
    top: 0.48rem;
    left: 0;
    width: 3px;
    height: 3px;
    border-radius: 1px;
    background: #8FA2A6;
}

.ai-result {
    margin-top: 0.8rem;
    padding: 1rem 1.1rem;
    border: 1px solid #2A2B2E;
    border-radius: 9px;
    background: #111214;
    color: #D8D4CA;
    font-size: 0.8rem;
    line-height: 1.7;
}

.update-card {
    padding: 0.68rem 0.72rem;
    border: 1px solid #242529;
    border-radius: 8px;
    background: #121315;
}

.update-version {
    color: #D8D4CA;
    font-size: 0.72rem;
    font-weight: 600;
}

.update-note {
    margin-top: 0.2rem;
    color: #6F6D68;
    font-size: 0.62rem;
    line-height: 1.45;
}

.stButton > button {
    min-height: 36px;
    border: 1px solid #2E2F33 !important;
    border-radius: 7px !important;
    background: #17181A !important;
    color: #D8D4CA !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    box-shadow: none !important;
}

.stButton > button:hover {
    border-color: #4A4B50 !important;
    background: #1D1E21 !important;
    color: #EDEAE3 !important;
}

.stButton > button:focus-visible {
    outline: 1px solid #C2A878 !important;
    outline-offset: 2px;
}

div[data-testid="stAlert"] {
    background: #141517 !important;
    border: 1px solid #2A2B2E !important;
    border-left: 2px solid var(--accent) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
    box-shadow: none !important;
}

div[data-testid="stSpinner"] {
    color: var(--accent) !important;
}

details {
    background: #121315 !important;
    border: 1px solid #242529 !important;
    border-radius: 8px !important;
}

[data-testid="stExpander"] {
    overflow: hidden;
    border: 1px solid #242529 !important;
    border-radius: 8px !important;
    background: #121315 !important;
}

[data-testid="stExpander"] details {
    border: 0 !important;
    border-radius: 0 !important;
    background: transparent !important;
}

[data-testid="stExpander"] summary {
    padding: 0.68rem 0.8rem !important;
    color: #B8B3A8 !important;
    font-size: 0.72rem !important;
}

[data-testid="stExpander"] summary:hover {
    color: #EDEAE3 !important;
}

[data-testid="stExpander"] summary svg {
    fill: #8C8982 !important;
}

::-webkit-scrollbar {
    width: 10px;
    height: 10px;
}

::-webkit-scrollbar-track {
    background: #0A0B0C;
}

::-webkit-scrollbar-thumb {
    background: #2A2B2E;
    border: 3px solid #0A0B0C;
    border-radius: 999px;
}

::-webkit-scrollbar-thumb:hover {
    background: #3A3B3F;
}

@media (max-width: 900px) {
    .metric-grid.big,
    .metric-grid.small {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .teams-grid {
        grid-template-columns: 1fr;
    }
    .glossary-grid {
        grid-template-columns: 1fr;
    }
    .ai-columns,
    .ai-maps {
        grid-template-columns: 1fr;
    }
    .match-strip {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .match-item:nth-child(2) {
        border-right: none;
    }
    .match-item:nth-child(-n+2) {
        border-bottom: 1px solid var(--line);
    }
}

@media (max-width: 560px) {
    .block-container {
        padding-top: 2rem;
    }
    .metric-grid.big,
    .metric-grid.small {
        grid-template-columns: 1fr;
    }
    .appbar {
        align-items: flex-start;
        flex-direction: column;
    }
    .appbar-meta {
        justify-content: flex-start;
    }
    .match-banner {
        padding: 1rem;
        border-radius: 12px;
    }
    .match-banner-top {
        align-items: flex-start;
        flex-direction: column;
        gap: 0.55rem;
    }
    .match-file {
        max-width: 100%;
    }
    .match-scoreline {
        gap: 0.45rem;
        margin: 1rem 0;
    }
    .banner-logo-wrap {
        width: 40px;
        height: 40px;
        flex-basis: 40px;
        border-radius: 8px;
    }
    .banner-team {
        gap: 0.45rem;
    }
    .banner-name {
        font-size: 0.82rem;
    }
    .banner-sub {
        font-size: 0.55rem;
    }
    .banner-score {
        font-size: 2.1rem;
    }
    .banner-score span {
        font-size: 1.1rem;
    }
    .match-facts {
        gap: 0.4rem 0.7rem;
    }
    .team-panel {
        padding: 0.8rem;
        border-radius: 12px;
    }
    .player-card {
        grid-template-columns: 44px minmax(0, 1fr) auto;
        gap: 0.5rem;
    }
    .player-avatar {
        width: 44px;
        height: 52px;
    }
    .player-stats {
        gap: 0.34rem;
    }
    .player-stat {
        min-width: 31px;
    }
    .player-stat-value {
        font-size: 0.68rem;
    }
    .player-stat-label {
        font-size: 0.47rem;
    }
    .match-strip {
        grid-template-columns: 1fr;
    }
    .match-item {
        border-right: none;
        border-bottom: 1px solid var(--line);
    }
    .match-item:last-child {
        border-bottom: none;
    }
    .upload-copy {
        flex-direction: column;
        gap: 0.2rem;
    }
    .ai-day {
        grid-template-columns: 1fr;
        gap: 0.45rem;
    }
}
</style>
"""


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _render_html(markup: str) -> None:
    compact = re.sub(r">\s+<", "><", markup).strip()
    st.markdown(compact, unsafe_allow_html=True)


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "<na>"} else text


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def _sid(value: Any) -> str:
    text = _text(value)
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _team_label(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().upper()
        if text in {"CT", "COUNTER-TERRORIST", "COUNTER-TERRORISTS", "COUNTER TERRORIST"}:
            return "CT"
        if text in {"T", "TERRORIST", "TERRORISTS"}:
            return "T"
        try:
            value = float(text)
        except ValueError:
            return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    if number == 3:
        return "CT"
    if number == 2:
        return "T"
    return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def _bool_series(series: pd.Series) -> pd.Series:
    return series.map(_as_bool).astype(bool)


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    lowered = {str(column).lower(): column for column in df.columns}
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
        found = lowered.get(candidate.lower())
        if found is not None:
            return found
    return None


def _clean_event(df: Any, keep_warmup: bool = False) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    frame = df.copy()
    if "is_warmup_period" in frame.columns and not keep_warmup:
        frame = frame[~_bool_series(frame["is_warmup_period"])]
    if "tick" in frame.columns:
        frame = frame[frame["tick"].notna()].copy()
        frame["tick"] = pd.to_numeric(frame["tick"], errors="coerce")
        frame = frame[frame["tick"].notna()]
    return frame.reset_index(drop=True)


def _weapon_label(raw: str) -> str:
    key = _text(raw).lower()
    if key in WEAPON_LABELS:
        return WEAPON_LABELS[key]
    if "knife" in key:
        return "Knife"
    return key.replace("_", " ").title() if key else "Unknown"


def _utility_kind(raw: str) -> str | None:
    key = _text(raw).lower()
    if "hegrenade" in key or key == "he":
        return "he"
    if any(marker in key for marker in ("molotov", "incendiary", "inferno")) or key in {"fire", "burn"}:
        return "fire"
    return None


def _round_values(frame: pd.DataFrame) -> set[int]:
    if frame.empty or "total_rounds_played" not in frame.columns:
        return set()
    values = pd.to_numeric(frame["total_rounds_played"], errors="coerce").dropna()
    result: set[int] = set()
    for value in values:
        try:
            number = int(round(float(value)))
        except (TypeError, ValueError):
            continue
        if number >= 0:
            result.add(number)
    return result


def _parse_single_event(parser: Any, name: str) -> pd.DataFrame:
    for others in (["total_rounds_played", "is_warmup_period"], ["total_rounds_played"], None):
        try:
            if others is None:
                return parser.parse_event(name)
            return parser.parse_event(name, other=others)
        except Exception:
            continue
    return pd.DataFrame()


def _coerce_batch(result: Any) -> dict[str, pd.DataFrame]:
    parsed: dict[str, pd.DataFrame] = {}
    if isinstance(result, dict):
        for name, frame in result.items():
            if isinstance(frame, pd.DataFrame):
                parsed[str(name)] = frame
        return parsed
    if isinstance(result, (list, tuple)):
        for item in result:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                name, frame = item
                if isinstance(frame, pd.DataFrame):
                    parsed[str(name)] = frame
            elif isinstance(item, dict):
                name = item.get("name") or item.get("event")
                frame = item.get("data") or item.get("df")
                if name and isinstance(frame, pd.DataFrame):
                    parsed[str(name)] = frame
    return parsed


def _parse_events(parser: Any, names: list[str]) -> dict[str, pd.DataFrame]:
    parsed: dict[str, pd.DataFrame] = {}
    for others in (["total_rounds_played", "is_warmup_period"], ["total_rounds_played"], None):
        try:
            if others is None:
                result = parser.parse_events(names)
            else:
                result = parser.parse_events(names, other=others)
            parsed = _coerce_batch(result)
            if parsed:
                break
        except Exception:
            continue
    for name in names:
        if name not in parsed or not isinstance(parsed[name], pd.DataFrame):
            parsed[name] = _parse_single_event(parser, name)
    for name in EVENT_NAMES:
        parsed.setdefault(name, pd.DataFrame())
    return parsed


def _parse_demo_bytes(raw: bytes) -> "DemoData":
    if DemoParser is None:
        raise RuntimeError("Библиотека demoparser2 не установлена.")
    handle = tempfile.NamedTemporaryFile(prefix="parsy_", suffix=".dem", delete=False)
    path = handle.name
    try:
        handle.write(raw)
        handle.close()
        parser = DemoParser(path)

        header: dict[str, Any] = {}
        try:
            header = dict(parser.parse_header())
        except Exception:
            header = {}

        player_info = pd.DataFrame()
        try:
            player_info = parser.parse_player_info()
        except Exception:
            player_info = pd.DataFrame()

        parsed = _parse_events(parser, list(EVENT_NAMES))
        return DemoData(header, player_info, parsed)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


class DemoData:
    def __init__(
        self,
        header: dict[str, Any],
        player_info: pd.DataFrame,
        raw_events: dict[str, pd.DataFrame],
    ) -> None:
        self.header = {str(key): value for key, value in (header or {}).items()}
        self.events = {
            name: _clean_event(
                raw_events.get(name, pd.DataFrame()),
                keep_warmup=name in {"player_team", "player_spawn"},
            )
            for name in EVENT_NAMES
        }
        self.player_names: dict[str, str] = {}
        self.initial_sides: dict[str, str] = {}
        self.team_numbers: dict[str, str] = {}
        self.timelines: dict[str, tuple[list[float], list[str]]] = {}
        self.rounds: list[int] = []
        self.round_map: dict[int, int] = {}
        self.round_info = pd.DataFrame()
        self.round_winners: dict[int, str] = {}
        self._start_ticks = pd.DataFrame(columns=["tick", "round"])
        self._all_sids: set[str] = set()
        self.players: list[dict[str, str]] = []

        self._prep_events()
        self._prepare_players(player_info)
        self._assign_rounds()
        self._build_timelines()
        self._build_round_info()
        self.tick_rate = self._find_tick_rate()

        if not self.players:
            raise ValueError("В демке не найдены игроки.")
        if not self.rounds:
            raise ValueError("В демке не найдены раунды.")

    def _prep_events(self) -> None:
        for name, frame in list(self.events.items()):
            if frame.empty:
                continue
            frame = frame.copy()

            id_sources = {
                "attacker": ["attacker_steamid", "attacker_id"],
                "victim": [
                    "victim_steamid",
                    "victim_id",
                    "user_steamid",
                    "user_id",
                ],
                "assister": ["assister_steamid", "assister_id"],
                "user": ["user_steamid", "user_id"],
            }
            for prefix, candidates in id_sources.items():
                id_column = _find_col(frame, candidates)
                if id_column is not None:
                    frame[f"{prefix}_id"] = frame[id_column].map(_sid)

            name_sources = {
                "attacker": ["attacker_name"],
                "victim": ["victim_name", "user_name"],
                "assister": ["assister_name"],
                "user": ["user_name"],
            }
            for prefix, candidates in name_sources.items():
                name_column = _find_col(frame, candidates)
                if name_column is not None:
                    frame[f"{prefix}_name"] = frame[name_column]

            weapon_column = _find_col(frame, ["weapon", "weapon_name"])
            if weapon_column is not None:
                frame["weapon_l"] = frame[weapon_column].map(
                    lambda value: _text(value).lower()
                )

            bool_columns = {
                "headshot_b": ["headshot"],
                "thrusmoke_b": ["thrusmoke", "thru_smoke"],
                "attackerblind_b": ["attackerblind", "attacker_blind"],
                "penetrated_b": ["penetrated", "penetration"],
                "assistedflash_b": ["assistedflash", "assisted_flash"],
            }
            for output, candidates in bool_columns.items():
                source = _find_col(frame, candidates)
                if source is not None:
                    frame[output] = _bool_series(frame[source])

            damage_column = _find_col(frame, ["dmg_health", "damage", "health_damage"])
            if damage_column is not None:
                frame["damage"] = pd.to_numeric(
                    frame[damage_column], errors="coerce"
                ).fillna(0.0).clip(lower=0.0)

            duration_column = _find_col(
                frame, ["blind_duration", "duration", "total_flash_duration"]
            )
            if duration_column is not None:
                frame["blind_duration"] = pd.to_numeric(
                    frame[duration_column], errors="coerce"
                ).fillna(0.0).clip(lower=0.0)

            if name == "player_team":
                team_column = _find_col(frame, ["team", "team_number", "team_num", "side"])
                if team_column is not None:
                    frame["side"] = frame[team_column].map(_team_label)

            if name == "round_end":
                winner_column = _find_col(
                    frame, ["winner", "winning_team", "winning_side", "team"]
                )
                if winner_column is not None:
                    frame["winner_side"] = frame[winner_column].map(_team_label)

            self.events[name] = frame

    def _prepare_players(self, player_info: pd.DataFrame) -> None:
        if isinstance(player_info, pd.DataFrame) and not player_info.empty:
            sid_column = _find_col(
                player_info, ["steamid", "user_steamid", "player_steamid"]
            )
            name_column = _find_col(player_info, ["name", "user_name", "player_name"])
            team_column = _find_col(
                player_info, ["team_number", "team_num", "team", "side"]
            )
            team_id_column = _find_col(player_info, ["team_number", "team_num"])
            for _, row in player_info.iterrows():
                sid = _sid(row.get(sid_column)) if sid_column else ""
                if not sid:
                    continue
                self._all_sids.add(sid)
                name = _text(row.get(name_column)) if name_column else ""
                if name:
                    self.player_names[sid] = name
                team_id = _text(row.get(team_id_column)) if team_id_column else ""
                if team_id:
                    self.team_numbers[sid] = team_id
                side = _team_label(row.get(team_column)) if team_column else None
                if side:
                    self.initial_sides[sid] = side

        for frame in self.events.values():
            if frame.empty:
                continue
            for prefix in ("attacker", "victim", "assister", "user"):
                id_column = f"{prefix}_id"
                name_column = f"{prefix}_name"
                if id_column not in frame.columns:
                    continue
                names = frame[name_column] if name_column in frame.columns else [None] * len(frame)
                for sid_value, name_value in zip(frame[id_column].tolist(), list(names)):
                    sid = _sid(sid_value)
                    if not sid:
                        continue
                    self._all_sids.add(sid)
                    if not self.player_names.get(sid):
                        name = _text(name_value)
                        if name:
                            self.player_names[sid] = name

        self.players = [
            {"sid": sid, "name": self.player_names.get(sid) or sid}
            for sid in self._all_sids
        ]
        self.players.sort(key=lambda item: (item["name"].lower(), item["sid"]))

    def _assign_rounds(self) -> None:
        starts = self.events.get("round_start", pd.DataFrame())

        if not starts.empty and "tick" in starts.columns:
            start_frame = (
                starts.dropna(subset=["tick"])
                .sort_values("tick")
                .drop_duplicates(subset=["tick"])
                .reset_index(drop=True)
            )
        else:
            start_frame = pd.DataFrame()

        if not start_frame.empty:
            start_frame["round"] = range(1, len(start_frame) + 1)
            self._start_ticks = start_frame[["tick", "round"]].copy()
            self.rounds = list(range(1, len(start_frame) + 1))
            self.round_map = {
                int(round(float(tick))): int(round_number)
                for tick, round_number in zip(
                    start_frame["tick"], start_frame["round"]
                )
            }

            for name, frame in list(self.events.items()):
                if frame.empty:
                    continue
                working = frame.copy()
                working["round"] = None
                self._fill_rounds_by_tick(working)
                working = working[working["round"].notna()].copy()
                if not working.empty:
                    working["round"] = working["round"].astype(int)
                self.events[name] = working.reset_index(drop=True)
            return

        raw_values: set[int] = set()
        if not starts.empty and "total_rounds_played" in starts.columns:
            raw_values.update(_round_values(starts))
        else:
            for frame in self.events.values():
                raw_values.update(_round_values(frame))

        if not raw_values:
            self.rounds = []
            return

        ordered = sorted(raw_values)
        self.round_map = {raw: index + 1 for index, raw in enumerate(ordered)}
        self.rounds = list(range(1, len(ordered) + 1))

        for name, frame in list(self.events.items()):
            if frame.empty:
                continue
            working = frame.copy()
            if "total_rounds_played" in working.columns:
                raw = pd.to_numeric(
                    working["total_rounds_played"], errors="coerce"
                )
                offset = -1 if name == "round_end" else 0
                working["round"] = raw.map(
                    lambda value: self.round_map.get(
                        int(round(float(value))) + offset
                    )
                    if pd.notna(value)
                    else None
                )
            else:
                working["round"] = None
            working = working[working["round"].notna()].copy()
            if not working.empty:
                working["round"] = working["round"].astype(int)
            self.events[name] = working.reset_index(drop=True)

    def _fill_rounds_by_tick(self, frame: pd.DataFrame) -> None:
        if "tick" not in frame.columns or self._start_ticks.empty:
            return
        needed = frame["round"].isna()
        if not needed.any():
            return
        left = frame.loc[needed, ["tick"]].copy()
        left["_index"] = left.index
        left = left.dropna(subset=["tick"]).sort_values("tick")
        right = self._start_ticks.dropna(subset=["tick"]).sort_values("tick")
        if left.empty or right.empty:
            return
        merged = pd.merge_asof(left, right, on="tick", direction="backward")
        merged = merged.dropna(subset=["round"])
        if merged.empty:
            return
        frame.loc[merged["_index"].to_numpy(), "round"] = merged["round"].to_numpy()

    def _build_timelines(self) -> None:
        team_frame = self.events.get("player_team", pd.DataFrame())
        timelines: dict[str, list[tuple[float, str]]] = defaultdict(list)
        if not team_frame.empty and "user_id" in team_frame.columns and "side" in team_frame.columns:
            for _, row in team_frame.iterrows():
                sid = _sid(row.get("user_id"))
                side = row.get("side")
                tick = _num(row.get("tick"), -1.0)
                if sid and side and tick >= 0:
                    timelines[sid].append((tick, str(side)))

        for sid, entries in timelines.items():
            entries.sort(key=lambda item: item[0])
            compressed: list[tuple[float, str]] = []
            for tick, side in entries:
                if not compressed or compressed[-1][1] != side:
                    compressed.append((tick, side))
            if compressed:
                self.timelines[sid] = (
                    [item[0] for item in compressed],
                    [item[1] for item in compressed],
                )
                if sid not in self.initial_sides:
                    self.initial_sides[sid] = compressed[0][1]

    def _build_round_info(self) -> None:
        starts = self.events.get("round_start", pd.DataFrame())
        ends = self.events.get("round_end", pd.DataFrame())
        rows: list[dict[str, Any]] = []
        for round_number in self.rounds:
            start_tick = None
            if not starts.empty:
                values = starts.loc[starts["round"] == round_number, "tick"]
                if not values.empty:
                    start_tick = float(values.min())

            end_tick = None
            winner = None
            if not ends.empty:
                round_ends = ends.loc[ends["round"] == round_number].sort_values("tick")
                if not round_ends.empty:
                    end_tick = float(round_ends["tick"].max())
                    if "winner_side" in round_ends.columns:
                        winners = round_ends["winner_side"].dropna()
                        if not winners.empty:
                            winner = str(winners.iloc[-1])
            rows.append(
                {
                    "round": round_number,
                    "start_tick": start_tick,
                    "end_tick": end_tick,
                    "winner": winner,
                }
            )
            if winner:
                self.round_winners[round_number] = winner
        self.round_info = pd.DataFrame(rows)

    def _find_tick_rate(self) -> float:
        for key, value in self.header.items():
            lowered = str(key).lower()
            if "tick" in lowered and ("rate" in lowered or "hz" in lowered):
                rate = _num(value, 0.0)
                if 8.0 <= rate <= 256.0:
                    return rate
        return 64.0

    def side_at(self, sid: str, tick: Any = None) -> str | None:
        if not sid:
            return None
        try:
            if tick is not None and pd.notna(tick):
                ticks, sides = self.timelines.get(sid, ([], []))
                index = bisect.bisect_right(ticks, float(tick)) - 1
                if index >= 0:
                    return sides[index]
        except (TypeError, ValueError):
            pass
        return self.initial_sides.get(sid)

    def is_teammate(self, first: str, second: str, tick: Any = None) -> bool:
        if not first or not second or first == second:
            return False
        first_side = self.side_at(first, tick)
        second_side = self.side_at(second, tick)
        return bool(first_side and second_side and first_side == second_side)

    def is_enemy(self, first: str, second: str, tick: Any = None) -> bool:
        if not first or not second or first == second:
            return False
        first_side = self.side_at(first, tick)
        second_side = self.side_at(second, tick)
        if first_side and second_side:
            return first_side != second_side
        return True

    def match_label(self) -> str:
        lowered = {str(key).lower(): value for key, value in self.header.items()}
        raw = None
        for key in ("map_name", "map", "mapname", "level_name"):
            if lowered.get(key):
                raw = str(lowered[key])
                break
        if not raw:
            return "CS2"
        name = raw.split("/")[-1]
        if name.lower().startswith("de_"):
            name = name[3:]
        return name.replace("_", " ").title()


def _death_records(demo: DemoData) -> list[dict[str, Any]]:
    frame = demo.events.get("player_death", pd.DataFrame())
    records: list[dict[str, Any]] = []
    if frame.empty:
        return records
    for _, row in frame.iterrows():
        round_number = _num(row.get("round"), 0)
        tick = _num(row.get("tick"), -1)
        if round_number <= 0 or tick < 0:
            continue
        records.append(
            {
                "round": int(round_number),
                "tick": tick,
                "attacker": _sid(row.get("attacker_id")),
                "victim": _sid(row.get("victim_id")),
                "assister": _sid(row.get("assister_id")),
                "weapon": _text(row.get("weapon_l")) or "unknown",
                "headshot": _as_bool(row.get("headshot_b")),
                "thrusmoke": _as_bool(row.get("thrusmoke_b")),
                "attackerblind": _as_bool(row.get("attackerblind_b")),
                "penetrated": _as_bool(row.get("penetrated_b")),
            }
        )
    records.sort(key=lambda item: (item["round"], item["tick"]))
    return records


def _played_rounds(demo: DemoData, sid: str) -> list[int]:
    spawns = demo.events.get("player_spawn", pd.DataFrame())
    if not spawns.empty and "user_id" in spawns.columns:
        values = spawns.loc[spawns["user_id"] == sid, "round"].dropna()
        rounds = sorted({int(value) for value in values})
        if rounds:
            return rounds
    return list(demo.rounds)


def _player_options(demo: DemoData) -> list[tuple[str, str]]:
    death_frame = demo.events.get("player_death", pd.DataFrame())
    kill_counts: Counter[str] = Counter()
    if not death_frame.empty and "attacker_id" in death_frame.columns:
        kill_counts.update(_sid(value) for value in death_frame["attacker_id"].tolist())

    ordered = sorted(
        demo.players,
        key=lambda player: (
            -kill_counts.get(player["sid"], 0),
            player["name"].lower(),
            player["sid"],
        ),
    )
    name_counts = Counter(player["name"] for player in ordered)
    seen: Counter[str] = Counter()
    options: list[tuple[str, str]] = []
    for player in ordered:
        name = player["name"]
        if name_counts[name] > 1:
            seen[name] += 1
            name = f"{name} · {seen[name]}"
        options.append((name, player["sid"]))
    return options


_liquipedia_last_request = 0.0


def _clean_wiki_value(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"'''?", "", text)
    return re.sub(r"\s+", " ", text).strip(" |")


def _wiki_field(text: str, field: str) -> str:
    match = re.search(
        rf"(?im)^\|[ \t]*{re.escape(field)}[ \t]*=[ \t]*(.*?)[ \t]*$",
        text,
    )
    return _clean_wiki_value(match.group(1)) if match else ""


def _liquipedia_api(params: dict[str, Any]) -> dict[str, Any]:
    global _liquipedia_last_request
    pause = 2.05 - (time.monotonic() - _liquipedia_last_request)
    if pause > 0:
        time.sleep(pause)
    query = {"action": "query", "format": "json", "formatversion": "2"}
    query.update(params)
    url = f"{LIQUIPEDIA_API}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": LIQUIPEDIA_USER_AGENT,
            "Accept-Encoding": "gzip",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
    finally:
        _liquipedia_last_request = time.monotonic()
    return data


def _liquipedia_pages(titles: list[str]) -> dict[str, Any]:
    clean = [title for title in dict.fromkeys(_text(title) for title in titles) if title]
    if not clean:
        return {}
    data = _liquipedia_api(
        {
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "redirects": "1",
            "titles": "|".join(clean[:50]),
        }
    )
    return data.get("query", {})


def _liquipedia_images(files: list[str]) -> dict[str, str]:
    clean = [file for file in dict.fromkeys(_text(file) for file in files) if file]
    titles = [
        file if file.lower().startswith("file:") else f"File:{file}"
        for file in clean
    ]
    if not titles:
        return {}
    data = _liquipedia_api(
        {
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": "480",
            "titles": "|".join(titles[:50]),
        }
    )
    urls: dict[str, str] = {}
    for page in data.get("query", {}).get("pages", []):
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("thumburl") or info.get("url")
        name = _text(page.get("title"))
        if name.lower().startswith("file:"):
            name = name[5:]
        if url and name:
            urls[name.replace("_", " ").lower()] = url
    return urls


def _country_code(country: str) -> str:
    return COUNTRY_CODES.get(_text(country).lower(), "")


def _flag_url(country: str) -> str:
    code = _country_code(country)
    return f"https://flagcdn.com/w40/{code}.png" if code else ""


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False, max_entries=8)
def _load_liquipedia_metadata(
    player_names: tuple[str, ...],
    server_teams: tuple[str, ...],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "players": {},
        "teams": {},
        "error": "",
    }
    names = tuple(
        name for name in dict.fromkeys(_text(value) for value in player_names) if name
    )
    if not names:
        return result

    players_query = _liquipedia_pages(list(names))

    players: dict[str, dict[str, Any]] = {}
    for page in players_query.get("pages", []):
        if page.get("missing") or not page.get("revisions"):
            continue
        wikitext = (
            page.get("revisions", [{}])[0]
            .get("slots", {})
            .get("main", {})
            .get("content", "")
        )
        if not wikitext:
            continue
        nickname = _wiki_field(wikitext, "id") or _text(page.get("title"))
        key = nickname.lower()
        if not key:
            continue
        players[key] = {
            "nickname": nickname,
            "real_name": _wiki_field(wikitext, "romanized_name")
            or _wiki_field(wikitext, "name"),
            "country": _wiki_field(wikitext, "country"),
            "role": _wiki_field(wikitext, "roles"),
            "image": _wiki_field(wikitext, "image"),
            "team_raw": _wiki_field(wikitext, "team"),
            "team": "",
            "team_key": "",
            "photo_url": "",
        }

    if not players:
        return result

    team_titles = {
        _text(team).lower(): _text(team)
        for team in server_teams
        if _text(team)
    }
    for player in players.values():
        raw_team = player.get("team_raw", "")
        if raw_team:
            team_titles.setdefault(raw_team.lower(), raw_team)

    teams: dict[str, dict[str, Any]] = {}
    redirects: dict[str, str] = {}
    if team_titles:
        try:
            teams_query = _liquipedia_pages(list(team_titles.values()))
        except Exception as error:
            result["error"] = str(error)
            teams_query = {}

        for redirect in teams_query.get("redirects", []):
            source = _text(redirect.get("from")).lower()
            target = _text(redirect.get("to"))
            if source and target:
                redirects[source] = target

        for page in teams_query.get("pages", []):
            if page.get("missing") or not page.get("revisions"):
                continue
            wikitext = (
                page.get("revisions", [{}])[0]
                .get("slots", {})
                .get("main", {})
                .get("content", "")
            )
            if not wikitext:
                continue
            name = _wiki_field(wikitext, "name") or _text(page.get("title"))
            location = (
                _wiki_field(wikitext, "location")
                or _wiki_field(wikitext, "location2")
            )
            teams[name.lower()] = {
                "name": name,
                "location": location,
                "country_code": _country_code(location),
                "logo": _wiki_field(wikitext, "image")
                or _wiki_field(wikitext, "logo"),
                "logo_url": "",
            }
            teams[_text(page.get("title")).lower()] = teams[name.lower()]

    for player in players.values():
        raw_team = player.get("team_raw", "")
        if not raw_team:
            continue
        canonical = redirects.get(raw_team.lower(), raw_team)
        team = teams.get(canonical.lower()) or teams.get(raw_team.lower())
        if team:
            player["team"] = team["name"]
            player["team_key"] = team["name"].lower()
        else:
            player["team"] = raw_team
            player["team_key"] = raw_team.lower()

    files = [
        player["image"] for player in players.values() if player.get("image")
    ] + [team["logo"] for team in teams.values() if team.get("logo")]
    if files:
        try:
            image_urls = _liquipedia_images(files)
        except Exception:
            image_urls = {}
        for player in players.values():
            image = _text(player.get("image"))
            if image:
                player["photo_url"] = image_urls.get(
                    image.replace("_", " ").lower(), ""
                )
        for team in teams.values():
            logo = _text(team.get("logo"))
            if logo:
                team["logo_url"] = image_urls.get(
                    logo.replace("_", " ").lower(), ""
                )

    result["ok"] = True
    result["players"] = players
    result["teams"] = teams
    return result


def _server_teams(server_name: str) -> list[str]:
    text = _text(server_name)
    if "::" in text:
        text = text.rsplit("::", 1)[-1]
    text = re.sub(r"^\s*(?:\[[^\]]*\]\s*)+", "", text)
    parts = re.split(r"\s+(?:vs\.?|versus)\s+", text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return []

    cleaned = []
    for part in parts:
        value = re.split(
            r"\s+[-|]\s+(?:de_|bo\d+|map\s*\d+|m\d+)",
            part,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        value = re.sub(
            r"\b(?:bo\d+|map\s*\d+|m\d+)\b.*$",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = value.strip(" -|:[]")
        if value and len(value) <= 48:
            cleaned.append(value)
    return cleaned if len(cleaned) == 2 else []


def _detect_demo_source(demo: DemoData, file_name: str) -> dict[str, Any]:
    server_name = _text(demo.header.get("server_name"))
    combined = f"{server_name} {file_name}".lower()
    markers = [
        label
        for token, label in ESPORTS_MARKERS.items()
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", combined)
    ]
    teams = _server_teams(server_name)
    is_hltv = "hltv" in combined
    is_esports = is_hltv or bool(teams) or bool(markers)
    if is_hltv:
        label = "HLTV"
    elif is_esports:
        label = "ESPORTS"
    else:
        label = "COMMUNITY"
    return {
        "server_name": server_name,
        "teams": teams,
        "markers": markers,
        "is_hltv": is_hltv,
        "is_esports": is_esports,
        "label": label,
        "marker_label": markers[0] if markers else "",
    }


def _group_teams(
    demo: DemoData,
    metadata: dict[str, Any],
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    assigned: set[str] = set()

    if demo.team_numbers:
        for player in demo.players:
            sid = player["sid"]
            team_key = demo.team_numbers.get(sid)
            if team_key:
                grouped[team_key].append(player)
                assigned.add(sid)

    if len(grouped) == 2:
        for player in demo.players:
            if player["sid"] in assigned:
                continue
            side = demo.initial_sides.get(player["sid"])
            matching = next(
                (
                    key
                    for key, members in grouped.items()
                    if side and demo.initial_sides.get(members[0]["sid"]) == side
                ),
                None,
            )
            target = matching or min(grouped, key=lambda key: len(grouped[key]))
            grouped[target].append(player)

    if len(grouped) != 2:
        grouped = defaultdict(list)
        for player in demo.players:
            side = demo.initial_sides.get(player["sid"]) or "?"
            grouped[side].append(player)
        if len(grouped) > 2:
            unknown = grouped.pop("?", [])
            primary = sorted(grouped, key=lambda key: (-len(grouped[key]), key))[:2]
            grouped = defaultdict(list, {key: grouped[key] for key in primary})
            for player in unknown:
                target = min(grouped, key=lambda key: len(grouped[key]))
                grouped[target].append(player)

    if len(grouped) != 2:
        ordered = sorted(demo.players, key=lambda player: player["name"].lower())
        grouped = defaultdict(list)
        midpoint = max(1, math.ceil(len(ordered) / 2))
        for index, player in enumerate(ordered):
            key = "a" if index < midpoint else "b"
            grouped[key].append(player)

    keys = sorted(grouped)
    if len(keys) < 2:
        return []

    server_team_names = [name for name in source.get("teams", []) if name]
    groups: list[dict[str, Any]] = []
    for index, key in enumerate(keys[:2]):
        members = grouped[key]
        side_counts = Counter(
            demo.initial_sides.get(player["sid"])
            for player in members
            if demo.initial_sides.get(player["sid"])
        )
        side = side_counts.most_common(1)[0][0] if side_counts else ""
        known_teams = Counter(
            metadata.get("players", {})
            .get(player["name"].lower(), {})
            .get("team", "")
            for player in members
        )
        known_teams.pop("", None)
        team_name = known_teams.most_common(1)[0][0] if known_teams else ""
        team_meta = metadata.get("teams", {}).get(team_name.lower(), {})
        if not team_name and server_team_names:
            team_name = server_team_names[index] if index < len(server_team_names) else ""
            team_meta = metadata.get("teams", {}).get(team_name.lower(), {})
        groups.append(
            {
                "key": key,
                "name": team_name or f"Команда {'AB'[index]}",
                "logo_url": team_meta.get("logo_url", ""),
                "location": team_meta.get("location", ""),
                "country_code": team_meta.get("country_code", ""),
                "side": side,
                "players": members,
                "score": 0,
                "identified": bool(team_meta),
            }
        )

    if len(groups) == 2:
        unknown_groups = [group for group in groups if not group["identified"]]
        known_names = {group["name"].lower() for group in groups if group["identified"]}
        remaining = [
            name for name in server_team_names if name.lower() not in known_names
        ]
        if len(unknown_groups) == 1 and len(remaining) == 1:
            unknown_groups[0]["name"] = remaining[0]
            meta = metadata.get("teams", {}).get(remaining[0].lower(), {})
            unknown_groups[0]["logo_url"] = meta.get("logo_url", "")
            unknown_groups[0]["location"] = meta.get("location", "")
            unknown_groups[0]["country_code"] = meta.get("country_code", "")
            unknown_groups[0]["identified"] = bool(meta)

    for group in groups:
        group["score"] = _team_round_score(demo, group["players"])

    return groups


def _team_round_score(demo: DemoData, players: list[dict[str, str]]) -> int:
    score = 0
    if demo.round_info.empty:
        return score
    sids = [player["sid"] for player in players]
    for row in demo.round_info.itertuples(index=False):
        winner = _text(getattr(row, "winner", ""))
        if winner not in {"T", "CT"}:
            continue
        tick = getattr(row, "start_tick", None)
        side = None
        for sid in sids:
            side = demo.side_at(sid, tick)
            if side:
                break
        if side == winner:
            score += 1
    return score


def _traded_deaths(
    deaths_by_round: dict[int, list[dict[str, Any]]],
    demo: DemoData,
    sid: str,
) -> tuple[int, set[int]]:
    count = 0
    rounds: set[int] = set()
    window = demo.tick_rate * TRADE_SECONDS

    for round_number, round_deaths in deaths_by_round.items():
        ordered = sorted(round_deaths, key=lambda item: item["tick"])
        for index, death in enumerate(ordered):
            if death["victim"] != sid:
                continue
            killer = death["attacker"]
            if not killer or killer == sid:
                continue
            if demo.is_teammate(sid, killer, death["tick"]):
                continue
            for follow_up in ordered[index + 1:]:
                if follow_up["tick"] - death["tick"] > window:
                    break
                if (
                    follow_up["victim"] == killer
                    and follow_up["attacker"]
                    and demo.is_teammate(sid, follow_up["attacker"], follow_up["tick"])
                ):
                    count += 1
                    rounds.add(round_number)
                    break
    return count, rounds


def _compute_clutches(
    demo: DemoData,
    sid: str,
    played_set: set[int],
) -> tuple[dict[int, dict[str, int]], dict[str, int]]:
    clutches = {
        1: {"won": 0, "lost": 0},
        2: {"won": 0, "lost": 0},
        3: {"won": 0, "lost": 0},
    }
    other = {"won": 0, "lost": 0}
    all_players = {player["sid"] for player in demo.players}

    spawns = demo.events.get("player_spawn", pd.DataFrame())
    spawned_by_round: dict[int, set[str]] = defaultdict(set)
    if not spawns.empty and "user_id" in spawns.columns:
        for _, row in spawns.iterrows():
            round_number = int(_num(row.get("round"), 0))
            spawned_sid = _sid(row.get("user_id"))
            if round_number > 0 and spawned_sid:
                spawned_by_round[round_number].add(spawned_sid)

    deaths_by_round: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for death in _death_records(demo):
        deaths_by_round[death["round"]].append(death)

    for round_number in sorted(played_set):
        participants = set(spawned_by_round.get(round_number, set()))
        if not participants:
            participants = set(all_players)
        participants.add(sid)
        round_deaths = sorted(
            deaths_by_round.get(round_number, []), key=lambda item: item["tick"]
        )
        for death in round_deaths:
            if death["attacker"]:
                participants.add(death["attacker"])
            if death["victim"]:
                participants.add(death["victim"])

        alive = set(participants)
        tick_groups: list[tuple[float, list[dict[str, Any]]]] = []
        for death in round_deaths:
            if not tick_groups or tick_groups[-1][0] != death["tick"]:
                tick_groups.append((death["tick"], [death]))
            else:
                tick_groups[-1][1].append(death)

        for tick, group in tick_groups:
            for death in group:
                alive.discard(death["victim"])
            if sid not in alive:
                break

            side = demo.side_at(sid, tick)
            if not side:
                continue

            teammates_alive = 0
            enemies_alive = 0
            for participant in participants:
                if participant not in alive:
                    continue
                participant_side = demo.side_at(participant, tick)
                if not participant_side:
                    continue
                if participant_side == side:
                    if participant != sid:
                        teammates_alive += 1
                else:
                    enemies_alive += 1

            if teammates_alive == 0 and enemies_alive > 0:
                winner = demo.round_winners.get(round_number)
                if winner and winner == side:
                    outcome = "won"
                elif winner:
                    outcome = "lost"
                else:
                    outcome = None
                if outcome:
                    if 1 <= enemies_alive <= 3:
                        clutches[enemies_alive][outcome] += 1
                    else:
                        other[outcome] += 1
                break

    return clutches, other


def analyze_player(demo: DemoData, sid: str) -> dict[str, Any]:
    played = _played_rounds(demo, sid)
    played_set = set(played)
    rounds_denominator = max(len(played_set), 1)

    deaths = _death_records(demo)
    deaths_by_round: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for death in deaths:
        deaths_by_round[death["round"]].append(death)

    kills = [
        death
        for death in deaths
        if death["attacker"] == sid
        and death["victim"]
        and death["victim"] != sid
        and not demo.is_teammate(sid, death["victim"], death["tick"])
    ]
    assists = [
        death
        for death in deaths
        if death["assister"] == sid
        and death["victim"]
        and death["victim"] != sid
        and not demo.is_teammate(sid, death["victim"], death["tick"])
    ]
    player_deaths = [death for death in deaths if death["victim"] == sid]

    headshot_kills = sum(1 for death in kills if death["headshot"])
    smoke_kills = sum(1 for death in kills if death["thrusmoke"])
    blind_kills = sum(1 for death in kills if death["attackerblind"])
    wallbangs = sum(1 for death in kills if death["penetrated"])

    traded_count, traded_rounds = _traded_deaths(deaths_by_round, demo, sid)
    kill_rounds = {death["round"] for death in kills}
    assist_rounds = {death["round"] for death in assists}
    death_rounds = {death["round"] for death in player_deaths}
    survived_rounds = played_set - death_rounds
    useful_rounds = (
        kill_rounds | assist_rounds | survived_rounds | traded_rounds
    ) & played_set
    kast = len(useful_rounds) / rounds_denominator * 100.0

    kills_per_round = Counter(death["round"] for death in kills)
    deaths_per_round = Counter(death["round"] for death in player_deaths)
    kd_series: list[dict[str, float]] = []
    cumulative_kills = 0
    cumulative_deaths = 0
    for round_number in demo.rounds:
        cumulative_kills += kills_per_round.get(round_number, 0)
        cumulative_deaths += deaths_per_round.get(round_number, 0)
        kd_series.append(
            {
                "round": round_number,
                "kd": cumulative_kills / max(cumulative_deaths, 1),
            }
        )

    weapon_counts: Counter[str] = Counter(death["weapon"] for death in kills)
    weapon_headshots: Counter[str] = Counter(
        death["weapon"] for death in kills if death["headshot"]
    )
    weapon_stats: list[dict[str, Any]] = []
    for weapon, count in weapon_counts.items():
        headshots = weapon_headshots.get(weapon, 0)
        weapon_stats.append(
            {
                "weapon": weapon,
                "label": _weapon_label(weapon),
                "kills": count,
                "headshots": headshots,
                "hs_pct": headshots / count * 100.0 if count else 0.0,
            }
        )
    weapon_stats.sort(key=lambda item: (-item["kills"], item["label"]))

    multikills = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for count in kills_per_round.values():
        if count > 0:
            multikills[min(count, 5)] += 1

    entry_kills = 0
    entry_deaths = 0
    entry_rounds: list[int] = []
    for round_number in demo.rounds:
        first_duel = None
        for death in deaths_by_round.get(round_number, []):
            if not death["attacker"] or not death["victim"]:
                continue
            if death["attacker"] == death["victim"]:
                continue
            if demo.is_teammate(death["attacker"], death["victim"], death["tick"]):
                continue
            first_duel = death
            break
        if not first_duel:
            continue
        if first_duel["attacker"] == sid:
            entry_kills += 1
            entry_rounds.append(round_number)
        elif first_duel["victim"] == sid:
            entry_deaths += 1
            entry_rounds.append(round_number)

    hurt = demo.events.get("player_hurt", pd.DataFrame())
    total_damage = 0.0
    he_damage = 0.0
    fire_damage = 0.0
    utility_by_round: dict[int, dict[str, float]] = defaultdict(
        lambda: {"he": 0.0, "fire": 0.0}
    )
    if not hurt.empty and "attacker_id" in hurt.columns:
        for _, row in hurt.iterrows():
            if _sid(row.get("attacker_id")) != sid:
                continue
            victim = _sid(row.get("victim_id"))
            if not victim or victim == sid:
                continue
            if demo.is_teammate(sid, victim, row.get("tick")):
                continue
            damage = _num(row.get("damage"), 0.0)
            if damage <= 0:
                continue
            total_damage += damage
            kind = _utility_kind(_text(row.get("weapon_l")))
            if kind:
                round_number = int(_num(row.get("round"), 0))
                if round_number > 0:
                    utility_by_round[round_number][kind] += damage
                if kind == "he":
                    he_damage += damage
                else:
                    fire_damage += damage

    blind = demo.events.get("player_blind", pd.DataFrame())
    enemy_blind_seconds = 0.0
    enemy_blind_events = 0
    team_flash_count = 0
    team_flash_seconds = 0.0
    effective_flash_keys: set[tuple[Any, ...]] = set()
    flash_by_round: dict[int, float] = defaultdict(float)
    flash_throws = 0

    detonations = demo.events.get("flashbang_detonate", pd.DataFrame())
    if not detonations.empty and "user_id" in detonations.columns:
        flash_throws = int((detonations["user_id"] == sid).sum())

    if not blind.empty and "attacker_id" in blind.columns:
        for _, row in blind.iterrows():
            if _sid(row.get("attacker_id")) != sid:
                continue
            victim = _sid(row.get("user_id")) or _sid(row.get("victim_id"))
            if not victim or victim == sid:
                continue
            duration = _num(row.get("blind_duration"), 0.0)
            tick = row.get("tick")
            if demo.is_teammate(sid, victim, tick):
                team_flash_count += 1
                team_flash_seconds += duration
                continue

            enemy_blind_events += 1
            enemy_blind_seconds += duration
            round_number = int(_num(row.get("round"), 0))
            if round_number > 0:
                flash_by_round[round_number] += duration

            if duration > 2.0:
                entity = _text(row.get("entityid"))
                if entity and entity not in {"0", "-1"}:
                    key: tuple[Any, ...] = ("entity", round_number, entity)
                else:
                    key = (
                        "tick",
                        round_number,
                        round(float(tick), 3) if pd.notna(tick) else -1.0,
                        victim,
                    )
                effective_flash_keys.add(key)

    clutches, other_clutches = _compute_clutches(demo, sid, played_set)

    plants = 0
    defuses = 0
    plant_frame = demo.events.get("bomb_planted", pd.DataFrame())
    if not plant_frame.empty and "user_id" in plant_frame.columns:
        plants = int((plant_frame["user_id"] == sid).sum())
    defuse_frame = demo.events.get("bomb_defused", pd.DataFrame())
    if not defuse_frame.empty and "user_id" in defuse_frame.columns:
        defuses = int((defuse_frame["user_id"] == sid).sum())
    explosion_frame = demo.events.get("bomb_exploded", pd.DataFrame())
    explosions = int(len(explosion_frame))

    utility_rows = []
    for round_number in sorted(played_set):
        entry = utility_by_round.get(round_number, {"he": 0.0, "fire": 0.0})
        utility_rows.append(
            {
                "round": round_number,
                "he": entry["he"],
                "fire": entry["fire"],
            }
        )

    flash_rows = [
        {"round": round_number, "seconds": flash_by_round.get(round_number, 0.0)}
        for round_number in sorted(played_set)
    ]

    kills_count = len(kills)
    deaths_count = len(player_deaths)
    kd_ratio = kills_count / deaths_count if deaths_count else float("inf")

    return {
        "sid": sid,
        "name": demo.player_names.get(sid, sid),
        "rounds": len(played_set),
        "kills": kills_count,
        "deaths": deaths_count,
        "assists": len(assists),
        "kd": kd_ratio,
        "adr": total_damage / rounds_denominator,
        "kast": kast,
        "hs_pct": headshot_kills / kills_count * 100.0 if kills_count else 0.0,
        "headshot_kills": headshot_kills,
        "traded": traded_count,
        "smoke_kills": smoke_kills,
        "blind_kills": blind_kills,
        "wallbangs": wallbangs,
        "damage": total_damage,
        "kd_series": kd_series,
        "weapon_stats": weapon_stats,
        "multikills": multikills,
        "entry_kills": entry_kills,
        "entry_deaths": entry_deaths,
        "entry_rounds": entry_rounds,
        "utility_damage": he_damage + fire_damage,
        "he_damage": he_damage,
        "fire_damage": fire_damage,
        "utility_rows": utility_rows,
        "flash_seconds": enemy_blind_seconds,
        "flash_events": enemy_blind_events,
        "effective_flashes": len(effective_flash_keys),
        "team_flashes": team_flash_count,
        "team_flash_seconds": team_flash_seconds,
        "flash_throws": flash_throws,
        "flash_rows": flash_rows,
        "clutches": clutches,
        "other_clutches": other_clutches,
        "plants": plants,
        "defuses": defuses,
        "explosions": explosions,
    }


METRIC_HELP = {
    "K/D Ratio": "Отношение убийств к смертям. 1.00 — игрок умирает ровно столько же, сколько убивает; выше 1.00 — положительный вклад в размен.",
    "ADR": "Average Damage per Round — средний урон, нанесённый за раунд. Учитывается весь урон, а не только добивания.",
    "KAST": "Процент раундов, где игрок сделал килл, отдал ассист, выжил или был разменян. Показывает стабильность участия.",
    "HS%": "Доля убийств в голову от общего числа киллов. Высокий процент важен для винтовок, но не является универсальной оценкой силы.",
    "Киллы": "Все убийства, совершённые игроком за матч.",
    "Смерти": "Сколько раз игрок погиб. В связке с киллами показывает обмен.",
    "Ассисты": "Убийства, в которых игрок помог уроном или ослеплением, но не получил финальный фраг.",
    "Размены": "Смерти игрока, после которых его убийцу быстро забрал тиммейт. Это командная ценность, а не личный фраг.",
    "Через дым": "Киллы через дым без видимости цели. Отдельный показатель агрессивных и нестандартных позиций.",
    "Слепые киллы": "Убийства, совершённые, пока сам игрок был ослеплён.",
    "Прострелы": "Киллы через укрытие или стену за счёт пробития.",
    "Раунды": "Сколько раундов игрок реально отыграл в демке.",
    "Entry Kills": "Первый килл раунда, открывший команде численное преимущество.",
    "Entry Deaths": "Первая смерть раунда. Показывает, как часто игрок проигрывает стартовую дуэль.",
    "Entry Success": "Доля выигранных первых дуэлей: Entry Kills / (Entry Kills + Entry Deaths).",
    "Opening Duels": "Сумма первых дуэлей раунда, в которых игрок участвовал.",
    "Utility Damage": "Урон от HE-гранат и зажигательных гранат.",
    "Flash Blind": "Суммарное время, на которое враги были ослеплены флешками игрока.",
    "Effective Flashes": "Флешки, которые ослепили врага дольше двух секунд.",
    "Team Flashes": "Сколько раз игрок ослепил своих тиммейтов. Чем меньше, тем чище утилита.",
    "HE Damage": "Урон только от осколочных гранат.",
    "Fire Damage": "Урон только от молотовых и зажигательных.",
    "Flashbangs": "Количество брошенных флешек.",
    "Enemies Blinded": "Сколько раз враги попали под ослепление игрока.",
    "Avg Blind": "Средняя длительность слепоты одного врага за флешку.",
    "Team Flash Time": "Суммарное время слепоты собственных тиммейтов.",
    "1v1": "Ситуация, когда игрок остался последним живым против одного противника.",
    "1v2": "Клатч-ситуация один против двух.",
    "1v3": "Клатч-ситуация один против трёх.",
    "Clutch Rate": "Доля выигранных клатчей 1v1, 1v2 и 1v3 от всех таких ситуаций.",
    "Пленты": "Сколько раз игрок установил бомбу.",
    "Дифьюзы": "Сколько раз игрок разминировал бомбу.",
    "Взрывы": "Сколько раундов закончилось взрывом бомбы.",
}


def _glossary_html() -> str:
    items = "".join(
        '<div class="glossary-item">'
        f'<div class="glossary-term">{_e(term)}</div>'
        f'<div class="glossary-text">{_e(text)}</div>'
        "</div>"
        for term, text in METRIC_HELP.items()
    )
    return f'<div class="glossary-grid">{items}</div>'


def _metric_card(
    label: str,
    value: str,
    hint: str = "",
    explanation: str = "",
) -> str:
    help_text = explanation or METRIC_HELP.get(label, "")
    help_html = (
        f'<span class="metric-help" tabindex="0" data-tip="{_e(help_text)}" '
        f'aria-label="{_e(label + ": " + help_text)}">?</span>'
        if help_text
        else ""
    )
    return (
        '<div class="metric-card">'
        f'<div class="metric-label-row"><span class="metric-label">{_e(label)}</span>{help_html}</div>'
        f'<div class="metric-value">{_e(value)}</div>'
        f'<div class="metric-hint">{_e(hint) if hint else "&nbsp;"}</div>'
        "</div>"
    )


def _render_metric_grid(cards: list[str], big: bool = False) -> None:
    grid_class = "metric-grid big" if big else "metric-grid small"
    _render_html(f'<div class="{grid_class}">{"".join(cards)}</div>')


def _section(title: str, caption: str = "") -> None:
    caption_html = f'<div class="section-caption">{_e(caption)}</div>' if caption else ""
    _render_html(
        f'<div class="section-head"><div class="section-title">{_e(title)}</div>{caption_html}</div>'
    )


def _empty_panel(text: str) -> None:
    _render_html(f'<div class="empty-panel">{_e(text)}</div>')


def _style_figure(
    figure: go.Figure,
    title: str,
    height: int = 340,
    x_title: str | None = None,
    y_title: str | None = None,
) -> None:
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0, 0, 0, 0.00)",
        plot_bgcolor="rgba(0, 0, 0, 0.00)",
        font={
            "family": '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif',
            "color": "#8A8780",
            "size": 12,
        },
        title={
            "text": title,
            "x": 0.012,
            "xanchor": "left",
            "y": 0.975,
            "yanchor": "top",
            "font": {"size": 15, "color": "#EDEAE3"},
        },
        margin={"l": 12, "r": 16, "t": 48, "b": 12},
        height=height,
        showlegend=False,
        colorway=PALETTE,
        hoverlabel={
            "bgcolor": "#17181A",
            "bordercolor": "rgba(194, 168, 120, 0.19)",
            "font": {"color": "#EDEAE3", "size": 12},
        },
    )
    figure.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor="rgba(255, 255, 255, 0.07)",
        tickfont={"color": "#7D7A74", "size": 11},
        title_font={"color": "#6A6862", "size": 11},
        title_standoff=10,
    )
    figure.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255, 255, 255, 0.04)",
        zeroline=False,
        linecolor="rgba(255, 255, 255, 0.00)",
        tickfont={"color": "#7D7A74", "size": 11},
        title_font={"color": "#6A6862", "size": 11},
        title_standoff=10,
    )
    if x_title:
        figure.update_xaxes(title_text=x_title)
    if y_title:
        figure.update_yaxes(title_text=y_title)


def _render_chart(figure: go.Figure, key: str) -> None:
    st.plotly_chart(
        figure,
        width="stretch",
        config=PLOT_CONFIG,
        key=key,
    )


def _format_seconds(value: float) -> str:
    return f"{value:.1f} с"


def _format_number(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def _render_demo_header(demo: DemoData, file_name: str) -> None:
    _render_html(
        f"""
        <div class="match-strip">
            <div class="match-item">
                <span class="label">Демка</span>
                <span class="value">{_e(file_name)}</span>
            </div>
            <div class="match-item">
                <span class="label">Карта</span>
                <span class="value">{_e(demo.match_label())}</span>
            </div>
            <div class="match-item">
                <span class="label">Раунды</span>
                <span class="value">{len(demo.rounds)}</span>
            </div>
            <div class="match-item">
                <span class="label">Состав</span>
                <span class="value">{len(demo.players)} игроков</span>
            </div>
        </div>
        """
    )


def _kd_text(report: dict[str, Any]) -> str:
    return "∞" if math.isinf(report["kd"]) else f'{report["kd"]:.2f}'


def _avatar_fallback() -> str:
    return """
    <div class="avatar-fallback">
        <svg viewBox="0 0 64 80" fill="none" aria-hidden="true">
            <circle cx="32" cy="27" r="13" fill="currentColor" opacity=".55"/>
            <path d="M12 76c0-13 9-23 20-23s20 10 20 23" fill="currentColor" opacity=".38"/>
            <path d="M14 30a18 18 0 0 1 36 0" stroke="currentColor" stroke-width="4" stroke-linecap="round" opacity=".8"/>
            <rect x="9" y="27" width="7" height="18" rx="3.5" fill="currentColor" opacity=".75"/>
            <rect x="48" y="27" width="7" height="18" rx="3.5" fill="currentColor" opacity=".75"/>
        </svg>
    </div>
    """


def _monogram(name: str) -> str:
    letters = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]", "", _text(name))
    return (letters[:2] or "CS").upper()


def _role_text(role: str) -> str:
    labels = {
        "rifle": "RIFLER",
        "rifler": "RIFLER",
        "awp": "AWPER",
        "igl": "IGL",
        "support": "SUPPORT",
        "entry": "ENTRY",
        "lurker": "LURKER",
        "coach": "COACH",
        "analyst": "ANALYST",
    }
    parts = [
        labels.get(part.strip().lower(), part.strip().upper())
        for part in re.split(r"[,/]", _text(role))
        if part.strip()
    ]
    return " · ".join(parts[:2])


def _team_logo_html(name: str, logo_url: str, wrapper_class: str, logo_class: str) -> str:
    monogram = (
        f'<span class="team-monogram" style="display:none">{_e(_monogram(name))}</span>'
        if logo_url
        else f'<span class="team-monogram">{_e(_monogram(name))}</span>'
    )
    image = (
        f'<img class="{logo_class}" src="{_e(logo_url)}" alt="{_e(name)}" '
        'loading="lazy" referrerpolicy="no-referrer" '
        'onerror="this.style.display=\'none\';this.previousElementSibling.style.display=\'flex\'">'
        if logo_url
        else ""
    )
    return f'<div class="{wrapper_class}">{monogram}{image}</div>'


def _player_card_html(
    player: dict[str, str],
    report: dict[str, Any],
    meta: dict[str, Any],
    selected: bool,
) -> str:
    name = _text(player.get("name"))
    photo = _text(meta.get("photo_url"))
    real_name = _text(meta.get("real_name")) or "Локальный профиль"
    country = _text(meta.get("country"))
    role = _role_text(_text(meta.get("role")))
    flag = _flag_url(country)
    kd = _kd_text(report)
    selected_class = " selected" if selected else ""
    photo_html = (
        f'<img src="{_e(photo)}" alt="{_e(name)}" loading="lazy" '
        'referrerpolicy="no-referrer" onerror="this.remove()">'
        if photo
        else ""
    )
    flag_html = (
        f'<img class="player-flag" src="{_e(flag)}" alt="{_e(country)}" '
        f'title="{_e(country)}" loading="lazy" onerror="this.remove()">'
        if flag
        else ""
    )
    role_html = f'<span class="role-pill">{_e(role)}</span>' if role else ""
    local_tag = (
        '<span class="player-local-tag">local</span>' if not photo else ""
    )
    return f"""
    <div class="player-card{selected_class}">
        <div class="player-avatar">
            {_avatar_fallback()}
            {photo_html}
        </div>
        <div class="player-body">
            <div class="player-top">
                <span class="player-nick">{_e(name)}</span>
                {flag_html}
            </div>
            <div class="player-real">{_e(real_name)}</div>
            <div class="player-badges">{role_html}{local_tag}</div>
        </div>
        <div class="player-stats">
            <div class="player-stat" title="K/D — отношение убийств к смертям">
                <div class="player-stat-value">{_e(kd)}</div>
                <div class="player-stat-label">K/D</div>
            </div>
            <div class="player-stat" title="ADR — средний урон за раунд">
                <div class="player-stat-value">{report["adr"]:.0f}</div>
                <div class="player-stat-label">ADR</div>
            </div>
            <div class="player-stat" title="KAST — доля раундов с киллом, ассистом, выживанием или разменом">
                <div class="player-stat-value">{report["kast"]:.0f}%</div>
                <div class="player-stat-label">KAST</div>
            </div>
        </div>
    </div>
    """


def _team_panel_html(
    group: dict[str, Any],
    reports: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
    selected_sid: str,
) -> str:
    players = group.get("players", [])
    cards = []
    for player in players:
        report = reports.get(player["sid"])
        if not report:
            continue
        meta = metadata.get("players", {}).get(player["name"].lower(), {})
        cards.append(
            _player_card_html(
                player,
                report,
                meta,
                player["sid"] == selected_sid,
            )
        )
    location = _text(group.get("location"))
    location_flag = _flag_url(location)
    location_html = (
        f'<div class="team-location">'
        f'<img class="player-flag" src="{_e(location_flag)}" alt="{_e(location)}" loading="lazy" onerror="this.remove()">'
        f"<span>{_e(location)}</span></div>"
        if location_flag
        else ""
    )
    side = _text(group.get("side"))
    side_html = (
        f'<span class="team-start-side" title="Сторона команды на старте матча: T или CT">'
        f"СТАРТ {_e(side)}</span>"
        if side
        else ""
    )
    identified = "ЛОКАЛЬНЫЙ СОСТАВ" if not group.get("identified") else "СОСТАВ"
    logo = _team_logo_html(
        _text(group.get("name")),
        _text(group.get("logo_url")),
        "team-logo-wrap",
        "team-logo",
    )
    return f"""
    <div class="team-panel">
        <div class="team-panel-head">
            {logo}
            <div class="team-copy">
                <div class="team-name">{_e(_text(group.get("name")))}</div>
                {location_html}
            </div>
            <div class="team-score-wrap">
                <div class="team-score" title="Счёт по завершённым раундам. Раунды без победителя не учитываются.">{int(group.get("score", 0))}</div>
                {side_html}
            </div>
        </div>
        <div class="roster-list">{"".join(cards)}</div>
        <div class="team-location" style="margin-top:0.65rem;justify-content:flex-end">{_e(identified)} · {len(players)} ИГРОКОВ</div>
    </div>
    """


def _render_match_banner(
    demo: DemoData,
    file_name: str,
    source: dict[str, Any],
    groups: list[dict[str, Any]],
) -> None:
    if len(groups) < 2:
        return
    left, right = groups[0], groups[1]
    mode = (
        "HLTV DEMO"
        if source["is_hltv"]
        else "PRO DEMO"
        if source["is_esports"]
        else "COMMUNITY DEMO"
    )
    mode_class = (
        "hltv"
        if source["is_hltv"]
        else "esports"
        if source["is_esports"]
        else "community"
    )
    server = _text(source.get("server_name")) or "локальный сервер"
    marker = _text(source.get("marker_label")) or "local"
    left_logo = _team_logo_html(
        _text(left.get("name")),
        _text(left.get("logo_url")),
        "banner-logo-wrap",
        "banner-logo",
    )
    right_logo = _team_logo_html(
        _text(right.get("name")),
        _text(right.get("logo_url")),
        "banner-logo-wrap",
        "banner-logo",
    )
    _render_html(
        f"""
        <div class="match-banner">
            <div class="match-banner-top">
                <div class="source-pill {mode_class}">{_e(mode)}</div>
                <div class="match-file" title="{_e(file_name)}">{_e(file_name)}</div>
            </div>
            <div class="match-scoreline">
                <div class="banner-team">
                    {left_logo}
                    <div class="banner-copy">
                        <div class="banner-name">{_e(_text(left.get("name")))}</div>
                        <div class="banner-sub">{_e(_text(left.get("location")) or "локальный состав")}</div>
                    </div>
                </div>
                <div class="banner-score" title="Счёт по завершённым раундам. Раунды без победителя не учитываются.">{int(left.get("score", 0))}<span>:</span>{int(right.get("score", 0))}</div>
                <div class="banner-team right">
                    {right_logo}
                    <div class="banner-copy">
                        <div class="banner-name">{_e(_text(right.get("name")))}</div>
                        <div class="banner-sub">{_e(_text(right.get("location")) or "локальный состав")}</div>
                    </div>
                </div>
            </div>
            <div class="match-facts">
                <span class="match-fact">Карта <strong>{_e(demo.match_label())}</strong></span>
                <span class="match-fact">Раунды <strong>{len(demo.rounds)}</strong></span>
                <span class="match-fact">Сервер <strong>{_e(server)}</strong></span>
                <span class="match-fact">Формат <strong>{_e(marker)}</strong></span>
            </div>
        </div>
        """
    )


def _source_note(source: dict[str, Any], metadata: dict[str, Any], total_players: int) -> str:
    found = len(metadata.get("players", {}))
    if source["is_esports"]:
        detection = (
            "HLTV-метка найдена в сервере или имени файла."
            if source["is_hltv"]
            else "HLTV-метка не найдена, но обнаружен турнирный сервер."
        )
        if metadata.get("ok") and found:
            profiles = (
                f"Профили Liquipedia: <strong>{found} из {total_players}</strong>. "
                "Фото, логотипы и флаги подставлены там, где они доступны."
            )
        else:
            profiles = (
                "Профили Liquipedia не загрузились: показываем силуэты и локальные данные."
            )
        return (
            f"<strong>Проверка демки: киберспорт.</strong> {detection} "
            f"{profiles} HLTV ID внутри .dem не хранится, поэтому статус определяется "
            "по турнирному серверу и составам."
        )
    return (
        "<strong>Проверка демки: обычный матч.</strong> Турнирный сервер и профили "
        "Liquipedia не найдены. Карточки остаются, но вместо фото показываются "
        "силуэты игроков в наушниках."
    )


def _team_snapshot(group: dict[str, Any], reports: dict[str, dict[str, Any]]) -> dict[str, float]:
    values = [
        reports[player["sid"]]
        for player in group.get("players", [])
        if player["sid"] in reports
    ]
    if not values:
        return {
            "adr": 0.0,
            "kast": 0.0,
            "hs": 0.0,
            "entry": 0.0,
            "utility": 0.0,
            "clutches": 0.0,
        }
    entry_kills = sum(item["entry_kills"] for item in values)
    entry_deaths = sum(item["entry_deaths"] for item in values)
    entry_attempts = entry_kills + entry_deaths
    return {
        "adr": sum(item["adr"] for item in values) / len(values),
        "kast": sum(item["kast"] for item in values) / len(values),
        "hs": sum(item["hs_pct"] for item in values) / len(values),
        "entry": entry_kills / entry_attempts * 100.0 if entry_attempts else 0.0,
        "utility": sum(item["utility_damage"] for item in values),
        "clutches": sum(
            item["clutches"][size]["won"] for item in values for size in (1, 2, 3)
        ),
    }


def _compare_html(groups: list[dict[str, Any]], reports: dict[str, dict[str, Any]]) -> str:
    if len(groups) < 2:
        return ""
    left = _team_snapshot(groups[0], reports)
    right = _team_snapshot(groups[1], reports)
    rows = [
        ("Средний ADR", left["adr"], right["adr"], "{:.1f}", "Средний урон за раунд"),
        ("Средний KAST", left["kast"], right["kast"], "{:.0f}%", "Стабильность участия в раундах"),
        ("Средний HS%", left["hs"], right["hs"], "{:.0f}%", "Доля убийств в голову"),
        ("Успех в первых дуэлях", left["entry"], right["entry"], "{:.0f}%", "Выигранные первые дуэли"),
        ("Урон гранатами", left["utility"], right["utility"], "{:.0f}", "Суммарный урон гранатами"),
        ("Клатчи", left["clutches"], right["clutches"], "{:.0f}", "Выигранные ситуации 1vX"),
    ]
    html_rows = []
    for label, left_value, right_value, fmt, hint in rows:
        total = max(left_value + right_value, 0.001)
        left_pct = left_value / total * 100.0
        right_pct = 100.0 - left_pct
        html_rows.append(
            f"""
            <div class="compare-row" title="{_e(hint)}">
                <div class="compare-head">
                    <span class="compare-value">{_e(fmt.format(left_value))}</span>
                    <span class="compare-label">{_e(label)}</span>
                    <span class="compare-value right">{_e(fmt.format(right_value))}</span>
                </div>
                <div class="compare-track">
                    <span class="compare-left" style="width:{left_pct:.1f}%"></span>
                    <span class="compare-right" style="width:{right_pct:.1f}%"></span>
                </div>
            </div>
            """
        )
    return f'<div class="compare-card"><div class="compare-list">{"".join(html_rows)}</div></div>'


def _general_tab(
    demo: DemoData,
    file_name: str,
    source: dict[str, Any],
    groups: list[dict[str, Any]],
    metadata: dict[str, Any],
    reports: dict[str, dict[str, Any]],
    selected_sid: str,
) -> None:
    _render_match_banner(demo, file_name, source, groups)
    _render_html(
        f'<div class="source-note">{_source_note(source, metadata, len(demo.players))}</div>'
    )

    _section(
        "Составы",
        "Две команды из демки. Выбранный игрок подсвечен. Состав и счёт берутся из демки; "
        "клубы, фото и флаги — актуальные профили Liquipedia.",
    )
    if len(groups) >= 2:
        panels = "".join(
            _team_panel_html(group, reports, metadata, selected_sid)
            for group in groups[:2]
        )
        _render_html(f'<div class="teams-grid">{panels}</div>')
    else:
        _empty_panel("Не удалось разделить игроков на две команды.")

    _section(
        "Сравнение команд",
        "Средние и суммарные показатели составов по завершённым раундам.",
    )
    _render_html(_compare_html(groups, reports))

    _section(
        "Расшифровка",
        "Наведите на знак «?» у любого показателя или откройте полный глоссарий.",
    )
    with st.expander("Все показатели и определения", expanded=False):
        _render_html(_glossary_html())


def _overview_tab(report: dict[str, Any]) -> None:
    kd_value = _kd_text(report)
    _render_metric_grid(
        [
            _metric_card(
                "K/D Ratio",
                kd_value,
                f'{report["kills"]} K · {report["deaths"]} D',
            ),
            _metric_card(
                "ADR",
                f'{report["adr"]:.1f}',
                f'{report["rounds"]} сыгранных раундов',
            ),
            _metric_card(
                "KAST",
                f'{report["kast"]:.0f}%',
                "Kill · Assist · Survive · Trade",
            ),
            _metric_card(
                "HS%",
                f'{report["hs_pct"]:.0f}%',
                f'{report["headshot_kills"]} из {report["kills"]} киллов',
            ),
        ],
        big=True,
    )

    _section("Детализация", "Полный срез по каждому действию выбранного игрока.")
    _render_metric_grid(
        [
            _metric_card("Киллы", _format_number(report["kills"]), "всего убийств"),
            _metric_card("Смерти", _format_number(report["deaths"]), "всего смертей"),
            _metric_card("Ассисты", _format_number(report["assists"]), "помощь в убийствах"),
            _metric_card("Размены", _format_number(report["traded"]), "смерти, которые отомстили"),
            _metric_card("Через дым", _format_number(report["smoke_kills"]), "smoke kills"),
            _metric_card("Слепые киллы", _format_number(report["blind_kills"]), "kills while blinded"),
            _metric_card("Прострелы", _format_number(report["wallbangs"]), "wallbang kills"),
            _metric_card("Раунды", _format_number(report["rounds"]), "сыграно в матче"),
        ]
    )


def _combat_tab(report: dict[str, Any], demo: DemoData) -> None:
    _section(
        "Динамика K/D",
        "Как менялась эффективность игрока от первого раунда к последнему.",
    )
    with st.container(border=True):
        series = report["kd_series"]
        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=[item["round"] for item in series],
                y=[item["kd"] for item in series],
                mode="lines+markers",
                name="K/D",
                line={
                    "color": PALETTE[0],
                    "width": 2.4,
                    "shape": "spline",
                    "smoothing": 0.9,
                },
                marker={
                    "size": 4.5,
                    "color": "rgba(237, 234, 227, 0.74)",
                    "line": {"color": PALETTE[0], "width": 1.2},
                },
                hovertemplate="Раунд %{x}<br>K/D %{y:.2f}<extra></extra>",
            )
        )
        figure.add_hline(
            y=1.0,
            line_dash="dot",
            line_color="rgba(255, 255, 255, 0.11)",
            annotation_text="1.00",
            annotation_position="bottom right",
            annotation_font={"color": "#7D7A74", "size": 10},
        )
        _style_figure(
            figure,
            "K/D по раундам",
            height=352,
            x_title="Раунд",
            y_title="K/D",
        )
        _render_chart(figure, f'kd_{report["sid"]}')

    left, right = st.columns(2, gap="medium")
    with left:
        _section("Оружие", "Киллы и доля хедшотов по каждому стволу.")
        with st.container(border=True):
            weapon_stats = report["weapon_stats"]
            if not weapon_stats:
                _empty_panel("У игрока пока нет киллов в этой демке.")
            else:
                frame = pd.DataFrame(weapon_stats)
                frame = frame.sort_values("kills", ascending=True)
                height = max(300, min(560, 72 + len(frame) * 28))
                figure = go.Figure(
                    go.Bar(
                        x=frame["kills"],
                        y=frame["label"],
                        orientation="h",
                        marker={
                            "color": frame["kills"],
                            "colorscale": [
                                [0.0, "#3A3428"],
                                [0.5, "#9C8258"],
                                [1.0, "#8FA2A6"],
                            ],
                            "showscale": False,
                            "line": {"color": "rgba(217, 201, 168, 0.09)", "width": 1},
                        },
                        text=[
                            f"{int(kills)} · {hs:.0f}% HS"
                            for kills, hs in zip(frame["kills"], frame["hs_pct"])
                        ],
                        textposition="outside",
                        cliponaxis=False,
                        customdata=frame[["hs_pct", "headshots"]].to_numpy(),
                        hovertemplate=(
                            "%{y}<br>%{x} киллов<br>"
                            "%{customdata[0]:.0f}% HS · %{customdata[1]} хедшотов"
                            "<extra></extra>"
                        ),
                        textfont={"color": "#B8B3A8", "size": 10.5},
                    )
                )
                _style_figure(
                    figure,
                    "Киллы по оружию",
                    height=height,
                    x_title="Киллы",
                )
                figure.update_layout(
                    margin={"l": 118, "r": 70, "t": 48, "b": 12},
                    bargap=0.42,
                )
                figure.update_xaxes(
                    showgrid=True,
                    gridcolor="rgba(255, 255, 255, 0.04)",
                    range=[0, max(frame["kills"].max() + 2, 3)],
                )
                _render_chart(figure, f'weapons_{report["sid"]}')

    with right:
        _section("Мультифраги", "Раунды с одним, двумя, тремя, четырьмя и пятью киллами.")
        with st.container(border=True):
            labels = ["1K", "2K", "3K", "4K", "ACE"]
            values = [report["multikills"][index] for index in range(1, 6)]
            colors = [PALETTE[0], PALETTE[5], PALETTE[1], PALETTE[2], PALETTE[3]]
            figure = go.Figure(
                go.Bar(
                    x=labels,
                    y=values,
                    marker={
                        "color": colors,
                        "line": {"color": "rgba(217, 201, 168, 0.10)", "width": 1},
                    },
                    text=values,
                    textposition="outside",
                    cliponaxis=False,
                    textfont={"color": "#CFCBC1", "size": 11},
                    hovertemplate="%{x}<br>%{y} раундов<extra></extra>",
                )
            )
            _style_figure(
                figure,
                "Раунды по числу фрагов",
                height=340,
                x_title="Фраги в раунде",
                y_title="Раунды",
            )
            figure.update_layout(bargap=0.48)
            figure.update_yaxes(
                rangemode="tozero",
                range=[0, max(max(values) + 1, 2)],
            )
            _render_chart(figure, f'multi_{report["sid"]}')

    _section("Дуэли", "Первые дуэли в раунде: opening kills и opening deaths.")
    entry_attempts = report["entry_kills"] + report["entry_deaths"]
    entry_success = (
        report["entry_kills"] / entry_attempts * 100.0 if entry_attempts else 0.0
    )
    _render_metric_grid(
        [
            _metric_card("Entry Kills", _format_number(report["entry_kills"]), "первые киллы в раунде"),
            _metric_card("Entry Deaths", _format_number(report["entry_deaths"]), "первые смерти в раунде"),
            _metric_card("Entry Success", f"{entry_success:.0f}%", "доля выигранных opening duels"),
            _metric_card("Opening Duels", _format_number(entry_attempts), "всего первых дуэлей"),
        ]
    )

def _utility_tab(report: dict[str, Any]) -> None:
    _render_metric_grid(
        [
            _metric_card(
                "Utility Damage",
                _format_number(report["utility_damage"]),
                "урон от HE и огня",
            ),
            _metric_card(
                "Flash Blind",
                _format_seconds(report["flash_seconds"]),
                "суммарная слепота врагов",
            ),
            _metric_card(
                "Effective Flashes",
                _format_number(report["effective_flashes"]),
                "слепота врага > 2 сек",
            ),
            _metric_card(
                "Team Flashes",
                _format_number(report["team_flashes"]),
                "ослеплённые тиммейты",
            ),
        ],
        big=True,
    )

    _section("Детализация утилиты", "Гранаты, ослепление и командный урон.")
    _render_metric_grid(
        [
            _metric_card("HE Damage", _format_number(report["he_damage"]), "урон от HE"),
            _metric_card("Fire Damage", _format_number(report["fire_damage"]), "урон от огня"),
            _metric_card("Flashbangs", _format_number(report["flash_throws"]), "брошено флешек"),
            _metric_card("Enemies Blinded", _format_number(report["flash_events"]), "ослеплённых врагов"),
            _metric_card(
                "Avg Blind",
                _format_seconds(
                    report["flash_seconds"] / report["flash_events"]
                    if report["flash_events"]
                    else 0.0
                ),
                "средняя слепота врага",
            ),
            _metric_card(
                "Team Flash Time",
                _format_seconds(report["team_flash_seconds"]),
                "суммарное время по тиммейтам",
            ),
        ]
    )

    if any(item["he"] or item["fire"] for item in report["utility_rows"]):
        left, right = st.columns(2, gap="medium")
        with left:
            _section("Урон по раундам", "HE и огонь в каждом раунде.")
            with st.container(border=True):
                frame = pd.DataFrame(report["utility_rows"])
                figure = go.Figure()
                figure.add_trace(
                    go.Bar(
                        x=frame["round"],
                        y=frame["he"],
                        name="HE",
                        marker_color=PALETTE[2],
                        hovertemplate="Раунд %{x}<br>HE: %{y:.0f}<extra></extra>",
                    )
                )
                figure.add_trace(
                    go.Bar(
                        x=frame["round"],
                        y=frame["fire"],
                        name="Fire",
                        marker_color=PALETTE[3],
                        hovertemplate="Раунд %{x}<br>Огонь: %{y:.0f}<extra></extra>",
                    )
                )
                _style_figure(
                    figure,
                    "Урон гранатами по раундам",
                    height=320,
                    x_title="Раунд",
                    y_title="Урон",
                )
                figure.update_layout(barmode="stack", bargap=0.42, showlegend=True)
                figure.update_layout(
                    legend={
                        "orientation": "h",
                        "yanchor": "bottom",
                        "y": 1.02,
                        "xanchor": "right",
                        "x": 1,
                        "font": {"color": "#8A8780", "size": 10},
                    }
                )
                figure.update_yaxes(rangemode="tozero")
                _render_chart(figure, f'utility_dmg_{report["sid"]}')
        with right:
            _section("Слепота по раундам", "Сколько секунд игрок держал врагов без зрения.")
            with st.container(border=True):
                frame = pd.DataFrame(report["flash_rows"])
                figure = go.Figure(
                    go.Scatter(
                        x=frame["round"],
                        y=frame["seconds"],
                        mode="lines+markers",
                        line={
                            "color": PALETTE[4],
                            "width": 2.2,
                            "shape": "spline",
                            "smoothing": 0.85,
                        },
                        marker={"size": 4, "color": PALETTE[4]},
                        hovertemplate="Раунд %{x}<br>%{y:.1f} сек<extra></extra>",
                    )
                )
                _style_figure(
                    figure,
                    "Слепота врагов по раундам",
                    height=320,
                    x_title="Раунд",
                    y_title="Секунды",
                )
                figure.update_yaxes(rangemode="tozero")
                _render_chart(figure, f'flash_time_{report["sid"]}')
    else:
        _empty_panel("В этой демке не найдено урона от гранат или ослеплений.")


def _clutches_tab(report: dict[str, Any]) -> None:
    clutch_cards = []
    for size in (1, 2, 3):
        won = report["clutches"][size]["won"]
        lost = report["clutches"][size]["lost"]
        attempts = won + lost
        rate = won / attempts * 100.0 if attempts else 0.0
        clutch_cards.append(
            _metric_card(
                f"1v{size}",
                f"{won} / {lost}",
                f"{rate:.0f}% — выиграно / попыток",
            )
        )

    total_won = sum(report["clutches"][size]["won"] for size in (1, 2, 3))
    total_lost = sum(report["clutches"][size]["lost"] for size in (1, 2, 3))
    total_attempts = total_won + total_lost
    total_rate = total_won / total_attempts * 100.0 if total_attempts else 0.0
    clutch_cards.append(
        _metric_card(
            "Clutch Rate",
            f"{total_rate:.0f}%",
            f"{total_won}W · {total_lost}L",
        )
    )
    _render_metric_grid(clutch_cards, big=True)

    left, right = st.columns(2, gap="medium")
    with left:
        _section(
            "1vX",
            "Ситуация фиксируется, когда игрок остаётся последним живым на стороне.",
        )
        with st.container(border=True):
            labels = ["1v1", "1v2", "1v3"]
            wins = [report["clutches"][size]["won"] for size in (1, 2, 3)]
            losses = [report["clutches"][size]["lost"] for size in (1, 2, 3)]
            figure = go.Figure()
            figure.add_trace(
                go.Bar(
                    x=labels,
                    y=wins,
                    name="Победы",
                    marker_color=PALETTE[2],
                    text=wins,
                    textposition="outside",
                    cliponaxis=False,
                    textfont={"color": "#CFCBC1", "size": 10.5},
                    hovertemplate="%{x}<br>Победы: %{y}<extra></extra>",
                )
            )
            figure.add_trace(
                go.Bar(
                    x=labels,
                    y=losses,
                    name="Поражения",
                    marker_color=PALETTE[4],
                    text=losses,
                    textposition="outside",
                    cliponaxis=False,
                    textfont={"color": "#CFCBC1", "size": 10.5},
                    hovertemplate="%{x}<br>Поражения: %{y}<extra></extra>",
                )
            )
            _style_figure(
                figure,
                "Клатчи 1v1 / 1v2 / 1v3",
                height=320,
                x_title="Ситуация",
                y_title="Раунды",
            )
            figure.update_layout(
                barmode="group",
                bargap=0.45,
                bargroupgap=0.12,
                showlegend=True,
            )
            figure.update_layout(
                legend={
                    "orientation": "h",
                    "yanchor": "bottom",
                    "y": 1.02,
                    "xanchor": "right",
                    "x": 1,
                    "font": {"color": "#8A8780", "size": 10},
                }
            )
            figure.update_yaxes(
                rangemode="tozero",
                range=[0, max(max(wins), max(losses), 1) + 1],
            )
            _render_chart(figure, f'clutch_chart_{report["sid"]}')

    with right:
        _section("Бомба", "Пленты и дифьюзы игрока, а также взрывы в матче.")
        with st.container(border=True):
            _render_metric_grid(
                [
                    _metric_card("Пленты", _format_number(report["plants"]), "установки C4"),
                    _metric_card("Дифьюзы", _format_number(report["defuses"]), "разминирования"),
                    _metric_card("Взрывы", _format_number(report["explosions"]), "взрывы бомбы"),
                ]
            )


def _ai_tab(
    report: dict[str, Any],
    demo: DemoData,
    groups: list[dict[str, Any]],
    sid: str,
    cache_key: str,
) -> None:
    player_name = _text(report.get("name"))
    map_name = demo.match_label()
    local = advisor.build_local_plan(report, demo, groups, sid, map_name)

    _section(
        "AI-тренер",
        "Локальный разбор статистики и план тренировок. Для дополнительного текстового "
        "разбора можно подключить локальную модель или OpenAI-совместимый API.",
    )
    _render_html(
        f"""
        <div class="ai-summary">
            <div class="ai-summary-label">Главный вывод</div>
            <div class="ai-summary-text">{_e(local["summary"])}</div>
        </div>
        """
    )

    strengths_html = "".join(
        f'<div class="ai-item"><div class="ai-item-text">{_e(item)}</div></div>'
        for item in local["strengths"]
    )
    weaknesses_html = "".join(
        f"""
        <div class="ai-item">
            <div class="ai-item-title">{_e(item["title"])}</div>
            <div class="ai-item-text">{_e(item["detail"])}</div>
            <div class="ai-tag">{_e(item["target"])}</div>
            <div class="ai-item-text">{_e(item["drill"])}</div>
        </div>
        """
        for item in local["weaknesses"]
    ) or '<div class="ai-item"><div class="ai-item-text">Явных провалов нет. Работай над стабильностью и усложняй тренировки.</div></div>'
    _render_html(
        f"""
        <div class="ai-columns">
            <div class="ai-panel">
                <div class="ai-panel-title">Сильные стороны</div>
                <div class="ai-list">{strengths_html}</div>
            </div>
            <div class="ai-panel">
                <div class="ai-panel-title">Что подкачать</div>
                <div class="ai-list">{weaknesses_html}</div>
            </div>
        </div>
        """
    )

    map_html = "".join(
        f"""
        <div class="ai-map">
            <div class="ai-map-name">{_e(item["name"])}{" · текущая" if item.get("current") else ""}</div>
            <div class="ai-map-why">{_e(item["why"])}</div>
            <ul class="ai-map-drills">
                {''.join(f'<li>{_e(drill)}</li>' for drill in item["drills"])}
            </ul>
        </div>
        """
        for item in local["maps"]
    )
    _section("Карты для тренировки", "Приоритет зависит от слабых метрик в этом матче.")
    _render_html(f'<div class="ai-maps">{map_html}</div>')

    week_html = "".join(
        f"""
        <div class="ai-day">
            <div class="ai-day-head">
                <div class="ai-day-title">{_e(item["day"])}</div>
                <div class="ai-day-meta">{_e(item["title"])} · {item["minutes"]} мин</div>
            </div>
            <ul class="ai-tasks">
                {''.join(f'<li>{_e(task)}</li>' for task in item["tasks"])}
            </ul>
        </div>
        """
        for item in local["week"]
    )
    _section("План на неделю", "Пять коротких сессий: аим, утилита, дуэли, карта и разбор.")
    _render_html(f'<div class="ai-week">{week_html}</div>')

    _section("Генеративный разбор", "Необязательно: локальный план уже готов. AI добавит текстовый разбор.")
    with st.expander("Подключить AI-модель", expanded=False):
        provider = st.selectbox(
            "AI-движок",
            list(advisor.AI_PRESETS),
            index=0,
            key=f"ai_provider_{cache_key}",
        )
        preset = advisor.AI_PRESETS[provider]
        if provider == "Локальный анализ":
            st.caption(
                "Используется встроенный аналитический движок. Демка и статистика "
                "никуда не отправляются."
            )
        else:
            base_url = st.text_input(
                "Base URL",
                value=str(preset.get("base_url") or ""),
                key=f"ai_base_{cache_key}_{provider}",
                help="Например: http://127.0.0.1:11434/v1 или https://api.openai.com/v1",
            )
            model = st.text_input(
                "Модель",
                value=str(preset.get("model") or ""),
                key=f"ai_model_{cache_key}_{provider}",
                help="Точное имя модели в выбранном API.",
            )
            api_key = st.text_input(
                "API-ключ",
                type="password",
                key=f"ai_key_{cache_key}_{provider}",
                help="Ключ хранится только в текущей сессии Parsy. Для Ollama ключ не нужен.",
            )
            st.caption(
                "Отправляются только рассчитанные метрики и никнейм. Демка не загружается. "
                "Проверяй ответы AI: модель может ошибаться."
            )
            if st.button(
                "Сгенерировать AI-разбор",
                key=f"ai_generate_{cache_key}_{provider}",
                use_container_width=True,
            ):
                settings = {
                    "base_url": base_url,
                    "model": model,
                    "api_key": api_key,
                }
                result_key = f"ai_result_{cache_key}_{provider}"
                try:
                    with st.spinner("AI-тренер готовит разбор..."):
                        text = advisor.generate_ai_advice(
                            report,
                            local,
                            map_name,
                            player_name,
                            settings,
                        )
                    st.session_state[result_key] = text
                except Exception as error:
                    st.error(str(error))
            result_key = f"ai_result_{cache_key}_{provider}"
            if st.session_state.get(result_key):
                with st.container(border=True):
                    st.markdown(st.session_state[result_key])
                if st.button(
                    "Очистить AI-разбор",
                    key=f"ai_clear_{cache_key}_{provider}",
                    use_container_width=True,
                ):
                    st.session_state.pop(result_key, None)
                    st.rerun()


def _format_size(size: int) -> str:
    value = float(size or 0)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024 or unit == "ГБ":
            return f"{value:.1f} {unit}" if unit != "Б" else f"{int(value)} Б"
        value /= 1024
    return f"{value:.1f} ГБ"


def _render_update_sidebar() -> None:
    _render_html('<div class="sidebar-rule"></div>')
    _render_html('<div class="sidebar-label">Обновление</div>')
    _render_html(
        f'<div class="update-card"><div class="update-version">Parsy {_e(APP_VERSION)}</div>'
        f'<div class="update-note">{"Установленная версия" if IS_INSTALLED else "Portable / режим разработки"}</div></div>'
    )
    if not IS_INSTALLED:
        _render_html(
            '<div class="update-note">Автообновление доступно в установленной версии. '
            "Portable-сборку обновляй заменой папки.</div>"
        )

    if st.button("Проверить обновления", key="check_updates", use_container_width=True):
        with st.spinner("Проверяем GitHub..."):
            try:
                st.session_state["update_info"] = updater.check_latest(APP_VERSION)
                st.session_state.pop("update_error", None)
            except Exception as error:
                st.session_state["update_info"] = None
                st.session_state["update_error"] = str(error)

    error = st.session_state.get("update_error")
    if error:
        st.error(error)
    info = st.session_state.get("update_info")
    if not info:
        return
    if not info.get("is_newer"):
        st.caption("Установлена последняя версия.")
        return

    st.success(f"Доступна версия {info['version']}")
    size = _format_size(int(info.get("asset", {}).get("size") or 0))
    st.caption(f"Установщик · {size}")
    if info.get("notes"):
        with st.expander("Что нового"):
            st.markdown(info["notes"])
    if not IS_INSTALLED:
        if info.get("html_url"):
            st.markdown(f"[Скачать с GitHub]({info['html_url']})")
        return
    if st.button("Скачать и обновить", key="download_update", use_container_width=True):
        progress = st.progress(0.0, text="Скачивание установщика...")

        def on_progress(done: int, total: int) -> None:
            if total:
                ratio = min(max(done / total, 0.0), 1.0)
                progress.progress(ratio, text=f"Скачивание установщика... {ratio * 100:.0f}%")
            else:
                progress.progress(0.5, text="Скачивание установщика...")

        try:
            installer = updater.download_installer(info, on_progress)
            updater.write_update_request(
                installer,
                str(info["version"]),
                str(info.get("asset", {}).get("sha256") or ""),
            )
            progress.progress(1.0, text="Установщик готов")
            st.success(
                "Обновление скачано. Parsy сейчас закроется, установит новую версию "
                "и запустится снова."
            )
            st.caption(
                "Если окно не закрылось автоматически, закрой Parsy вручную: "
                "установка начнётся после завершения приложения."
            )
        except Exception as error:
            st.error(str(error))


def _render_sidebar_brand() -> None:
    _render_html(
        """
        <div class="sidebar-brand">
            <div class="brand-mark"><span></span></div>
            <div>
                <div class="brand-name">Parsy</div>
                <div class="brand-sub">demo intelligence</div>
            </div>
        </div>
        """
    )


def _render_workspace_bar(
    demo: DemoData,
    source: dict[str, Any],
    groups: list[dict[str, Any]],
) -> None:
    if len(groups) >= 2:
        match_title = f"{_text(groups[0].get('name'))} vs {_text(groups[1].get('name'))}"
    else:
        match_title = _text(source.get("server_name")) or demo.match_label()
    mode_label = (
        "HLTV DEMO"
        if source["is_hltv"]
        else "PRO DEMO"
        if source["is_esports"]
        else "COMMUNITY DEMO"
    )
    mode_class = (
        "hltv"
        if source["is_hltv"]
        else "esports"
        if source["is_esports"]
        else "community"
    )
    _render_html(
        f"""
        <div class="appbar">
            <div class="workspace-name">
                <span class="workspace-kicker">Матч</span>
                <span class="workspace-title">{_e(match_title)}</span>
            </div>
            <div class="appbar-meta">
                <span class="source-pill {mode_class}">{_e(mode_label)}</span>
                <span class="meta-pill">Карта <strong>{_e(demo.match_label())}</strong></span>
                <span class="meta-pill">Раунды <strong>{len(demo.rounds)}</strong></span>
            </div>
        </div>
        """
    )


def _render_empty_screen() -> None:
    _render_html(
        """
        <div class="empty-state">
            <div class="empty-state-title">Загрузите демку, чтобы увидеть полный профиль</div>
            <div class="empty-state-sub">
                Загрузка находится в боковой панели. Файл демки не отправляется на сервер;
                для про-карточек передаются только никнеймы и названия команд.
                Поддерживаются демки CS2 из матчмейкинга, HLTV и турнирных серверов.
            </div>
        </div>
        """
    )


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    with st.sidebar:
        _render_sidebar_brand()
        _render_html('<div class="sidebar-label">Демка</div>')
        uploaded = st.file_uploader(
            "Загрузить демку",
            type=["dem"],
            label_visibility="collapsed",
            help="Поддерживаются .dem файлы Counter-Strike 2 размером до 500 МБ.",
            max_upload_size=MAX_UPLOAD_MB,
            key="demo_upload",
        )
        _render_html(
            '<div class="sidebar-note">.dem до 500 МБ. Файл разбирается локально; '
            "для про-профилей отправляются только никнеймы и названия команд.</div>"
        )
        _render_update_sidebar()

    if uploaded is None:
        _render_html(
            """
            <div class="hero">
                <div class="eyebrow">PARSY / DEMO INTELLIGENCE</div>
                <h1>Демка под микроскопом</h1>
                <p>
                    K/D, ADR, KAST, утилиты, клатчи и бомба — весь киберспортивный
                    контекст в одном локальном интерфейсе.
                </p>
                <div class="hero-line"></div>
            </div>
            """
        )
        _render_empty_screen()
        return

    if DemoParser is None:
        st.error(
            "Библиотека demoparser2 не установлена. Выполните: "
            "py -m pip install --upgrade demoparser2"
        )
        return

    try:
        signature = (
            uploaded.name,
            getattr(uploaded, "size", None),
            DEMO_CACHE_VERSION,
        )
    except Exception:
        signature = (uploaded.name, None, DEMO_CACHE_VERSION)

    demo: DemoData | None = None
    if st.session_state.get("demo_signature") != signature:
        raw = uploaded.getvalue()
        if not raw:
            st.error("Файл пустой. Загрузите корректную демку CS2.")
            return
        with st.spinner("Разбираем демку: события, раунды, стороны и утилита..."):
            try:
                demo = _parse_demo_bytes(raw)
            except Exception:
                st.session_state.pop("demo_obj", None)
                st.session_state.pop("demo_signature", None)
                st.error(
                    "Не удалось прочитать демку. Файл повреждён, обрезан "
                    "или не является демкой CS2."
                )
                with st.expander("Технические детали"):
                    st.code(traceback.format_exc())
                return
        st.session_state["demo_obj"] = demo
        st.session_state["demo_signature"] = signature
    else:
        demo = st.session_state.get("demo_obj")

    if demo is None or not all(
        hasattr(demo, attribute)
        for attribute in ("events", "players", "rounds", "player_names", "round_info")
    ):
        st.error("Не удалось восстановить разобранную демку. Загрузите файл заново.")
        return

    source = _detect_demo_source(demo, uploaded.name)
    metadata: dict[str, Any] = {"ok": False, "players": {}, "teams": {}, "error": ""}
    if source["is_esports"]:
        with st.spinner("Подтягиваем профили игроков и команд..."):
            try:
                metadata = _load_liquipedia_metadata(
                    tuple(player["name"] for player in demo.players),
                    tuple(source.get("teams", [])),
                )
            except Exception:
                metadata["error"] = traceback.format_exc()

    groups = _group_teams(demo, metadata, source)
    options = _player_options(demo)
    if not options:
        st.error("В демке не удалось найти игроков.")
        return

    _render_workspace_bar(demo, source, groups)

    labels = [label for label, _ in options]
    label_to_sid = {label: sid for label, sid in options}
    widget_key = f"player_select_{uploaded.name}_{getattr(uploaded, 'size', '')}"

    with st.sidebar:
        _render_html('<div class="sidebar-rule"></div>')
        _render_html('<div class="sidebar-label">Матч</div>')
        if len(groups) >= 2:
            sidebar_match = (
                f"{_text(groups[0].get('name'))}  vs  {_text(groups[1].get('name'))}"
            )
        else:
            sidebar_match = _text(source.get("server_name")) or uploaded.name
        _render_html(
            f"""
            <div class="sidebar-match">
                <div class="sidebar-match-title" title="{_e(sidebar_match)}">{_e(sidebar_match)}</div>
                <div class="sidebar-match-meta">
                    {_e(demo.match_label())} · {len(demo.rounds)} раундов · {_e(source.get("label", ""))}
                </div>
            </div>
            """
        )
        _render_html(
            '<div class="sidebar-label" style="margin-top:1rem">Профиль игрока</div>'
        )
        selected_label = st.selectbox(
            "Профиль игрока",
            labels,
            index=0,
            key=widget_key,
            label_visibility="collapsed",
            help="Выбор меняет профиль во вкладках «Игрок», «Бой», «Утилиты» и «Клатчи».",
        )
        _render_html(
            '<div class="sidebar-note">Общий разбор и составы команд остаются '
            "независимыми от выбранного игрока.</div>"
        )

    sid = label_to_sid.get(selected_label, options[0][1])

    reports: dict[str, dict[str, Any]] = {}
    analysis_error = ""
    for player in demo.players:
        try:
            reports[player["sid"]] = analyze_player(demo, player["sid"])
        except Exception:
            analysis_error = traceback.format_exc()
            continue

    report = reports.get(sid)
    if report is None:
        st.error("Не удалось рассчитать статистику выбранного игрока.")
        with st.expander("Технические детали"):
            st.code(analysis_error or "Не удалось рассчитать ни одного игрока.")
        return

    general, player_tab, combat, utility, clutches, ai_tab = st.tabs(
        ["Общий", "Игрок", "Бой", "Утилиты", "Клатчи", "AI-тренер"]
    )

    with general:
        _general_tab(
            demo,
            uploaded.name,
            source,
            groups,
            metadata,
            reports,
            sid,
        )

    with player_tab:
        _overview_tab(report)

    with combat:
        _combat_tab(report, demo)

    with utility:
        _utility_tab(report)

    with clutches:
        _clutches_tab(report)

    with ai_tab:
        _ai_tab(report, demo, groups, sid, f"{signature[0]}_{signature[1]}_{sid}")

    _render_html(
        '<div class="footer-note">Parsy · локальный разбор демки · '
        "профили и логотипы: Liquipedia</div>"
    )


if __name__ == "__main__":
    main()
