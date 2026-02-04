# Supabase Setup Guide

Supabase is a free PostgreSQL database in the cloud. Perfect for this project.

---

## 1. Create Account

1. Go to **https://supabase.com**
2. Click **"Start your project"**
3. Login with **GitHub** (recommended) or Email

---

## 2. Create New Project

1. Click **"New Project"**
2. Fill in:
   - **Name:** `astro-weather` (or whatever you prefer)
   - **Database Password:** Generate a secure password & SAVE IT!
   - **Region:** Frankfurt (eu-central-1) - closest to your location
3. Click **"Create new project"**
4. Wait 1-2 minutes until project is ready

---

## 3. Create Database Schema

1. In the Supabase Dashboard, click **"SQL Editor"** on the left
2. Click **"New query"**
3. Copy the **entire contents** of `supabase_schema.sql` into it
4. Click **"Run"** (or Ctrl+Enter)
5. You should see: "Success. No rows returned"

**Verify tables were created:**
- Click **"Table Editor"** on the left
- You should see:
  - `cloudwatcher_readings`
  - `meteoblue_hourly`
  - `observation_windows`
  - `training_pairs`
  - `api_call_log`
  - `seeing_quality_reference`

---

## 4. Get API Credentials

1. Click **"Project Settings"** on the left (gear icon)
2. Click **"API"** in the submenu
3. Note down:

**Project URL:**
```
https://xxxxxxxxxxxx.supabase.co
```

**anon public Key** (the long one starting with eyJ...):
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxx...
```

Note: This is the **anon key** - safe for client applications.

---

## 5. Add to .env

On your Synology, edit `/volume1/scripts/astro_weather/.env`:

```bash
export SUPABASE_URL="https://xxxxxxxxxxxx.supabase.co"
export SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxx..."
```

---

## 6. Test Connection

```bash
cd /volume1/scripts/astro_weather
source .env

python3 << 'EOF'
import os
from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

print(f"URL: {url}")
print(f"Key: {key[:20]}...")

client = create_client(url, key)

# Test: Empty query
result = client.table("cloudwatcher_readings").select("*").limit(1).execute()
print(f"Connection OK! Rows: {len(result.data)}")
EOF
```

---

## Using the Supabase Dashboard

### View Data

1. **Table Editor** -> Select table -> See all rows
2. Click on a row to edit
3. Filter and sorting available

### SQL Queries

In the **SQL Editor** you can query directly:

```sql
-- Last 10 CloudWatcher readings
SELECT timestamp, sky_quality, sky_minus_ambient, sky_brightness_mpsas
FROM cloudwatcher_readings
ORDER BY timestamp DESC
LIMIT 10;

-- Best hours in the next 3 days
SELECT timestamp, astro_score, seeing_arcsec, totalcloud
FROM meteoblue_hourly
WHERE timestamp > NOW()
  AND zenith_angle > 108  -- Astronomical night
ORDER BY astro_score DESC
LIMIT 20;

-- How often was meteoblue correct?
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN cloud_classification_match THEN 1 ELSE 0 END) as correct,
  ROUND(100.0 * SUM(CASE WHEN cloud_classification_match THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy_pct
FROM training_pairs;
```

### Charts (with Supabase)

Supabase has no built-in charting, but you can:
- Export data (CSV)
- Connect with external tools (Grafana, Metabase)
- Or build a simple dashboard later

---

## Costs

**Free Tier (sufficient for us!):**
- 500 MB database
- 2 GB bandwidth
- 50,000 monthly requests

With 5-minute polling:
- ~8,640 CloudWatcher inserts/month
- ~720 meteoblue inserts/month
- **Well under the limit!**

---

## Security

The `anon` key is safe for client applications because:
- Row Level Security (RLS) can restrict access
- For our private project, RLS is optional

If you want to enable RLS (optional):
```sql
-- Example: Allow read only
ALTER TABLE cloudwatcher_readings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow read" ON cloudwatcher_readings FOR SELECT USING (true);
CREATE POLICY "Allow insert" ON cloudwatcher_readings FOR INSERT WITH CHECK (true);
```

---

## Checklist

- [ ] Supabase account created
- [ ] Project created (Region: Frankfurt)
- [ ] Schema executed (SQL Editor)
- [ ] Tables visible in Table Editor
- [ ] API URL noted
- [ ] API Key (anon) noted
- [ ] Added to `.env` on Synology
- [ ] Connection test successful
