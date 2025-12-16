from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def _clean(x: Any) -> str:
    # handles BOM, quotes, weird whitespace
    s = str(x or "")
    s = s.replace("\ufeff", "").replace('"', "").strip()
    return s


def _sym(x: Any) -> str:
    return _clean(x).upper()


def _fnum(x: Any) -> Optional[float]:
    try:
        s = _clean(x)
        if not s:
            return None
        s = s.replace(",", "")
        return float(s)
    except Exception:
        return None


def _f2(x: Any) -> Optional[float]:
    v = _fnum(x)
    if v is None:
        return None
    return float(f"{v:.2f}")


def _parse_expiry(x: Any) -> Optional[datetime]:
    """
    MCX bhavcopy commonly has:
      31DEC2025
      31-DEC-2025
      31 Dec 2025
      2025-12-31
    """
    s = _clean(x).upper()
    if not s:
        return None

    for fmt in ("%d%b%Y", "%d-%b-%Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def _add_trading_days(d: datetime, n: int) -> datetime:
    """
    Adds N trading days (skips Sat/Sun).
    """
    cur = d
    added = 0
    while added < n:
        cur = cur + timedelta(days=1)
        if cur.weekday() < 5:  # Mon..Fri
            added += 1
    return cur


@dataclass
class CommodityRecoConfig:
    stop_loss_frac: float = 0.35
    t1_rr: float = 1.25
    t2_rr: float = 2.25
    min_volume_lots: float = 1.0
    max_days_to_expiry: int = 180
    sell_by_trading_days: int = 2


class CommodityRecoAgent:
    """
    Rule-based starter from MCX FUTCOM bhavcopy:
    - Picks nearest expiry per symbol
    - BUY if Close > PrevClose, SELL if Close < PrevClose, else HOLD
    - SL/Targets from risk multiples
    - sell_by uses trading days (no Sat/Sun), capped at expiry-1 trading day
    - confidence varies with (move vs range) and volume/oi
    """

    def __init__(self, cfg: Optional[CommodityRecoConfig] = None):
        self.cfg = cfg or CommodityRecoConfig()

    def recommend_from_bhavcopy_rows(self, as_of: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        a = datetime.strptime(as_of, "%Y-%m-%d")

        fut = []
        for r in rows:
            inst = _sym(r.get("Instrument Name"))
            if inst != "FUTCOM":
                continue

            sym = _sym(r.get("Symbol"))
            exp = _parse_expiry(r.get("Expiry Date"))
            if not sym or not exp:
                continue

            dte = (exp.date() - a.date()).days
            if dte < 0 or dte > self.cfg.max_days_to_expiry:
                continue

            vol = _fnum(r.get("Volume(Lots)")) or 0.0
            if vol < self.cfg.min_volume_lots:
                continue

            fut.append((sym, exp, dte, r))

        # nearest expiry per symbol
        best: Dict[str, tuple] = {}
        for sym, exp, dte, r in fut:
            cur = best.get(sym)
            if cur is None or dte < cur[2]:
                best[sym] = (sym, exp, dte, r)

        out: List[Dict[str, Any]] = []
        for sym, exp, dte, r in sorted(best.values(), key=lambda x: x[0]):
            close = _fnum(r.get("Close")) or 0.0
            prev = _fnum(r.get("Previous Close")) or 0.0
            hi = _fnum(r.get("High")) or close
            lo = _fnum(r.get("Low")) or close

            if close <= 0 or prev <= 0:
                action = "HOLD"
            elif close > prev:
                action = "BUY"
            elif close < prev:
                action = "SELL"
            else:
                action = "HOLD"

            day_range = max(1e-6, hi - lo)
            move = abs(close - prev)

            entry = close
            sl = t1 = t2 = None

            if action == "BUY":
                sl = entry - max(entry * self.cfg.stop_loss_frac, 0.5 * day_range)
                risk = max(0.01, entry - sl)
                t1 = entry + self.cfg.t1_rr * risk
                t2 = entry + self.cfg.t2_rr * risk
            elif action == "SELL":
                # NOTE: for SELL, SL is ABOVE entry (that is correct for a short)
                sl = entry + max(entry * self.cfg.stop_loss_frac, 0.5 * day_range)
                risk = max(0.01, sl - entry)
                t1 = entry - self.cfg.t1_rr * risk
                t2 = entry - self.cfg.t2_rr * risk

            # sell_by = as_of + N trading days (skip weekends), cap at expiry-1 day (also trading-day-ish)
            sell_by = None
            try:
                sb = _add_trading_days(a, self.cfg.sell_by_trading_days)

                # cap to expiry - 1 calendar day, then if weekend, roll back to Friday
                cap = datetime.combine(exp.date() - timedelta(days=1), datetime.min.time())
                if cap.weekday() >= 5:
                    cap = cap - timedelta(days=(cap.weekday() - 4))  # Sat->Fri(1), Sun->Fri(2)

                if sb > cap:
                    sb = cap
                if sb < a:
                    sb = a
                sell_by = sb.strftime("%Y-%m-%d")
            except Exception:
                pass

            # confidence (varies):
            # - base: HOLD 0.15, trade 0.30
            # - boost by "move vs range"
            # - tiny boost by volume/oi (log scaled)
            vol_lots = _fnum(r.get("Volume(Lots)")) or 0.0
            oi_lots = _fnum(r.get("Open Interest(Lots)")) or 0.0

            if action == "HOLD":
                conf = 0.15
            else:
                strength = min(1.0, move / day_range)  # 0..1
                liq = min(1.0, (0.15 * (0.0 if vol_lots <= 0 else (1.0 + (vol_lots ** 0.25))) +
                                0.10 * (0.0 if oi_lots <= 0 else (1.0 + (oi_lots ** 0.25)))) / 10.0)
                conf = 0.30 + 0.45 * strength + 0.10 * liq
                conf = max(0.25, min(0.85, conf))

            out.append({
                "as_of": as_of,
                "exchange": "MCX",
                "instrument": "FUTCOM",
                "symbol": sym,
                "expiry": exp.strftime("%d-%b-%Y").upper(),
                "dte": int(dte),
                "action": action,
                "ltp": _f2(close),
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
                    "move": _f2(move),
                    "day_range": _f2(day_range),
                    "volume_lots": float(vol_lots),
                    "oi_lots": float(oi_lots),
                }
            })

        return out
