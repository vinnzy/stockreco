from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import math

@dataclass
class IvSummary:
    atm_iv: Optional[float] = None          # decimal
    iv_percentile: Optional[float] = None   # 0..100 (simple percentile vs history)

def percentile_of_score(history: List[float], x: float) -> float:
    if not history:
        return float("nan")
    s = sorted(history)
    # proportion <= x
    count = 0
    for v in s:
        if v <= x:
            count += 1
    return 100.0 * count / len(s)

def compute_iv_summary(atm_iv: Optional[float], iv_history: List[float]) -> IvSummary:
    if atm_iv is None:
        return IvSummary(None, None)
    hist = [v for v in iv_history if v is not None and not math.isnan(v) and v > 0]
    if not hist:
        return IvSummary(atm_iv, None)
    return IvSummary(atm_iv=atm_iv, iv_percentile=percentile_of_score(hist, atm_iv))
