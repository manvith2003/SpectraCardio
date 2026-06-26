"""
app.py -- Brugada Syndrome ECG Screening Dashboard
==================================================
Interactive dashboard for an FFT-based screening demonstration on the
PhysioNet Brugada-HUCA dataset (69 Brugada / 287 healthy, 12-lead, 100 Hz).

Run locally:   streamlit run app.py

DISCLAIMER: This is an analytical / educational screening demonstration on a
public research dataset. It is NOT a diagnostic tool and must not be used for
medical decisions.
"""

import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

_HERE = os.path.dirname(os.path.abspath(__file__))
# Works whether run from repo root (Streamlit Cloud) or from src/ (local)
OUT = os.path.join(_HERE, "..", "outputs")
if not os.path.exists(os.path.join(OUT, "patient_scores.csv")):
    OUT = os.path.join(os.getcwd(), "outputs")

st.set_page_config(page_title="Brugada ECG Screening", layout="wide")


@st.cache_data
def load(name):
    return pd.read_csv(os.path.join(OUT, name))


# ----------------------------------------------------------------------------
st.title("🫀 Brugada Syndrome — FFT-based ECG Screening")
st.caption(
    "Spectral analysis of precordial leads V1–V3 to flag a rare, "
    "potentially fatal cardiac arrhythmia. Data: PhysioNet Brugada-HUCA "
    "(CC BY-SA 4.0)."
)
st.warning(
    "⚠️ **Screening demonstration on a research dataset — NOT a diagnostic "
    "tool.** Built for portfolio/educational purposes. No medical decisions "
    "should be based on this.",
    icon="⚠️",
)

scores = load("patient_scores.csv")
spectra = load("avg_spectra.csv")
importance = load("feature_importance.csv")
cohort = load("query_cohort_overview.csv")
hf = load("query_hf_power_by_group.csv")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Cohort", "🌊 FFT Spectra", "🚦 Patient Triage", "🔍 What drives it"]
)

# --- Tab 1: cohort overview --------------------------------------------------
with tab1:
    st.subheader("Cohort overview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total patients", int(scores.shape[0]))
    c2.metric("Brugada cases", int((scores.brugada == 1).sum()))
    c3.metric("Healthy controls", int((scores.brugada == 0).sum()))
    st.markdown(
        "The cohort is **imbalanced (~19% positive)** — realistic for a rare "
        "disease. That is why this project reports **recall on the Brugada "
        "class**, not accuracy: a model that always says *healthy* would score "
        "81% while catching nobody."
    )
    st.dataframe(cohort, use_container_width=True)
    st.markdown("**Mean high-frequency relative power (15–40 Hz) by group:**")
    st.dataframe(hf, use_container_width=True)
    st.info(
        "Brugada patients show markedly **lower high-frequency power** in "
        "V1–V3 — the spectral signature this screen exploits."
    )

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
                      xaxis_range=[0, 40], height=480,
                      legend=dict(x=0.7, y=0.95))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(
        "Averaged across all patients, the **Brugada spectrum sits below the "
        "healthy one in the 15–35 Hz band** — a consistent, learnable "
        "difference rather than noise. This is the empirical basis for using "
        "FFT features here, consistent with prior spectral-ECG findings in "
        "Brugada syndrome (García-Iglesias et al., 2019)."
    )

# --- Tab 3: triage -----------------------------------------------------------
with tab3:
    st.subheader("Patient triage by risk score")
    st.markdown(
        "Each patient gets an out-of-fold model **risk score**. Adjust the "
        "screening threshold below. For a screening aid we accept more false "
        "alarms to **miss fewer real cases** (higher recall)."
    )
    thr = st.slider("Screening threshold", 0.10, 0.90, 0.25, 0.05)
    s = scores.copy()
    s["flag"] = (s.risk_score >= thr).astype(int)
    pos = s[s.brugada == 1]
    caught = int(((pos.risk_score >= thr)).sum())
    missed = int((pos.shape[0] - caught))
    false_alarm = int(((s.brugada == 0) & (s.risk_score >= thr)).sum())
    recall = caught / max(pos.shape[0], 1)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Brugada caught", caught)
    m2.metric("Brugada MISSED", missed)
    m3.metric("Recall", f"{recall:.0%}")
    m4.metric("False alarms", false_alarm)
    st.dataframe(
        s.assign(risk_score=s.risk_score.round(3))
         .rename(columns={"brugada": "true_label"})
         [["patient_id", "true_label", "sudden_death", "risk_score", "flag"]]
         .sort_values("risk_score", ascending=False),
        use_container_width=True, height=360,
    )

# --- Tab 4: feature importance ----------------------------------------------
with tab4:
    st.subheader("What the model relies on")
    top = importance.head(12).iloc[::-1]
    fig = px.bar(top, x="importance", y="feature", orientation="h", height=480)
    fig.update_layout(xaxis_title="Random-Forest importance", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)
    st.success(
        "The top predictors are the **FFT high-frequency band-power and "
        "spectral-entropy features in V1** — confirming the spectral "
        "(FFT) approach drives the screening, not just raw morphology."
    )

st.divider()
st.caption(
    "Pipeline: WFDB ingest → band-pass filter → FFT + morphology features → "
    "SQL cohort analysis → class-weighted classifier (stratified CV) → this "
    "dashboard. Source + methodology in the project README."
)
