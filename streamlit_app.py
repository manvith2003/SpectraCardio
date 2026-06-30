"""
streamlit_app.py — SpectraCardio unified dashboard
==================================================
One web UI for the whole project: cohort analysis, FFT spectra, patient triage,
model drivers, AND a live real-time monitor with early-warning forecasting.

Run locally (from the repo root):
    pip install -r requirements.txt
    streamlit run streamlit_app.py          # opens http://localhost:8501

Deploy free on Streamlit Community Cloud:
    push the repo to GitHub -> share.streamlit.io -> New app -> pick this repo
    and `streamlit_app.py` as the entry file. (The Live Monitor's "Synthetic
    demo" works on the cloud with no data download.)

DISCLAIMER: analytical / educational screening demonstration on a public
research dataset. NOT a diagnostic tool; no medical decisions should rely on it.
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_HERE, "outputs")
sys.path.insert(0, os.path.join(_HERE, "src"))
sys.path.insert(0, os.path.join(_HERE, "src", "realtime"))

st.set_page_config(page_title="SpectraCardio — ECG Screening", layout="wide",
                   page_icon="🫀")


@st.cache_data
def load(name):
    return pd.read_csv(os.path.join(OUT, name))


# ---------------------------------------------------------------- header -----
st.title("🫀 SpectraCardio — FFT-based ECG Screening for Brugada Syndrome")
st.caption("Spectral analysis of precordial leads V1–V3 to flag a rare, "
           "potentially fatal arrhythmia. Data: PhysioNet Brugada-HUCA (CC BY-SA 4.0).")
st.warning("⚠️ **Screening demonstration on a research dataset — NOT a diagnostic "
           "tool.** Built for portfolio/educational purposes.", icon="⚠️")

scores = load("patient_scores.csv")
spectra = load("avg_spectra.csv")
importance = load("feature_importance.csv")
cohort = load("query_cohort_overview.csv")
hf = load("query_hf_power_by_group.csv")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Cohort", "🌊 FFT Spectra", "🚦 Triage", "🔍 What drives it",
     "🩺 Live Monitor + Forecast"])

# --- Tab 1: cohort -----------------------------------------------------------
with tab1:
    st.subheader("Cohort overview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total patients", int(scores.shape[0]))
    c2.metric("Brugada cases", int((scores.brugada == 1).sum()))
    c3.metric("Healthy controls", int((scores.brugada == 0).sum()))
    st.markdown("The cohort is **imbalanced (~19% positive)** — realistic for a rare "
                "disease. That is why this project reports **recall on the Brugada "
                "class**, not accuracy: a model that always says *healthy* scores 81% "
                "while catching nobody.")
    st.dataframe(cohort, use_container_width=True)
    st.markdown("**Mean high-frequency relative power (15–40 Hz) by group:**")
    st.dataframe(hf, use_container_width=True)

# --- Tab 2: FFT spectra ------------------------------------------------------
with tab2:
    st.subheader("Average FFT power spectrum: Brugada vs Healthy")
    lead = st.selectbox("Precordial lead", ["V1", "V2", "V3"], index=0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=spectra["freq"], y=spectra[f"{lead}_brugada"],
                             name="Brugada (avg)", line=dict(color="crimson")))
    fig.add_trace(go.Scatter(x=spectra["freq"], y=spectra[f"{lead}_healthy"],
                             name="Healthy (avg)", line=dict(color="steelblue")))
    fig.update_layout(xaxis_title="Frequency (Hz)", yaxis_title="|FFT| magnitude",
                      xaxis_range=[0, 40], height=460, legend=dict(x=0.7, y=0.95))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("Averaged across patients, the **Brugada spectrum sits below the "
                "healthy one in the 15–35 Hz band** — a consistent, learnable "
                "difference and the basis for the FFT features.")

# --- Tab 3: triage -----------------------------------------------------------
with tab3:
    st.subheader("Patient triage by risk score")
    thr = st.slider("Screening threshold", 0.10, 0.90, 0.25, 0.05)
    s = scores.copy()
    s["flag"] = (s.risk_score >= thr).astype(int)
    pos = s[s.brugada == 1]
    caught = int((pos.risk_score >= thr).sum())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Brugada caught", caught)
    m2.metric("Brugada MISSED", int(pos.shape[0] - caught))
    m3.metric("Recall", f"{caught / max(pos.shape[0], 1):.0%}")
    m4.metric("False alarms", int(((s.brugada == 0) & (s.risk_score >= thr)).sum()))
    st.dataframe(
        s.assign(risk_score=s.risk_score.round(3))
         .rename(columns={"brugada": "true_label"})
         [["patient_id", "true_label", "sudden_death", "risk_score", "flag"]]
         .sort_values("risk_score", ascending=False),
        use_container_width=True, height=340)

# --- Tab 4: feature importance ----------------------------------------------
with tab4:
    st.subheader("What the model relies on")
    top = importance.head(12).iloc[::-1]
    fig = px.bar(top, x="importance", y="feature", orientation="h", height=460)
    fig.update_layout(xaxis_title="Random-Forest importance", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)
    st.success("Top predictors are the **FFT high-frequency band-power and "
               "spectral-entropy features in V1** — the spectral approach drives it.")

# --- Tab 5: live monitor + forecast -----------------------------------------
with tab5:
    st.subheader("Real-time monitor with early-warning forecast")
    st.markdown("Streams an ECG at its true rate, recomputes FFT features on a "
                "**sliding 12 s window**, scores Brugada risk live, and **forecasts** "
                "the risk a few steps ahead to pre-alert *before* it crosses the line.")

    FS = 100
    LEADS = ["V1", "V2", "V3"]
    cc1, cc2, cc3, cc4 = st.columns(4)
    synthetic = cc1.toggle("Synthetic demo (no data download)", value=True)
    record = cc2.text_input("Patient id (if not synthetic)", value="188981")
    speed = cc3.slider("Replay speed ×", 5, 60, 30)
    threshold = cc4.slider("Flag threshold", 0.0, 1.0, 0.10, 0.01)
    start = st.button("▶ Start live stream", type="primary")

    def _load_signal():
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
            rec = os.path.join(_HERE, "data", "files", str(rec), str(rec))
        r = wfdb.rdrecord(rec)
        return r.p_signal, r.sig_name

    g1, g2 = st.columns([2, 1])
    trace_ph, spec_ph = g1.empty(), g1.empty()
    gauge_ph, prog_ph = g2.empty(), g2.empty()
    warn_ph = st.empty()
    timeline_ph = st.empty()

    if start:
        try:
            from analyzer import RealTimeAnalyzer
            from scoring import load_scorer
            from forecaster import RiskForecaster
        except Exception as e:
            st.error(f"Could not load the real-time engine ({e}). "
                     f"Run `pip install -r requirements.txt`.")
            st.stop()

        sig, names = _load_signal()
        idx = {l: names.index(l) for l in LEADS if l in names}
        an = RealTimeAnalyzer(load_scorer(), window_sec=12, hop_sec=1.0,
                              threshold=threshold)
        step = max(1, int(FS / speed))
        HORIZON = 4
        fc = RiskForecaster(hop_sec=step / FS)
        risk_hist, t_hist = [], []

        for i in range(sig.shape[0]):
            row = sig[i]
            an.push({"t": i / FS, "leads": {l: float(row[idx[l]]) for l in idx}})
            if i % step != 0:
                continue

            v1 = list(an.buffers["V1"])
            trace_ph.line_chart(pd.DataFrame({"V1 (mV)": np.array(v1[-6 * FS:]) if v1 else [0]}),
                                height=170)
            if len(v1) >= FS:
                w = np.array(v1); w = (w - w.mean()) / (w.std() + 1e-8)
                Y = np.abs(np.fft.rfft(w)); f = np.fft.rfftfreq(len(w), 1 / FS)
                m = f <= 40
                spec_ph.area_chart(pd.DataFrame({"power": Y[m] ** 2},
                                                index=np.round(f[m], 1)), height=170)

            if an.warmup_pct() >= 100:
                risk = an.scorer.predict_proba(an._features())
                risk_hist.append(risk); t_hist.append(round(i / FS, 1))
                flagged = risk >= threshold
                fc.update(risk)
                fhat = fc.forecast(HORIZON)
                warn = fc.pre_alert(threshold, HORIZON)
                gauge_ph.metric("Live Brugada risk", f"{risk:.2f}",
                                delta="FLAG" if flagged else ("WARN ↑" if warn else "ok"),
                                delta_color="inverse" if (flagged or warn) else "normal")
                prog_ph.progress(min(int(risk * 100), 100),
                                 text=f"forecast {fhat:.2f} | slope {fc.slope_per_sec():+.3f}/s")
                if warn and not flagged:
                    lt = warn["lead_time_sec"]
                    warn_ph.warning(f"🔮 **Early-warning pre-alert** — projected to cross "
                                    f"{threshold:.2f} in ~{lt:.0f}s (forecast {fhat:.2f}).")
                elif flagged:
                    warn_ph.error("🚩 Risk crossed the screening threshold — flag for review.")
                else:
                    warn_ph.empty()
                dt = step / FS
                fut_t = [round(t_hist[-1] + k * dt, 1) for k in range(1, HORIZON + 1)]
                fut_v = [fc.forecast(k) for k in range(1, HORIZON + 1)]
                timeline_ph.line_chart(
                    pd.DataFrame({"risk": risk_hist + [None] * HORIZON,
                                  "forecast": [None] * len(risk_hist) + fut_v},
                                 index=t_hist + fut_t), height=220)
            else:
                gauge_ph.metric("Live Brugada risk", "—",
                                delta=f"buffering {an.warmup_pct():.0f}%")
            time.sleep(0.03)
        st.success("Stream complete.")
    else:
        st.info("Toggle options and press **Start live stream**. The risk score begins "
                "once the 12-second analysis window has filled.")

st.divider()
st.caption("Pipeline: WFDB ingest → band-pass → FFT + morphology features → SQL "
           "cohort analysis → class-weighted classifier → real-time monitor + "
           "forecast. Methodology in the README.")
