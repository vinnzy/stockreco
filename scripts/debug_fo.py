import pandas as pd
from pathlib import Path

def main():
    repo = Path(".").resolve()
    as_of = "2025-12-16"
    
    # Try different potential filenames shown in `ls` earlier
    files = ["fo16122025.csv", "fo_16122025.csv"]
    
    for f in files:
        csv_path = repo / "data/derivatives" / as_of / f
        if csv_path.exists():
            print(f"Reading {csv_path}...")
            try:
                df = pd.read_csv(csv_path)
                df.columns = [c.strip().upper() for c in df.columns]
                print(f"Columns in {f}:")
                print(list(df.columns))
                
                # Check if it has BHARTI options
                rel = df[df["SYMBOL"].str.strip().str.upper() == "BHARTIARTL"]
                if not rel.empty:
                    print(f"Found {len(rel)} BHARTIARTL rows.")
            except Exception as e:
                print(f"Error reading {f}: {e}")
        else:
            print(f"{csv_path} does not exist.")

if __name__ == "__main__":
    main()
