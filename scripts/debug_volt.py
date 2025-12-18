from pathlib import Path
import pandas as pd
import glob

repo_root = Path(".").resolve()
data_dir = repo_root / "data"
as_of = "2025-12-16"
dir_path = data_dir / "stocks" / as_of
suffix = "16122025"

print(f"Checking dir: {dir_path}")
print(f"Exists? {dir_path.exists()}")

pattern = f"*VOLT*{suffix}*"
print(f"Glob pattern: {pattern}")
files = list(dir_path.glob(pattern))
print(f"Found files: {files}")

if files:
    f = files[0]
    print(f"Reading: {f}")
    df = pd.read_csv(f)
    print("Columns:", list(df.columns))
    
    # Check column match logic
    df.columns = [c.strip() for c in df.columns]
    vol_col = next((c for c in df.columns if "Annualized Volatility" in c), None)
    print(f"Matched Vol Column: '{vol_col}'")
    
    if vol_col:
        print(f"First row val: {df.iloc[0][vol_col]}")
