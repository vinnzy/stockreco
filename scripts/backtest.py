from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Literal, Optional

import pandas as pd

from stockreco.config.settings import settings
from stockreco.ingest.yfinance_fetch import load_ohlcv
from stockreco.utils.dates import previous_business_day
from stockreco.models.predict import score_asof
from stockreco.agents.pipeline import run_agents

Mode = Literal["strict", "aggressive"]

def _next_trading_day(df: pd.DataFrame, asof: str, ticker: str) -> pd.Timestamp:
    d = pd.to_datetime(asof)
    x = df[(df["ticker"] == ticker) & (df["date"] > d)].sort_values("date").head(1)
    if x.empty:
        raise ValueError(f"No next-day OHLCV found for {ticker} after {asof}")
    return pd.to_datetime(x.iloc[0]["date"])

def _day_row(df: pd.DataFrame, ticker: str, date: pd.Timestamp) -> pd.Series:
    x = df[(df["ticker"] == ticker) & (df["date"] == date)]
    if x.empty:
        raise ValueError(f"No OHLCV row for {ticker} on {date.date()}")
    return x.iloc[0]

def evaluate_next_day(ohlcv: pd.DataFrame, ticker: str, asof: str) -> dict:
    nxt = _next_trading_day(ohlcv, asof, ticker)
    r = _day_row(ohlcv, ticker, nxt)
    o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
    return {
        "next_date": nxt.date().isoformat(),
        "ret_oc": (c / o) - 1.0,
        "exp_oh": (h / o) - 1.0,
        "dd_ol": (l / o) - 1.0,
    }

def win_rules(
    style: Literal["buy_call", "buy_put", "sell_premium"],
    m: dict,
    *,
    call_exp_min: float = 0.012,     # +1.2% intraday upside expansion
    put_exp_min: float = 0.012,      # +1.2% intraday downside expansion
    max_dd_for_calls: float = 0.010, # -1.0% max drawdown tolerance
    range_max: float = 0.008,        # +-0.8% day for selling premium
) -> tuple[int, int]:
    ret_oc, exp_oh, dd_ol = m["ret_oc"], m["exp_oh"], m["dd_ol"]

    if style == "buy_call":
        buy_win = int((exp_oh >= call_exp_min) and (dd_ol >= -max_dd_for_calls))
        return buy_win, 0

    if style == "buy_put":
        down_exp = -dd_ol
        buy_win = int((down_exp >= put_exp_min) and (exp_oh <= range_max))
        return buy_win, 0

    # sell premium: want small realized move (theta wins)
    rng = max(exp_oh, -dd_ol)
    sell_win = int((abs(ret_oc) <= range_max) and (rng <= range_max))
    return 0, sell_win

def run_one_date(
    target_date: str,
    mode: Mode,
    max_trades: int,
    opt_style: Literal["buy_call","buy_put","sell_premium","both"] = "both",
) -> pd.DataFrame:
    target = dt.date.fromisoformat(target_date)
    asof = previous_business_day(target).isoformat()

    feat = pd.read_parquet(settings.data_dir / "features.parquet")
    model_dir = settings.models_dir / asof
    scored = score_asof(feat, asof=asof, model_dir=model_dir)

    agent_out = run_agents(scored=scored, as_of=asof, use_llm=bool(settings.openai_api_key), mode=mode, max_trades=max_trades)
    picks = agent_out.get("analyst", {}).get("final", [])
    # if final empty, fall back to top proposer (optional; comment out if you want strict “no picks = no rows”)
    if not picks:
        picks = agent_out.get("proposer", {}).get("top10", [])[:max_trades]

    ohlcv = load_ohlcv(settings.data_dir / "ohlcv.parquet")
    rows = []
    for p in picks[:max_trades]:
        ticker = p["ticker"]
        m = evaluate_next_day(ohlcv, ticker, asof)
        if opt_style == "both":
            buy_win, sell_win = win_rules("buy_call", m)
        else:
            buy_win, sell_win = win_rules(opt_style, m)
        rows.append({
            "target_date": target_date,
            "as_of": asof,
            "mode": mode,
            "ticker": ticker,
            "ret_oc": m["ret_oc"],
            "exp_oh": m["exp_oh"],
            "dd_ol": m["dd_ol"],
            "buy_win": buy_win,
            "sell_win": sell_win,
            "opt_style": opt_style,
        })
    return pd.DataFrame(rows)

def run_range(
    start: str,
    end: str,
    mode: Mode,
    max_trades: int,
    out_csv: Path,
    opt_style: Literal["buy_call","buy_put","sell_premium","both"] = "both",
):
    dates = pd.date_range(start=start, end=end, freq="D")
    all_rows = []
    for d in dates:
        # you can skip weekends quickly; previous_business_day handles target->asof, but target itself may be non-trading
        if d.weekday() >= 5:
            continue
        try:
            df = run_one_date(d.date().isoformat(), mode=mode, max_trades=max_trades, opt_style=opt_style)
            if not df.empty:
                all_rows.append(df)
        except Exception as e:
            # keep going; log if you want
            continue

    out = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv} rows={len(out)}")

if __name__ == "__main__":
    run_range(
        start="2025-11-15",
        end="2025-12-12",
        mode="aggressive",
        max_trades=2,
        out_csv=Path("reports/backtest_aggressive.csv"),
        opt_style="both",
    )
