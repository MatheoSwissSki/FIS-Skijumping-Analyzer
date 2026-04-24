"""
Plotly-Charts im dunklen Theme, passend zur HTML-Version.
Alle Charts zeigen Distanz auf der X-Achse und können überlagerte Sprünge darstellen.
"""

from __future__ import annotations

from typing import List, Optional, Callable

import pandas as pd
import plotly.graph_objects as go

from data_parser import Jump


# Einheitliches Layout für alle Charts
DARK_LAYOUT = dict(
    plot_bgcolor="#111318",
    paper_bgcolor="#111318",
    font=dict(family="JetBrains Mono, monospace", size=10, color="#b8bcc6"),
    xaxis=dict(
        gridcolor="#1f232c",
        zerolinecolor="#484c55",
        linecolor="#2a2f3a",
        tickfont=dict(size=10, color="#70757f"),
        title=dict(text="Distanz [m]", font=dict(size=9, color="#70757f")),
    ),
    yaxis=dict(
        gridcolor="#1f232c",
        zerolinecolor="#484c55",
        linecolor="#2a2f3a",
        tickfont=dict(size=10, color="#70757f"),
    ),
    margin=dict(l=50, r=20, t=10, b=40),
    hovermode="x unified",
    hoverlabel=dict(
        bgcolor="rgba(24, 27, 34, 0.95)",
        bordercolor="#2a2f3a",
        font=dict(family="JetBrains Mono, monospace", size=11, color="#f4f5f7"),
    ),
    showlegend=True,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        bgcolor="rgba(0,0,0,0)",
        font=dict(size=10),
    ),
)


def _base_figure(title_unit: str = "", height: int = 300) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**DARK_LAYOUT, height=height)
    if title_unit:
        fig.update_yaxes(title=dict(text=title_unit, font=dict(size=9, color="#70757f")))
    return fig


def _add_landing_markers(fig: go.Figure, jumps: List[Jump]) -> None:
    """Vertikale gestrichelte Linien an den jeweiligen Landedistanzen."""
    for j in jumps:
        if j.summary.distance is None:
            continue
        fig.add_vline(
            x=j.summary.distance,
            line=dict(color=j.color, dash="dash", width=1),
            opacity=0.5,
        )


def _add_scrub_marker(fig: go.Figure, pos: Optional[float], color: str) -> None:
    """Vertikale volle Linie an der aktuellen Inspector-Position."""
    if pos is None:
        return
    fig.add_vline(
        x=pos,
        line=dict(color=color, width=1.5),
        opacity=0.9,
    )


def make_single_series_chart(
    jumps: List[Jump],
    y_col: str,
    unit: str,
    fill: bool = False,
    scrub_pos: Optional[float] = None,
    scrub_color: Optional[str] = None,
    height: int = 300,
    peak_sectors_by_jump: Optional[dict] = None,  # {jump_id: [(start, end), ...]}
    peak_color: str = "#facc15",
) -> go.Figure:
    """Ein Chart mit einer Kurve pro Sprung."""
    fig = _base_figure(unit, height=height)

    # Peak-Sektoren des gescrubten Sprungs als Hintergrund
    if peak_sectors_by_jump:
        for jump_id, sectors in peak_sectors_by_jump.items():
            for start, end in sectors:
                fig.add_vrect(
                    x0=start,
                    x1=end,
                    fillcolor=peak_color,
                    opacity=0.12,
                    line_width=0,
                    layer="below",
                )

    for j in jumps:
        df = j.df
        valid = df[df[y_col].notna() & df["pos"].notna()]
        if valid.empty:
            continue
        label = f"{j.meta.last_name}"
        if j.meta.round_:
            label += f" · {j.meta.round_}"
        if j.meta.date:
            label += f" · {j.meta.date}"

        fig.add_trace(
            go.Scatter(
                x=valid["pos"],
                y=valid[y_col],
                mode="lines",
                name=label,
                line=dict(color=j.color, width=2, shape="spline", smoothing=0.8),
                fill="tozeroy" if fill else None,
                fillcolor=f"rgba{_hex_to_rgba(j.color, 0.1)}" if fill else None,
                hovertemplate=f"<b>{label}</b><br>%{{x:.1f}} m · %{{y:.2f}} {unit}<extra></extra>",
            )
        )

    _add_landing_markers(fig, jumps)
    if scrub_pos is not None and scrub_color:
        _add_scrub_marker(fig, scrub_pos, scrub_color)
    return fig


