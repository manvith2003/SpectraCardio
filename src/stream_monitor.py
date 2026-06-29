"""
stream_monitor.py
-----------------
Real-time ECG triage simulation.

Hospitals don't get all their ECGs at once -- recordings arrive one patient at
a time. This script REPLAYS the cohort as a live data stream: each patient's
recording "arrives", the screening model's risk score is read, and the monitor
decides in real time whether to raise a triage flag for clinician review. It
keeps a running tally of how the screen is performing as the stream advances.

The scores replayed here are the genuine out-of-fold scores from the stratified
5-fold cross-validation in train_model.py (saved in outputs/patient_scores.csv),
so every number the monitor reports is honest -- no patient is scored by a model
that was trained on it.

This demonstrates streaming / event-driven data handling, online metric
tracking, and threshold-based alerting on top of the batch analysis pipeline.

Usage:
    python src/stream_monitor.py                  # default screening threshold 0.10
    python src/stream_monitor.py --threshold 0.20 # stricter (fewer false alarms)
    python src/stream_monitor.py --rate 0.0       # no delay (instant replay)
    python src/stream_monitor.py --rate 0.15      # ~0.15s between patients (demo feel)
    python src/stream_monitor.py --shuffle        # randomize arrival order

NOTE: analytical screening demonstration on a research dataset -- NOT a
diagnostic tool.
"""

import os
import csv
import time
import argparse
import random

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(_ROOT, "outputs")
SCORES = os.path.join(OUT_DIR, "patient_scores.csv")
STREAM_LOG = os.path.join(OUT_DIR, "stream_log.csv")


def load_stream():
    """Read the per-patient out-of-fold scores as the incoming 'feed'."""
    rows = []
    with open(SCORES, newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "patient_id": r["patient_id"],
                "brugada": int(r["brugada"]),
                "sudden_death": int(r["sudden_death"]),
                "risk_score": float(r["risk_score"]),
            })
    return rows


def main():
    ap = argparse.ArgumentParser(description="Real-time ECG triage simulation.")
    ap.add_argument("--threshold", type=float, default=0.10,
                    help="Risk score at/above which a patient is flagged for review "
                         "(default 0.10 = screening-oriented, high recall).")
    ap.add_argument("--rate", type=float, default=0.04,
                    help="Seconds to wait between patients (simulated arrival rate).")
    ap.add_argument("--shuffle", action="store_true",
                    help="Randomize arrival order instead of risk-sorted order.")
    args = ap.parse_args()

    stream = load_stream()
    if args.shuffle:
        random.shuffle(stream)

    total_pos = sum(p["brugada"] for p in stream)

    # Running counters updated as each patient 'arrives'.
    n = tp = fp = fn = tn = 0
    log_rows = []

    print("=" * 72)
    print(" SpectraCardio  |  REAL-TIME ECG TRIAGE MONITOR (simulation)")
    print(f" Screening threshold: risk >= {args.threshold:.2f}  ->  FLAG for review")
    print("=" * 72)
    print(f"{'#':>4} {'patient':>10} {'risk':>6}  {'decision':<12} {'truth':<9} outcome")
    print("-" * 72)

    for p in stream:
        n += 1
        flagged = p["risk_score"] >= args.threshold
        is_pos = p["brugada"] == 1

        if flagged and is_pos:
            tp += 1; outcome = "TRUE ALERT"
        elif flagged and not is_pos:
            fp += 1; outcome = "false alarm"
        elif not flagged and is_pos:
            fn += 1; outcome = "** MISSED **"
        else:
            tn += 1; outcome = "clear"

        decision = "FLAG" if flagged else "clear"
        truth = "Brugada" if is_pos else "healthy"
        scd = "  (SCD history)" if p["sudden_death"] == 1 and is_pos else ""

        print(f"{n:>4} {p['patient_id']:>10} {p['risk_score']:>6.3f}  "
              f"{decision:<12} {truth:<9} {outcome}{scd}")

        log_rows.append({
            "arrival_index": n, "patient_id": p["patient_id"],
            "risk_score": round(p["risk_score"], 4), "flagged": int(flagged),
            "brugada": p["brugada"], "outcome": outcome.strip("* ").lower(),
            "running_recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
            "running_flag_rate": round((tp + fp) / n, 4),
        })

        if args.rate > 0:
            time.sleep(args.rate)

    # Final running-screen report.
    recall = tp / total_pos if total_pos else 0.0
    healthy = tn + fp
    fpr = fp / healthy if healthy else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    flagged_total = tp + fp

    print("-" * 72)
    print(" STREAM COMPLETE -- triage summary")
    print(f"   Patients streamed     : {n}")
    print(f"   Flagged for review    : {flagged_total}  ({flagged_total / n:.0%} of feed)")
    print(f"   Brugada caught (recall): {tp}/{total_pos}  ({recall:.1%})")
    print(f"   Brugada missed         : {fn}")
    print(f"   False alarms           : {fp}/{healthy} healthy  (FPR {fpr:.1%})")
    print(f"   Precision of the flag  : {precision:.1%}")
    print("=" * 72)
    print(" Read-out: a low threshold maximizes recall (catch the dangerous cases)")
    print(" at the cost of more false alarms -- the right trade for a first-pass")
    print(" screen that hands a short, enriched review list to a cardiologist.")

    with open(STREAM_LOG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
        w.writeheader(); w.writerows(log_rows)
    print(f"\n Per-patient stream log saved -> {STREAM_LOG}")


if __name__ == "__main__":
    main()
