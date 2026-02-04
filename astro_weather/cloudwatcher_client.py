#!/usr/bin/env python3
"""
CloudWatcher Solo Client for Synology NAS
==========================================

Polls the CloudWatcher Solo via HTTP and pushes data to Supabase.
Designed for Synology Task Scheduler or as daemon.

Location: Wietesch/Rheine
Solo URL: http://192.168.1.151/cgi-bin/cgiLastData
"""

import requests
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Dict, Any
import os
import json
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# DATA MODEL
# ============================================

@dataclass
class CloudWatcherReading:
    """Single reading from CloudWatcher Solo"""

    # Timestamp (from Solo, GMT)
    timestamp: datetime

    # Clouds (the most important!)
    clouds: float              # Sky-Ambient temperature in °C (more negative = clearer)
    clouds_safe: int           # 0=cloudy/unsafe, 1=clear/safe for astro

    # Temperatures
    sky_temp: float            # IR sky temperature (rawir)
    ambient_temp: float        # Ambient temperature
    dew_point: float           # Dew point
    humidity: int              # Humidity %
    humidity_safe: int         # 0=too humid, 1=OK

    # Sky brightness (SQM value!)
    sky_brightness_mpsas: float  # mag/arcsec² (higher = darker, 18+ = good)
    light_safe: int              # 0=too bright, 1=dark enough

    # Rain
    rain: int                  # Wetness amount (raw value)
    rain_safe: int             # 0=wet, 1=dry

    # Wind (if connected)
    wind: float                # km/h (-1 = not connected)
    gust: float                # Gusts km/h
    wind_safe: int             # 0=too windy, 1=OK

    # Pressure
    pressure_abs: float        # Absolute pressure hPa
    pressure_rel: float        # Relative pressure hPa
    pressure_safe: int         # Less relevant for us

    # Overall status
    safe: int                  # 0=Unsafe, 1=Safe (all OK)

    # Device information
    serial: str
    firmware: str
    
    @property
    def is_clear(self) -> bool:
        """Is the sky clear? (clouds_safe=1)"""
        return self.clouds_safe == 1

    @property
    def is_cloudy(self) -> bool:
        """Is it cloudy? (clouds_safe=0)"""
        return self.clouds_safe == 0

    @property
    def sky_quality_name(self) -> str:
        """Readable sky quality"""
        if self.clouds_safe == 1:
            return "CLEAR"
        elif self.clouds_safe == 2:
            return "CLOUDY"
        else:
            return "UNKNOWN"
    
    @property
    def is_safe_for_imaging(self) -> bool:
        """Is it safe for imaging? (clear, dry, dark, overall safe)"""
        return (
            self.clouds_safe == 1 and  # Clear sky
            self.rain_safe == 1 and    # Dry
            self.light_safe == 1 and   # Dark enough
            self.safe == 1             # Overall status OK (1=safe)
        )
    
    @property
    def bortle_estimate(self) -> int:
        """
        Estimated Bortle class from SQM value
        
        SQM → Bortle:
        >21.75 → 1 (Excellent dark)
        21.5-21.75 → 2
        21.25-21.5 → 3
        20.5-21.25 → 4 (Rural/suburban transition)
        19.5-20.5 → 5
        18.5-19.5 → 6 (Bright suburban)
        <18.5 → 7-9 (Urban)
        """
        sqm = self.sky_brightness_mpsas
        if sqm >= 21.75: return 1
        elif sqm >= 21.5: return 2
        elif sqm >= 21.25: return 3
        elif sqm >= 20.5: return 4
        elif sqm >= 19.5: return 5
        elif sqm >= 18.5: return 6
        elif sqm >= 18.0: return 7
        else: return 8
    
    def to_dict(self) -> Dict[str, Any]:
        """Converts to dictionary for DB/JSON"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "clouds": self.clouds,
            "clouds_safe": self.clouds_safe,
            "sky_quality": self.sky_quality_name,
            "sky_temp": self.sky_temp,
            "ambient_temp": self.ambient_temp,
            "dew_point": self.dew_point,
            "humidity": self.humidity,
            "humidity_safe": self.humidity_safe,
            "sky_brightness_mpsas": self.sky_brightness_mpsas,
            "light_safe": self.light_safe,
            "bortle_estimate": self.bortle_estimate,
            "rain": self.rain,
            "rain_safe": self.rain_safe,
            "wind": self.wind if self.wind >= 0 else None,
            "gust": self.gust if self.gust >= 0 else None,
            "wind_safe": self.wind_safe,
            "pressure_abs": self.pressure_abs,
            "pressure_rel": self.pressure_rel,
            "safe": self.safe,
            "is_safe_for_imaging": self.is_safe_for_imaging,
            "serial": self.serial,
            "firmware": self.firmware
        }
    
    def summary(self) -> str:
        """Brief summary"""
        # Status icons based on correct logic
        overall = "✅" if self.is_safe_for_imaging else "❌"
        sky = "☀️ CLEAR" if self.clouds_safe == 1 else "☁️ CLOUDY"
        rain = "💧" if self.rain_safe == 0 else ""
        
        return (
            f"{overall} {self.timestamp.strftime('%H:%M:%S')} | "
            f"Sky: {sky} ({self.clouds:+.1f}°C) | "
            f"SQM: {self.sky_brightness_mpsas:.2f} (Bortle ~{self.bortle_estimate}) | "
            f"Temp: {self.ambient_temp:.1f}°C | "
            f"Hum: {self.humidity}% {rain}"
        )


# ============================================
# CLOUDWATCHER CLIENT
# ============================================

class CloudWatcherSoloClient:
    """
    Client for CloudWatcher Solo via HTTP
    """

    def __init__(self, host: str = "192.168.1.151", port: int = 80, timeout: int = 10):
        """
        Args:
            host: IP address of the Solo
            port: HTTP port (default 80)
            timeout: Request timeout in seconds
        """
        self.base_url = f"http://{host}:{port}"
        self.data_url = f"{self.base_url}/cgi-bin/cgiLastData"
        self.timeout = timeout
        self._last_reading: Optional[CloudWatcherReading] = None
        self._last_raw: Optional[str] = None
    
    def fetch(self) -> CloudWatcherReading:
        """
        Fetches current data from CloudWatcher Solo

        Returns:
            CloudWatcherReading with all sensor data

        Raises:
            requests.RequestException on connection errors
            ValueError on parse errors
        """
        logger.debug(f"Fetching data from {self.data_url}")
        
        response = requests.get(self.data_url, timeout=self.timeout)
        response.raise_for_status()
        
        self._last_raw = response.text
        reading = self._parse_response(response.text)
        self._last_reading = reading
        
        logger.info(f"CloudWatcher: {reading.summary()}")
        return reading
    
    def _parse_response(self, text: str) -> CloudWatcherReading:
        """
        Parses the key=value response from Solo

        Example input:
            dataGMTTime=2026/01/23 17:53:25
            cwinfo=Serial: 2653, FW: 5.89
            clouds=-8.360000
            ...
        """
        data = {}
        
        for line in text.strip().split('\n'):
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                data[key.strip()] = value.strip()
        
        # Parse timestamp (GMT)
        time_str = data.get("dataGMTTime", "")
        try:
            timestamp = datetime.strptime(time_str, "%Y/%m/%d %H:%M:%S")
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        except ValueError:
            timestamp = datetime.now(timezone.utc)
            logger.warning(f"Could not parse timestamp: {time_str}, using current time")
        
        # Parse device information
        cwinfo = data.get("cwinfo", "")
        serial = ""
        firmware = ""
        if "Serial:" in cwinfo:
            parts = cwinfo.split(",")
            for part in parts:
                if "Serial:" in part:
                    serial = part.split(":")[1].strip()
                elif "FW:" in part:
                    firmware = part.split(":")[1].strip()
        
        return CloudWatcherReading(
            timestamp=timestamp,
            clouds=float(data.get("clouds", 0)),
            clouds_safe=int(data.get("cloudsSafe", 0)),
            sky_temp=float(data.get("rawir", 0)),  # rawir is the actual IR measurement
            ambient_temp=float(data.get("temp", 0)),
            dew_point=float(data.get("dewp", 0)),
            humidity=int(data.get("hum", 0)),
            humidity_safe=int(data.get("humSafe", 1)),
            sky_brightness_mpsas=float(data.get("lightmpsas", 0)),
            light_safe=int(data.get("lightSafe", 1)),
            rain=int(data.get("rain", 0)),
            rain_safe=int(data.get("rainSafe", 1)),
            wind=float(data.get("wind", -1)),
            gust=float(data.get("gust", -1)),
            wind_safe=int(data.get("windSafe", 1)),
            pressure_abs=float(data.get("abspress", 0)),
            pressure_rel=float(data.get("relpress", 0)),
            pressure_safe=int(data.get("pressureSafe", 1)),
            safe=int(data.get("safe", 1)),
            serial=serial,
            firmware=firmware
        )
    
    def get_last_reading(self) -> Optional[CloudWatcherReading]:
        """Returns the last reading (without new request)"""
        return self._last_reading

    def get_last_raw(self) -> Optional[str]:
        """Returns the last raw response (for debugging)"""
        return self._last_raw

    def is_reachable(self) -> bool:
        """Checks if the Solo is reachable"""
        try:
            response = requests.get(self.base_url, timeout=5)
            return response.status_code == 200
        except:
            return False


# ============================================
# SUPABASE INTEGRATION
# ============================================

class CloudWatcherDatabase:
    """
    Stores CloudWatcher data in Supabase
    """
    
    def __init__(self, supabase_url: str, supabase_key: str):
        from supabase import create_client
        self.client = create_client(supabase_url, supabase_key)
        logger.info("Supabase client initialized for CloudWatcher")
    
    def insert_reading(self, reading: CloudWatcherReading) -> bool:
        """
        Saves a reading to the database

        Returns:
            True on success
        """
        record = {
            "timestamp": reading.timestamp.isoformat(),
            "sky_temperature": reading.sky_temp,
            "ambient_temperature": reading.ambient_temp,
            "sky_minus_ambient": reading.clouds,  # This is sky-ambient
            "sky_quality": reading.sky_quality_name,
            "sky_quality_raw": reading.clouds_safe,
            "rain_sensor": reading.rain,
            "light_sensor": reading.sky_brightness_mpsas,
            "humidity": reading.humidity,
            "raw_json": reading.to_dict()
        }
        
        try:
            result = self.client.table("cloudwatcher_readings") \
                .insert(record) \
                .execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"Failed to insert reading: {e}")
            return False
    
    def get_recent_readings(self, hours: int = 24) -> list:
        """Gets readings from the last N hours"""
        from datetime import timedelta
        
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        
        result = self.client.table("cloudwatcher_readings") \
            .select("*") \
            .gte("timestamp", since) \
            .order("timestamp", desc=True) \
            .execute()
        
        return result.data if result.data else []


# ============================================
# POLLING DAEMON
# ============================================

def run_polling_daemon(config: Dict[str, Any]):
    """
    Main loop for the polling daemon

    Args:
        config: Configuration with:
            - cloudwatcher_host
            - poll_interval_seconds
            - supabase_url (optional)
            - supabase_key (optional)
    """
    # CloudWatcher Client
    cw = CloudWatcherSoloClient(
        host=config.get("cloudwatcher_host", "192.168.1.151")
    )
    
    # Supabase (optional)
    db = None
    if config.get("supabase_url") and config.get("supabase_key"):
        try:
            db = CloudWatcherDatabase(
                config["supabase_url"],
                config["supabase_key"]
            )
            logger.info("Supabase integration enabled")
        except Exception as e:
            logger.warning(f"Could not initialize Supabase: {e}")
    
    poll_interval = config.get("poll_interval_seconds", 300)
    
    logger.info(f"Starting polling daemon (interval: {poll_interval}s)")
    logger.info(f"CloudWatcher: {cw.data_url}")
    
    while True:
        try:
            # Fetch data
            reading = cw.fetch()

            # Save to DB (if configured)
            if db:
                if db.insert_reading(reading):
                    logger.debug("Reading saved to Supabase")
                else:
                    logger.warning("Failed to save reading to Supabase")

            # Optional: Local JSON file for debugging
            if config.get("local_json_file"):
                with open(config["local_json_file"], "w") as f:
                    json.dump(reading.to_dict(), f, indent=2)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Error: {e}")

        # Wait
        time.sleep(poll_interval)


# ============================================
# SYNOLOGY-SPECIFIC: SINGLE POLL
# ============================================

def single_poll_and_save(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single poll - for Synology Task Scheduler

    Can be called as cron job every 5 minutes.

    Returns:
        Status dictionary
    """
    status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": False,
        "reading": None,
        "saved_to_db": False,
        "error": None
    }
    
    try:
        # Fetch CloudWatcher
        cw = CloudWatcherSoloClient(
            host=config.get("cloudwatcher_host", "192.168.1.151")
        )
        reading = cw.fetch()
        status["reading"] = reading.to_dict()

        # Save to Supabase
        if config.get("supabase_url") and config.get("supabase_key"):
            db = CloudWatcherDatabase(
                config["supabase_url"],
                config["supabase_key"]
            )
            status["saved_to_db"] = db.insert_reading(reading)
        
        status["success"] = True
        
    except Exception as e:
        status["error"] = str(e)
        logger.error(f"Single poll failed: {e}")
    
    return status


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CloudWatcher Solo Polling Client")
    parser.add_argument("--host", default="192.168.1.151", help="CloudWatcher IP")
    parser.add_argument("--interval", type=int, default=300, help="Poll interval in seconds")
    parser.add_argument("--single", action="store_true", help="Single poll (for cron)")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--test", action="store_true", help="Test connection only")
    args = parser.parse_args()

    # Configuration from environment variables
    config = {
        "cloudwatcher_host": args.host,
        "poll_interval_seconds": args.interval,
        "supabase_url": os.environ.get("SUPABASE_URL", ""),
        "supabase_key": os.environ.get("SUPABASE_KEY", ""),
        "local_json_file": os.environ.get("CW_JSON_FILE", ""),
    }
    
    if args.test:
        # Test connection only
        print(f"Testing connection to {args.host}...")
        cw = CloudWatcherSoloClient(host=args.host)
        
        if cw.is_reachable():
            print("✅ CloudWatcher is reachable")
            reading = cw.fetch()
            print("\n" + "=" * 60)
            print("CURRENT READING:")
            print("=" * 60)
            print(reading.summary())
            print("\nRAW DATA:")
            print("-" * 60)
            for k, v in reading.to_dict().items():
                print(f"  {k}: {v}")
        else:
            print("❌ CloudWatcher not reachable")
            exit(1)
    
    elif args.single:
        # Single poll (for Synology Task Scheduler)
        status = single_poll_and_save(config)
        print(json.dumps(status, indent=2))
        exit(0 if status["success"] else 1)
    
    elif args.daemon:
        # Run as daemon
        run_polling_daemon(config)

    else:
        # Default: Show help and test once
        parser.print_help()
        print("\n" + "=" * 60)
        print("QUICK TEST:")
        print("=" * 60)
        
        cw = CloudWatcherSoloClient(host=args.host)
        try:
            reading = cw.fetch()
            print(reading.summary())
            print("\n✅ CloudWatcher working! Use --single for cron or --daemon for continuous polling.")
        except Exception as e:
            print(f"❌ Error: {e}")

