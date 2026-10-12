"""
Urban Mobility Explorer — Database Builder
==========================================

One-shot pipeline:
    1. Load yellow taxi trips (CSV or Parquet, auto-detected)
    2. Load taxi zone lookup
    3. Clean the data (duplicates, nulls, outliers, temporal anomalies)
    4. Engineer features (speed, tip%, fare/mile, airport flag, etc.)
    5. Populate the normalized SQLite database

Usage:
    python backend/db/build_database.py

Output:
    database/urban_mobility.db    (SQLite, ready to query)
"""
# ETL pipeline - load - clean - features- store

import os
import sys
import sqlite3
import time
from pathlib import Path
from datetime import datetime

import pandas as pd

# ============================================================================
# PATHS
# ============================================================================
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DB_DIR = ROOT / "database"
DB_PATH = DB_DIR / "urban_mobility.db"
SCHEMA_PATH = ROOT / "backend" / "db" / "schema.sql"

# ============================================================================
# CONSTANTS
# ============================================================================
AIRPORT_ZONES = {132, 138}          # JFK, LaGuardia
MAX_TRIP_DISTANCE_MILES = 100
MAX_TRIP_DURATION_MINUTES = 24 * 60
MAX_FARE = 500.00
MIN_FARE = 0.00
MAX_PASSENGERS = 8
BATCH_SIZE = 100_000

PAYMENT_MAP = {
    1: "Credit card",
    2: "Cash",
    3: "No charge",
    4: "Dispute",
    5: "Unknown",
    6: "Voided trip",
}

RATE_CODE_MAP = {
    1: "Standard rate",
    2: "JFK",
    3: "Newark",
    4: "Nassau or Westchester",
    5: "Negotiated fare",
    6: "Group ride",
    99: "Unknown",
}


# ============================================================================
# HELPERS
# ============================================================================
def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def find_trip_file() -> Path:
    """Auto-detect the trip data file (parquet preferred, else CSV)."""
    parquets = sorted(DATA_DIR.glob("yellow_tripdata_*.parquet"))
    if parquets:
        return parquets[-1]
    csvs = sorted(DATA_DIR.glob("yellow_tripdata_*.csv"))
    if csvs:
        return csvs[-1]
    raise FileNotFoundError(
        f"No yellow_tripdata_*.parquet or .csv found in {DATA_DIR}"
    )


