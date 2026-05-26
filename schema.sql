-- AgriQuant AI — PostgreSQL Schema
-- Version 3.2 | Multi-commodity expansion Q1 2026
-- Run: psql -d agriquant -f schema.sql

-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS timescaledb;   -- time-series optimization
CREATE EXTENSION IF NOT EXISTS postgis;        -- geospatial queries
CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- fuzzy text search

-- ============================================================
-- ENUMS
-- ============================================================
CREATE TYPE commodity_code AS ENUM ('OJ','KC','CC','SB','ZC','ZW');
CREATE TYPE signal_direction AS ENUM ('LONG','SHORT','NEUTRAL');
CREATE TYPE risk_level AS ENUM ('low','moderate','high','critical','extreme');
CREATE TYPE enso_phase AS ENUM (
    'strong_el_nino','el_nino','neutral','la_nina','strong_la_nina'
);
CREATE TYPE data_source AS ENUM (
    'NOAA','INMET','GOES16','SENTINEL2','MODIS',
    'LANDSAT8','PLANET_LABS','CME','ICE','USDA_NASS',
    'USDA_WASDE','CONAB','ICCO','ICO','SMAP','GFS','ECMWF'
);

-- ============================================================
-- WEATHER OBSERVATIONS (TimescaleDB hypertable)
-- ============================================================
CREATE TABLE weather_observations (
    id              BIGSERIAL,
    observed_at     TIMESTAMPTZ     NOT NULL,
    commodity       commodity_code  NOT NULL,
    region_name     VARCHAR(100)    NOT NULL,
    country         CHAR(2)         NOT NULL,
    lat             DECIMAL(8,5)    NOT NULL,
    lon             DECIMAL(8,5)    NOT NULL,
    temp_min_c      DECIMAL(5,2),
    temp_max_c      DECIMAL(5,2),
    temp_current_c  DECIMAL(5,2),
    humidity_pct    DECIMAL(5,2),
    rainfall_mm     DECIMAL(8,3),
    wind_speed_ms   DECIMAL(6,2),
    wind_dir_deg    SMALLINT,
    pressure_hpa    DECIMAL(7,2),
    cloud_cover_pct SMALLINT,
    source          data_source     NOT NULL,
    raw_json        JSONB,
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    PRIMARY KEY (id, observed_at)
);

SELECT create_hypertable('weather_observations', 'observed_at',
    chunk_time_interval => INTERVAL '7 days');

CREATE INDEX ON weather_observations (commodity, observed_at DESC);
CREATE INDEX ON weather_observations (region_name, observed_at DESC);
CREATE INDEX ON weather_observations
    USING GIST (ST_MakePoint(lon, lat));  -- geospatial index

