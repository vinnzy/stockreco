# LLM-Based Options Reviewer & Analyst Implementation Plan

## Goal
Enhance the rule-based options recommendation pipeline with an optional **LLM-based quantitative & qualitative review**. This mirrors the existing stock recommendation pipeline's "Proposer-Reviewer-Analyst" architecture.

## Architecture

We will introduce a `use_llm` flag to `run_eod_option_reco.py`.

1.  **Proposer (Unchanged)**: `OptionRecoAgent` generates quantitative candidates based on strikes, greeks, and signals.
2.  **Reviewer (Hybrid)**:
    -   *Rule-Based (Current)*: Hard filters for IV, DTE, Theta.
    -   *LLM-Based (New)*: OpenAI model reviews candidates for "common sense" risks, market regime context, and qualitative factors. It acts as a second filter.
3.  **Analyst (LLM Enhanced)**:
    -   Currently, `rationale` is template-based strings.
    -   *New*: LLM generates a cohesive "Trading Thesis" paragraph explaining *why* this option was picked (e.g., "High confidence bullish setup on NIFTY with low IV suggests buying calls...").

## JSON Schemas

We need to define strict schemas for the LLM output to ensure compatibility with our frontend and reportwriters.

### Reviewer Schema
```json
{
  "type": "object",
  "properties": {
    "approved": {"type": "array", "items": {"type": "string"}}, // List of symbols
    "rejected": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "symbol": {"type": "string"},
          "reason": {"type": "string"}
        },
        "required": ["symbol", "reason"],
        "additionalProperties": false
      }
    }
  },
  "required": ["approved", "rejected"],
  "additionalProperties": false
}
```

### Analyst Schema
```json
{
  "type": "object",
  "properties": {
    "final_notes": {"type": "string"}, // Summary of the day's options strategy
    "recommendations": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "symbol": {"type": "string"},
          "rationale_summary": {"type": "string"}, // LLM generated explanation
          "confidence_adjustment": {"type": "number"} // Optional +/- adjustments
        },
        "required": ["symbol", "rationale_summary"],
        "additionalProperties": false
      }
    }
  },
  "required": ["recommendations"],
  "additionalProperties": false
}
```

## Proposed Changes

### 1. New Module: `src/stockreco/agents/options_llm.py`
-   Implement `review_options_llm(candidates, as_of)`
-   Implement `analyze_options_llm(approved_candidates, as_of)`
-   Construct prompts that include:
    -   Candidate details (Strike, Expiry, IV, Theta, Delta)
    -   Underlying Technicals (RSI, ADX, Trend)
    -   Market Context (VIX if available, or sector info)

### 2. Update `scripts/run_eod_option_reco.py`
-   Add `--use-llm` CLI argument.
-   If flag is set:
    -   Run `OptionRecoAgent` (Proposer).
    -   Run `review_options_llm` (Reviewer).
    -   Run `analyze_options_llm` (Analyst).
    -   Merge LLM outputs into the final report structure.

### 3. Report & Frontend
-   The existing `reviewer` output structure (`approved`/`rejected`) is compatible.
-   The `rationale` field in expected output can simply be replaced by the LLM-generated text.
-   No major frontend changes needed if we stick to the existing data shape!

## Verification Plan
1.  **Dry Run**: Run with `--use-llm` utilizing existing OpenAI key (if configured).
2.  **Schema Check**: Ensure JSON outputs parse correctly.
3.  **Frontend Check**: Verify the "Reviewer" column still works and "Rationale" text looks natural.
