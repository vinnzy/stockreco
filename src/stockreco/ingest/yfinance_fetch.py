from __future__ import annotations
import pandas as pd
import yfinance as yf
from pathlib import Path
from stockreco.config.settings import settings

def fetch_ohlcv(tickers: list[str], start: str, end: str | None = None) -> pd.DataFrame:
    '''
    Returns a long dataframe:
      date, ticker, open, high, low, close, adj_close, volume
    '''
    df = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        group_by="ticker",
        auto_adjust=False,
        actions=False,
        threads=True,
        progress=False,
    )

    rows = []
    if isinstance(df.columns, pd.MultiIndex):
        for t in tickers:
            if t not in df.columns.get_level_values(0):
                continue
            sub = df[t].copy()
            sub.columns = [c.lower().replace(" ", "_") for c in sub.columns]
            sub["ticker"] = t
            sub = sub.reset_index()
            # Normalize date column name to lowercase
            sub = sub.rename(columns={col: "date" for col in sub.columns if col.lower() == "date"})
            rows.append(sub)
        out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    else:
        # single ticker
        out = df.copy()
        out.columns = [c.lower().replace(" ", "_") for c in out.columns]
        out["ticker"] = tickers[0]
        out = out.reset_index()
        # Normalize date column name to lowercase
        out = out.rename(columns={col: "date" for col in out.columns if col.lower() == "date"})

    out = out.rename(columns={
        "adj_close": "adj_close",
        "adj close": "adj_close",
    })
    out["date"] = pd.to_datetime(out["date"]).dt.date
    keep = ["date","ticker","open","high","low","close","adj_close","volume"]
    for k in keep:
        if k not in out.columns:
            out[k] = pd.NA
    return out[keep].sort_values(["ticker","date"])

def save_ohlcv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)

def load_ohlcv(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)
