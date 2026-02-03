# 🖥️ Synology NAS - Native Python Setup

Komplette Anleitung für das Astro Weather System auf Synology DSM 7.x **ohne Docker**.

---

## 📋 Voraussetzungen

- Synology NAS mit **DSM 7.0+**
- **Admin-Zugang** zur NAS
- **SSH aktiviert** (Systemsteuerung → Terminal & SNMP → SSH aktivieren)
- CloudWatcher Solo erreichbar unter `192.168.1.151`

---

## 🚀 Schritt-für-Schritt Installation

### 1. Python 3 installieren

**Via Package Center (DSM GUI):**
1. Öffne **Package Center**
2. Suche nach **"Python 3.11"** (oder neueste verfügbare Version)
3. Installieren

Falls nicht im Package Center: Python kommt oft mit anderen Paketen wie "Web Station" oder kann über Community-Quellen installiert werden.

---

### 2. SSH-Verbindung herstellen

```bash
# Von deinem PC aus:
ssh admin@<DEINE-NAS-IP>

# Passwort eingeben, dann root werden:
sudo -i
```

---

### 3. Python & pip prüfen

```bash
# Prüfe Python
python3 --version
# Sollte zeigen: Python 3.9+ oder 3.11+

# Prüfe pip
pip3 --version

# Falls pip fehlt:
python3 -m ensurepip --upgrade
# ODER:
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py
```

---

### 4. Projektverzeichnis erstellen

```bash
# Erstelle Verzeichnis (auf Volume 1, anpassen falls anders)
mkdir -p /volume1/scripts/astro_weather
cd /volume1/scripts/astro_weather
```

---

### 5. Python-Pakete installieren

```bash
# Installiere benötigte Pakete
pip3 install requests supabase python-dateutil

# Prüfe Installation
python3 -c "import requests; from supabase import create_client; print('✅ OK')"
```

---

### 6. Projektdateien hochladen

**Option A: Via File Station (GUI)**
1. Öffne **File Station** in DSM
2. Navigiere zu `/volume1/scripts/astro_weather`
3. Lade die `.py` Dateien hoch (Upload-Button)

**Option B: Via SCP (Terminal)**
```bash
# Von deinem PC aus (wo die Dateien liegen):
scp *.py admin@<NAS-IP>:/volume1/scripts/astro_weather/
```

**Option C: Via wget direkt auf NAS**
Falls du die Dateien irgendwo hostest oder manuell erstellst.

---

### 7. Konfigurationsdatei erstellen

```bash
cd /volume1/scripts/astro_weather

# Erstelle .env Datei
cat > .env << 'EOF'
# ============================================
# ASTRO WEATHER KONFIGURATION
# ============================================

# Standort Wietesch
export ASTRO_LAT="52.17"
export ASTRO_LON="7.25"

# CloudWatcher Solo
export CLOUDWATCHER_HOST="192.168.1.151"

# meteoblue API
export METEOBLUE_API_KEY="YOUR_METEOBLUE_API_KEY"

# Supabase (HIER DEINE CREDENTIALS EINTRAGEN!)
export SUPABASE_URL="https://DEIN-PROJEKT.supabase.co"
export SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Optional: Pushover Benachrichtigungen
# export PUSHOVER_USER=""
# export PUSHOVER_TOKEN=""
EOF

# Schütze die Datei (nur root lesbar)
chmod 600 .env
```

**⚠️ WICHTIG:** Ersetze `SUPABASE_URL` und `SUPABASE_KEY` mit deinen echten Credentials!

---

### 8. Verbindung testen

```bash
cd /volume1/scripts/astro_weather
source .env

# Test 1: CloudWatcher Solo
echo "=== CloudWatcher Test ==="
python3 cloudwatcher_client.py --test

# Test 2: meteoblue API
echo "=== meteoblue Test ==="
python3 scheduler.py --test-mb

# Test 3: Gesamtstatus
echo "=== Gesamtstatus ==="
python3 scheduler.py --status
```

**Erwartete Ausgabe:**
```
=== CloudWatcher Test ===
✅ CloudWatcher is reachable
✅ 18:45:23 | Sky: ☀️ CLEAR (-8.4°C) | SQM: 18.40 (Bortle ~6) | Temp: 1.3°C | Hum: 72%

=== meteoblue Test ===
Fetched 168 hours
Next 12 hours:
🌙 19:00 | Score: 72 ✨ | Seeing: 1.4" | Clouds: 18% | Jet: 22m/s
...
```

---

### 9. Wrapper-Script erstellen

Für den Task Scheduler brauchen wir ein Shell-Script:

