"""
Rendert die Flight-Inspector-Szene als SVG-String:
Schanzenprofil aus Daten + Skispringer-Avatar + Weiten-Marker + V-Pfeil.
"""

from __future__ import annotations

import math
from typing import List, Optional

import pandas as pd

from data_parser import Jump


def render_scene_svg(
    inspect_jump: Jump,
    inspect_pos: float,
    all_active_jumps: List[Jump],
    width: int = 900,
    height: int = 420,
    peak_sectors: Optional[list[tuple[float, float]]] = None,
    peak_label: str = "",
    peak_color: str = "#facc15",
) -> str:
    """
    Liefert das fertige SVG als String.

    - inspect_jump: der gerade inspizierte Sprung (dessen Avatar gezeigt wird)
    - inspect_pos:  aktuelle Scrub-Position entlang der Flugdistanz
    - all_active_jumps: alle aktiven Sprünge (für Weiten-Marker)
    - peak_sectors: optionale (pos_start, pos_end)-Bereiche in denen der
      gewählte Parameter innerhalb 5% seines Maximums liegt — werden auf der
      Flugbahn als dicker gelber Overlay-Strich eingezeichnet
    - peak_label: Text der zum Peak-Overlay angezeigt wird (z.B. "Max Höhe")
    """
    W, H = width, height
    m_l, m_r, m_t, m_b = 40, 40, 30, 60
    plot_w = W - m_l - m_r
    plot_h = H - m_t - m_b

    # ─── Alle Sprünge die in die Szene sollen ───
    jumps_for_scene = [j for j in all_active_jumps if not j.df["x"].isna().all()]
    if inspect_jump.id not in {j.id for j in jumps_for_scene}:
        jumps_for_scene = [inspect_jump] + jumps_for_scene

    # ─── X-Range ───
    x_min, x_max = 0.0, 0.0
    for j in jumps_for_scene:
        x_max = max(x_max, j.df["x"].max(skipna=True) or 0)
    x_max = max(x_max, 50.0) + 8.0

    # ─── Y-Range: weltY = z (negativ beim Fallen); Boden = z - h ───
    y_min, y_max = float("inf"), float("-inf")
    for j in jumps_for_scene:
        if j.df["z"].notna().any():
            y_min = min(y_min, j.df["z"].min())
            y_max = max(y_max, j.df["z"].max())
            valid = j.df[j.df["z"].notna() & j.df["h"].notna()]
            if not valid.empty:
                y_min = min(y_min, (valid["z"] - valid["h"]).min())
    if not math.isfinite(y_min) or not math.isfinite(y_max):
        y_min, y_max = -120.0, 10.0
    y_max += 3
    y_min -= 3

    # Skalen
    scale_x = plot_w / (x_max - x_min)
    scale_y_raw = plot_h / (y_max - y_min)
    base_scale = min(scale_x, scale_y_raw)
    scale_used_x = base_scale
    scale_used_y = min(base_scale * 1.4, scale_y_raw)

    used_w = (x_max - x_min) * scale_used_x
    used_h = (y_max - y_min) * scale_used_y
    offset_x = (plot_w - used_w) / 2
    offset_y = (plot_h - used_h) / 2

    def to_x(wx: float) -> float:
        return m_l + offset_x + (wx - x_min) * scale_used_x

    def to_y(wy: float) -> float:
        return m_t + offset_y + (y_max - wy) * scale_used_y

    # ─── SVG bauen ───
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'style="width:100%;height:auto;display:block;background:linear-gradient(180deg,#0d1218 0%,#161c25 70%,#1f2733 100%);">'
    ]

    # ─── Hügel aus Daten ───
    hill_pts: list[tuple[float, float]] = []
    valid = inspect_jump.df[
        inspect_jump.df["x"].notna()
        & inspect_jump.df["z"].notna()
        & inspect_jump.df["h"].notna()
    ]
    for _, row in valid.iterrows():
        hill_pts.append((float(row["x"]), float(row["z"] - row["h"])))

    if len(hill_pts) > 1:
        # Anlaufschanze nach links extrapolieren
        (x1, y1), (x2, y2) = hill_pts[0], hill_pts[1]
        slope = (y2 - y1) / (x2 - x1 or 1)
        extend_x = x1 - 15
        hill_pts.insert(0, (extend_x, y1 - slope * (x1 - extend_x)))

        # Auslauf nach rechts (flacher werdend)
        (x2, y2), (x1, y1) = hill_pts[-1], hill_pts[-2]
        slope = (y2 - y1) / (x2 - x1 or 1)
        extend_x = x2 + 25
        hill_pts.append((extend_x, y2 + slope * (extend_x - x2) * 0.3))

    if hill_pts:
        # Hügel-Füllung
        d = f"M {to_x(hill_pts[0][0]):.1f} {to_y(hill_pts[0][1]):.1f}"
        for x, y in hill_pts[1:]:
            d += f" L {to_x(x):.1f} {to_y(y):.1f}"
        last_x_px = to_x(hill_pts[-1][0])
        first_x_px = to_x(hill_pts[0][0])
        d_fill = d + f" L {last_x_px:.1f} {H} L {first_x_px:.1f} {H} Z"
        parts.append(f'<path d="{d_fill}" fill="rgba(255,255,255,0.08)"/>')
        parts.append(
            f'<path d="{d}" fill="none" stroke="rgba(255,255,255,0.35)" '
            f'stroke-width="1.5" stroke-linejoin="round"/>'
        )

    # ─── Schanzentisch-Marker ───
    h0 = float(inspect_jump.df["h"].iloc[0]) if not inspect_jump.df.empty else 3.5
    table_x = to_x(0)
    table_y = to_y(-h0)
    parts.append(
        f'<line x1="{table_x}" y1="{table_y}" x2="{table_x}" y2="{table_y - 14}" '
        f'stroke="rgba(255,255,255,0.4)" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{table_x}" y="{table_y - 18}" text-anchor="middle" '
        f'font-family="monospace" font-size="10" fill="rgba(255,255,255,0.6)">Schanzentisch</text>'
    )

    # ─── X-Achsen-Beschriftung ───
    dv = 0
    while dv <= x_max:
        x_px = to_x(dv)
        parts.append(
            f'<text x="{x_px}" y="{H - 30}" text-anchor="middle" '
            f'font-family="monospace" font-size="10" fill="#70757f">{dv} m</text>'
        )
        dv += 30

    # ─── Flugbahn (komplett, transparent) ───
    path_d = ""
    for _, p in inspect_jump.df.iterrows():
        if pd.notna(p["x"]) and pd.notna(p["z"]):
            x_px, y_px = to_x(float(p["x"])), to_y(float(p["z"]))
            path_d += ("M" if not path_d else "L") + f"{x_px:.1f} {y_px:.1f} "
    if path_d:
        parts.append(
            f'<path d="{path_d}" fill="none" stroke="{inspect_jump.color}" '
            f'stroke-width="2" opacity="0.35" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    # ─── Bereits geflogener Teil ───
    flown_d = ""
    for _, p in inspect_jump.df.iterrows():
        if pd.isna(p["x"]) or pd.isna(p["z"]):
            continue
        if p["pos"] > inspect_pos:
            break
        x_px, y_px = to_x(float(p["x"])), to_y(float(p["z"]))
        flown_d += ("M" if not flown_d else "L") + f"{x_px:.1f} {y_px:.1f} "
    if flown_d:
        parts.append(
            f'<path d="{flown_d}" fill="none" stroke="{inspect_jump.color}" '
            f'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    # ─── Peak-Sektor-Overlays auf der Flugbahn ───
    # Für jeden (pos_start, pos_end)-Sektor zeichnen wir die entsprechenden
    # Flugbahn-Punkte als breite farbige Linie on top
    if peak_sectors:
        for start_pos, end_pos in peak_sectors:
            sector_d = ""
            for _, p in inspect_jump.df.iterrows():
                if pd.isna(p["x"]) or pd.isna(p["z"]):
                    continue
                if p["pos"] < start_pos or p["pos"] > end_pos:
                    continue
                x_px, y_px = to_x(float(p["x"])), to_y(float(p["z"]))
                sector_d += ("M" if not sector_d else "L") + f"{x_px:.1f} {y_px:.1f} "
            if sector_d:
                parts.append(
                    f'<path d="{sector_d}" fill="none" stroke="{peak_color}" '
                    f'stroke-width="6" stroke-linecap="round" stroke-linejoin="round" '
                    f'opacity="0.55"/>'
                )

    # ─── Flugweiten-Marker für alle aktiven Sprünge ───
    markers = []
    for j in jumps_for_scene:
        if j.summary.distance is None:
            continue
        last_valid = j.df[j.df["x"].notna()]
        if last_valid.empty:
            continue
        land_x = float(last_valid["x"].iloc[-1])
        markers.append({"jump": j, "distance": j.summary.distance, "land_x": land_x})

    markers.sort(key=lambda m: m["land_x"])
    last_marker_px = -float("inf")
    stack_level = 0
    for mk in markers:
        mx = to_x(mk["land_x"])
        if mx - last_marker_px < 60:
            stack_level += 1
        else:
            stack_level = 0
        last_marker_px = mx
        mk["stack"] = stack_level

    for mk in markers:
        mx = to_x(mk["land_x"])
        j = mk["jump"]
        is_current = j.id == inspect_jump.id
        opacity = 1.0 if is_current else 0.7
        top_y = m_t + 8
        bot_y = H - 32

        # Gestrichelte Linie
        parts.append(
            f'<line x1="{mx}" x2="{mx}" y1="{top_y}" y2="{bot_y}" '
            f'stroke="{j.color}" stroke-width="{1.5 if is_current else 1}" '
            f'stroke-dasharray="3 3" opacity="{opacity * 0.85}"/>'
        )

        # Distanz-Label oben
        label_text = f"{mk['distance']:.1f} m"
        label_w = len(label_text) * 6 + 12
        label_y = top_y + mk["stack"] * 18
        parts.append(
            f'<rect x="{mx - label_w/2}" y="{label_y - 12}" width="{label_w}" height="16" '
            f'fill="{j.color}" opacity="{opacity}"/>'
        )
        parts.append(
            f'<text x="{mx}" y="{label_y}" text-anchor="middle" '
            f'font-family="monospace" font-size="10" font-weight="600" fill="#fff">{label_text}</text>'
        )

        # Athleten-Kürzel unten
        parts.append(
            f'<text x="{mx}" y="{bot_y + 14}" text-anchor="middle" '
            f'font-family="monospace" font-size="9" fill="{j.color}" '
            f'opacity="{opacity}" letter-spacing="0.08em">{j.meta.last_name.upper()}</text>'
        )

    # ─── Avatar an aktueller Position ───
    from data_parser import interpolate_at
    point = interpolate_at(inspect_jump.df, inspect_pos)

    if point and pd.notna(point.get("x")) and pd.notna(point.get("z")):
        cx = to_x(point["x"])
        cy = to_y(point["z"])
        avatar_scale = min(plot_w, plot_h) * 0.05

        aoa = 0.0
        if pd.notna(point.get("aoa_l")) and pd.notna(point.get("aoa_r")):
            aoa = (point["aoa_l"] + point["aoa_r"]) / 2
        elif pd.notna(point.get("aoa_l")):
            aoa = point["aoa_l"]
        elif pd.notna(point.get("aoa_r")):
            aoa = point["aoa_r"]

        roll_avg = 0.0
        if pd.notna(point.get("roll_l")) and pd.notna(point.get("roll_r")):
            roll_avg = (abs(point["roll_l"]) + abs(point["roll_r"])) / 2

        opening = max(0, min(60, point.get("open", 0) or 0))

        flight_angle_deg = 0
        if pd.notna(point.get("v_h")) and pd.notna(point.get("v_v")):
            flight_angle_deg = math.degrees(math.atan2(-point["v_v"], point["v_h"]))
        body_deg = -(flight_angle_deg + aoa)

        # Ski-Konstruktor
        ski_len = avatar_scale * 4.5
        ski_w = max(1.5, avatar_scale * 0.3)
        half_open = opening / 2

        def make_ski(rot_deg):
            return (
                f'<g transform="rotate({rot_deg})">'
                f'<rect x="{-ski_len * 0.3}" y="{-ski_w/2}" width="{ski_len}" height="{ski_w}" '
                f'fill="#e2e8f0" rx="{ski_w/2}"/>'
                f'<rect x="{ski_len * 0.7 - 6}" y="{-ski_w/2}" width="6" height="{ski_w}" '
                f'fill="{inspect_jump.color}"/>'
                f'</g>'
            )

        roll_factor = math.cos(math.radians(roll_avg))

        avatar_g = (
            f'<g transform="translate({cx} {cy}) rotate({body_deg})">'
            f'{make_ski(-half_open)}'
            f'{make_ski(half_open)}'
            # Torso
            f'<ellipse cx="{-avatar_scale * 0.3}" cy="0" rx="{avatar_scale * 1.4}" '
            f'ry="{avatar_scale * 0.55 * roll_factor}" fill="#1a1f2b" '
            f'stroke="{inspect_jump.color}" stroke-width="1.5"/>'
            # Hals
            f'<line x1="{avatar_scale * 0.9}" y1="0" x2="{avatar_scale * 1.3}" y2="0" '
            f'stroke="{inspect_jump.color}" stroke-width="2"/>'
            # Kopf
            f'<circle cx="{avatar_scale * 1.3}" cy="0" r="{avatar_scale * 0.45 * roll_factor}" '
            f'fill="{inspect_jump.color}"/>'
            # Arme
            f'<line x1="{-avatar_scale}" y1="{-avatar_scale * 0.4 * roll_factor}" '
            f'x2="{avatar_scale * 0.6}" y2="{-avatar_scale * 0.9 * roll_factor}" '
            f'stroke="#1a1f2b" stroke-width="2.5" stroke-linecap="round"/>'
            f'<line x1="{-avatar_scale}" y1="{avatar_scale * 0.4 * roll_factor}" '
            f'x2="{avatar_scale * 0.6}" y2="{avatar_scale * 0.9 * roll_factor}" '
            f'stroke="#1a1f2b" stroke-width="2.5" stroke-linecap="round"/>'
            f'</g>'
        )
        parts.append(avatar_g)

        # Geschwindigkeitspfeil mit Beschriftung
        if pd.notna(point.get("v_h")) and pd.notna(point.get("v_v")) and pd.notna(point.get("v_r")):
            parts.append(
                '<defs><marker id="v-arrow-head" viewBox="0 0 10 10" refX="8" refY="5" '
                'markerWidth="6" markerHeight="6" orient="auto">'
                '<path d="M 0 0 L 10 5 L 0 10 Z" fill="#fff" opacity="0.85"/>'
                '</marker></defs>'
            )
            v_mag = max(30, min(80, point["v_r"] * 0.55))
            angle = math.atan2(-point["v_v"], point["v_h"])
            dx = math.cos(angle) * v_mag
            dy = -math.sin(angle) * v_mag  # SVG y invertiert

            label_offset = 12
            perp_x = -math.sin(angle) * label_offset
            perp_y = -math.cos(angle) * label_offset
            lx, ly = dx + perp_x, dy + perp_y
            label_text = f"v = {point['v_r']:.1f} km/h"
            label_w = len(label_text) * 5.5 + 10

            parts.append(
                f'<g transform="translate({cx} {cy})">'
                f'<line x1="0" y1="0" x2="{dx:.1f}" y2="{dy:.1f}" stroke="#fff" '
                f'stroke-width="2" opacity="0.85" marker-end="url(#v-arrow-head)"/>'
                f'<rect x="{lx - label_w/2:.1f}" y="{ly - 7:.1f}" width="{label_w}" height="14" '
                f'fill="rgba(24,27,34,0.85)" stroke="rgba(255,255,255,0.2)" stroke-width="0.5" rx="2"/>'
                f'<text x="{lx:.1f}" y="{ly + 3:.1f}" text-anchor="middle" '
                f'font-family="monospace" font-size="10" font-weight="500" fill="#fff">{label_text}</text>'
                f'</g>'
            )

    # ─── Peak-Legende links oben (falls Peak-Overlay aktiv) ───
    if peak_sectors and peak_label:
        legend_x = m_l + 10
        legend_y = m_t + 14
        parts.append(
            f'<rect x="{legend_x - 6}" y="{legend_y - 10}" width="180" height="20" '
            f'fill="rgba(10,11,13,0.75)" stroke="rgba(250,204,21,0.3)" stroke-width="1" rx="2"/>'
        )
        parts.append(
            f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 16}" y2="{legend_y}" '
            f'stroke="{peak_color}" stroke-width="4" opacity="0.7" stroke-linecap="round"/>'
        )
        parts.append(
            f'<text x="{legend_x + 22}" y="{legend_y + 3}" '
            f'font-family="monospace" font-size="9" fill="#facc15" '
            f'letter-spacing="0.1em" text-transform="uppercase">{peak_label} · within 5% of max</text>'
        )

    parts.append("</svg>")
    return "".join(parts)
