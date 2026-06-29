"""
build_bi_exports.py
-------------------
Reshapes the analysis outputs into BI-tool-ready datasets:

  powerbi/  -> a clean STAR SCHEMA (fact + dimension tables) for Power BI,
               the layout Power BI's model view and DAX expect.
  tableau/  -> a single denormalized LONG table for Tableau Public, the
               layout Tableau's "one row per mark" model likes best.

Both are built from the same source files (features.csv, patient_scores.csv,
dashboard_data.json), so the two dashboards tell an identical, consistent story.

Run after train_model.py + export_dashboard_data.py:
    python src/build_bi_exports.py
"""

import os
import sys
import json
import numpy as np
import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src", "realtime"))
OUT_DIR = os.path.join(_ROOT, "outputs")
PBI_DIR = os.path.join(_ROOT, "powerbi")
TAB_DIR = os.path.join(_ROOT, "tableau")

LEADS = ["V1", "V2", "V3"]
BANDS = {
    "lf_0p5_5": ("LF (0.5-5 Hz)", 0.5, 5, "ST / T-wave morphology band"),
    "mf_5_15": ("MF (5-15 Hz)", 5, 15, "QRS bulk energy band"),
    "hf_15_40": ("HF (15-40 Hz)", 15, 40, "High-frequency content (key Brugada signal)"),
}


def load():
    feats = pd.read_csv(os.path.join(OUT_DIR, "features.csv"))
    scores = pd.read_csv(os.path.join(OUT_DIR, "patient_scores.csv"))[
        ["patient_id", "risk_score", "flagged"]]
    df = feats.merge(scores, on="patient_id", how="left")
    df["group_label"] = df["brugada"].map({1: "Brugada", 0: "Healthy"})
    df["scd_label"] = df["sudden_death"].map({1: "SCD history", 0: "No SCD"})
    df["basal_label"] = df["basal_pattern"].map({1: "Basal pattern", 0: "No basal pattern"})
    return df


def band_power_long(df):
    """One row per (patient, lead, band): the heart of both exports."""
    rows = []
    for _, r in df.iterrows():
        for lead in LEADS:
            for band, (blabel, lo, hi, desc) in BANDS.items():
                rows.append({
                    "patient_id": r["patient_id"],
                    "lead": lead,
                    "band": band,
                    "band_label": blabel,
                    "abs_power": r[f"{lead}_bp_{band}"],
                    "rel_power": r[f"{lead}_bpr_{band}"],
                })
    return pd.DataFrame(rows)


def lead_spectral_long(df):
    """One row per (patient, lead): lead-level spectral summaries."""
    rows = []
    for _, r in df.iterrows():
        for lead in LEADS:
            rows.append({
                "patient_id": r["patient_id"], "lead": lead,
                "dom_freq": r[f"{lead}_dom_freq"],
                "centroid": r[f"{lead}_centroid"],
                "spec_entropy": r[f"{lead}_spec_entropy"],
                "edge95": r[f"{lead}_edge95"],
                "rms": r[f"{lead}_rms"], "ptp": r[f"{lead}_ptp"],
                "n_peaks": r[f"{lead}_n_peaks"],
            })
    return pd.DataFrame(rows)


def threshold_curve():
    d = json.load(open(os.path.join(OUT_DIR, "dashboard_data.json")))
    cur = pd.DataFrame(d["curve"])
    cur = cur.rename(columns={"t": "threshold"})
    cur["precision"] = cur["caught"] / (cur["caught"] + cur["false_alarm"]).replace(0, pd.NA)
    return cur


