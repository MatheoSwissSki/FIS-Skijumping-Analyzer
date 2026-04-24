# Deployment auf Streamlit Community Cloud

Streamlit Community Cloud bietet **kostenloses Hosting** für öffentliche
Streamlit-Apps direkt aus GitHub-Repositories. Hier die Schritt-für-Schritt
Anleitung:

## Vorbereitung

### 1. GitHub-Repository erstellen

Auf [github.com/new](https://github.com/new):

- Repository-Name: `skijump-analyzer` (oder dein Wunschname)
- Visibility: **Public** (für kostenloses Streamlit-Hosting nötig)
- Keine README, keine `.gitignore` hinzufügen — die Dateien sind bereits lokal

### 2. Lokales Git-Repository initialisieren und pushen

```bash
cd skijump-analyzer

git init
git add .
git commit -m "Initial commit: Skijumping FIS Analyzer (Streamlit)"

git branch -M main
git remote add origin https://github.com/<DEIN-USERNAME>/skijump-analyzer.git
git push -u origin main
```

## Deployment

### 3. Streamlit Cloud Account

Gehe zu [share.streamlit.io](https://share.streamlit.io) und logge dich mit
deinem GitHub-Account ein. Bei Bedarf die Berechtigung zum Repo-Zugriff
erteilen.

### 4. App erstellen

Klicke auf **"New app"** und fülle aus:

- **Repository**: `<DEIN-USERNAME>/skijump-analyzer`
- **Branch**: `main`
- **Main file path**: `app.py`
- **App URL** (optional): gewünschte URL wählen, z.B. `skijumping-fis`

Dann **"Deploy!"** klicken.

### 5. Warten

Streamlit baut das Image und installiert die Abhängigkeiten aus
`requirements.txt`. Das dauert beim ersten Mal ca. 2–4 Minuten. Danach ist
die App live unter:

```
https://<dein-app-name>.streamlit.app
```

## Nach dem Deployment

### Automatische Updates

Jeder Push auf `main` deployed automatisch neu — kein extra Befehl nötig.

### Logs

In der Streamlit-Cloud-Oberfläche kann man unter **"Manage app"** die Live-Logs
anzeigen — hilfreich bei Fehlerdiagnose.

### Secrets (falls später nötig)

Wenn du API-Keys oder andere sensitive Daten verwenden willst, gehe zu
**Settings → Secrets** in Streamlit Cloud und trage sie im TOML-Format ein.
In der App dann über `st.secrets["MY_KEY"]` abrufbar.

### Custom Domain (optional)

Unter **Settings → Custom subdomain** lässt sich die URL anpassen.

## Alternative: Lokales Deployment

Falls du die App intern hosten willst (z.B. im Firmennetz), kannst du sie
auch mit einem einfachen Docker-Container laufen lassen:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Oder direkt als Systemservice:

```bash
streamlit run app.py --server.port 8501 --server.headless true
```

## Troubleshooting

### App startet nicht / Fehler beim Deployment

- Prüfe ob alle Abhängigkeiten in `requirements.txt` stehen
- Prüfe ob die Python-Version passt (Streamlit Cloud nutzt standardmäßig Python 3.11)
- Schaue in die Logs in der Streamlit-Cloud-Oberfläche

### App ist langsam

- Streamlit Community Cloud hat begrenzte Ressourcen (1 GB RAM)
- Für viele gleichzeitige Nutzer ist ein eigener Hosting-Provider empfehlenswert

### CSV-Upload funktioniert nicht

- Max. Upload-Größe in `.streamlit/config.toml` ist auf 50 MB gesetzt
- Falls größere Dateien nötig sind: Wert erhöhen
