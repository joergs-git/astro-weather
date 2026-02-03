#!/usr/bin/env python3
"""
meteoblue API Client für Astrophotographie
==========================================

Ruft alle relevanten Wetterdaten für Astrophotographie ab:
- Seeing (Arcseconds, Index 1 & 2)
- Jet Stream & Bad Layers
- Wolkenschichten (Low/Mid/High)
- Nightsky Brightness
- Mond-Daten

Autor: Claude für Joerg @ Wietesch
"""

import os
import requests
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AstroConditions:
    """Astronomische Bedingungen für einen Zeitpunkt"""
    timestamp: datetime
    
    # Seeing
    seeing_arcsec: float          # Bogensekunden (kleiner = besser)
    seeing_index1: int            # 1-5 (1 = best)
    seeing_index2: int            # 1-5 (1 = best)
    jetstream_speed: float        # m/s (ideal: 10-25)
    
    # Bad Layers
    badlayer_bottom: Optional[int] = None   # Höhe in m
    badlayer_top: Optional[int] = None      # Höhe in m
    badlayer_gradient: Optional[float] = None  # K/100m
    
    # Wolken
    totalcloud: int = 0           # % (0-100)
    lowclouds: int = 0            # %
    midclouds: int = 0            # %
    highclouds: int = 0           # %
    visibility: int = 0           # m
    fog_probability: int = 0      # %
    
    # Himmelshelligkeit
    nightsky_brightness_actual: float = 0.0    # Lux
    nightsky_brightness_clearsky: float = 0.0  # Lux (zum Vergleich)
    moonlight_actual: float = 0.0              # % of full moon
    zenith_angle: float = 0.0                  # Grad (Sonne)
    
    # Basis-Wetter
    temperature: float = 0.0      # °C
    humidity: int = 0             # %
    precipitation_prob: int = 0   # %
    wind_speed: float = 0.0       # km/h
    
    # Berechnete Scores
    astro_score: int = field(init=False)
    quality_class: str = field(init=False)
    
    def __post_init__(self):
        self.astro_score = self._calculate_astro_score()
        self.quality_class = self._classify_quality()
    
    def _calculate_astro_score(self) -> int:
        """
        Berechnet Gesamt-Score (0-100) für Astrophotographie
        
        Gewichtung:
        - Wolken: max -50 Punkte
        - Seeing: max -30 Punkte  
        - Jet Stream: max -10 Punkte
        - Mondlicht/Helligkeit: max -10 Punkte
        """
        score = 100
        
        # Wolken (max -50)
        cloud_penalty = self.totalcloud * 0.5
        score -= cloud_penalty
        
        # Seeing in Arcseconds (max -30)
        # <1.0" = excellent, 1.0-1.5" = good, 1.5-2.5" = average, >2.5" = poor
        if self.seeing_arcsec > 1.0:
            seeing_penalty = min(30, (self.seeing_arcsec - 1.0) * 15)
            score -= seeing_penalty
        
        # Jet Stream (max -10)
        # Ideal: 10-25 m/s, schlecht: >35 oder <5
        if self.jetstream_speed > 35:
            jet_penalty = min(10, (self.jetstream_speed - 35) * 0.5)
            score -= jet_penalty
        elif self.jetstream_speed < 5:
            # Zu wenig Jet Stream kann auch problematisch sein (stehende Luft)
            score -= 3
        
        # Mondlicht (max -10) - nur relevant bei Nacht
        if self.zenith_angle > 90:  # Sonne unter Horizont
            if self.moonlight_actual > 30:
                moon_penalty = min(10, self.moonlight_actual * 0.15)
                score -= moon_penalty
        
        # Niederschlagswahrscheinlichkeit (Bonus-Malus)
        if self.precipitation_prob > 30:
            score -= min(10, self.precipitation_prob * 0.1)
        
        return max(0, min(100, int(score)))
    
    def _classify_quality(self) -> str:
        """Klassifiziert die Nacht-Qualität"""
        if self.astro_score >= 85:
            return "EXCELLENT"
        elif self.astro_score >= 70:
            return "GOOD"
        elif self.astro_score >= 50:
            return "AVERAGE"
        elif self.astro_score >= 30:
            return "POOR"
        else:
            return "BAD"
    
    def get_seeing_quality(self) -> str:
        """Klassifiziert nur das Seeing"""
        if self.seeing_arcsec < 0.8:
            return "Excellent (<0.8\")"
        elif self.seeing_arcsec < 1.2:
            return "Very Good (0.8-1.2\")"
        elif self.seeing_arcsec < 1.5:
            return "Good (1.2-1.5\")"
        elif self.seeing_arcsec < 2.0:
            return "Average (1.5-2.0\")"
        elif self.seeing_arcsec < 2.5:
            return "Below Average (2.0-2.5\")"
        elif self.seeing_arcsec < 3.0:
            return "Poor (2.5-3.0\")"
        else:
            return "Bad (>3.0\")"
    
    def is_night(self) -> bool:
        """Prüft ob es Nacht ist (Sonne unter Horizont)"""
        return self.zenith_angle > 90
    
    def is_astronomical_night(self) -> bool:
        """Prüft ob astronomische Nacht (Sonne >18° unter Horizont)"""
        return self.zenith_angle > 108
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert zu Dictionary für DB-Speicherung"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "seeing_arcsec": self.seeing_arcsec,
            "seeing_index1": self.seeing_index1,
            "seeing_index2": self.seeing_index2,
            "jetstream_speed": self.jetstream_speed,
            "badlayer_bottom": self.badlayer_bottom,
            "badlayer_top": self.badlayer_top,
            "badlayer_gradient": self.badlayer_gradient,
            "totalcloud": self.totalcloud,
            "lowclouds": self.lowclouds,
            "midclouds": self.midclouds,
            "highclouds": self.highclouds,
            "visibility": self.visibility,
            "fog_probability": self.fog_probability,
            "nightsky_brightness_actual": self.nightsky_brightness_actual,
            "nightsky_brightness_clearsky": self.nightsky_brightness_clearsky,
            "moonlight_actual": self.moonlight_actual,
            "zenith_angle": self.zenith_angle,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "precipitation_prob": self.precipitation_prob,
            "wind_speed": self.wind_speed,
            "astro_score": self.astro_score,
            "quality_class": self.quality_class
        }
    
    def summary(self) -> str:
        """Kurze Zusammenfassung für Anzeige"""
        night_status = "🌙" if self.is_astronomical_night() else "🌅" if self.is_night() else "☀️"
        
        quality_emoji = {
            "EXCELLENT": "🌟",
            "GOOD": "✨",
            "AVERAGE": "⭐",
            "POOR": "☁️",
            "BAD": "❌"
        }
        
        return (
            f"{night_status} {self.timestamp.strftime('%H:%M')} | "
            f"Score: {self.astro_score} {quality_emoji.get(self.quality_class, '')} | "
            f"Seeing: {self.seeing_arcsec:.1f}\" | "
            f"Clouds: {self.totalcloud}% | "
            f"Jet: {self.jetstream_speed:.0f}m/s"
        )


