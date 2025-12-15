from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional



def _as_ymd(as_of: str) -> datetime:
    return datetime.strptime(as_of, "%Y-%m-%d")


def _parse_bhav_date(s: str) -> Optional[datetime]:
    # "12 Dec 2025"
    try:
        return datetime.strptime(str(s).strip(), "%d %b %Y")
    except Exception:
        return None


def _parse_expiry(s: str) -> Optional[datetime]:
    # "27FEB2026"
    try:
        return datetime.strptime(str(s).strip().upper(), "%d%b%Y")
    except Exception:
        return None


def _sym(s: str) -> str:
    return str(s or "").strip().upper()


def _f2(x: Any) -> Optional[float]:
    try:
        v = float(x)
        return float(f"{v:.2f}")
    except Exception:
        return None
def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def _confidence_from_signal(
    action: str,
    close: float,
    prev: float,
    hi: float,
    lo: float,
    vol_lots: float,
    oi_lots: float,
) -> float:
    """
    Builds a 0..1 confidence score from:
      - absolute return vs prev close
      - intraday range vs prev close
      - liquidity proxy: volume lots
      - interest proxy: OI lots

    Tuned for bhavcopy-scale numbers; clamps to sane bounds.
    """
    if action == "HOLD":
        # still vary a bit based on liquidity/range so not all 12%
        base = 0.12
    else:
        base = 0.22

    if prev <= 0:
        return base

    ret = abs((close - prev) / prev)          # e.g. 0.01 = 1%
    rng = abs((hi - lo) / prev) if prev > 0 else 0.0

    # Normalize into 0..1 bands (you can tune these)
    a = _clamp(ret / 0.012, 0.0, 1.0)         # 1.2% move => strong
    b = _clamp(rng / 0.020, 0.0, 1.0)         # 2.0% range => strong
    c = _clamp((vol_lots or 0.0) / 5000.0, 0.0, 1.0)
    d = _clamp((oi_lots or 0.0) / 5000.0, 0.0, 1.0)

    # Weighted blend
    conf = base + 0.34 * a + 0.22 * b + 0.14 * c + 0.08 * d

    # Penalize ultra-low liquidity
    if (vol_lots or 0.0) < 50:
        conf *= 0.80
    if (oi_lots or 0.0) < 50:
        conf *= 0.90

    # Final clamp
    lo_bound = 0.12 if action == "HOLD" else 0.20
    hi_bound = 0.80
    return _clamp(conf, lo_bound, hi_bound)


@dataclass
class CommodityRecoConfig:
    stop_loss_frac: float = 0.35     # similar to options premium SL%
    t1_rr: float = 1.25
    t2_rr: float = 2.25
    min_volume_lots: float = 1.0     # filter dead contracts
    max_days_to_expiry: int = 180    # ignore far contracts
    sell_by_days: int = 2            # default timebox


class CommodityRecoAgent:
    """
    Rule-based starter:
    - Uses BhavCopyDateWise FUTCOM rows.
    - Picks nearest expiry per symbol.
    - BUY if Close > PrevClose, SELL if Close < PrevClose, HOLD if flat.
    - Targets from risk multiple; Sell-by capped at expiry-1.
    """
    def __init__(self, cfg: Optional[CommodityRecoConfig] = None):
        self.cfg = cfg or CommodityRecoConfig()

    def recommend_from_bhavcopy_rows(self, as_of: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        a = _as_ymd(as_of)

        # Keep only FUTCOM rows and valid expiries
        fut = []
        for r in rows:
            if _sym(r.get("Instrument Name")) != "FUTCOM":
                continue
            sym = _sym(r.get("Symbol"))
            exp = _parse_expiry(r.get("Expiry Date"))
            if not sym or not exp:
                continue

            dte = (exp.date() - a.date()).days
            if dte < 0:
                continue
            if dte > self.cfg.max_days_to_expiry:
                continue

            vol = float(r.get("Volume(Lots)") or 0.0)
            if vol < self.cfg.min_volume_lots:
                continue

            fut.append((sym, exp, dte, r))

        # Pick nearest expiry per symbol
        best: Dict[str, tuple] = {}
        for sym, exp, dte, r in fut:
            cur = best.get(sym)
            if cur is None or dte < cur[2]:
                best[sym] = (sym, exp, dte, r)

        out: List[Dict[str, Any]] = []
        for sym, exp, dte, r in sorted(best.values(), key=lambda x: x[0]):
            close = float(r.get("Close") or 0.0)
            prev = float(r.get("Previous Close") or 0.0)
            hi = float(r.get("High") or close)
            lo = float(r.get("Low") or close)

            if close <= 0 or prev <= 0:
                action = "HOLD"
            elif close > prev:
                action = "BUY"
            elif close < prev:
                action = "SELL"
            else:
                action = "HOLD"

            # crude volatility proxy
            day_range = max(1e-9, hi - lo)

            entry = close
            if action == "BUY":
                sl = entry - max(entry * self.cfg.stop_loss_frac, 0.5 * day_range)
                risk = max(0.01, entry - sl)
                t1 = entry + self.cfg.t1_rr * risk
                t2 = entry + self.cfg.t2_rr * risk
            elif action == "SELL":
                sl = entry + max(entry * self.cfg.stop_loss_frac, 0.5 * day_range)
                risk = max(0.01, sl - entry)
                t1 = entry - self.cfg.t1_rr * risk
                t2 = entry - self.cfg.t2_rr * risk
            else:
                sl = None
                t1 = None
                t2 = None

            # sell_by: as_of + N days (cap at expiry-1)
            sell_by = None
            try:
                sb = a + timedelta(days=self.cfg.sell_by_days)
                cap = datetime.combine(exp.date() - timedelta(days=1), datetime.min.time())
                if sb > cap:
                    sb = cap
                if sb < a:
                    sb = a
                sell_by = sb.strftime("%Y-%m-%d")
            except Exception:
                pass

            vol_lots = float(r.get("Volume(Lots)") or 0.0)
            oi_lots = float(r.get("Open Interest(Lots)") or 0.0)

            conf = _confidence_from_signal(
                action=action,
                close=close,
                prev=prev,
                hi=hi,
                lo=lo,
                vol_lots=vol_lots,
                oi_lots=oi_lots,
            )


            out.append({
                "as_of": as_of,
                "exchange": "MCX",
                "instrument": "FUTCOM",
                "symbol": sym,
                "expiry": exp.strftime("%d-%b-%Y").upper(),
                "dte": int(dte),
                "action": action,
                "ltp": _f2(close),             # bhavcopy close as LTP proxy
                "entry_price": _f2(entry),
                "sl": _f2(sl),
                "t1": _f2(t1),
                "t2": _f2(t2),
                "sell_by": sell_by,
                "confidence": float(f"{conf:.2f}"),
                "diagnostics": {
                    "high": _f2(hi),
                    "low": _f2(lo),
                    "prev_close": _f2(prev),
                    "volume_lots": float(r.get("Volume(Lots)") or 0.0),
                    "oi_lots": float(r.get("Open Interest(Lots)") or 0.0),
                }
            })

        return out
