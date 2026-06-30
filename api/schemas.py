"""
schemas.py — Pydantic request/response models (validation + auto OpenAPI docs).
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ScoreRequest(BaseModel):
    """Score a single ECG window. Provide V1–V3 sample arrays (≥ a few seconds
    at 100 Hz; the full 12 s window is recommended to match training)."""
    leads: Dict[str, List[float]] = Field(
        ..., description="Map of lead name -> samples, must include V1, V2, V3",
        json_schema_extra={"example": {"V1": [0.01, -0.02], "V2": [0.0], "V3": [0.0]}})
    threshold: Optional[float] = Field(None, ge=0.0, le=1.0)

    @field_validator("leads")
    @classmethod
    def _need_precordial(cls, v):
        missing = [l for l in ("V1", "V2", "V3") if l not in v]
        if missing:
            raise ValueError(f"missing required leads: {missing}")
        for l in ("V1", "V2", "V3"):
            if len(v[l]) < 200:
                raise ValueError(f"lead {l} needs >=200 samples (>=2 s at 100 Hz)")
        return v


class FeatureContribution(BaseModel):
    feature: str
    importance: float


class ScoreResponse(BaseModel):
    risk_score: float
    flagged: bool
    threshold: float
    top_features: List[FeatureContribution]
    scorer: str
    disclaimer: str


class ForecastRequest(BaseModel):
    """Forecast the next risk values from a recent risk history."""
    risks: List[float] = Field(..., min_length=2,
                               description="recent risk scores in time order")
    threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    horizon: Optional[int] = Field(None, ge=1, le=60)


class ForecastResponse(BaseModel):
    forecast: float
    slope_per_step: float
    pre_alert: bool
    lead_time_steps: Optional[float]
    threshold: int | float
    disclaimer: str


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    scorer: str
    model_loaded: bool


class CohortResponse(BaseModel):
    total: int
    brugada: int
    healthy: int
    roc_auc: float
    disclaimer: str
