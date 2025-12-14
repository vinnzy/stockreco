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
        "p_expand": float(r.get("p_expand", 0.0)),
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
    """EOD-only proxy for "options tradability" (ranking helper), now Model-B aware via p_expand.

    Model A: p_up  (direction)
    Model B: p_expand (range/vol expansion proxy)
    We use p_expand as an additional positive term in options suitability.
    """
    df = scored.copy()

    atr_n = _minmax(df.get("atr_pct", 0).fillna(0))
    adx_n = _minmax(df.get("adx_14", 0).fillna(0))
    rs_n = _minmax(df.get("rel_strength_5d", 0).fillna(0))

    rsi = df.get("rsi_14", 50).fillna(50)
    rsi_impulse = ((rsi <= 35).astype(float) + (rsi >= 60).astype(float)) / 2.0

    # Model-B: probability of expansion
    pexp = df.get("p_expand", 0.0).fillna(0.0)
    pexp_n = _minmax(pexp)

    chop_penalty = (df.get("adx_14", 0).fillna(0) < 12).astype(float) * 0.25

    df["options_score"] = (
        0.35 * atr_n +
        0.25 * adx_n +
        0.15 * rsi_impulse +
        0.10 * rs_n +
        0.15 * pexp_n -
        chop_penalty
    )
    return df


def should_no_trade(
    scored: pd.DataFrame,
    pup_min: float = 0.55,
    spread_min: float = 0.06,
    pexp_min: float = 0.55,
) -> Tuple[bool, List[str]]:
    """Conservative NO-TRADE rule for options (Model-A + Model-B aware).

    - Need directional edge (p_up) AND
    - Need expansion edge (p_expand)
    """
    notes: List[str] = []
    if len(scored) == 0:
        return True, ["No scored rows available (data/feature issue)."]

    top3_mean_pup = float(scored.head(3)["p_up"].mean())
    spread_pup = float(scored["p_up"].quantile(0.90) - scored["p_up"].quantile(0.10))

    if "p_expand" in scored.columns:
        top3_mean_pexp = float(scored.head(3)["p_expand"].fillna(0).mean())
    else:
        top3_mean_pexp = 0.0

    if top3_mean_pup < pup_min:
        notes.append(f"Low conviction: mean p_up of top 3 is {top3_mean_pup:.2f} (< {pup_min:.2f}).")
    if spread_pup < spread_min:
        notes.append(f"Low separation: p_up spread (P90-P10) is {spread_pup:.2f} (< {spread_min:.2f}).")
    if top3_mean_pexp < pexp_min:
        notes.append(f"Low expansion: mean p_expand of top 3 is {top3_mean_pexp:.2f} (< {pexp_min:.2f}).")

    # strict NO-TRADE if direction is weak+clustered OR expansion is weak
    if ((top3_mean_pup < pup_min) and (spread_pup < spread_min)) or (top3_mean_pexp < pexp_min):
        notes.append("NO-TRADE for options recommended (edge too small / too clustered).")
        return True, notes

    return False, notes


