from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from .. import math_utils
from ...ingest.derivatives.provider_base import OptionChainRow

@dataclass
class OiSummary:
    pcr_oi: Optional[float] = None
    pcr_vol: Optional[float] = None
    call_oi: Optional[float] = None
    put_oi: Optional[float] = None

def compute_oi_summary(chain: List[OptionChainRow]) -> OiSummary:
    call_oi = sum([r.oi or 0.0 for r in chain if r.option_type == "CE"])
    put_oi = sum([r.oi or 0.0 for r in chain if r.option_type == "PE"])
    call_vol = sum([r.volume or 0.0 for r in chain if r.option_type == "CE"])
    put_vol = sum([r.volume or 0.0 for r in chain if r.option_type == "PE"])
    pcr_oi = (put_oi / call_oi) if call_oi > 0 else None
    pcr_vol = (put_vol / call_vol) if call_vol > 0 else None
    return OiSummary(pcr_oi=pcr_oi, pcr_vol=pcr_vol, call_oi=call_oi, put_oi=put_oi)
