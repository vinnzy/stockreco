import pandas as pd
from pathlib import Path

def main():
    repo = Path(".").resolve()
    as_of = "2025-12-16"
    csv_path = repo / "data/derivatives" / as_of / "op16122025.csv"
    
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().upper() for c in df.columns]
    
    # Clean symbol
    # Note: Column name is OPEN_INT* with asterisk
    if "OPEN_INT*" in df.columns:
        df = df.rename(columns={"OPEN_INT*": "OPEN_INT"})
        
    df = df.dropna(subset=["SYMBOL"])
    rows = df[df["SYMBOL"].str.strip().str.upper().str.contains("BHARTI")]
    
    print(f"Unique Expiries: {rows['EXP_DATE'].unique()}")
    print(f"Unique Types: {rows['OPT_TYPE'].unique()}")

    # 30 Dec expiry
    # Try simpler match
    expiry_mask = rows["EXP_DATE"].astype(str).str.contains("30")
    rows = rows[expiry_mask]
    
    if rows.empty:
        print("No rows found after expiry filter.")
        return

    ce_rows = rows[rows["OPT_TYPE"].str.strip() == "CE"].sort_values("STR_PRICE")
    
    if ce_rows.empty:
         print("No CE rows found.")
         return
    
    print("--- BHARTIARTL CE OI PROFILE ---")
    print(ce_rows[["STR_PRICE", "OPEN_INT"]].to_string(index=False))
    
    max_oi_row = ce_rows.loc[ce_rows["OPEN_INT"].idxmax()]
    print(f"\nMAX OI STRIKE: {max_oi_row['STR_PRICE']} (OI: {max_oi_row['OPEN_INT']})")
    
    spot = 2102  # Approx
    print(f"Spot: {spot}")
    if max_oi_row['STR_PRICE'] <= spot and abs(max_oi_row['STR_PRICE'] - spot) < 20:
        print("ALERT: Max OI is ATM/ITM!")

if __name__ == "__main__":
    main()
