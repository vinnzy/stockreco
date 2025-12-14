from __future__ import annotations
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Query

from stockreco.ingest.derivatives.provider_base import OptionChainRow

router = APIRouter(prefix="/api/options", tags=["options"])

def get_latest_chain_row(option_symbol: str) -> Optional[OptionChainRow]:
    """
    Wire this into your chain cache/store/provider.
    Return latest OptionChainRow for exact option_symbol.
    """
    return None

@router.get("/quotes")
def get_option_quotes(symbols: List[str] = Query(...)) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for s in symbols:
        sym = s.strip().upper()
        row = get_latest_chain_row(sym)
        if not row:
            out[sym] = {"ok": False}
            continue

        out[sym] = {
            "ok": True,
            "ltp": float(getattr(row, "ltp", 0.0) or 0.0),
            "bid": float(getattr(row, "bid", 0.0) or 0.0),
            "ask": float(getattr(row, "ask", 0.0) or 0.0),
            "iv": float(getattr(row, "iv", 0.0) or 0.0),
            "delta": float(getattr(row, "delta", 0.0) or 0.0),
            "gamma": float(getattr(row, "gamma", 0.0) or 0.0),
            "theta": float(getattr(row, "theta", 0.0) or 0.0),
            "vega": float(getattr(row, "vega", 0.0) or 0.0),
        }

    return {"data": out}
