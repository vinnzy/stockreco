
import subprocess
from datetime import datetime
import glob
import os
import sys

def run():
    # Recos to check
    reco_files = sorted(glob.glob("reports/options/option_reco_*.json"))
    # Market data dates to check against
    outcome_dates = ["2025-12-16", "2025-12-17", "2025-12-18"]
    
    python_cmd = ".venv/bin/python" if os.path.exists(".venv/bin/python") else "python3"

    for o_date in outcome_dates:
        print(f"--- Processing Outcome Date: {o_date} ---")
        for r_file in reco_files:
            try:
                cmd = [python_cmd, "scripts/generate_option_performance.py", "--reco-file", r_file, "--outcome-date", o_date]
                subprocess.run(cmd, check=False)
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    run()
