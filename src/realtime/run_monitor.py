"""
run_monitor.py
--------------
Run the real-time Brugada screen on ANY live source.

    # Replay a real recording at true 100 Hz (needs `python download_data.py` first)
    python src/realtime/run_monitor.py --source wfdb --record 188981 --speed 4

    # Receive a live feed over TCP (start this first, then run replay_sender.py)
    python src/realtime/run_monitor.py --source socket --port 9009

    # Receive a live feed piped on stdin
    cat feed.jsonl | python src/realtime/run_monitor.py --source stdin

It prints a continuously-updating risk line and fires an alert when the live
score crosses the screening threshold, then logs every score to
outputs/realtime_log.csv.

NOTE: analytical screening demonstration on a research dataset -- NOT a
diagnostic tool.
"""

import os
import sys
import csv
import argparse

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from realtime.sources import WFDBFileSource, SocketSource, StdinSource
from realtime.analyzer import RealTimeAnalyzer
from realtime.scoring import load_scorer
from realtime.forecaster import RiskForecaster

OUT_DIR = os.path.join(_ROOT, "outputs")
DATA_DIR = os.path.join(_ROOT, "data")


def build_source(args):
    if args.source == "wfdb":
        rec = args.record
        # Accept either a full path or a bare patient id under data/files/<id>/<id>
        if not os.path.sep in str(rec):
            rec = os.path.join(DATA_DIR, "files", str(rec), str(rec))
        return WFDBFileSource(rec, speed=args.speed, loop=args.loop)
    if args.source == "socket":
        return SocketSource(host=args.host, port=args.port)
    if args.source == "stdin":
        return StdinSource()
    raise ValueError(args.source)


def main():
    ap = argparse.ArgumentParser(description="Real-time ECG Brugada screen.")
    ap.add_argument("--source", choices=["wfdb", "socket", "stdin"], default="wfdb")
    ap.add_argument("--record", default="188981", help="patient id or WFDB path (wfdb source)")
    ap.add_argument("--speed", type=float, default=4.0, help="replay speed multiple (wfdb)")
    ap.add_argument("--loop", action="store_true", help="loop the recording forever")
    ap.add_argument("--window", type=float, default=12.0, help="analysis window (seconds)")
    ap.add_argument("--hop", type=float, default=1.0, help="re-score every N seconds")
    ap.add_argument("--threshold", type=float, default=0.10, help="flag threshold")
    ap.add_argument("--forecast-horizon", type=int, default=4,
                    help="steps (x hop) to forecast ahead for the early-warning pre-alert")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9009)
    args = ap.parse_args()

    scorer = load_scorer()
    analyzer = RealTimeAnalyzer(scorer, window_sec=args.window,
                                hop_sec=args.hop, threshold=args.threshold)
    forecaster = RiskForecaster(hop_sec=args.hop)
    H = args.forecast_horizon
    source = build_source(args)

    print("=" * 70)
    print(" SpectraCardio  |  REAL-TIME ECG ANALYZER + EARLY-WARNING FORECAST")
    print(f" window {args.window:.0f}s | rescore every {args.hop:.0f}s | "
          f"flag risk>={args.threshold:.2f} | forecast {H*args.hop:.0f}s ahead")
    print("=" * 70)

    log_path = os.path.join(OUT_DIR, "realtime_log.csv")
    log_rows = []
    last_warm = -1
    alerted = False
    pre_alerted = False

    for sample in source:
        # Show a warm-up progress line until the window fills.
        if analyzer.warmup_pct() < 100:
            w = int(analyzer.warmup_pct())
            if w != last_warm and w % 10 == 0:
                print(f"  buffering window... {w}%", end="\r", flush=True)
                last_warm = w

        ev = analyzer.push(sample)
        if ev is None:
            continue

        # update the early-warning forecaster with the new score
        forecaster.update(ev["risk"])
        fcast = forecaster.forecast(H)
        warn = forecaster.pre_alert(args.threshold, H)

        bar = "#" * int(ev["risk"] * 30)
        status = "FLAG" if ev["flagged"] else ("WARN" if warn else "  ok")
        print(f"  t={ev['t']:6.1f}s  risk={ev['risk']:.3f} [{bar:<30}] {status}   "
              f"fcast({H*args.hop:.0f}s)={fcast:.3f} slope={forecaster.slope_per_sec():+.3f}/s",
              flush=True)

        if warn and not ev["flagged"] and not pre_alerted:
            lt = warn["lead_time_sec"]
            lt_s = f"~{lt:.0f}s" if lt is not None else "imminent"
            print(f"  >>> PRE-ALERT: risk trending up, projected to cross "
                  f"{args.threshold:.2f} in {lt_s} (forecast {fcast:.2f}) <<<", flush=True)
            pre_alerted = True

        if ev["flagged"] and not alerted:
            print(f"  >>> ALERT: risk crossed {args.threshold:.2f} at t={ev['t']:.1f}s "
                  f"-- flag for clinician review <<<", flush=True)
            alerted = True

        log_rows.append({"t": round(ev["t"], 2), "risk": round(ev["risk"], 4),
                         "forecast": round(fcast, 4),
                         "slope_per_sec": round(forecaster.slope_per_sec(), 4),
                         "pre_alert": int(bool(warn)),
                         "flagged": int(ev["flagged"]),
                         "v1_hf_relpower": round(ev["v1_hf_relpower"], 4),
                         "v1_spec_entropy": round(ev["v1_spec_entropy"], 3)})

    if log_rows:
        with open(log_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
            w.writeheader(); w.writerows(log_rows)
        final = log_rows[-1]
        print("-" * 70)
        print(f" stream ended | last risk {final['risk']:.3f} | "
              f"{sum(r['flagged'] for r in log_rows)}/{len(log_rows)} windows flagged")
        print(f" live log saved -> {log_path}")


if __name__ == "__main__":
    main()
