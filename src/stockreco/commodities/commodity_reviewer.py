from __future__ import annotations
from typing import List, Dict, Any, Tuple

class CommodityReviewer:
    """
    Reviewer for MCX Commodity/Option recommendations.
    Filters based on:
    - Minimum Confidence
    - Minimum Volume
    - Risk/Reward Sanity
    """
    
    def __init__(self, min_confidence: float = 0.60, min_volume: int = 5):
        self.min_confidence = min_confidence
        self.min_volume = min_volume

    def review(self, recos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        approved = []
        for r in recos:
            if self._check(r):
                approved.append(r)
        return approved

    def _check(self, r: Dict[str, Any]) -> bool:
        # 1. Skip HOLDs (unless we want to report them?)
        # Let's filter out HOLDs from final report usually, or keep them if high confidence (unlikely)
        if r.get("action") == "HOLD":
            return False

        # 2. Confidence Check
        conf = float(r.get("confidence", 0.0))
        if conf < self.min_confidence:
            return False

        # 3. Volume Check
        diag = r.get("diagnostics", {})
        vol = diag.get("volume_lots", 0)
        if vol < self.min_volume:
            return False

        # 4. Target > Entry Check (Sanity)
        entry = r.get("entry_price")
        t1 = r.get("t1")
        if entry and t1:
            if r["action"] == "BUY" and t1 <= entry:
                return False
            if r["action"] == "SELL" and t1 >= entry:
                return False
        
        return True
