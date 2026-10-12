"""
Dump the SQLite database to database/dump.sql using chunked streaming.
This avoids the memory spike from sqlite3.iterdump() on a 7.4M-row DB.
"""
import sqlite3
from pathlib import Path
import time

DB = Path("database/urban_mobility.db")
OUT = Path("database/dump.sql")

print(f"Opening {DB} ...")
conn = sqlite3.connect(str(DB))
conn.text_factory = str

print("Writing dump ...")
t0 = time.time()

with open(OUT, "w", encoding="utf-8", buffering=1_000_000) as f:
    # 1. Schema for all tables
    f.write("BEGIN TRANSACTION;\n")
    for (sql,) in conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND type IN ('table','index','view')"
    ):
        f.write(sql + ";\n")
    f.write("COMMIT;\n\n")

    # 2. Rows for the small dimension tables
    for table in ["boroughs", "service_zones", "taxi_zones",
                  "payment_types", "rate_codes"]:
        print(f"  Dumping {table} ...")
        cur = conn.execute(f"SELECT * FROM {table}")
        cols = [d[0] for d in cur.description]
        for row in cur:
            values = []
            for v in row:
                if v is None:
                    values.append("NULL")
                elif isinstance(v, (int, float)):
                    values.append(str(v))
                else:
                    s = str(v).replace("'", "''")
                    values.append(f"'{s}'")
            f.write(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(values)});\n")

    # 3. Skip dim_time and trips for now (too large — see note below)
    f.write("\n-- NOTE: dim_time and trips are excluded from this dump.\n")
    f.write("-- Rebuild them by running: python backend/db/build_database.py\n")

conn.close()

size_mb = OUT.stat().st_size / (1024 * 1024)
elapsed = time.time() - t0
print(f"Done in {elapsed:.1f}s. Dump size: {size_mb:.1f} MB")