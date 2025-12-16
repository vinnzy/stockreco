from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import math

from stockreco.ingest.derivatives.provider_base import OptionChainRow, UnderlyingSnapshot, normalize_to_nse_symbol
from stockreco.options.greeks import implied_vol, bs_greeks, intrinsic_extrinsic
from stockreco.options.risk import delta_based_sl

# Re-use some helpers from the main agent if possible, or redefine for independence
# To keep independence, we redefine essentials here.

def _parse_expiry(exp: str) -> Optional[datetime]:
    if not exp:
        return None
    try:
        return datetime.strptime(str(exp).strip(), "%d-%b-%Y")
    except Exception:
        try:
            return datetime.strptime(str(exp).strip(), "%Y-%m-%d")
        except Exception:
            return None

def _days_to_expiry(as_of: str, expiry: str) -> Optional[int]:
    a = datetime.strptime(as_of, "%Y-%m-%d")
    e = _parse_expiry(expiry)
    if not e:
        return None
    return max(0, (e.date() - a.date()).days)

def _round2(x: Optional[float]) -> Optional[float]:
    if x is None: return None
    return float(f"{float(x):.2f}")

@dataclass
class IntradayOptionReco:
    as_of: str
    symbol: str
    bias: str
    instrument: str
    action: str
    side: str
    expiry: str
    strike: float
    entry_price: float
    sl_premium: float
    targets: List[Dict[str, float]]
    confidence: float
    rationale: List[str]
    diagnostics: Dict[str, Any]
    
    # Extra fields for UI
    spot: float
    delta: Optional[float] = None
    iv: Optional[float] = None
    dte: Optional[int] = None
    sell_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "symbol": self.symbol,
            "bias": self.bias,
            "instrument": self.instrument,
            "action": self.action,
            "side": self.side,
            "expiry": self.expiry,
            "strike": self.strike,
            "entry_price": self.entry_price,
            "sl_premium": self.sl_premium,
            "targets": self.targets,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "diagnostics": self.diagnostics,
            "spot": self.spot,
            "delta": self.delta,
            "iv": self.iv,
            "dte": self.dte,
            "sell_by": self.sell_by,
        }

