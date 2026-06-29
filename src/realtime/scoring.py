"""
scoring.py
----------
Pluggable scorers that map a 42-feature window vector to a Brugada risk score.

  RFModelScorer  : loads the trained Random Forest (outputs/rf_model.joblib) -
                   the project's real model. Requires scikit-learn + joblib.
  LogisticScorer : a transparent, dependency-light logistic-regression fallback
                   trained on outputs/features.csv with NumPy only. Used when the
                   RF model / sklearn isn't available, and for testing. It is a
                   weaker but honest stand-in (clearly labelled at runtime).

Both expose .predict_proba(feature_dict) -> float in [0, 1] and read the feature
column ORDER from features.csv so the vector always matches how the model was
trained (meta columns patient_id / basal_pattern / sudden_death / brugada excluded).
"""

import os
import numpy as np
import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(_ROOT, "outputs")
META_COLS = ["patient_id", "basal_pattern", "sudden_death", "brugada"]


def feature_order():
    """The exact feature-column order used to train the model."""
    head = pd.read_csv(os.path.join(OUT_DIR, "features.csv"), nrows=1)
    return [c for c in head.columns if c not in META_COLS]


def vector_from_dict(feat_dict, cols):
    return np.array([feat_dict[c] for c in cols], dtype=float)


class RFModelScorer:
    """Wraps the trained Random Forest saved by train_model.py."""

    name = "RandomForest (trained model)"

    def __init__(self, model_path=None):
        import joblib  # lazy
        self.cols = feature_order()
        self.model = joblib.load(model_path or os.path.join(OUT_DIR, "rf_model.joblib"))

    def predict_proba(self, feat_dict):
        x = vector_from_dict(feat_dict, self.cols).reshape(1, -1)
        return float(self.model.predict_proba(x)[0, 1])


class LogisticScorer:
    """NumPy-only standardized logistic regression, fit on features.csv.

    Class-weighted gradient descent so the rare Brugada class isn't ignored
    (mirrors the batch model's class_weight='balanced' intent).
    """

    name = "Logistic (NumPy fallback)"

    def __init__(self, l2=1.0, iters=4000, lr=0.5, seed=42):
        self.cols = feature_order()
        df = pd.read_csv(os.path.join(OUT_DIR, "features.csv"))
        X = df[self.cols].to_numpy(float)
        y = df["brugada"].to_numpy(float)

        # Standardize (store stats to apply at inference time).
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0) + 1e-9
        Xs = (X - self.mu) / self.sd

        # Class weights (balanced).
        n = len(y); npos = y.sum(); nneg = n - npos
        w = np.where(y == 1, n / (2 * npos), n / (2 * nneg))

        rng = np.random.default_rng(seed)
        d = Xs.shape[1]
        self.beta = np.zeros(d)
        self.b = 0.0
        for _ in range(iters):
            z = Xs @ self.beta + self.b
            p = 1 / (1 + np.exp(-z))
            g = (p - y) * w
            grad_beta = Xs.T @ g / n + l2 * self.beta / n
            grad_b = g.mean()
            self.beta -= lr * grad_beta
            self.b -= lr * grad_b

    def predict_proba(self, feat_dict):
        x = vector_from_dict(feat_dict, self.cols)
        xs = (x - self.mu) / self.sd
        z = xs @ self.beta + self.b
        return float(1 / (1 + np.exp(-z)))


def load_scorer(prefer_rf=True):
    """Return the best available scorer, announcing which one is active."""
    if prefer_rf and os.path.exists(os.path.join(OUT_DIR, "rf_model.joblib")):
        try:
            s = RFModelScorer()
            print(f"[scorer] {s.name}")
            return s
        except Exception as e:
            print(f"[scorer] RF unavailable ({e}); using fallback.")
    s = LogisticScorer()
    print(f"[scorer] {s.name} -- run train_model.py to enable the Random Forest.")
    return s
