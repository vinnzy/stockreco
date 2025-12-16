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
    
    def review(self, recommendations: List[Any]) -> Tuple[List[Any], List[Dict[str, str]]]:
        """
        Review a list of option recommendations.
        
        Args:
            recommendations: List of OptionReco objects or dicts
            
        Returns:
            Tuple of (approved_list, rejected_list)
            - approved_list: recommendations that passed all filters
            - rejected_list: list of dicts with {symbol, reason}
        """
        approved = []
        rejected = []
        
        for reco in recommendations:
            # Convert to dict if needed
            if hasattr(reco, "to_dict"):
                reco_dict = reco.to_dict()
            elif isinstance(reco, dict):
                reco_dict = reco
            else:
                reco_dict = getattr(reco, "__dict__", {})
            
            # Skip HOLD recommendations (already neutral)
            if reco_dict.get("action") == "HOLD":
                approved.append(reco)
                continue
            
            # Apply filters
            rejection_reason = self._check_recommendation(reco_dict)
            
            if rejection_reason:
                rejected.append({
                    "symbol": reco_dict.get("symbol", "UNKNOWN"),
                    "side": reco_dict.get("side"),
                    "strike": reco_dict.get("strike"),
                    "expiry": reco_dict.get("expiry"),
                    "reason": rejection_reason
                })
            else:
                approved.append(reco)
        
        return approved, rejected
    
    def _check_recommendation(self, reco: Dict[str, Any]) -> str:
        """
        Check a single recommendation against all filters.
        
        Returns:
            Empty string if approved, rejection reason if rejected
        """
        symbol = reco.get("symbol", "UNKNOWN")
        
        # 1. Confidence check
        confidence = float(reco.get("confidence", 0.0))
        min_conf = self._min_confidence()
        if confidence < min_conf:
            return f"Confidence {confidence:.2f} below {min_conf:.2f} threshold for {self.cfg.mode} mode"
        
        # 2. DTE check
        dte = reco.get("dte")
        if dte is not None:
            min_dte = self._min_dte()
            if dte < min_dte:
                return f"DTE {dte} below minimum {min_dte} for {self.cfg.mode} mode (theta cliff risk)"
        
        # 3. IV check
        iv = reco.get("iv")
        if iv is not None:
            max_iv = self._max_iv()
            if iv > max_iv:
                return f"IV {iv:.1f}% exceeds {max_iv:.1f}% threshold (high premium/IV crush risk)"
        
        # 4. Theta decay check
        theta_per_day = reco.get("theta_per_day")
        entry_price = reco.get("entry_price")
        if theta_per_day is not None and entry_price is not None and entry_price > 0:
            theta_pct = abs(theta_per_day) / entry_price
            max_theta = self._max_theta_pct()
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
    mode: Mode = "strict"
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
    
    approved, rejected = reviewer.review(recommendations)
    
    return {
        "recommender": recommendations,
        "reviewer": {
            "approved": approved,
            "rejected": rejected
        },
        "final": approved
    }
