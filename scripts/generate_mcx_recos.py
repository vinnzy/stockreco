from __future__ import annotations

import argparse
import json
from pathlib import Path
import csv
from typing import Any, Dict, List

from stockreco.commodities.commodity_reco_agent import CommodityRecoAgent


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_bhavcopy_file(as_of: str) -> Path:
    ddir = repo_root() / "data" / "mcx" / as_of
    if not ddir.exists():
        raise FileNotFoundError(f"Missing data dir: {ddir}")

    # e.g. BhavCopyDateWise_12122025.csv
    matches = sorted(ddir.glob("BhavCopyDateWise_*.csv"))
    if not matches:
        raise FileNotFoundError(f"No BhavCopyDateWise_*.csv found in {ddir}")
    return matches[-1]


def read_csv_rows(p: Path) -> List[Dict[str, Any]]:
    with p.open("r", newline="") as f:
        r = csv.DictReader(f)
        return list(r)


def write_reports(as_of: str, recos: List[Dict[str, Any]]) -> Dict[str, str]:
    out_dir = repo_root() / "reports" / "mcx"
    out_dir.mkdir(parents=True, exist_ok=True)

    jp = out_dir / f"mcx_reco_{as_of}.json"
    cp = out_dir / f"mcx_reco_{as_of}.csv"

    jp.write_text(json.dumps(recos, indent=2, default=str))

    cols = ["as_of","exchange","instrument","symbol","display_name","expiry","dte","action","option_type","strike_price","ltp","entry_price","sl","t1","t2","sell_by","confidence"]
    with cp.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in recos:
            w.writerow(r)

    return {"json": str(jp), "csv": str(cp)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", required=True, help="YYYY-MM-DD (folder under data/derivatives)")
    args = ap.parse_args()

    bhav = find_bhavcopy_file(args.as_of)
    rows = read_csv_rows(bhav)

    print("Rows:", len(rows))
    print("Sample keys:", list(rows[0].keys()) if rows else "NO ROWS")

    agent = CommodityRecoAgent()
    recos = agent.recommend_from_bhavcopy_rows(args.as_of, rows)
    print("Agent Recos:", len(recos))
    
    from stockreco.commodities.commodity_reviewer import CommodityReviewer
    reviewer = CommodityReviewer(min_confidence=0.60)
    approved = reviewer.review(recos)
    print("Reviewed Recos:", len(approved))

    # sort by confidence desc
    approved.sort(key=lambda x: x["confidence"], reverse=True)

    paths = write_reports(args.as_of, approved)
    print("Wrote:", paths)


if __name__ == "__main__":
    main()