def _rule_based_reviewer(
    top10: List[Dict[str, Any]],
    *,
    mode: str,
    min_pexp_strict: float = 0.55,
    min_pexp_aggr: float = 0.30,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """Reviewer that rejects options-hostile setups, now including Model-B (p_expand)."""
    approved: List[str] = []
    rejected: List[Dict[str, str]] = []

    pexp_min = min_pexp_strict if mode == "strict" else min_pexp_aggr

    for item in top10:
        sig = item.get("signals", {})
        rsi = sig.get("rsi_14")
        adx = sig.get("adx_14")
        atr = sig.get("atr_pct")
        pexp = float(item.get("p_expand", 0.0))

        # Model-B gate: need expansion probability
        if pexp < pexp_min:
            rejected.append({
                "ticker": item["ticker"],
                "reason": f"Model-B p_expand too low ({pexp:.2f} < {pexp_min:.2f}) — options may not expand intraday."
            })
            continue

        if adx is not None and adx < 14:
            rejected.append({"ticker": item["ticker"], "reason": "ADX too low (likely chop) — options premiums decay."})
            continue

        if atr is not None and atr < 0.012:
            rejected.append({"ticker": item["ticker"], "reason": "ATR% too low — often insufficient premium expansion for intraday targets."})
            continue

        if rsi is not None and rsi > 74 and (adx is None or adx < 25):
            rejected.append({"ticker": item["ticker"], "reason": "Overbought RSI without strong trend; mean-reversion risk."})
            continue

        approved.append(item["ticker"])

    return approved, rejected


def run_agents(
    scored: pd.DataFrame,
    as_of: str,
    use_llm: bool,
    mode: str = "strict",
    max_trades: int = 10,
    no_trade_pup: Optional[float] = None,
    no_trade_spread: Optional[float] = None,
    no_trade_pexp: Optional[float] = None,
) -> dict:
    """
    mode:
      - strict: apply NO-TRADE gate to FINAL picks, but still show proposer/reviewer output
      - aggressive: bypass/relax NO-TRADE gate and allow up to max_trades picks

    IMPORTANT:
      - Model-B must be merged into `scored` as column `p_expand` before calling run_agents.
    """
    mode = (mode or "strict").lower().strip()
    if mode not in ("strict", "aggressive"):
        mode = "strict"

    # Re-rank for options suitability (Model-B aware)
    scored2 = compute_options_suitability(scored)
    scored2 = scored2.sort_values(["options_score", "score"], ascending=False)

    strict_pup = 0.55 if no_trade_pup is None else float(no_trade_pup)
    strict_spread = 0.06 if no_trade_spread is None else float(no_trade_spread)
    strict_pexp = 0.55 if no_trade_pexp is None else float(no_trade_pexp)

    strict_no_trade, strict_notes = should_no_trade(
        scored2, pup_min=strict_pup, spread_min=strict_spread, pexp_min=strict_pexp
    )

    top25 = scored2.head(25).copy()
    candidates = [_snapshot_row(r) for _, r in top25.iterrows()]

    # ------------------------
    # RULE-BASED PATH
    # ------------------------
    if not use_llm:
        # Proposer: top 10 by options suitability
        top10: List[Dict[str, Any]] = []
        for i, c in enumerate(candidates[:10], start=1):
            top10.append({
                "ticker": c["ticker"],
                "rank": i,
                "p_up": c["p_up"],
                "p_expand": c.get("p_expand", 0.0),
                "signals": c["signals"],
                "thesis": (
                    "Ranked for options suitability (ATR/ADX/RSI impulse + Model-B p_expand) plus calibrated p_up; "
                    "confirm intraday price action before entry."
                ),
                "invalidate_if": [
                    "Broad market turns risk-off",
                    "Large gap-down open (breaks structure)",
                    "High IV / wide spreads in options",
                    "Very low liquidity / slippage",
                ],
            })

        approved, rejected = _rule_based_reviewer(top10, mode=mode)

        # Analyst: attach playbook, enforce max_trades
        final: List[Dict[str, Any]] = []
        for item in top10:
            if item["ticker"] not in approved:
                continue
            p = float(item["p_up"])
            pexp = float(item.get("p_expand", 0.0))
            label = "High" if p >= 0.62 else "Medium" if p >= 0.56 else "Low"
            final.append({
                "ticker": item["ticker"],
                "p_up": p,
                "p_expand": pexp,
                "confidence_label": label,
                "why": item["thesis"],
                "options_playbook": build_options_playbook(p),
            })
            if len(final) >= int(max_trades):
                break

        regime_notes: List[str] = ["EOD-based; take options only on intraday confirmation."]

        if mode == "strict":
            if strict_no_trade:
                regime_notes.extend(strict_notes)
                final = []
        else:
            if strict_no_trade:
                regime_notes.append("STRICT NO-TRADE would have triggered; proceeding in AGGRESSIVE mode.")
                regime_notes.extend(strict_notes)

        approved_for_display = approved[: max(0, int(max_trades))]

        return {
            "proposer": {"as_of": as_of, "top10": top10},
            "reviewer": {"approved": approved_for_display, "rejected": rejected},
            "analyst": {"final": final, "regime_notes": regime_notes},
            "scored": scored2,
        }

    # ------------------------
    # LLM PATH
    # ------------------------
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

    # Enforce max_trades on approvals
    if "approved" in reviewer and isinstance(reviewer["approved"], list):
        reviewer["approved"] = reviewer["approved"][: int(max_trades)]

    analyst_prompt = f"""You are the Analyst. Use proposer picks and reviewer approvals.
For each approved ticker, keep calibrated p_up and provide:
- confidence_label (High/Medium/Low)
- why (1 short paragraph grounded in signals, including p_expand if present)
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
    analyst["regime_notes"].append("EOD-based; take options only on intraday confirmation.")
    analyst["final"] = (analyst.get("final") or [])[: int(max_trades)]

    # Apply strict gate only to FINAL list (not proposer/reviewer)
    if mode == "strict" and strict_no_trade:
        analyst["regime_notes"].extend(strict_notes)
        analyst["final"] = []
    elif mode == "aggressive" and strict_no_trade:
        analyst["regime_notes"].append("STRICT NO-TRADE would have triggered; proceeding in AGGRESSIVE mode.")
        analyst["regime_notes"].extend(strict_notes)

    return {"proposer": proposer, "reviewer": reviewer, "analyst": analyst, "scored": scored2}
