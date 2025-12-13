from __future__ import annotations
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD, ADXIndicator, SMAIndicator, EMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands

def _safe_group_apply(df: pd.DataFrame, fn):
    return df.groupby("ticker", group_keys=False).apply(fn)

def add_technical_features(ohlcv: pd.DataFrame, nifty: pd.DataFrame) -> pd.DataFrame:
    '''
    ohlcv: long df per stock
    nifty: long df with ticker == ^NSEI
    '''
    ohlcv = ohlcv.copy()
    ohlcv = ohlcv.sort_values(["ticker","date"])
    nifty = nifty.sort_values(["date"]).rename(columns={"close":"nifty_close"})[["date","nifty_close"]]
    ohlcv = ohlcv.merge(nifty, on="date", how="left")

    def per_ticker(g: pd.DataFrame) -> pd.DataFrame:
        g = g.sort_values("date").copy()
        close = pd.to_numeric(g["close"], errors="coerce")
        high = pd.to_numeric(g["high"], errors="coerce")
        low  = pd.to_numeric(g["low"], errors="coerce")
        vol  = pd.to_numeric(g["volume"], errors="coerce")

        g["ret_1d"] = close.pct_change(1)
        g["ret_5d"] = close.pct_change(5)
        g["ret_10d"] = close.pct_change(10)

        g["vol_surge_20d"] = vol / vol.rolling(20).mean()

        g["rsi_14"] = RSIIndicator(close, window=14).rsi()
        macd = MACD(close)
        g["macd"] = macd.macd()
        g["macd_signal"] = macd.macd_signal()
        g["macd_hist"] = macd.macd_diff()

        g["sma_20"] = SMAIndicator(close, window=20).sma_indicator()
        g["sma_50"] = SMAIndicator(close, window=50).sma_indicator()
        g["ema_20"] = EMAIndicator(close, window=20).ema_indicator()

        bb = BollingerBands(close, window=20, window_dev=2)
        g["bb_h"] = bb.bollinger_hband()
        g["bb_l"] = bb.bollinger_lband()
        g["bb_p"] = bb.bollinger_pband()

        atr = AverageTrueRange(high, low, close, window=14)
        g["atr"] = atr.average_true_range()
        g["atr_pct"] = g["atr"] / close

        adx = ADXIndicator(high, low, close, window=14)
        g["adx_14"] = adx.adx()

        # Relative strength vs Nifty (5D)
        nifty_close = pd.to_numeric(g["nifty_close"], errors="coerce")
        g["nifty_ret_5d"] = nifty_close.pct_change(5)
        g["rel_strength_5d"] = g["ret_5d"] - g["nifty_ret_5d"]

        # Trend flags
        g["close_above_sma20"] = (close > g["sma_20"]).astype("int")
        g["close_above_sma50"] = (close > g["sma_50"]).astype("int")
        g["sma20_above_sma50"] = (g["sma_20"] > g["sma_50"]).astype("int")

        return g

    feat = _safe_group_apply(ohlcv, per_ticker)

    # Label for training: next-day up move (close-to-close)
    feat["next_ret_1d"] = feat.groupby("ticker")["close"].pct_change(-1) * -1  # shift(-1) / current - 1
    feat["label_up"] = (feat["next_ret_1d"] > 0).astype("int")

    return feat

FEATURE_COLS = [
    "ret_1d","ret_5d","ret_10d",
    "vol_surge_20d",
    "rsi_14",
    "macd","macd_signal","macd_hist",
    "sma_20","sma_50","ema_20",
    "bb_h","bb_l","bb_p",
    "atr","atr_pct",
    "adx_14",
    "rel_strength_5d",
    "close_above_sma20","close_above_sma50","sma20_above_sma50",
]