def load_trips(path: Path) -> pd.DataFrame:
    """Load trip data (parquet or CSV). CSV loaded as strings then coerced."""
    log(f"Loading trips from {path.name} ...")
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(
            path,
            low_memory=False,
            dtype=str,
            keep_default_na=False,
            na_values=[""],
        )
        log(f"  CSV parsed: {len(df):,} rows")

        numeric_cols = [
            "VendorID", "passenger_count", "trip_distance", "RatecodeID",
            "PULocationID", "DOLocationID", "payment_type",
            "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
            "improvement_surcharge", "total_amount", "congestion_surcharge",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        for col in ["tpep_pickup_datetime", "tpep_dropoff_datetime"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        log(f"  Coerced dtypes")

    log(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")
    return df


# ============================================================================
# CLEANING
# ============================================================================
class Cleaner:
    def __init__(self):
        self.log = {
            "raw": 0,
            "duplicates": 0,
            "missing_critical": 0,
            "temporal": 0,
            "distance": 0,
            "fare": 0,
            "passenger": 0,
            "final": 0,
        }

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        self.log["raw"] = len(df)

        # --- 1. Duplicates ---
        before = len(df)
        df = df.drop_duplicates()
        self.log["duplicates"] = before - len(df)
        log(f"  Removed duplicates: {self.log['duplicates']:,}")

        # --- 2. Missing critical fields ---
        critical = [
            "tpep_pickup_datetime", "tpep_dropoff_datetime",
            "PULocationID", "DOLocationID", "trip_distance",
            "fare_amount", "total_amount",
        ]
        before = len(df)
        df = df.dropna(subset=critical)
        self.log["missing_critical"] = before - len(df)
        log(f"  Removed missing-critical: {self.log['missing_critical']:,}")

        # --- 3. Timestamps + duration ---
        df["tpep_pickup_datetime"] = pd.to_datetime(
            df["tpep_pickup_datetime"], errors="coerce"
        )
        df["tpep_dropoff_datetime"] = pd.to_datetime(
            df["tpep_dropoff_datetime"], errors="coerce"
        )

        df["trip_duration_minutes"] = (
            df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]
        ).dt.total_seconds() / 60.0

        before = len(df)
        df = df[
            (df["trip_duration_minutes"] > 0) &
            (df["trip_duration_minutes"] <= MAX_TRIP_DURATION_MINUTES) &
            (df["tpep_pickup_datetime"].notna()) &
            (df["tpep_dropoff_datetime"].notna())
        ]
        self.log["temporal"] = before - len(df)
        log(f"  Removed temporal anomalies: {self.log['temporal']:,}")

        # --- 4. Distance ---
        before = len(df)
        df = df[
            (df["trip_distance"] > 0) &
            (df["trip_distance"] <= MAX_TRIP_DISTANCE_MILES)
        ]
        self.log["distance"] = before - len(df)
        log(f"  Removed distance anomalies: {self.log['distance']:,}")

        # --- 5. Fare ---
        before = len(df)
        df = df[
            (df["fare_amount"] >= MIN_FARE) &
            (df["fare_amount"] <= MAX_FARE) &
            (df["total_amount"] >= df["fare_amount"])
        ]
        self.log["fare"] = before - len(df)
        log(f"  Removed fare anomalies: {self.log['fare']:,}")

        # --- 6. Passenger count ---
        if "passenger_count" in df.columns:
            median_pax = df["passenger_count"].median()
            df["passenger_count"] = (
                df["passenger_count"].fillna(median_pax).astype(int)
            )
            before = len(df)
            df = df[
                (df["passenger_count"] >= 0) &
                (df["passenger_count"] <= MAX_PASSENGERS)
            ]
            self.log["passenger"] = before - len(df)
            log(f"  Removed passenger anomalies: {self.log['passenger']:,}")

        df = df.reset_index(drop=True)
        self.log["final"] = len(df)
        return df


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================
def engineer_features(df: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    log("Engineering features ...")

    # speed_mph
    df["speed_mph"] = (df["trip_distance"] / df["trip_duration_minutes"]) * 60.0
    df["speed_mph"] = df["speed_mph"].clip(upper=80)

    # tip_percentage
    df["tip_percentage"] = (df["tip_amount"] / df["fare_amount"]) * 100.0
    df.loc[df["fare_amount"] <= 0, "tip_percentage"] = 0

    # fare_per_mile
    df["fare_per_mile"] = df["fare_amount"] / df["trip_distance"]

    # revenue_per_minute
    df["revenue_per_minute"] = df["total_amount"] / df["trip_duration_minutes"]

    # is_airport_trip
    df["is_airport_trip"] = (
        df["PULocationID"].isin(AIRPORT_ZONES) |
        df["DOLocationID"].isin(AIRPORT_ZONES)
    ).astype(int)

    # Hour / is_weekend
    df["hour"] = df["tpep_pickup_datetime"].dt.hour
    df["is_weekend"] = (df["tpep_pickup_datetime"].dt.dayofweek >= 5).astype(int)

    # is_cross_borough (needs borough mapping)
    zone_map = zones.set_index("LocationID")["Borough"].to_dict()
    df["pickup_borough"] = df["PULocationID"].map(zone_map)
    df["dropoff_borough"] = df["DOLocationID"].map(zone_map)
    df["is_cross_borough"] = (
        (df["pickup_borough"].notna()) &
        (df["dropoff_borough"].notna()) &
        (df["pickup_borough"] != df["dropoff_borough"])
    ).astype(int)

    return df


# ============================================================================
# DATABASE HELPERS
# ============================================================================
def open_db() -> sqlite3.Connection:
    """Create the DB (drop if exists) and apply schema."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        log(f"Removing existing DB: {DB_PATH.name}")
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    log(f"Applied schema from {SCHEMA_PATH.name}")
    return conn


def seed_boroughs(conn, zones: pd.DataFrame) -> None:
    rows = [(b,) for b in sorted(zones["Borough"].dropna().unique())]
    conn.executemany(
        "INSERT OR IGNORE INTO boroughs(borough_name) VALUES (?)", rows
    )
    conn.commit()


def seed_service_zones(conn, zones: pd.DataFrame) -> None:
    rows = [(s,) for s in sorted(zones["service_zone"].dropna().unique())]
    conn.executemany(
        "INSERT OR IGNORE INTO service_zones(zone_name) VALUES (?)", rows
    )
    conn.commit()


def seed_taxi_zones(conn, zones: pd.DataFrame) -> None:
    bmap = dict(conn.execute(
        "SELECT borough_name, borough_id FROM boroughs"
    ).fetchall())
    smap = dict(conn.execute(
        "SELECT zone_name, service_zone_id FROM service_zones"
    ).fetchall())

    rows = []
    for _, r in zones.iterrows():
        rows.append((
            int(r["LocationID"]),
            r["Zone"],
            bmap.get(r["Borough"]),
            smap.get(r["service_zone"]),
        ))
    conn.executemany(
        "INSERT OR IGNORE INTO taxi_zones"
        "(location_id, zone_name, borough_id, service_zone_id) "
        "VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    log(f"  Seeded {len(rows)} taxi zones")


def seed_payment_types(conn) -> None:
    rows = list(PAYMENT_MAP.items())
    conn.executemany(
        "INSERT OR IGNORE INTO payment_types"
        "(payment_type_id, payment_description) VALUES (?, ?)",
        rows,
    )
    conn.commit()


def seed_rate_codes(conn) -> None:
    rows = list(RATE_CODE_MAP.items())
    conn.executemany(
        "INSERT OR IGNORE INTO rate_codes"
        "(rate_code_id, rate_description) VALUES (?, ?)",
        rows,
    )
    conn.commit()


def seed_dim_time(conn, df: pd.DataFrame) -> None:
    log("  Building dim_time ...")
    times = pd.concat([
        df["tpep_pickup_datetime"],
        df["tpep_dropoff_datetime"],
    ]).dropna().unique()

    rows = []
    for ts in pd.to_datetime(times):
        hour = ts.hour
        dow = ts.dayofweek
        if hour < 6:
            tod = "Night"
        elif hour < 12:
            tod = "Morning"
        elif hour < 18:
            tod = "Afternoon"
        else:
            tod = "Evening"

        rows.append((
            ts.strftime("%Y-%m-%d %H:%M:%S"),
            ts.strftime("%Y-%m-%d"),
            hour,
            dow,
            ts.strftime("%A"),
            ts.month,
            ts.year,
            1 if dow >= 5 else 0,
            tod,
        ))

    conn.executemany(
        "INSERT OR IGNORE INTO dim_time("
        "full_datetime, date, hour, day_of_week, day_name, "
        "month, year, is_weekend, time_of_day) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    log(f"  dim_time has {len(rows):,} unique timestamps")


def insert_trips(conn, df: pd.DataFrame) -> None:
    """Insert trips in batches, resolving FK IDs on the fly."""
    log("  Building lookup maps ...")
    tmap = dict(conn.execute(
        "SELECT full_datetime, time_id FROM dim_time"
    ).fetchall())

    valid_zones = set(
        r[0] for r in conn.execute("SELECT location_id FROM taxi_zones").fetchall()
    )
    valid_payments = set(
        r[0] for r in conn.execute(
            "SELECT payment_type_id FROM payment_types"
        ).fetchall()
    )
    valid_rates = set(
        r[0] for r in conn.execute("SELECT rate_code_id FROM rate_codes").fetchall()
    )

    def dt_to_key(ts) -> str:
        return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    total = len(df)
    inserted = 0
    skipped = 0
    log(f"  Inserting {total:,} trips in batches of {BATCH_SIZE:,} ...")

    sql = """
    INSERT INTO trips (
        pickup_time_id, dropoff_time_id,
        pickup_location_id, dropoff_location_id,
        payment_type_id, rate_code_id,
        vendor_id, passenger_count,
        trip_distance, trip_duration_minutes,
        fare_amount, extra, mta_tax, tip_amount, tolls_amount,
        improvement_surcharge, congestion_surcharge, total_amount,
        speed_mph, tip_percentage, fare_per_mile, revenue_per_minute,
        is_airport_trip, is_cross_borough
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    def clean_float(v):
        if v is None or pd.isna(v):
            return 0.0
        return float(v)

    def clean_int(v):
        if v is None or pd.isna(v):
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    def valid_int(v, allowed):
        iv = clean_int(v)
        if iv is None:
            return None
        return iv if iv in allowed else None

    for start in range(0, total, BATCH_SIZE):
        batch = df.iloc[start:start + BATCH_SIZE]
        rows = []
        for _, r in batch.iterrows():
            pu_time = tmap.get(dt_to_key(r["tpep_pickup_datetime"]))
            do_time = tmap.get(dt_to_key(r["tpep_dropoff_datetime"]))
            if pu_time is None or do_time is None:
                skipped += 1
                continue

            pu_loc = clean_int(r["PULocationID"])
            do_loc = clean_int(r["DOLocationID"])

            # Skip trips referencing unknown zones (must satisfy FK)
            if pu_loc not in valid_zones or do_loc not in valid_zones:
                skipped += 1
                continue

            rows.append((
                pu_time, do_time,
                pu_loc, do_loc,
                valid_int(r.get("payment_type"), valid_payments),
                valid_int(r.get("RatecodeID"), valid_rates),
                clean_int(r.get("VendorID")),
                clean_int(r.get("passenger_count", 1)) or 1,
                clean_float(r["trip_distance"]),
                clean_float(r["trip_duration_minutes"]),
                clean_float(r["fare_amount"]),
                clean_float(r.get("extra", 0)),
                clean_float(r.get("mta_tax", 0)),
                clean_float(r.get("tip_amount", 0)),
                clean_float(r.get("tolls_amount", 0)),
                clean_float(r.get("improvement_surcharge", 0)),
                clean_float(r.get("congestion_surcharge", 0)),
                clean_float(r["total_amount"]),
                clean_float(r.get("speed_mph")),
                clean_float(r.get("tip_percentage")),
                clean_float(r.get("fare_per_mile")),
                clean_float(r.get("revenue_per_minute")),
                int(r.get("is_airport_trip", 0)),
                int(r.get("is_cross_borough", 0)),
            ))

        try:
            conn.executemany(sql, rows)
            conn.commit()
        except sqlite3.IntegrityError as e:
            log(f"    ⚠ Batch insert warning: {e}")
            conn.rollback()
            for row in rows:
                try:
                    conn.execute(sql, row)
                except sqlite3.IntegrityError:
                    skipped += 1
            conn.commit()

        inserted += len(rows)
        if (start // BATCH_SIZE) % 10 == 0:
            log(
                f"    ✓ {min(start + BATCH_SIZE, total):,} / {total:,}  "
                f"(skipped {skipped:,})"
            )

    log(f"  Total inserted: {inserted:,}, skipped: {skipped:,}")


# ============================================================================
# MAIN
# ============================================================================
# ----------------------------------------------------------------------------
# Main entry point for the ETL pipeline.
#
# Stages:
#   1. Locate the parquet or CSV trip files.
#   2. Load the taxi_zone_lookup.csv dimension.
#   3. Read trips (100k-row chunks handled by pandas).
#   4. Clean: duplicated, nulls, temporarl, distance, fare, pax.
#   5. Engineer: speed, tip %, fare per mile. airport/cross-borough.
#   6. Create schema, seed dimensions, build dim_time.
#   7. Insert trips in 100k batcheds with FK validation.
#   8. print cleaning report for the technical documentation.
# ----------------------------------------------------------------------------

def log_pipeline_version():
    """
    prints the pipeline version at startup.
    Helps track which run produced which database snapshot.
    """
    print("=" * 60)
    print("Urban Mobility Explore  - ETL pipeline v1.0")
    print("python 3.12 | pandas| pyarrow | SQlite")
    print("=" * 60)


def main() -> int:
    t0 = time.time()

    log("=== Urban Mobility Explorer — Database Builder ===")
    trip_path = find_trip_file()
    zone_path = DATA_DIR / "taxi_zone_lookup.csv"
    if not zone_path.exists():
        log(f"ERROR: {zone_path} not found")
        return 1

    zones = pd.read_csv(zone_path)

    df = load_trips(trip_path)

    log("Cleaning ...")
    cleaner = Cleaner()
    df = cleaner.clean(df)

    df = engineer_features(df, zones)

    log("Building database ...")
    conn = open_db()

    log("Seeding dimensions ...")
    seed_boroughs(conn, zones)
    seed_service_zones(conn, zones)
    seed_taxi_zones(conn, zones)
    seed_payment_types(conn)
    seed_rate_codes(conn)
    seed_dim_time(conn, df)

    log("Inserting trips ...")
    insert_trips(conn, df)

    c = cleaner.log
    elapsed = time.time() - t0
    print()
    print("=" * 60)
    print(" CLEANING REPORT")
    print("=" * 60)
    print(f" Raw rows:              {c['raw']:>12,}")
    print(f" Duplicates:           -{c['duplicates']:>12,}")
    print(f" Missing critical:     -{c['missing_critical']:>12,}")
    print(f" Temporal anomalies:   -{c['temporal']:>12,}")
    print(f" Distance anomalies:   -{c['distance']:>12,}")
    print(f" Fare anomalies:       -{c['fare']:>12,}")
    print(f" Passenger anomalies:  -{c['passenger']:>12,}")
    print("-" * 60)
    print(f" Kept:                  {c['final']:>12,}  "
          f"({c['final']/c['raw']*100:.1f}%)")
    print("=" * 60)
    print(f" Time elapsed: {elapsed:.1f}s")
    print(f" DB location:  {DB_PATH}")
    print("=" * 60)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())