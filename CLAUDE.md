# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Astrophotography weather forecasting system for Wietesch/Rheine (52.17°N, 7.25°E). Combines meteoblue weather API data with CloudWatcher Solo ground truth measurements, storing everything in Supabase.

## Commands

```bash
# Test meteoblue API connection
python astro_weather/meteoblue_client.py

# Test CloudWatcher Solo connection
python astro_weather/cloudwatcher_client.py --test

# Show configuration
python astro_weather/config.py

# Single update (for cron/Synology Task Scheduler)
python astro_weather/scheduler.py --single

# Run as daemon (continuous operation)
python astro_weather/scheduler.py --daemon

# Force meteoblue fetch (ignores time check)
python astro_weather/scheduler.py --single --force-mb

# Show current status
python astro_weather/scheduler.py --status
```

## Architecture

### Data Flow
1. **meteoblue API** → hourly astro forecasts (seeing, clouds, jetstream, moonlight) → `meteoblue_hourly` table
2. **CloudWatcher Solo** → 5-minute ground truth readings (sky temp, SQM, humidity) → `cloudwatcher_readings` table
3. **Scheduler** combines both, finds observation windows, sends Pushover notifications

### Key Modules
- `meteoblue_client.py`: API client with `AstroConditions` dataclass, calculates astro_score (0-100)
- `cloudwatcher_client.py`: HTTP client for Solo device at `192.168.1.151`, parses key=value response
- `supabase_client.py`: Database wrapper with `AstroDatabase` class
- `scheduler.py`: Main orchestrator with `AstroWeatherDB` class, handles polling intervals
- `config.py`: Central configuration dictionary, reads from environment variables

### Astro-Score Calculation
Score starts at 100, deductions:
- Clouds: `totalcloud * 0.5` (max -50)
- Seeing: `(arcsec - 1.0) * 15` (max -30)
- Jetstream: `(speed - 35) * 0.5` if >35 m/s (max -10)
- Moonlight: `moonlight * 0.15` if >30% (max -10)

### Environment Variables
Required: `METEOBLUE_API_KEY`
Optional: `SUPABASE_URL`, `SUPABASE_KEY`, `CLOUDWATCHER_HOST`, `PUSHOVER_USER`, `PUSHOVER_TOKEN`

### Synology Deployment
Use `run_update.sh` with Synology Task Scheduler. Runs as cron every 5 minutes - CloudWatcher polled each time, meteoblue only at minute 0-9 (hourly).
