from __future__ import annotations

from pathlib import Path
from typing import Dict
import json

import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
except Exception:
    lgb = None

import joblib

FEATURE_COLS = [
    "rsi_14", "macd_hist", "adx_14", "atr_pct",
    "rel_strength_5d",
    "close_above_sma20", "close_above_sma50", "sma20_above_sma50",
]

def _make_expand_label(df: pd.DataFrame, thr: float = 0.012) -> pd.Series:
    """Label 1 if next-day expansion exceeds thr.

    Prefer next day (high/open - 1) if open/high exist, else (close/open - 1).
    """
    if "open" in df.columns and "high" in df.columns:
        next_open = df["open"].shift(-1)
        next_high = df["high"].shift(-1)
        expand = (next_high / next_open) - 1.0
    elif "open" in df.columns and "close" in df.columns:
        next_open = df["open"].shift(-1)
        next_close = df["close"].shift(-1)
        expand = (next_close / next_open) - 1.0
    else:
        expand = pd.Series(np.nan, index=df.index)

    return (expand >= thr).astype("float")  # keep float -> we can dropna safely later

def train_expand_lgbm(
    feat: pd.DataFrame,
    asof: str,
    model_dir: Path,
    thr: float = 0.012,
) -> Dict:
    """Train Model-B: P(next-day expansion >= thr). Writes expand.pkl to model_dir."""
    if lgb is None:
        raise ImportError("lightgbm is required for Model-B (expand). pip install lightgbm")

    df = feat.copy()
    df["date"] = pd.to_datetime(df["date"])
    cutoff = pd.to_datetime(asof)

    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    # label per ticker without shape surprises
    y = []
    for _, g in df.groupby("ticker", sort=False):
        y.append(_make_expand_label(g, thr=thr))
    df["y_expand"] = pd.concat(y, axis=0).sort_index()

    df = df.dropna(subset=["y_expand"])
    df["y_expand"] = df["y_expand"].astype(int)

    train_df = df[df["date"] <= cutoff].copy()
    if train_df.empty:
        raise ValueError(f"No training rows for expand model asof={asof}")

    X = train_df[FEATURE_COLS].replace([np.inf, -np.inf], np.nan).fillna(0.0).values
    yv = train_df["y_expand"].astype(int).values

    dtrain = lgb.Dataset(X, label=yv)
    params = dict(
        objective="binary",
        metric="auc",
        learning_rate=0.05,
        num_leaves=31,
        min_data_in_leaf=50,
        feature_fraction=0.9,
        bagging_fraction=0.9,
        bagging_freq=1,
        seed=42,
        verbose=-1,
    )
    booster = lgb.train(params, dtrain, num_boost_round=400)

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(booster, model_dir / "expand.pkl")

    meta = {
        "asof": asof,
        "thr": thr,
        "n_rows": int(len(train_df)),
        "pos_rate": float(yv.mean()) if len(yv) else None,
        "features": FEATURE_COLS,
    }
    (model_dir / "expand_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
