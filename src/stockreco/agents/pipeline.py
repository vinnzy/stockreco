from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any

import pandas as pd

from stockreco.agents.llm import openai_json
from stockreco.agents.schemas import PROPOSER_SCHEMA, REVIEWER_SCHEMA, ANALYST_SCHEMA
from stockreco.report.options_playbook import build_options_playbook


def _snapshot_row(r: pd.Series) -> dict:
    return {
        "ticker": r["ticker"],
        "p_up": float(r["p_up"]),
        "score": float(r["score"]),
        # present only after re-ranking; kept for LLM candidate context + report visibility
        "options_score": float(r.get("options_score", 0.0)),
        "signals": {
            "rsi_14": None if pd.isna(r.get("rsi_14")) else float(r["rsi_14"]),
            "macd_hist": None if pd.isna(r.get("macd_hist")) else float(r["macd_hist"]),
            "adx_14": None if pd.isna(r.get("adx_14")) else float(r["adx_14"]),
            "rel_strength_5d": None if pd.isna(r.get("rel_strength_5d")) else float(r["rel_strength_5d"]),
            "atr_pct": None if pd.isna(r.get("atr_pct")) else float(r["atr_pct"]),
            "close_above_sma20": int(r.get("close_above_sma20", 0)),
            "close_above_sma50": int(r.get("close_above_sma50", 0)),
            "sma20_above_sma50": int(r.get("sma20_above_sma50", 0)),
        },
    }


