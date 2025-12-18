import pandas as pd
from pathlib import Path

def main():
    repo = Path(".").resolve()
    as_of = "2025-12-16"
    csv_path = repo / "data/derivatives" / as_of / "op16122025.csv"
    
    print(f"Reading {csv_path}...")
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().upper() for c in df.columns]
    print("Columns found in CSV:")
    print(list(df.columns))

if __name__ == "__main__":
    main()
