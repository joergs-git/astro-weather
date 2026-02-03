-- ============================================
-- SUPABASE SCHEMA: Astrophotographie Vorhersage
-- Standort: Wietesch/Rheine (52.17°N, 7.25°E)
-- ============================================

-- Aktiviere UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. METEOBLUE STÜNDLICHE VORHERSAGEN
-- ============================================

CREATE TABLE IF NOT EXISTS meteoblue_hourly (
    id BIGSERIAL PRIMARY KEY,
    
    -- Zeitstempel (UTC)
    timestamp TIMESTAMPTZ NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- SEEING (das wichtigste für Astro!)
    seeing_arcsec DECIMAL(4,2),           -- Bogensekunden (0.5 - 5.0)
    seeing_index1 SMALLINT,               -- 1-5 (1 = best)
    seeing_index2 SMALLINT,               -- 1-5 (1 = best)
    
    -- JET STREAM & BAD LAYERS
    jetstream_speed DECIMAL(5,1),         -- m/s
    badlayer_bottom INTEGER,              -- Höhe in m
    badlayer_top INTEGER,                 -- Höhe in m
    badlayer_gradient DECIMAL(4,2),       -- K/100m
    
    -- WOLKEN
    totalcloud SMALLINT,                  -- % (0-100)
    lowclouds SMALLINT,                   -- %
    midclouds SMALLINT,                   -- %
    highclouds SMALLINT,                  -- %
    visibility INTEGER,                   -- m
    fog_probability SMALLINT,             -- %
    
    -- HIMMELSHELLIGKEIT
    nightsky_brightness_actual DECIMAL(10,6),    -- Lux
    nightsky_brightness_clearsky DECIMAL(10,6),  -- Lux
    moonlight_actual DECIMAL(5,2),               -- % of full moon
    zenith_angle DECIMAL(5,2),                   -- Grad
    
    -- BASIS-WETTER
    temperature DECIMAL(4,1),             -- °C
    humidity SMALLINT,                    -- %
    precipitation_prob SMALLINT,          -- %
    wind_speed DECIMAL(4,1),              -- km/h
    wind_direction SMALLINT,              -- Grad
    
    -- BERECHNETE SCORES
    astro_score SMALLINT,                 -- 0-100
    quality_class VARCHAR(20),            -- EXCELLENT/GOOD/AVERAGE/POOR/BAD
    
    -- CONSTRAINT: Ein Eintrag pro Stunde
    UNIQUE(timestamp)
);

-- Index für schnelle Abfragen
CREATE INDEX idx_meteoblue_timestamp ON meteoblue_hourly(timestamp);
CREATE INDEX idx_meteoblue_score ON meteoblue_hourly(astro_score DESC);
CREATE INDEX idx_meteoblue_quality ON meteoblue_hourly(quality_class, timestamp);


-- ============================================
-- 2. CLOUDWATCHER SOLO MESSUNGEN (Ground Truth)
-- ============================================

CREATE TABLE IF NOT EXISTS cloudwatcher_readings (
    id BIGSERIAL PRIMARY KEY,
    
    -- Zeitstempel
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Kernmessungen
    sky_temperature DECIMAL(5,2),         -- °C (IR-Messung, rawir)
    ambient_temperature DECIMAL(5,2),     -- °C
    sky_minus_ambient DECIMAL(5,2),       -- °C (clouds Wert, negativer = klarer)
    
    -- Klassifikation (KORRIGIERT: 0=cloudy, 1=clear)
    sky_quality VARCHAR(20),              -- CLEAR/CLOUDY
    sky_quality_raw SMALLINT,             -- 0=Cloudy/Unsafe, 1=Clear/Safe
    
    -- Himmelshelligkeit (SQM)
    light_sensor DECIMAL(5,2),            -- mag/arcsec² (lightmpsas)
    light_safe SMALLINT,                  -- 0=zu hell, 1=dunkel genug
    
    -- Regen
    rain_sensor INTEGER,                  -- Nässemenge Rohwert
    rain_safe SMALLINT,                   -- 0=nass, 1=trocken
    
    -- Weitere Sensoren
    humidity SMALLINT,                    -- %
    humidity_safe SMALLINT,               -- 0=zu feucht, 1=OK
    dew_point DECIMAL(5,2),               -- °C
    
    -- Druck
    pressure_abs DECIMAL(7,2),            -- hPa
    pressure_rel DECIMAL(7,2),            -- hPa
    
    -- Gesamtstatus (KORRIGIERT: 0=safe, 1=unsafe)
    safe SMALLINT,                        -- 0=Safe (alles OK), 1=Unsafe
    
    -- Geräteinformationen
    device_serial VARCHAR(20),
    device_firmware VARCHAR(20),
    
    -- Rohdaten für Debugging
    raw_json JSONB,
    
    UNIQUE(timestamp)
);

