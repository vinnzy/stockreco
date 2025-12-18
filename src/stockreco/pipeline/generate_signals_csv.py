from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from stockreco.ingest.market_context import MarketContextLoader

@dataclass
class SignalConfig:
    mode: str = "aggressive"
    atr_lookback: int = 14
    buy_thr_atr_frac: float = 0.45
    sell_thr_atr_frac: float = 0.45
    soft_cap: float = 2.25  # ratio at which soft reaches 1.0

def _asof_default() -> str:
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def _yf_ticker(sym: str) -> str:
    s = sym.strip().upper()
    if s == "NIFTY":
        return "^NSEI"
    if s == "BANKNIFTY":
        return "^NSEBANK"
    return sym

def _scalar(x):
    try:
        return float(x.item())
    except Exception:
        try:
            return float(x.iloc[0])
        except Exception:
            return float(x)

def _atr(df: pd.DataFrame, n: int = 14) -> float:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(n).mean()
    return float(atr.iloc[-1])

def _soft_linear(ratio: float, cap: float) -> float:
    if cap <= 0:
        return 0.0
    if ratio <= 0:
        return 0.0
    if ratio >= cap:
        return 1.0
    return float(ratio / cap)

def generate_signals_csv(
    repo_root: Path,
    universe: List[str],
    as_of: Optional[str] = None,
    cfg: Optional[SignalConfig] = None,
) -> Path:
    cfg = cfg or SignalConfig()
    as_of = as_of or _asof_default()

    out_dir = repo_root / "data" / "models" / as_of
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "signals.csv"
    
    # Load market context
    ctx_loader = MarketContextLoader(repo_root / "data")
    ctx = ctx_loader.load_context(as_of)
    print(f"[INFO] Loaded context for {as_of}: {len(ctx.volatility)} vols, {len(ctx.delivery_stats)} delivs, {len(ctx.bulk_deals)} bulk deals")
    
    # Analyze participant OI (FII) for crude market sentiment
    fii_stats = ctx.participant_oi.get("FII")
    fii_sentiment = 0.0 # -1 to 1
    if fii_stats:
        try:
            longs = float(fii_stats.get("Total Long Contracts", 0))
            shorts = float(fii_stats.get("Total Short Contracts", 0))
            if (longs + shorts) > 0:
                fii_sentiment = (longs - shorts) / (longs + shorts)
        except:
            pass
            
    rows: List[Dict] = []

    for sym in universe:
        sym = sym.strip().upper()
        ysym = _yf_ticker(sym)

        df = yf.download(ysym, period="3mo", interval="1d", progress=False, auto_adjust=False)
        if df is None or df.empty:
            print(f"[WARN] No data for {sym} ({ysym})")
            continue

        last = df.iloc[-1]
        o = _scalar(last["Open"])
        h = _scalar(last["High"])
        l = _scalar(last["Low"])
        c = _scalar(last["Close"])
        if o <= 0:
            print(f"[WARN] Bad open for {sym}")
            continue

        ret_oc = (c - o) / o
        exp_oh = (h - o) / o
        dd_ol = (l - o) / o

        atr_points = _atr(df, cfg.atr_lookback)
        atr_pct = (atr_points / o) if o > 0 else 0.0

        buy_thr = cfg.buy_thr_atr_frac * atr_pct
        sell_thr = cfg.sell_thr_atr_frac * atr_pct

        buy_ratio = (exp_oh / buy_thr) if buy_thr > 1e-9 else 0.0
        sell_ratio = (abs(dd_ol) / sell_thr) if sell_thr > 1e-9 else 0.0

        buy_soft = _soft_linear(buy_ratio, cfg.soft_cap)
        sell_soft = _soft_linear(sell_ratio, cfg.soft_cap)

        direction_score = float(buy_soft - sell_soft)
        strength = float(max(buy_soft, sell_soft))

        # keep hard wins as before
        buy_win = 1 if (ret_oc > 0 and exp_oh >= buy_thr) else 0
        sell_win = 1 if (ret_oc < 0 and abs(dd_ol) >= sell_thr) else 0

        rows.append(
            dict(
                target_date=as_of,
                as_of=as_of,
                mode=cfg.mode,
                ticker=sym,
                ret_oc=ret_oc,
                exp_oh=exp_oh,
                dd_ol=dd_ol,
                buy_win=buy_win,
                sell_win=sell_win,
                opt_style="both",
                atr_points=atr_points,
                atr_pct=atr_pct,
                buy_thr=buy_thr,
                sell_thr=sell_thr,
                buy_soft=buy_soft,
                sell_soft=sell_soft,
                direction_score=direction_score,
                strength=strength,
                # New Context Fields (Lookup using symbol without .NS suffix for Indian stocks)
                volatility_annualized=ctx.volatility.get(sym.replace(".NS", ""), 0.0),
                delivery_per=ctx.delivery_stats.get(sym.replace(".NS", ""), 0.0),
                delivery_spike=1 if ctx.delivery_stats.get(sym.replace(".NS", ""), 0.0) > 50.0 else 0, # Simple threshold for now
                has_bulk_deal=1 if sym.replace(".NS", "") in ctx.bulk_deals else 0,
                fii_sentiment=fii_sentiment,
            )
        )

    if not rows:
        raise RuntimeError("No signals generated. Check universe symbols / yfinance availability.")

    pd.DataFrame(rows).to_csv(out_path, index=False)
    return out_path
