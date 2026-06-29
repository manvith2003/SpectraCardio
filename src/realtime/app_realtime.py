"""
app_realtime.py
---------------
Live-updating Streamlit dashboard for the real-time ECG screen.

Plays a recording (or synthetic signal) as a live feed and animates, in real
time:
  - the scrolling V1 ECG trace,
  - the live FFT power spectrum of the current window,
  - a risk gauge + running risk timeline,
  - a screening flag.

Run:
    streamlit run src/realtime/app_realtime.py

Screen-record this for your portfolio -- a live, animated risk monitor is a
strong visual to show alongside the GitHub repo.

NOTE: analytical screening demonstration on a research dataset -- NOT a
diagnostic tool.
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import streamlit as st

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "src"))
DATA_DIR = os.path.join(_ROOT, "data")
FS = 100
LEADS = ["V1", "V2", "V3"]

from realtime.analyzer import RealTimeAnalyzer
from realtime.scoring import load_scorer
from realtime.forecaster import RiskForecaster

st.set_page_config(page_title="SpectraCardio — Live ECG Screen", layout="wide")
st.title("🫀 SpectraCardio — Real-Time ECG Brugada Screen")
st.caption("Live sliding-window FFT analysis. Educational demo on research data — "
           "NOT a diagnostic tool.")


def load_signal(record, synthetic):
    if synthetic:
        n = 24 * FS
        t = np.arange(n) / FS
        rng = np.random.default_rng(0)
        base = 0.6 * np.sin(2 * np.pi * 1.2 * t) + 0.2 * np.sin(2 * np.pi * 12 * t)
        sig = np.stack([base + 0.05 * rng.standard_normal(n) for _ in LEADS], axis=1)
        return sig, LEADS
    import wfdb
    rec = record
    if os.path.sep not in str(rec):
        rec = os.path.join(DATA_DIR, "files", str(rec), str(rec))
    r = wfdb.rdrecord(rec)
    return r.p_signal, r.sig_name


# ---- controls --------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
synthetic = c1.toggle("Synthetic demo (no data download)", value=True)
record = c2.text_input("Patient id (if not synthetic)", value="188981")
speed = c3.slider("Replay speed (×)", 1, 50, 20)
threshold = c4.slider("Flag threshold", 0.0, 1.0, 0.10, 0.01)
start = st.button("▶ Start live stream", type="primary")

# layout placeholders
g1, g2 = st.columns([2, 1])
trace_ph = g1.empty()
spec_ph = g1.empty()
gauge_ph = g2.empty()
metric_ph = g2.empty()
warn_ph = st.empty()
timeline_ph = st.empty()

if start:
    sig, names = load_signal(record, synthetic)
    idx = {l: names.index(l) for l in LEADS if l in names}
    scorer = load_scorer()
    an = RealTimeAnalyzer(scorer, window_sec=12, hop_sec=1.0, threshold=threshold)

    risk_hist, t_hist = [], []
    window_v1 = []
    n = sig.shape[0]
    step = max(1, int(FS / (speed)))  # samples to advance per UI frame
    HORIZON = 4                       # forecast steps ahead (UI frames)
    fc = RiskForecaster(hop_sec=step / FS)

    for i in range(n):
        row = sig[i]
        an.push({"t": i / FS, "leads": {l: float(row[idx[l]]) for l in idx}})
        window_v1 = list(an.buffers["V1"])

        if i % step != 0:
            continue

        # scrolling V1 trace (last ~6 s)
        tail = np.array(window_v1[-6 * FS:]) if window_v1 else np.array([0.0])
        trace_ph.line_chart(pd.DataFrame({"V1 (mV)": tail}), height=180)

        # live spectrum of current window
        if len(window_v1) >= FS:
            w = np.array(window_v1)
            w = (w - w.mean()) / (w.std() + 1e-8)
            Y = np.abs(np.fft.rfft(w))
            f = np.fft.rfftfreq(len(w), 1 / FS)
            m = f <= 40
            spec_ph.area_chart(pd.DataFrame({"power": (Y[m] ** 2)}, index=np.round(f[m], 1)),
                               height=180)

        # live score for display: read the current window directly every frame
        # (independent of the analyzer's hop cadence, which paces the CLI log)
        if an.warmup_pct() >= 100:
            risk = scorer.predict_proba(an._features())
            risk_hist.append(risk); t_hist.append(round(i / FS, 1))
            flagged = risk >= threshold

            # early-warning forecast
            fc.update(risk)
            fhat = fc.forecast(HORIZON)
            warn = fc.pre_alert(threshold, HORIZON)

            gauge_ph.metric("Live Brugada risk", f"{risk:.2f}",
                            delta="FLAG" if flagged else ("WARN ↑" if warn else "ok"),
                            delta_color="inverse" if (flagged or warn) else "normal")
            metric_ph.progress(min(int(risk * 100), 100),
                               text=f"{'⚠️ FLAGGED for review' if flagged else 'below threshold'} "
                                    f"| forecast {fhat:.2f} | slope {fc.slope_per_sec():+.3f}/s")

            if warn and not flagged:
                lt = warn["lead_time_sec"]
                warn_ph.warning(f"🔮 **Early-warning pre-alert** — risk trending up, "
                                f"projected to cross {threshold:.2f} in "
                                f"~{lt:.0f}s (forecast {fhat:.2f}).")
            elif flagged:
                warn_ph.error(f"🚩 Risk crossed the screening threshold — flag for review.")
            else:
                warn_ph.empty()

            # timeline with a dashed-style forecast tail extended HORIZON steps ahead
            dt = step / FS
            fut_t = [round(t_hist[-1] + k * dt, 1) for k in range(1, HORIZON + 1)]
            fut_v = [fc.forecast(k) for k in range(1, HORIZON + 1)]
            chart_df = pd.DataFrame(
                {"risk": risk_hist + [None] * HORIZON,
                 "forecast": [None] * len(risk_hist) + fut_v},
                index=t_hist + fut_t)
            timeline_ph.line_chart(chart_df, height=220)
        else:
            gauge_ph.metric("Live Brugada risk", "—",
                            delta=f"buffering {an.warmup_pct():.0f}%")
        time.sleep(0.03)

    st.success("Stream complete.")
else:
    st.info("Set options and press **Start live stream**. The risk score begins "
            "once the 12-second analysis window has filled.")
