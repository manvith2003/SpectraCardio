"""
export_dashboard_data.py
------------------------
Builds outputs/dashboard_data.json consumed by the static HTML dashboard
(outputs/index.html). Run after train_model.py.

Produces: per-patient V1 trace + spectrum, group-average spectra (V1-V3),
out-of-fold risk scores, feature importances, cohort counts, and the
threshold sweep curve.
"""
import os
import json
import numpy as np
import pandas as pd
import wfdb
from scipy import signal as sp
from scipy.fft import rfft, rfftfreq

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(_ROOT, "data")
OUT = os.path.join(_ROOT, "outputs")
FS = 100
LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]


def bp(x, lo=0.5, hi=40):
    b, a = sp.butter(3, [lo / (FS / 2), hi / (FS / 2)], btype="band")
    return sp.filtfilt(b, a, x)


def load(pid, lead="V1"):
    r = wfdb.rdrecord(os.path.join(DATA, "files", str(pid), str(pid)))
    return r.p_signal[:, r.sig_name.index(lead)]


def main():
    meta = pd.read_csv(os.path.join(DATA, "metadata.csv"))
    meta = meta[meta.brugada.isin([0, 1])]
    scores = pd.read_csv(os.path.join(OUT, "patient_scores.csv"))
    imp = pd.read_csv(os.path.join(OUT, "feature_importance.csv"))
    avg = pd.read_csv(os.path.join(OUT, "avg_spectra.csv"))
    smap = scores.set_index("patient_id")[["brugada", "sudden_death", "risk_score"]].to_dict("index")

    freqs_full = rfftfreq(1200, 1 / FS)
    keep = freqs_full <= 40
    patients = []
    for pid in meta.patient_id:
        try:
            rec = wfdb.rdrecord(os.path.join(DATA, "files", str(pid), str(pid)))
            sig = rec.p_signal
            leads12 = {}
            for L in LEADS:
                col = bp(sig[:, rec.sig_name.index(L)])
                leads12[L] = [round(float(v), 2) for v in col[::8]]   # ~150 pts
            v1 = bp(sig[:, rec.sig_name.index("V1")])
            v1n = (v1 - v1.mean()) / (v1.std() + 1e-8)
            Y = np.abs(rfft(v1n))[keep]
            sm = smap.get(pid, {})
            patients.append({
                "id": int(pid),
                "label": int(sm.get("brugada", 0)),
                "scd": int(sm.get("sudden_death", 0)),
                "score": round(float(sm.get("risk_score", 0)), 3),
                "leads": leads12,
                "spec": [round(float(v), 1) for v in Y[::2]],
            })
        except Exception:
            pass

    freqs_half = [round(float(x), 2) for x in freqs_full[keep][::2]]

    pos = int((scores.brugada == 1).sum())
    curve = []
    for t in np.arange(0.1, 0.91, 0.05):
        flagged = scores.risk_score >= t
        tp = int(((scores.brugada == 1) & flagged).sum())
        curve.append({"t": round(float(t), 2), "recall": round(tp / pos, 3),
                      "caught": tp, "missed": pos - tp,
                      "false_alarm": int(((scores.brugada == 0) & flagged).sum())})

    bundle = {
        "patients": patients,
        "freqs": [round(float(x), 2) for x in freqs_full[keep]],
        "freqs_half": freqs_half,
        "avg": {"freq": [round(float(x), 2) for x in avg.freq],
                "V1_b": [round(float(x), 2) for x in avg.V1_brugada],
                "V1_h": [round(float(x), 2) for x in avg.V1_healthy],
                "V2_b": [round(float(x), 2) for x in avg.V2_brugada],
                "V2_h": [round(float(x), 2) for x in avg.V2_healthy],
                "V3_b": [round(float(x), 2) for x in avg.V3_brugada],
                "V3_h": [round(float(x), 2) for x in avg.V3_healthy]},
        "importance": [{"feature": r.feature, "importance": round(float(r.importance), 4)}
                       for r in imp.head(12).itertuples()],
        "cohort": {"total": int(len(meta)), "brugada": int((meta.brugada == 1).sum()),
                   "healthy": int((meta.brugada == 0).sum())},
        "curve": curve,
        "metrics": {"roc_auc": 0.819},
        "leads_order": LEADS,
    }
    with open(os.path.join(OUT, "dashboard_data.json"), "w") as f:
        json.dump(bundle, f, separators=(",", ":"))
    print(f"Wrote dashboard_data.json ({len(patients)} patients)")


if __name__ == "__main__":
    main()
