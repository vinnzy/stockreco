import pandas as pd
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(".").resolve() / "src"))
from stockreco.ingest.derivatives.local_csv_provider import LocalCsvProvider

def main():
    repo = Path(".").resolve()
    as_of = "2025-12-16"
    
    # 1. Inspect Raw CSV
    csv_path = repo / "data/derivatives" / as_of / "op16122025.csv"
    if not csv_path.exists():
        print(f"op CSV not found at {csv_path}")
        return

    print(f"Reading first 20 lines of {csv_path}...")
    df = pd.read_csv(csv_path, nrows=20)
    df.columns = [c.strip().upper() for c in df.columns]
    
    if "CONTRACT_D" in df.columns:
        print("\nSample CONTRACT_D values:")
        print(df["CONTRACT_D"].head(10))
    else:
        print(f"CONTRACT_D column missing. Columns: {df.columns}")

    # 2. Test Provider
    print(f"\nTesting Provider for RELIANCE...")
    try:
        prov = LocalCsvProvider(repo_root=repo, as_of=as_of)
        chain = prov.get_option_chain("RELIANCE")
        print(f"Found {len(chain)} rows for RELIANCE")
    except Exception as e:
        print(f"Provider failed for RELIANCE: {e}")

if __name__ == "__main__":
    main()
