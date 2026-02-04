#!/usr/bin/env python3
"""
Supabase Integration for Astrophotography Forecasting System
=============================================================

Stores meteoblue forecasts and CloudWatcher readings.
Finds observation windows and manages training data.
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import asdict
import logging

from supabase import create_client, Client

# Local import
from meteoblue_client import AstroConditions, MeteoblueAstroClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AstroDatabase:
    """
    Supabase wrapper for astrophotography data
    """

    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initializes the database connection

        Args:
            supabase_url: Supabase Project URL
            supabase_key: Supabase anon/service key
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        logger.info("Supabase client initialized")
    
    # ==========================================
    # METEOBLUE FORECASTS
    # ==========================================

    def upsert_hourly_forecast(self, conditions: List[AstroConditions]) -> int:
        """
        Saves/updates hourly forecasts

        Args:
            conditions: List of AstroConditions

        Returns:
            Number of inserted/updated rows
        """
        records = []
        for cond in conditions:
            record = {
                "timestamp": cond.timestamp.isoformat(),
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
            }
            records.append(record)
        
        # Upsert (INSERT ... ON CONFLICT UPDATE)
        result = self.client.table("meteoblue_hourly") \
            .upsert(records, on_conflict="timestamp") \
            .execute()
        
        count = len(result.data) if result.data else 0
        logger.info(f"Upserted {count} hourly forecasts")
        return count
    
    def get_forecast(self,
                     start: datetime,
                     end: datetime,
                     only_night: bool = False,
                     min_score: int = 0) -> List[Dict]:
        """
        Gets forecasts from the database

        Args:
            start: Start time
            end: End time
            only_night: Only astronomical night (zenith > 108°)
            min_score: Minimum astro score

        Returns:
            List of forecast dictionaries
        """
        query = self.client.table("meteoblue_hourly") \
            .select("*") \
            .gte("timestamp", start.isoformat()) \
            .lte("timestamp", end.isoformat()) \
            .gte("astro_score", min_score) \
            .order("timestamp")
        
        if only_night:
            query = query.gt("zenith_angle", 108)
        
        result = query.execute()
        return result.data if result.data else []
    
    def get_best_upcoming_hours(self, limit: int = 20) -> List[Dict]:
        """
        Gets the best upcoming hours
        """
        result = self.client.table("meteoblue_hourly") \
            .select("*") \
            .gt("timestamp", datetime.now().isoformat()) \
            .gt("zenith_angle", 108) \
            .order("astro_score", desc=True) \
            .limit(limit) \
            .execute()
        
        return result.data if result.data else []
    
    # ==========================================
    # CLOUDWATCHER READINGS
    # ==========================================

    def insert_cloudwatcher_reading(self,
                                    sky_temp: float,
                                    ambient_temp: float,
                                    sky_quality: str,
                                    raw_json: dict = None) -> bool:
        """
        Saves a CloudWatcher reading

        Args:
            sky_temp: Sky temperature (IR)
            ambient_temp: Ambient temperature
            sky_quality: CLEAR/CLOUDY/VERY_CLOUDY
            raw_json: Complete JSON from CloudWatcher

        Returns:
            True on success
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "sky_temperature": sky_temp,
            "ambient_temperature": ambient_temp,
            "sky_minus_ambient": sky_temp - ambient_temp,
            "sky_quality": sky_quality,
            "raw_json": raw_json
        }
        
        result = self.client.table("cloudwatcher_readings") \
            .insert(record) \
            .execute()
        
        return bool(result.data)
    
    def get_cloudwatcher_readings(self,
                                  start: datetime,
                                  end: datetime) -> List[Dict]:
        """Gets CloudWatcher readings for a time period"""
        result = self.client.table("cloudwatcher_readings") \
            .select("*") \
            .gte("timestamp", start.isoformat()) \
            .lte("timestamp", end.isoformat()) \
            .order("timestamp") \
            .execute()
        
        return result.data if result.data else []
    
    # ==========================================
    # TRAINING PAIRS
    # ==========================================

    def create_training_pairs(self,
                              start: datetime,
                              end: datetime) -> int:
        """
        Creates training pairs from forecasts and readings

        Matches meteoblue forecasts with CloudWatcher readings
        on an hourly basis.

        Returns:
            Number of created pairs
        """
        # Get all forecasts in time period
        forecasts = self.get_forecast(start, end)

        # Get all CloudWatcher readings
        readings = self.get_cloudwatcher_readings(start, end)
        
        if not forecasts or not readings:
            logger.warning("No data for training pairs")
            return 0
        
        # Group readings by hour
        readings_by_hour = {}
        for r in readings:
            hour = datetime.fromisoformat(r["timestamp"]).replace(minute=0, second=0, microsecond=0)
            if hour not in readings_by_hour:
                readings_by_hour[hour] = []
            readings_by_hour[hour].append(r)

        # Create pairs
        pairs = []
        for fc in forecasts:
            fc_hour = datetime.fromisoformat(fc["timestamp"]).replace(minute=0, second=0, microsecond=0)

            if fc_hour in readings_by_hour:
                # Average of readings in this hour
                hour_readings = readings_by_hour[fc_hour]
                avg_sky_temp = sum(r["sky_temperature"] for r in hour_readings) / len(hour_readings)
                avg_diff = sum(r["sky_minus_ambient"] for r in hour_readings) / len(hour_readings)

                # Most frequent quality
                qualities = [r["sky_quality"] for r in hour_readings]
                actual_quality = max(set(qualities), key=qualities.count)

                # Comparison: Was the forecast correct?
                forecast_clear = fc["totalcloud"] < 30
                actual_clear = actual_quality == "CLEAR"
                match = forecast_clear == actual_clear
                
                pair = {
                    "timestamp": fc_hour.isoformat(),
                    "forecast_seeing_arcsec": fc["seeing_arcsec"],
                    "forecast_totalcloud": fc["totalcloud"],
                    "forecast_astro_score": fc["astro_score"],
                    "actual_sky_temp": avg_sky_temp,
                    "actual_sky_quality": actual_quality,
                    "actual_sky_minus_ambient": avg_diff,
                    "cloud_classification_match": match,
                    "hour_of_day": fc_hour.hour,
                    "day_of_year": fc_hour.timetuple().tm_yday
                }
                pairs.append(pair)
        
        if pairs:
            result = self.client.table("training_pairs") \
                .upsert(pairs, on_conflict="timestamp") \
                .execute()
            count = len(result.data) if result.data else 0
            logger.info(f"Created {count} training pairs")
            return count
        
        return 0
    
    # ==========================================
    # OBSERVATION WINDOWS
    # ==========================================

    def save_observation_window(self, window: Dict) -> bool:
        """Saves an observation window"""
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
        
        result = self.client.table("observation_windows") \
            .insert(record) \
            .execute()
        
        return bool(result.data)
    
    def get_upcoming_windows(self, min_score: int = 60) -> List[Dict]:
        """Gets upcoming observation windows"""
        result = self.client.table("observation_windows") \
            .select("*") \
            .gt("start_time", datetime.now().isoformat()) \
            .gte("avg_score", min_score) \
            .order("start_time") \
            .execute()
        
        return result.data if result.data else []
    
    def mark_window_notified(self, window_id: int) -> bool:
        """Marks a window as notified"""
        result = self.client.table("observation_windows") \
            .update({
                "notified": True,
                "notification_sent_at": datetime.now().isoformat()
            }) \
            .eq("id", window_id) \
            .execute()
        
        return bool(result.data)
    
    # ==========================================
    # STATISTICS
    # ==========================================

    def get_daily_summary(self, date: datetime = None) -> Dict:
        """
        Gets the daily summary

        Args:
            date: Date (default: today)

        Returns:
            Dictionary with daily statistics
        """
        if date is None:
            date = datetime.now()
        
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        forecasts = self.get_forecast(start, end)
        
        if not forecasts:
            return {"date": date.date().isoformat(), "data": None}
        
        night_hours = [f for f in forecasts if f["zenith_angle"] > 108]
        good_hours = [f for f in night_hours if f["astro_score"] >= 70]
        
        return {
            "date": date.date().isoformat(),
            "total_hours": len(forecasts),
            "night_hours": len(night_hours),
            "good_hours": len(good_hours),
            "best_score": max(f["astro_score"] for f in night_hours) if night_hours else None,
            "best_seeing": min(f["seeing_arcsec"] for f in night_hours) if night_hours else None,
            "avg_clouds": sum(f["totalcloud"] for f in night_hours) / len(night_hours) if night_hours else None
        }
    
    # ==========================================
    # API LOGGING
    # ==========================================

    def log_api_call(self,
                     api_name: str,
                     endpoint: str,
                     credits_used: int,
                     success: bool,
                     response_time_ms: int = 0,
                     error_message: str = None) -> None:
        """Logs an API call"""
        record = {
            "api_name": api_name,
            "endpoint": endpoint,
            "credits_used": credits_used,
            "success": success,
            "response_time_ms": response_time_ms,
            "error_message": error_message
        }
        
        self.client.table("api_call_log").insert(record).execute()


