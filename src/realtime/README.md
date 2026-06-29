# Real-time ECG analysis (`src/realtime/`)

This package turns the batch Brugada screen into a **live, streaming pipeline**.
Instead of analyzing a fixed CSV of precomputed features, it ingests ECG samples
as they arrive, recomputes FFT spectral features on a **sliding window**, and
re-scores Brugada risk continuously.

```
   SOURCE                  ANALYZER                       SCORER            OUTPUT
 ┌──────────┐   samples   ┌────────────────────────┐    ┌──────────┐    ┌──────────────┐
 │ device / │ ─────────►  │ 12 s sliding window     │──► │ Random   │──► │ live risk +  │
 │ socket / │             │ → band-pass → FFT       │    │ Forest / │    │ flag + log + │
 │ file     │             │ → 42 features (V1–V3)   │    │ logistic │    │ dashboard    │
 └──────────┘             └────────────────────────┘    └──────────┘    └──────────────┘
        every `hop` seconds (default 1 s) once the window is full
```

## Why it's built this way

**The source is pluggable** (`sources.py`). The analyzer consumes a generic
sample stream, so the *same* code runs on a replayed recording, a TCP socket, or
stdin. Swap `WFDBFileSource` for `SocketSource` and you're ingesting a live feed —
no analysis changes. A real ECG device just needs to emit one JSON sample per
line: `{"t": 1.23, "leads": {"V1": 0.01, "V2": -0.02, "V3": 0.0}}`.

**The window matches the training length on purpose.** The model was trained on
features from full 12-second recordings, so the live analyzer defaults to a 12 s
window. That keeps the live feature distribution comparable to training. A shorter
window (`--window 4`) updates faster but drifts from the training distribution —
a real-time-vs-fidelity trade-off, exposed as a flag rather than hidden.

**Feature code is shared, not copied.** The analyzer imports the exact
`bandpass` / `spectral_features` / `morphology_features` from `extract_features.py`,
so the streaming and batch paths can never silently diverge.

**The scorer degrades gracefully** (`scoring.py`). It uses the trained Random
Forest (`outputs/rf_model.joblib`) when available; otherwise it falls back to a
transparent NumPy logistic model trained on `features.csv`, and says which one is
active. Run `python src/train_model.py` first to enable the Random Forest.

## Quick start

```bash
# 0) one-time: get the raw recordings + train the model
python download_data.py
python src/extract_features.py
python src/train_model.py

# A) Replay a real recording at 4× real time
python src/realtime/run_monitor.py --source wfdb --record 188981 --speed 4

# B) Live animated dashboard (great for a portfolio screen-recording)
streamlit run src/realtime/app_realtime.py    # toggle "Synthetic demo" for no-download

# C) Pluggable live feed over TCP (producer + consumer)
#   terminal 1 (consumer/server):
python src/realtime/run_monitor.py --source socket --port 9009
#   terminal 2 (producer = stand-in for a real device):
python src/realtime/replay_sender.py --record 188981 --speed 4
#   (add --synthetic to the sender to test the wiring with no data download)
```

## Early-warning forecasting (predict the spike before it happens)

On top of the live score, `forecaster.py` runs **Holt's double-exponential
smoothing** on the risk stream — an online, trend-aware time-series forecast. It
projects the risk a few steps ahead and fires a **PRE-ALERT while the current
risk is still below threshold**, with an estimated lead time until the crossing.
Same idea a trading model uses to flag a move early.

```bash
python src/realtime/forecast_demo.py     # self-contained, no data/scipy needed
```

In the demo it fires the pre-alert ~3 seconds before the risk actually crosses
0.10. The CLI monitor shows a live `fcast(4s)=…` column and a `WARN` state; the
Streamlit dashboard draws the forecast as a tail extending ahead of the risk line
plus a pre-alert banner. Tune with `--forecast-horizon`.

**Honest scope:** this forecasts the *model's risk signal as it evolves* (a
streaming-analytics / forecasting technique demo). It is not a validated clinical
predictor of a future cardiac event — the research dataset (single 12 s snapshots)
can't support that claim, and the code says so.

## Files

| File | Role |
|------|------|
| `sources.py` | Pluggable sample sources: `WFDBFileSource`, `ArraySource`, `SocketSource`, `StdinSource` |
| `analyzer.py` | `RealTimeAnalyzer` — sliding-window buffering + FFT features + scoring cadence |
| `scoring.py` | `RFModelScorer` (trained RF) and `LogisticScorer` (NumPy fallback) |
| `forecaster.py` | `RiskForecaster` — Holt early-warning forecast + pre-alert with lead time |
| `forecast_demo.py` | Self-contained early-warning demo on a synthetic ramping risk |
| `run_monitor.py` | CLI to run the live screen on any source; writes `outputs/realtime_log.csv` |
| `replay_sender.py` | TCP producer that streams a recording (the device stand-in) |
| `app_realtime.py` | Streamlit live dashboard (scrolling trace, live spectrum, risk gauge, forecast) |

> **Disclaimer:** analytical / educational screening demonstration on a public
> research dataset. NOT a diagnostic tool.