def make_dual_series_chart(
    jumps: List[Jump],
    series: list[tuple[str, str, bool]],  # List of (col, label, dashed)
    unit: str,
    scrub_pos: Optional[float] = None,
    scrub_color: Optional[str] = None,
    height: int = 300,
) -> go.Figure:
    """Chart mit mehreren Serien pro Sprung (z.B. V_h und V_v zusammen)."""
    fig = _base_figure(unit, height=height)

    for j in jumps:
        for col, series_label, dashed in series:
            df = j.df
            valid = df[df[col].notna() & df["pos"].notna()]
            if valid.empty:
                continue
            full_label = f"{j.meta.last_name} · {series_label}"
            fig.add_trace(
                go.Scatter(
                    x=valid["pos"],
                    y=valid[col],
                    mode="lines",
                    name=full_label,
                    line=dict(
                        color=j.color,
                        width=1.5 if dashed else 2,
                        shape="spline",
                        smoothing=0.8,
                        dash="dash" if dashed else "solid",
                    ),
                    hovertemplate=f"<b>{full_label}</b><br>%{{x:.1f}} m · %{{y:.2f}} {unit}<extra></extra>",
                )
            )

    _add_landing_markers(fig, jumps)
    if scrub_pos is not None and scrub_color:
        _add_scrub_marker(fig, scrub_pos, scrub_color)
    return fig


# ─── Mini-Tracks für den Inspector ───────────────────────────────────────

MINI_LAYOUT = dict(
    plot_bgcolor="#181b22",
    paper_bgcolor="#181b22",
    font=dict(family="JetBrains Mono, monospace", size=9, color="#70757f"),
    margin=dict(l=0, r=0, t=4, b=4),
    xaxis=dict(visible=False, fixedrange=True),
    yaxis=dict(visible=False, fixedrange=True, zeroline=True, zerolinecolor="#484c55"),
    hovermode=False,
    showlegend=False,
    height=60,
)


def make_mini_track(
    jump: Jump,
    series: list[tuple[str, str]],  # List of (col, color)
    scrub_pos: Optional[float],
    fill_first: bool = False,
    peak_sectors: Optional[list[tuple[float, float]]] = None,
    peak_color: str = "#facc15",
) -> go.Figure:
    """Kompakter Verlaufs-Chart für den Inspector."""
    fig = go.Figure()
    fig.update_layout(**MINI_LAYOUT)

    # Peak-Sektoren als gelbe Hintergrund-Bänder
    if peak_sectors:
        for start, end in peak_sectors:
            fig.add_vrect(
                x0=start,
                x1=end,
                fillcolor=peak_color,
                opacity=0.18,
                line_width=0,
                layer="below",
            )

    for i, (col, color) in enumerate(series):
        valid = jump.df[jump.df[col].notna() & jump.df["pos"].notna()]
        if valid.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=valid["pos"],
                y=valid[col],
                mode="lines",
                line=dict(color=color, width=1.5, shape="spline", smoothing=0.8),
                fill="tozeroy" if (fill_first and i == 0) else None,
                fillcolor=f"rgba{_hex_to_rgba(color, 0.12)}" if (fill_first and i == 0) else None,
            )
        )

    # Scrubber-Linie
    if scrub_pos is not None:
        fig.add_vline(
            x=scrub_pos,
            line=dict(color=jump.color, width=1.5),
            opacity=0.85,
        )

    return fig


# ─── Helpers ─────────────────────────────────────────────────────────────

def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """'#ff2d2d' + 0.1 → '(255, 45, 45, 0.1)'"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"({r}, {g}, {b}, {alpha})"
