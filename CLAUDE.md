# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Astrophotography weather forecasting system for Wietesch/Rheine, Germany (52.17°N, 7.25°E). Combines meteoblue Astronomy Seeing API forecasts with CloudWatcher Solo ground truth measurements and AllSky camera imagery, storing everything in Supabase for ML training and Grafana visualization.

**Goal:** Build a local ML model that corrects meteoblue cloud forecasts using ground truth data, answering: *"Is it worth setting up the telescope tonight?"*

## Commands

```bash
# Single update (for cron/Synology Task Scheduler, every 5 min)
python3 scheduler.py --single

# Force meteoblue fetch (ignores hourly time check)
python3 scheduler.py --single --force-mb

# Test CloudWatcher Solo connection
python3 scheduler.py --test-cw

# Test meteoblue API connection
python3 scheduler.py --test-mb

# Show current status
python3 scheduler.py --status

# Run as daemon (continuous operation)
python3 scheduler.py --daemon
```

**Production path on Synology NAS:**
```
/volume1/homes/klaasjoerg/astro_weather_script/astro_weather/
```

## Architecture

### Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ CloudWatcher    │     │ meteoblue API   │     │ AllSky Oculus   │     │ AllSky ZWO      │
│ Solo            │     │ Astro Seeing    │     │ (Mono, Night)   │     │ (Color, 24h)    │
│ 192.168.1.151   │     │                 │     │                 │     │                 │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │ HTTP/5min             │ REST/60min             │ rsync/1min            │ rsync/1min (jpg)
         │                       │                       │                       │ rsync/5min (fits)
         ▼                       ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                           Synology NAS (scheduler.py)                                       │
│  • Poll CloudWatcher every 5 min                                                            │
│  • Fetch meteoblue forecast hourly (minute 0-9)                                             │
│  • Link AllSky Oculus + ZWO images + ZWO FITS to each reading                               │
│  • Detect observation windows, send Pushover notifications                                  │
└────────────────────────────────┬────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                              Supabase (PostgreSQL)                                          │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────┐  ┌───────────────────┐  │
│  │ cloudwatcher_      │  │ meteoblue_hourly   │  │ observation_   │  │ notification_     │  │
│  │ readings           │  │ (archived, INSERT) │  │ windows        │  │ queue             │  │
│  │ + allsky_url       │  │                    │  │                │  │                   │  │
│  │ + zwo_url          │  │                    │  │                │  │                   │  │
│  │ + zwo_fits_url     │  │                    │  │                │  │                   │  │
│  └────────────────────┘  └────────────────────┘  └────────────────┘  └───────────────────┘  │
└────────────────────────────┬────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Grafana Cloud   │
                    │ (Dashboards)    │
                    └─────────────────┘
```

### Key Modules

- `scheduler.py` — Main orchestrator with `AstroWeatherDB` class. Handles polling intervals, AllSky image linking, and notification dispatch.
- `cloudwatcher_client.py` — HTTP client for CloudWatcher Solo at `192.168.1.151/cgi-bin/cgiLastData`. Parses key=value response format.
- `meteoblue_client.py` — API client for meteoblue Astronomy Seeing package. `AstroConditions` dataclass with `astro_score` (0-100) calculation.
- `run_update.sh` — Shell wrapper for Synology Task Scheduler (sources `.env`, runs `scheduler.py --single`).

### AllSky Image Helpers (in scheduler.py)

- `find_allsky_image(timestamp)` — Finds Oculus AllSky JPG within 6 minutes before timestamp
- `find_zwo_image(timestamp)` — Finds ZWO AllSky JPG within 6 minutes before timestamp
- `find_zwo_fits(timestamp)` — Finds ZWO FITS raw file within 8 minutes before timestamp

All use glob pattern matching on UTC-timestamped filenames.

## Database Schema

### cloudwatcher_readings
| Column | Type | Notes |
|--------|------|-------|
| timestamp | TIMESTAMPTZ | Reading time (UTC) |
| sky_temperature | DECIMAL | IR sky temp (°C) |
| ambient_temperature | DECIMAL | Ambient temp (°C) |
| sky_minus_ambient | DECIMAL | Cloud indicator |
| sky_quality | TEXT | CLEAR / CLOUDY / UNKNOWN |
| sky_quality_raw | INT | 0=Unknown, 1=Safe, 2=Unsafe |
| light_sensor | DECIMAL | SQM (mpsas) |
| safe | INT | Overall: 1=Safe, 0=Unsafe |
| allsky_url | TEXT | Path to Oculus AllSky JPG |
| zwo_url | TEXT | Path to ZWO AllSky JPG |
| zwo_fits_url | TEXT | Path to ZWO FITS raw file |
| raw_json | JSONB | Complete raw response |

### meteoblue_hourly
| Column | Type | Notes |
|--------|------|-------|
| timestamp | TIMESTAMPTZ | Forecast target time |
| fetched_at | TIMESTAMPTZ | When forecast was retrieved |
| seeing_arcsec | DECIMAL | Astronomical seeing |
| totalcloud | INT | Total cloud cover (%) |
| astro_score | INT | Calculated score (0-100) |
| zenith_angle | DECIMAL | >108° = astronomical night |

**Important:** Uses INSERT (not UPSERT) to archive all forecast versions for ML training. Each hourly slot gets multiple rows with different `fetched_at` timestamps.

## Critical Design Decisions

### CloudWatcher Solo Safe Flags (confirmed by Lunatico developer)
```
0 = Unknown
1 = Safe      ✅
2 = Unsafe    ❌
```
This applies to: `cloudsSafe`, `lightSafe`, `rainSafe`, `windSafe`, `safe`

Code checks `== 1` for safe conditions. The `sky_quality_name` maps: 1→CLEAR, 2→CLOUDY, 0→UNKNOWN.

### CloudWatcher URL Endpoint
```
http://192.168.1.151/cgi-bin/cgiLastData
```
(Changed from older `/cgi-bin/lastData.pl`)

### meteoblue Archival Strategy
Every hourly fetch stores ALL 168 forecast hours (7 days) as new rows. This preserves forecast evolution for ML training — enables comparing first vs. last forecast for any given hour.

### AllSky File Paths
```
Oculus:  /volume1/AllSky-Rheine/{YYYY-MM-DD}/jpg/{YYYYMMDDTHHMMSSz}.jpg
ZWO JPG: /volume1/AllSky-Rheine/zwo/{YYYY-MM-DD}/jpg/zwo_{YYYYMMDDTHHMMSSz}.jpg
ZWO FITS: /volume1/AllSky-Rheine/zwo/{YYYY-MM-DD}/fits/zwo_{YYYYMMDDTHHMMSSz}.fit
```

**AllSky rsync uses UTC date for folder names** (not local time). Fixed to prevent midnight crossover bug where files after 00:00 UTC ended up in previous day's folder.

### Astro-Score Calculation
Score starts at 100, deductions:
- Clouds: `totalcloud * 0.5` (max -50)
- Seeing: `(arcsec - 1.0) * 15` (max -30)
- Jetstream: `(speed - 35) * 0.5` if >35 m/s (max -10)
- Moonlight: `moonlight * 0.15` if >30% (max -10)

Quality classes: Excellent (≥80), Good (≥60), Moderate (≥40), Poor (≥20), Bad (<20)

## Environment Variables

**Required:**
- `METEOBLUE_API_KEY` — meteoblue Astronomy Seeing API key

**Required for Supabase:**
- `SUPABASE_URL` — Project URL (e.g., `https://xxx.supabase.co`)
- `SUPABASE_KEY` — Anon key

