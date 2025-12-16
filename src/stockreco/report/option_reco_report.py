from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import json
import csv
from stockreco.agents.option_reco_agent import _ensure_sell_by


def _safe_targets(t):
    # targets can be None, dict, list
    if t is None:
        return []
    if isinstance(t, dict):
        return [t]
    if isinstance(t, (list, tuple)):
        return list(t)
    return []

def write_option_recos(out_dir: Path, as_of: str, recos: Any) -> Dict[str, str]:
    """
    Writes both JSON and CSV under:
      <out_dir>/options/option_reco_<as_of>.json
      <out_dir>/options/option_reco_<as_of>.csv
    
    Supports both formats:
    - Old: List of OptionReco objects
    - New: Dict with {recommender, reviewer, final} structure
    
    Works even if reco.targets is None or dict.
    """
    out_dir = Path(out_dir)
    (out_dir / "options").mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "options" / f"option_reco_{as_of}.json"
    csv_path = out_dir / "options" / f"option_reco_{as_of}.csv"

    # Detect format
    is_structured = isinstance(recos, dict) and "reviewer" in recos
    
    if is_structured:
        # New format: write full structure to JSON
        # Extract approved recommendations for CSV
        approved_recos = recos.get("final", [])
        full_structure = {
            "as_of": as_of,
            "recommender": _serialize_recos(recos.get("recommender", [])),
            "reviewer": {
                "approved": _serialize_recos(recos["reviewer"].get("approved", [])),
                "rejected": recos["reviewer"].get("rejected", [])
            },
            "final": _serialize_recos(approved_recos)
        }
        json_path.write_text(json.dumps(full_structure, indent=2, default=str))
        csv_recos = approved_recos
    else:
        # Old format: simple list
        payload = _serialize_recos(recos)
        json_path.write_text(json.dumps(payload, indent=2, default=str))
        csv_recos = recos

    # Write CSV (approved recommendations only)
    _write_csv(csv_path, csv_recos)

    return {"json": str(json_path), "csv": str(csv_path)}


def _serialize_recos(recos: List[Any]) -> List[Dict[str, Any]]:
    """Convert list of OptionReco objects to list of dicts."""
    payload = []
    for r in recos:
        if hasattr(r, "to_dict"):
            d = r.to_dict()
        elif isinstance(r, dict):
            d = r
        else:
            d = getattr(r, "__dict__", {})
        
        # Ensure sell_by exists for older schema / edge cases
        d = _ensure_sell_by(d)
        payload.append(d)
    return payload


def _write_csv(csv_path: Path, recos: List[Any]) -> None:
    """Write recommendations to CSV file."""
    cols = [
        "as_of","symbol","bias","instrument","action","side","expiry","strike",
        "entry_price","sl_premium","sl_invalidation",
        "t1_underlying","t1_premium","t2_underlying","t2_premium",
        "confidence",
        # extra diagnostics
        "spot","ltp","iv","dte","theta_per_day","delta","extrinsic","sell_by",
    ]

    payload = _serialize_recos(recos)
    
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for d in payload:
            tlist = _safe_targets(d.get("targets"))
            t1 = (tlist[0] if len(tlist) > 0 else {}) or {}
            t2 = (tlist[1] if len(tlist) > 1 else {}) or {}
            w.writerow({
                "as_of": d.get("as_of"),
                "symbol": d.get("symbol"),
                "bias": d.get("bias"),
                "instrument": d.get("instrument"),
                "action": d.get("action"),
                "side": d.get("side"),
                "expiry": d.get("expiry"),
                "strike": d.get("strike"),
                "entry_price": d.get("entry_price"),
                "sl_premium": d.get("sl_premium"),
                "sl_invalidation": d.get("sl_invalidation"),
                "t1_underlying": t1.get("underlying"),
                "t1_premium": t1.get("premium"),
                "t2_underlying": t2.get("underlying"),
                "t2_premium": t2.get("premium"),
                "confidence": d.get("confidence"),
                "spot": d.get("spot"),
                "ltp": d.get("ltp"),
                "iv": d.get("iv"),
                "dte": d.get("dte"),
                "theta_per_day": d.get("theta_per_day"),
                "delta": d.get("delta"),
                "extrinsic": d.get("extrinsic"),
                "sell_by": d.get("sell_by"),
            })