def _minmax(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    mn, mx = float(s.min()), float(s.max())
    if mx == mn:
        return s * 0.0
    return (s - mn) / (mx - mn)


def compute_options_suitability(scored: pd.DataFrame) -> pd.DataFrame:
    """EOD-only proxy for "options tradability".

    Intent: for intraday options trades targeting +20–50% premium, you generally need:
      - enough daily range (ATR%)
      - a trend / directional movement probability (ADX)
      - either strong momentum (RSI>=60) or bounce potential (RSI<=35)
      - some relative strength vs peers

    This is NOT a guarantee; it's just a better ranking than pure p_up/score for options.
    """
    df = scored.copy()

    atr_n = _minmax(df.get("atr_pct", 0).fillna(0))
    adx_n = _minmax(df.get("adx_14", 0).fillna(0))
    rs_n = _minmax(df.get("rel_strength_5d", 0).fillna(0))

    rsi = df.get("rsi_14", 50).fillna(50)
    # impulse if oversold bounce OR strong momentum zone
    rsi_impulse = ((rsi <= 35).astype(float) + (rsi >= 60).astype(float)) / 2.0

    # penalize very low-trend chop
    chop_penalty = (df.get("adx_14", 0).fillna(0) < 12).astype(float) * 0.25

    df["options_score"] = (
        0.40 * atr_n
        + 0.30 * adx_n
        + 0.20 * rsi_impulse
        + 0.10 * rs_n
        - chop_penalty
    )
    return df


def should_no_trade(
    scored: pd.DataFrame, pup_min: float = 0.55, spread_min: float = 0.06
) -> Tuple[bool, List[str]]:
    """Conservative NO-TRADE rule for options."""
    notes: List[str] = []
    if len(scored) == 0:
        return True, ["No scored rows available (data/feature issue)."]

    top3_mean = float(scored.head(3)["p_up"].mean())
    spread = float(scored["p_up"].quantile(0.90) - scored["p_up"].quantile(0.10))

    if top3_mean < pup_min:
        notes.append(f"Low conviction: mean p_up of top 3 is {top3_mean:.2f} (< {pup_min:.2f}).")
    if spread < spread_min:
        notes.append(f"Low separation: p_up spread (P90-P10) is {spread:.2f} (< {spread_min:.2f}).")

    if (top3_mean < pup_min) and (spread < spread_min):
        notes.append("NO-TRADE for options recommended (edge too small / too clustered).")
        return True, notes

    return False, notes


def run_agents(
    scored: pd.DataFrame,
    as_of: str,
    use_llm: bool,
    mode: str = "strict",
    max_trades: int = 10,
    no_trade_pup: Optional[float] = None,
    no_trade_spread: Optional[float] = None,
) -> Dict[str, Any]:
    """
    mode:
      - "strict": if NO-TRADE gate triggers, output 0 picks
      - "aggressive": still output up to max_trades even if NO-TRADE triggers (but keep notes)
    """
    mode = (mode or "strict").lower().strip()
    if mode not in ("strict", "aggressive"):
        mode = "strict"

    # Use defaults when CLI passes None
    pup_min = 0.55 if no_trade_pup is None else float(no_trade_pup)
    spread_min = 0.06 if no_trade_spread is None else float(no_trade_spread)

    # Re-rank for options suitability (EOD proxy), then score
    scored2 = compute_options_suitability(scored)
    scored2 = scored2.sort_values(["options_score", "score"], ascending=False)

    no_trade, nt_notes = should_no_trade(scored2, pup_min=pup_min, spread_min=spread_min)

    # STRICT: immediately return NO-TRADE
    if no_trade and mode == "strict":
        return {
            "proposer": {"as_of": as_of, "top10": []},
            "reviewer": {"approved": [], "rejected": []},
            "analyst": {"final": [], "regime_notes": nt_notes},
            "scored": scored2,
        }

    # Candidate snapshot
    top25 = scored2.head(25).copy()
    candidates = [_snapshot_row(r) for _, r in top25.iterrows()]

    def _mk_final_from_ranked(df_ranked: pd.DataFrame, k: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for _, r in df_ranked.head(k).iterrows():
            p = float(r.get("p_up", 0.50))
            label = "High" if p >= 0.62 else "Medium" if p >= 0.56 else "Low"
            out.append(
                {
                    "ticker": r["ticker"],
                    "p_up": p,
                    "confidence_label": label,
                    "why": (
                        "Aggressive mode: strict NO-TRADE gate may be active; "
                        "this is a tactical candidate ranked by options suitability (ATR/ADX/RSI impulse) "
                        "plus calibrated score. Take only on intraday confirmation."
                        if mode == "aggressive" and no_trade
                        else
                        "Ranked for options suitability (ATR/ADX/RSI impulse) plus calibrated p_up; confirm intraday price action before entry."
                    ),
                    "options_playbook": build_options_playbook(p),
                }
            )
        return out

    # ---- NO LLM PATH ----
    if not use_llm:
        # Rule-based proposer: take top 10 by options suitability
        top10: List[Dict[str, Any]] = []
        for i, c in enumerate(candidates[:10], start=1):
            top10.append(
                {
                    "ticker": c["ticker"],
                    "rank": i,
                    "p_up": c["p_up"],
                    "signals": c["signals"],
                    "thesis": (
                        "Ranked for options suitability (ATR/ADX/RSI impulse) plus calibrated p_up; "
                        "confirm intraday price action before entry."
                    ),
                    "invalidate_if": [
                        "Broad market turns risk-off",
                        "Large gap-down open (breaks structure)",
                        "High IV / wide spreads in options",
                        "Very low liquidity / slippage",
                    ],
                }
            )

        # Rule-based reviewer: drop options-hostile setups
        approved: List[str] = []
        rejected: List[Dict[str, str]] = []
        for item in top10:
            rsi = item["signals"].get("rsi_14")
            adx = item["signals"].get("adx_14")
            atr = item["signals"].get("atr_pct")

            if adx is not None and adx < 14:
                rejected.append(
                    {"ticker": item["ticker"], "reason": "ADX too low (likely chop) — options premiums decay."}
                )
                continue

            if atr is not None and atr < 0.012:
                rejected.append(
                    {"ticker": item["ticker"], "reason": "ATR% too low — often insufficient premium expansion for intraday targets."}
                )
                continue

            if rsi is not None and rsi > 74 and (adx is None or adx < 25):
                rejected.append(
                    {"ticker": item["ticker"], "reason": "Overbought RSI without strong trend; mean-reversion risk."}
                )
                continue

            approved.append(item["ticker"])

        # Build final:
        # - strict: from approved list, capped by max_trades
        # - aggressive+no_trade: IGNORE gate, take from ranked options_score list (top k)
        final: List[Dict[str, Any]] = []
        if mode == "aggressive" and no_trade:
            final = _mk_final_from_ranked(scored2, max_trades)
        else:
            for item in top10:
                if item["ticker"] not in approved:
                    continue
                p = float(item["p_up"])
                label = "High" if p >= 0.62 else "Medium" if p >= 0.56 else "Low"
                final.append(
                    {
                        "ticker": item["ticker"],
                        "p_up": p,
                        "confidence_label": label,
                        "why": item["thesis"],
                        "options_playbook": build_options_playbook(p),
                    }
                )
                if len(final) >= max_trades:
                    break

        regime_notes: List[str] = ["EOD-based; take options only on intraday confirmation."]
        if no_trade:
            regime_notes.extend(nt_notes)
        if mode == "aggressive" and no_trade:
            regime_notes.append(
                f"Aggressive override: strict NO-TRADE triggered, but emitting up to {max_trades} tactical candidates."
            )

        return {
            "proposer": {"as_of": as_of, "top10": top10},
            "reviewer": {"approved": approved, "rejected": rejected},
            "analyst": {"final": final, "regime_notes": regime_notes},
            "scored": scored2,
        }

    # ---- LLM PATH ----
    proposer_prompt = f"""You are the Proposer. From the candidates list, select up to 10 tickers most likely to show upward momentum tomorrow.
Return JSON strictly matching the schema. Include clear invalidate_if conditions.
as_of={as_of}
Candidates JSON:
{candidates}
"""
    proposer = openai_json(proposer_prompt, PROPOSER_SCHEMA)

    reviewer_prompt = f"""You are the Reviewer/Critic. You will accept/reject each proposer pick.
Reject if signals are contradictory, too volatile, or thesis is weak.
Return JSON strictly matching schema.
Proposer JSON:
{proposer}
"""
    reviewer = openai_json(reviewer_prompt, REVIEWER_SCHEMA)

    # cap approvals to max_trades
    if "approved" in reviewer and isinstance(reviewer["approved"], list):
        reviewer["approved"] = reviewer["approved"][:max_trades]

    analyst_prompt = f"""You are the Analyst. Use proposer picks and reviewer approvals.
For each approved ticker, keep calibrated p_up and provide:
- confidence_label (High/Medium/Low)
- why (1 short paragraph grounded in signals)
- options_playbook: bullet-like strings (delta band, entry confirmation, stop, targets)
Return JSON strictly matching schema.
as_of={as_of}
Proposer JSON:
{proposer}
Reviewer JSON:
{reviewer}
"""
    analyst = openai_json(analyst_prompt, ANALYST_SCHEMA)

    # ensure options playbook exists even if LLM outputs empty
    for item in analyst.get("final", []):
        if not item.get("options_playbook"):
            item["options_playbook"] = build_options_playbook(float(item.get("p_up", 0.55)))

    analyst.setdefault("regime_notes", [])
    analyst["regime_notes"].append(f"Max {max_trades} trades enforced for options discipline.")

    # If aggressive + no_trade, but LLM returned nothing, fall back to ranked picks
    if mode == "aggressive" and no_trade and not analyst.get("final"):
        analyst["final"] = _mk_final_from_ranked(scored2, max_trades)
        analyst["regime_notes"].append(
            f"Aggressive override: strict NO-TRADE triggered; fallback to top {max_trades} by options_score."
        )

    if no_trade:
        analyst["regime_notes"].extend(nt_notes)

    return {"proposer": proposer, "reviewer": reviewer, "analyst": analyst, "scored": scored2}