**Optional:**
- `CLOUDWATCHER_HOST` — Default: `192.168.1.151`
- `ALLSKY_BASE_PATH` — Default: `/volume1/AllSky-Rheine`
- `PUSHOVER_USER` — Pushover user key
- `PUSHOVER_TOKEN` — Pushover app token
- `ASTRO_LAT` — Default: `52.17`
- `ASTRO_LON` — Default: `7.25`

## Synology Deployment

Script runs via Synology Task Scheduler every 5 minutes using `run_update.sh`.

- CloudWatcher: polled every run (5 min)
- meteoblue: only at minute 0-9 (effectively hourly)
- AllSky Oculus: synced every minute via cron on AllSky camera
- AllSky ZWO: JPGs every minute, FITS every 5 minutes via cron

Python 3.8 at `/usr/bin/python3.8` on Synology. Dependencies: `requests`, `supabase`, `python-dateutil`.

## Monitoring & Notifications

### Supabase pg_cron Jobs
- `check_data_freshness()` — Every 30 min, alerts if CloudWatcher >60min or meteoblue >120min stale
- `daily_status_report()` — Daily at 08:00 CET (07:00 UTC), pushes 24h stats with Oculus/ZWO link rates

### Pushover
Notifications dispatched via Supabase Edge Function `pushover-notifier` which reads from `notification_queue`.

## Grafana Integration

Connected via Grafana Cloud → PostgreSQL data source.

**Connection:** Uses read-only user `grafanareader` via Supavisor pooler:
```
Host: aws-0-eu-central-1.pooler.supabase.com:5432
User: grafanareader.{PROJECT_REF}
Database: postgres
SSL: require
```

**Key query pattern for meteoblue:** Always use `DISTINCT ON (timestamp) ORDER BY timestamp, fetched_at DESC` to get only the latest forecast per hour (avoids duplicate archived rows).

**Forecast evolution query:** Join latest (`fetched_at DESC`) and earliest (`fetched_at ASC`) forecasts to compare prediction stability.

## ML Training (Planned)

After 2-4 weeks of data collection:

```
INPUT:  meteoblue forecast + time + season + pressure trend
OUTPUT: Corrected cloud probability for this location
GROUND TRUTH: CloudWatcher readings + AllSky images (Oculus + ZWO)
```

**Training pairs table:** `training_pairs` with meteoblue JSONB, cloudwatcher JSONB, `forecast_hours_ahead`, and `allsky_path`.

**Goal:** Learn local correction patterns like "westerly winds → meteoblue underestimates clouds by 15%" or "6h forecasts more accurate than 12h for this location."

## File Structure

```
astro-weather-forecast/
├── CLAUDE.md
├── README.md
├── LICENSE (MIT)
├── CHANGELOG.md
├── .gitignore
├── .env.example
├── astro_weather/
│   ├── scheduler.py              # Main orchestrator + AllSky helpers
│   ├── cloudwatcher_client.py    # CloudWatcher Solo HTTP client
│   ├── meteoblue_client.py       # meteoblue Astro API client
│   └── run_update.sh             # Synology Task Scheduler wrapper
├── sql/
│   └── supabase_schema.sql       # Complete DB schema + functions
├── allsky/
│   └── rsync-to-synology.sh      # AllSky camera sync (UTC-based folders)
└── docs/
    ├── INSTALLATION.md
    └── QUICKREF.md
```
