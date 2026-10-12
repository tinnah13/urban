# Urban Mobility Explorer - Flask Api
# This module exposes 9 Rest endpoints that serve
# aggregated NYC yello-taxi data from a SQlite database.
# All queries go through SQAlchemy Core with parameterized 
#statements to prevent SQL injection.
# Flask API - exposes /api/* endpoints

import os
import sys
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine, text

# Make custom algorithms importable
sys.path.insert(0, str(Path(__file__).parent))
from algorithms.custom_sort import get_top_k_trips
from algorithms.anomaly_detector import detect_anomalies_iqr

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
DB_PATH = ROOT / "database" / "urban_mobility.db"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)

engine = create_engine(f"sqlite:///{DB_PATH}", future=True)


# ============================================================================
# Static frontend
# ============================================================================
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ============================================================================
# Health
# ============================================================================
@app.route("/api/health")
def health():
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM trips")).scalar()
    return jsonify({"status": "ok", "trips": n})


# ============================================================================
# Summary KPIs
# ============================================================================
@app.route("/api/summary")
def summary():
    q = text("""
        SELECT
            COUNT(*)                          AS total_trips,
            ROUND(AVG(trip_distance), 2)      AS avg_distance,
            ROUND(AVG(trip_duration_minutes),2) AS avg_duration,
            ROUND(AVG(total_amount), 2)       AS avg_fare,
            ROUND(AVG(speed_mph), 2)          AS avg_speed,
            ROUND(AVG(tip_percentage), 2)     AS avg_tip_pct,
            ROUND(SUM(total_amount), 2)       AS total_revenue
        FROM trips
    """)
    with engine.connect() as conn:
        row = conn.execute(q).fetchone()
    return jsonify(dict(row._mapping))


# ============================================================================
# Hourly demand
# ============================================================================
@app.route("/api/hourly")
def hourly():
    q = text("""
        SELECT
            dt.hour,
            COUNT(*)                       AS trips,
            ROUND(AVG(t.total_amount), 2)  AS avg_fare,
            ROUND(AVG(t.speed_mph), 2)     AS avg_speed
        FROM trips t
        JOIN dim_time dt ON t.pickup_time_id = dt.time_id
        GROUP BY dt.hour
        ORDER BY dt.hour
    """)
    with engine.connect() as conn:
        return jsonify([dict(r._mapping) for r in conn.execute(q)])


# ============================================================================
# Boroughs
# ============================================================================
@app.route("/api/boroughs")
def boroughs():
    q = text("""
        SELECT
            b.borough_name                    AS borough,
            COUNT(*)                          AS trips,
            ROUND(AVG(t.total_amount), 2)     AS avg_fare,
            ROUND(AVG(t.trip_distance), 2)    AS avg_distance
        FROM trips t
        JOIN taxi_zones tz ON t.pickup_location_id = tz.location_id
        JOIN boroughs b    ON tz.borough_id = b.borough_id
        GROUP BY b.borough_name
        ORDER BY trips DESC
    """)
    with engine.connect() as conn:
        return jsonify([dict(r._mapping) for r in conn.execute(q)])


# ============================================================================
# Top zones — uses CUSTOM top-K algorithm
# ============================================================================
@app.route("/api/top-zones")
def top_zones():
    k = int(request.args.get("k", 10))
    q = text("""
        SELECT
            tz.zone_name                   AS zone,
            b.borough_name                 AS borough,
            COUNT(*)                       AS trips,
            ROUND(AVG(t.total_amount), 2)  AS avg_fare
        FROM trips t
        JOIN taxi_zones tz ON t.pickup_location_id = tz.location_id
        JOIN boroughs b    ON tz.borough_id = b.borough_id
        GROUP BY tz.zone_name, b.borough_name
    """)
    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(q)]

    # >>> CUSTOM ALGORITHM — no sorted()/heapq/pandas <<<
    return jsonify(get_top_k_trips(rows, key="trips", k=k, reverse=True))


