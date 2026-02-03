# 🗄️ Supabase Setup Anleitung

Supabase ist eine kostenlose PostgreSQL-Datenbank in der Cloud. Perfekt für unser Projekt.

---

## 1. Account erstellen

1. Gehe zu **https://supabase.com**
2. Klicke **"Start your project"**
3. Login mit **GitHub** (empfohlen) oder Email

---

## 2. Neues Projekt erstellen

1. Klicke **"New Project"**
2. Fülle aus:
   - **Name:** `astro-weather` (oder wie du willst)
   - **Database Password:** Sicheres Passwort generieren & SPEICHERN!
   - **Region:** Frankfurt (eu-central-1) ← Nächste zu dir
3. Klicke **"Create new project"**
4. Warte 1-2 Minuten bis Projekt bereit ist

---

## 3. Datenbank-Schema erstellen

1. Im Supabase Dashboard, klicke links auf **"SQL Editor"**
2. Klicke **"New query"**
3. Kopiere den **gesamten Inhalt** von `supabase_schema.sql` hinein
4. Klicke **"Run"** (oder Ctrl+Enter)
5. Du solltest sehen: "Success. No rows returned"

**Prüfen ob Tabellen erstellt wurden:**
- Klicke links auf **"Table Editor"**
- Du solltest sehen:
  - `cloudwatcher_readings`
  - `meteoblue_hourly`
  - `observation_windows`
  - `training_pairs`
  - `api_call_log`
  - `seeing_quality_reference`

---

## 4. API-Credentials holen

1. Klicke links auf **"Project Settings"** (Zahnrad-Icon)
2. Klicke auf **"API"** im Untermenü
3. Notiere dir:

**Project URL:**
```
https://xxxxxxxxxxxx.supabase.co
```

**anon public Key** (der lange mit eyJ...):
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxx...
```

⚠️ Das ist der **anon key** - sicher für Client-Anwendungen.

---

## 5. In .env eintragen

Auf deiner Synology, editiere `/volume1/scripts/astro_weather/.env`:

```bash
export SUPABASE_URL="https://xxxxxxxxxxxx.supabase.co"
export SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxx..."
```

---

## 6. Verbindung testen

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

# Test: Leere Abfrage
result = client.table("cloudwatcher_readings").select("*").limit(1).execute()
print(f"✅ Verbindung OK! Rows: {len(result.data)}")
EOF
```

---

## 📊 Supabase Dashboard nutzen

### Daten ansehen

1. **Table Editor** → Wähle Tabelle → Siehst alle Zeilen
2. Klicke auf eine Zeile zum Editieren
3. Filter und Sortierung möglich

### SQL Abfragen

Im **SQL Editor** kannst du direkt abfragen:

```sql
-- Letzte 10 CloudWatcher Messungen
SELECT timestamp, sky_quality, sky_minus_ambient, sky_brightness_mpsas
FROM cloudwatcher_readings
ORDER BY timestamp DESC
LIMIT 10;

-- Beste Stunden der nächsten 3 Tage
SELECT timestamp, astro_score, seeing_arcsec, totalcloud
FROM meteoblue_hourly
WHERE timestamp > NOW()
  AND zenith_angle > 108  -- Astronomische Nacht
ORDER BY astro_score DESC
LIMIT 20;

-- Wie oft lag meteoblue richtig?
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN cloud_classification_match THEN 1 ELSE 0 END) as correct,
  ROUND(100.0 * SUM(CASE WHEN cloud_classification_match THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy_pct
FROM training_pairs;
```

### Charts (mit Supabase)

Supabase hat kein eingebautes Charting, aber du kannst:
- Daten exportieren (CSV)
- Mit externen Tools verbinden (Grafana, Metabase)
- Oder später ein einfaches Dashboard bauen

---

## 💰 Kosten

**Free Tier (reicht für uns!):**
- 500 MB Datenbank
- 2 GB Bandwidth
- 50.000 monatliche Requests

Bei 5-Minuten-Polling:
- ~8.640 CloudWatcher-Inserts/Monat
- ~720 meteoblue-Inserts/Monat
- **Weit unter dem Limit!**

---

## 🔒 Sicherheit

Der `anon` Key ist sicher für Client-Anwendungen weil:
- Row Level Security (RLS) kann Zugriff einschränken
- Für unser privates Projekt ist RLS optional

Falls du RLS aktivieren willst (optional):
```sql
-- Beispiel: Nur Lesen erlauben
ALTER TABLE cloudwatcher_readings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow read" ON cloudwatcher_readings FOR SELECT USING (true);
CREATE POLICY "Allow insert" ON cloudwatcher_readings FOR INSERT WITH CHECK (true);
```

---

## ✅ Checkliste

- [ ] Supabase Account erstellt
- [ ] Projekt erstellt (Region: Frankfurt)
- [ ] Schema ausgeführt (SQL Editor)
- [ ] Tabellen sichtbar im Table Editor
- [ ] API URL notiert
- [ ] API Key (anon) notiert
- [ ] In `.env` auf Synology eingetragen
- [ ] Verbindungstest erfolgreich
