import unittest
from dataclasses import dataclass
from typing import List, Optional
import sys
import os

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from stockreco.agents.option_reco_agent import OptionRecoAgent, OptionRecoConfig, OptionReco
from stockreco.ingest.derivatives.provider_base import OptionChainRow, UnderlyingSnapshot

class TestOptionRecoLogic(unittest.TestCase):
    def setUp(self):
        self.cfg = OptionRecoConfig(mode="strict")
        self.agent = OptionRecoAgent(self.cfg)
        
        # Mock Underlying
        self.underlying = UnderlyingSnapshot(
            symbol="TEST",
            spot=1000.0,
            as_of_iso="2025-12-17"
        )
        
        # Mock Option Chain
        # Create a few strikes around 1000
        self.chain = []
        for strike in [950, 960, 970, 980, 990, 1000, 1010, 1020, 1030, 1040, 1050]:
            # Call
            ltp = max(2.0, 1000.0 - strike + 10.0)
            self.chain.append(OptionChainRow(
                strike=float(strike), expiry="2025-12-25", option_type="CE",
                volume=5000.0, ltp=ltp,
                bid=ltp-0.5, ask=ltp+0.5, iv=0.20, oi=10000.0
            ))
            # Put
            ltp = max(2.0, strike - 1000.0 + 10.0)
            self.chain.append(OptionChainRow(
                strike=float(strike), expiry="2025-12-25", option_type="PE",
                volume=5000.0, ltp=ltp,
                bid=ltp-0.5, ask=ltp+0.5, iv=0.20, oi=10000.0
            ))

    def test_smart_money_boost(self):
        # Bullish Signal
        signal_row = {
            "ticker": "TEST",
            "buy_win": 1,
            "sell_win": 0,
            "strength": 0.5,
            "smart_money_score": 0.8, # Strong Bullish FII
            "pcr": 1.0
        }
        
        reco = self.agent.recommend("2025-12-17", "TEST", signal_row, self.underlying, self.chain)
        
        if reco.action != "BUY":
            print(f"\n[DEBUG] Reco is {reco.action}. Rationale: {reco.rationale}")
            
        # Should be a BUY CE
        self.assertIsNotNone(reco)
        self.assertEqual(reco.action, "BUY")
        self.assertEqual(reco.side, "CE")
        print(f"\n[Test Smart Money] Conf: {reco.confidence}, SmartMoneyScore: {reco.smart_money_score}")
        self.assertEqual(reco.smart_money_score, 0.8)
        # Verify rationale mentions smart money
        found = any("Smart Money Bullish" in r for r in reco.rationale)
        self.assertTrue(found, "Rationale should mention Smart Money Bullish")

    def test_smart_money_penalty(self):
        # Bullish Signal but Bearish Smart Money
        signal_row = {
            "ticker": "TEST",
            "buy_win": 1,
            "sell_win": 0,
            "strength": 0.5,
            "smart_money_score": -0.8, # Strong Bearish FII
            "pcr": 1.0
        }
        
        reco = self.agent.recommend("2025-12-17", "TEST", signal_row, self.underlying, self.chain)
        
        # Logic might penalize confidence heavily or flip bias?
        # Current logic: Conf *= 0.70
        if reco and reco.action == "BUY":
             print(f"\n[Test Smart Money Penalty] Conf: {reco.confidence}, SmartMoneyScore: {reco.smart_money_score}")
             found = any("Smart Money Bearish" in r for r in reco.rationale)
             self.assertTrue(found, "Rationale should mention Smart Money Bearish penalty")
             
    def test_pcr_filter(self):
        # Bullish Signal but High PCR (Overbought)
        signal_row = {
            "ticker": "TEST",
            "buy_win": 1,
            "sell_win": 0,
            "strength": 0.5,
            "smart_money_score": 0.0,
            "pcr": 1.7
        }
        
        reco = self.agent.recommend("2025-12-17", "TEST", signal_row, self.underlying, self.chain)
        
        if reco and reco.action == "BUY" and reco.side == "CE":
             print(f"\n[Test PCR High] Conf: {reco.confidence}, PCR: {reco.pcr}")
             found = any("High PCR" in r for r in reco.rationale)
             self.assertTrue(found, "Rationale should warn about High PCR")

if __name__ == '__main__':
    unittest.main()
