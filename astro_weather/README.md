# Astrophotography Weather Forecasting System

Local weather forecasting system optimized for astrophotography at location **Wietesch/Rheine**.

## Features

- **Seeing forecast** in arcseconds
- **Jet Stream & Bad Layers** analysis
- **Cloud layers** (Low/Mid/High)
- **Nightsky Brightness** in Lux
- **Moonlight** and astronomical twilight
- **Automatic observation window detection**
- **Astro-Score** (0-100) for quick assessment
- **Ground Truth** integration with CloudWatcher Solo
- **ML Training Data** for local forecast improvement

## Data Sources

| Source | Data | Cost |
|--------|------|------|
| **meteoblue** | Seeing, Clouds, Moonlight, Jet Stream | ~40k Credits/Call |
| **CloudWatcher Solo** | Sky Temperature (Ground Truth) | Hardware available |
| **Open-Meteo** (optional) | ICON-D2 Backup | Free |

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

- [ ] CloudWatcher Solo Integration
- [ ] Telegram Bot for notifications
- [ ] Web Dashboard
- [ ] ML model for local correction
- [ ] Open-Meteo Fallback
- [ ] Satellite image integration

## License

Private project for Joerg @ Wietesch

## Credits

- [meteoblue](https://www.meteoblue.com) - Weather data & Seeing
- [Supabase](https://supabase.com) - Database
- [Lunatico](https://lunatico.es) - CloudWatcher Hardware
