"""Builds the data warehouse into a temp DB and checks integrity + a report."""
import os
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_warehouse_builds_and_is_consistent(tmp_path):
    db = tmp_path / "wh.db"
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "warehouse", "build_warehouse.py"),
         "--db", str(db)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert db.exists()

    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON;")

    # row counts match the known cohort/star-schema sizes
    assert conn.execute("SELECT COUNT(*) FROM dim_patient").fetchone()[0] == 356
    assert conn.execute("SELECT COUNT(*) FROM fact_band_power").fetchone()[0] == 356 * 3 * 3

    # referential integrity holds
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

    # the gains view-style query: deciles must capture 100% of positives by the end
    cum = conn.execute("""
        WITH ranked AS (
          SELECT f.patient_id, p.brugada,
                 NTILE(10) OVER (ORDER BY f.rel_power ASC) AS decile
          FROM fact_band_power f JOIN dim_patient p ON p.patient_id=f.patient_id
          WHERE f.lead='V1' AND f.band='hf_15_40')
        SELECT SUM(brugada) FROM ranked
    """).fetchone()[0]
    assert cum == 69
    conn.close()
