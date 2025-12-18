from __future__ import annotations

from typing import List, Dict, Any, Tuple, Literal
from dataclasses import dataclass

Mode = Literal["strict", "opportunistic", "speculative"]


@dataclass
class ReviewerConfig:
    """Configuration for options reviewer thresholds."""
    mode: Mode = "strict"
    
    # IV thresholds (as percentage, e.g., 60 = 60%)
    strict_max_iv: float = 60.0
    opp_max_iv: float = 80.0
    spec_max_iv: float = 100.0
    
    # Confidence floors
    strict_min_confidence: float = 0.35
    opp_min_confidence: float = 0.28
    spec_min_confidence: float = 0.22
    
    # DTE minimums
    strict_min_dte: int = 5
    opp_min_dte: int = 2
    spec_min_dte: int = 1
    
    # Theta risk: max theta decay as % of entry price per day
    # Theta risk: max theta decay as % of entry price per day
    strict_max_theta_pct: float = 0.08  # 8% per day
    opp_max_theta_pct: float = 0.12     # 12% per day
    spec_max_theta_pct: float = 0.15    # 15% per day
    
    # Minimum OI (if available)
    min_oi: float = 0.0  # 0 = no filter
    
    # Risk/reward check: entry should be reasonable vs strike distance
    max_entry_strike_ratio: float = 0.15  # entry < 15% of strike for OTM


