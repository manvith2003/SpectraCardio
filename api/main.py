"""
main.py — SpectraCardio FastAPI application.

Run:  uvicorn api.main:app --reload      (docs at http://localhost:8000/docs)

RESEARCH / EDUCATIONAL SOFTWARE — NOT a medical device. Every response carries a
disclaimer header and the scoring/forecast payloads embed it explicitly.
"""

import time
import logging

from fastapi import FastAPI, Header, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from . import schemas, service, __version__

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("spectracardio")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=("FFT-based ECG screening API (Brugada syndrome). **" +
                 settings.DISCLAIMER + "**"),
)

app.add_middleware(
    CORSMiddleware, allow_origins=settings.ALLOW_ORIGINS,
    allow_methods=["*"], allow_headers=["*"])


# --- middleware: request logging + timing + disclaimer header ---------------
@app.middleware("http")
async def observability(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    dt = (time.perf_counter() - t0) * 1000
    response.headers["X-SpectraCardio-Disclaimer"] = (
        "research/educational only - not a medical device")
    response.headers["X-Process-Time-ms"] = f"{dt:.1f}"
    log.info("%s %s -> %s (%.1f ms)", request.method, request.url.path,
             response.status_code, dt)
    return response


# --- security: optional API key on protected routes -------------------------
def require_api_key(x_api_key: str = Header(default="")):
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
    return True


# --- error handling ---------------------------------------------------------
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal error"})


# --- routes -----------------------------------------------------------------
@app.get("/health", response_model=schemas.HealthResponse, tags=["meta"])
def health():
    try:
        sc = service.get_scorer()
        return {"status": "ok", "app": settings.APP_NAME, "version": __version__,
                "scorer": sc.name, "model_loaded": True}
    except Exception as e:
        log.error("scorer load failed: %s", e)
        return {"status": "degraded", "app": settings.APP_NAME, "version": __version__,
                "scorer": "unavailable", "model_loaded": False}


@app.get("/api/cohort", response_model=schemas.CohortResponse, tags=["data"])
def get_cohort():
    return service.cohort()


@app.get("/api/patients", tags=["data"])
def get_patients(limit: int = 50):
    if not 1 <= limit <= 400:
        raise ValueError("limit must be between 1 and 400")
    return service.patients(limit)


@app.get("/api/patients/{pid}", tags=["data"])
def get_patient(pid: int):
    p = service.patient(pid)
    if p is None:
        raise HTTPException(status_code=404, detail=f"patient {pid} not found")
    return p


@app.get("/api/threshold-curve", tags=["data"])
def get_curve():
    return service.threshold_curve()


@app.post("/api/score", response_model=schemas.ScoreResponse, tags=["screening"])
def score(req: schemas.ScoreRequest, _=Depends(require_api_key)):
    return service.score_window(req.leads, req.threshold)


@app.post("/api/forecast", response_model=schemas.ForecastResponse, tags=["screening"])
def forecast(req: schemas.ForecastRequest, _=Depends(require_api_key)):
    return service.forecast_risks(req.risks, req.threshold, req.horizon)


# --- serve the React UI + data (mounted last so it doesn't shadow the API) --
try:
    app.mount("/", StaticFiles(directory=settings.WEB_DIR, html=True), name="web")
except Exception as e:  # pragma: no cover
    log.warning("static UI not mounted: %s", e)
