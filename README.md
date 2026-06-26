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
| Recall @ screening threshold | **~88%** (catches 61/69 cases) | Catches the rare, dangerous cases — the clinical priority |

**Why not accuracy?** A model that always predicts "healthy" scores ~81% here while catching zero real cases. That's useless for screening. I optimized for **recall on the Brugada class** and explicitly traded off more false alarms — the correct call for a flag-for-review aid.

## Interactive dashboard

A custom static dashboard (`outputs/index.html`, deployable free on GitHub Pages) with five views:

- **Overview** — cohort stats and the "why recall, not accuracy" rationale
- **FFT Spectra** — average Brugada-vs-healthy power spectrum per lead (V1–V3)
- **Triage** — every patient ranked by risk, with a live screening-threshold slider
- **Patient Viewer** — click any patient to see their real ECG trace + personal FFT spectrum
- **Model** — feature importances and the recall/false-alarm threshold sweep

It's a static page loading `outputs/dashboard_data.json` — no server needed. A Streamlit version (`src/app.py`) is also included.

## Tech stack & skills demonstrated

| Skill | Tools used |
|-------|-----------|
| Signal processing & FFT | SciPy (`butter`, `filtfilt`, `rfft`), NumPy |
| Feature engineering | pandas, custom spectral + morphology features |
| SQL / cohort analysis | SQLite, analytical `GROUP BY` / ranking queries |
| Machine learning | scikit-learn (Random Forest, Logistic Regression, stratified CV) |
| Handling imbalance | class weighting, recall/precision/F1, threshold tuning |
| Data visualization | HTML/JS, Chart.js, Streamlit/Plotly |
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
# then open outputs/index.html in a browser (or: streamlit run src/app.py)
```

## Dataset

- **PhysioNet Brugada-HUCA** (Costa Cortez & García Iglesias, 2026), CC BY-SA 4.0
- 363 subjects · 12-lead · 12 s · 100 Hz · https://doi.org/10.13026/0m2w-dy83

## Honest limitations

69 positive cases from a single center means this is a **proof-of-concept screening aid, not a deployable diagnostic**. A deep-learning model was deliberately avoided — the data volume doesn't support it, and a simpler interpretable model is more honest here. The spectral approach is grounded in the dataset authors' prior finding that spectral ECG analysis improves Brugada prediction (García-Iglesias et al., *J Clin Med* 2019).

## Citation

Costa Cortez, N., & García Iglesias, D. (2026). *Brugada-HUCA: 12-Lead ECG Recordings for the Study of Brugada Syndrome* (v1.0.0). PhysioNet.
