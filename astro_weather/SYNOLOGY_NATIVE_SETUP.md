# Synology NAS - Native Python Setup

Complete guide for the Astro Weather System on Synology DSM 7.x **without Docker**.

---

## Prerequisites

- Synology NAS with **DSM 7.0+**
- **Admin access** to the NAS
- **SSH enabled** (Control Panel -> Terminal & SNMP -> Enable SSH)
- CloudWatcher Solo reachable at `192.168.1.151`

---

## Step-by-Step Installation

### 1. Install Python 3

**Via Package Center (DSM GUI):**
1. Open **Package Center**
2. Search for **"Python 3.11"** (or latest available version)
3. Install

If not in Package Center: Python often comes with other packages like "Web Station" or can be installed via community sources.

---

### 2. Establish SSH Connection

```bash
# From your PC:
ssh admin@<YOUR-NAS-IP>

# Enter password, then become root:
sudo -i
```

---

### 3. Check Python & pip

```bash
# Check Python
python3 --version
# Should show: Python 3.9+ or 3.11+

# Check pip
pip3 --version

# If pip is missing:
python3 -m ensurepip --upgrade
# OR:
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py
```

---

### 4. Create Project Directory

```bash
# Create directory (on Volume 1, adjust if different)
mkdir -p /volume1/scripts/astro_weather
cd /volume1/scripts/astro_weather
```

---

### 5. Install Python Packages

```bash
# Install required packages
pip3 install requests supabase python-dateutil

# Verify installation
python3 -c "import requests; from supabase import create_client; print('OK')"
```

---

### 6. Upload Project Files

**Option A: Via File Station (GUI)**
1. Open **File Station** in DSM
2. Navigate to `/volume1/scripts/astro_weather`
3. Upload the `.py` files (Upload button)

**Option B: Via SCP (Terminal)**
```bash
# From your PC (where the files are):
scp *.py admin@<NAS-IP>:/volume1/scripts/astro_weather/
```

**Option C: Via wget directly on NAS**
If you host the files somewhere or create them manually.

---

### 7. Create Configuration File

```bash
cd /volume1/scripts/astro_weather

# Create .env file
cat > .env << 'EOF'
# ============================================
# ASTRO WEATHER CONFIGURATION
# ============================================

# Location Wietesch
export ASTRO_LAT="52.17"
export ASTRO_LON="7.25"

# CloudWatcher Solo
export CLOUDWATCHER_HOST="192.168.1.151"

# meteoblue API
export METEOBLUE_API_KEY="YOUR_METEOBLUE_API_KEY"

# Supabase (ENTER YOUR CREDENTIALS HERE!)
export SUPABASE_URL="https://YOUR-PROJECT.supabase.co"
export SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Optional: Pushover notifications
# export PUSHOVER_USER=""
# export PUSHOVER_TOKEN=""
EOF

# Protect the file (only root readable)
chmod 600 .env
```

**IMPORTANT:** Replace `SUPABASE_URL` and `SUPABASE_KEY` with your real credentials!

---

### 8. Test Connection

```bash
cd /volume1/scripts/astro_weather
source .env

# Test 1: CloudWatcher Solo
echo "=== CloudWatcher Test ==="
python3 cloudwatcher_client.py --test

# Test 2: meteoblue API
echo "=== meteoblue Test ==="
python3 scheduler.py --test-mb

# Test 3: Overall status
echo "=== Overall Status ==="
python3 scheduler.py --status
```

**Expected output:**
```
=== CloudWatcher Test ===
CloudWatcher is reachable
18:45:23 | Sky: CLEAR (-8.4C) | SQM: 18.40 (Bortle ~6) | Temp: 1.3C | Hum: 72%

=== meteoblue Test ===
Fetched 168 hours
Next 12 hours:
19:00 | Score: 72 | Seeing: 1.4" | Clouds: 18% | Jet: 22m/s
...
```

---

### 9. Create Wrapper Script

For the Task Scheduler we need a shell script:

