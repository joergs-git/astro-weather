#!/usr/bin/env python3
"""
Astro Weather Scheduler für Synology NAS
=========================================

Kombinierter Scheduler der:
1. CloudWatcher Solo alle 5 Minuten pollt
2. meteoblue alle 60 Minuten abruft
3. Alles zu Supabase schiebt
4. Beobachtungsfenster erkennt
5. Optional Benachrichtigungen sendet

Für Synology Task Scheduler oder als Python-Daemon.

Autor: Claude für Joerg
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Lokale Imports
from cloudwatcher_client import CloudWatcherSoloClient, CloudWatcherDatabase, CloudWatcherReading
from meteoblue_client import MeteoblueAstroClient, AstroConditions

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        # Optional: Log-Datei
        # logging.FileHandler('/var/log/astro_weather.log')
    ]
)
logger = logging.getLogger("astro_scheduler")


# ============================================
# KONFIGURATION
# ============================================

DEFAULT_CONFIG = {
    # Standort
    "lat": 52.17,
    "lon": 7.25,
    "timezone": "Europe/Berlin",
    
    # CloudWatcher Solo
    "cloudwatcher_host": "192.168.1.151",
    "cloudwatcher_poll_interval": 300,  # 5 Minuten
    
    # meteoblue
    "meteoblue_api_key": "",  # Aus Umgebungsvariable
    "meteoblue_poll_interval": 3600,  # 60 Minuten
    "meteoblue_forecast_days": 7,
    
    # Supabase
    "supabase_url": "",
    "supabase_key": "",
    
    # Benachrichtigungen
    "notify_min_score": 70,
    "notify_min_hours": 3,
    
    # Pushover (optional)
    "pushover_user": "",
    "pushover_token": "",
}



# ============================================
# ALLSKY HELPER
# ============================================

def find_allsky_image(timestamp, base_path="/volume1/AllSky-Rheine"):
    """Find closest AllSky image for timestamp (within 60 sec before)"""
    import os
    import glob
    
    date_str = timestamp.strftime("%Y-%m-%d")
    img_dir = f"{base_path}/{date_str}/jpg"
    
    if not os.path.exists(img_dir):
        return None
    
    # Check current and previous minute
    candidates = []
    for offset in range(0, 6):
        check_time = timestamp - timedelta(minutes=offset)
        pattern = f"{img_dir}/{check_time.strftime('%Y%m%dT%H%M')}*.jpg"
        candidates.extend(glob.glob(pattern))
    
    if not candidates:
        return None
    
    candidates.sort(reverse=True)
    return candidates[0]


def find_zwo_image(timestamp, base_path="/volume1/AllSky-Rheine/zwo"):
    """Find closest ZWO AllSky image for timestamp (within 5 min before)"""
    import os
    import glob
    
    date_str = timestamp.strftime("%Y-%m-%d")
    img_dir = f"{base_path}/{date_str}/jpg"
    
    if not os.path.exists(img_dir):
        return None
    
    # Check current and previous 5 minutes
    candidates = []
    for offset in range(0, 6):
        check_time = timestamp - timedelta(minutes=offset)
        pattern = f"{img_dir}/zwo_{check_time.strftime('%Y%m%dT%H%M')}*.jpg"
        candidates.extend(glob.glob(pattern))
    
    if not candidates:
        return None
    
    candidates.sort(reverse=True)
    return candidates[0]


def find_zwo_fits(timestamp, base_path="/volume1/AllSky-Rheine/zwo"):
    """Find closest ZWO FITS file for timestamp (within 5 min before)"""
    import os
    import glob
    
    date_str = timestamp.strftime("%Y-%m-%d")
    fits_dir = f"{base_path}/{date_str}/fits"
    
    if not os.path.exists(fits_dir):
        return None
    
    # Check current and previous 5 minutes
    candidates = []
    for offset in range(0, 8):
        check_time = timestamp - timedelta(minutes=offset)
        pattern = f"{fits_dir}/zwo_{check_time.strftime('%Y%m%dT%H%M')}*.fit"
        candidates.extend(glob.glob(pattern))
    
    if not candidates:
        return None
    
    candidates.sort(reverse=True)
    return candidates[0]

def load_config() -> Dict[str, Any]:
    """Lädt Konfiguration aus Umgebungsvariablen"""
    config = DEFAULT_CONFIG.copy()
    
    # Überschreibe mit Umgebungsvariablen
    env_mapping = {
        "CLOUDWATCHER_HOST": "cloudwatcher_host",
        "METEOBLUE_API_KEY": "meteoblue_api_key",
        "SUPABASE_URL": "supabase_url",
        "SUPABASE_KEY": "supabase_key",
        "PUSHOVER_USER": "pushover_user",
        "PUSHOVER_TOKEN": "pushover_token",
        "ASTRO_LAT": "lat",
        "ASTRO_LON": "lon",
    }
    
    for env_key, config_key in env_mapping.items():
        value = os.environ.get(env_key)
        if value:
            # Konvertiere numerische Werte
            if config_key in ["lat", "lon"]:
                config[config_key] = float(value)
            else:
                config[config_key] = value
    
    return config


# ============================================
# SUPABASE WRAPPER (KOMBINIERT)
# ============================================

class AstroWeatherDB:
    """Kombinierte Datenbank für CloudWatcher + meteoblue"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        from supabase import create_client
        self.client = create_client(supabase_url, supabase_key)
        logger.info("AstroWeatherDB initialized")
    
    # --- CloudWatcher ---
    
    def save_cloudwatcher(self, reading: CloudWatcherReading) -> bool:
        """Speichert CloudWatcher-Messung"""
        record = {
            "timestamp": reading.timestamp.isoformat(),
            "sky_temperature": reading.sky_temp,
            "ambient_temperature": reading.ambient_temp,
            "sky_minus_ambient": reading.clouds,
            "sky_quality": reading.sky_quality_name,  # CLEAR oder CLOUDY
            "sky_quality_raw": reading.clouds_safe,   # 0=cloudy, 1=clear
            "light_sensor": reading.sky_brightness_mpsas,
            "light_safe": reading.light_safe,
            "rain_sensor": reading.rain,
            "rain_safe": reading.rain_safe,
            "humidity": reading.humidity,
            "humidity_safe": reading.humidity_safe,
            "dew_point": reading.dew_point,
            "pressure_abs": reading.pressure_abs,
            "pressure_rel": reading.pressure_rel,
            "safe": reading.safe,
            "device_serial": reading.serial,
            "device_firmware": reading.firmware,
            "raw_json": reading.to_dict(),
            "allsky_url": find_allsky_image(reading.timestamp),
            "zwo_url": find_zwo_image(reading.timestamp),
            "zwo_fits_url": find_zwo_fits(reading.timestamp)
        }
        
        try:
            self.client.table("cloudwatcher_readings").insert(record).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to save CloudWatcher: {e}")
            return False
    
    # --- meteoblue ---
    
    def save_meteoblue(self, conditions: list) -> int:
        """Speichert meteoblue Vorhersagen (upsert)"""
        records = []
        for cond in conditions:
            records.append({
                "timestamp": cond.timestamp.isoformat(),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "seeing_arcsec": cond.seeing_arcsec,
                "seeing_index1": cond.seeing_index1,
                "seeing_index2": cond.seeing_index2,
                "jetstream_speed": cond.jetstream_speed,
                "badlayer_bottom": cond.badlayer_bottom,
                "badlayer_top": cond.badlayer_top,
                "badlayer_gradient": cond.badlayer_gradient,
                "totalcloud": cond.totalcloud,
                "lowclouds": cond.lowclouds,
                "midclouds": cond.midclouds,
                "highclouds": cond.highclouds,
                "visibility": cond.visibility,
                "fog_probability": cond.fog_probability,
                "nightsky_brightness_actual": cond.nightsky_brightness_actual,
                "nightsky_brightness_clearsky": cond.nightsky_brightness_clearsky,
                "moonlight_actual": cond.moonlight_actual,
                "zenith_angle": cond.zenith_angle,
                "temperature": cond.temperature,
                "humidity": cond.humidity,
                "precipitation_prob": cond.precipitation_prob,
                "wind_speed": cond.wind_speed,
                "astro_score": cond.astro_score,
                "quality_class": cond.quality_class
            })
        
        try:
            result = self.client.table("meteoblue_hourly") \
                .insert(records) \
                .execute()
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error(f"Failed to save meteoblue: {e}")
            return 0
    
    # --- Observation Windows ---
    
    def save_window(self, window: Dict) -> bool:
        """Speichert ein Beobachtungsfenster"""
        record = {
            "start_time": window["start"].isoformat(),
            "end_time": window["end"].isoformat(),
            "duration_hours": window["hours"],
            "avg_score": int(window["avg_score"]),
            "min_score": window["min_score"],
            "avg_seeing_arcsec": window["avg_seeing"],
            "avg_clouds": int(window["avg_clouds"]),
            "notified": False
        }
        
        try:
            self.client.table("observation_windows").insert(record).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to save window: {e}")
            return False
    
    def get_unnotified_windows(self, min_score: int = 70) -> list:
        """Holt Fenster die noch nicht benachrichtigt wurden"""
        now = datetime.now(timezone.utc).isoformat()
        
        result = self.client.table("observation_windows") \
            .select("*") \
            .gt("start_time", now) \
            .gte("avg_score", min_score) \
            .eq("notified", False) \
            .order("start_time") \
            .execute()
        
        return result.data if result.data else []
    
    def mark_notified(self, window_id: int) -> bool:
        """Markiert Fenster als benachrichtigt"""
        try:
            self.client.table("observation_windows") \
                .update({"notified": True, "notification_sent_at": datetime.now(timezone.utc).isoformat()}) \
                .eq("id", window_id) \
                .execute()
            return True
        except:
            return False
    
    # --- API Log ---
    
    def log_api_call(self, api: str, endpoint: str, credits: int, success: bool, ms: int = 0):
        """Loggt API-Aufrufe"""
        try:
            self.client.table("api_call_log").insert({
                "api_name": api,
                "endpoint": endpoint,
                "credits_used": credits,
                "success": success,
                "response_time_ms": ms
            }).execute()
        except:
            pass  # Logging sollte nie crashen


