from __future__ import annotations
import math

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def safe_float(x, default=None):
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default
