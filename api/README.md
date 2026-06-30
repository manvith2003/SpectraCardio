# SpectraCardio API (`api/`)

A production-grade **FastAPI** backend that serves the trained screening model and
the analysis data, and also serves the React UI. Auto-generated OpenAPI docs at
`/docs`.

> ⚠️ **RESEARCH / EDUCATIONAL software — NOT a medical device, not clinically
> validated, not for diagnosis or patient care.** Every response carries a
> disclaimer header and the scoring/forecast payloads embed it explicitly. Real
> clinical use would require multi-center validation, prospective trials, and
> regulatory clearance (FDA / CE / CDSCO) under a medical-device quality system.

## Run locally

```bash
pip install -r requirements-dev.txt          # api deps + pytest
uvicorn api.main:app --reload                 # http://localhost:8000
#   docs:  http://localhost:8000/docs
#   UI:    http://localhost:8000/   (serves index.html + outputs/)
```

## Run with Docker

```bash
docker compose up --build                     # http://localhost:8000
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | liveness + which scorer is loaded |
| GET | `/api/cohort` | cohort counts + ROC-AUC |
| GET | `/api/patients?limit=` | patients ranked by risk |
| GET | `/api/patients/{id}` | one patient: trace + spectrum |
| GET | `/api/threshold-curve` | recall/false-alarm sweep |
| POST | `/api/score` | score a posted V1–V3 ECG window → risk + flag |
| POST | `/api/forecast` | early-warning forecast from a risk history |

### Example: score a window

```bash
curl -X POST http://localhost:8000/api/score \
  -H "Content-Type: application/json" \
  -d '{"leads":{"V1":[...1200 samples...],"V2":[...],"V3":[...]}}'
```

### Example: early-warning forecast

```bash
curl -X POST http://localhost:8000/api/forecast \
  -H "Content-Type: application/json" \
  -d '{"risks":[0.02,0.03,0.05,0.07,0.09],"threshold":0.10}'
# -> {"forecast":0.11,"pre_alert":true,"lead_time_steps":...}
```

## Configuration (env vars)

| Var | Default | Meaning |
|-----|---------|---------|
| `SC_THRESHOLD` | `0.10` | screening flag threshold |
| `SC_API_KEY` | _(unset)_ | if set, `/api/score` & `/api/forecast` require `X-API-Key` |
| `SC_ALLOW_ORIGINS` | `*` | CORS origins (comma-separated) |
| `SC_LOG_LEVEL` | `INFO` | log level |
| `SC_MODEL_PATH` | `outputs/rf_model.joblib` | model file; falls back to NumPy logistic |
| `SC_FORECAST_HORIZON` | `4` | steps ahead for the pre-alert |

## Model loading

On startup the service loads the Random Forest from `SC_MODEL_PATH` if present
(run `python src/train_model.py` to create it), otherwise it uses a transparent
NumPy logistic fallback trained from `outputs/features.csv` so the API always
works. `/health` reports which one is active.

## Tests

```bash
pytest -q
```

CI (`.github/workflows/ci.yml`) runs the suite and builds the Docker image on
every push.
