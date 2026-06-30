"""
build_warehouse.py — ETL the star schema into a SQL data warehouse and run the
warehouse-grade analytical queries.

Pipeline position:
    build_bi_exports.py  ->  fact/dim CSVs (powerbi/)  ->  THIS  ->  SQL warehouse

Steps:
  1. create the dimensional schema + views (warehouse/schema.sql)
  2. load the conformed dimensions, then the facts (FK-safe order)
  3. run every report in warehouse/analytics.sql, print it, and export to
     outputs/wh_<report>.csv

Engine: SQLite by default (zero-install, ships with Python). The SQL is standard
window-function SQL, so it ports to DuckDB / Postgres / a cloud warehouse with
minimal changes.

    python warehouse/build_warehouse.py
    python warehouse/build_warehouse.py --db /tmp/spectracardio.db
"""

import os
import re
import argparse
import sqlite3
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
PBI = os.path.join(_ROOT, "powerbi")
OUT = os.path.join(_ROOT, "outputs")

# table -> (source csv, columns to load in DDL order)
LOAD = {
    "dim_patient": ("dim_patient.csv",
        ["patient_id", "group_label", "brugada", "sudden_death", "scd_label",
         "basal_pattern", "basal_label", "risk_score", "flagged"]),
    "dim_lead": ("dim_lead.csv", ["lead", "region", "lead_order"]),
    "dim_band": ("dim_band.csv",
        ["band", "band_label", "freq_low_hz", "freq_high_hz", "description"]),
    "fact_band_power": ("fact_band_power.csv",
        ["patient_id", "lead", "band", "abs_power", "rel_power"]),
    "fact_lead_spectral": ("fact_lead_spectral.csv",
        ["patient_id", "lead", "dom_freq", "centroid", "spec_entropy",
         "edge95", "rms", "ptp", "n_peaks"]),
    "fact_threshold_curve": ("fact_threshold_curve.csv",
        ["threshold", "recall", "caught", "missed", "false_alarm", "precision"]),
}
LOAD_ORDER = ["dim_patient", "dim_lead", "dim_band",
              "fact_band_power", "fact_lead_spectral", "fact_threshold_curve"]


def parse_reports(sql_text):
    """Split analytics.sql into {name: query} on '-- name:' markers."""
    parts = re.split(r"--\s*name:\s*(\w+)", sql_text)
    reports = {}
    for i in range(1, len(parts), 2):
        reports[parts[i].strip()] = parts[i + 1].strip()
    return reports


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(_HERE, "spectracardio.db"))
    args = ap.parse_args()

    if os.path.exists(args.db):
        os.remove(args.db)
    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON;")

    # 1. schema + views
    with open(os.path.join(_HERE, "schema.sql")) as f:
        conn.executescript(f.read())

    # 2. load (dims before facts so FKs resolve)
    for tbl in LOAD_ORDER:
        csv, cols = LOAD[tbl]
        df = pd.read_csv(os.path.join(PBI, csv))[cols]
        df.to_sql(tbl, conn, if_exists="append", index=False)
        print(f"loaded {len(df):>5} rows -> {tbl}")
    conn.commit()

    # quick integrity check
    bad = conn.execute("PRAGMA foreign_key_check;").fetchall()
    print("FK integrity:", "OK" if not bad else f"VIOLATIONS {bad}")

    # 3. run reports
    with open(os.path.join(_HERE, "analytics.sql")) as f:
        reports = parse_reports(f.read())
    os.makedirs(OUT, exist_ok=True)
    for name, q in reports.items():
        res = pd.read_sql_query(q, conn)
        res.to_csv(os.path.join(OUT, f"wh_{name}.csv"), index=False)
        print(f"\n===== {name} =====")
        print(res.to_string(index=False))

    print(f"\nWarehouse built -> {args.db}")
    print("Query it directly:  sqlite3", args.db,
          '"SELECT * FROM vw_lead_band_group;"')
    conn.close()


if __name__ == "__main__":
    main()