-- ============================================================
-- NDVI & SATELLITE OBSERVATIONS
-- ============================================================
CREATE TABLE satellite_observations (
    id              BIGSERIAL PRIMARY KEY,
    observed_at     TIMESTAMPTZ     NOT NULL,
    commodity       commodity_code  NOT NULL,
    region_name     VARCHAR(100)    NOT NULL,
    lat             DECIMAL(8,5)    NOT NULL,
    lon             DECIMAL(8,5)    NOT NULL,
    ndvi_mean       DECIMAL(6,4),
    ndvi_min        DECIMAL(6,4),
    ndvi_max        DECIMAL(6,4),
    ndwi            DECIMAL(6,4),   -- water index
    lst_kelvin      DECIMAL(7,2),   -- land surface temp
    soil_moisture   DECIMAL(6,4),   -- SMAP 0-1 scale
    cloud_cover_pct SMALLINT,
    pixel_count     INTEGER,
    source          data_source     NOT NULL,
    resolution_m    SMALLINT,
    raw_json        JSONB,
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

SELECT create_hypertable('satellite_observations', 'observed_at',
    chunk_time_interval => INTERVAL '30 days');

CREATE INDEX ON satellite_observations (commodity, observed_at DESC);

-- ============================================================
-- AI PREDICTIONS
-- ============================================================
CREATE TABLE ai_predictions (
    id                  BIGSERIAL PRIMARY KEY,
    predicted_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    commodity           commodity_code  NOT NULL,
    region_name         VARCHAR(100),
    event_type          VARCHAR(50)     NOT NULL,
    signal              signal_direction NOT NULL,
    confidence          DECIMAL(4,3)    CHECK (confidence BETWEEN 0 AND 1),
    estimated_move_pct  DECIMAL(6,2),
    time_horizon_hours  SMALLINT,
    primary_driver      VARCHAR(200),
    claude_reasoning    TEXT,
    ml_ensemble_score   DECIMAL(5,4),
    model_version       VARCHAR(20),
    data_sources        data_source[],
    raw_response        JSONB,
    actual_move_pct     DECIMAL(6,2),   -- filled after resolution
    resolved_at         TIMESTAMPTZ,
    correct             BOOLEAN,        -- filled after resolution
    created_at          TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX ON ai_predictions (commodity, predicted_at DESC);
CREATE INDEX ON ai_predictions (signal, commodity);
CREATE INDEX ON ai_predictions (correct) WHERE correct IS NOT NULL;

-- ============================================================
-- TRADES & PERFORMANCE
-- ============================================================
CREATE TABLE trades (
    id                  BIGSERIAL PRIMARY KEY,
    opened_at           TIMESTAMPTZ     NOT NULL,
    closed_at           TIMESTAMPTZ,
    commodity           commodity_code  NOT NULL,
    ticker              VARCHAR(10)     NOT NULL,
    exchange            VARCHAR(10)     NOT NULL,
    direction           signal_direction NOT NULL,
    contracts           SMALLINT        NOT NULL,
    entry_price         DECIMAL(12,4)   NOT NULL,
    exit_price          DECIMAL(12,4),
    stop_loss_price     DECIMAL(12,4),
    target_price        DECIMAL(12,4),
    position_size_usd   DECIMAL(12,2),
    pnl_usd             DECIMAL(12,2),
    pnl_pct             DECIMAL(6,3),
    hold_days           SMALLINT,
    prediction_id       BIGINT          REFERENCES ai_predictions(id),
    exit_reason         VARCHAR(50),    -- stop_loss|target_hit|time_exit|manual
    broker              VARCHAR(50)     DEFAULT 'Interactive Brokers',
    created_at          TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX ON trades (commodity, opened_at DESC);
CREATE INDEX ON trades (pnl_pct);

-- ============================================================
-- SUPPLY REPORTS
-- ============================================================
CREATE TABLE supply_reports (
    id              BIGSERIAL PRIMARY KEY,
    published_at    TIMESTAMPTZ     NOT NULL,
    report_type     VARCHAR(50)     NOT NULL,  -- WASDE, CONAB, ICCO, etc.
    commodity       commodity_code  NOT NULL,
    region          VARCHAR(100),
    metric          VARCHAR(100),              -- production, consumption, stocks_ending
    value           DECIMAL(14,4),
    unit            VARCHAR(30),               -- million_tons, thousand_bags, etc.
    prior_value     DECIMAL(14,4),
    revision_pct    DECIMAL(6,2),
    signal          signal_direction,
    source_url      TEXT,
    raw_json        JSONB,
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX ON supply_reports (commodity, published_at DESC);
CREATE INDEX ON supply_reports (report_type, published_at DESC);

-- ============================================================
-- ENSO / MACRO SIGNALS
-- ============================================================
CREATE TABLE enso_readings (
    id          BIGSERIAL PRIMARY KEY,
    reading_at  TIMESTAMPTZ     NOT NULL,
    oni_value   DECIMAL(4,2)    NOT NULL,
    phase       enso_phase      NOT NULL,
    source      VARCHAR(30)     DEFAULT 'NOAA_CPC',
    created_at  TIMESTAMPTZ     DEFAULT NOW()
);

SELECT create_hypertable('enso_readings', 'reading_at',
    chunk_time_interval => INTERVAL '90 days');

-- ============================================================
-- MARKET PRICES (tick data cache)
-- ============================================================
CREATE TABLE market_prices (
    id          BIGSERIAL,
    price_at    TIMESTAMPTZ     NOT NULL,
    commodity   commodity_code  NOT NULL,
    ticker      VARCHAR(10)     NOT NULL,
    bid         DECIMAL(12,4),
    ask         DECIMAL(12,4),
    last        DECIMAL(12,4),
    volume      INTEGER,
    open_int    INTEGER,
    source      VARCHAR(20)     DEFAULT 'CME',
    PRIMARY KEY (id, price_at)
);

SELECT create_hypertable('market_prices', 'price_at',
    chunk_time_interval => INTERVAL '1 day');

CREATE INDEX ON market_prices (commodity, price_at DESC);
CREATE INDEX ON market_prices (ticker, price_at DESC);

-- ============================================================
-- VIEWS
-- ============================================================

-- Recent prediction accuracy by commodity
CREATE VIEW prediction_accuracy AS
SELECT
    commodity,
    COUNT(*) FILTER (WHERE correct IS NOT NULL) AS resolved_count,
    ROUND(AVG(CASE WHEN correct THEN 1.0 ELSE 0.0 END) * 100, 1) AS win_rate_pct,
    ROUND(AVG(pnl_pct) FILTER (WHERE pnl_pct > 0), 2) AS avg_winner_pct,
    ROUND(AVG(pnl_pct) FILTER (WHERE pnl_pct < 0), 2) AS avg_loser_pct,
    ROUND(
        ABS(AVG(pnl_pct) FILTER (WHERE pnl_pct > 0)) /
        NULLIF(ABS(AVG(pnl_pct) FILTER (WHERE pnl_pct < 0)), 0),
        2
    ) AS win_loss_ratio
FROM ai_predictions p
LEFT JOIN trades t ON t.prediction_id = p.id
GROUP BY commodity;

-- Active signals
CREATE VIEW active_signals AS
SELECT
    p.commodity,
    p.signal,
    p.confidence,
    p.estimated_move_pct,
    p.primary_driver,
    p.predicted_at,
    p.time_horizon_hours,
    NOW() - p.predicted_at AS age
FROM ai_predictions p
WHERE p.resolved_at IS NULL
  AND p.predicted_at > NOW() - INTERVAL '72 hours'
ORDER BY p.confidence DESC;

-- Rolling 30-day performance
CREATE VIEW rolling_performance AS
SELECT
    DATE_TRUNC('day', opened_at) AS trade_date,
    commodity,
    COUNT(*) AS trades,
    ROUND(SUM(pnl_usd), 2) AS daily_pnl_usd,
    ROUND(AVG(pnl_pct), 3) AS avg_pnl_pct,
    ROUND(SUM(SUM(pnl_usd)) OVER (
        ORDER BY DATE_TRUNC('day', opened_at)
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 2) AS cumulative_pnl_usd
FROM trades
WHERE opened_at > NOW() - INTERVAL '30 days'
GROUP BY 1, 2
ORDER BY 1 DESC, 2;