```bash
cat > /volume1/scripts/astro_weather/run_update.sh << 'EOF'
#!/bin/bash
# Astro Weather Update Script for Synology Task Scheduler

# Change to directory
cd /volume1/scripts/astro_weather

# Load environment variables
source .env

# Python path (adjust if necessary)
PYTHON="/usr/local/bin/python3"

# If Python is elsewhere:
# PYTHON="/volume1/@appstore/Python3.11/usr/bin/python3"

# Run update
$PYTHON scheduler.py --single

# Pass through exit code
exit $?
EOF

chmod +x /volume1/scripts/astro_weather/run_update.sh
```

---

### 10. Set Up Task Scheduler (DSM GUI)

1. Open **Control Panel** -> **Task Scheduler**

2. Click **Create** -> **Scheduled Task** -> **User-defined script**

3. **General tab:**
   - Name: `Astro Weather Update`
   - User: `root`
   - Enabled: (check the box)

4. **Schedule tab:**
   - Run on days: Daily
   - First run time: `00:00`
   - Frequency: Repeat every **5 minutes**
   - Last run time: `23:55`

5. **Task Settings tab:**
   - Run command:
   ```
   /volume1/scripts/astro_weather/run_update.sh >> /var/log/astro_weather.log 2>&1
   ```
   - (optional) Send run details by email

6. Click **OK**

---

### 11. Set Up Log Rotation (optional but recommended)

```bash
# Create logrotate config
cat > /etc/logrotate.d/astro_weather << 'EOF'
/var/log/astro_weather.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
EOF
```

---

### 12. Run First Manual Test

```bash
# As root
/volume1/scripts/astro_weather/run_update.sh

# Check log
tail -20 /var/log/astro_weather.log
```

---

## Checklist

- [ ] Python 3 installed and working
- [ ] pip3 installed
- [ ] `requests` and `supabase` packages installed
- [ ] Project files in `/volume1/scripts/astro_weather/`
- [ ] `.env` file with correct credentials
- [ ] CloudWatcher test successful (`--test`)
- [ ] meteoblue test successful (`--test-mb`)
- [ ] `run_update.sh` created and executable
- [ ] Task Scheduler task created
- [ ] First manual run successful

---

## Troubleshooting

### "Python not found"

```bash
# Find Python
find / -name "python3" 2>/dev/null

# Typical paths on Synology:
# /usr/local/bin/python3
# /usr/bin/python3
# /volume1/@appstore/Python3.11/usr/bin/python3
```

### "Module not found: requests"

```bash
# Check which pip belongs to which Python
which pip3
which python3

# Install for the correct Python
/usr/local/bin/python3 -m pip install requests supabase
```

### "Connection refused" for CloudWatcher

```bash
# Test ping
ping 192.168.1.151

# Test HTTP directly
curl -v http://192.168.1.151/cgi-bin/lastData.pl

# If firewall issue: Check NAS firewall rules
```

### "Supabase connection error"

```bash
# Test credentials
python3 << 'EOF'
import os
os.environ['SUPABASE_URL'] = 'https://xxx.supabase.co'
os.environ['SUPABASE_KEY'] = 'eyJ...'
from supabase import create_client
client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])
print("Supabase connected!")
EOF
```

### Task not running

```bash
# Check Task Scheduler logs
cat /var/log/synolog/synoscheduler.log | grep -i astro

# Test manually
/volume1/scripts/astro_weather/run_update.sh
echo "Exit code: $?"
```

---

## Monitoring

### Watch Live Log

```bash
tail -f /var/log/astro_weather.log
```

### Check Recent Entries

```bash
tail -50 /var/log/astro_weather.log
```

### Query Status

```bash
cd /volume1/scripts/astro_weather && source .env && python3 scheduler.py --status
```

---

## What Happens After Setup?

**Every 5 minutes:**
- CloudWatcher is polled
- Data is saved to Supabase

**Every full hour (minute 0-4):**
- meteoblue 7-day forecast is fetched
- Data is saved to Supabase
- Observation windows are detected

**In Supabase you collect:**
- `cloudwatcher_readings` - Ground truth every 5 min
- `meteoblue_hourly` - Forecast data hourly
- `observation_windows` - Detected good nights

After 2-4 weeks you have enough data for ML training!
