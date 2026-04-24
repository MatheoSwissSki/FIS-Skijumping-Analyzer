"""CSV-Parsing und Sprung-Datenaufbereitung."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import StringIO
from typing import Optional

import pandas as pd


@dataclass
class JumpMeta:
    """Metadaten eines Sprungs aus dem Dateinamen."""
    file_name: str
    last_name: str = "Unknown"
    first_name: str = ""
    nation: str = ""
    round_: str = ""
    date: str = ""
    time: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def subtitle(self) -> str:
        parts = [self.nation, self.round_, self.date]
        return " · ".join(p for p in parts if p)


@dataclass
class JumpSummary:
    """Aggregierte Kennzahlen eines Sprungs."""
    distance: Optional[float] = None
    v_h0: Optional[float] = None
    # Maxima
    v_r_max: Optional[float] = None
    v_v_max: Optional[float] = None
    v_v_max_abs: Optional[float] = None
    max_h: Optional[float] = None
    max_aoa_l: Optional[float] = None
    max_aoa_r: Optional[float] = None
    max_roll_l: Optional[float] = None
    max_roll_r: Optional[float] = None
    max_open: Optional[float] = None
    # Durchschnitte (nur über Flugphase, pos > 5m)
    avg_v_r: Optional[float] = None
    avg_h: Optional[float] = None
    avg_aoa_l: Optional[float] = None
    avg_aoa_r: Optional[float] = None
    avg_roll_l: Optional[float] = None
    avg_roll_r: Optional[float] = None
    avg_open: Optional[float] = None
    # Sonstiges
    y_drift: Optional[float] = None
    roll_asym_avg: Optional[float] = None


@dataclass
class Jump:
    """Ein kompletter Sprung mit Metadaten, Messpunkten und Kennzahlen."""
    id: str
    color: str
    meta: JumpMeta
    df: pd.DataFrame                     # Spalten: pos, h, x, y, z, open, aoa_l, aoa_r, roll_l, roll_r, v_h, v_v, v_r
    summary: JumpSummary
    active: bool = True


# ─────────────────────────────────────────────────────────────────────────
# Dateinamen-Parser
# ─────────────────────────────────────────────────────────────────────────

def parse_file_name(file_name: str) -> JumpMeta:
    """
    Extrahiert Metadaten aus FIS-Dateinamen wie
    '001_011_HAUSWIRTH_Sandro_SUI_1st_20260328-092940_C_OfficialResults.csv'
    """
    base = re.sub(r"\.csv$", "", file_name, flags=re.IGNORECASE)
    parts = base.split("_")
    meta = JumpMeta(file_name=file_name)

    # Finde Drei-Buchstaben-Nation (IOC-Code, Großbuchstaben)
    nat_idx = next(
        (i for i, p in enumerate(parts) if re.fullmatch(r"[A-Z]{3}", p)), -1
    )

    if nat_idx > 1:
        meta.last_name = parts[nat_idx - 2]
        meta.first_name = parts[nat_idx - 1]
        meta.nation = parts[nat_idx]
        if nat_idx + 1 < len(parts):
            meta.round_ = parts[nat_idx + 1]

        dt_match = next((p for p in parts if re.fullmatch(r"\d{8}-\d{6}", p)), None)
        if dt_match:
            y, mo, d = dt_match[0:4], dt_match[4:6], dt_match[6:8]
            hh, mm = dt_match[9:11], dt_match[11:13]
            meta.date = f"{d}.{mo}.{y}"
            meta.time = f"{hh}:{mm}"
    else:
        meta.last_name = parts[0] if parts else "Unknown"

    return meta


# ─────────────────────────────────────────────────────────────────────────
# CSV-Parser
# ─────────────────────────────────────────────────────────────────────────

# Mapping: Original-Spaltenname → interner Name
COLUMN_MAP = {
    "Position": "pos",
    "Height above ground [m]": "h",
    "X [m]": "x",
    "Y [m]": "y",
    "Z [m]": "z",
    "Opening Angle [°]": "open",
    "Stalling Angle Left [°]": "aoa_l",
    "Stalling Angle Right [°]": "aoa_r",
    "Roll Angle Left [°]": "roll_l",
    "Roll Angle Right [°]": "roll_r",
    "Speed hor. [km/h]": "v_h",
    "Speed vert. [km/h]": "v_v",
    "Speed resulting [km/h]": "v_r",
}


def parse_csv(content: bytes | str) -> pd.DataFrame:
    """
    Parst eine Swiss Timing FIS CSV. Das Format nutzt Semikolons und
    hat eine lange Wind-Sensor-Spalte am Ende die gequoted ist.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    df = pd.read_csv(
        StringIO(content),
        sep=";",
        engine="python",
        quotechar='"',
        on_bad_lines="skip",
    )

    # Nur die uns interessierenden Spalten behalten und umbenennen
    keep = {orig: new for orig, new in COLUMN_MAP.items() if orig in df.columns}
    df = df[list(keep.keys())].rename(columns=keep)

    # Numerische Konvertierung (leere Strings und 'NaN' → NaN)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Nur Zeilen mit gültiger, nicht-negativer Position behalten
    df = df[df["pos"].notna() & (df["pos"] >= 0)].copy()
    df = df.sort_values("pos").reset_index(drop=True)

    return df


# ─────────────────────────────────────────────────────────────────────────
# Summary-Berechnung
# ─────────────────────────────────────────────────────────────────────────