# ============================================
# BENACHRICHTIGUNGEN
# ============================================

def send_pushover(user_key: str, api_token: str, title: str, message: str, priority: int = 0) -> bool:
    """
    Sendet Pushover-Benachrichtigung
    
    Args:
        user_key: Pushover User Key
        api_token: Pushover API Token
        title: Nachrichtentitel
        message: Nachrichtentext
        priority: -2 bis 2 (0 = normal)
    
    Returns:
        True bei Erfolg
    """
    import requests
    
    try:
        response = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": api_token,
                "user": user_key,
                "title": title,
                "message": message,
                "priority": priority
            },
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Pushover failed: {e}")
        return False


def format_window_notification(window: Dict) -> str:
    """Formatiert ein Beobachtungsfenster für Benachrichtigung"""
    start = datetime.fromisoformat(window["start_time"])
    end = datetime.fromisoformat(window["end_time"])
    
    return (
        f"🔭 Gute Astro-Nacht!\n\n"
        f"📅 {start.strftime('%a %d.%m.')}\n"
        f"⏰ {start.strftime('%H:%M')} - {end.strftime('%H:%M')}\n"
        f"⭐ Score: {window['avg_score']}\n"
        f"👁️ Seeing: {window['avg_seeing_arcsec']:.1f}\"\n"
        f"☁️ Wolken: {window['avg_clouds']}%"
    )


