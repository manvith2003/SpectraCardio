"""
download_data.py
----------------
Downloads the open-access PhysioNet Brugada-HUCA dataset (~18 MB, CC BY-SA 4.0)
into ./data so the pipeline can be reproduced from scratch.

Usage:  python download_data.py
"""
import os
import zipfile
import urllib.request

BASE = "https://physionet.org/files/brugada-huca/1.0.0"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def fetch(fname):
    os.makedirs(DATA, exist_ok=True)
    dest = os.path.join(DATA, fname)
    print(f"Downloading {fname} ...")
    urllib.request.urlretrieve(f"{BASE}/{fname}", dest)
    return dest


def main():
    fetch("metadata.csv")
    zip_path = fetch("files.zip")
    print("Unzipping waveform files ...")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(DATA)
    print(f"Done. Data in {DATA}")


if __name__ == "__main__":
    main()