CREATE INDEX idx_cw_timestamp ON cloudwatcher_readings(timestamp);
CREATE INDEX idx_cw_quality ON cloudwatcher_readings(sky_quality_raw, timestamp);


-- ============================================
-- 3. TRAINING PAIRS (Vorhersage vs. Realität)
-- ============================================

CREATE TABLE IF NOT EXISTS training_pairs (
    id BIGSERIAL PRIMARY KEY,
    
    -- Zeitstempel (auf volle Stunde gerundet)
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Vorhersage (von meteoblue)
    forecast_seeing_arcsec DECIMAL(4,2),
    forecast_totalcloud SMALLINT,
    forecast_astro_score SMALLINT,
    
    -- Realität (vom CloudWatcher)
    actual_sky_temp DECIMAL(5,2),
    actual_sky_minus_ambient DECIMAL(5,2),
    actual_clouds_safe SMALLINT,          -- 0=cloudy, 1=clear
    actual_sqm DECIMAL(5,2),              -- SQM Wert
    
    -- Berechnete Fehler
    cloud_classification_match BOOLEAN,   -- Hat die Vorhersage gestimmt?
    -- meteoblue sagt klar (<30% clouds) UND Solo sagt klar (clouds_safe=1)
    
    seeing_available BOOLEAN DEFAULT FALSE,  -- Haben wir FWHM-Messung?
    actual_fwhm_arcsec DECIMAL(4,2),      -- Gemessenes FWHM aus Aufnahmen
    seeing_error DECIMAL(4,2),            -- forecast - actual
    
    -- Wetterbedingungen für ML-Features
    hour_of_day SMALLINT,
    day_of_year SMALLINT,
    
    UNIQUE(timestamp)
);

CREATE INDEX idx_training_timestamp ON training_pairs(timestamp);


-- ============================================
-- 4. BEOBACHTUNGSFENSTER (gefundene gute Nächte)
-- ============================================

CREATE TABLE IF NOT EXISTS observation_windows (
    id BIGSERIAL PRIMARY KEY,
    
    -- Zeitraum
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    duration_hours DECIMAL(4,1),
    
    -- Durchschnittswerte
    avg_score SMALLINT,
    min_score SMALLINT,
    avg_seeing_arcsec DECIMAL(4,2),
    avg_clouds SMALLINT,
    avg_jetstream DECIMAL(5,1),
    
    -- Status
    notified BOOLEAN DEFAULT FALSE,
    notification_sent_at TIMESTAMPTZ,
    
    -- Wurde beobachtet?
    was_used BOOLEAN,
    user_rating SMALLINT,                 -- 1-5 Sterne vom Nutzer
    user_notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_windows_start ON observation_windows(start_time);
CREATE INDEX idx_windows_score ON observation_windows(avg_score DESC);


-- ============================================
-- 5. SEEING-QUALITÄTS-REFERENZ
-- ============================================

CREATE TABLE IF NOT EXISTS seeing_quality_reference (
    id SERIAL PRIMARY KEY,
    arcsec_min DECIMAL(4,2),
    arcsec_max DECIMAL(4,2),
    quality_name VARCHAR(30),
    quality_code VARCHAR(10),
    description TEXT,
    suitable_for TEXT
);

INSERT INTO seeing_quality_reference (arcsec_min, arcsec_max, quality_name, quality_code, description, suitable_for)
VALUES
    (0.0, 0.8, 'Excellent', 'A', 'Sub-arcsecond seeing, professionelle Qualität', 'Planetenfotografie, hochauflösende Deep Sky'),
    (0.8, 1.2, 'Very Good', 'B', 'Sehr gutes Seeing, selten in Mitteleuropa', 'Galaxien-Details, Planetarische Nebel'),
    (1.2, 1.5, 'Good', 'C', 'Gutes Seeing für Deep Sky', 'Die meisten Deep Sky Objekte'),
    (1.5, 2.0, 'Average', 'D', 'Durchschnittlich, brauchbar', 'Helle Nebel, große Galaxien'),
    (2.0, 2.5, 'Below Average', 'E', 'Unterdurchschnittlich', 'Nur großflächige Objekte'),
    (2.5, 3.0, 'Poor', 'F', 'Schlechtes Seeing', 'Widefield, nur helle Objekte'),
    (3.0, 99.0, 'Bad', 'G', 'Unbrauchbar für Imaging', 'Nur visuell oder aufschiebbarer Imaging');


-- ============================================
-- 6. API CALL LOG (für Credit-Tracking)
-- ============================================

CREATE TABLE IF NOT EXISTS api_call_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    api_name VARCHAR(50),                 -- 'meteoblue', 'open-meteo', etc.
    endpoint VARCHAR(100),
    credits_used INTEGER,
    success BOOLEAN,
    error_message TEXT,
    response_time_ms INTEGER
);

