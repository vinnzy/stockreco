from __future__ import annotations
import pandas as pd
from pathlib import Path
import joblib

from stockreco.features.build_features import FEATURE_COLS

def score_asof(feat: pd.DataFrame, asof: str, model_dir: Path) -> pd.DataFrame:
    asof_date = pd.to_datetime(asof).date()
    df = feat[feat["date"] == asof_date].copy()
    df = df.dropna(subset=FEATURE_COLS)

    calib = joblib.load(model_dir / "calib.pkl")
    p = calib.predict_proba(df[FEATURE_COLS])[:,1]
    df["p_up"] = p
    df["score"] = df["p_up"] + 0.15 * df["rel_strength_5d"].fillna(0) - 0.05 * df["atr_pct"].fillna(0)
    df = df.sort_values("score", ascending=False)
    return df
