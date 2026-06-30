"""API tests via FastAPI TestClient (requires fastapi/httpx; runs in CI/Docker)."""
import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "degraded")
    assert "X-SpectraCardio-Disclaimer" in r.headers


def test_cohort():
    r = client.get("/api/cohort")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == body["brugada"] + body["healthy"]
    assert "disclaimer" in body


def test_patients_limit_validation():
    assert client.get("/api/patients?limit=10").status_code == 200
    assert client.get("/api/patients?limit=99999").status_code == 422


def test_patient_not_found():
    assert client.get("/api/patients/-1").status_code == 404


def test_score_rejects_short_window():
    # validation should reject < 200 samples
    r = client.post("/api/score", json={"leads": {"V1": [0.0], "V2": [0.0], "V3": [0.0]}})
    assert r.status_code == 422


def test_forecast_pre_alert():
    r = client.post("/api/forecast",
                    json={"risks": [0.02, 0.03, 0.05, 0.07, 0.09], "threshold": 0.10})
    assert r.status_code == 200
    body = r.json()
    assert body["pre_alert"] is True
    assert body["forecast"] >= 0.10


@pytest.mark.skipif(pytest.importorskip("scipy", reason="needs scipy") is None, reason="scipy")
def test_score_full_window():
    fs = 100; n = 12 * fs; t = np.arange(n) / fs
    sig = (0.6 * np.sin(2 * np.pi * 1.2 * t) + 0.2 * np.sin(2 * np.pi * 12 * t)).tolist()
    r = client.post("/api/score", json={"leads": {"V1": sig, "V2": sig, "V3": sig}})
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["risk_score"] <= 1.0
    assert "disclaimer" in body and len(body["top_features"]) == 5