# ============================================
# HAUPT-TASKS
# ============================================

def task_poll_cloudwatcher(config: Dict) -> Optional[CloudWatcherReading]:
    """Task: CloudWatcher pollen"""
    logger.debug("Polling CloudWatcher...")
    
    try:
        cw = CloudWatcherSoloClient(host=config["cloudwatcher_host"])
        reading = cw.fetch()
        logger.info(f"CW: {reading.summary()}")
        return reading
    except Exception as e:
        logger.error(f"CloudWatcher poll failed: {e}")
        return None


def task_fetch_meteoblue(config: Dict) -> Optional[list]:
    """Task: meteoblue Vorhersage abrufen"""
    logger.debug("Fetching meteoblue forecast...")
    
    if not config.get("meteoblue_api_key"):
        logger.warning("No meteoblue API key configured")
        return None
    
    try:
        client = MeteoblueAstroClient(
            config["meteoblue_api_key"],
            config["lat"],
            config["lon"],
            config["timezone"]
        )
        conditions = client.fetch_astro_forecast(config["meteoblue_forecast_days"])
        logger.info(f"meteoblue: {len(conditions)} hours fetched")
        return conditions
    except Exception as e:
        logger.error(f"meteoblue fetch failed: {e}")
        return None


def task_find_windows(conditions: list, config: Dict) -> list:
    """Task: Beobachtungsfenster finden"""
    if not conditions:
        return []
    
    client = MeteoblueAstroClient("", 0, 0)  # Nur für die Methode
    windows = client.get_best_windows(
        conditions,
        min_score=config.get("notify_min_score", 70),
        min_hours=config.get("notify_min_hours", 2)
    )
    
    logger.info(f"Found {len(windows)} observation windows")
    return windows


