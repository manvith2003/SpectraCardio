"""
analyzer.py
-----------
The real-time analysis engine.

It consumes a live sample stream (from any source in sources.py), keeps a
SLIDING WINDOW of the most recent samples, and every `hop` samples recomputes
the FFT spectral + morphology features on V1-V3 and re-scores Brugada risk.
The result is a continuously-updating risk estimate and a screening flag.

Design choice worth explaining in an interview: the window length defaults to
the full 12 s recording (1200 samples) used to train the model, so the live
feature distribution matches training and the score is comparable. A shorter
window updates more often but drifts from the training distribution -- a
classic real-time vs. fidelity trade-off, exposed here as a CLI flag.

Feature computation is imported from the batch extractor (extract_features.py)
so the streaming path and the batch path are guaranteed identical.
"""

import os
import sys
from collections import deque
import numpy as np

# Reuse the EXACT batch feature functions (single source of truth).
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
from extract_features import bandpass, spectral_features, morphology_features  # noqa: E402

LEADS = ["V1", "V2", "V3"]
FS = 100


class RealTimeAnalyzer:
    def __init__(self, scorer, fs=FS, window_sec=12.0, hop_sec=1.0,
                 threshold=0.10):
        self.scorer = scorer
        self.fs = fs
        self.window = int(window_sec * fs)
        self.hop = int(hop_sec * fs)
        self.threshold = threshold
        self.buffers = {l: deque(maxlen=self.window) for l in LEADS}
        self.samples_since_score = 0
        self.n_samples = 0

    def _features(self):
        """Compute the 42-feature vector on the current window."""
        feats = {}
        for lead in LEADS:
            raw = np.asarray(self.buffers[lead], dtype=float)
            filt = bandpass(raw, fs=self.fs)
            feats.update(spectral_features(filt, fs=self.fs, prefix=f"{lead}_"))
            feats.update(morphology_features(filt, fs=self.fs, prefix=f"{lead}_"))
        return feats

    def push(self, sample):
        """Feed one multi-lead sample. Returns an event dict when a fresh score
        is produced (every `hop` samples once the window is full), else None."""
        leads = sample["leads"]
        for l in LEADS:
            if l in leads:
                self.buffers[l].append(leads[l])
        self.n_samples += 1

        full = len(self.buffers[LEADS[0]]) >= self.window
        if not full:
            return None

        self.samples_since_score += 1
        if self.samples_since_score < self.hop:
            return None
        self.samples_since_score = 0

        feats = self._features()
        risk = self.scorer.predict_proba(feats)
        return {
            "t": sample.get("t", self.n_samples / self.fs),
            "risk": risk,
            "flagged": risk >= self.threshold,
            "window_filled_pct": 100.0,
            "v1_hf_relpower": feats["V1_bpr_hf_15_40"],
            "v1_spec_entropy": feats["V1_spec_entropy"],
        }

    def warmup_pct(self):
        return 100.0 * len(self.buffers[LEADS[0]]) / self.window
