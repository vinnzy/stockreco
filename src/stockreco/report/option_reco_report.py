from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Union
import json
import pandas as pd
from dataclasses import asdict, is_dataclass

def _to_dict(x: Any) -> Dict[str, Any]:
    if x is None:
        return {}
    if is_dataclass(x):
        return asdict(x)
    if isinstance(x, dict):
        return x
    # best-effort
    try:
        return dict(x)
    except Exception:
        return {"value": x}

def _extract_targets(d: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize targets into flat fields used in CSV/report."""
    t = d.get("targets")

    # Case 1: new format dict/object {t1_underlying,...}
    if isinstance(t, dict):
        return {
            "t1_underlying": t.get("t1_underlying"),
            "t1_premium": t.get("t1_premium"),
            "t2_underlying": t.get("t2_underlying"),
            "t2_premium": t.get("t2_premium"),
        }

    # Case 2: dataclass (OptionTargets)
    if is_dataclass(t):
        td = asdict(t)
        return {
            "t1_underlying": td.get("t1_underlying"),
            "t1_premium": td.get("t1_premium"),
            "t2_underlying": td.get("t2_underlying"),
            "t2_premium": td.get("t2_premium"),
        }

    # Case 3: legacy list/tuple [t1, t2] where each is dict/object
    if isinstance(t, (list, tuple)):
        t1 = t[0] if len(t) > 0 else None
        t2 = t[1] if len(t) > 1 else None
        t1d = _to_dict(t1)
        t2d = _to_dict(t2)
        return {
            "t1_underlying": t1d.get("underlying") or t1d.get("t1_underlying"),
            "t1_premium": t1d.get("premium") or t1d.get("t1_premium"),
            "t2_underlying": t2d.get("underlying") or t2d.get("t2_underlying"),
            "t2_premium": t2d.get("premium") or t2d.get("t2_premium"),
        }

    return {"t1_underlying": None, "t1_premium": None, "t2_underlying": None, "t2_premium": None}

def write_option_recos(out_dir: Path, as_of: str, recos: List[Any]) -> Dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"option_reco_{as_of}.json"
    csv_path = out_dir / f"option_reco_{as_of}.csv"

    # Convert recos to dicts
    out_rows: List[Dict[str, Any]] = []
    for r in recos:
        d = _to_dict(r)

        # Normalize field names
        symbol = d.get("symbol") or d.get("ticker") or d.get("underlying")
        d["symbol"] = symbol

        # Flatten targets
        tflat = _extract_targets(d)
        d.update(tflat)

        out_rows.append(d)

    # JSON
    json_path.write_text(json.dumps(out_rows, indent=2, default=str), encoding="utf-8")

    # CSV (stable column ordering expected by UI)
    cols = [
        "as_of","symbol","bias","instrument","action","side","expiry","strike",
        "entry","stop_loss",
        "t1_underlying","t1_premium","t2_underlying","t2_premium",
        "confidence",
    ]

    df = pd.DataFrame(out_rows)

    # Backward compatible names in CSV output expected earlier:
    rename = {
        "entry": "entry_price",
        "stop_loss": "sl_premium",
    }
    for k in list(rename.keys()):
        if k not in df.columns and rename[k] in df.columns:
            # already present under new name; reverse rename not needed
            pass

    df = df.rename(columns=rename)

    # ensure all cols exist
    for c in cols:
        if c not in df.columns:
            df[c] = None

    # apply old expected names for sl/entry
    final_cols = [
        "as_of","symbol","bias","instrument","action","side","expiry","strike",
        "entry_price","sl_premium",
        # keep sl_invalidation if present else empty
        "sl_invalidation",
        "t1_underlying","t1_premium","t2_underlying","t2_premium",
        "confidence",
    ]
    if "sl_invalidation" not in df.columns:
        df["sl_invalidation"] = None
    for c in final_cols:
        if c not in df.columns:
            df[c] = None

    df[final_cols].to_csv(csv_path, index=False)
    return {"json": str(json_path), "csv": str(csv_path)}
