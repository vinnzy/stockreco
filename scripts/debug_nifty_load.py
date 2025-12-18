
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

from stockreco.ingest.derivatives.local_csv_provider import LocalCsvProvider

def main():
    repo = Path.cwd()
    as_of = "2025-12-17"
    
    print(f"Testing LocalCsvProvider for NIFTY on {as_of}")
    
    try:
        provider = LocalCsvProvider(repo_root=repo, as_of=as_of)
        
        # Test 1: NIFTY
        print("\n--- Trying symbol='NIFTY' ---")
        try:
            chain = provider.get_option_chain("NIFTY")
            print(f"Success! Found {len(chain)} rows for NIFTY")
            # Print sample
            if chain:
                print(f"Sample: {chain[0]}")
        except Exception as e:
            print(f"Failed: {e}")

        # Test 2: NIFTY 50
        print("\n--- Trying symbol='NIFTY 50' ---")
        try:
            chain = provider.get_option_chain("NIFTY 50")
            print(f"Success! Found {len(chain)} rows for NIFTY 50")
        except Exception as e:
            print(f"Failed: {e}")

        # Test 3: BANKNIFTY
        print("\n--- Trying symbol='BANKNIFTY' ---")
        try:
            chain = provider.get_option_chain("BANKNIFTY")
            print(f"Success! Found {len(chain)} rows for BANKNIFTY")
        except Exception as e:
            print(f"Failed: {e}")

    except Exception as e:
        print(f"Provider init failed: {e}")

if __name__ == "__main__":
    main()
