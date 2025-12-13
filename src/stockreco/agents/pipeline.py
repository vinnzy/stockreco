from __future__ import annotations
import pandas as pd
from stockreco.agents.llm import openai_json
from stockreco.agents.schemas import PROPOSER_SCHEMA, REVIEWER_SCHEMA, ANALYST_SCHEMA
from stockreco.report.options_playbook import build_options_playbook

def _snapshot_row(r: pd.Series) -> dict:
    return {
        "ticker": r["ticker"],
        "p_up": float(r["p_up"]),
        "score": float(r["score"]),
        "signals": {
            "rsi_14": None if pd.isna(r.get("rsi_14")) else float(r["rsi_14"]),
            "macd_hist": None if pd.isna(r.get("macd_hist")) else float(r["macd_hist"]),
            "adx_14": None if pd.isna(r.get("adx_14")) else float(r["adx_14"]),
            "rel_strength_5d": None if pd.isna(r.get("rel_strength_5d")) else float(r["rel_strength_5d"]),
            "atr_pct": None if pd.isna(r.get("atr_pct")) else float(r["atr_pct"]),
            "close_above_sma20": int(r.get("close_above_sma20", 0)),
            "close_above_sma50": int(r.get("close_above_sma50", 0)),
            "sma20_above_sma50": int(r.get("sma20_above_sma50", 0)),
        }
    }

def run_agents(scored: pd.DataFrame, as_of: str, use_llm: bool) -> dict:
    top25 = scored.head(25).copy()
    candidates = [_snapshot_row(r) for _, r in top25.iterrows()]

    if not use_llm:
        # Rule-based proposer: take top 10 by score
        top10 = []
        for i, c in enumerate(candidates[:10], start=1):
            top10.append({
                "ticker": c["ticker"],
                "rank": i,
                "p_up": c["p_up"],
                "signals": c["signals"],
                "thesis": "Strong score from calibrated model + relative strength; confirm intraday price action before entry.",
                "invalidate_if": ["Broad market turns risk-off", "Large gap-down open", "High IV / wide spreads in options"]
            })
        # Rule-based reviewer: drop overbought+weak trend, or high vol
        approved = []
        rejected = []
        for item in top10:
            rsi = item["signals"].get("rsi_14")
            adx = item["signals"].get("adx_14")
            atr = item["signals"].get("atr_pct")
            if rsi is not None and rsi > 74 and (adx is None or adx < 18):
                rejected.append({"ticker": item["ticker"], "reason": "Overbought RSI with weak trend strength (ADX)."})
            elif atr is not None and atr > 0.05:
                rejected.append({"ticker": item["ticker"], "reason": "High ATR% suggests noisy next-day direction; prefer cleaner setups."})
            else:
                approved.append(item["ticker"])

        # Analyst: attach options playbook
        final = []
        for item in top10:
            if item["ticker"] not in approved:
                continue
            p = float(item["p_up"])
            label = "High" if p >= 0.62 else "Medium" if p >= 0.56 else "Low"
            final.append({
                "ticker": item["ticker"],
                "p_up": p,
                "confidence_label": label,
                "why": item["thesis"],
                "options_playbook": build_options_playbook(p)
            })
        return {"proposer":{"as_of":as_of,"top10":top10}, "reviewer":{"approved":approved,"rejected":rejected}, "analyst":{"final":final, "regime_notes":["EOD-based model; confirm with next-day price action before taking options."]}}

    # LLM path
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

    approved_set = set(reviewer["approved"])
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
    return {"proposer": proposer, "reviewer": reviewer, "analyst": analyst}
