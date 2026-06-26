"""
extract_features.py
--------------------
Brugada syndrome ECG screening - feature extraction stage.

For each patient recording in the Brugada-HUCA dataset, this script:
  1. Loads the 12-lead ECG and isolates the precordial leads V1-V3
     (where the Brugada coved-type ST elevation lives).
  2. Applies a 0.5-40 Hz band-pass filter (baseline-wander + high-freq noise removal).
  3. Extracts FFT-based spectral features + simple time-domain morphology features.
  4. Writes a tidy feature table to CSV (consumed next by the SQL loader).

The spectral-feature approach is grounded in the dataset authors' own prior
finding that spectral analysis of the ECG improves Brugada prediction
(Garcia-Iglesias et al., J Clin Med 2019).

NOTE: This is an analytical screening demonstration on a research dataset.
It is NOT a diagnostic tool and must not be used for medical decisions.
"""

import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import wfdb
from scipy import signal as sp
from scipy.fft import rfft, rfftfreq
from scipy.stats import entropy as scipy_entropy

DATA_DIR = os.path.join(_ROOT, "data")
OUT_DIR = os.path.join(_ROOT, "outputs")
FS = 100  # sampling frequency (Hz), per dataset spec
LEADS = ["V1", "V2", "V3"]

# Frequency bands (Hz) for band-power features.
BANDS = {
    "lf_0p5_5": (0.5, 5),     # ST / T-wave morphology
    "mf_5_15": (5, 15),       # QRS bulk
    "hf_15_40": (15, 40),     # high-freq content (RBBB-like differences show here)
}


def bandpass(x, lo=0.5, hi=40, fs=FS, order=3):
    b, a = sp.butter(order, [lo / (fs / 2), hi / (fs / 2)], btype="band")
    return sp.filtfilt(b, a, x, axis=0)


def spectral_features(sig, fs=FS, prefix=""):
    """FFT-based features for a single 1-D signal."""
    s = (sig - sig.mean()) / (sig.std() + 1e-8)
    Y = np.abs(rfft(s))
    f = rfftfreq(len(s), 1 / fs)
    psd = Y ** 2
    total = psd.sum() + 1e-12

    feats = {}
    # Band powers (absolute + relative)
    for name, (lo, hi) in BANDS.items():
        mask = (f >= lo) & (f < hi)
        bp = psd[mask].sum()
        feats[f"{prefix}bp_{name}"] = bp
        feats[f"{prefix}bpr_{name}"] = bp / total

    # Dominant frequency and spectral centroid
    feats[f"{prefix}dom_freq"] = f[np.argmax(psd)]
    feats[f"{prefix}centroid"] = (f * psd).sum() / total
    # Spectral entropy (flatness of the spectrum)
    p = psd / total
    feats[f"{prefix}spec_entropy"] = scipy_entropy(p + 1e-12)
    # Spectral edge frequency (95% of energy below this)
    cumE = np.cumsum(psd) / total
    feats[f"{prefix}edge95"] = f[np.searchsorted(cumE, 0.95)]
    return feats


def morphology_features(sig, fs=FS, prefix=""):
    """Simple time-domain morphology features for a single 1-D lead."""
    feats = {}
    feats[f"{prefix}rms"] = float(np.sqrt(np.mean(sig ** 2)))
    feats[f"{prefix}ptp"] = float(np.ptp(sig))          # peak-to-peak amplitude
    feats[f"{prefix}std"] = float(np.std(sig))
    # crude R-peak count -> heart-rate proxy
    peaks, _ = sp.find_peaks(sig, distance=int(0.3 * fs),
                             height=np.std(sig) * 1.5)
    feats[f"{prefix}n_peaks"] = len(peaks)
    return feats


def process_patient(pid):
    rec = wfdb.rdrecord(os.path.join(DATA_DIR, "files", str(pid), str(pid)))
    idx = [rec.sig_name.index(l) for l in LEADS]
    raw = rec.p_signal[:, idx]                 # (1200, 3)
    filt = bandpass(raw)
    row = {"patient_id": pid}
    for j, lead in enumerate(LEADS):
        col = filt[:, j]
        row.update(spectral_features(col, prefix=f"{lead}_"))
        row.update(morphology_features(col, prefix=f"{lead}_"))
    return row


def main():
    meta = pd.read_csv(os.path.join(DATA_DIR, "metadata.csv"))
    # keep only clean binary labels
    meta = meta[meta["brugada"].isin([0, 1])].copy()
    rows, failed = [], 0
    for pid in meta["patient_id"]:
        try:
            rows.append(process_patient(pid))
        except Exception as e:
            failed += 1
    feats = pd.DataFrame(rows)
    df = meta.merge(feats, on="patient_id", how="inner")
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "features.csv")
    df.to_csv(out, index=False)
    print(f"Extracted features for {len(df)} patients "
          f"({(df.brugada==1).sum()} Brugada, {(df.brugada==0).sum()} healthy); "
          f"{failed} failed.")
    print(f"Feature columns: {df.shape[1]-4} features")
    print(f"Saved -> {out}")


if __name__ == "__main__":
    main()