class OptionReviewer:
    """
    Rule-based reviewer for options recommendations.
    Filters out high-risk or low-quality option picks based on:
    - IV levels
    - Theta decay risk
    - DTE constraints
    - Confidence thresholds
    - Liquidity (OI)
    """
    
    def __init__(self, cfg: ReviewerConfig = None):
        self.cfg = cfg or ReviewerConfig()
    
    def _max_iv(self) -> float:
        """Get max IV threshold for current mode."""
        if self.cfg.mode == "opportunistic":
            return self.cfg.opp_max_iv
        if self.cfg.mode == "speculative":
            return self.cfg.spec_max_iv
        return self.cfg.strict_max_iv
    
    def _min_confidence(self) -> float:
        """Get min confidence threshold for current mode."""
        if self.cfg.mode == "opportunistic":
            return self.cfg.opp_min_confidence
        if self.cfg.mode == "speculative":
            return self.cfg.spec_min_confidence
        return self.cfg.strict_min_confidence
    
    def _min_dte(self) -> int:
        """Get min DTE threshold for current mode."""
        if self.cfg.mode == "opportunistic":
            return self.cfg.opp_min_dte
        if self.cfg.mode == "speculative":
            return self.cfg.spec_min_dte
        return self.cfg.strict_min_dte
    
    def _max_theta_pct(self) -> float:
        """Get max theta decay % threshold for current mode."""
        if self.cfg.mode == "opportunistic":
            return self.cfg.opp_max_theta_pct
        if self.cfg.mode == "speculative":
            return self.cfg.spec_max_theta_pct
        return self.cfg.strict_max_theta_pct
    
    def review(self, recommendations: List[Any], vix: Optional[float] = None) -> Tuple[List[Any], List[Dict[str, str]]]:
        """
        Review a list of option recommendations.
        NEW: Accepts 'vix' to dynamically adjust strictness.
        """
        approved = []
        rejected = []
        
        # Dynamic Regime Adjustment
        effective_mode = self.cfg.mode
        regime_note = ""
        
        if vix is not None and vix > 0:
            if vix > 22.0:
                if effective_mode != "strict":
                    effective_mode = "strict"
                    regime_note = f" [Market Regime: High VIX ({vix:.1f}) -> Enforcing STRICT mode]"
            elif vix < 12.0:
                 if effective_mode == "strict":
                     effective_mode = "opportunistic"
                     regime_note = f" [Market Regime: Low VIX ({vix:.1f}) -> Allowing OPPORTUNISTIC mode]"
        
        for reco in recommendations:
            # Convert to dict if needed
            if hasattr(reco, "to_dict"):
                reco_dict = reco.to_dict()
            elif isinstance(reco, dict):
                reco_dict = reco
            else:
                reco_dict = getattr(reco, "__dict__", {})
            
            # Skip HOLD recommendations (already neutral)
            # Do NOT add to approved list (approved means valid signal to trade)
            # Skip HOLD recommendations (already neutral)
            # Do NOT add to approved list (approved means valid signal to trade)
            if reco_dict.get("action") == "HOLD":
                # Check if it was due to an error, so we can expose it in Rejected list
                rats = reco_dict.get("rationale", [])
                # If rationale contains explicit failure message
                if any(("Failed to load" in str(r) or "Error" in str(r)) for r in rats):
                   rejected.append({
                        "symbol": reco_dict.get("symbol", "UNKNOWN"),
                        "side": "N/A",
                        "strike": "N/A",
                        "expiry": "N/A",
                        "reason": f"System Error: {'; '.join(str(r) for r in rats)}"
                    })
                continue
            
            # Apply filters
            rejection_reason = self._check_recommendation(reco_dict, effective_mode)
            
            if rejection_reason:
                rejected.append({
                    "symbol": reco_dict.get("symbol", "UNKNOWN"),
                    "side": reco_dict.get("side"),
                    "strike": reco_dict.get("strike"),
                    "expiry": reco_dict.get("expiry"),
                    "reason": rejection_reason + regime_note
                })
            else:
                if regime_note:
                    # Append regime note to rationale if possible
                    existing = reco_dict.get("rationale", [])
                    if isinstance(existing, list):
                        existing.append(regime_note.strip())
                approved.append(reco)
        
        return approved, rejected
    
    def _check_recommendation(self, reco: Dict[str, Any], mode_override: Optional[str] = None) -> str:
        """
        Check a single recommendation against all filters.
        
        Returns:
            Empty string if approved, rejection reason if rejected
        """
        symbol = reco.get("symbol", "UNKNOWN")
        mode = mode_override or self.cfg.mode
        
        # 1. Confidence check
        confidence = float(reco.get("confidence", 0.0))
        # 1. Min Confidence
        min_conf = {
            "strict": self.cfg.strict_min_confidence,
            "opportunistic": self.cfg.opp_min_confidence,
            "speculative": self.cfg.spec_min_confidence,
        }.get(mode, self.cfg.strict_min_confidence)

        if confidence < min_conf:
            return f"Confidence {confidence:.2f} below {min_conf:.2f} threshold for {mode} mode"
        
        # 2. DTE check
        dte = reco.get("dte")
        if dte is not None:
            # 2. Min DTE
            min_dte = {
                "strict": self.cfg.strict_min_dte,
                "opportunistic": self.cfg.opp_min_dte,
                "speculative": self.cfg.spec_min_dte,
            }.get(mode, self.cfg.strict_min_dte)
            
            if dte < min_dte:
                return f"DTE {dte} below minimum {min_dte} for {mode} mode (theta cliff risk)"
        
        # 3. IV check
        iv = reco.get("iv")
        if iv is not None:
             # 3. Max IV
            max_iv = {
                "strict": self.cfg.strict_max_iv,
                "opportunistic": self.cfg.opp_max_iv,
                "speculative": self.cfg.spec_max_iv,
            }.get(mode, self.cfg.strict_max_iv)
            
            if iv > max_iv:
                return f"IV {iv:.1f}% exceeds {max_iv:.1f}% threshold (high premium/IV crush risk)"
        
        # 4. Theta decay check
        theta_per_day = reco.get("theta_per_day")
        entry_price = reco.get("entry_price")
        if theta_per_day is not None and entry_price is not None and entry_price > 0:
            theta_pct = abs(theta_per_day) / entry_price
             # 4. Max Theta
            max_theta = {
                "strict": self.cfg.strict_max_theta_pct,
                "opportunistic": self.cfg.opp_max_theta_pct,
                "speculative": self.cfg.spec_max_theta_pct,
            }.get(mode, self.cfg.strict_max_theta_pct)
            
            if theta_pct > max_theta:
                return f"Theta decay {theta_pct*100:.1f}% of entry per day exceeds {max_theta*100:.1f}% threshold"
        
        # 5. Liquidity check (OI)
        if self.cfg.min_oi > 0:
            diagnostics = reco.get("diagnostics") or {}
            oi = diagnostics.get("oi", 0)
            if oi < self.cfg.min_oi:
                return f"Open Interest {oi} below minimum {self.cfg.min_oi} (liquidity risk)"
        
        # 6. Entry/Strike sanity check (avoid overpaying for far OTM)
        entry_price = reco.get("entry_price")
        strike = reco.get("strike")
        if entry_price and strike and strike > 0:
            ratio = entry_price / strike
            if ratio > self.cfg.max_entry_strike_ratio:
                return f"Entry/Strike ratio {ratio:.2%} too high (likely overpriced OTM option)"
        
        # All checks passed
        return ""


def review_option_recommendations(
    recommendations: List[Any],
    mode: Mode = "strict",
    vix: Optional[float] = None
) -> Dict[str, Any]:
    """
    Convenience function to review option recommendations.
    
    Args:
        recommendations: List of OptionReco objects or dicts
        mode: Review mode (strict/opportunistic/speculative)
        
    Returns:
        Dict with keys:
        - recommender: original recommendations
        - reviewer: {approved: [...], rejected: [{symbol, reason}, ...]}
        - final: approved recommendations only
    """
    cfg = ReviewerConfig(mode=mode)
    reviewer = OptionReviewer(cfg)
    
    approved, rejected = reviewer.review(recommendations, vix=vix)
    
    return {
        "recommender": recommendations,
        "reviewer": {
            "approved": approved,
            "rejected": rejected
        },
        "final": approved
    }
