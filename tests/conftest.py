"""Pytest path setup so `api`, `src`, and `src/realtime` modules import cleanly."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "src"), os.path.join(ROOT, "src", "realtime")):
    if p not in sys.path:
        sys.path.insert(0, p)
