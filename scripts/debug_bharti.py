import pandas as pd
from pathlib import Path

def main():
    repo = Path(".").resolve()
    as_of = "2025-12-16"
    csv_path = repo / "data/derivatives" / as_of / "op16122025.csv"
    
    print(f"Reading {csv_path}...")
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().upper() for c in df.columns]
    
    # Filter BHARTIARTL
    # Try different variations just in case
    df = df.dropna(subset=["SYMBOL"])
    rows = df[df["SYMBOL"].str.strip().str.upper().str.contains("BHARTI")]
    print(f"Found {len(rows)} rows for BHARTI.")
    
    if rows.empty: return

    # Check 30 Dec expiry
    # expiry might be 30/12/2025 or 30-Dec-2025
    rows = rows[rows["EXP_DATE"].str.contains("30/12/2025") | rows["EXP_DATE"].str.contains("30-Dec-2025")]
    print(f"Rows for 30 Dec Expiry: {len(rows)}")
    
    # Look at Strike 2100
    r2100 = rows[abs(rows["STR_PRICE"] - 2100) < 1]
    
    print("\n--- STRIKE 2100 ---")
    if not r2100.empty:
        print(r2100[["OPTION_TYP", "OPEN_INT", "CHG_IN_OI", "CLOSE_PRICE"]].to_string())
    else:
        print("Strike 2100 not found.")
        
    # Find Max OI Change
    print("\n--- MAX CE OI CHANGE ---")
    ce_rows = rows[rows["OPTION_TYP"] == "CE"]
    if not ce_rows.empty:
        max_row = ce_rows.loc[ce_rows["CHG_IN_OI"].idxmax()]
        print(f"Strike: {max_row['STR_PRICE']}, OI Chg: {max_row['CHG_IN_OI']}, OI: {max_row['OPEN_INT']}")
        
    print("\n--- MAX PE OI CHANGE ---")
    pe_rows = rows[rows["OPTION_TYP"] == "PE"]
    if not pe_rows.empty:
        max_row = pe_rows.loc[pe_rows["CHG_IN_OI"].idxmax()]
        print(f"Strike: {max_row['STR_PRICE']}, OI Chg: {max_row['CHG_IN_OI']}, OI: {max_row['OPEN_INT']}")

if __name__ == "__main__":
    main()