```bash
cat > /volume1/scripts/astro_weather/run_update.sh << 'EOF'
#!/bin/bash
# Astro Weather Update Script für Synology Task Scheduler

# Ins Verzeichnis wechseln
cd /volume1/scripts/astro_weather

# Umgebungsvariablen laden
source .env

# Python-Pfad (anpassen falls nötig)
PYTHON="/usr/local/bin/python3"

# Falls Python woanders liegt:
# PYTHON="/volume1/@appstore/Python3.11/usr/bin/python3"

# Update ausführen
$PYTHON scheduler.py --single

# Exit-Code weitergeben
exit $?
EOF

chmod +x /volume1/scripts/astro_weather/run_update.sh
```

---

### 10. Task Scheduler einrichten (DSM GUI)

1. Öffne **Systemsteuerung** → **Aufgabenplaner**

2. Klicke **Erstellen** → **Geplante Aufgabe** → **Benutzerdefiniertes Skript**

3. **Reiter "Allgemein":**
   - Name: `Astro Weather Update`
   - Benutzer: `root`
   - Aktiviert: ✓ (Haken setzen)

4. **Reiter "Zeitplan":**
   - Ausführungstage: Täglich
   - Erste Ausführungszeit: `00:00`
   - Häufigkeit: Alle **5 Minuten** wiederholen
   - Letzte Ausführungszeit: `23:55`

5. **Reiter "Aufgabeneinstellungen":**
   - Befehl ausführen:
   ```
   /volume1/scripts/astro_weather/run_update.sh >> /var/log/astro_weather.log 2>&1
   ```
   - ✓ Ausführungsdetails per E-Mail senden (optional)

6. **OK** klicken

---

### 11. Log-Rotation einrichten (optional aber empfohlen)

```bash
# Erstelle logrotate Config
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

### 12. Ersten manuellen Test ausführen

```bash
# Als root
/volume1/scripts/astro_weather/run_update.sh

# Prüfe Log
tail -20 /var/log/astro_weather.log
```

---

## ✅ Checkliste

- [ ] Python 3 installiert und funktioniert
- [ ] pip3 installiert
- [ ] `requests` und `supabase` Pakete installiert
- [ ] Projektdateien in `/volume1/scripts/astro_weather/`
- [ ] `.env` Datei mit korrekten Credentials
- [ ] CloudWatcher Test erfolgreich (`--test`)
- [ ] meteoblue Test erfolgreich (`--test-mb`)
- [ ] `run_update.sh` erstellt und ausführbar
- [ ] Task Scheduler Aufgabe erstellt
- [ ] Erster manueller Durchlauf erfolgreich

---

## 🔧 Troubleshooting

### "Python not found"

```bash
# Finde Python
find / -name "python3" 2>/dev/null

# Typische Pfade auf Synology:
# /usr/local/bin/python3
# /usr/bin/python3
# /volume1/@appstore/Python3.11/usr/bin/python3
```

### "Module not found: requests"

```bash
# Prüfe welches pip zu welchem Python gehört
which pip3
which python3

# Installiere für das richtige Python
/usr/local/bin/python3 -m pip install requests supabase
```

### "Connection refused" bei CloudWatcher

```bash
# Ping testen
ping 192.168.1.151

# HTTP direkt testen
curl -v http://192.168.1.151/cgi-bin/lastData.pl

# Falls Firewall-Problem: Prüfe NAS Firewall-Regeln
```

### "Supabase connection error"

```bash
# Teste Credentials
python3 << 'EOF'
import os
os.environ['SUPABASE_URL'] = 'https://xxx.supabase.co'
os.environ['SUPABASE_KEY'] = 'eyJ...'
from supabase import create_client
client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])
print("✅ Supabase connected!")
EOF
```

### Task läuft nicht

```bash
# Prüfe Task Scheduler Logs
cat /var/log/synolog/synoscheduler.log | grep -i astro

# Manuell testen
/volume1/scripts/astro_weather/run_update.sh
echo "Exit code: $?"
```

---

## 📊 Monitoring

### Live-Log beobachten

```bash
tail -f /var/log/astro_weather.log
```

### Letzte Einträge prüfen

```bash
tail -50 /var/log/astro_weather.log
```

### Status abfragen

```bash
cd /volume1/scripts/astro_weather && source .env && python3 scheduler.py --status
```

---

## 📈 Was passiert nach dem Setup?

**Alle 5 Minuten:**
- CloudWatcher wird gepollt
- Daten werden in Supabase gespeichert

**Jede volle Stunde (Minute 0-4):**
- meteoblue 7-Tage Forecast wird abgerufen
- Daten werden in Supabase gespeichert
- Beobachtungsfenster werden erkannt

**In Supabase sammelst du:**
- `cloudwatcher_readings` - Ground Truth alle 5 min
- `meteoblue_hourly` - Forecast-Daten stündlich
- `observation_windows` - Erkannte gute Nächte

Nach 2-4 Wochen hast du genug Daten fürs ML-Training! 🎯
