# Astro Weather Forecast

### *"Is it worth setting up the telescope tonight?"*

> **Smart astrophotography weather forecasting** that combines professional seeing predictions with local ground truth measurements to give you a reliable answer.

---

## The Problem

Every astrophotographer knows the frustration: you check the weather forecast, it says "clear skies", you spend 30 minutes setting up your equipment... and then clouds roll in. Or the seeing is so bad your images are unusable.

**Standard weather apps don't cut it for astrophotography.**

## The Solution

This system combines **three data sources** to give you accurate, location-specific predictions:

| | Source | What it provides |
|:--:|--------|------------------|
| **1** | **meteoblue Astronomy API** | Professional seeing forecasts, jet stream, cloud layers, astronomical twilight |
| **2** | **CloudWatcher Solo** | Real-time ground truth from your location (IR sky temp, SQM readings) |
| **3** | **AllSky Cameras** | Visual confirmation with timestamped images |

The result? An **Astro-Score (0-100)** that tells you at a glance whether tonight is worth your time.

---

## Key Features

| Feature | Description |
|:--------|:------------|
| **Seeing Forecast** | Arcsecond predictions - know if planetary or deep-sky imaging is possible |
| **Astro-Score** | Single 0-100 number combining clouds, seeing, jet stream, and moonlight |
| **Observation Windows** | Automatic detection of the best multi-hour windows |
| **Ground Truth** | CloudWatcher Solo validates forecasts with actual sky conditions |
| **ML Training** | Collects data to build a local correction model for your specific location |
| **Push Notifications** | Pushover alerts when conditions become favorable |
| **Grafana Dashboards** | Visual monitoring of all metrics over time |

---

## How It Works

```
Every 5 minutes:  CloudWatcher Solo  -->  Ground truth to Supabase
Every hour:       meteoblue API      -->  7-day forecast to Supabase
Continuous:       AllSky cameras     -->  Timestamped images linked to readings
                          |
                          v
                  Astro-Score calculation
                          |
                          v
              Good window detected? --> Pushover notification
```

---

## Data Sources

| Source | Data | Update Frequency |
|--------|------|------------------|
| **meteoblue** | Seeing, Clouds, Moonlight, Jet Stream | Hourly |
| **CloudWatcher Solo** | Sky Temp, SQM, Humidity, Rain | Every 5 min |
| **AllSky Oculus** | Night sky images (mono) | Every minute |
| **AllSky ZWO** | Color images + FITS | JPG/min, FITS/5min |

## Quick Start

### 1. Installation

```bash
# Clone repository or copy files
cd astro_weather

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Set environment variables:

```bash
# Required
export METEOBLUE_API_KEY="YOUR_METEOBLUE_API_KEY"

# Optional (for data storage)
export SUPABASE_URL="https://YOUR_PROJECT.supabase.co"
export SUPABASE_KEY="eyJ..."

# Optional (for notifications)
export PUSHOVER_USER="..."
export PUSHOVER_TOKEN="..."
```

### 3. Test

```bash
# Test meteoblue API
python meteoblue_client.py

# Show configuration
python config.py
```

## Project Structure

```
astro_weather/
├── meteoblue_client.py    # API client for meteoblue
├── supabase_client.py     # Database integration
├── config.py              # Configuration
├── supabase_schema.sql    # Database schema
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## meteoblue API

### Available Variables (tested)

| Variable | Description |
|----------|-------------|
| `seeing_arcsec` | Seeing in arcseconds |
| `seeing1`, `seeing2` | Seeing Index 1-5 |
| `jetstream` | Jet Stream Speed (m/s) |
| `badlayer_bottom/top/gradient` | Bad Layers |
| `totalcloudcover` | Total cloud cover (%) |
| `lowclouds/midclouds/highclouds` | Cloud layers |
| `nightskybrightness_actual` | Sky brightness (Lux) |
| `moonlight_actual` | Moonlight (% of full) |
| `zenithangle` | Sun position (>108° = astro night) |

