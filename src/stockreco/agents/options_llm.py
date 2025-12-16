from __future__ import annotations
from typing import List, Dict, Any
from stockreco.agents.llm import openai_json

# -------------------------------------------------------------------------
# SCHEMAS
# -------------------------------------------------------------------------

OPTIONS_REVIEWER_SCHEMA = {
    "type": "object",
    "properties": {
        "approved": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of ticker symbols that are approved for trading."
        },
        "rejected": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "reason": {"type": "string", "description": "Concise reason for rejection."}
                },
                "required": ["symbol", "reason"],
                "additionalProperties": False
            }
        }
    },
    "required": ["approved", "rejected"],
    "additionalProperties": False
}

OPTIONS_ANALYST_SCHEMA = {
    "type": "object",
    "properties": {
        "final_notes": {
            "type": "string",
            "description": "A brief summary of the overall options strategy or market regime notes for the day."
        },
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "rationale_summary": {
                        "type": "string",
                        "description": "A cohesive trading thesis paragraph explaining why this option trade is attractive based on technicals and Greeks."
                    },
                    "confidence_adjustment": {
                        "type": "number",
                        "description": "Optional adjustment to confidence score (e.g. +0.05 or -0.05) based on qualitative factors. Use 0.0 if no change."
                    }
                },
                "required": ["symbol", "rationale_summary"],
                "additionalProperties": False
            }
        }
    },
    "required": ["recommendations"],
    "additionalProperties": False
}


# -------------------------------------------------------------------------
# LLM FUNCTIONS
# -------------------------------------------------------------------------

def review_options_llm(candidates: List[Dict[str, Any]], as_of: str) -> Dict[str, Any]:
    """
    Uses LLM to review a list of option candidates.
    Acts as a risk manager/critic to filter out poor setups.
    """
    if not candidates:
        return {"approved": [], "rejected": []}

    prompt = f"""You are an Options Risk Manager. Review these potential option trades for tomorrow ({as_of}).
Your goal is to REJECT trades that look risky, have contradictory signals, or weak setups.
APPROVE trades that have strong alignment between technicals and the specific option contract selected.

Criteria for REJECTION:
- Buying CALLS when RSI is overbought (>75) without strong momentum
- Buying PUTS when RSI is oversold (<25) without strong momentum
- Theta decay > 10% of entry price for swing trades (unless high momentum)
- Extremely low liquidity or very wide spreads implied (if visible)
- Contradictory signals (e.g. bullish bias but Moving Averages are bearish)

Return JSON strictly matching the schema.

Candidates:
{_format_candidates_for_prompt(candidates)}
"""
    return openai_json(prompt, OPTIONS_REVIEWER_SCHEMA)


def analyze_options_llm(approved_recos: List[Dict[str, Any]], as_of: str) -> Dict[str, Any]:
    """
    Uses LLM to generate qualitative analysis (trading thesis) for approved options.
    """
    if not approved_recos:
        return {"recommendations": [], "final_notes": "No approved recommendations."}

    prompt = f"""You are a Senior Options Analyst. Write a trading thesis for these approved option setups for {as_of}.
 For each symbol:
 1. Write a 'rationale_summary': A single, punchy paragraph explaining the trade. Mention the setup (e.g. "Breakout retest", "Momentum continuation"), key technicals, and why this specific option (Strike/Expiry) is a good risk/reward.
 2. Provide a 'confidence_adjustment': A small float (e.g. 0.05, -0.02, 0.0) if you feel the automated score needs a qualitative nudge.

Return JSON strictly matching the schema.

Approved Trades:
{_format_candidates_for_prompt(approved_recos)}
"""
    return openai_json(prompt, OPTIONS_ANALYST_SCHEMA)


def _format_candidates_for_prompt(candidates: List[Dict[str, Any]]) -> str:
    """Helper to format candidate list for LLM context, minimizing tokens."""
    lines = []
    for c in candidates:
        # Extract key info
        sym = c.get("symbol")
        side = c.get("side")
        strike = c.get("strike")
        expiry = c.get("expiry")
        conf = c.get("confidence", 0.0)
        
        # Diagnostics/Technicals often nested in 'diagnostics' or top level depending on stage
        diag = c.get("diagnostics", {})
        # Fallback to checking if they are at top level (unlikely for OptionReco but possible)
        
        # Format a compact representation
        lines.append(f"--- {sym} {side} {strike} ({expiry}) ---")
        lines.append(f"Confidence: {conf:.2f}")
        
        # Add technicals if available in 'rationale' or 'diagnostics'
        # simpler to dump the dict keys that matter
        # For OptionReco objects, we might have 'rationale' as list of strings
        if "rationale" in c:
            lines.append(f"Auto-Rationale: {c['rationale']}")
            
        # Add Greeks/Pricing if available
        if "entry" in c: lines.append(f"Entry: {c['entry']}")
        if "iv" in c: lines.append(f"IV: {c.get('iv')}")
        if "theta_per_day" in c: lines.append(f"Theta/Day: {c.get('theta_per_day')}")
        
    return "\n".join(lines)
