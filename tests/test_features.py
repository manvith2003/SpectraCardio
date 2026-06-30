"""Tests for windowed feature extraction (requires scipy; runs in CI/Docker)."""
import os
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scipy = pytest.importorskip("scipy")  # skip locally if scipy isn't installed


def test_features_match_training_columns():
    from api import service
    from scoring import feature_order
    fs = 100
    n = 12 * fs
    t = np.arange(n) / fs
    sig = 0.6 * np.sin(2 * np.pi * 1.2 * t) + 0.2 * np.sin(2 * np.pi * 12 * t)
    leads = {"V1": sig.tolist(), "V2": sig.tolist(), "V3": sig.tolist()}
    feats = service.features_from_window(leads)
    assert set(feats.keys()) == set(feature_order())
    assert len(feats) == 42
