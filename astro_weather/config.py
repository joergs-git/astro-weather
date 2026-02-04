#!/usr/bin/env python3
"""
Astrophotography Forecasting System
====================================

Configuration and startup script

Location: Wietesch/Rheine
"""

import os

# ============================================
# CONFIGURATION
# ============================================

CONFIG = {
    # Location Wietesch
    "location": {
        "name": "Wietesch",
        "lat": 52.17,
        "lon": 7.25,
        "timezone": "Europe/Berlin",
        "elevation_m": 45  # approx. elevation
    },

    # meteoblue API
    "meteoblue": {
        "api_key": os.environ.get("METEOBLUE_API_KEY", ""),
        "forecast_days": 7,
        # Combined package for all astro data
        "package": "seeing-1h_clouds-1h_moonlight-1h_air-1h_basic-1h",
        # Estimated credits per call (~40,000 for this package)
        "estimated_credits_per_call": 40000,
    },

    # Supabase
    "supabase": {
        "url": os.environ.get("SUPABASE_URL", ""),
        "key": os.environ.get("SUPABASE_KEY", ""),  # anon key for client
        "service_key": os.environ.get("SUPABASE_SERVICE_KEY", ""),  # for server
    },

    # CloudWatcher Solo
    "cloudwatcher": {
        "ip": os.environ.get("CLOUDWATCHER_IP", "192.168.1.100"),
        "port": 80,
        "poll_interval_seconds": 300,  # 5 minutes
    },

    # Scoring parameters
    "scoring": {
        # Weights for astro score
        "cloud_weight": 0.5,      # max -50 points
        "seeing_weight": 15,      # (arcsec - 1.0) * weight, max -30
        "jetstream_weight": 0.5,  # (speed - 35) * weight, max -10
        "moonlight_weight": 0.15, # moonlight * weight, max -10

        # Thresholds
        "min_score_for_window": 60,
        "min_window_hours": 2,
        "excellent_score": 85,
        "good_score": 70,
    },

    # Seeing classification
    "seeing_classes": {
        "excellent": (0.0, 0.8),
        "very_good": (0.8, 1.2),
        "good": (1.2, 1.5),
        "average": (1.5, 2.0),
        "below_average": (2.0, 2.5),
        "poor": (2.5, 3.0),
        "bad": (3.0, 99.0)
    },

    # Notifications
    "notifications": {
        "enabled": True,
        "min_score": 70,
        "min_hours": 3,
        "channels": ["email", "pushover"],  # Available: email, pushover, telegram

        # Email
        "email": {
            "smtp_server": os.environ.get("SMTP_SERVER", ""),
            "smtp_port": 587,
            "sender": os.environ.get("EMAIL_SENDER", ""),
            "recipient": os.environ.get("EMAIL_RECIPIENT", ""),
            "password": os.environ.get("EMAIL_PASSWORD", ""),
        },

        # Pushover (https://pushover.net)
        "pushover": {
            "user_key": os.environ.get("PUSHOVER_USER", ""),
            "api_token": os.environ.get("PUSHOVER_TOKEN", ""),
        },
    },

    # Scheduler
    "scheduler": {
        # When to fetch meteoblue data (cron-like)
        "meteoblue_update_interval_minutes": 60,  # Every hour
        "meteoblue_update_hours": list(range(0, 24)),  # All hours

        # CloudWatcher polling
        "cloudwatcher_poll_interval_seconds": 300,  # 5 minutes

        # Training pair creation
        "training_pair_interval_hours": 6,
    },

    # Logging
    "logging": {
        "level": "INFO",
        "file": "/var/log/astro_weather/app.log",
        "max_size_mb": 10,
        "backup_count": 5,
    }
}


# ============================================
# HELPER FUNCTIONS
# ============================================

def validate_config() -> list:
    """Validates the configuration and returns warnings"""
    warnings = []

    if not CONFIG["meteoblue"]["api_key"]:
        warnings.append("METEOBLUE_API_KEY not set!")

    if not CONFIG["supabase"]["url"]:
        warnings.append("SUPABASE_URL not set (data will not be saved)")

    if not CONFIG["supabase"]["key"]:
        warnings.append("SUPABASE_KEY not set (data will not be saved)")

    if CONFIG["notifications"]["enabled"]:
        if not CONFIG["notifications"]["email"]["smtp_server"]:
            warnings.append("Email notification enabled but SMTP not configured")

    return warnings


def print_config_summary():
    """Prints a summary of the configuration"""
    print("=" * 60)
    print("ASTRO WEATHER SYSTEM - CONFIGURATION")
    print("=" * 60)

    print(f"\nLocation: {CONFIG['location']['name']}")
    print(f"   Coordinates: {CONFIG['location']['lat']}N, {CONFIG['location']['lon']}E")
    print(f"   Timezone: {CONFIG['location']['timezone']}")

    print(f"\nmeteoblue:")
    if CONFIG['meteoblue']['api_key']:
        print(f"   API Key: {CONFIG['meteoblue']['api_key'][:8]}...")
    else:
        print(f"   API Key: not set")
    print(f"   Package: {CONFIG['meteoblue']['package']}")
    print(f"   Update interval: {CONFIG['scheduler']['meteoblue_update_interval_minutes']} min")

    print(f"\nSupabase:")
    if CONFIG["supabase"]["url"]:
        print(f"   URL: {CONFIG['supabase']['url'][:40]}...")
        print(f"   Key: {'set' if CONFIG['supabase']['key'] else 'missing'}")
    else:
        print("   Not configured")

    print(f"\nCloudWatcher:")
    print(f"   IP: {CONFIG['cloudwatcher']['ip']}")
    print(f"   Poll interval: {CONFIG['cloudwatcher']['poll_interval_seconds']}s")

    print(f"\nNotifications:")
    print(f"   Enabled: {'yes' if CONFIG['notifications']['enabled'] else 'no'}")
    if CONFIG["notifications"]["enabled"]:
        print(f"   Min Score: {CONFIG['notifications']['min_score']}")
        print(f"   Min Hours: {CONFIG['notifications']['min_hours']}")

    warnings = validate_config()
    if warnings:
        print("\nWARNINGS:")
        for w in warnings:
            print(f"   - {w}")
    else:
        print("\nConfiguration complete!")

    print("=" * 60)


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print_config_summary()
