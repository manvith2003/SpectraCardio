"""
build_db.py
-----------
Loads the extracted feature table into a SQLite database and runs a set of
analytical SQL queries -- the kind a data analyst would write to understand
the cohort before modelling. Saves query results to CSV for the dashboard /
memo and prints a readable summary.
"""

import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sqlite3
import pandas as pd

OUT_DIR = os.path.join(_ROOT, "outputs")
DB_PATH = os.path.join(OUT_DIR, "brugada.db")


def build():
    df = pd.read_csv(os.path.join(OUT_DIR, "features.csv"))
    conn = sqlite3.connect(DB_PATH)
    df.to_sql("ecg_features", conn, if_exists="replace", index=False)

    queries = {}

    # 1. Cohort overview -- class balance + sudden-death rate per group
    queries["cohort_overview"] = """
        SELECT
            CASE brugada WHEN 1 THEN 'Brugada' ELSE 'Healthy' END AS group_label,
            COUNT(*)                              AS n_patients,
            ROUND(AVG(sudden_death) * 100, 1)     AS pct_sudden_death,
            ROUND(AVG(basal_pattern) * 100, 1)    AS pct_basal_pattern
        FROM ecg_features
        GROUP BY brugada
        ORDER BY brugada DESC;
    """

    # 2. Mean high-frequency relative band power in V1 by group
    #    (the discriminative feature we spotted in the signal check)
    queries["hf_power_by_group"] = """
        SELECT
            CASE brugada WHEN 1 THEN 'Brugada' ELSE 'Healthy' END AS group_label,
            ROUND(AVG(V1_bpr_hf_15_40), 4) AS avg_V1_hf_relpower,
            ROUND(AVG(V2_bpr_hf_15_40), 4) AS avg_V2_hf_relpower,
            ROUND(AVG(V3_bpr_hf_15_40), 4) AS avg_V3_hf_relpower,
            ROUND(AVG(V1_spec_entropy), 3) AS avg_V1_spec_entropy
        FROM ecg_features
        GROUP BY brugada
        ORDER BY brugada DESC;
    """

    # 3. Rank patients by a simple "suspicion score" (low HF power = more Brugada-like)
    #    Useful as a triage list -- who a clinician might review first.
    queries["top_suspicion_healthy_labelled"] = """
        SELECT patient_id, brugada,
               ROUND(V1_bpr_hf_15_40, 4) AS V1_hf_relpower,
               ROUND(V1_spec_entropy, 3) AS V1_spec_entropy
        FROM ecg_features
        ORDER BY V1_bpr_hf_15_40 ASC
        LIMIT 15;
    """

    # 4. Sudden-death subgroup -- do these patients differ spectrally?
    queries["sudden_death_profile"] = """
        SELECT
            CASE sudden_death WHEN 1 THEN 'Had SCD event' ELSE 'No SCD event' END AS scd_group,
            COUNT(*) AS n,
            ROUND(AVG(V1_bpr_hf_15_40), 4) AS avg_V1_hf_relpower,
            ROUND(AVG(V1_centroid), 2)     AS avg_V1_centroid
        FROM ecg_features
        WHERE brugada = 1
        GROUP BY sudden_death;
    """

    results = {}
    for name, q in queries.items():
        results[name] = pd.read_sql_query(q, conn)
        results[name].to_csv(os.path.join(OUT_DIR, f"query_{name}.csv"), index=False)

    conn.close()
    return results


if __name__ == "__main__":
    res = build()
    for name, df in res.items():
        print(f"\n===== {name} =====")
        print(df.to_string(index=False))