class IntradayOptionAgent:
    """
    Agent specifically for generating Intraday Option Buy recommendations
    targeting > 15% quick profit on the next day.
    """
    def __init__(self):
        # Configuration hardcoded for this specific task
        self.min_profit_pct = 0.15
        self.risk_reward_min = 1.8  # Stricter risk reward (User: "do not lose money")
        self.min_confidence = 0.60
        self.min_dte = 2
        self.max_dte = 30
        
    def recommend(
        self,
        as_of: str,
        symbol: str,
        signal_row: Dict[str, Any],
        underlying: UnderlyingSnapshot,
        chain: List[OptionChainRow],
    ) -> Optional[IntradayOptionReco]:
        
        s = normalize_to_nse_symbol(symbol)
        spot = float(getattr(underlying, "spot", None) or 0.0)
        if spot <= 0:
            return None

        # 1. Determine Bias
        buy_win = int(signal_row.get("buy_win", 0) or 0)
        sell_win = int(signal_row.get("sell_win", 0) or 0)
        direction_score = float(signal_row.get("direction_score", 0.0) or 0.0)
        
        # Stricter directional requirement for intraday "quick profit"
        if direction_score > 0.20 or (buy_win > sell_win and direction_score > 0.1):
            side = "CE"
            bias = "BULLISH"
        elif direction_score < -0.20 or (sell_win > buy_win and direction_score < -0.1):
            side = "PE"
            bias = "BEARISH"
        else:
            return None # No strong bias
            
        # 2. Filter Chain
        candidates = []
        for r in chain:
            if (r.option_type or "").upper() != side: continue
            dte = _days_to_expiry(as_of, r.expiry)
            if dte is None or dte < self.min_dte or dte > self.max_dte: continue
            
            # Liq check
            if (r.oi or 0) < 500: continue
            
            candidates.append((r, dte))
            
        if not candidates:
            return None
            
        # 3. Select Best Strike
        atr_points = float(signal_row.get("atr_points", 0.0) or (spot * 0.01))
        
        scored_candidates = []
        for r, dte in candidates:
            strike = float(r.strike)
            ltp = float(r.ltp or 0)
            if ltp <= 0: continue
            
            # Distance from spot
            if side == "CE":
                moneyness = (spot - strike) / spot # +ve = ITM
            else:
                moneyness = (strike - spot) / spot # +ve = ITM
                
            # Prefer slightly ITM (0% to 3%) or ATM.
            score = 0
            if -0.01 <= moneyness <= 0.04:
                score += 10
            elif -0.05 <= moneyness < -0.01:
                score += 5 
            else:
                score += 0 
                
            # Liquid
            if (r.oi or 0) > 10000: score += 2
             
            scored_candidates.append((r, dte, score))
            
        scored_candidates.sort(key=lambda x: x[2], reverse=True)
        if not scored_candidates:
            return None
            
        best_row, best_dte, best_score = scored_candidates[0]
        
        # 4. Calculate Targets & SL
        entry = float(best_row.ltp)
        strike = float(best_row.strike)
        
        # Target: > 15%
        # User: "bit more leash" -> allow volatility, so maybe wider SL than typical scalping
        # But "do not lose money" -> strong RR.
        # Let's target +15% and +30%.
        
        target1 = entry * (1.0 + self.min_profit_pct)
        target2 = entry * (1.0 + (self.min_profit_pct * 2))
        
        # SL logic:
        # User implies strict timeline but wiggle room.
        # Let's set SL based on Technicals (ATR-based on premium?) or Delta-based?
        # Simpler: Use 1:2 RR.
        # Rew = 15%. Risk = 7.5%.
        sl_pct = self.min_profit_pct / 2.0 
        stop_loss = entry * (1.0 - sl_pct)
        
        rr_ratio = (target1 - entry) / (entry - stop_loss)
        
        # Greeks for diagnostics
        T = max(1e-6, best_dte / 365.0)
        iv = implied_vol(entry, spot, strike, T, 0.07, side)
        g = bs_greeks(spot, strike, T, 0.07, iv, side) if iv else None
        
        # Confidence Tuning
        # Base: 0.4. Max 0.9.
        # Direction score contribution
        # score=0.2 -> +0.2. score=0.4 -> +0.4.
        conf = 0.4 + abs(direction_score)
        if best_score < 10: conf -= 0.1
        if best_dte < 5: conf -= 0.1 # Theta risk
        
        conf = min(0.90, max(0.1, conf))
        
        if conf < self.min_confidence:
            return None
            
        # Stricter Timeline: Sell By T+1 (End of tomorrow)
        # Assuming as_of is T0.
        try:
             as_of_dt = datetime.strptime(as_of, "%Y-%m-%d")
             sell_by_dt = as_of_dt + timedelta(days=1)
             sell_by = sell_by_dt.strftime("%Y-%m-%d")
        except:
             sell_by = None

        rationale = [
            f"Directional Score {direction_score:.2f} ({bias})",
            f"Intraday Setup: Buy {side} {strike} @ {entry}",
            f"Targets: {target1:.2f} (15%) / {target2:.2f} (30%)",
            f"Stop Loss: {stop_loss:.2f} ({sl_pct*100:.1f}%)",
            f"Sell-By: {sell_by} (Strict T+1 Exit)"
        ]
        
        diagnostics = {
                "direction_score": direction_score,
                "moneyness_score": best_score,
                "iv": iv,
                "rr_ratio": float(f"{rr_ratio:.2f}")
        }
        
        return IntradayOptionReco(
            as_of=as_of,
            symbol=s,
            bias=bias,
            instrument="OPTION",
            action="BUY",
            side=side,
            expiry=best_row.expiry,
            strike=strike,
            entry_price=_round2(entry),
            sl_premium=_round2(stop_loss),
            targets=[
                {"premium": _round2(target1)},
                {"premium": _round2(target2)}
            ],
            confidence=_round2(conf),
            rationale=rationale,
            diagnostics=diagnostics,
            spot=_round2(spot),
            delta=_round2(g.delta if g else None),
            iv=_round2(iv*100) if iv else None,
            dte=best_dte,
            sell_by=sell_by
        )
