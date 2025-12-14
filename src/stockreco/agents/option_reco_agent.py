from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Literal
from math import fabs

from stockreco.ingest.derivatives.provider_base import OptionChainRow, UnderlyingSnapshot

Bias = Literal["BULLISH","BEARISH","NEUTRAL"]
Instrument = Literal["OPTION","FUTURE","NONE"]
Action = Literal["BUY","SELL","HOLD"]
Side = Optional[Literal["CE","PE","FUT"]]

@dataclass
class OptionTargets:
    t1_underlying: float
    t2_underlying: float
    t1_premium: float
    t2_premium: float

@dataclass
class OptionReco:
    as_of: str
    symbol: str
    bias: Bias
    instrument: Instrument
    action: Action
    side: Side = None
    expiry: Optional[str] = None
    strike: Optional[float] = None
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    targets: Optional[OptionTargets] = None
    confidence: float = 0.0
    rationale: Optional[List[str]] = None
    diagnostics: Optional[Dict[str, Any]] = None

class OptionRecoAgent:
    def __init__(
        self,
        risk_free_rate: float = 0.07,
        entry_slippage_pct: float = 0.002,
        stop_loss_premium_factor: float = 0.70,
        default_atr_points: Optional[Dict[str, float]] = None,
        iv_history: Optional[Dict[str, Any]] = None,
        min_direction_score: float = 0.08,  # lowered
        force_trade_on_ret_sign: bool = True,
    ):
        self.risk_free_rate = risk_free_rate
        self.entry_slippage_pct = entry_slippage_pct
        self.stop_loss_premium_factor = stop_loss_premium_factor
        self.default_atr_points = default_atr_points or {}
        self.iv_history = iv_history or {}
        self.min_direction_score = float(min_direction_score)
        self.force_trade_on_ret_sign = bool(force_trade_on_ret_sign)

    def _nearest_expiry(self, chain: List[OptionChainRow]) -> Optional[str]:
        exps = sorted({str(r.expiry) for r in chain if r.expiry and str(r.expiry) != "UNKNOWN"})
        return exps[0] if exps else (str(chain[0].expiry) if chain else None)

    def _step(self, symbol: str) -> float:
        s = symbol.upper().replace(".NS","")
        if s == "NIFTY":
            return 50.0
        if s == "BANKNIFTY":
            return 100.0
        return 10.0

    def _pick_strike(self, chain: List[OptionChainRow], spot: float, cp: str, step: float) -> Optional[OptionChainRow]:
        strikes = sorted({r.strike for r in chain if r.option_type == cp})
        if not strikes:
            return None
        atm = min(strikes, key=lambda k: abs(k - spot))
        target = atm + step if cp == "CE" else atm - step
        pick = min(strikes, key=lambda k: abs(k - target))
        rows = [r for r in chain if r.option_type == cp and float(r.strike) == float(pick)]
        if not rows:
            return None
        rows.sort(key=lambda r: float(r.oi or 0.0), reverse=True)
        return rows[0]

    def recommend(self, as_of: str, symbol: str, signal_row: Dict[str, Any], underlying: UnderlyingSnapshot, chain: List[OptionChainRow]) -> OptionReco:
        buy_win = int(float(signal_row.get("buy_win") or 0))
        sell_win = int(float(signal_row.get("sell_win") or 0))
        buy_soft = float(signal_row.get("buy_soft") or 0.0)
        sell_soft = float(signal_row.get("sell_soft") or 0.0)
        direction_score = signal_row.get("direction_score")
        if direction_score is None:
            direction_score = buy_soft - sell_soft
        direction_score = float(direction_score)

        ret_oc = signal_row.get("ret_oc")
        try:
            ret_oc = float(ret_oc) if ret_oc is not None else 0.0
        except Exception:
            ret_oc = 0.0

        diag = {
            "buy_win": buy_win,
            "sell_win": sell_win,
            "buy_soft": buy_soft,
            "sell_soft": sell_soft,
            "direction_score": direction_score,
            "ret_oc": ret_oc,
        }

        # Decide if actionable
        actionable = (fabs(direction_score) >= self.min_direction_score) or bool(buy_win or sell_win)

        # Fallback: if still weak, use ret_oc sign for a very low confidence next-day bias
        if not actionable and self.force_trade_on_ret_sign and fabs(ret_oc) >= 0.001:
            direction_score = 0.10 if ret_oc > 0 else -0.10
            diag["fallback_ret_bias"] = True
            actionable = True

        if not actionable:
            return OptionReco(
                as_of=as_of, symbol=symbol, bias="NEUTRAL", instrument="NONE", action="HOLD",
                confidence=0.10,
                rationale=["No directional edge and ret_oc too small; skipping trade."],
                diagnostics=diag
            )

        if direction_score > 0 or buy_win:
            bias: Bias = "BULLISH"
            side: Side = "CE"
        else:
            bias = "BEARISH"
            side = "PE"

        exp = self._nearest_expiry(chain)
        spot = float(underlying.spot)
        step = self._step(symbol)
        chain_e = [r for r in chain if (not exp) or str(r.expiry) == str(exp)]

        pick = self._pick_strike(chain_e, spot=spot, cp=side, step=step)
        if pick is None:
            return OptionReco(
                as_of=as_of, symbol=symbol, bias="NEUTRAL", instrument="NONE", action="HOLD",
                confidence=0.10,
                rationale=["Could not pick strike from option chain for computed bias."],
                diagnostics=diag
            )

        entry = float(pick.ltp) * (1.0 + self.entry_slippage_pct)
        sl = float(entry) * float(self.stop_loss_premium_factor)

        atr_points = signal_row.get("atr_points")
        try:
            atr_points = float(atr_points)
        except Exception:
            atr_points = float(self.default_atr_points.get(symbol.upper().replace(".NS",""), 0.0)) or 0.0
        if atr_points <= 0:
            atr_points = spot * 0.008

        if side == "CE":
            t1_u = spot + 0.5 * atr_points
            t2_u = spot + 1.0 * atr_points
        else:
            t1_u = spot - 0.5 * atr_points
            t2_u = spot - 1.0 * atr_points

        # premium targets conservative for next day
        t1_p = entry * 1.25
        t2_p = entry * 1.50

        conf = min(0.75, 0.25 + 0.50 * min(1.0, fabs(direction_score)))
        rationale = [
            f"buy_soft={buy_soft:.2f}, sell_soft={sell_soft:.2f}, direction_score={direction_score:.2f}.",
            f"Selected {side} {pick.strike} exp {exp} using EOD premium as entry proxy.",
            f"Targets from ATR_points≈{atr_points:.0f}: underlying T1/T2; premium T1/T2 multipliers."
        ]

        return OptionReco(
            as_of=as_of, symbol=symbol, bias=bias, instrument="OPTION", action="BUY",
            side=side, expiry=exp, strike=float(pick.strike),
            entry=float(entry), stop_loss=float(sl),
            targets=OptionTargets(
                t1_underlying=float(t1_u),
                t2_underlying=float(t2_u),
                t1_premium=float(t1_p),
                t2_premium=float(t2_p),
            ),
            confidence=float(conf),
            rationale=rationale,
            diagnostics=diag
        )