### API Call

```python
from meteoblue_client import MeteoblueAstroClient

client = MeteoblueAstroClient(
    api_key="YOUR_METEOBLUE_API_KEY",
    lat=52.17,
    lon=7.25
)

# 7-day forecast
conditions = client.fetch_astro_forecast(forecast_days=7)

# Best observation windows
windows = client.get_best_windows(conditions, min_score=60)
```

### Credits Usage

| Package | Credits/Call |
|---------|--------------|
| basic-1h | ~8,000 |
| clouds-1h | ~10,000 |
| moonlight-1h | ~10,000 |
| seeing-1h | ~10,000 (estimated) |
| **Combined** | **~40,000** |

With 10M Free Trial Credits: **~250 Calls** = ~10 days with hourly updates.

## Astro-Score

The Astro-Score (0-100) combines all factors:

```
Score = 100
      - (clouds * 0.5)           # max -50
      - ((seeing - 1.0) * 15)    # max -30
      - ((jetstream - 35) * 0.5) # max -10
      - (moonlight * 0.15)       # max -10
```

| Score | Quality | Meaning |
|-------|---------|---------|
| 85+ | EXCELLENT | Perfect night |
| 70-84 | GOOD | Very good |
| 50-69 | AVERAGE | Usable |
| 30-49 | POOR | Suboptimal |
| <30 | BAD | Do not observe |

## Seeing Classification

| Arcseconds | Quality | Suitable for |
|------------|---------|--------------|
| <0.8" | Excellent | Planets, HR imaging |
| 0.8-1.2" | Very Good | Galaxy details |
| 1.2-1.5" | Good | Deep Sky |
| 1.5-2.0" | Average | Bright nebulae |
| 2.0-2.5" | Below Avg | Large objects |
| 2.5-3.0" | Poor | Widefield only |
| >3.0" | Bad | Visual only |

## Supabase Setup

1. Create a Supabase project: https://supabase.com
2. Run the schema:

```bash
# In Supabase SQL Editor:
# Copy contents of supabase_schema.sql
```

3. Get credentials from Project Settings -> API

## Automation

### Cron Job (Linux)

```bash
# Hourly update
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

## Example Output

```
===============================================================
NEXT 24 HOURS:
---------------------------------------------------------------
 23:00 | Score: 78 | Seeing: 1.3" | Clouds: 12% | Jet: 22m/s
 00:00 | Score: 82 | Seeing: 1.1" | Clouds: 8%  | Jet: 20m/s
 01:00 | Score: 85 | Seeing: 0.9" | Clouds: 5%  | Jet: 18m/s
 02:00 | Score: 87 | Seeing: 0.8" | Clouds: 3%  | Jet: 15m/s
...

BEST WINDOWS:
---------------------------------------------------------------
1. Fri 24.01. 01:00 - 05:00
   Duration: 4h | Avg Score: 85 | Avg Seeing: 0.9" | Avg Clouds: 4%
===============================================================
```

## Troubleshooting

### API Error 400
- Package name misspelled
- Combination not supported

### API Error 401
- API key invalid or expired

### No Data
- Check coordinates
- Check timezone

## Roadmap

- [x] CloudWatcher Solo integration
- [x] Supabase data storage
- [x] Pushover notifications
- [x] AllSky camera integration (Oculus + ZWO)
- [x] Grafana dashboards
- [ ] ML model for local forecast correction
- [ ] Telegram Bot notifications
- [ ] Open-Meteo fallback
- [ ] Satellite image integration

## License

MIT License - See [LICENSE](LICENSE)

## Credits

- [meteoblue](https://www.meteoblue.com) - Astronomy Seeing API
- [Supabase](https://supabase.com) - PostgreSQL database & Edge Functions
- [Lunatico](https://lunatico.es) - CloudWatcher Solo hardware
- [Grafana](https://grafana.com) - Visualization dashboards
