from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Query, HTTPException

router = APIRouter(prefix="/api/options", tags=["options"])

# 15s cache (matches UI polling)
_CACHE_TTL_SEC = 15
_CACHE_TS: float = 0.0
_CACHE: Dict[str, Dict[str, Any]] = {}
_REPO_ROOT: Optional[Path] = None


def set_repo_root(repo_root: Path) -> None:
    """Set the repository root path for finding data files."""
    global _REPO_ROOT
    _REPO_ROOT = repo_root


def _normalize_symbol(s: str) -> str:
    # Your UI sends ADANIENT.NS24FEB262280CE, but exchange symbols often don't include .NS
    return s.strip().upper().replace(".NS", "")


def _latest_derivatives_dir() -> Optional[Path]:
    if not _REPO_ROOT:
        return None
    base = _REPO_ROOT / "data" / "derivatives"
    if not base.exists():
        return None
    
    dates = []
    for d in base.iterdir():
        try:
            datetime.strptime(d.name, "%Y-%m-%d")
            dates.append(d)
        except Exception:
            pass
    
    if not dates:
        return None
    
    dates.sort()
    return dates[-1]


def _read_op_csv(path: Path) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}

    def g(row: Dict[str, str], *keys: str, default: str = "") -> str:
        for k in keys:
            if k in row and row[k] not in (None, ""):
                return row[k]
        return default

    def fnum(x: str, default: float = 0.0) -> float:
        try:
            return float(x)
        except Exception:
            return default

    try:
        with path.open(newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                sym = g(row, "tradingsymbol", "TRADING_SYMBOL", "symbol", "SYMBOL")
                if not sym:
                    continue

                sym = _normalize_symbol(sym)

                out[sym] = {
                    "ok": True,
                    "ltp": round(fnum(g(row, "ltp", "LTP", "lastPrice", "LAST_PRICE")), 2),
                    "bid": round(fnum(g(row, "bid", "BID", "bidprice", "BID_PRICE")), 2),
                    "ask": round(fnum(g(row, "ask", "ASK", "askprice", "ASK_PRICE")), 2),
                    # optional columns (if present in op csv)
                    "iv": round(fnum(g(row, "iv", "IV"), 0.0), 4),
                    "delta": round(fnum(g(row, "delta", "DELTA"), 0.0), 4),
                    "gamma": round(fnum(g(row, "gamma", "GAMMA"), 0.0), 6),
                    "theta": round(fnum(g(row, "theta", "THETA"), 0.0), 6),
                    "vega": round(fnum(g(row, "vega", "VEGA"), 0.0), 6),
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading CSV file {path}: {e}")

    return out


def _refresh_cache_if_needed() -> None:
    global _CACHE_TS, _CACHE
    now = time.time()
    if _CACHE and (now - _CACHE_TS) < _CACHE_TTL_SEC:
        return

    base_dir = _latest_derivatives_dir()
    if not base_dir:
        _CACHE = {}
        _CACHE_TS = now
        return

    files = list(base_dir.glob("op*.csv"))
    if not files:
        _CACHE = {}
        _CACHE_TS = now
        return

    _CACHE = _read_op_csv(files[0])
    _CACHE_TS = now


@router.get("/ltp")
def get_ltp(options: List[str] = Query(..., description="Repeated: ?options=SYM&options=SYM2")):
    try:
        if not _REPO_ROOT:
            raise HTTPException(
                status_code=500, 
                detail="Repository root not initialized. Server configuration error."
            )
        
        _refresh_cache_if_needed()

        out: Dict[str, Dict[str, Any]] = {}
        for raw in options:
            k = _normalize_symbol(raw)
            row = _CACHE.get(k)
            if not row:
                out[k] = {"ok": False, "ltp": None}
            else:
                out[k] = row

        return {"as_of": "live", "data": out}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
