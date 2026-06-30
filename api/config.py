"""
config.py — runtime configuration via environment variables.

Twelve-factor style: every setting has a safe default and can be overridden with
an env var, so the same image runs in dev, staging, and prod without code changes.
"""

import os

_API_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_API_DIR)


def _envbool(name, default=False):
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "on")


class Settings:
    # paths
    ROOT = ROOT
    OUTPUTS = os.getenv("SC_OUTPUTS", os.path.join(ROOT, "outputs"))
    MODEL_PATH = os.getenv("SC_MODEL_PATH", os.path.join(ROOT, "outputs", "rf_model.joblib"))
    WEB_DIR = os.getenv("SC_WEB_DIR", ROOT)  # serves index.html + outputs/

    # service
    APP_NAME = "SpectraCardio API"
    VERSION = "1.0.0"
    LOG_LEVEL = os.getenv("SC_LOG_LEVEL", "INFO").upper()

    # screening defaults
    DEFAULT_THRESHOLD = float(os.getenv("SC_THRESHOLD", "0.10"))
    WINDOW_SEC = float(os.getenv("SC_WINDOW_SEC", "12"))
    FS = int(os.getenv("SC_FS", "100"))
    FORECAST_HORIZON = int(os.getenv("SC_FORECAST_HORIZON", "4"))

    # security
    API_KEY = os.getenv("SC_API_KEY", "")            # if set, required on protected routes
    ALLOW_ORIGINS = os.getenv("SC_ALLOW_ORIGINS", "*").split(",")

    DISCLAIMER = (
        "RESEARCH / EDUCATIONAL DEMONSTRATION ONLY. Not a medical device, not "
        "clinically validated, and not for diagnosis or any patient-care decision. "
        "Outputs are screening-aid scores on a public research dataset."
    )


settings = Settings()
