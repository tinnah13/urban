-- ==============================================================================
-- NYC Yellow taxi 
-- ------------------------------------------------------------------------------
-- Design rationale:
--   * 5 dimensions isolate low-cardinality reference data.
--   * dim_time is a standard star-schema pattern that lets us precompute
--     hour-of-day, day-of-week, weekend flags once instead of at query time.
--   * trps is the fact table and stores engineeres columns as materialised
--     attributes to avoid recomputation on every read.
--   * Foreign keys enforce referential integrity. The ETL pipeline
--     pre-filters records that would violated that violate them.
-- ==============================================================================


-- Schema
-- ============================================================================
-- Urban Mobility Explorer — NYC Yellow Taxi Database Schema
-- ============================================================================
-- Normalized star schema: 7 tables (5 dimensions + 1 time dim + 1 fact)
-- Adapted for 2019 TLC data (no airport_fee, no cbd_congestion_fee)
-- Compatible with SQLite (dev) and PostgreSQL (prod)
-- ============================================================================

-- ---------------------------------------------------------------------------
-- DIMENSION: Boroughs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS boroughs (
    borough_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    borough_name    TEXT    NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- DIMENSION: Service Zones (EWR, Boro Zone, Yellow Zone, Airports, N/A)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS service_zones (
    service_zone_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_name       TEXT    NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- DIMENSION: Taxi Zones (265 zones + Unknown + Outside NYC)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taxi_zones (
    location_id     INTEGER PRIMARY KEY,
    zone_name       TEXT    NOT NULL,
    borough_id      INTEGER NOT NULL REFERENCES boroughs(borough_id),
    service_zone_id INTEGER          REFERENCES service_zones(service_zone_id)
);

-- ---------------------------------------------------------------------------
-- DIMENSION: Payment Types
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payment_types (
    payment_type_id     INTEGER PRIMARY KEY,
    payment_description TEXT    NOT NULL
);

-- ---------------------------------------------------------------------------
-- DIMENSION: Rate Codes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rate_codes (
    rate_code_id     INTEGER PRIMARY KEY,
    rate_description TEXT    NOT NULL
);

-- ---------------------------------------------------------------------------
-- DIMENSION: Time (star-schema date/time dimension)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_time (
    time_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    full_datetime TEXT    NOT NULL UNIQUE,   -- ISO8601 string
    date          TEXT    NOT NULL,          -- YYYY-MM-DD
    hour          INTEGER NOT NULL CHECK (hour >= 0 AND hour <= 23),
    day_of_week   INTEGER NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6),
    day_name      TEXT    NOT NULL,
    month         INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    year          INTEGER NOT NULL,
    is_weekend    INTEGER NOT NULL CHECK (is_weekend IN (0, 1)),
    time_of_day   TEXT    NOT NULL           -- Night / Morning / Afternoon / Evening
);

-- ---------------------------------------------------------------------------
-- FACT: Trips
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trips (
    trip_id                 INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Foreign keys to dimensions
    pickup_time_id          INTEGER NOT NULL REFERENCES dim_time(time_id),
    dropoff_time_id         INTEGER NOT NULL REFERENCES dim_time(time_id),
    pickup_location_id      INTEGER NOT NULL REFERENCES taxi_zones(location_id),
    dropoff_location_id     INTEGER NOT NULL REFERENCES taxi_zones(location_id),
    payment_type_id         INTEGER          REFERENCES payment_types(payment_type_id),
    rate_code_id            INTEGER          REFERENCES rate_codes(rate_code_id),

    -- Raw measures
    vendor_id               INTEGER,
    passenger_count         INTEGER NOT NULL DEFAULT 1,
    trip_distance           REAL    NOT NULL,
    trip_duration_minutes   REAL    NOT NULL,

    -- Fare breakdown
    fare_amount             REAL    NOT NULL,
    extra                   REAL    DEFAULT 0,
    mta_tax                 REAL    DEFAULT 0,
    tip_amount              REAL    DEFAULT 0,
    tolls_amount            REAL    DEFAULT 0,
    improvement_surcharge   REAL    DEFAULT 0,
    congestion_surcharge    REAL    DEFAULT 0,
    total_amount            REAL    NOT NULL,

    -- Engineered features
    speed_mph               REAL,
    tip_percentage          REAL,
    fare_per_mile           REAL,
    revenue_per_minute      REAL,
    is_airport_trip         INTEGER DEFAULT 0 CHECK (is_airport_trip IN (0, 1)),
    is_cross_borough        INTEGER DEFAULT 0 CHECK (is_cross_borough IN (0, 1)),

    -- Metadata
    created_at              TEXT    DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES for query optimization
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_trips_pickup_time       ON trips(pickup_time_id);
CREATE INDEX IF NOT EXISTS idx_trips_dropoff_time      ON trips(dropoff_time_id);
CREATE INDEX IF NOT EXISTS idx_trips_pickup_location   ON trips(pickup_location_id);
CREATE INDEX IF NOT EXISTS idx_trips_dropoff_location  ON trips(dropoff_location_id);
CREATE INDEX IF NOT EXISTS idx_trips_payment_type      ON trips(payment_type_id);
CREATE INDEX IF NOT EXISTS idx_trips_rate_code         ON trips(rate_code_id);
CREATE INDEX IF NOT EXISTS idx_trips_distance          ON trips(trip_distance);
CREATE INDEX IF NOT EXISTS idx_trips_fare              ON trips(fare_amount);
CREATE INDEX IF NOT EXISTS idx_trips_duration          ON trips(trip_duration_minutes);
CREATE INDEX IF NOT EXISTS idx_trips_airport           ON trips(is_airport_trip);
CREATE INDEX IF NOT EXISTS idx_trips_cross_borough     ON trips(is_cross_borough);

-- Composite indexes for common joins
CREATE INDEX IF NOT EXISTS idx_trips_pickup_zone_time
    ON trips(pickup_time_id, pickup_location_id);
CREATE INDEX IF NOT EXISTS idx_trips_route
    ON trips(pickup_location_id, dropoff_location_id);

-- Time dimension indexes
CREATE INDEX IF NOT EXISTS idx_dim_time_date     ON dim_time(date);
CREATE INDEX IF NOT EXISTS idx_dim_time_hour     ON dim_time(hour);
CREATE INDEX IF NOT EXISTS idx_dim_time_year_mo  ON dim_time(year, month);

-- ============================================================================
-- VIEWS for analytics
-- ============================================================================

-- Hourly demand summary
DROP VIEW IF EXISTS v_hourly_demand;
CREATE VIEW v_hourly_demand AS
SELECT
    dt.hour,
    dt.day_of_week,
    dt.is_weekend,
    COUNT(*)                     AS trip_count,
    ROUND(AVG(t.trip_distance), 2)          AS avg_distance,
    ROUND(AVG(t.total_amount), 2)           AS avg_fare,
    ROUND(AVG(t.trip_duration_minutes), 2)  AS avg_duration,
    ROUND(AVG(t.speed_mph), 2)              AS avg_speed
FROM trips t
JOIN dim_time dt ON t.pickup_time_id = dt.time_id
GROUP BY dt.hour, dt.day_of_week, dt.is_weekend;

-- Zone performance summary
DROP VIEW IF EXISTS v_zone_performance;
CREATE VIEW v_zone_performance AS
SELECT
    tz.location_id,
    tz.zone_name,
    b.borough_name,
    COUNT(*)                    AS total_trips,
    ROUND(AVG(t.total_amount), 2)        AS avg_fare,
    ROUND(AVG(t.tip_percentage), 2)      AS avg_tip_pct,
    ROUND(AVG(t.trip_distance), 2)       AS avg_distance,
    ROUND(SUM(t.total_amount), 2)        AS total_revenue
FROM trips t
JOIN taxi_zones tz ON t.pickup_location_id = tz.location_id
JOIN boroughs b    ON tz.borough_id = b.borough_id
GROUP BY tz.location_id, tz.zone_name, b.borough_name;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================