from __future__ import annotations
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score
import lightgbm as lgb
import joblib

from stockreco.features.build_features import FEATURE_COLS

def train_calibrated_lgbm(feat: pd.DataFrame, asof: str, model_dir: Path) -> dict:
    '''
    Trains on data <= asof, using time-series split for calibration.
    Saves:
      - lgbm.pkl (base estimator)
      - calib.pkl (calibrator wrapper)
      - meta.json
    '''
    asof_date = pd.to_datetime(asof).date()
    train_df = feat[feat["date"] <= asof_date].copy()

    # Drop rows without enough history / labels
    train_df = train_df.dropna(subset=FEATURE_COLS + ["label_up"])
    X = train_df[FEATURE_COLS]
    y = train_df["label_up"].astype(int)

    base = lgb.LGBMClassifier(
        n_estimators=600,
        learning_rate=0.03,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )

    # Fit base
    base.fit(X, y)

    # Calibrate probabilities (isotonic) using last split as calibration
    # For small datasets, we keep it simple.
    # A more robust approach: split by date bands, or conformal calibration.
    tscv = TimeSeriesSplit(n_splits=5)
    # Take last fold for calibration
    splits = list(tscv.split(X))
    train_idx, cal_idx = splits[-1]
    base2 = lgb.LGBMClassifier(
        n_estimators=600,
        learning_rate=0.03,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )
    base2.fit(X.iloc[train_idx], y.iloc[train_idx])
    calib = CalibratedClassifierCV(base2, method="isotonic", cv="prefit")
    calib.fit(X.iloc[cal_idx], y.iloc[cal_idx])

    # Evaluate
    proba = calib.predict_proba(X.iloc[cal_idx])[:,1]
    auc = float(roc_auc_score(y.iloc[cal_idx], proba)) if len(set(y.iloc[cal_idx])) > 1 else float("nan")

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(base, model_dir / "lgbm.pkl")
    joblib.dump(calib, model_dir / "calib.pkl")
    meta = {"asof": asof, "feature_cols": FEATURE_COLS, "auc_cal_fold": auc}
    (model_dir / "meta.json").write_text(pd.Series(meta).to_json(), encoding="utf-8")

    return meta

def load_calibrated(model_dir: Path):
    import joblib
    calib = joblib.load(model_dir / "calib.pkl")
    meta = (model_dir / "meta.json").read_text(encoding="utf-8")
    return calib, meta
