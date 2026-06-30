"""
service.py — business logic behind the API.

Loads the scorer once (lazy singleton), computes FFT features on a posted ECG
window using the SAME code as the batch/real-time pipelines, scores risk, runs
the early-warning forecaster, and serves cohort/patient data.
"""

import os
import sys
import json
import functools
import numpy as np

from .config import settings

# make the project's analysis modules importable
sys.path.insert(0, os.path.join(settings.ROOT, "src"))
sys.path.insert(0, os.path.join(settings.ROOT, "src", "realtime"))

LEADS = ["V1", "V2", "V3"]


@functools.lru_cache(maxsize=1)
def get_scorer():
    """Load the model once. RF if available, else the NumPy logistic fallback."""
    from scoring import load_scorer
    return load_scorer()


@functools.lru_cache(maxsize=1)
def _feature_funcs():
    from extract_features import bandpass, spectral_features, morphology_features
    return bandpass, spectral_features, morphology_features


@functools.lru_cache(maxsize=1)
def _importance():
    import pandas as pd
    p = os.path.join(settings.OUTPUTS, "feature_importance.csv")
    return pd.read_csv(p)


@functools.lru_cache(maxsize=1)
def _dashboard():
    with open(os.path.join(settings.OUTPUTS, "dashboard_data.json")) as f:
        return json.load(f)


def features_from_window(leads: dict) -> dict:
    """Compute the 42-feature vector from a posted ECG window."""
    bandpass, spectral_features, morphology_features = _feature_funcs()
    feats = {}
    for lead in LEADS:
        raw = np.asarray(leads[lead], dtype=float)
        filt = bandpass(raw, fs=settings.FS)
        feats.update(spectral_features(filt, fs=settings.FS, prefix=f"{lead}_"))
        feats.update(morphology_features(filt, fs=settings.FS, prefix=f"{lead}_"))
    return feats


def score_window(leads: dict, threshold: float | None = None) -> dict:
    thr = settings.DEFAULT_THRESHOLD if threshold is None else threshold
    scorer = get_scorer()
    feats = features_from_window(leads)
    risk = scorer.predict_proba(feats)
    top = _importance().head(5)
    return {
        "risk_score": round(float(risk), 4),
        "flagged": bool(risk >= thr),
        "threshold": thr,
        "top_features": [{"feature": r.feature, "importance": float(r.importance)}
                         for r in top.itertuples()],
        "scorer": scorer.name,
        "disclaimer": settings.DISCLAIMER,
    }


def forecast_risks(risks: list, threshold: float | None = None,
                   horizon: int | None = None) -> dict:
    from forecaster import RiskForecaster
    thr = settings.DEFAULT_THRESHOLD if threshold is None else threshold
    H = settings.FORECAST_HORIZON if horizon is None else horizon
    fc = RiskForecaster(hop_sec=1.0)
    for r in risks:
        fc.update(float(r))
    warn = fc.pre_alert(thr, H)
    return {
        "forecast": round(fc.forecast(H), 4),
        "slope_per_step": round(fc.slope_per_sec(), 4),
        "pre_alert": bool(warn),
        "lead_time_steps": (round(warn["lead_time_sec"], 2)
                            if warn and warn["lead_time_sec"] is not None else None),
        "threshold": thr,
        "disclaimer": settings.DISCLAIMER,
    }


def cohort() -> dict:
    d = _dashboard()
    c = d["cohort"]
    return {"total": c["total"], "brugada": c["brugada"], "healthy": c["healthy"],
            "roc_auc": d["metrics"]["roc_auc"], "disclaimer": settings.DISCLAIMER}


def patients(limit: int = 50) -> list:
    d = _dashboard()
    rows = sorted(d["patients"], key=lambda p: -p["score"])[:limit]
    return [{"id": p["id"], "label": p["label"], "scd": p["scd"],
             "risk_score": p["score"]} for p in rows]


def patient(pid: int) -> dict | None:
    d = _dashboard()
    for p in d["patients"]:
        if p["id"] == pid:
            return {"id": p["id"], "label": p["label"], "scd": p["scd"],
                    "risk_score": p["score"], "leads": p["leads"],
                    "spectrum": p["spec"], "freqs": d["freqs_half"]}
    return None


def threshold_curve() -> list:
    return _dashboard()["curve"]