def summarize(df: pd.DataFrame) -> JumpSummary:
    """Aggregierte Kennzahlen aus dem Messpunkt-DataFrame."""
    s = JumpSummary()
    if df.empty:
        return s

    s.distance = float(df["pos"].max())

    # V_h0: erste Horizontal-Geschwindigkeit > 50 km/h (Absprung)
    v_h_valid = df[df["v_h"].notna() & (df["v_h"] > 50)]
    if not v_h_valid.empty:
        s.v_h0 = float(v_h_valid["v_h"].iloc[0])

    # Flugphase für Durchschnitte (ab pos > 5m, ohne letzten Landepunkt)
    flight = df[(df["pos"] > 5) & (df["pos"] < df["pos"].max())]
    if flight.empty:
        flight = df

    # Maxima und Durchschnitte für Geschwindigkeit
    if df["v_r"].notna().any():
        s.v_r_max = float(df["v_r"].max())
        s.avg_v_r = float(flight["v_r"].mean()) if flight["v_r"].notna().any() else None

    if df["v_v"].notna().any():
        idx_max_abs = df["v_v"].abs().idxmax()
        s.v_v_max = float(df["v_v"].loc[idx_max_abs])
        s.v_v_max_abs = abs(s.v_v_max)

    # Höhe
    if df["h"].notna().any():
        s.max_h = float(df["h"].max())
        s.avg_h = float(flight["h"].mean()) if flight["h"].notna().any() else None

    # AoA links/rechts (Maxima absolut, Durchschnitte mit Vorzeichen)
    for col, max_attr, avg_attr in [
        ("aoa_l", "max_aoa_l", "avg_aoa_l"),
        ("aoa_r", "max_aoa_r", "avg_aoa_r"),
        ("roll_l", "max_roll_l", "avg_roll_l"),
        ("roll_r", "max_roll_r", "avg_roll_r"),
        ("open", "max_open", "avg_open"),
    ]:
        if col in df.columns and df[col].notna().any():
            # Max = größter Betrag (mit Vorzeichen)
            idx = df[col].abs().idxmax()
            setattr(s, max_attr, float(df[col].loc[idx]))
            # Durchschnitt über Flugphase
            if flight[col].notna().any():
                setattr(s, avg_attr, float(flight[col].mean()))

    if df["y"].notna().any():
        s.y_drift = float(df["y"].max() - df["y"].min())

    # Roll-Asymmetrie Ø
    flight_roll = df[(df["pos"] > 20) & df["roll_l"].notna() & df["roll_r"].notna()]
    if not flight_roll.empty:
        s.roll_asym_avg = float((flight_roll["roll_l"].abs() - flight_roll["roll_r"].abs()).abs().mean())

    return s


def peak_sectors(df: pd.DataFrame, col: str, use_abs: bool = False, tolerance: float = 0.05) -> list[tuple[float, float]]:
    """
    Findet zusammenhängende Sektoren (pos-Bereiche) in denen der Parameter
    innerhalb `tolerance` (Default 5%) seines Maximums liegt.

    Returns: Liste von (pos_start, pos_end) Tupeln.

    Wenn use_abs=True, wird |col| für Maximum und Vergleich genutzt (sinnvoll
    für Winkel die positiv/negativ sein können wie Roll).

    Die Landeanomalie (letzte 3m vor Aufprall) wird ignoriert, um nicht die
    Aufprall-Spikes zu finden.
    """
    if col not in df.columns or df[col].isna().all() or df.empty:
        return []

    # Landeanomalie ausklammern
    if len(df) > 1:
        max_pos = df["pos"].max()
        flight_df = df[df["pos"] < max_pos - 3].copy()
        if flight_df.empty:
            flight_df = df
    else:
        flight_df = df

    values = flight_df[col].abs() if use_abs else flight_df[col]
    max_val = values.max()
    if pd.isna(max_val) or max_val == 0:
        return []

    threshold = max_val * (1 - tolerance)
    in_peak = values >= threshold

    sectors = []
    in_sector = False
    start_pos = 0.0
    positions = flight_df["pos"].values
    mask = in_peak.values

    for i, (pos, is_peak) in enumerate(zip(positions, mask)):
        if is_peak and not in_sector:
            start_pos = pos
            in_sector = True
        elif not is_peak and in_sector:
            end_pos = positions[i - 1] if i > 0 else pos
            sectors.append((float(start_pos), float(end_pos)))
            in_sector = False

    if in_sector:
        sectors.append((float(start_pos), float(positions[-1])))

    # Nur Sektoren mit mindestens 2m Länge behalten
    sectors = [(s, e) for s, e in sectors if (e - s) >= 2.0]

    return sectors


def interpolate_at(df: pd.DataFrame, pos: float) -> dict:
    """
    Linear-interpolierter Messpunkt bei Distanz `pos`.
    Gibt ein Dict mit den gleichen Keys wie die DataFrame-Spalten zurück.
    """
    if df.empty:
        return {}

    if pos <= df["pos"].iloc[0]:
        return df.iloc[0].to_dict()
    if pos >= df["pos"].iloc[-1]:
        return df.iloc[-1].to_dict()

    # Finde umgebende Indizes
    lo = df["pos"].searchsorted(pos, side="right") - 1
    lo = max(0, min(len(df) - 2, lo))
    a = df.iloc[lo]
    b = df.iloc[lo + 1]

    denom = (b["pos"] - a["pos"]) or 1.0
    t = (pos - a["pos"]) / denom

    result = {}
    for col in df.columns:
        va, vb = a[col], b[col]
        if pd.isna(va) and pd.isna(vb):
            result[col] = float("nan")
        elif pd.isna(va):
            result[col] = float(vb)
        elif pd.isna(vb):
            result[col] = float(va)
        else:
            result[col] = float(va + (vb - va) * t)
    return result
