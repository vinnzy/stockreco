#!/usr/bin/env python3
"""
Unit tests for the OptionReviewer module.
Tests approval and rejection logic for various scenarios.
"""

from stockreco.agents.option_reviewer import OptionReviewer, ReviewerConfig


def test_approval_valid_recommendation():
    """Test that a valid recommendation is approved."""
    reviewer = OptionReviewer(ReviewerConfig(mode="strict"))
    
    reco = {
        "symbol": "NIFTY",
        "action": "BUY",
        "confidence": 0.45,
        "dte": 7,
        "iv": 45.0,
        "theta_per_day": 5.0,
        "entry_price": 100.0,
        "strike": 24000.0,
        "side": "CE"
    }
    
    approved, rejected = reviewer.review([reco])
    
    assert len(approved) == 1, "Valid recommendation should be approved"
    assert len(rejected) == 0, "No rejections expected"
    print("✓ Test passed: Valid recommendation approved")


def test_rejection_low_confidence():
    """Test rejection due to low confidence."""
    reviewer = OptionReviewer(ReviewerConfig(mode="strict"))
    
    reco = {
        "symbol": "NIFTY",
        "action": "BUY",
        "confidence": 0.25,  # Below strict threshold of 0.35
        "dte": 7,
        "iv": 45.0,
        "side": "CE"
    }
    
    approved, rejected = reviewer.review([reco])
    
    assert len(approved) == 0, "Low confidence should be rejected"
    assert len(rejected) == 1, "Should have one rejection"
    assert "Confidence" in rejected[0]["reason"]
    print(f"✓ Test passed: Low confidence rejected - {rejected[0]['reason']}")


def test_rejection_low_dte():
    """Test rejection due to low DTE (theta cliff risk)."""
    reviewer = OptionReviewer(ReviewerConfig(mode="strict"))
    
    reco = {
        "symbol": "BANKNIFTY",
        "action": "BUY",
        "confidence": 0.50,
        "dte": 3,  # Below strict minimum of 5
        "iv": 45.0,
        "side": "PE"
    }
    
    approved, rejected = reviewer.review([reco])
    
    assert len(approved) == 0, "Low DTE should be rejected in strict mode"
    assert len(rejected) == 1, "Should have one rejection"
    assert "DTE" in rejected[0]["reason"]
    print(f"✓ Test passed: Low DTE rejected - {rejected[0]['reason']}")


def test_rejection_high_iv():
    """Test rejection due to high IV."""
    reviewer = OptionReviewer(ReviewerConfig(mode="strict"))
    
    reco = {
        "symbol": "NIFTY",
        "action": "BUY",
        "confidence": 0.50,
        "dte": 7,
        "iv": 75.0,  # Above strict threshold of 60%
        "side": "CE"
    }
    
    approved, rejected = reviewer.review([reco])
    
    assert len(approved) == 0, "High IV should be rejected"
    assert len(rejected) == 1, "Should have one rejection"
    assert "IV" in rejected[0]["reason"]
    print(f"✓ Test passed: High IV rejected - {rejected[0]['reason']}")


def test_rejection_high_theta():
    """Test rejection due to excessive theta decay."""
    reviewer = OptionReviewer(ReviewerConfig(mode="strict"))
    
    reco = {
        "symbol": "NIFTY",
        "action": "BUY",
        "confidence": 0.50,
        "dte": 7,
        "iv": 45.0,
        "theta_per_day": 12.0,  # 12% of entry per day
        "entry_price": 100.0,
        "side": "CE"
    }
    
    approved, rejected = reviewer.review([reco])
    
    assert len(approved) == 0, "High theta decay should be rejected"
    assert len(rejected) == 1, "Should have one rejection"
    assert "Theta" in rejected[0]["reason"]
    print(f"✓ Test passed: High theta rejected - {rejected[0]['reason']}")


def test_mode_opportunistic_more_permissive():
    """Test that opportunistic mode is more permissive than strict."""
    strict_reviewer = OptionReviewer(ReviewerConfig(mode="strict"))
    opp_reviewer = OptionReviewer(ReviewerConfig(mode="opportunistic"))
    
    # Recommendation that fails strict but passes opportunistic
    reco = {
        "symbol": "NIFTY",
        "action": "BUY",
        "confidence": 0.30,  # Below strict (0.35) but above opportunistic (0.28)
        "dte": 3,  # Below strict (5) but above opportunistic (2)
        "iv": 65.0,  # Above strict (60) but below opportunistic (80)
        "side": "CE"
    }
    
    strict_approved, strict_rejected = strict_reviewer.review([reco])
    opp_approved, opp_rejected = opp_reviewer.review([reco])
    
    assert len(strict_approved) == 0, "Should be rejected in strict mode"
    assert len(opp_approved) == 1, "Should be approved in opportunistic mode"
    print("✓ Test passed: Opportunistic mode is more permissive")


def test_hold_recommendations_always_approved():
    """Test that HOLD recommendations are always approved."""
    reviewer = OptionReviewer(ReviewerConfig(mode="strict"))
    
    reco = {
        "symbol": "NIFTY",
        "action": "HOLD",
        "confidence": 0.10,  # Very low confidence
        "dte": 1,  # Very low DTE
        "iv": 90.0,  # Very high IV
        "side": None
    }
    
    approved, rejected = reviewer.review([reco])
    
    assert len(approved) == 1, "HOLD recommendations should always be approved"
    assert len(rejected) == 0, "No rejections for HOLD"
    print("✓ Test passed: HOLD recommendations always approved")


def test_multiple_recommendations():
    """Test reviewing multiple recommendations at once."""
    reviewer = OptionReviewer(ReviewerConfig(mode="strict"))
    
    recos = [
        {"symbol": "NIFTY", "action": "BUY", "confidence": 0.50, "dte": 7, "iv": 45.0, "side": "CE"},
        {"symbol": "BANKNIFTY", "action": "BUY", "confidence": 0.25, "dte": 7, "iv": 45.0, "side": "PE"},  # Low conf
        {"symbol": "RELIANCE", "action": "BUY", "confidence": 0.50, "dte": 2, "iv": 45.0, "side": "CE"},  # Low DTE
        {"symbol": "TCS", "action": "HOLD", "confidence": 0.10, "dte": 1, "iv": 90.0, "side": None},  # HOLD
    ]
    
    approved, rejected = reviewer.review(recos)
    
    assert len(approved) == 2, "Should approve 2 (1 valid BUY + 1 HOLD)"
    assert len(rejected) == 2, "Should reject 2 (low conf + low DTE)"
    print(f"✓ Test passed: Multiple recommendations - {len(approved)} approved, {len(rejected)} rejected")


if __name__ == "__main__":
    print("Running OptionReviewer unit tests...\n")
    
    try:
        test_approval_valid_recommendation()
        test_rejection_low_confidence()
        test_rejection_low_dte()
        test_rejection_high_iv()
        test_rejection_high_theta()
        test_mode_opportunistic_more_permissive()
        test_hold_recommendations_always_approved()
        test_multiple_recommendations()
        
        print("\n" + "="*50)
        print("All tests passed! ✓")
        print("="*50)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
