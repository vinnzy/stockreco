from __future__ import annotations
import pandas as pd
from pathlib import Path
from stockreco.features.build_features import FEATURE_COLS
from stockreco.models.train_model import train_calibrated_lgbm
from stockreco.models.predict import score_asof

def walk_forward(feat: pd.DataFrame, start: str, end: str, model_root: Path) -> pd.DataFrame:
    dates = sorted(d for d in feat["date"].unique() if str(d) >= start and str(d) <= end)
    rows = []
    for d in dates:
        asof = str(d)
        model_dir = model_root / asof
        if not (model_dir / "calib.pkl").exists():
            train_calibrated_lgbm(feat, asof=asof, model_dir=model_dir)
        scored = score_asof(feat, asof=asof, model_dir=model_dir)
        top = scored.head(10).copy()
        # Realized next-day return for these picks
        top["realized_next_ret"] = top["next_ret_1d"]
        rows.append({
            "asof": asof,
            "avg_p_up": float(top["p_up"].mean()) if len(top) else None,
            "hit_rate": float((top["realized_next_ret"] > 0).mean()) if len(top) else None,
            "avg_next_ret": float(top["realized_next_ret"].mean()) if len(top) else None,
        })
    return pd.DataFrame(rows)
