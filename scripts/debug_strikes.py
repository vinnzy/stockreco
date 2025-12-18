import pandas as pd
from pathlib import Path

def main():
    repo = Path(".").resolve()
    as_of = "2025-12-16"
    csv_path = repo / "data/derivatives" / as_of / "op16122025.csv"
    
    print(f"Reading {csv_path}...")
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().upper() for c in df.columns]
    
    # Filter RELIANCE
    rel = df[df["SYMBOL"].str.strip().str.upper() == "RELIANCE"]
    if rel.empty:
        print("RELIANCE not found in options CSV.")
        return
        
    print(f"Found {len(rel)} rows.")
    strikes = sorted(rel["STR_PRICE"].unique())
    print(f"Unique Strikes: {strikes}")
    
    # Check closeness to 1542
    nearby = [s for s in strikes if 1400 <= s <= 1700]
    print(f"Strikes near 1542: {nearby}")

if __name__ == "__main__":
    main()
