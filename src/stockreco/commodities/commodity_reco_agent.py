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
    - Picks nearest expiry per symbol for Trend (FUTCOM).
    - If mapped to a liquid Option (OPTFUT/OPTCOM), recommends BUY CE (if Bullish) or BUY PE (if Bearish).
    - If no liquid option found, recommends Future.
    
    Logic:
    1. Determine Trend from Liquid Future (BUY/SELL).
    2. If Bullish -> Look for CE, if Bearish -> Look for PE.
    3. Option Criteria:
       - Expiry: Nearest monthly expiry (up to max_days).
       - Strike: ATM (closest to Future Price).
       - Liquidity: Must have some volume/OI.
    4. Levels:
       - Entry: Option LTP
       - SL: 30% below Entry (approx risk management for options)
       - Target: 50% above Entry
    """

    def __init__(self, cfg: Optional[CommodityRecoConfig] = None):
        self.cfg = cfg or CommodityRecoConfig()

    def recommend_from_bhavcopy_rows(self, as_of: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        a = datetime.strptime(as_of, "%Y-%m-%d")

        # 1. Parse Futures and Options
        fut_candidates = []
        # options_map: symbol -> expiry(date) -> strike(float) -> type(CE/PE) -> row
        options_map: Dict[str, Dict[datetime, Dict[float, Dict[str, Any]]]] = {}

        for r in rows:
            inst = _sym(r.get("Instrument Name"))
            sym = _sym(r.get("Symbol"))
            exp = _parse_expiry(r.get("Expiry Date"))
            
            if not sym or not exp:
                continue

            dte = (exp.date() - a.date()).days
            if dte < 0 or dte > self.cfg.max_days_to_expiry:
                continue

            if inst == "FUTCOM":
                vol = _fnum(r.get("Volume(Lots)")) or 0.0
                if vol >= self.cfg.min_volume_lots:
                    fut_candidates.append((sym, exp, dte, r))
            
            elif inst in ("OPTFUT", "OPTCOM"):
                # "16 Dec 2025","OPTFUT","GOLDM        ","29DEC2025","CE","133100.00",...
                opt_type = _clean(r.get("Option Type")).upper() # CE/PE
                strike = _fnum(r.get("Strike Price"))
                
                if not opt_type or strike is None:
                    continue
                
                if sym not in options_map:
                    options_map[sym] = {}
                if exp not in options_map[sym]:
                    options_map[sym][exp] = {}
                if strike not in options_map[sym][exp]:
                    options_map[sym][exp][strike] = {}
                
                options_map[sym][exp][strike][opt_type] = r

        # 2. Determine Trend from Nearest Liquid Future
        best_fut: Dict[str, tuple] = {}
        for sym, exp, dte, r in fut_candidates:
            cur = best_fut.get(sym)
            if cur is None or dte < cur[2]:
                best_fut[sym] = (sym, exp, dte, r)

        out: List[Dict[str, Any]] = []

        for sym, fut_exp, fut_dte, fut_row in sorted(best_fut.values(), key=lambda x: x[0]):
            # -- Analyze Future Trend --
            close = _fnum(fut_row.get("Close")) or 0.0
            prev = _fnum(fut_row.get("Previous Close")) or 0.0
            
            if close <= 0 or prev <= 0:
                continue

            trend = "HOLD"
            if close > prev:
                trend = "BUY"
            elif close < prev:
                trend = "SELL"
            
            if trend == "HOLD":
                continue

            # -- Attempt to find Option Trade --
            # We want to BUY Options.
            # Bullish -> Buy CE
            # Bearish -> Buy PE
            
            target_opt_type = "CE" if trend == "BUY" else "PE"
            
            # Find best option expiry (nearest valid)
            # We prefer the same expiry as future, or nearest available in options map
            opt_chain = options_map.get(sym, {})
            if not opt_chain:
                # No options found, skip options logic, maybe fallback?
                # For now let's just skip reporting if user specifically asked for options
                # But to maintain utility, we can report Future if no option.
                # However, user explicitly asked for Options. Let's try to report Future as fallback.
                self._add_entry(out, as_of, sym, fut_row, trend, "FUTCOM", fut_exp, 0.0, "")
                continue

            # Find valid option expiry with data
            valid_expiries = sorted(opt_chain.keys())
            
            # Pick nearest expiry that has data
            picked_exp = None
            if valid_expiries:
                picked_exp = valid_expiries[0] # Nearest
            
            if not picked_exp:
                 self._add_entry(out, as_of, sym, fut_row, trend, "FUTCOM", fut_exp, 0.0, "")
                 continue

            straddle_map = opt_chain[picked_exp]
            
            # Pick ATM Strike
            # Future Price is reference
            fut_price = close
            
            best_k = None
            min_dist = float("inf")
            
            available_strikes = sorted(straddle_map.keys())
            
            for k in available_strikes:
                dist = abs(k - fut_price)
                if dist < min_dist:
                    min_dist = dist
                    best_k = k
            
            if best_k is None:
                 self._add_entry(out, as_of, sym, fut_row, trend, "FUTCOM", fut_exp, 0.0, "")
                 continue

            # Check if specific option exists
            opt_row = straddle_map[best_k].get(target_opt_type)
            if not opt_row:
                 self._add_entry(out, as_of, sym, fut_row, trend, "FUTCOM", fut_exp, 0.0, "")
                 continue

            # Use Option Row to generate signal
            # Always BUY the option (Long CE or Long PE)
            self._add_entry(out, as_of, sym, opt_row, "BUY", "OPTFUT", picked_exp, best_k, target_opt_type)

        return out

    def _add_entry(self, out: List, as_of: str, sym: str, r: Dict, action: str, 
                   inst_repl: str, exp: datetime, strike: float, opt_type: str):
        
        close = _fnum(r.get("Close")) or 0.0
        prev = _fnum(r.get("Previous Close")) or 0.0
        hi = _fnum(r.get("High")) or close
        lo = _fnum(r.get("Low")) or close
        vol_lots = _fnum(r.get("Volume(Lots)")) or 0.0
        oi_lots = _fnum(r.get("Open Interest(Lots)")) or 0.0
        
        if close <= 0:
            return

        day_range = max(1e-6, hi - lo)
        move = abs(close - prev)
        
        # Risk Management defaults for Options vs Futures
        if inst_repl in ("OPTFUT", "OPTCOM"):
            # Option Logic: Long only
            entry = close
            # Stop Loss: 30% of Premium or Low of day?
            # Using 30% of premium is standard for buying options
            sl = entry * 0.70
            risk = entry - sl
            t1 = entry + (risk * 1.5) # 1.5R
            t2 = entry + (risk * 3.0) # 3R
        else:
            # Futures Logic
            entry = close
            if action == "BUY":
                sl = entry - max(entry * self.cfg.stop_loss_frac * 0.01, 0.5 * day_range) # 1% SL or half range
                risk = max(0.01, entry - sl)
                t1 = entry + risk * 1.5
                t2 = entry + risk * 3.0
            else: # SELL
                sl = entry + max(entry * 0.01, 0.5 * day_range)
                risk = max(0.01, sl - entry)
                t1 = entry - risk * 1.5
                t2 = entry - risk * 3.0

        # Sell By
        sell_by = None
        try:
             sb = _add_trading_days(datetime.strptime(as_of, "%Y-%m-%d"), self.cfg.sell_by_trading_days)
             sell_by = sb.strftime("%Y-%m-%d")
        except:
            pass
        
        # Confidence Tuning
        conf = 0.50
        
        if vol_lots > 1000: conf += 0.15
        elif vol_lots > 100: conf += 0.10
        elif vol_lots > 10: conf += 0.05
        
        if oi_lots > 500: conf += 0.10
        elif oi_lots > 50: conf += 0.05
        
        if day_range > 0 and move/day_range > 0.6:
             conf += 0.05
             
        conf = min(0.90, conf)
        
        exp_str = exp.strftime("%d-%b-%Y").upper()
        # Compact expiry for display: 29-DEC
        exp_short = exp.strftime("%d-%b").upper()
        dte = (exp.date() - datetime.strptime(as_of, "%Y-%m-%d").date()).days
        
        display_name = ""
        if inst_repl in ("OPTFUT", "OPTCOM"):
            # Format: GOLDM 132600 CE (29-DEC)
            display_name = f"{sym} {int(strike) if strike.is_integer() else strike} {opt_type} ({exp_short})"
        else:
            display_name = f"{sym} FUT ({exp_short})"

        out.append({
            "as_of": as_of,
            "exchange": "MCX",
            "instrument": inst_repl,
            "symbol": sym,
            "display_name": display_name,
            "expiry": exp_str,
            "dte": int(dte),
            "action": action, # Always BUY for options
            "option_type": opt_type,
            "strike_price": strike,
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
                "volume_lots": float(vol_lots),
                "oi_lots": float(oi_lots),
            }
        })

