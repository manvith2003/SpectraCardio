"""
forecast_demo.py
----------------
Self-contained demo of the early-warning forecaster -- no data download, no
scipy/sklearn. It synthesizes a rising risk trajectory (as if a Brugada pattern
is scrolling into the analysis window) and shows the forecaster raising a
PRE-ALERT several seconds before the risk actually crosses the threshold.

    python src/realtime/forecast_demo.py

Saves outputs/forecast_demo_log.csv for inspection / charting.
"""

import os
import csv
import numpy as np
from forecaster import RiskForecaster

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(_ROOT, "outputs")


def synth_risk(n=40, hop=1.0, seed=1):
    """A risk signal that stays low, then ramps up through the threshold."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) * hop
    base = np.full(n, 0.04)
    ramp_start = 12
    base[ramp_start:] += np.linspace(0, 0.32, n - ramp_start)  # climbs past 0.10
    noise = 0.015 * rng.standard_normal(n)
    return t, np.clip(base + noise, 0, 1)


def main(threshold=0.10, horizon_steps=4, hop=1.0):
    t, risk = synth_risk(hop=hop)
    fc = RiskForecaster(hop_sec=hop)

    print("=" * 74)
    print(" SpectraCardio  |  EARLY-WARNING RISK FORECAST (demo)")
    print(f" threshold {threshold:.2f} | forecasting {horizon_steps*hop:.0f}s ahead")
    print("=" * 74)
    print(f"{'t(s)':>5} {'risk':>6} {'forecast':>9} {'slope/s':>8}  status")
    print("-" * 74)

    rows = []
    fired_at = crossed_at = None
    for i in range(len(t)):
        fc.update(risk[i])
        fhat = fc.forecast(horizon_steps)
        lo, hi = fc.band(horizon_steps)
        warn = fc.pre_alert(threshold, horizon_steps)

        status = "ok"
        if risk[i] >= threshold:
            status = "THRESHOLD CROSSED"
            if crossed_at is None:
                crossed_at = t[i]
        elif warn:
            status = f"PRE-ALERT (lead ~{warn['lead_time_sec']:.0f}s)"
            if fired_at is None:
                fired_at = t[i]

        print(f"{t[i]:>5.0f} {risk[i]:>6.3f} {fhat:>9.3f} {fc.slope_per_sec():>8.3f}  {status}")
        rows.append({"t": t[i], "risk": round(risk[i], 4),
                     "forecast": round(fhat, 4),
                     "forecast_lo": round(lo, 4), "forecast_hi": round(hi, 4),
                     "slope_per_sec": round(fc.slope_per_sec(), 4),
                     "pre_alert": int(bool(warn)),
                     "crossed": int(risk[i] >= threshold)})

    print("-" * 74)
    if fired_at is not None and crossed_at is not None:
        print(f" Pre-alert fired at t={fired_at:.0f}s; risk actually crossed at "
              f"t={crossed_at:.0f}s  ->  {crossed_at - fired_at:.0f}s of early warning.")
    elif crossed_at is not None:
        print(f" Risk crossed at t={crossed_at:.0f}s (no early warning fired).")
    else:
        print(" Risk never crossed the threshold in this run.")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "forecast_demo_log.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f" Log saved -> {path}")


if __name__ == "__main__":
    main()
