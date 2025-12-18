import sys
import os
sys.path.append(os.path.abspath("src"))  # Ensure src is in path

import unittest
from datetime import datetime
from stockreco.agents.option_reco_agent import OptionRecoAgent, OptionRecoConfig
from stockreco.ingest.derivatives.provider_base import OptionChainRow, UnderlyingSnapshot

class TestOptionExpiryLogic(unittest.TestCase):
    def setUp(self):
        self.agent = OptionRecoAgent()
        # Ensure strict mode / defaults
        self.agent.cfg.min_oi = 1000
        self.agent.cfg.min_volume = 500
        self.agent.cfg.margin_period_days = 5
        self.as_of = "2025-12-15"
        self.expiry_near = "2025-12-17"  # DTE=2 (Danger)
        self.expiry_next = "2025-12-30"  # DTE=15 (Safe)
        
        self.spot = 1000.0
        # UnderlyingSnapshot has symbol, spot, as_of_iso
        self.underlying = UnderlyingSnapshot(symbol="TEST", spot=self.spot, as_of_iso=self.as_of)
        
        # Base signal row
        self.signal_row = {
            "buy_win": 10, "sell_win": 0, "direction_score": 0.5,
            "atr_points": 20.0, "atr_pct": 0.02,
            "volatility_annualized": 0.25
        }

    def _make_row(self, expiry, strike, oi, volume, ltp=50.0, side="CE"):
        # OptionChainRow has strike, expiry, option_type, ltp, ... (no symbol, no timestamp)
        return OptionChainRow(
            strike=strike, expiry=expiry, option_type=side,
            ltp=ltp, bid=49.0, ask=51.0, volume=volume, oi=oi,
            oi_change=0, iv=0.20
        )

    def test_liquidity_filtering(self):
        # Create a chain with one illiquid and one liquid option
        illiquid = self._make_row(self.expiry_next, 1020, 100.0, 100.0) # OI < 1000
        liquid = self._make_row(self.expiry_next, 1020, 5000.0, 5000.0)
        
        # Pass both
        reco = self.agent.recommend(self.as_of, "TEST", self.signal_row, self.underlying, [illiquid, liquid])
        
        # Should result in BUY
        self.assertEqual(reco.action, "BUY")
        
        # Test ONLY illiquid
        reco_ill = self.agent.recommend(self.as_of, "TEST", self.signal_row, self.underlying, [illiquid])
        self.assertEqual(reco_ill.action, "HOLD")
        self.assertIn("No suitable CE options", reco_ill.rationale[0])

    def test_stock_expiry_rollover(self):
        # Stock: Danger zone expiry + Safe expiry available. Should pick Safe.
        danger = self._make_row(self.expiry_near, 1020, 5000.0, 5000.0)
        safe = self._make_row(self.expiry_next, 1020, 5000.0, 5000.0)
        
        reco = self.agent.recommend(self.as_of, "TEST", self.signal_row, self.underlying, [danger, safe])
        
        self.assertEqual(reco.action, "BUY")
        self.assertEqual(reco.expiry, self.expiry_next)
        self.assertNotEqual(reco.sell_by, self.as_of) # Should not be intraday

    def test_stock_expiry_forced_intraday(self):
        # Stock: Only Danger zone expiry available. Should be Intraday.
        danger = self._make_row(self.expiry_near, 1020, 5000.0, 5000.0)
        
        reco = self.agent.recommend(self.as_of, "TEST", self.signal_row, self.underlying, [danger])
        
        self.assertEqual(reco.action, "BUY")
        self.assertEqual(reco.expiry, self.expiry_near)
        self.assertEqual(reco.sell_by, self.as_of) # Forced Intraday
        self.assertTrue(any("Capping to INTRADAY" in r for r in reco.rationale))

    def test_index_expiry_no_cap(self):
        # Index: Danger zone expiry. Should NOT be Intraday.
        danger = OptionChainRow(
            strike=1020, expiry=self.expiry_near, option_type="CE",
            ltp=50.0, bid=49.0, ask=51.0, volume=5000.0, oi=5000.0,
            oi_change=0, iv=0.20
        )
        
        # Mock underlying symbol too
        underlying = UnderlyingSnapshot(symbol="NIFTY", spot=1000.0, as_of_iso=self.as_of)

        reco = self.agent.recommend(self.as_of, "NIFTY", self.signal_row, underlying, [danger])
        
        self.assertEqual(reco.action, "BUY")
        self.assertEqual(reco.expiry, self.expiry_near)
        self.assertNotEqual(reco.sell_by, self.as_of)
        self.assertFalse(any("Capping to INTRADAY" in r for r in reco.rationale))

if __name__ == "__main__":
    unittest.main()