# ============================================
# MAIN PROGRAM: Scheduler/Cron Job
# ============================================

def run_hourly_update(config: Dict) -> Dict:
    """
    Hourly update job

    1. Fetches new meteoblue forecast
    2. Saves to Supabase
    3. Finds observation windows
    4. Optional: Sends notification

    Args:
        config: Configuration with API keys etc.

    Returns:
        Status dictionary
    """
    import time
    start_time = time.time()
    
    # Initialization
    db = AstroDatabase(
        config["supabase_url"],
        config["supabase_key"]
    )
    
    client = MeteoblueAstroClient(
        config["meteoblue_api_key"],
        config["lat"],
        config["lon"]
    )
    
    status = {
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "hours_fetched": 0,
        "hours_saved": 0,
        "windows_found": 0,
        "credits_used": 0,
        "error": None
    }
    
    try:
        # 1. Fetch forecast
        conditions = client.fetch_astro_forecast(forecast_days=7)
        status["hours_fetched"] = len(conditions)
        status["credits_used"] = client.get_credits_used()

        # 2. Save to DB
        saved = db.upsert_hourly_forecast(conditions)
        status["hours_saved"] = saved

        # 3. Find observation windows
        windows = client.get_best_windows(conditions, min_score=60, min_hours=2)
        status["windows_found"] = len(windows)

        # 4. Save new windows
        for w in windows:
            db.save_observation_window(w)

        # 5. Log API call
        response_time = int((time.time() - start_time) * 1000)
        db.log_api_call(
            "meteoblue",
            client.ASTRO_PACKAGE,
            status["credits_used"],
            True,
            response_time
        )
        
        status["success"] = True
        logger.info(f"Hourly update complete: {status}")
        
    except Exception as e:
        status["error"] = str(e)
        logger.error(f"Hourly update failed: {e}")
    
    return status


# ============================================
# DEMO
# ============================================

if __name__ == "__main__":
    # Configuration from environment variables or directly
    config = {
        "supabase_url": os.environ.get("SUPABASE_URL", "https://YOUR_PROJECT.supabase.co"),
        "supabase_key": os.environ.get("SUPABASE_KEY", "YOUR_ANON_KEY"),
        "meteoblue_api_key": os.environ.get("METEOBLUE_API_KEY", ""),
        "lat": 52.17,
        "lon": 7.25
    }
    
    print("=" * 60)
    print("ASTRO DATABASE - DEMO")
    print("=" * 60)
    
    if "YOUR_PROJECT" in config["supabase_url"]:
        print("\nPlease configure Supabase credentials!")
        print("   Set SUPABASE_URL and SUPABASE_KEY as environment variables")
        print("   or enter them directly in config.")
        print("\n   Example:")
        print("   export SUPABASE_URL='https://abc123.supabase.co'")
        print("   export SUPABASE_KEY='eyJ...'")
    else:
        # Run update
        status = run_hourly_update(config)
        print(f"\nStatus: {status}")
