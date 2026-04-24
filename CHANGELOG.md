# Changelog

## [1.0.0] - 2026-04-23

### Initial Release — Streamlit-Version

Komplette Neuimplementierung der HTML-Version in Python mit Streamlit,
deployment-ready für Streamlit Community Cloud.

### Features

- **CSV-Upload** mit Drag & Drop (Streamlit `file_uploader`)
- **Automatisches Dateinamen-Parsing** (Athlet, Nation, Runde, Datum)
- **Sprungkarten** mit Kennzahlen-Übersicht (Distanz, V₀, V max, Max Höhe, Y-Drift)
- **Im Vergleich aktivieren/deaktivieren** pro Sprung
- **Überlagerte Plotly-Charts** aller aktiven Sprünge:
  - Flugkurve · Höhe über Grund (mit Flächenfüllung)
  - Resultierende Geschwindigkeit
  - Horizontal vs. Vertikal
  - Anstellwinkel links/rechts
  - Roll-Winkel links/rechts
  - Top View · Y-Drift
- **Head-to-Head** bei 2 aktiven Sprüngen mit grün/rot Highlight
- **Best/Worst** Highlight in der Kennzahlentabelle bei ≥ 2 Sprüngen
- **Flight Inspector** mit:
  - Schanzenprofil aus X/Z-Daten rekonstruiert
  - 2D-Skispringer-Avatar (V-Stellung, AoA, Roll)
  - Beschrifteter Geschwindigkeitspfeil
  - Weiten-Marker für alle aktiven Sprünge
  - 4 Mini-Verlaufstracks (Höhe, AoA L/R, Roll L/R, Geschwindigkeit)
  - Scrub-Slider entlang der Flugdistanz

### Technisch

- `app.py` — Streamlit-UI, State, Layout
- `data_parser.py` — CSV-Parsing mit pandas, lineare Interpolation
- `scene_renderer.py` — reines SVG-Rendering (kein Canvas, keine JS-Animation)
- `charts.py` — Plotly-Helpers im dunklen Theme
- `.streamlit/config.toml` — Dunkles Theme, rote Akzente
- GitHub Actions: Lint/Syntax-Check bei jedem Push

## [1.1.0] - 2026-04-23

### Added

- **Erweiterter Athletenvergleich** — für jeden Parameter werden jetzt sowohl
  Maximalwerte als auch Durchschnittswerte (über die Flugphase) angezeigt:
  - Geschwindigkeit: max + Ø
  - Flughöhe: max + Ø
  - Anstellwinkel Links/Rechts: max + Ø
  - Roll-Winkel Links/Rechts: max + Ø
  - Opening Angle: max + Ø
- **Peak-Sektor-Analyse (Within 5% of Max)** — Flight Inspector hat jetzt
  klickbare Parameter-Buttons:
  - Keine Hervorhebung
  - Flughöhe
  - Geschwindigkeit
  - Anstellwinkel Links / Rechts
  - Roll-Winkel Links / Rechts
- Bei Auswahl eines Parameters werden die Bereiche, in denen dieser innerhalb
  5% seines Maximums liegt, visuell hervorgehoben:
  - Als **dicke gelbe Linie direkt auf der Flugbahn** in der Flight-Inspector-Szene
  - Als **gelbe Bänder im Hintergrund** des passenden Mini-Charts
  - Als **gelbe Bänder im Hintergrund** des passenden großen Vergleichs-Charts
  - Mit Legende oben links in der Szene
- **Neutral-Direction** für Winkel-Metriken eingeführt — AoA und Roll bekommen
  kein grün/rot mehr, da weder "mehr" noch "weniger" eindeutig besser ist.

### Technisch

- Neue Funktion `peak_sectors()` in `data_parser.py` — findet
  zusammenhängende Sektoren mit konfigurierbarer Toleranz, schließt
  Landeanomalie aus
- `JumpSummary` erweitert: `avg_v_r`, `avg_h`, `max_aoa_l`, `avg_aoa_l`,
  `max_aoa_r`, `avg_aoa_r`, `max_roll_l`, `avg_roll_l`, `max_roll_r`,
  `avg_roll_r`, `max_open`, `avg_open`
- METRICS-Definition gruppiert (result/speed/height/aoa/roll/open/stability)
- `make_mini_track()` und `make_single_series_chart()` akzeptieren jetzt
  `peak_sectors` bzw. `peak_sectors_by_jump` als Overlay-Input
- `render_scene_svg()` akzeptiert `peak_sectors`, `peak_label` und
  `peak_color` für das Overlay