class MeteoblueAstroClient:
    """
    Client für meteoblue API mit Fokus auf Astrophotographie
    """
    
    BASE_URL = "https://my.meteoblue.com/packages"
    
    # Optimales kombiniertes Paket für Astrophotographie
    ASTRO_PACKAGE = "seeing-1h_clouds-1h_moonlight-1h_air-1h_basic-1h"
    
    def __init__(self, api_key: str, lat: float, lon: float, timezone: str = "Europe/Berlin"):
        self.api_key = api_key
        self.lat = lat
        self.lon = lon
        self.timezone = timezone
        self._last_response = None
        self._credits_used = 0
    
    def fetch_astro_forecast(self, forecast_days: int = 7) -> List[AstroConditions]:
        """
        Holt die komplette Astro-Vorhersage
        
        Args:
            forecast_days: Anzahl Tage (1-7)
        
        Returns:
            Liste von AstroConditions für jede Stunde
        """
        url = f"{self.BASE_URL}/{self.ASTRO_PACKAGE}"
        params = {
            "lat": self.lat,
            "lon": self.lon,
            "apikey": self.api_key,
            "format": "json",
            "forecast_days": min(7, max(1, forecast_days)),
            "tz": self.timezone
        }
        
        logger.info(f"Fetching astro forecast for {self.lat}°N, {self.lon}°E...")
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            self._last_response = response.json()
            self._credits_used = int(response.headers.get("X-Credits-Used", 0))
            
            logger.info(f"Received data, credits used: {self._credits_used}")
            
            return self._parse_response(self._last_response)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
    
    def _parse_response(self, data: Dict[str, Any]) -> List[AstroConditions]:
        """Parst die API-Antwort zu AstroConditions-Objekten"""
        conditions = []
        
        data_1h = data.get("data_1h", {})
        
        # Zeitstempel
        times = data_1h.get("time", [])
        
        # Extrahiere alle Arrays
        seeing_arcsec = data_1h.get("seeing_arcsec", [])
        seeing1 = data_1h.get("seeing1", [])
        seeing2 = data_1h.get("seeing2", [])
        jetstream = data_1h.get("jetstream", [])
        
        badlayer_bottom = data_1h.get("badlayer_bottom", [])
        badlayer_top = data_1h.get("badlayer_top", [])
        badlayer_gradient = data_1h.get("badlayer_gradient", [])
        
        totalcloud = data_1h.get("totalcloudcover", [])
        lowclouds = data_1h.get("lowclouds", [])
        midclouds = data_1h.get("midclouds", [])
        highclouds = data_1h.get("highclouds", [])
        visibility = data_1h.get("visibility", [])
        fog_prob = data_1h.get("fog_probability", [])
        
        nsb_actual = data_1h.get("nightskybrightness_actual", [])
        nsb_clearsky = data_1h.get("nightskybrightness_clearsky", [])
        moonlight = data_1h.get("moonlight_actual", [])
        zenith = data_1h.get("zenithangle", [])
        
        temperature = data_1h.get("temperature", [])
        humidity = data_1h.get("relativehumidity", [])
        precip_prob = data_1h.get("precipitation_probability", [])
        windspeed = data_1h.get("windspeed", [])
        
        for i, time_str in enumerate(times):
            try:
                # Parse timestamp - meteoblue liefert lokale Zeit (Europe/Berlin) ohne Timezone
                # Format: "2026-01-23 00:00"
                naive_ts = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                
                # Konvertiere lokale Zeit zu UTC
                # Europe/Berlin: UTC+1 (Winter/CET) oder UTC+2 (Sommer/CEST)
                # Sommerzeit: letzter Sonntag März bis letzter Sonntag Oktober
                from datetime import timezone as dt_tz, timedelta
                
                # Einfache Sommerzeitberechnung
                month = naive_ts.month
                if 4 <= month <= 10:
                    # April bis Oktober: wahrscheinlich Sommerzeit (UTC+2)
                    # (vereinfacht - exakte Berechnung wäre komplexer)
                    offset_hours = 2
                else:
                    # November bis März: Winterzeit (UTC+1)
                    offset_hours = 1
                
                local_tz = dt_tz(timedelta(hours=offset_hours))
                local_ts = naive_ts.replace(tzinfo=local_tz)
                ts = local_ts.astimezone(dt_tz.utc)
                
                cond = AstroConditions(
                    timestamp=ts,
                    seeing_arcsec=self._safe_get(seeing_arcsec, i, 2.0),
                    seeing_index1=int(self._safe_get(seeing1, i, 3)),
                    seeing_index2=int(self._safe_get(seeing2, i, 3)),
                    jetstream_speed=self._safe_get(jetstream, i, 20.0),
                    badlayer_bottom=self._safe_get(badlayer_bottom, i, None),
                    badlayer_top=self._safe_get(badlayer_top, i, None),
                    badlayer_gradient=self._safe_get(badlayer_gradient, i, None),
                    totalcloud=int(self._safe_get(totalcloud, i, 0)),
                    lowclouds=int(self._safe_get(lowclouds, i, 0)),
                    midclouds=int(self._safe_get(midclouds, i, 0)),
                    highclouds=int(self._safe_get(highclouds, i, 0)),
                    visibility=int(self._safe_get(visibility, i, 10000)),
                    fog_probability=int(self._safe_get(fog_prob, i, 0)),
                    nightsky_brightness_actual=self._safe_get(nsb_actual, i, 0.0),
                    nightsky_brightness_clearsky=self._safe_get(nsb_clearsky, i, 0.0),
                    moonlight_actual=self._safe_get(moonlight, i, 0.0),
                    zenith_angle=self._safe_get(zenith, i, 0.0),
                    temperature=self._safe_get(temperature, i, 10.0),
                    humidity=int(self._safe_get(humidity, i, 50)),
                    precipitation_prob=int(self._safe_get(precip_prob, i, 0)),
                    wind_speed=self._safe_get(windspeed, i, 0.0)
                )
                conditions.append(cond)
                
            except Exception as e:
                logger.warning(f"Failed to parse hour {i}: {e}")
                continue
        
        return conditions
    
    @staticmethod
    def _safe_get(arr: list, idx: int, default):
        """Sicherer Array-Zugriff mit Default-Wert"""
        try:
            val = arr[idx] if idx < len(arr) else default
            return val if val is not None else default
        except (IndexError, TypeError):
            return default
    
    def get_best_windows(self, 
                         conditions: List[AstroConditions],
                         min_score: int = 60,
                         min_hours: int = 2,
                         only_night: bool = True) -> List[Dict]:
        """
        Findet die besten Beobachtungsfenster
        
        Args:
            conditions: Liste von AstroConditions
            min_score: Minimaler Astro-Score (0-100)
            min_hours: Minimale Fensterlänge in Stunden
            only_night: Nur astronomische Nacht berücksichtigen
        
        Returns:
            Liste von Fenstern mit Start, Ende, Durchschnitts-Score
        """
        windows = []
        current_window = None
        
        for cond in conditions:
            # Filter: Nur Nacht und min. Score
            is_valid = cond.astro_score >= min_score
            if only_night:
                is_valid = is_valid and cond.is_astronomical_night()
            
            if is_valid:
                if current_window is None:
                    current_window = {
                        "start": cond.timestamp,
                        "end": cond.timestamp,
                        "conditions": [cond],
                        "scores": [cond.astro_score]
                    }
                else:
                    current_window["end"] = cond.timestamp
                    current_window["conditions"].append(cond)
                    current_window["scores"].append(cond.astro_score)
            else:
                # Fenster beenden
                if current_window is not None:
                    hours = len(current_window["conditions"])
                    if hours >= min_hours:
                        current_window["hours"] = hours
                        current_window["avg_score"] = sum(current_window["scores"]) / hours
                        current_window["min_score"] = min(current_window["scores"])
                        current_window["avg_seeing"] = sum(c.seeing_arcsec for c in current_window["conditions"]) / hours
                        current_window["avg_clouds"] = sum(c.totalcloud for c in current_window["conditions"]) / hours
                        windows.append(current_window)
                    current_window = None
        
        # Letztes Fenster nicht vergessen
        if current_window is not None:
            hours = len(current_window["conditions"])
            if hours >= min_hours:
                current_window["hours"] = hours
                current_window["avg_score"] = sum(current_window["scores"]) / hours
                current_window["min_score"] = min(current_window["scores"])
                current_window["avg_seeing"] = sum(c.seeing_arcsec for c in current_window["conditions"]) / hours
                current_window["avg_clouds"] = sum(c.totalcloud for c in current_window["conditions"]) / hours
                windows.append(current_window)
        
        # Nach Durchschnitts-Score sortieren
        windows.sort(key=lambda w: w["avg_score"], reverse=True)
        
        return windows
    
    def get_credits_used(self) -> int:
        """Gibt die beim letzten Call verbrauchten Credits zurück"""
        return self._credits_used
    
    def get_raw_response(self) -> Optional[Dict]:
        """Gibt die letzte Roh-Antwort zurück"""
        return self._last_response


