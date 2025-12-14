from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import json
import csv
from stockreco.options.option_reco_agent import _ensure_sell_by


def _safe_targets(t):
    # targets can be None, dict, list
    if t is None:
        return []
    if isinstance(t, dict):
        return [t]
    if isinstance(t, (list, tuple)):
        return list(t)
    return []

def write_option_recos(out_dir: Path, as_of: str, recos: List[Any]) -> Dict[str, str]:
    """
    Writes both JSON and CSV under:
      <out_dir>/options/option_reco_<as_of>.json
      <out_dir>/options/option_reco_<as_of>.csv
    Works even if reco.targets is None or dict.
    """
    out_dir = Path(out_dir)
    (out_dir / "options").mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "options" / f"option_reco_{as_of}.json"
    csv_path = out_dir / "options" / f"option_reco_{as_of}.csv"

    # Serialize
    payload = []
    for r in recos:
        if hasattr(r, "to_dict"):
            d = r.to_dict()
        elif isinstance(r, dict):
            d = r
        else:
            d = getattr(r, "__dict__", {})

        # ✅ ensure sell_by exists for older schema / edge cases
        d = _ensure_sell_by(d)
        payload.append(d)


    json_path.write_text(json.dumps(payload, indent=2, default=str))

    # CSV (flatten)
    cols = [
        "as_of","symbol","bias","instrument","action","side","expiry","strike",
        "entry_price","sl_premium","sl_invalidation",
        "t1_underlying","t1_premium","t2_underlying","t2_premium",
        "confidence",
        # extra diagnostics
        "spot","ltp","iv","dte","theta_per_day","delta","extrinsic","sell_by",
    ]

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

    return {"json": str(json_path), "csv": str(csv_path)}
