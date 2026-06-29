"""
replay_sender.py
----------------
A PRODUCER that streams ECG samples to the analyzer over TCP -- the stand-in
for a real ECG device / hospital feed. It demonstrates the pluggable live-input
path: run_monitor.py (with --source socket) is the consumer/server; this is the
client that pushes samples to it.

    # terminal 1 (consumer):
    python src/realtime/run_monitor.py --source socket --port 9009

    # terminal 2 (this producer):
    python src/realtime/replay_sender.py --record 188981 --speed 4
    #   ...or stream synthetic samples to test the wiring with no data download:
    python src/realtime/replay_sender.py --synthetic --speed 50

In production you would replace this script with the real device adapter; the
wire format is one JSON object per line:
    {"t": 1.23, "leads": {"V1": 0.01, "V2": -0.02, "V3": 0.0, ...}}
"""

import os
import sys
import json
import time
import socket
import argparse
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(_ROOT, "data")
FS = 100
LEADS = ["V1", "V2", "V3"]


def synthetic_signal(seconds=20, fs=FS):
    """A crude ECG-like signal (sum of harmonics + noise) just to exercise the
    pipe end-to-end without downloading data. NOT clinically meaningful."""
    n = int(seconds * fs)
    t = np.arange(n) / fs
    rng = np.random.default_rng(0)
    base = 0.6 * np.sin(2 * np.pi * 1.2 * t) + 0.2 * np.sin(2 * np.pi * 12 * t)
    sig = np.stack([base + 0.05 * rng.standard_normal(n) for _ in LEADS], axis=1)
    return sig, LEADS


def wfdb_signal(record):
    import wfdb
    if os.path.sep not in str(record):
        record = os.path.join(DATA_DIR, "files", str(record), str(record))
    rec = wfdb.rdrecord(record)
    return rec.p_signal, rec.sig_name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default="188981")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9009)
    ap.add_argument("--speed", type=float, default=4.0, help="x real-time")
    args = ap.parse_args()

    if args.synthetic:
        sig, names = synthetic_signal()
    else:
        sig, names = wfdb_signal(args.record)

    rate = FS * args.speed
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((args.host, args.port))
    print(f"[sender] streaming {sig.shape[0]} samples ({len(names)} leads) "
          f"to {args.host}:{args.port} at {args.speed}x")
    t0 = time.time()
    with s.makefile("w") as f:
        for i, row in enumerate(sig):
            msg = {"t": i / FS, "leads": {n: float(v) for n, v in zip(names, row)}}
            f.write(json.dumps(msg) + "\n")
            f.flush()
            target = t0 + (i + 1) / rate
            dt = target - time.time()
            if dt > 0:
                time.sleep(dt)
    s.close()
    print("[sender] done.")


if __name__ == "__main__":
    main()
