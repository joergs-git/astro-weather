#!/usr/bin/env python3
"""
Astrophotographie Vorhersage-System
===================================

Konfiguration und Startskript

Standort: Wietesch/Rheine
"""

import os

# ============================================
# KONFIGURATION
# ============================================

CONFIG = {
    # Standort Wietesch
    "location": {
        "name": "Wietesch",
        "lat": 52.17,
        "lon": 7.25,
        "timezone": "Europe/Berlin",
        "elevation_m": 45  # ca. Höhe
    },
    
    # meteoblue API
    "meteoblue": {
        "api_key": os.environ.get("METEOBLUE_API_KEY", ""),
        "forecast_days": 7,
        # Kombiniertes Paket für alle Astro-Daten
        "package": "seeing-1h_clouds-1h_moonlight-1h_air-1h_basic-1h",
        # Geschätzte Credits pro Call (~40.000 für dieses Paket)
        "estimated_credits_per_call": 40000,
    },
    
    # Supabase
    "supabase": {
        "url": os.environ.get("SUPABASE_URL", ""),
        "key": os.environ.get("SUPABASE_KEY", ""),  # anon key für Client
        "service_key": os.environ.get("SUPABASE_SERVICE_KEY", ""),  # für Server
    },
    
    # CloudWatcher Solo
    "cloudwatcher": {
        "ip": os.environ.get("CLOUDWATCHER_IP", "192.168.1.100"),
        "port": 80,
        "poll_interval_seconds": 300,  # 5 Minuten
    },
    
    # Scoring-Parameter
    "scoring": {
        # Gewichtungen für Astro-Score
        "cloud_weight": 0.5,      # max -50 Punkte
        "seeing_weight": 15,      # (arcsec - 1.0) * weight, max -30
        "jetstream_weight": 0.5,  # (speed - 35) * weight, max -10
        "moonlight_weight": 0.15, # moonlight * weight, max -10
        
        # Thresholds
        "min_score_for_window": 60,
        "min_window_hours": 2,
        "excellent_score": 85,
        "good_score": 70,
    },
    
    # Seeing-Klassifikation
    "seeing_classes": {
        "excellent": (0.0, 0.8),
        "very_good": (0.8, 1.2),
        "good": (1.2, 1.5),
        "average": (1.5, 2.0),
        "below_average": (2.0, 2.5),
        "poor": (2.5, 3.0),
        "bad": (3.0, 99.0)
    },
    
    # Benachrichtigungen
    "notifications": {
        "enabled": True,
        "min_score": 70,
        "min_hours": 3,
        "channels": ["email", "pushover"],  # Verfügbare: email, pushover, telegram
        
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
        # Wann meteoblue Daten abrufen (cron-ähnlich)
        "meteoblue_update_interval_minutes": 60,  # Jede Stunde
        "meteoblue_update_hours": list(range(0, 24)),  # Alle Stunden
        
        # CloudWatcher Polling
        "cloudwatcher_poll_interval_seconds": 300,  # 5 Minuten
        
        # Training-Pair Erstellung
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
# HILFSFUNKTIONEN
# ============================================

def validate_config() -> list:
    """Validiert die Konfiguration und gibt Warnungen zurück"""
    warnings = []
    
    if not CONFIG["meteoblue"]["api_key"]:
        warnings.append("❌ METEOBLUE_API_KEY nicht gesetzt!")
    
    if not CONFIG["supabase"]["url"]:
        warnings.append("⚠️  SUPABASE_URL nicht gesetzt (Daten werden nicht gespeichert)")
    
    if not CONFIG["supabase"]["key"]:
        warnings.append("⚠️  SUPABASE_KEY nicht gesetzt (Daten werden nicht gespeichert)")
    
    if CONFIG["notifications"]["enabled"]:
        if not CONFIG["notifications"]["email"]["smtp_server"]:
            warnings.append("⚠️  Email-Benachrichtigung aktiviert, aber SMTP nicht konfiguriert")
    
    return warnings


def print_config_summary():
    """Gibt eine Zusammenfassung der Konfiguration aus"""
    print("=" * 60)
    print("ASTRO WEATHER SYSTEM - KONFIGURATION")
    print("=" * 60)
    
    print(f"\n📍 Standort: {CONFIG['location']['name']}")
    print(f"   Koordinaten: {CONFIG['location']['lat']}°N, {CONFIG['location']['lon']}°E")
    print(f"   Timezone: {CONFIG['location']['timezone']}")
    
    print(f"\n🌤️  meteoblue:")
    print(f"   API Key: {CONFIG['meteoblue']['api_key'][:8]}...")
    print(f"   Paket: {CONFIG['meteoblue']['package']}")
    print(f"   Update-Intervall: {CONFIG['scheduler']['meteoblue_update_interval_minutes']} min")
    
    print(f"\n🗄️  Supabase:")
    if CONFIG["supabase"]["url"]:
        print(f"   URL: {CONFIG['supabase']['url'][:40]}...")
        print(f"   Key: {'✓ gesetzt' if CONFIG['supabase']['key'] else '❌ fehlt'}")
    else:
        print("   ⚠️  Nicht konfiguriert")
    
    print(f"\n📡 CloudWatcher:")
    print(f"   IP: {CONFIG['cloudwatcher']['ip']}")
    print(f"   Poll-Intervall: {CONFIG['cloudwatcher']['poll_interval_seconds']}s")
    
    print(f"\n🔔 Benachrichtigungen:")
    print(f"   Aktiviert: {'✓' if CONFIG['notifications']['enabled'] else '❌'}")
    if CONFIG["notifications"]["enabled"]:
        print(f"   Min Score: {CONFIG['notifications']['min_score']}")
        print(f"   Min Stunden: {CONFIG['notifications']['min_hours']}")
    
    warnings = validate_config()
    if warnings:
        print("\n⚠️  WARNUNGEN:")
        for w in warnings:
            print(f"   {w}")
    else:
        print("\n✅ Konfiguration vollständig!")
    
    print("=" * 60)


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print_config_summary()