def task_send_notifications(db: AstroWeatherDB, config: Dict):
    """Task: Benachrichtigungen für neue Fenster senden"""
    if not config.get("pushover_user") or not config.get("pushover_token"):
        return
    
    windows = db.get_unnotified_windows(config.get("notify_min_score", 70))
    
    for w in windows:
        # Nur Fenster die mind. X Stunden haben
        if w.get("duration_hours", 0) >= config.get("notify_min_hours", 3):
            message = format_window_notification(w)
            
            if send_pushover(
                config["pushover_user"],
                config["pushover_token"],
                "🔭 Astro-Fenster!",
                message
            ):
                db.mark_notified(w["id"])
                logger.info(f"Notification sent for window {w['id']}")


# ============================================
# SCHEDULER MODI
# ============================================

def run_single_update(config: Dict, force_mb: bool = False) -> Dict:
    """
    Einzelner Update-Durchlauf (für Synology Task Scheduler)
    
    Kann als Cron alle 5 Minuten laufen:
    - CloudWatcher wird jedes Mal gepollt
    - meteoblue nur zur vollen Stunde
    """
    status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cloudwatcher": {"success": False},
        "meteoblue": {"success": False, "skipped": False},
        "notifications": {"sent": 0}
    }
    
    # DB initialisieren (optional)
    db = None
    if config.get("supabase_url") and config.get("supabase_key"):
        try:
            db = AstroWeatherDB(config["supabase_url"], config["supabase_key"])
        except Exception as e:
            logger.error(f"Supabase init failed: {e}")
    
    # 1. CloudWatcher pollen (immer)
    reading = task_poll_cloudwatcher(config)
    if reading:
        status["cloudwatcher"]["success"] = True
        status["cloudwatcher"]["sky_quality"] = reading.sky_quality_name
        status["cloudwatcher"]["is_safe"] = reading.is_safe_for_imaging
        
        if db:
            db.save_cloudwatcher(reading)
    
    # 2. meteoblue nur zur vollen Stunde (Minute 0-9)
    current_minute = datetime.now().minute
    if force_mb or current_minute < 10:
        conditions = task_fetch_meteoblue(config)
        if conditions:
            status["meteoblue"]["success"] = True
            status["meteoblue"]["hours"] = len(conditions)
            
            if db:
                saved = db.save_meteoblue(conditions)
                status["meteoblue"]["saved"] = saved
                
                # Fenster finden und speichern
                windows = task_find_windows(conditions, config)
                for w in windows:
                    db.save_window(w)
                status["meteoblue"]["windows"] = len(windows)
                
                # Benachrichtigungen
                task_send_notifications(db, config)
    else:
        status["meteoblue"]["skipped"] = True
        status["meteoblue"]["reason"] = f"Not full hour (minute={current_minute})"
    
    return status


