# 🔭 Astrophotographie Vorhersage-System

Lokales Wettervorhersage-System optimiert für Astrophotographie am Standort **Wietesch/Rheine**.

## ✨ Features

- **Seeing-Vorhersage** in Bogensekunden (arcsec)
- **Jet Stream & Bad Layers** Analyse
- **Wolkenschichten** (Low/Mid/High)
- **Nightsky Brightness** in Lux
- **Mondlicht** und astronomische Dämmerung
- **Automatische Beobachtungsfenster-Erkennung**
- **Astro-Score** (0-100) für schnelle Bewertung
- **Ground Truth** Integration mit CloudWatcher Solo
- **ML-Training Data** für lokale Vorhersage-Verbesserung

## 📊 Datenquellen

| Quelle | Daten | Kosten |
|--------|-------|--------|
| **meteoblue** | Seeing, Clouds, Moonlight, Jet Stream | ~40k Credits/Call |
| **CloudWatcher Solo** | Sky Temperature (Ground Truth) | Hardware vorhanden |
| **Open-Meteo** (optional) | ICON-D2 Backup | Kostenlos |

## 🚀 Quick Start

### 1. Installation

```bash
# Repository klonen oder Dateien kopieren
cd astro_weather

# Dependencies installieren
pip install -r requirements.txt
```

### 2. Konfiguration

Setze Umgebungsvariablen:

```bash
# Pflicht
export METEOBLUE_API_KEY="YOUR_METEOBLUE_API_KEY"

# Optional (für Datenspeicherung)
export SUPABASE_URL="https://YOUR_PROJECT.supabase.co"
export SUPABASE_KEY="eyJ..."

# Optional (für Benachrichtigungen)
export PUSHOVER_USER="..."
export PUSHOVER_TOKEN="..."
```

### 3. Test

```bash
# Teste meteoblue API
python meteoblue_client.py

# Zeige Konfiguration
python config.py
```

## 📁 Projektstruktur

```
astro_weather/
├── meteoblue_client.py    # API Client für meteoblue
├── supabase_client.py     # Datenbank-Integration
├── config.py              # Konfiguration
├── supabase_schema.sql    # Datenbank-Schema
├── requirements.txt       # Python Dependencies
└── README.md              # Diese Datei
```

## 🌤️ meteoblue API

### Verfügbare Variablen (getestet ✓)

| Variable | Beschreibung |
|----------|--------------|
| `seeing_arcsec` | Seeing in Bogensekunden |
| `seeing1`, `seeing2` | Seeing Index 1-5 |
| `jetstream` | Jet Stream Speed (m/s) |
| `badlayer_bottom/top/gradient` | Bad Layers |
| `totalcloudcover` | Gesamtbewölkung (%) |
| `lowclouds/midclouds/highclouds` | Wolkenschichten |
| `nightskybrightness_actual` | Himmelshelligkeit (Lux) |
| `moonlight_actual` | Mondlicht (% of full) |
| `zenithangle` | Sonnenstand (>108° = astro. Nacht) |

### API Call

```python
from meteoblue_client import MeteoblueAstroClient

client = MeteoblueAstroClient(
    api_key="YOUR_METEOBLUE_API_KEY",
    lat=52.17,
    lon=7.25
)

# 7-Tage Vorhersage
conditions = client.fetch_astro_forecast(forecast_days=7)

# Beste Beobachtungsfenster
windows = client.get_best_windows(conditions, min_score=60)
```

### Credits-Verbrauch

| Paket | Credits/Call |
|-------|--------------|
| basic-1h | ~8.000 |
| clouds-1h | ~10.000 |
| moonlight-1h | ~10.000 |
| seeing-1h | ~10.000 (geschätzt) |
| **Kombiniert** | **~40.000** |

Mit 10 Mio Free Trial Credits: **~250 Calls** = ~10 Tage bei stündlichem Update.

## 📈 Astro-Score

Der Astro-Score (0-100) kombiniert alle Faktoren:

```
Score = 100
      - (clouds * 0.5)           # max -50
      - ((seeing - 1.0) * 15)    # max -30
      - ((jetstream - 35) * 0.5) # max -10
      - (moonlight * 0.15)       # max -10
```

| Score | Qualität | Bedeutung |
|-------|----------|-----------|
| 85+ | 🌟 EXCELLENT | Perfekte Nacht |
| 70-84 | ✨ GOOD | Sehr gut |
| 50-69 | ⭐ AVERAGE | Brauchbar |
| 30-49 | ☁️ POOR | Suboptimal |
| <30 | ❌ BAD | Nicht beobachten |

## 🔭 Seeing-Klassifikation

| Arcseconds | Qualität | Geeignet für |
|------------|----------|--------------|
| <0.8" | Excellent | Planeten, HR-Imaging |
| 0.8-1.2" | Very Good | Galaxien-Details |
| 1.2-1.5" | Good | Deep Sky |
| 1.5-2.0" | Average | Helle Nebel |
| 2.0-2.5" | Below Avg | Große Objekte |
| 2.5-3.0" | Poor | Nur Widefield |
| >3.0" | Bad | Nur visuell |

## 🗄️ Supabase Setup

1. Erstelle ein Supabase Projekt: https://supabase.com
2. Führe das Schema aus:

```bash
# In Supabase SQL Editor:
# Kopiere Inhalt von supabase_schema.sql
```

3. Hole die Credentials aus Project Settings → API

## 🔄 Automatisierung

### Cron Job (Linux)

```bash
# Stündlicher Update
0 * * * * cd /path/to/astro_weather && python -c "from supabase_client import run_hourly_update; run_hourly_update(config)" >> /var/log/astro_weather.log 2>&1
```

### Systemd Service

```ini
[Unit]
Description=Astro Weather Service
After=network.target

[Service]
Type=simple
User=joerg
WorkingDirectory=/path/to/astro_weather
ExecStart=/usr/bin/python3 scheduler.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 📊 Beispiel-Output

```
===============================================================
NÄCHSTE 24 STUNDEN:
---------------------------------------------------------------
🌙 23:00 | Score: 78 ✨ | Seeing: 1.3" | Clouds: 12% | Jet: 22m/s
🌙 00:00 | Score: 82 ✨ | Seeing: 1.1" | Clouds: 8%  | Jet: 20m/s
🌙 01:00 | Score: 85 🌟 | Seeing: 0.9" | Clouds: 5%  | Jet: 18m/s
🌙 02:00 | Score: 87 🌟 | Seeing: 0.8" | Clouds: 3%  | Jet: 15m/s
...

BESTE FENSTER:
---------------------------------------------------------------
1. Fr 24.01. 01:00 - 05:00
   Dauer: 4h | Ø Score: 85 | Ø Seeing: 0.9" | Ø Wolken: 4%
===============================================================
```

## 🛠️ Troubleshooting

### API Error 400
- Paketname falsch geschrieben
- Kombination nicht unterstützt

### API Error 401
- API Key ungültig oder abgelaufen

### Keine Daten
- Koordinaten prüfen
- Zeitzone prüfen

## 📝 Roadmap

- [ ] CloudWatcher Solo Integration
- [ ] Telegram Bot für Benachrichtigungen
- [ ] Web Dashboard
- [ ] ML-Modell für lokale Korrektur
- [ ] Open-Meteo Fallback
- [ ] Satellitenbilder-Integration

## 📜 Lizenz

Privates Projekt für Joerg @ Wietesch

## 🙏 Credits

- [meteoblue](https://www.meteoblue.com) - Wetterdaten & Seeing
- [Supabase](https://supabase.com) - Datenbank
- [Lunatico](https://lunatico.es) - CloudWatcher Hardware
