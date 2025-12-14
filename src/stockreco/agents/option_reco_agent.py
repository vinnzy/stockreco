from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple, Literal
from datetime import datetime, timedelta
import math

from stockreco.ingest.derivatives.provider_base import OptionChainRow, UnderlyingSnapshot, normalize_to_nse_symbol
from stockreco.options.greeks import implied_vol, bs_greeks, intrinsic_extrinsic
from stockreco.options.risk import delta_based_sl

Mode = Literal["strict", "opportunistic", "speculative"]

_EXP_FMT = "%d-%b-%Y"


def _parse_expiry(exp: str) -> Optional[datetime]:
    if not exp:
        return None
    exp = str(exp).strip()
    # allow "06-JAN-2026" etc
    try:
        return datetime.strptime(exp, _EXP_FMT)
    except Exception:
        # already ISO?
        try:
            return datetime.strptime(exp, "%Y-%m-%d")
        except Exception:
            return None


def _days_to_expiry(as_of: str, expiry: str) -> Optional[int]:
    a = datetime.strptime(as_of, "%Y-%m-%d")
    e = _parse_expiry(expiry)
    if not e:
        return None
    return max(0, (e.date() - a.date()).days)


def _round2(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(f"{float(x):.2f}")
    except Exception:
        return None


def _median_step(strikes: List[float]) -> float:
    s = sorted({float(x) for x in strikes if x is not None})
    if len(s) < 2:
        return 1.0
    diffs = [abs(s[i + 1] - s[i]) for i in range(len(s) - 1) if abs(s[i + 1] - s[i]) > 0]
    if not diffs:
        return 1.0
    diffs.sort()
    return diffs[len(diffs) // 2]


def _round_to_step(x: float, step: float) -> float:
    if step <= 0:
        return x
    return round(x / step) * step


@dataclass
class OptionReco:
    as_of: str
    symbol: str
    bias: str
    instrument: str
    action: str  # BUY / SELL / HOLD
    side: Optional[str] = None  # CE / PE
    expiry: Optional[str] = None
    strike: Optional[float] = None
    entry_price: Optional[float] = None
    sl_premium: Optional[float] = None
    sl_invalidation: Optional[float] = None
    targets: Optional[List[Dict[str, float]]] = None
    confidence: float = 0.0
    rationale: Optional[List[str]] = None
    diagnostics: Optional[Dict[str, Any]] = None

    # extra analytics (for UI)
    spot: Optional[float] = None
    ltp: Optional[float] = None
    iv: Optional[float] = None
    dte: Optional[int] = None
    theta_per_day: Optional[float] = None
    delta: Optional[float] = None
    extrinsic: Optional[float] = None
    sell_by: Optional[str] = None
    breakeven: Optional[float] = None

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
            "sl_invalidation": self.sl_invalidation,
            "targets": self.targets,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "diagnostics": self.diagnostics,
            "spot": self.spot,
            "ltp": self.ltp,
            "iv": self.iv,
            "dte": self.dte,
            "theta_per_day": self.theta_per_day,
            "delta": self.delta,
            "extrinsic": self.extrinsic,
            "sell_by": self.sell_by,
            "breakeven": self.breakeven,
        }


@dataclass
class OptionRecoConfig:
    # NEW: mode controls strict/opportunistic/speculative thresholds
    mode: Mode = "strict"

    # expiry selection
    min_dte: int = 5  # avoid 0-4 DTE theta cliff (strict)
    max_dte: int = 45  # avoid far months by default

    # selection
    max_moneyness_atr: float = 1.2  # allow strikes within +/- 1.2 ATR
    min_oi: float = 0.0
    min_volume: float = 0.0

    # pricing/targets
    entry_slippage_frac: float = 0.03  # ask a slightly better entry than LTP
    stop_loss_frac: float = 0.35  # SL on premium
    t1_rr: float = 1.25  # reward multiple vs risk
    t2_rr: float = 2.25

    # IV/theta heuristics
    r_rate: float = 0.07
    theta_sell_by_budget_frac: float = 0.45  # max allowed theta burn vs extrinsic

    # NEW: directional thresholds (per mode; defaults tuned for NSE options)
    strict_min_dir: float = 0.15
    opp_min_dir: float = 0.08
    spec_min_dir: float = 0.05

    # NEW: allow range trade suggestions when direction is unclear but expansion likely
    strict_min_range_atr_pct: float = 0.012
    opp_min_range_atr_pct: float = 0.010
    spec_min_range_atr_pct: float = 0.008

    # NEW: confidence floors (avoid “0%”)
    conf_floor_hold: float = 0.12
    conf_floor_trade_strict: float = 0.35
    conf_floor_trade_opp: float = 0.28
    conf_floor_trade_spec: float = 0.22

    # NEW: opportunistic can dip into nearer expiries but still avoid 0DTE
    opp_min_dte: int = 2
    spec_min_dte: int = 1


class OptionRecoAgent:
    def __init__(self, cfg: Optional[OptionRecoConfig] = None):
        self.cfg = cfg or OptionRecoConfig()

    def _min_dir(self) -> float:
        if self.cfg.mode == "opportunistic":
            return self.cfg.opp_min_dir
        if self.cfg.mode == "speculative":
            return self.cfg.spec_min_dir
        return self.cfg.strict_min_dir

    def _min_dte(self) -> int:
        if self.cfg.mode == "opportunistic":
            return min(self.cfg.min_dte, self.cfg.opp_min_dte)
        if self.cfg.mode == "speculative":
            return min(self.cfg.min_dte, self.cfg.spec_min_dte)
        return self.cfg.min_dte

    def _min_range_atr_pct(self) -> float:
        if self.cfg.mode == "opportunistic":
            return self.cfg.opp_min_range_atr_pct
        if self.cfg.mode == "speculative":
            return self.cfg.spec_min_range_atr_pct
        return self.cfg.strict_min_range_atr_pct

    def _sell_by_fallback(self, as_of: str, expiry: str) -> Optional[str]:
        """
        Simple sell-by if greeks unavailable:
        - DTE<=2 -> same day
        - DTE<=5 -> +1 day
        - else   -> +2 days
        capped at expiry-1
        """
        a = datetime.strptime(as_of, "%Y-%m-%d")
        e = _parse_expiry(expiry)
        if not e:
            return None
        dte = max(0, (e.date() - a.date()).days)

        if dte <= 2:
            sb = a
        elif dte <= 5:
            sb = a + timedelta(days=1)
        else:
            sb = a + timedelta(days=2)

        cap = datetime.combine((e.date() - timedelta(days=1)), datetime.min.time())
        if sb > cap:
            sb = cap
        if sb < a:
            sb = a
        return sb.strftime("%Y-%m-%d")

    def _range_trade_suggestion(
        self,
        as_of: str,
        symbol: str,
        spot: float,
        atr_points: float,
        atr_pct: float,
        chain: List[OptionChainRow],
    ) -> Optional[Dict[str, Any]]:
        if not chain:
            return None

        # choose nearest expiry with at least min_dte
        min_dte = self._min_dte()
        expiries = sorted({r.expiry for r in chain if r.expiry})
        best_exp = None
        best_dte = None
        for exp in expiries:
            dte = _days_to_expiry(as_of, exp)
            if dte is None:
                continue
            if dte >= min_dte:
                best_exp, best_dte = exp, dte
                break
        if not best_exp:
            best_exp = expiries[0]
            best_dte = _days_to_expiry(as_of, best_exp) or None

        strikes = [float(r.strike) for r in chain if r.expiry == best_exp and r.strike is not None]
        step = _median_step(strikes)
        atm = _round_to_step(spot, step)
        wing = max(step, _round_to_step(0.5 * atr_points, step))
        low_k = atm - wing
        high_k = atm + wing

        sell_by = self._sell_by_fallback(as_of, best_exp)

        return {
            "type": "RANGE",
            "mode": self.cfg.mode,
            "expiry": best_exp,
            "dte": best_dte,
            "spot": _round2(spot),
            "atr_points": _round2(atr_points),
            "atr_pct": float(f"{atr_pct:.4f}"),
            "primary": {
                "strategy": "LONG_STRADDLE",
                "CE": {"strike": atm},
                "PE": {"strike": atm},
            },
            "alternate": {
                "strategy": "LONG_STRANGLE",
                "CE": {"strike": high_k},
                "PE": {"strike": low_k},
            },
            "sell_by": sell_by,
            "note": "If IV crush happens after event/overnight, exit early even if spot moves slowly.",
        }

    def recommend(
        self,
        as_of: str,
        symbol: str,
        signal_row: Dict[str, Any],
        underlying: UnderlyingSnapshot,
        chain: List[OptionChainRow],
    ) -> OptionReco:
        """
        Uses your EOD directional score to decide CE/PE, then picks a near-ATM, liquid option
        in the DTE window, and attaches IV/theta + sell_by to manage time decay.
        Also supports range-trade suggestion in opportunistic/speculative when direction is unclear.
        """
        s = normalize_to_nse_symbol(symbol)
        spot = float(getattr(underlying, "spot", None) or 0.0)
        if spot <= 0:
            raise RuntimeError("Underlying spot missing/invalid")

        # Direction decision from signals.csv (buy_win/sell_win + soft scores)
        buy_win = int(signal_row.get("buy_win", 0) or 0)
        sell_win = int(signal_row.get("sell_win", 0) or 0)
        direction_score = float(signal_row.get("direction_score", 0.0) or 0.0)
        buy_soft = float(signal_row.get("buy_soft", 0.0) or 0.0)
        sell_soft = float(signal_row.get("sell_soft", 0.0) or 0.0)

        atr_points = float(signal_row.get("atr_points", 0.0) or 0.0)
        atr_pct = float(signal_row.get("atr_pct", 0.0) or 0.0)

        if atr_points <= 0:
            # rough fallback if missing
            atr_points = spot * 0.01
        if atr_pct <= 0 and spot > 0:
            atr_pct = atr_points / spot

        min_dir = self._min_dir()

        diag_base = {
            "mode": self.cfg.mode,
            "buy_win": buy_win,
            "sell_win": sell_win,
            "buy_soft": buy_soft,
            "sell_soft": sell_soft,
            "direction_score": direction_score,
            "atr_points": atr_points,
            "atr_pct": atr_pct,
            "spot": spot,
        }

        # ---- NO EDGE -> HOLD (but may propose RANGE strategy) ----
        no_edge = (
            buy_win == 0
            and sell_win == 0
            and abs(direction_score) < min_dir
            and buy_soft == 0
            and sell_soft == 0
        )

        if no_edge:
            conf = max(self.cfg.conf_floor_hold, 0.12)
            explain = (
                f"No directional edge for mode={self.cfg.mode}: "
                f"|direction_score|={abs(direction_score):.2f} < {min_dir:.2f}, buy/sell wins=0."
            )
            diag_base["confidence_explain"] = explain
            return OptionReco(
                as_of=as_of,
                symbol=s,
                bias="NEUTRAL",
                instrument="NONE",
                action="HOLD",
                confidence=float(f"{conf:.2f}"),
                rationale=["No directional edge for next session.", explain],
                diagnostics=diag_base,
                spot=_round2(spot),
            )

        # Determine side/bias/edge
        if buy_win > sell_win or direction_score > 0:
            side = "CE"
            bias = "BULLISH"
            edge = max(direction_score, buy_soft, 0.2)
        elif sell_win > buy_win or direction_score < 0:
            side = "PE"
            bias = "BEARISH"
            edge = max(abs(direction_score), sell_soft, 0.2)
        else:
            side = "CE" if buy_soft >= sell_soft else "PE"
            bias = "BULLISH" if side == "CE" else "BEARISH"
            edge = max(buy_soft, sell_soft, 0.2)

        # ---- Range-trade suggestion when direction is weak/unclear ----
        # If direction_score is weak but ATR% suggests expansion, recommend straddle/strangle (diagnostics only).
        # This avoids forcing a naked buy that can die by theta/IV.
        weak_direction = abs(direction_score) < min_dir
        both_present = (buy_soft > 0 and sell_soft > 0) or (buy_win > 0 and sell_win > 0)
        range_ok = (
            self.cfg.mode in ("opportunistic", "speculative")
            and weak_direction
            and (atr_pct >= self._min_range_atr_pct())
            and bool(chain)
            and (both_present or abs(buy_soft - sell_soft) <= 0.10)
        )
        if range_ok:
            suggestion = self._range_trade_suggestion(as_of, s, spot, atr_points, atr_pct, chain)
            conf = max(
                self.cfg.conf_floor_trade_opp if self.cfg.mode == "opportunistic" else self.cfg.conf_floor_trade_spec,
                0.30,
            )
            explain = (
                f"Range regime: weak direction (|direction_score|={abs(direction_score):.2f} < {min_dir:.2f}) "
                f"but ATR%={atr_pct:.2%} suggests expansion. Suggested straddle/strangle (see diagnostics)."
            )
            diagnostics = dict(diag_base)
            diagnostics["range_trade_suggestion"] = suggestion
            diagnostics["confidence_explain"] = explain
            return OptionReco(
                as_of=as_of,
                symbol=s,
                bias="NEUTRAL",
                instrument="NONE",
                action="HOLD",  # keep schema stable; UI shows suggestion
                confidence=float(f"{conf:.2f}"),
                rationale=[
                    "No clean directional edge; range strategy suggested (diagnostics.range_trade_suggestion).",
                    explain,
                ],
                diagnostics=diagnostics,
                spot=_round2(spot),
            )

        # choose expiry window and near-the-money strike (liquid)
        min_strike = spot - self.cfg.max_moneyness_atr * atr_points
        max_strike = spot + self.cfg.max_moneyness_atr * atr_points

        # filter chain by side + DTE window + moneyness band
        candidates: List[Tuple[OptionChainRow, int]] = []
        min_dte = self._min_dte()
        for r in chain:
            if (r.option_type or "").upper() != side:
                continue
            dte = _days_to_expiry(as_of, r.expiry)
            if dte is None:
                continue
            if dte < min_dte or dte > self.cfg.max_dte:
                continue
            if r.strike < min_strike or r.strike > max_strike:
                continue
            if self.cfg.min_oi and (r.oi or 0) < self.cfg.min_oi:
                continue
            if self.cfg.min_volume and (r.volume or 0) < self.cfg.min_volume:
                continue
            candidates.append((r, dte))

        if not candidates:
            # relax DTE as fallback: pick nearest expiry (but still avoid 0DTE)
            for r in chain:
                if (r.option_type or "").upper() != side:
                    continue
                dte = _days_to_expiry(as_of, r.expiry)
                if dte is None or dte < 1:
                    continue
                candidates.append((r, dte))

        if not candidates:
            conf = max(self.cfg.conf_floor_hold, 0.12)
            explain = f"No suitable {side} options found after expiry/liquidity filters."
            diagnostics = dict(diag_base)
            diagnostics["confidence_explain"] = explain
            return OptionReco(
                as_of=as_of,
                symbol=s,
                bias="NEUTRAL",
                instrument="NONE",
                action="HOLD",
                confidence=float(f"{conf:.2f}"),
                rationale=[explain],
                diagnostics=diagnostics,
                spot=_round2(spot),
            )

        # score: near ATM + high OI + moderate premium (avoid deep ITM/OTM)
        def score_row(row: OptionChainRow, dte: int) -> float:
            atm = abs(row.strike - spot) / max(1.0, atr_points)
            oi = float(row.oi or 0.0)
            vol = float(row.volume or 0.0)
            prem = float(row.ltp or 0.0)
            # prefer 7-21 DTE
            dte_pref = abs(dte - 14) / 14.0
            return -atm + 0.000001 * oi + 0.000001 * vol - 0.002 * dte_pref - 0.0005 * prem

        best, best_dte = max(candidates, key=lambda x: score_row(x[0], x[1]))

        ltp = float(best.ltp)
        strike = float(best.strike)
        dte = int(best_dte)
        T = max(1e-6, dte / 365.0)

        # IV + greeks
        iv = implied_vol(ltp, spot, strike, T, self.cfg.r_rate, side)
        g = bs_greeks(spot, strike, T, self.cfg.r_rate, iv, side) if iv else None
        intrinsic, extrinsic = intrinsic_extrinsic(spot, strike, ltp, side)

        # Entry, SL, Targets on premium
        entry = ltp * (1.0 - self.cfg.entry_slippage_frac)

        sl = delta_based_sl(
            entry=entry,
            spot=spot,
            delta=(g.delta if g else None),
            gamma=(g.gamma if g else None),
            mode=self.cfg.mode,
            max_loss_frac=self.cfg.stop_loss_frac,
        )

        risk = max(0.01, entry - sl)
        t1 = entry + self.cfg.t1_rr * risk
        t2 = entry + self.cfg.t2_rr * risk

        # Underlying targets (rough, using ATR)
        t1_u = spot + (1.0 if side == "CE" else -1.0) * 0.8 * atr_points
        t2_u = spot + (1.0 if side == "CE" else -1.0) * 1.6 * atr_points

        # Sell-by heuristic: if theta burn likely eats X% of extrinsic before then.
        sell_by = None
        theta_pd = g.theta_per_day if (g and g.theta_per_day is not None) else None
        if theta_pd is not None and extrinsic > 0:
            theta_burn = abs(theta_pd)
            budget = self.cfg.theta_sell_by_budget_frac * extrinsic
            # days until budget is consumed (cap within DTE)
            if theta_burn > 1e-6:
                days_budget = int(max(1, min(dte, budget / theta_burn)))
                # keep at least 1 day buffer before expiry
                sell_by_dt = datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=days_budget)
                # never after expiry - 1
                exp_dt = _parse_expiry(best.expiry)
                if exp_dt:
                    last = exp_dt.date() - timedelta(days=1)
                    if sell_by_dt.date() > last:
                        sell_by_dt = datetime.combine(last, datetime.min.time())
                sell_by = sell_by_dt.strftime("%Y-%m-%d")
        if not sell_by:
            sell_by = self._sell_by_fallback(as_of, best.expiry)

        # Confidence blend (mode-aware floors)
        conf = min(
            0.95,
            0.25
            + 0.60 * min(1.0, edge)
            + 0.10 * (1.0 - min(1.0, abs(strike - spot) / max(1.0, atr_points))),
        )

        if dte < 3:
            conf *= 0.75  # theta cliff
        if iv and iv > 0.40:
            conf *= 0.90  # high IV risk

        # floors
        if self.cfg.mode == "strict":
            conf = max(conf, self.cfg.conf_floor_trade_strict)
        elif self.cfg.mode == "opportunistic":
            conf = max(conf, self.cfg.conf_floor_trade_opp)
        else:
            conf = max(conf, self.cfg.conf_floor_trade_spec)

        # Breakeven in underlying at expiry
        breakeven = (strike + entry) if side == "CE" else (strike - entry)

        rationale = [
            f"{bias} bias from EOD signal (direction_score={direction_score:.2f}, buy_win={buy_win}, sell_win={sell_win}).",
            f"Picked near-ATM {side} with DTE={dte} to reduce theta cliff; liquidity via OI/volume where available.",
        ]
        if iv:
            rationale.append(
                f"Implied vol ~ {iv*100:.1f}%; theta/day ~ {abs(theta_pd):.2f} premium units."
                if theta_pd
                else f"Implied vol ~ {iv*100:.1f}%."
            )
        if sell_by:
            rationale.append(f"Sell-by {sell_by} (time-boxed to manage theta/IV risk).")

        explain = (
            f"mode={self.cfg.mode}; side={side}; "
            f"direction_score={direction_score:.2f}; buy_soft={buy_soft:.2f}; sell_soft={sell_soft:.2f}; "
            f"DTE={dte}; IV={'n/a' if not iv else f'{iv*100:.1f}%'}; sell_by={sell_by}."
        )
        diagnostics = dict(diag_base)
        diagnostics.update(
            {
                "ltp": ltp,
                "intrinsic": intrinsic,
                "extrinsic": extrinsic,
                "iv": iv,
                "theta_per_day": theta_pd,
                "delta": (g.delta if g else None),
                "confidence_explain": explain,
                "sell_by": sell_by,
            }
        )
        rationale.append(explain)

        return OptionReco(
            as_of=as_of,
            symbol=s,
            bias=bias,
            instrument="OPTION",
            action="BUY",
            side=side,
            expiry=best.expiry,
            strike=strike,
            entry_price=_round2(entry),
            sl_premium=_round2(sl),
            sl_invalidation=_round2(spot - (1.0 if side == "CE" else -1.0) * 0.6 * atr_points),
            targets=[
                {"underlying": _round2(t1_u), "premium": _round2(t1)},
                {"underlying": _round2(t2_u), "premium": _round2(t2)},
            ],
            confidence=float(f"{conf:.2f}"),
            rationale=rationale,
            diagnostics=diagnostics,
            spot=_round2(spot),
            ltp=_round2(ltp),
            iv=_round2(iv * 100.0) if iv else None,  # store as %
            dte=dte,
            theta_per_day=_round2(theta_pd),
            delta=_round2(g.delta) if g else None,
            extrinsic=_round2(extrinsic),
            sell_by=sell_by,
            breakeven=_round2(breakeven),
        )
