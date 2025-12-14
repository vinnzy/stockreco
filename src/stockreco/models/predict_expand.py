from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import joblib

from stockreco.models.expand_model import FEATURE_COLS

def score_expand_asof(feat: pd.DataFrame, asof: str, model_dir: Path) -> pd.DataFrame:
    """Return per-ticker p_expand for the given asof date."""
    df = feat.copy()
    df["date"] = pd.to_datetime(df["date"])
    asof_dt = pd.to_datetime(asof)
    day = df[df["date"] == asof_dt].copy()
    if day.empty:
        raise ValueError(f"No feature rows for asof={asof}")

    booster = joblib.load(model_dir / "expand.pkl")
    X = day[FEATURE_COLS].replace([np.inf,-np.inf], np.nan).fillna(0.0).values
    p = booster.predict(X)
    day["p_expand"] = p.astype(float)
    return day[["ticker","p_expand"]].sort_values("p_expand", ascending=False).reset_index(drop=True)
