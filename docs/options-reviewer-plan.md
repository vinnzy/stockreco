# Implementation Plan: Options Reviewer Agent

## Problem Statement

Currently, the options recommendation system uses a single `OptionRecoAgent` that directly generates recommendations. The stock recommendation system, however, uses a more sophisticated **proposer → reviewer → analyst** pipeline that provides better quality control and transparency.

This implementation will add a reviewer agent to the options recommendation flow, similar to the stock recommendation system, to create a combined final recommendation based on both the recommender (proposer) and reviewer outputs.

## Current State

### Stock Recommendations
- **Proposer**: Generates top 10 stock picks based on momentum/technical indicators
- **Reviewer**: Filters picks using rule-based or LLM-based criteria (checks ADX, RSI, ATR, p_expand)
- **Analyst**: Creates final recommendations with playbooks from approved picks
- Output structure: `{proposer: {...}, reviewer: {...}, analyst: {...}}`

### Options Recommendations
- **Single Agent**: `OptionRecoAgent` directly generates option recommendations
- No review/filtering step
- Output: Simple array of `OptionReco` objects
- Frontend expects: `recommended_options` array

## Proposed Changes

### 1. Create Options Reviewer Module

#### [NEW] [option_reviewer.py](file:///Users/vinodkeshav/myprojects/stockreco/src/stockreco/agents/option_reviewer.py)

Create a new reviewer agent that applies options-specific filters:

**Review Criteria:**
- **IV Check**: Reject if IV is too high (>60% for strict mode, >80% for opportunistic/speculative)
- **Theta Risk**: Reject if theta decay is too aggressive relative to confidence
- **DTE Check**: Reject if DTE is too low for the mode (strict: ≥5, opportunistic: ≥2, speculative: ≥1)
- **Liquidity**: Reject if OI/volume is too low (when available in diagnostics)
- **Confidence Floor**: Reject if confidence is below mode-specific thresholds
- **Spread Risk**: Reject if entry-to-strike distance suggests poor risk/reward

**Output Structure:**
```python
{
  "approved": [list of approved OptionReco objects],
  "rejected": [
    {"symbol": "...", "reason": "..."},
    ...
  ]
}
```

### 2. Integrate Reviewer into Options Pipeline

#### [MODIFY] [run_eod_option_reco.py](file:///Users/vinodkeshav/myprojects/stockreco/scripts/run_eod_option_reco.py)

Update the main script to:
1. Generate recommendations using `OptionRecoAgent` (proposer/recommender)
2. Pass recommendations through `OptionReviewer` for filtering
3. Create combined output with both recommender and reviewer results
4. Update output format to match stock recommendation structure

**Changes:**
- Import the new `OptionReviewer` class
- After generating recos, apply reviewer filtering
- Create structured output: `{recommender: [...], reviewer: {approved: [...], rejected: [...]}, final: [...]}`
- Keep backward compatibility by also writing the `final` list as the main output

### 3. Update Report Writer

#### [MODIFY] [option_reco_report.py](file:///Users/vinodkeshav/myprojects/stockreco/src/stockreco/report/option_reco_report.py)

Update to handle both old and new output formats:
- Accept either a list of recos (old format) or structured dict with reviewer info (new format)
- Write main JSON with full structure including reviewer details
- Write CSV with approved recommendations only
- Add optional reviewer summary file

### 4. Frontend Compatibility

#### [MODIFY] [OptionsRecommendations.jsx](file:///Users/vinodkeshav/myprojects/stockreco/frontend/src/pages/OptionsRecommendations.jsx)

Update `pickOptionsRows` to handle new structure:
- Check for `final` or `approved` arrays in addition to `recommended_options`
- Maintain backward compatibility with existing format

---

## Verification Plan

### Automated Tests

1. **Unit Test for Reviewer Logic**
   ```bash
   # Create test file: tests/test_option_reviewer.py
   # Run with:
   python -m pytest tests/test_option_reviewer.py -v
   ```
   - Test approval of valid recommendations
   - Test rejection based on IV, theta, DTE, confidence
   - Test mode-specific thresholds

2. **Integration Test**
   ```bash
   # Run the full options recommendation pipeline
   python scripts/run_eod_option_reco.py --as-of 2025-12-13 --universe "NIFTY,BANKNIFTY" --mode strict
   ```
   - Verify output structure includes `recommender`, `reviewer`, and `final` keys
   - Verify CSV and JSON files are created
   - Check that rejected recommendations have reasons

### Manual Verification

1. **Check Output Structure**
   - Inspect `reports/options/option_reco_2025-12-13.json`
   - Verify it contains `recommender`, `reviewer` (with `approved` and `rejected`), and `final` sections
   - Confirm rejected items have clear reasons

2. **Frontend Display**
   - Start the frontend server
   - Navigate to Options Recommendations page
   - Verify recommendations display correctly
   - Check that only approved recommendations are shown

3. **Compare Modes**
   ```bash
   # Run in different modes
   python scripts/run_eod_option_reco.py --mode strict --universe "NIFTY,BANKNIFTY"
   python scripts/run_eod_option_reco.py --mode opportunistic --universe "NIFTY,BANKNIFTY"
   python scripts/run_eod_option_reco.py --mode speculative --universe "NIFTY,BANKNIFTY"
   ```
   - Verify strict mode has more rejections
   - Verify speculative mode is more permissive
   - Check reviewer reasons match mode-specific criteria

---

## Implementation Notes

- The reviewer will be **rule-based** (not LLM-based) to keep it fast and deterministic
- Maintain backward compatibility in output format
- Use similar structure to stock recommendation reviewer for consistency
- Add detailed rejection reasons for transparency
- Mode-aware thresholds to match the agent's mode configuration
