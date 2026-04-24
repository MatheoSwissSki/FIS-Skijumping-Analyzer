"""
Skijumping FIS Analyzer — Streamlit App

Drag & Drop von FIS-Ski-Jumping-Telemetrie-CSVs, interaktive Vergleiche und
ein Flight Inspector mit 2D-Skispringer-Avatar.
"""

from __future__ import annotations

import base64
import time
import uuid
from pathlib import Path
from typing import List, Optional

import pandas as pd
import streamlit as st

from data_parser import Jump, JumpMeta, parse_csv, parse_file_name, summarize, interpolate_at, peak_sectors
from scene_renderer import render_scene_svg
from charts import (
    make_single_series_chart,
    make_dual_series_chart,
    make_mini_track,
)

# ═══════════════════════════════════════════════════════════════════════════
# Konstanten
# ═══════════════════════════════════════════════════════════════════════════

APP_TITLE = "Skijumping FIS Analyzer"
APP_ICON = "🎿"
PALETTE = ['#ff2d2d', '#38bdf8', '#facc15', '#a78bfa', '#4ade80', '#fb923c', '#f472b6', '#22d3ee']

METRICS = [
    {"key": "distance",      "label": "Distanz",              "unit": "m",    "dp": 1, "dir": "higher", "group": "result"},
    {"key": "v_h0",          "label": "V₀ horizontal",        "unit": "km/h", "dp": 2, "dir": "higher", "group": "result"},
    # Geschwindigkeit: Max + Durchschnitt
    {"key": "v_r_max",       "label": "V max",                "unit": "km/h", "dp": 1, "dir": "higher", "group": "speed"},
    {"key": "avg_v_r",       "label": "V Ø",                  "unit": "km/h", "dp": 1, "dir": "higher", "group": "speed"},
    {"key": "v_v_max_abs",   "label": "V vertikal max",       "unit": "km/h", "dp": 1, "dir": "higher", "group": "speed"},
    # Höhe: Max + Durchschnitt
    {"key": "max_h",         "label": "Höhe max",             "unit": "m",    "dp": 2, "dir": "higher", "group": "height"},
    {"key": "avg_h",         "label": "Höhe Ø",               "unit": "m",    "dp": 2, "dir": "higher", "group": "height"},
    # Anstellwinkel L/R: Max + Durchschnitt
    {"key": "max_aoa_l",     "label": "AoA Links max",        "unit": "°",    "dp": 1, "dir": "neutral", "group": "aoa"},
    {"key": "avg_aoa_l",     "label": "AoA Links Ø",          "unit": "°",    "dp": 1, "dir": "neutral", "group": "aoa"},
    {"key": "max_aoa_r",     "label": "AoA Rechts max",       "unit": "°",    "dp": 1, "dir": "neutral", "group": "aoa"},
    {"key": "avg_aoa_r",     "label": "AoA Rechts Ø",         "unit": "°",    "dp": 1, "dir": "neutral", "group": "aoa"},
    # Roll L/R: Max + Durchschnitt
    {"key": "max_roll_l",    "label": "Roll Links max",       "unit": "°",    "dp": 1, "dir": "neutral", "group": "roll"},
    {"key": "avg_roll_l",    "label": "Roll Links Ø",         "unit": "°",    "dp": 1, "dir": "neutral", "group": "roll"},
    {"key": "max_roll_r",    "label": "Roll Rechts max",      "unit": "°",    "dp": 1, "dir": "neutral", "group": "roll"},
    {"key": "avg_roll_r",    "label": "Roll Rechts Ø",        "unit": "°",    "dp": 1, "dir": "neutral", "group": "roll"},
    # Opening: Max + Durchschnitt
    {"key": "max_open",      "label": "Opening max",          "unit": "°",    "dp": 1, "dir": "higher", "group": "open"},
    {"key": "avg_open",      "label": "Opening Ø",            "unit": "°",    "dp": 1, "dir": "higher", "group": "open"},
    # Stabilität
    {"key": "y_drift",       "label": "Seitliche Ablage",     "unit": "m",    "dp": 2, "dir": "lower",  "group": "stability"},
    {"key": "roll_asym_avg", "label": "Roll-Asymmetrie Ø",    "unit": "°",    "dp": 2, "dir": "lower",  "group": "stability"},
]

# Parameter-Presets für Flight Inspector (was gehighlightet werden kann)
PEAK_PARAMS = {
    "none":   {"label": "Keine Hervorhebung", "col": None, "use_abs": False},
    "h":      {"label": "Flughöhe",           "col": "h",     "use_abs": False},
    "v_r":    {"label": "Geschwindigkeit",    "col": "v_r",   "use_abs": False},
    "aoa_l":  {"label": "Anstellwinkel Links","col": "aoa_l", "use_abs": True},
    "aoa_r":  {"label": "Anstellwinkel Rechts","col": "aoa_r","use_abs": True},
    "roll_l": {"label": "Roll-Winkel Links",  "col": "roll_l","use_abs": True},
    "roll_r": {"label": "Roll-Winkel Rechts", "col": "roll_r","use_abs": True},
}

