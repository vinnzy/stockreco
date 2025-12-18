#!/usr/bin/env python3
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from stockreco.ingest.market_context import MarketContextLoader

def main():
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data"
    
    loader = MarketContextLoader(data_dir)
    as_of = "2025-12-16"
    
    print(f"Loading context for {as_of}...")
    ctx = loader.load_context(as_of)
    
    print(f"\n--- Statistics for {as_of} ---")
    print(f"Volatility Entries: {len(ctx.volatility)}")
    print(f"Participant OI Types: {list(ctx.participant_oi.keys())}")
    print(f"Bulk Deal Symbols: {len(ctx.bulk_deals)}")
    print(f"Delivery Stats Entries: {len(ctx.delivery_stats)}")
    
    if ctx.volatility:
        sample_sym = list(ctx.volatility.keys())[0]
        print(f"\nSample Volatility ({sample_sym}): {ctx.volatility[sample_sym]}")

    if ctx.participant_oi:
        print(f"\nFII Stats: {ctx.participant_oi.get('FII')}")
        
    if ctx.bulk_deals:
        sample_sym = list(ctx.bulk_deals.keys())[0]
        print(f"\nSample Bulk Deal ({sample_sym}): {ctx.bulk_deals[sample_sym]}")

    if ctx.volatility and ctx.participant_oi and ctx.bulk_deals:
        print("\n✅ Verification SUCCESS: All data types loaded.")
    else:
        print("\n⚠️ Verification WARNING: Some data types empty.")

if __name__ == "__main__":
    main()
