import pandas as pd
from pathlib import Path

def main():
    repo = Path(".").resolve()
    as_of = "2025-12-16"
    
    csv_path = repo / "data/stocks" / as_of / "sec_bhavdata_full_16122025.csv"
    print(f"Checking path: {csv_path}")
    
    if not csv_path.exists():
        print("❌ File DOES NOT exist!")
        return

    print("✅ File exists. Reading...")
    try:
        df = pd.read_csv(csv_path)
        print(f"Loaded {len(df)} rows.")
        print("Columns:", list(df.columns))
        
        # Normalize columns
        df.columns = [c.strip().upper() for c in df.columns]
        
        # Check RELIANCE
        print("Searching for RELIANCE...")
        rel = df[df["SYMBOL"].str.strip().str.upper() == "RELIANCE"]
        if not rel.empty:
            print("✅ Found RELIANCE:")
            print(rel.iloc[0])
        else:
            print("❌ RELIANCE not found in DataFrame.")
            print("Sample symbols:", df["SYMBOL"].head(5).tolist())
            
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")

if __name__ == "__main__":
    main()