ASSETS_DIR = Path(__file__).parent / "assets"


# ═══════════════════════════════════════════════════════════════════════════
# Page Setup
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)


def inject_css() -> None:
    st.markdown(
        """
        <style>
        /* Hauptfarben - passend zur HTML-Version */
        :root {
            --bg-0: #0a0b0d;
            --bg-1: #111318;
            --bg-2: #181b22;
            --bg-3: #22262f;
            --line: #2a2f3a;
            --text-0: #f4f5f7;
            --text-1: #b8bcc6;
            --text-2: #70757f;
            --text-3: #484c55;
            --accent: #ff2d2d;
            --good: #22c55e;
            --bad: #ef4444;
        }

        /* Streamlit-eigene Paddings verkleinern */
        .block-container { padding-top: 1rem; padding-bottom: 3rem; max-width: 1400px; }

        /* Header */
        .app-header {
            display: flex;
            align-items: center;
            gap: 20px;
            padding-bottom: 18px;
            border-bottom: 1px solid #2a2f3a;
            margin-bottom: 24px;
        }
        .app-logo { height: 52px; width: auto; display: block; }
        .app-title {
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 22px;
            letter-spacing: -0.02em;
            line-height: 1;
            color: #f4f5f7;
            margin: 0;
        }
        .app-subtitle {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: #70757f;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            margin-top: 4px;
        }
        .header-divider {
            width: 1px; height: 40px;
            background: #2a2f3a;
        }

        /* Section Titles */
        .section-title {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: #70757f;
            text-transform: uppercase;
            letter-spacing: 0.2em;
            margin: 24px 0 12px 0;
            padding-bottom: 8px;
            border-bottom: 1px solid #2a2f3a;
        }

        /* Jump Cards */
        .jump-card {
            background: #111318;
            border: 1px solid #2a2f3a;
            border-left: 3px solid var(--card-color, #ff2d2d);
            padding: 14px 16px;
            margin-bottom: 10px;
            transition: border-color 0.15s;
        }
        .jump-card .head {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
        }
        .jump-card .name {
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 600;
            font-size: 15px;
            color: #f4f5f7;
            line-height: 1.2;
        }
        .jump-card .meta {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            color: #70757f;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-top: 2px;
        }
        .jump-card .distance-badge {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: #f4f5f7;
            padding: 3px 8px;
            background: #22262f;
            border: 1px solid #2a2f3a;
            white-space: nowrap;
        }
        .jump-card .stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1px;
            background: #2a2f3a;
            margin-top: 10px;
        }
        .jump-card .stat { background: #181b22; padding: 8px 10px; }
        .jump-card .stat-lbl {
            font-family: 'JetBrains Mono', monospace;
            font-size: 9px;
            color: #70757f;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }
        .jump-card .stat-val {
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            font-weight: 500;
            color: #f4f5f7;
        }
        .jump-card .stat-val .unit {
            font-size: 9px;
            color: #70757f;
            margin-left: 2px;
        }

        /* Head-to-Head */
        .h2h-row {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            border-bottom: 1px solid #1f232c;
            background: #111318;
        }
        .h2h-cell {
            padding: 12px 16px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .h2h-cell.left { justify-content: flex-end; }
        .h2h-cell.right { justify-content: flex-start; }
        .h2h-cell.label {
            justify-content: center;
            background: #181b22;
            font-size: 10px;
            color: #70757f;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            flex-direction: column;
            gap: 3px;
            text-align: center;
        }
        .h2h-cell.label .u {
            font-size: 9px;
            color: #484c55;
            letter-spacing: 0.1em;
        }
        .h2h-cell.winner {
            background: linear-gradient(to right, rgba(34,197,94,0.12), transparent 75%);
        }
        .h2h-cell.left.winner {
            background: linear-gradient(to left, rgba(34,197,94,0.12), transparent 75%);
        }
        .h2h-cell.loser {
            background: linear-gradient(to right, rgba(239,68,68,0.12), transparent 75%);
        }
        .h2h-cell.left.loser {
            background: linear-gradient(to left, rgba(239,68,68,0.12), transparent 75%);
        }
        .h2h-cell.winner .val { color: #22c55e; font-weight: 600; }
        .h2h-cell.loser .val { color: #ef4444; font-weight: 600; }
        .h2h-cell .delta {
            font-size: 10px;
            color: #70757f;
        }
        .h2h-cell.winner .delta { color: #22c55e; }
        .h2h-cell.loser .delta { color: #ef4444; }

        /* Stat-Grid im Inspector */
        .data-block {
            background: #181b22;
            border: 1px solid #1f232c;
            padding: 12px 14px;
            margin-bottom: 10px;
        }
        .data-block-title {
            font-family: 'JetBrains Mono', monospace;
            font-size: 9px;
            color: #484c55;
            text-transform: uppercase;
            letter-spacing: 0.2em;
            margin-bottom: 8px;
        }
        .data-grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px 16px;
        }
        .data-item-lbl {
            font-family: 'JetBrains Mono', monospace;
            font-size: 9px;
            color: #70757f;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }
        .data-item-val {
            font-family: 'JetBrains Mono', monospace;
            font-size: 15px;
            font-weight: 500;
            color: #f4f5f7;
            margin-top: 1px;
        }
        .data-item-val .u {
            font-size: 9px;
            color: #70757f;
            margin-left: 2px;
        }

        /* Streamlit button styling anpassen */
        .stButton > button {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            border-radius: 0;
            border: 1px solid #2a2f3a;
            background: #22262f;
            color: #b8bcc6;
        }
        .stButton > button:hover {
            border-color: #ff2d2d;
            color: #ff2d2d;
        }

        /* Upload-Area */
        [data-testid="stFileUploader"] section {
            background: #111318;
            border: 2px dashed #2a2f3a;
            padding: 24px;
        }
        [data-testid="stFileUploader"] section:hover {
            border-color: #ff2d2d;
        }

        /* Slider */
        .stSlider [data-baseweb="slider"] > div > div {
            background: #ff2d2d;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    logo_path = ASSETS_DIR / "logo-myswissski.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()
        logo_src = f"data:image/jpeg;base64,{logo_b64}"
        logo_html = f'<img class="app-logo" src="{logo_src}" alt="MySwissSki"/>'
    else:
        logo_html = ""

    st.markdown(
        f"""
        <div class="app-header">
            {logo_html}
            <div class="header-divider"></div>
            <div>
                <h1 class="app-title">{APP_TITLE}</h1>
                <div class="app-subtitle">Flight Telemetry // Motion Sensors</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# State
# ═══════════════════════════════════════════════════════════════════════════

def init_state() -> None:
    if "jumps" not in st.session_state:
        st.session_state.jumps: List[Jump] = []
    if "next_color_idx" not in st.session_state:
        st.session_state.next_color_idx = 0
    if "inspect_id" not in st.session_state:
        st.session_state.inspect_id: Optional[str] = None
    if "inspect_pos" not in st.session_state:
        st.session_state.inspect_pos: float = 0.0
    if "processed_files" not in st.session_state:
        # Set zur Deduplizierung von Datei-Uploads (gleiche Datei nicht mehrfach laden)
        st.session_state.processed_files: set = set()


def add_jump_from_upload(uploaded_file) -> None:
    """Verarbeitet eine hochgeladene CSV-Datei und fügt sie zum State hinzu."""
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    if file_key in st.session_state.processed_files:
        return
    st.session_state.processed_files.add(file_key)

    try:
        content = uploaded_file.getvalue()
        df = parse_csv(content)
        if df.empty:
            st.warning(f"Keine gültigen Messpunkte in {uploaded_file.name}")
            return
        meta = parse_file_name(uploaded_file.name)
        summary = summarize(df)
        color = PALETTE[st.session_state.next_color_idx % len(PALETTE)]
        st.session_state.next_color_idx += 1

        jump = Jump(
            id=str(uuid.uuid4())[:8],
            color=color,
            meta=meta,
            df=df,
            summary=summary,
            active=True,
        )
        st.session_state.jumps.append(jump)
    except Exception as e:
        st.error(f"Fehler beim Laden von {uploaded_file.name}: {e}")


def get_active_jumps() -> List[Jump]:
    return [j for j in st.session_state.jumps if j.active]


def get_inspect_jump() -> Optional[Jump]:
    if not st.session_state.inspect_id:
        return None
    return next((j for j in st.session_state.jumps if j.id == st.session_state.inspect_id), None)


# ═══════════════════════════════════════════════════════════════════════════
# UI-Abschnitte
# ═══════════════════════════════════════════════════════════════════════════

def render_upload() -> None:
    uploaded = st.file_uploader(
        "CSV-Auswertung hochladen (Drag & Drop oder Klick)",
        type=["csv"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded:
        for f in uploaded:
            add_jump_from_upload(f)


def fmt(v, dp=1) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return f"{float(v):.{dp}f}"
    except (ValueError, TypeError):
        return "—"


def render_jump_cards() -> None:
    if not st.session_state.jumps:
        return

    st.markdown(
        f'<div class="section-title">Geladene Sprünge — {len(st.session_state.jumps):02d}</div>',
        unsafe_allow_html=True,
    )

    # In Reihen von 3 Karten darstellen
    cols_per_row = 3
    for i in range(0, len(st.session_state.jumps), cols_per_row):
        cols = st.columns(cols_per_row)
        for j_idx, jump in enumerate(st.session_state.jumps[i:i + cols_per_row]):
            with cols[j_idx]:
                render_single_jump_card(jump)


def render_single_jump_card(jump: Jump) -> None:
    s = jump.summary
    is_inspected = st.session_state.inspect_id == jump.id

    st.markdown(
        f"""
        <div class="jump-card" style="--card-color: {jump.color};">
            <div class="head">
                <div>
                    <div class="name">{jump.meta.full_name}</div>
                    <div class="meta">{jump.meta.subtitle}</div>
                </div>
                <div class="distance-badge">{fmt(s.distance, 1)} m</div>
            </div>
            <div class="stats">
                <div class="stat">
                    <div class="stat-lbl">V₀ horiz.</div>
                    <div class="stat-val">{fmt(s.v_h0, 1)}<span class="unit">km/h</span></div>
                </div>
                <div class="stat">
                    <div class="stat-lbl">V max</div>
                    <div class="stat-val">{fmt(s.v_r_max, 1)}<span class="unit">km/h</span></div>
                </div>
                <div class="stat">
                    <div class="stat-lbl">Max Höhe</div>
                    <div class="stat-val">{fmt(s.max_h, 2)}<span class="unit">m</span></div>
                </div>
                <div class="stat">
                    <div class="stat-lbl">Y-Drift</div>
                    <div class="stat-val">{fmt(s.y_drift, 2)}<span class="unit">m</span></div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Controls unter der Karte
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        active = st.checkbox(
            "Im Vergleich",
            value=jump.active,
            key=f"active_{jump.id}",
        )
        if active != jump.active:
            jump.active = active
            st.rerun()
    with c2:
        label = "⏺ Inspiziert" if is_inspected else "▶ Inspizieren"
        if st.button(label, key=f"inspect_{jump.id}", use_container_width=True):
            if is_inspected:
                st.session_state.inspect_id = None
            else:
                st.session_state.inspect_id = jump.id
                st.session_state.inspect_pos = 0.0
            st.rerun()
    with c3:
        if st.button("✕", key=f"remove_{jump.id}", help="Sprung entfernen"):
            if is_inspected:
                st.session_state.inspect_id = None
            st.session_state.jumps = [j for j in st.session_state.jumps if j.id != jump.id]
            st.rerun()


def render_inspector() -> None:
    jump = get_inspect_jump()
    if not jump:
        return

    st.markdown(
        '<div class="section-title">Flight Inspector</div>',
        unsafe_allow_html=True,
    )

    # Kopfzeile mit Athlet
    head_col1, head_col2 = st.columns([5, 1])
    with head_col1:
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:12px; padding:10px 14px; background:#181b22; border:1px solid #2a2f3a; margin-bottom:2px;">
                <div style="width:12px; height:12px; background:{jump.color};"></div>
                <div style="font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:16px;">{jump.meta.full_name}</div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:10px; color:#70757f; letter-spacing:0.1em; text-transform:uppercase;">{jump.meta.subtitle} · Distanz {jump.summary.distance:.1f} m</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with head_col2:
        if st.button("Schliessen ✕", key="inspector_close", use_container_width=True):
            st.session_state.inspect_id = None
            st.rerun()

    # ─── Parameter-Auswahl (klickbar) für Peak-Highlighting ───
    st.markdown(
        '<div style="font-family:JetBrains Mono,monospace; font-size:10px; color:#70757f; '
        'letter-spacing:0.15em; text-transform:uppercase; margin-top:12px; margin-bottom:6px;">'
        'Sektoren innerhalb 5 % des Maximums hervorheben</div>',
        unsafe_allow_html=True,
    )
    param_cols = st.columns(len(PEAK_PARAMS))
    for i, (key, cfg) in enumerate(PEAK_PARAMS.items()):
        with param_cols[i]:
            is_active = st.session_state.get("peak_param", "none") == key
            btn_label = ("● " if is_active else "") + cfg["label"]
            if st.button(btn_label, key=f"param_{key}", use_container_width=True):
                st.session_state.peak_param = key
                st.rerun()

    active_param = st.session_state.get("peak_param", "none")
    active_cfg = PEAK_PARAMS[active_param]

    # Peak-Sektoren für gewählten Parameter berechnen
    current_peak_sectors = []
    if active_cfg["col"] is not None:
        current_peak_sectors = peak_sectors(
            jump.df,
            active_cfg["col"],
            use_abs=active_cfg["use_abs"],
            tolerance=0.05,
        )

    # Scrubber-Slider
    max_dist = jump.summary.distance or 100.0
    new_pos = st.slider(
        "Position entlang des Flugs",
        min_value=0.0,
        max_value=float(max_dist),
        value=float(min(st.session_state.inspect_pos, max_dist)),
        step=0.5,
        key="inspect_slider",
        label_visibility="collapsed",
    )
    st.session_state.inspect_pos = new_pos

    # Haupt-Layout: Szene links (breit), Datenpanel rechts (schmal)
    scene_col, data_col = st.columns([2, 1])

    with scene_col:
        active_jumps = get_active_jumps()
        svg = render_scene_svg(
            inspect_jump=jump,
            inspect_pos=new_pos,
            all_active_jumps=active_jumps,
            peak_sectors=current_peak_sectors if current_peak_sectors else None,
            peak_label=active_cfg["label"] if active_param != "none" else "",
        )
        st.markdown(svg, unsafe_allow_html=True)

        # Mini-Tracks unter der Szene
        render_mini_tracks(jump, new_pos, active_param)

    with data_col:
        render_data_panel(jump, new_pos)


def render_data_panel(jump: Jump, pos: float) -> None:
    point = interpolate_at(jump.df, pos)
    if not point:
        return

    def v(key, dp=1):
        val = point.get(key)
        if val is None or pd.isna(val):
            return "—"
        return f"{val:.{dp}f}"

    # Geschwindigkeits-Block
    st.markdown(
        f"""
        <div class="data-block">
            <div class="data-block-title">Geschwindigkeit</div>
            <div class="data-grid-2">
                <div>
                    <div class="data-item-lbl">Resultierend</div>
                    <div class="data-item-val">{v('v_r', 1)}<span class="u">km/h</span></div>
                </div>
                <div>
                    <div class="data-item-lbl">Horizontal</div>
                    <div class="data-item-val">{v('v_h', 1)}<span class="u">km/h</span></div>
                </div>
                <div>
                    <div class="data-item-lbl">Vertikal</div>
                    <div class="data-item-val">{v('v_v', 1)}<span class="u">km/h</span></div>
                </div>
                <div>
                    <div class="data-item-lbl">Höhe ü. Grund</div>
                    <div class="data-item-val">{v('h', 2)}<span class="u">m</span></div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # AoA-Block
    st.markdown(
        f"""
        <div class="data-block">
            <div class="data-block-title">Anstellwinkel (AoA)</div>
            <div class="data-grid-2">
                <div>
                    <div class="data-item-lbl">Links</div>
                    <div class="data-item-val">{v('aoa_l', 1)}<span class="u">°</span></div>
                </div>
                <div>
                    <div class="data-item-lbl">Rechts</div>
                    <div class="data-item-val">{v('aoa_r', 1)}<span class="u">°</span></div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Roll-Block
    st.markdown(
        f"""
        <div class="data-block">
            <div class="data-block-title">Roll-Winkel</div>
            <div class="data-grid-2">
                <div>
                    <div class="data-item-lbl">Links</div>
                    <div class="data-item-val">{v('roll_l', 1)}<span class="u">°</span></div>
                </div>
                <div>
                    <div class="data-item-lbl">Rechts</div>
                    <div class="data-item-val">{v('roll_r', 1)}<span class="u">°</span></div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Ski-Block
    st.markdown(
        f"""
        <div class="data-block">
            <div class="data-block-title">Ski-Stellung</div>
            <div class="data-grid-2">
                <div>
                    <div class="data-item-lbl">Opening Angle</div>
                    <div class="data-item-val">{v('open', 1)}<span class="u">°</span></div>
                </div>
                <div>
                    <div class="data-item-lbl">Y-Ablage</div>
                    <div class="data-item-val">{v('y', 2)}<span class="u">m</span></div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_mini_tracks(jump: Jump, pos: float, active_param: str = "none") -> None:
    """4 kompakte Verlaufs-Charts: Höhe, AoA, Roll, Geschwindigkeit."""
    # Welcher Track soll Peak-Highlighting bekommen?
    # Mapping von active_param → Track-Index + Konfiguration
    param_to_track = {
        "h":      {"track_idx": 0, "col": "h",     "use_abs": False},
        "aoa_l":  {"track_idx": 1, "col": "aoa_l", "use_abs": True},
        "aoa_r":  {"track_idx": 1, "col": "aoa_r", "use_abs": True},
        "roll_l": {"track_idx": 2, "col": "roll_l","use_abs": True},
        "roll_r": {"track_idx": 2, "col": "roll_r","use_abs": True},
        "v_r":    {"track_idx": 3, "col": "v_r",   "use_abs": False},
    }

    tracks = [
        ("Flughöhe [m]", [("h", jump.color)], True),
        ("Anstellwinkel L/R [°]", [("aoa_l", "#60a5fa"), ("aoa_r", "#f87171")], False),
        ("Roll-Winkel L/R [°]", [("roll_l", "#60a5fa"), ("roll_r", "#f87171")], False),
        ("Geschwindigkeit [km/h]", [("v_r", jump.color)], False),
    ]

    # Peak-Sektoren für aktiven Track berechnen
    peak_for_track_idx = None
    param_cfg = param_to_track.get(active_param)
    if param_cfg:
        sectors = peak_sectors(jump.df, param_cfg["col"], use_abs=param_cfg["use_abs"], tolerance=0.05)
        peak_for_track_idx = (param_cfg["track_idx"], sectors)

    for i, (label, series, fill) in enumerate(tracks):
        # Label mit Peak-Info falls aktiv
        is_peak_track = peak_for_track_idx and peak_for_track_idx[0] == i
        peak_info = ""
        if is_peak_track and peak_for_track_idx[1]:
            peak_info = f' <span style="color:#facc15;">· Peak: {len(peak_for_track_idx[1])} Sektor(en)</span>'

        st.markdown(
            f'<div style="font-family:JetBrains Mono,monospace; font-size:9px; '
            f'color:#70757f; letter-spacing:0.1em; text-transform:uppercase; '
            f'margin-top:8px; margin-bottom:2px;">{label}{peak_info}</div>',
            unsafe_allow_html=True,
        )

        sectors_for_chart = peak_for_track_idx[1] if is_peak_track else None
        fig = make_mini_track(
            jump,
            series,
            pos,
            fill_first=fill,
            peak_sectors=sectors_for_chart,
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": False, "staticPlot": True},
        )


def compare_metric(a, b, direction: str) -> str:
    """Gibt 'a', 'b', 'tie', 'na' oder 'neutral' zurück."""
    if a is None or b is None or pd.isna(a) or pd.isna(b):
        return "na"
    if direction == "neutral":
        return "neutral"
    diff = a - b
    if abs(diff) < 1e-6:
        return "tie"
    if direction == "higher":
        return "a" if diff > 0 else "b"
    if direction == "lower":
        return "a" if diff < 0 else "b"
    return "tie"


def render_h2h() -> None:
    active = get_active_jumps()
    if len(active) != 2:
        return

    A, B = active
    st.markdown(
        '<div class="section-title">Head-to-Head Vergleich</div>',
        unsafe_allow_html=True,
    )

    # Kopf
    st.markdown(
        f"""
        <div style="display:grid; grid-template-columns:1fr auto 1fr; gap:20px; align-items:center;
                    padding:16px 20px; background:#111318; border:1px solid #2a2f3a; margin-bottom:2px;">
            <div>
                <div style="display:flex; align-items:center; gap:10px;">
                    <div style="width:10px; height:10px; background:{A.color};"></div>
                    <span style="font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:16px;">{A.meta.full_name}</span>
                </div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:10px; color:#70757f; letter-spacing:0.12em; text-transform:uppercase; margin-top:3px;">{A.meta.subtitle}</div>
            </div>
            <div style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#484c55; letter-spacing:0.2em; padding:6px 12px; border:1px solid #2a2f3a;">VS</div>
            <div style="text-align:right;">
                <div style="display:flex; align-items:center; gap:10px; flex-direction:row-reverse;">
                    <div style="width:10px; height:10px; background:{B.color};"></div>
                    <span style="font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:16px;">{B.meta.full_name}</span>
                </div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:10px; color:#70757f; letter-spacing:0.12em; text-transform:uppercase; margin-top:3px;">{B.meta.subtitle}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Metrik-Zeilen
    rows_html = []
    for m in METRICS:
        av = getattr(A.summary, m["key"])
        bv = getattr(B.summary, m["key"])
        winner = compare_metric(av, bv, m["dir"])

        left_cls, right_cls = "", ""
        left_extra, right_extra = "", ""

        if winner == "a":
            left_cls, right_cls = "winner", "loser"
            delta = abs(av - bv)
            left_extra = f'<span style="color:#22c55e;">▲</span><span class="delta">+{delta:.{m["dp"]}f}</span>'
            right_extra = f'<span class="delta">−{delta:.{m["dp"]}f}</span><span style="color:#ef4444;">▼</span>'
        elif winner == "b":
            left_cls, right_cls = "loser", "winner"
            delta = abs(bv - av)
            left_extra = f'<span style="color:#ef4444;">▼</span><span class="delta">−{delta:.{m["dp"]}f}</span>'
            right_extra = f'<span class="delta">+{delta:.{m["dp"]}f}</span><span style="color:#22c55e;">▲</span>'

        rows_html.append(
            f"""
            <div class="h2h-row">
                <div class="h2h-cell left {left_cls}">
                    {left_extra}
                    <span class="val">{fmt(av, m['dp'])}</span>
                </div>
                <div class="h2h-cell label">
                    <span>{m['label']}</span>
                    <span class="u">{m['unit']}</span>
                </div>
                <div class="h2h-cell right {right_cls}">
                    <span class="val">{fmt(bv, m['dp'])}</span>
                    {right_extra}
                </div>
            </div>
            """
        )

    st.markdown(
        f'<div style="border:1px solid #2a2f3a; border-top:none;">{"".join(rows_html)}</div>'
        f'<div style="text-align:center; font-family:JetBrains Mono,monospace; font-size:10px; color:#484c55; '
        f'letter-spacing:0.15em; text-transform:uppercase; margin-top:10px;">Grün = besser · Rot = schlechter</div>',
        unsafe_allow_html=True,
    )


def render_charts() -> None:
    active = get_active_jumps()
    if not active:
        return

    st.markdown(
        '<div class="section-title">Flugkurven Vergleich</div>',
        unsafe_allow_html=True,
    )

    # Scrub-Position und -Farbe nur wenn ein Sprung inspiziert wird UND er aktiv ist
    inspect_jump = get_inspect_jump()
    scrub_pos = None
    scrub_color = None
    if inspect_jump and inspect_jump.active:
        scrub_pos = st.session_state.inspect_pos
        scrub_color = inspect_jump.color

    # Peak-Sektoren für den aktiven Parameter (nur auf dem gescrubten Sprung)
    active_param = st.session_state.get("peak_param", "none")
    param_to_col = {
        "h": ("h", False),
        "v_r": ("v_r", False),
        "aoa_l": ("aoa_l", True),
        "aoa_r": ("aoa_r", True),
        "roll_l": ("roll_l", True),
        "roll_r": ("roll_r", True),
    }

    def peaks_for_chart(chart_col: str) -> Optional[dict]:
        """Gibt {jump_id: [sectors]} zurück wenn der Parameter für diesen Chart relevant ist."""
        if active_param == "none" or not inspect_jump or not inspect_jump.active:
            return None
        cfg = param_to_col.get(active_param)
        if not cfg:
            return None
        if cfg[0] != chart_col:
            return None
        sectors = peak_sectors(inspect_jump.df, cfg[0], use_abs=cfg[1], tolerance=0.05)
        return {inspect_jump.id: sectors} if sectors else None

    # Höhe - breiter Chart
    st.markdown('<div style="font-family:Space Grotesk,sans-serif; font-weight:600; font-size:14px; margin-top:16px;">Flugkurve · Höhe über Grund</div>', unsafe_allow_html=True)
    st.plotly_chart(
        make_single_series_chart(
            active, "h", "m", fill=True,
            scrub_pos=scrub_pos, scrub_color=scrub_color, height=340,
            peak_sectors_by_jump=peaks_for_chart("h"),
        ),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    # Zwei Spalten für mittlere Charts
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div style="font-family:Space Grotesk,sans-serif; font-weight:600; font-size:14px; margin-top:16px;">Resultierende Geschwindigkeit</div>', unsafe_allow_html=True)
        st.plotly_chart(
            make_single_series_chart(
                active, "v_r", "km/h",
                scrub_pos=scrub_pos, scrub_color=scrub_color,
                peak_sectors_by_jump=peaks_for_chart("v_r"),
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )

        st.markdown('<div style="font-family:Space Grotesk,sans-serif; font-weight:600; font-size:14px; margin-top:16px;">Anstellwinkel Links</div>', unsafe_allow_html=True)
        st.plotly_chart(
            make_single_series_chart(
                active, "aoa_l", "°",
                scrub_pos=scrub_pos, scrub_color=scrub_color,
                peak_sectors_by_jump=peaks_for_chart("aoa_l"),
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )

        st.markdown('<div style="font-family:Space Grotesk,sans-serif; font-weight:600; font-size:14px; margin-top:16px;">Roll-Winkel Links</div>', unsafe_allow_html=True)
        st.plotly_chart(
            make_single_series_chart(
                active, "roll_l", "°",
                scrub_pos=scrub_pos, scrub_color=scrub_color,
                peak_sectors_by_jump=peaks_for_chart("roll_l"),
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    with c2:
        st.markdown('<div style="font-family:Space Grotesk,sans-serif; font-weight:600; font-size:14px; margin-top:16px;">Horizontal vs. Vertikal</div>', unsafe_allow_html=True)
        st.plotly_chart(
            make_dual_series_chart(
                active,
                series=[("v_h", "horizontal", False), ("v_v", "vertikal", True)],
                unit="km/h",
                scrub_pos=scrub_pos,
                scrub_color=scrub_color,
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )

        st.markdown('<div style="font-family:Space Grotesk,sans-serif; font-weight:600; font-size:14px; margin-top:16px;">Anstellwinkel Rechts</div>', unsafe_allow_html=True)
        st.plotly_chart(
            make_single_series_chart(
                active, "aoa_r", "°",
                scrub_pos=scrub_pos, scrub_color=scrub_color,
                peak_sectors_by_jump=peaks_for_chart("aoa_r"),
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )

        st.markdown('<div style="font-family:Space Grotesk,sans-serif; font-weight:600; font-size:14px; margin-top:16px;">Roll-Winkel Rechts</div>', unsafe_allow_html=True)
        st.plotly_chart(
            make_single_series_chart(
                active, "roll_r", "°",
                scrub_pos=scrub_pos, scrub_color=scrub_color,
                peak_sectors_by_jump=peaks_for_chart("roll_r"),
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    st.markdown('<div style="font-family:Space Grotesk,sans-serif; font-weight:600; font-size:14px; margin-top:16px;">Top View · Seitliche Ablage</div>', unsafe_allow_html=True)
    st.plotly_chart(
        make_single_series_chart(active, "y", "m", scrub_pos=scrub_pos, scrub_color=scrub_color, height=260),
        use_container_width=True,
        config={"displayModeBar": False},
    )


def render_summary_table() -> None:
    active = get_active_jumps()
    if not active:
        return

    st.markdown(
        '<div class="section-title">Kennzahlen Tabelle</div>',
        unsafe_allow_html=True,
    )

    # Best/Worst pro Metrik bestimmen (nur für 'higher' / 'lower')
    best_worst = {}
    if len(active) >= 2:
        for m in METRICS:
            if m["dir"] == "neutral":
                continue
            best_j, worst_j, best_v, worst_v = None, None, None, None
            for j in active:
                v = getattr(j.summary, m["key"])
                if v is None or pd.isna(v):
                    continue
                if best_v is None:
                    best_v = worst_v = v
                    best_j = worst_j = j
                    continue
                if m["dir"] == "higher":
                    if v > best_v:
                        best_v, best_j = v, j
                    if v < worst_v:
                        worst_v, worst_j = v, j
                elif m["dir"] == "lower":
                    if v < best_v:
                        best_v, best_j = v, j
                    if v > worst_v:
                        worst_v, worst_j = v, j
            if best_j and worst_j and best_j.id != worst_j.id:
                best_worst[m["key"]] = {"best": best_j.id, "worst": worst_j.id}

    # DataFrame-basierte Tabelle mit Style
    rows = []
    for j in active:
        row = {
            "Sprung": f"● {j.meta.full_name} {j.meta.nation}".strip(),
        }
        for m in METRICS:
            v = getattr(j.summary, m["key"])
            row[m["label"]] = fmt(v, m["dp"])
        rows.append(row)

    df_display = pd.DataFrame(rows)

    # Wir rendern als HTML-Tabelle für die Farben
    html_rows = []
    for i, j in enumerate(active):
        cells = []
        cells.append(
            f'<td style="font-family:Space Grotesk,sans-serif; color:#f4f5f7; padding:10px 12px;">'
            f'<span style="display:inline-block; width:8px; height:8px; background:{j.color}; margin-right:8px;"></span>'
            f'{j.meta.last_name} {j.meta.first_name}'
            f'<span style="color:#70757f; font-family:JetBrains Mono,monospace; font-size:10px; margin-left:6px;">{j.meta.nation} {j.meta.round_}</span>'
            f'</td>'
        )
        for m in METRICS:
            v = getattr(j.summary, m["key"])
            cell_style = "padding:10px 12px; font-family:JetBrains Mono,monospace; font-size:12px;"
            if m["key"] in best_worst:
                if best_worst[m["key"]]["best"] == j.id:
                    cell_style += " color:#22c55e; background:rgba(34,197,94,0.07); font-weight:600;"
                elif best_worst[m["key"]]["worst"] == j.id:
                    cell_style += " color:#ef4444; background:rgba(239,68,68,0.06); font-weight:600;"
            cells.append(f'<td style="{cell_style}">{fmt(v, m["dp"])}</td>')
        html_rows.append(f'<tr style="border-bottom:1px solid #1f232c;">{"".join(cells)}</tr>')

    header_cells = [
        '<th style="padding:12px; text-align:left; font-family:JetBrains Mono,monospace; font-size:10px; color:#70757f; text-transform:uppercase; letter-spacing:0.12em; background:#181b22; border-bottom:1px solid #2a2f3a;">Sprung</th>'
    ]
    for m in METRICS:
        if m["dir"] == "higher":
            arrow = "↑ besser"
        elif m["dir"] == "lower":
            arrow = "↓ besser"
        else:
            arrow = ""
        header_cells.append(
            f'<th style="padding:12px; text-align:left; font-family:JetBrains Mono,monospace; font-size:10px; color:#70757f; text-transform:uppercase; letter-spacing:0.12em; background:#181b22; border-bottom:1px solid #2a2f3a;">'
            f'{m["label"]} <span style="font-size:8px; color:#484c55; margin-left:4px;">[{m["unit"]}] {arrow}</span>'
            f'</th>'
        )

    st.markdown(
        f"""
        <div style="background:#111318; border:1px solid #2a2f3a; overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse;">
                <thead><tr>{"".join(header_cells)}</tr></thead>
                <tbody>{"".join(html_rows)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    init_state()
    inject_css()
    render_header()
    render_upload()
    render_jump_cards()
    render_inspector()
    render_h2h()
    render_charts()
    render_summary_table()


if __name__ == "__main__":
    main()