CREATE INDEX idx_api_log_timestamp ON api_call_log(timestamp);
CREATE INDEX idx_api_log_name ON api_call_log(api_name, timestamp);


-- ============================================
-- 7. VIEWS FÜR EINFACHE ABFRAGEN
-- ============================================

-- Nur astronomische Nächte (Sonne > 18° unter Horizont)
CREATE OR REPLACE VIEW v_astronomical_nights AS
SELECT *
FROM meteoblue_hourly
WHERE zenith_angle > 108
ORDER BY timestamp;

-- Beste Stunden der nächsten 7 Tage
CREATE OR REPLACE VIEW v_best_hours AS
SELECT 
    timestamp,
    seeing_arcsec,
    totalcloud,
    jetstream_speed,
    astro_score,
    quality_class
FROM meteoblue_hourly
WHERE timestamp > NOW()
  AND zenith_angle > 108
  AND astro_score >= 60
ORDER BY astro_score DESC, timestamp
LIMIT 50;

-- Tägliche Zusammenfassung
CREATE OR REPLACE VIEW v_daily_summary AS
SELECT 
    DATE(timestamp) as date,
    COUNT(*) FILTER (WHERE zenith_angle > 108) as night_hours,
    COUNT(*) FILTER (WHERE zenith_angle > 108 AND astro_score >= 70) as good_hours,
    MAX(astro_score) FILTER (WHERE zenith_angle > 108) as best_score,
    MIN(seeing_arcsec) FILTER (WHERE zenith_angle > 108) as best_seeing,
    AVG(totalcloud) FILTER (WHERE zenith_angle > 108)::INTEGER as avg_clouds
FROM meteoblue_hourly
WHERE timestamp > NOW()
GROUP BY DATE(timestamp)
ORDER BY date;


-- ============================================
-- 8. FUNKTIONEN
-- ============================================

-- Funktion: Berechne Astro-Score
CREATE OR REPLACE FUNCTION calculate_astro_score(
    p_seeing_arcsec DECIMAL,
    p_totalcloud SMALLINT,
    p_jetstream DECIMAL,
    p_moonlight DECIMAL,
    p_zenith_angle DECIMAL
) RETURNS SMALLINT AS $$
DECLARE
    score INTEGER := 100;
BEGIN
    -- Wolken (max -50)
    score := score - (p_totalcloud * 0.5)::INTEGER;
    
    -- Seeing (max -30)
    IF p_seeing_arcsec > 1.0 THEN
        score := score - LEAST(30, ((p_seeing_arcsec - 1.0) * 15)::INTEGER);
    END IF;
    
    -- Jet Stream (max -10)
    IF p_jetstream > 35 THEN
        score := score - LEAST(10, ((p_jetstream - 35) * 0.5)::INTEGER);
    ELSIF p_jetstream < 5 THEN
        score := score - 3;
    END IF;
    
    -- Mondlicht (max -10, nur bei Nacht)
    IF p_zenith_angle > 90 AND p_moonlight > 30 THEN
        score := score - LEAST(10, (p_moonlight * 0.15)::INTEGER);
    END IF;
    
    RETURN GREATEST(0, LEAST(100, score))::SMALLINT;
END;
$$ LANGUAGE plpgsql;


-- ============================================
-- 9. POLICIES (Row Level Security) - Optional
-- ============================================

-- Falls du RLS aktivieren willst:
-- ALTER TABLE meteoblue_hourly ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Public read" ON meteoblue_hourly FOR SELECT USING (true);


-- ============================================
-- INITIALISIERUNG ABGESCHLOSSEN
-- ============================================

COMMENT ON TABLE meteoblue_hourly IS 'Stündliche Vorhersagen von meteoblue inkl. Seeing, Clouds, Moonlight';
COMMENT ON TABLE cloudwatcher_readings IS 'Rohdaten vom CloudWatcher Solo als Ground Truth';
COMMENT ON TABLE training_pairs IS 'Gepaarte Daten für ML-Training: Vorhersage vs. Realität';
COMMENT ON TABLE observation_windows IS 'Erkannte gute Beobachtungsfenster';