# ============================================
# DEMO / TEST
# ============================================

if __name__ == "__main__":
    # Konfiguration
    API_KEY = os.environ.get("METEOBLUE_API_KEY", "")
    LAT = 52.17  # Wietesch (korrigiert)
    LON = 7.25
    
    print("=" * 70)
    print("METEOBLUE ASTRO CLIENT - DEMO")
    print(f"Standort: Wietesch ({LAT}°N, {LON}°E)")
    print("=" * 70)
    print()
    
    # Client erstellen
    client = MeteoblueAstroClient(API_KEY, LAT, LON)
    
    # Vorhersage abrufen
    print("Lade 7-Tage Astro-Vorhersage...")
    conditions = client.fetch_astro_forecast(forecast_days=7)
    print(f"✓ {len(conditions)} Stunden geladen")
    print()
    
    # Zeige die nächsten 24 Stunden
    print("NÄCHSTE 24 STUNDEN:")
    print("-" * 70)
    for cond in conditions[:24]:
        print(cond.summary())
    print()
    
    # Beste Fenster finden
    print("BESTE BEOBACHTUNGSFENSTER (Score >= 60, mind. 2h):")
    print("-" * 70)
    windows = client.get_best_windows(conditions, min_score=60, min_hours=2)
    
    if windows:
        for i, w in enumerate(windows[:5], 1):
            print(f"\n{i}. {w['start'].strftime('%a %d.%m. %H:%M')} - {w['end'].strftime('%H:%M')}")
            print(f"   Dauer: {w['hours']}h | Ø Score: {w['avg_score']:.0f} | Min: {w['min_score']}")
            print(f"   Ø Seeing: {w['avg_seeing']:.1f}\" | Ø Wolken: {w['avg_clouds']:.0f}%")
    else:
        print("⚠️  Keine guten Fenster in den nächsten 7 Tagen gefunden")
    
    print()
    print("=" * 70)
    print(f"Credits verwendet: {client.get_credits_used()}")
    print("=" * 70)
