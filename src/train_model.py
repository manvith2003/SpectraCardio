"""
train_model.py
--------------
Supervised Brugada-vs-healthy classifier on the FFT + morphology features.

Because the cohort is imbalanced (69 Brugada / 287 healthy ~ 19% positive),
accuracy is a misleading metric: a model that always predicts "healthy"
scores ~81%. We therefore report RECALL, PRECISION and F1 on the Brugada
class, plus ROC-AUC, all under stratified 5-fold cross-validation so every
patient is evaluated out-of-fold. Class weighting handles the imbalance.

Catching the rare-but-fatal positive case is the clinical priority, so recall
on the Brugada class is the headline number.

NOTE: analytical screening demonstration on a research dataset -- NOT a
diagnostic tool.
"""

import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import (classification_report, confusion_matrix,
                             roc_auc_score, recall_score, precision_score,
                             f1_score)

OUT_DIR = os.path.join(_ROOT, "outputs")


def load_xy():
    df = pd.read_csv(os.path.join(OUT_DIR, "features.csv"))
    meta_cols = ["patient_id", "basal_pattern", "sudden_death", "brugada"]
    feat_cols = [c for c in df.columns if c not in meta_cols]
    X = df[feat_cols].values
    y = df["brugada"].values
    return df, X, y, feat_cols


def evaluate(name, clf, X, y):
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    proba = cross_val_predict(clf, X, y, cv=cv, method="predict_proba")[:, 1]
    pred = (proba >= 0.5).astype(int)
    print(f"\n===== {name} (5-fold stratified CV, out-of-fold) =====")
    print(f"  Brugada-class RECALL    : {recall_score(y, pred):.3f}")
    print(f"  Brugada-class PRECISION : {precision_score(y, pred):.3f}")
    print(f"  Brugada-class F1        : {f1_score(y, pred):.3f}")
    print(f"  ROC-AUC                 : {roc_auc_score(y, proba):.3f}")
    print(f"  Confusion matrix [tn fp / fn tp]:")
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    print(f"      healthy: {tn:3d} correct, {fp:3d} false alarms")
    print(f"      brugada: {tp:3d} caught,  {fn:3d} MISSED")
    return proba, pred


def main():
    df, X, y, feat_cols = load_xy()
    print(f"Loaded {len(y)} patients | {y.sum()} Brugada / {(y==0).sum()} healthy")

    logit = Pipeline([("sc", StandardScaler()),
                      ("clf", LogisticRegression(max_iter=2000,
                                                 class_weight="balanced"))])
    rf = RandomForestClassifier(n_estimators=400, class_weight="balanced",
                                random_state=42, n_jobs=-1)

    evaluate("Logistic Regression", logit, X, y)
    proba, pred = evaluate("Random Forest", rf, X, y)

    # Fit RF on all data for the dashboard + feature importances
    rf.fit(X, y)
    importances = pd.DataFrame({"feature": feat_cols,
                                "importance": rf.feature_importances_}
                               ).sort_values("importance", ascending=False)
    importances.to_csv(os.path.join(OUT_DIR, "feature_importance.csv"), index=False)
    print("\nTop 10 features driving the model:")
    print(importances.head(10).to_string(index=False))

    # Save per-patient out-of-fold scores for the dashboard triage view
    df_out = df[["patient_id", "brugada", "sudden_death"]].copy()
    df_out["risk_score"] = proba
    df_out["flagged"] = pred
    df_out.sort_values("risk_score", ascending=False).to_csv(
        os.path.join(OUT_DIR, "patient_scores.csv"), index=False)
    joblib.dump(rf, os.path.join(OUT_DIR, "rf_model.joblib"))
    print(f"\nSaved model + patient scores -> {OUT_DIR}")


if __name__ == "__main__":
    main()