def run_daemon(config: Dict):
    """
    Daemon-Modus: Läuft kontinuierlich
    
    - CloudWatcher alle 5 Minuten
    - meteoblue alle 60 Minuten
    """
    logger.info("Starting Astro Weather Daemon")
    logger.info(f"CloudWatcher: {config['cloudwatcher_host']}")
    logger.info(f"meteoblue: {'configured' if config.get('meteoblue_api_key') else 'not configured'}")
    logger.info(f"Supabase: {'configured' if config.get('supabase_url') else 'not configured'}")
    
    # DB initialisieren
    db = None
    if config.get("supabase_url") and config.get("supabase_key"):
        db = AstroWeatherDB(config["supabase_url"], config["supabase_key"])
    
    last_meteoblue = datetime.min
    meteoblue_interval = timedelta(seconds=config["meteoblue_poll_interval"])
    cw_interval = config["cloudwatcher_poll_interval"]
    
    while True:
        try:
            now = datetime.now()
            
            # CloudWatcher (immer)
            reading = task_poll_cloudwatcher(config)
            if reading and db:
                db.save_cloudwatcher(reading)
            
            # meteoblue (wenn Intervall erreicht)
            if now - last_meteoblue >= meteoblue_interval:
                conditions = task_fetch_meteoblue(config)
                if conditions:
                    if db:
                        db.save_meteoblue(conditions)
                        windows = task_find_windows(conditions, config)
                        for w in windows:
                            db.save_window(w)
                        task_send_notifications(db, config)
                    last_meteoblue = now
            
        except Exception as e:
            logger.error(f"Daemon error: {e}")
        
        time.sleep(cw_interval)


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Astro Weather Scheduler")
    parser.add_argument("--single", action="store_true", help="Single update (for cron)")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--test-cw", action="store_true", help="Test CloudWatcher only")
    parser.add_argument("--test-mb", action="store_true", help="Test meteoblue only")
    parser.add_argument("--force-mb", action="store_true", help="Force meteoblue fetch (ignore time check)")
    parser.add_argument("--status", action="store_true", help="Show current status")
    args = parser.parse_args()
    
    config = load_config()
    
    if args.test_cw:
        # Nur CloudWatcher testen
        reading = task_poll_cloudwatcher(config)
        if reading:
            print(json.dumps(reading.to_dict(), indent=2))
        else:
            print("Failed to read CloudWatcher")
            sys.exit(1)
    
    elif args.test_mb:
        # Nur meteoblue testen
        conditions = task_fetch_meteoblue(config)
        if conditions:
            print(f"Fetched {len(conditions)} hours")
            print("\nNext 12 hours:")
            for c in conditions[:12]:
                print(c.summary())
        else:
            print("Failed to fetch meteoblue")
            sys.exit(1)
    
    elif args.status:
        # Aktuellen Status zeigen
        print("=" * 60)
        print("ASTRO WEATHER STATUS")
        print("=" * 60)
        
        # CloudWatcher
        print("\n📡 CloudWatcher Solo:")
        reading = task_poll_cloudwatcher(config)
        if reading:
            print(f"   {reading.summary()}")
            print(f"   Safe for imaging: {'✅ Yes' if reading.is_safe_for_imaging else '❌ No'}")
        else:
            print("   ❌ Not reachable")
        
        # meteoblue
        print("\n🌤️  meteoblue Forecast:")
        conditions = task_fetch_meteoblue(config)
        if conditions:
            # Nächste gute Stunde finden
            good_hours = [c for c in conditions if c.astro_score >= 70 and c.is_astronomical_night()]
            if good_hours:
                next_good = good_hours[0]
                print(f"   Next good hour: {next_good.timestamp.strftime('%a %H:%M')} (Score: {next_good.astro_score})")
            else:
                print("   No good hours in forecast")
        
        print("=" * 60)
    
    elif args.single:
        # Einzelner Update (für Cron)
        status = run_single_update(config, force_mb=args.force_mb)
        print(json.dumps(status, indent=2, default=str))
        sys.exit(0 if status["cloudwatcher"]["success"] else 1)
    
    elif args.daemon:
        # Daemon-Modus
        run_daemon(config)
    
    else:
        parser.print_help()
        print("\n" + "=" * 60)
        print("QUICK STATUS:")
        print("=" * 60)
        
        # Zeige aktuelle Konfiguration
        print(f"\n📍 Location: {config['lat']}°N, {config['lon']}°E")
        print(f"📡 CloudWatcher: {config['cloudwatcher_host']}")
        print(f"🌤️  meteoblue: {'✓ configured' if config.get('meteoblue_api_key') else '❌ missing METEOBLUE_API_KEY'}")
        print(f"🗄️  Supabase: {'✓ configured' if config.get('supabase_url') else '❌ missing SUPABASE_URL'}")
        print(f"🔔 Pushover: {'✓ configured' if config.get('pushover_user') else '❌ not configured'}")
        
        print("\n" + "=" * 60)
        print("For Synology Task Scheduler, use: python scheduler.py --single")
        print("For continuous operation, use: python scheduler.py --daemon")
