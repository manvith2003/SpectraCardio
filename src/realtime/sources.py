"""
sources.py
----------
Pluggable real-time ECG sample SOURCES.

Every source is an iterator that yields one multi-lead sample at a time:
    {"t": <seconds>, "leads": {"V1": float, "V2": float, "V3": float, ...}}

The analyzer consumes this stream and never needs to know whether the samples
came from a file replay, a TCP socket, stdin, or an in-memory array. That single
abstraction is what makes the pipeline "real-time data ready": swap the source,
keep the analysis.

Sources provided:
  - ArraySource    : stream an in-memory (n_samples, n_leads) array (tests/demo)
  - WFDBFileSource : replay a real Brugada-HUCA recording at its true 100 Hz rate
  - SocketSource   : receive a live feed over TCP (one JSON sample per line)
  - StdinSource    : receive a live feed piped on stdin (one JSON sample per line)
"""

import sys
import time
import json
import socket as _socket

FS_DEFAULT = 100  # Hz, per dataset spec


class ArraySource:
    """Stream an in-memory array as if it were arriving live.

    signal : np.ndarray of shape (n_samples, n_leads)
    lead_names : list[str] naming each column
    rate : real-time pacing in Hz (None = as fast as possible)
    loop : if True, restart at the end (simulate a never-ending monitor feed)
    """

    def __init__(self, signal, lead_names, fs=FS_DEFAULT, rate=None, loop=False):
        self.signal = signal
        self.lead_names = list(lead_names)
        self.fs = fs
        self.rate = rate
        self.loop = loop

    def __iter__(self):
        n = self.signal.shape[0]
        i = 0
        t0 = time.time()
        emitted = 0
        while True:
            row = self.signal[i % n]
            yield {"t": emitted / self.fs,
                   "leads": {ln: float(row[j]) for j, ln in enumerate(self.lead_names)}}
            emitted += 1
            i += 1
            if i >= n and not self.loop:
                break
            if self.rate:
                target = t0 + emitted / self.rate
                dt = target - time.time()
                if dt > 0:
                    time.sleep(dt)


class WFDBFileSource:
    """Replay a real Brugada-HUCA recording at (a multiple of) its true rate.

    Reads the full-resolution 12-lead signal via wfdb -- the same loader the
    batch feature extractor uses -- so live features match the trained model.

    speed : 1.0 = real time (12 s recording plays in 12 s); 0 = no delay.
    """

    def __init__(self, record_path, fs=FS_DEFAULT, speed=1.0, loop=False):
        self.record_path = record_path
        self.fs = fs
        self.speed = speed
        self.loop = loop

    def __iter__(self):
        import wfdb  # imported lazily so the rest of the pkg has no hard dep
        rec = wfdb.rdrecord(self.record_path)
        sig = rec.p_signal
        names = rec.sig_name
        rate = (self.fs * self.speed) if self.speed else None
        yield from ArraySource(sig, names, fs=self.fs, rate=rate, loop=self.loop)


class SocketSource:
    """Receive a live feed over TCP. Each line is a JSON sample:
        {"t": 1.23, "leads": {"V1": 0.01, "V2": -0.02, ...}}
    Pair with realtime/replay_sender.py (or a real device that speaks this).
    """

    def __init__(self, host="127.0.0.1", port=9009):
        self.host = host
        self.port = port

    def __iter__(self):
        srv = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        srv.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(1)
        print(f"[SocketSource] waiting for a feed on {self.host}:{self.port} ...")
        conn, addr = srv.accept()
        print(f"[SocketSource] connected: {addr}")
        with conn, conn.makefile("r") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)
        srv.close()


class StdinSource:
    """Receive a live feed piped on stdin (one JSON sample per line)."""

    def __iter__(self):
        for line in sys.stdin:
            line = line.strip()
            if line:
                yield json.loads(line)
