from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import json, csv

def write_commodity_recos(out_dir: Path, as_of: str, recos: List[Any]) -> Dict[str, str]:
    out_dir = Path(out_dir)
    (out_dir / "commodities").mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "commodities" / f"commodity_reco_{as_of}.json"
    csv_path  = out_dir / "commodities" / f"commodity_reco_{as_of}.csv"

    payload = []
    for r in recos:
        if hasattr(r, "to_dict"):
            payload.append(r.to_dict())
        elif isinstance(r, dict):
            payload.append(r)
        else:
            payload.append(getattr(r, "__dict__", {}))

    json_path.write_text(json.dumps(payload, indent=2, default=str))

    cols = ["as_of","exchange","symbol","expiry","instrument","action","bias",
            "ltp","entry_price","sl_price","t1","t2","confidence","sell_by"]

    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for d in payload:
            t = d.get("targets") or []
            t1 = (t[0].get("price") if len(t) > 0 and isinstance(t[0], dict) else None)
            t2 = (t[1].get("price") if len(t) > 1 and isinstance(t[1], dict) else None)
            w.writerow({
                "as_of": d.get("as_of"),
                "exchange": d.get("exchange"),
                "symbol": d.get("symbol"),
                "expiry": d.get("expiry"),
                "instrument": d.get("instrument"),
                "action": d.get("action"),
                "bias": d.get("bias"),
                "ltp": d.get("ltp"),
                "entry_price": d.get("entry_price"),
                "sl_price": d.get("sl_price"),
                "t1": t1,
                "t2": t2,
                "confidence": d.get("confidence"),
                "sell_by": d.get("sell_by"),
            })

    return {"json": str(json_path), "csv": str(csv_path)}
