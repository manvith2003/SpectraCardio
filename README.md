# 🫀 SpectraCardio — FFT-Based ECG Screening for Brugada Syndrome

**An end-to-end data-analysis project: from raw 12-lead ECG signals to an interactive risk-triage dashboard.**
Signal processing (FFT) → feature engineering → SQL cohort analysis → a recall-tuned classifier → a deployed dashboard.

![Python](https://img.shields.io/badge/Python-3.9+-blue) ![SciPy](https://img.shields.io/badge/SciPy-signal%20%2B%20FFT-orange) ![SQLite](https://img.shields.io/badge/SQL-SQLite-green) ![scikit--learn](https://img.shields.io/badge/scikit--learn-RandomForest-red) ![Dashboard](https://img.shields.io/badge/Dashboard-HTML%2FJS%2FChart.js-yellow)

> ⚠️ **Disclaimer:** Analytical / educational **screening demonstration on a public research dataset**. **NOT a diagnostic tool** and not for any medical decision. Brugada diagnosis is a clinical decision made by cardiologists.

---

## What this project shows

I took 356 real anonymized 12-lead ECG recordings and asked a practical analytics question: **can spectral features of the heartbeat flag patients who may have Brugada syndrome** — a rare but potentially fatal arrhythmia — so a clinician knows who to review first?

This required the full data-analyst toolkit end to end:

- **Data acquisition & cleaning** — ingesting raw WFDB signal files, filtering noise, handling missing/ambiguous labels.
- **Feature engineering** — turning a 1,200-point time series per lead into 42 interpretable features using the **Fast Fourier Transform** (band power, spectral entropy, spectral centroid, edge frequency) plus time-domain morphology.
- **SQL analysis** — loading the feature table into **SQLite** and writing cohort queries to compare groups and build a triage ranking.
- **Modeling with the right metric** — a class-weighted classifier evaluated on **recall**, not accuracy, because the cohort is imbalanced and missing a fatal condition is the costly error.
- **Communication** — an interactive dashboard and a written rationale so a non-technical stakeholder can follow the *why*.

## Headline results (out-of-fold, stratified 5-fold CV)

| Metric | Result | Why it matters |
|--------|--------|----------------|
| Cohort | 356 patients · **69 Brugada / 287 healthy** (~19% positive) | Realistic class imbalance |
| Top signal | V1 high-frequency (15–40 Hz) **relative power: 0.099 (Brugada) vs 0.183 (healthy)** | Brugada patients have ~2× lower HF power in V1 — the spectral approach works |
| ROC-AUC | **≈ 0.82** (Random Forest) | Good separation for a single-center screen |
| Recall @ screening threshold (0.10) | **~90%** (catches 62/69) — at the cost of 132/287 false alarms | High recall is the clinical priority; the false-alarm cost is the honest trade-off |

**Why not accuracy?** A model that always predicts "healthy" scores ~81% here while catching zero real cases. That's useless for screening. I optimized for **recall on the Brugada class** and explicitly accepted more false alarms — at a screening threshold of 0.10 the model catches ~90% of Brugada cases (62/69) but flags 46% of healthy patients too. That trade-off is the correct call for a first-pass flag-for-review aid, and the dashboard's threshold slider makes the recall/false-alarm balance explicit rather than hiding it.

## Three ways to consume the analysis

Beyond the batch pipeline, the project ships the same findings through the tools
data-analyst roles actually screen for:

- **Real-time waveform analysis** (`src/realtime/`) — a true streaming pipeline:
  ingests ECG samples from a pluggable source (file replay, TCP socket, or stdin),
  recomputes FFT spectral features on a **sliding 12 s window**, and re-scores
  Brugada risk continuously, firing a flag when risk crosses threshold. Includes a
  live-updating **Streamlit dashboard** (`app_realtime.py`) and a socket producer so
  a real ECG device feed could drop in. See `src/realtime/README.md`. The analyzer
  reuses the exact batch feature code, so streaming and batch never diverge.
- **Early-warning forecasting** (`src/realtime/forecaster.py`) — Holt
  double-exponential smoothing on the live risk stream projects the score a few
  steps ahead and fires a **pre-alert before** the risk crosses threshold, with an
  estimated lead time (a trading-style "predict the spike early" technique). Demo:
  `python src/realtime/forecast_demo.py` (fires ~3 s before the crossing).
- **Cohort triage replay** (`src/stream_monitor.py`) — replays the cohort's
  cross-validated scores as a patient feed and tracks recall / false-alarm rate as
  the stream advances, a quick online-metrics demo. Run: `python src/stream_monitor.py`.
- **Advanced SQL cohort analysis** (`sql/analysis.sql` + `src/deep_analysis.py`) —
  CTEs and window functions (`NTILE`, `PERCENT_RANK`) for a risk-decile lift table,
  per-lead separation, and a "healthy-but-high-suspicion" review list, auto-written
  up in `outputs/sql_findings.md`.
- **Dimensional data warehouse** (`warehouse/`) — a star-schema SQL warehouse
  (DDL with enforced foreign keys, ETL loader, semantic views) plus warehouse-grade
  analytics: cumulative-gains via `NTILE` + running `SUM() OVER`, `LAG()` marginal
  cost-per-case analysis, conditional-aggregation pivots, `PERCENT_RANK`/`CUME_DIST`
  percentiles, and rollup summaries. Build: `python warehouse/build_warehouse.py`.
  See `warehouse/README.md`.
- **Power BI & Tableau-ready data** (`powerbi/`, `tableau/`) — a clean star schema
  with DAX measures for Power BI, and a denormalized long table for Tableau Public,
  each with a step-by-step build guide. Generated by `src/build_bi_exports.py`.

A quick result from the SQL layer: bucketing patients into deciles by V1
high-frequency power, the most-suspicious decile is **52.8% Brugada** versus
near-0% in the cleanest deciles — and a second, independent feature (spectral
entropy) shows the same gradient (44.9% → 3.4% across quartiles).

## Modern web app (glassmorphism React)

`index.html` at the repo root is a sleek dark **React + Chart.js** single-page app
(glass cards, animated gradient background, neon accents) with six views: Overview,
FFT Spectra, Triage (live threshold slider), Patient Viewer, Model, and an animated
**Live Monitor** with early-warning forecasting. No build step — it loads
`outputs/dashboard_data.json` directly.

```bash
python -m http.server 8000        # serve locally, then open http://localhost:8000
```

Deploy free: on **GitHub Pages** it becomes your homepage at
`https://<user>.github.io/SpectraCardio/`; or import the repo on **Vercel**
(framework "Other", no build command) for a `*.vercel.app` URL.

## Production backend (FastAPI + Docker + CI)

A production-grade **FastAPI** service (`api/`) serves the model and data, with
auto-generated OpenAPI docs, input validation, structured logging, optional API-key
auth, CORS, health checks, and a mandatory disclaimer on every response. It also
serves the React UI.

```bash
pip install -r requirements-dev.txt
uvicorn api.main:app --reload     # API + docs at http://localhost:8000/docs
# or, containerized:
docker compose up --build
```

Endpoints include `/health`, `/api/cohort`, `/api/patients`, `/api/score`
(score a posted ECG window), and `/api/forecast` (early-warning). Tests run with
`pytest`; GitHub Actions (`.github/workflows/ci.yml`) runs the suite and builds the
Docker image on every push. Full details in [`api/README.md`](api/README.md).

**Deploy the whole stack free** (UI + API + docs from one URL) on Render via the
included `render.yaml` Blueprint — see [`DEPLOY.md`](DEPLOY.md).

> ⚠️ This is **production-grade engineering of a research demo** — robust, tested,
> deployable software. It is **not** a cleared medical device. Real clinical use
> would require multi-center validation, prospective trials, and regulatory
> clearance (FDA / CE / CDSCO) under a medical-device quality system (IEC 62304).

## Classic dashboard

A custom static dashboard (`outputs/index.html`, deployable free on GitHub Pages) with five views:

- **Overview** — cohort stats and the "why recall, not accuracy" rationale
- **FFT Spectra** — average Brugada-vs-healthy power spectrum per lead (V1–V3)
- **Triage** — every patient ranked by risk, with a live screening-threshold slider
- **Patient Viewer** — click any patient to see their real ECG trace + personal FFT spectrum
- **Model** — feature importances and the recall/false-alarm threshold sweep

It's a static page loading `outputs/dashboard_data.json` — no server needed.

## Unified web app (one UI, deployable)

`streamlit_app.py` is a single dashboard that bundles **everything** — cohort
stats, FFT spectra, patient triage, model drivers, and a **live real-time monitor
with early-warning forecasting** — into one app.

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py        # opens http://localhost:8501
```

**Deploy it free** on Streamlit Community Cloud: push the repo to GitHub, go to
[share.streamlit.io](https://share.streamlit.io) → New app → pick this repo and
`streamlit_app.py` as the entry file. The Live Monitor's "Synthetic demo" toggle
runs on the cloud with no data download, so the deployed app works out of the box.

## Tech stack & skills demonstrated

| Skill | Tools used |
|-------|-----------|
| Signal processing & FFT | SciPy (`butter`, `filtfilt`, `rfft`), NumPy |
| Feature engineering | pandas, custom spectral + morphology features |
| SQL / cohort analysis | SQLite — CTEs, window functions (`NTILE`, `PERCENT_RANK`), lift analysis |
| Machine learning | scikit-learn (Random Forest, Logistic Regression, stratified CV) |
| Handling imbalance | class weighting, recall/precision/F1, threshold tuning |
| Streaming / real-time | sliding-window FFT analysis on a live sample feed, pluggable sources (socket/stdin/file), online metric tracking |
| BI / dashboarding | Power BI star schema + DAX, Tableau Public, HTML/JS + Chart.js, Streamlit/Plotly |
| Data modeling | star schema (fact/dimension), tidy long-format reshaping |
| Reproducibility | scripted pipeline, pinned `requirements.txt` |

## Pipeline

```
WFDB ingest → band-pass filter (0.5–40 Hz) → FFT + morphology feature
extraction (V1–V3) → SQLite cohort analysis → class-weighted classifier
(stratified 5-fold CV) → interactive dashboard
```

| Stage | Tool | File |
|-------|------|------|
| Download data | urllib | `download_data.py` |
| Feature extraction (FFT + morphology) | SciPy, wfdb | `src/extract_features.py` |
| SQL cohort analysis | SQLite | `src/build_db.py` |
| Classifier + evaluation | scikit-learn | `src/train_model.py` |
| Dashboard data export | NumPy/pandas | `src/export_dashboard_data.py` |
| Dashboard (static) | HTML/JS/Chart.js | `outputs/index.html` |
| Dashboard (alt) | Streamlit/Plotly | `src/app.py` |

## Reproduce from scratch

```bash
pip install -r requirements.txt
python download_data.py                  # ~18 MB, open access
python src/extract_features.py
python src/build_db.py
python src/train_model.py
python src/export_dashboard_data.py
python src/deep_analysis.py              # advanced SQL findings -> outputs/sql_findings.md
python src/build_bi_exports.py           # Power BI + Tableau datasets
python src/stream_monitor.py             # real-time triage simulation
# then open outputs/index.html in a browser (or: streamlit run src/app.py)
```

## Dataset

- **PhysioNet Brugada-HUCA** (Costa Cortez & García Iglesias, 2026), CC BY-SA 4.0
- 363 subjects · 12-lead · 12 s · 100 Hz · https://doi.org/10.13026/0m2w-dy83

## Honest limitations

69 positive cases from a single center means this is a **proof-of-concept screening aid, not a deployable diagnostic**. A deep-learning model was deliberately avoided — the data volume doesn't support it, and a simpler interpretable model is more honest here. The spectral approach is grounded in the dataset authors' prior finding that spectral ECG analysis improves Brugada prediction (García-Iglesias et al., *J Clin Med* 2019).

## Citation

Costa Cortez, N., & García Iglesias, D. (2026). *Brugada-HUCA: 12-Lead ECG Recordings for the Study of Brugada Syndrome* (v1.0.0). PhysioNet.
