import pandas as pd
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(".").resolve() / "src"))
from stockreco.ingest.derivatives.local_csv_provider import LocalCsvProvider

def main():
    repo = Path(".").resolve()
    as_of = "2025-12-16"
    
    # 1. Inspect Raw CSV for RELIANCE
    csv_path = repo / "data/derivatives" / as_of / "op16122025.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df.columns = [c.strip().upper() for c in df.columns]
        
        # Filter for RELIANCE
        rel = df[df["SYMBOL"] == "RELIANCE"]
        if not rel.empty:
            print(f"\nRELIANCE Option Rows: {len(rel)}")
            print("Strikes sample:", rel["STR_PRICE"].unique()[:10])
            print("LTP sample:", rel["CLOSE_PRICE"].head(5).values)
        else:
            print("RELIANCE not found in op file.")

    # 2. Check Equity Bhavcopy for Spot
    stock_dir = repo / "data/stocks" / as_of
    bhav = list(stock_dir.glob("sec_bhavdata_full*.csv"))
    if bhav:
        df_eq = pd.read_csv(bhav[0])
        df_eq.columns = [c.strip().upper() for c in df_eq.columns]
        rel_eq = df_eq[df_eq["SYMBOL"] == "RELIANCE"]
        if not rel_eq.empty:
             print(f"\nRELIANCE Equity Spot (Bhavcopy): {rel_eq['CLOSE_PRICE'].values[0]}")
        else:
             print("RELIANCE not found in Equity Bhavcopy")
