# Contributing

## Development-Setup

```bash
git clone https://github.com/<user>/skijump-analyzer.git
cd skijump-analyzer

# Virtuelle Umgebung (empfohlen)
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt

# App starten mit Auto-Reload bei Code-Änderungen
streamlit run app.py
```

## Projekt-Struktur

Die App ist in klar getrennte Module aufgeteilt:

- **`app.py`** — Streamlit-UI, State-Management, Layout
- **`data_parser.py`** — CSV-Parsing, Dateinamen-Extraktion, Summary-Berechnung
- **`scene_renderer.py`** — SVG-Rendering für den Flight Inspector (Schanzenprofil, Avatar, Weiten-Marker)
- **`charts.py`** — Plotly-Chart-Helpers für die Vergleichsansicht

Bei neuen Features diese Trennung beibehalten.

## Code-Stil

- Type-Hints wo sinnvoll
- Dataclasses für Domain-Objekte (siehe `JumpMeta`, `JumpSummary`, `Jump`)
- Kommentare auf Deutsch sind OK, Variablennamen bitte Englisch
- Keine externen Dependencies ohne triftigen Grund — aktuell nur Streamlit, Pandas, Plotly

## Testen

Manueller Test-Flow:

1. App starten: `streamlit run app.py`
2. Beispiel-CSV aus `examples/` hochladen → sollte sofort sichtbar sein
3. Zweite CSV hochladen → Charts überlagern sich
4. Einen der Sprünge deaktivieren → Head-to-Head sollte bei 2 aktiven erscheinen
5. "Inspizieren" klicken → Flight Inspector öffnet sich, Slider scrubbt den Avatar

## Pull Requests

1. Fork
2. Feature-Branch: `git checkout -b feature/kurzname`
3. Lokal testen
4. Commit mit aussagekräftiger Message
5. Push + PR auf `main`

## Neue Features: Ideen-Backlog

Siehe [README](README.md#mitwirken) — dort stehen offene Features.