def forecast_timeline(threshold=0.10, horizon_steps=4, hop=1.0):
    """Run the early-warning forecaster over an illustrative monitoring episode
    and return a time-indexed table for BI tools to chart (live risk vs forecast
    vs threshold, with pre-alert and crossing markers).

    The episode mirrors src/realtime/forecast_demo.py: risk sits low, then ramps
    up through the threshold -- the scenario where the early-warning matters.
    Illustrative (not a specific patient); the forecaster logic is the real one.
    """
    from forecaster import RiskForecaster

    n = 40
    rng = np.random.default_rng(1)
    t = np.arange(n) * hop
    risk = np.full(n, 0.04)
    risk[12:] += np.linspace(0, 0.32, n - 12)
    risk = np.clip(risk + 0.015 * rng.standard_normal(n), 0, 1)

    fc = RiskForecaster(hop_sec=hop)
    rows = []
    for i in range(n):
        fc.update(risk[i])
        fhat = fc.forecast(horizon_steps)
        lo, hi = fc.band(horizon_steps)
        warn = fc.pre_alert(threshold, horizon_steps)
        rows.append({
            "t_sec": float(t[i]),
            "risk": round(float(risk[i]), 4),
            "forecast": round(fhat, 4),
            "forecast_lo": round(lo, 4),
            "forecast_hi": round(hi, 4),
            "slope_per_sec": round(fc.slope_per_sec(), 4),
            "threshold": threshold,
            "pre_alert": int(bool(warn)),
            "flagged": int(risk[i] >= threshold),
            "lead_time_sec": round(warn["lead_time_sec"], 1) if warn and warn["lead_time_sec"] else None,
        })
    return pd.DataFrame(rows)


def main():
    os.makedirs(PBI_DIR, exist_ok=True)
    os.makedirs(TAB_DIR, exist_ok=True)
    df = load()

    # ---- POWER BI STAR SCHEMA --------------------------------------------
    dim_patient = df[["patient_id", "group_label", "brugada", "sudden_death",
                      "scd_label", "basal_pattern", "basal_label",
                      "risk_score", "flagged"]].copy()
    dim_patient.to_csv(os.path.join(PBI_DIR, "dim_patient.csv"), index=False)

    dim_lead = pd.DataFrame({
        "lead": LEADS,
        "region": ["Right precordial"] * 3,
        "lead_order": [1, 2, 3],
    })
    dim_lead.to_csv(os.path.join(PBI_DIR, "dim_lead.csv"), index=False)

    dim_band = pd.DataFrame([
        {"band": b, "band_label": v[0], "freq_low_hz": v[1],
         "freq_high_hz": v[2], "description": v[3]}
        for b, v in BANDS.items()])
    dim_band.to_csv(os.path.join(PBI_DIR, "dim_band.csv"), index=False)

    fact_band = band_power_long(df)
    fact_band.to_csv(os.path.join(PBI_DIR, "fact_band_power.csv"), index=False)

    fact_lead = lead_spectral_long(df)
    fact_lead.to_csv(os.path.join(PBI_DIR, "fact_lead_spectral.csv"), index=False)

    curve = threshold_curve()
    curve.to_csv(os.path.join(PBI_DIR, "fact_threshold_curve.csv"), index=False)

    fcast = forecast_timeline()
    fcast.to_csv(os.path.join(PBI_DIR, "fact_forecast_timeline.csv"), index=False)

    # ---- TABLEAU DENORMALIZED LONG TABLE ---------------------------------
    tab = fact_band.merge(
        df[["patient_id", "group_label", "brugada", "sudden_death", "scd_label",
            "risk_score", "flagged"]], on="patient_id", how="left")
    ent = fact_lead[["patient_id", "lead", "spec_entropy", "centroid",
                     "dom_freq", "edge95"]]
    tab = tab.merge(ent, on=["patient_id", "lead"], how="left")
    tab = tab.merge(dim_lead[["lead", "region"]], on="lead", how="left")
    tab = tab.merge(dim_band[["band", "band_label", "freq_low_hz", "freq_high_hz"]]
                    .rename(columns={"band_label": "band_label_dim"}),
                    on="band", how="left")
    tab.to_csv(os.path.join(TAB_DIR, "tableau_features_long.csv"), index=False)
    # Also a one-row-per-patient table for the triage / score-distribution views.
    dim_patient.to_csv(os.path.join(TAB_DIR, "tableau_patients.csv"), index=False)
    curve.to_csv(os.path.join(TAB_DIR, "tableau_threshold_curve.csv"), index=False)
    fcast.to_csv(os.path.join(TAB_DIR, "tableau_forecast_timeline.csv"), index=False)

    print("Power BI star schema written ->", PBI_DIR)
    for f in sorted(os.listdir(PBI_DIR)):
        print("   ", f)
    print("Tableau datasets written ->", TAB_DIR)
    for f in sorted(os.listdir(TAB_DIR)):
        print("   ", f)
    print(f"\nfact_band_power rows: {len(fact_band)}  (356 patients x 3 leads x 3 bands)")
    print(f"tableau_features_long rows: {len(tab)}")


if __name__ == "__main__":
    main()
