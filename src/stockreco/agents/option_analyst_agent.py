from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

from stockreco.agents.option_reco_agent import OptionReco
# Optional LLM integration
try:
    from stockreco.agents.options_llm import analyze_options_llm
except ImportError:
    analyze_options_llm = None

@dataclass
class AnalystRecommendation:
    """container for a final analyst recommendation"""
    symbol: str
    reco: OptionReco  # The original recommendation
    final_verdict: str  # "STRONG_BUY", "BUY", "WATCH", "AVOID"
    analyst_confidence: float  # Adjusted confidence
    analysis_summary: str  # Human readable thesis
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "reco": self.reco.to_dict(),
            "final_verdict": self.final_verdict,
            "analyst_confidence": self.analyst_confidence,
            "analysis_summary": self.analysis_summary
        }

class OptionAnalystAgent:
    """
    The Analyst Layer runs AFTER the Reviewer.
    It takes the approved options and performs a final deep-dive analysis.
    
    Capabilities:
    1. Cross-checks with Market Context (FII, Volatility) - although Agent did this, Analyst verifies it strictly.
    2. Applies qualitative rules (e.g. strict confidence thresholds for STRONG BUY).
    3. If LLM is enabled, uses it to generate the qualitative thesis.
    """
    
    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm

    def analyze(self, approved_recos: List[OptionReco], as_of: str, 
               vol_map: Dict[str, float] = None, fii_sent: float = 0.0) -> List[AnalystRecommendation]:
        
        results: List[AnalystRecommendation] = []
        
        # 1. Rule-Based Analysis First
        for reco in approved_recos:
            verdict = "BUY"
            summary = "Standard algorithmic approval."
            conf = reco.confidence
            
            # --- Rule: Absolute Confidence Thresholds ---
            if conf >= 0.85:
                verdict = "STRONG_BUY"
                summary = f"High confidence ({conf:.2f}) algorithmic signal."
            elif conf < 0.60:
                verdict = "WATCH"
                summary = f"Moderate confidence ({conf:.2f}); actionable but higher risk."
            
            # --- Rule: FII Conflict Check (Double Check) ---
            # If agent didn't catch it or for emphasizing risk
            if fii_sent != 0.0:
                if (reco.side == "CE" and fii_sent < -0.5) or (reco.side == "PE" and fii_sent > 0.5):
                     # Strong conflict against major FII positioning
                     if verdict == "STRONG_BUY":
                         verdict = "BUY" # Downgrade
                         summary += " Downgraded from Strong Buy due to opposing FII sentiment."
                     elif verdict == "BUY":
                         # Maintain buy but warn
                         summary += " Caution: Trading against strong FII positioning."

            # --- Rule: Smart Money Score (Participant OI) ---
            # Added for contextual awareness
            sm_score = getattr(reco, "smart_money_score", 0.0) or 0.0
            if abs(sm_score) > 0.3:
                 if (reco.side == "CE" and sm_score > 0) or (reco.side == "PE" and sm_score < 0):
                     summary += f" Smart Money supports this trade (Score {sm_score:.2f})."
                 else:
                     summary += f" WARNING: Smart Money is opposing (Score {sm_score:.2f})."
            
            # --- Rule: PCR Context ---
            pcr = getattr(reco, "pcr", 0.0) or 0.0
            if pcr > 0:
                if pcr > 1.5:
                    summary += f" PCR({pcr:.2f}) is elevated (Overbought risk)."
                elif pcr < 0.6:
                    summary += f" PCR({pcr:.2f}) is low (Oversold risk)."

            # --- Rule: Volatility Extremes ---
            # Agent handles this, but Analyst confirms.
            # If iv is very high (>50%) and we are buying, downgrade to WATCH
            # Note: reco.iv is usually percentage (e.g. 25.0 = 25%) but handle both scales just in case
            is_extreme = False
            if reco.iv:
                # heuristic: if > 2.0, likely percentage. if < 1.0, likely decimal. 
                # but 1.5% IV is possible. 
                # Standard OptionReco output is percentage (e.g. 17.16).
                if reco.iv > 50.0:
                    is_extreme = True
            
            if is_extreme:
                verdict = "WATCH"
                summary = "Downgraded to WATCH due to extreme Implied Volatility (>50%); risk of crush."

            results.append(AnalystRecommendation(
                symbol=reco.symbol,
                reco=reco,
                final_verdict=verdict,
                analyst_confidence=conf,
                analysis_summary=summary
            ))

        # 2. LLM Analysis (Enhancement)
        if self.use_llm and analyze_options_llm:
            try:
                # Prepare dicts for LLM
                candidates_for_llm = []
                for res in results:
                    r = res.reco
                    # Only analyze actionable BUYs (which they should be if they passed reviewer)
                    if r.action == "BUY":
                        candidates_for_llm.append({
                            "symbol": r.symbol,
                            "action": r.action,
                            "side": r.side,
                            "strike": r.strike,
                            "expiry": r.expiry,
                            "confidence": res.analyst_confidence,
                            "entry": r.entry_price,
                            "iv": r.iv,
                            "theta_per_day": r.theta_per_day,
                            "rationale": r.rationale,
                            "diagnostics": r.diagnostics
                        })

                if candidates_for_llm:
                    print(f"  [Analyst] Sending {len(candidates_for_llm)} trades to LLM Analyst...")
                    llm_out = analyze_options_llm(candidates_for_llm, as_of)
                    
                    # Merge LLM insights
                    analysis_map = {item["symbol"]: item for item in llm_out.get("recommendations", [])}
                    final_notes = llm_out.get("final_notes", "")
                    
                    for res in results:
                        if res.symbol in analysis_map:
                            ana = analysis_map[res.symbol]
                            
                            # Replace summary with LLM thesis
                            res.analysis_summary = ana.get("rationale_summary", res.analysis_summary)
                            
                            # Apply confidence adjustment
                            adj = ana.get("confidence_adjustment", 0.0)
                            if adj:
                                old_c = res.analyst_confidence
                                new_c = max(0.0, min(1.0, old_c + adj))
                                res.analyst_confidence = new_c
                                # Adjust verdict based on new confidence
                                if new_c >= 0.85: res.final_verdict = "STRONG_BUY"
                                elif new_c < 0.60: res.final_verdict = "WATCH"
                                else: res.final_verdict = "BUY"
                                
            except Exception as e:
                print(f"  [Analyst] LLM enhancement failed: {e}")
                
        return results
