"""Tests for the NumPy logistic fallback scorer (numpy + pandas only)."""
import os
import numpy as np
import pandas as pd
from scoring import LogisticScorer, feature_order

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_logistic_separates_classes():
    sc = LogisticScorer()
    cols = feature_order()
    df = pd.read_csv(os.path.join(ROOT, "outputs", "features.csv"))
    probs = np.array([sc.predict_proba(dict(zip(cols, row)))
                      for row in df[cols].to_numpy()])
    y = df["brugada"].to_numpy()
    # mean probability should be clearly higher for true Brugada cases
    assert probs[y == 1].mean() > probs[y == 0].mean() + 0.2
    # all probabilities are valid
    assert probs.min() >= 0.0 and probs.max() <= 1.0


def test_feature_order_excludes_meta():
    cols = feature_order()
    for meta in ("patient_id", "brugada", "sudden_death", "basal_pattern"):
        assert meta not in cols
    assert len(cols) == 42