# ============================================================================
# Trips with filters
# ============================================================================
@app.route("/api/trips")
def trips():
    limit    = min(int(request.args.get("limit", 200)), 1000)
    borough  = request.args.get("borough")
    payment  = request.args.get("payment", type=int)
    min_fare = request.args.get("min_fare", type=float)
    max_fare = request.args.get("max_fare", type=float)
    airport  = request.args.get("airport", type=int)

    where, params = [], {}
    if borough:
        where.append("b.borough_name = :borough"); params["borough"] = borough
    if payment is not None:
        where.append("t.payment_type_id = :payment"); params["payment"] = payment
    if min_fare is not None:
        where.append("t.total_amount >= :min_fare"); params["min_fare"] = min_fare
    if max_fare is not None:
        where.append("t.total_amount <= :max_fare"); params["max_fare"] = max_fare
    if airport is not None:
        where.append("t.is_airport_trip = :airport"); params["airport"] = airport

    clause = ("WHERE " + " AND ".join(where)) if where else ""
    q = text(f"""
        SELECT
            t.trip_id,
            dt.full_datetime               AS pickup_time,
            tz.zone_name                   AS pickup_zone,
            b.borough_name                 AS pickup_borough,
            t.trip_distance,
            t.trip_duration_minutes,
            t.total_amount,
            t.tip_percentage,
            t.speed_mph,
            t.is_airport_trip
        FROM trips t
        JOIN dim_time dt   ON t.pickup_time_id = dt.time_id
        JOIN taxi_zones tz ON t.pickup_location_id = tz.location_id
        JOIN boroughs b    ON tz.borough_id = b.borough_id
        {clause}
        ORDER BY t.trip_id
        LIMIT :limit
    """)
    params["limit"] = limit
    with engine.connect() as conn:
        return jsonify([dict(r._mapping) for r in conn.execute(q, params)])


# ============================================================================
# Anomalies — uses CUSTOM IQR detector
# ============================================================================
@app.route("/api/anomalies")
def anomalies():
    limit = min(int(request.args.get("limit", 5000)), 20000)
    q = text(f"""
        SELECT trip_id, trip_distance, total_amount,
               trip_duration_minutes, speed_mph, tip_percentage
        FROM trips
        LIMIT {limit}
    """)
    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(q)]

    # >>> CUSTOM ALGORITHM <<<
    normal, bad = detect_anomalies_iqr(rows, field="total_amount", multiplier=1.5)
    return jsonify({
        "scanned": len(rows),
        "normal_count": len(normal),
        "anomaly_count": len(bad),
        "anomalies": bad[:100],
    })


# ============================================================================
# Filters metadata (for dropdowns)
# ============================================================================
@app.route("/api/filters")
def filters():
    with engine.connect() as conn:
        boroughs = [r[0] for r in conn.execute(text(
            "SELECT borough_name FROM boroughs ORDER BY borough_name"
        ))]
        payments = [dict(r._mapping) for r in conn.execute(text(
            "SELECT payment_type_id, payment_description FROM payment_types ORDER BY payment_type_id"
        ))]
    return jsonify({"boroughs": boroughs, "payments": payments})


# ============================================================================
# Insights
# ============================================================================
@app.route("/api/insights")
def insights():
    with engine.connect() as conn:
        peak = conn.execute(text("""
            SELECT dt.hour, COUNT(*) AS c
            FROM trips t JOIN dim_time dt ON t.pickup_time_id = dt.time_id
            GROUP BY dt.hour ORDER BY c DESC LIMIT 1
        """)).fetchone()

        airport = conn.execute(text("""
            SELECT is_airport_trip,
                   ROUND(AVG(total_amount), 2) AS avg_fare,
                   COUNT(*) AS trips
            FROM trips GROUP BY is_airport_trip
        """)).fetchall()

        cb = conn.execute(text("""
            SELECT is_cross_borough,
                   ROUND(AVG(tip_percentage), 2) AS avg_tip
            FROM trips GROUP BY is_cross_borough
        """)).fetchall()

    return jsonify({
        "peak_hour": dict(peak._mapping) if peak else None,
        "airport": [dict(r._mapping) for r in airport],
        "cross_borough": [dict(r._mapping) for r in cb],
    })

@app.route("/api/ping")
def ping():
    """
    lightweight liveness endpoint.
    used by load balancers and uptime monitors.
    returns 200 with pong payload when the service is up.
    """
    from datetime import datetime
    return jsonify({
        "pong": True,
        "service": "urban-mobility-explorer",
        "ts": datetime.utcnow().isoformat(),
    })

@app.route("/api/version")
def version():
    """
    Returns the current API version.
    Useful for clients to detect breaking changes.
    """
    return jsonify({
        "version": "1.0.0",
        "dataset": "NYC yellow taxi 2019-01",
        "records": 7434709,
    })


# ============================================================================
if __name__ == "__main__":
    print(f"Database: {DB_PATH}")
    print(f"Frontend: {FRONTEND_DIR}")
    print("Starting Flask on http://localhost:5000 ...")
    app.run(host="0.0.0.0", port=5000, debug=True)
