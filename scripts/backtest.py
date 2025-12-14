from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

# ---- Adjust these imports to match your project layout ----
from stockreco.config.settings import settings
from stockreco.utils.dates import previous_business_day
from stockreco.universe.nifty50_static import NIFTY50, NIFTY_INDEX
from stockreco.ingest.yfinance_fetch import load_ohlcv
from stockreco.features.build_features import add_technical_features
from stockreco.models.train_model import train_calibrated_lgbm
from stockreco.models.predict import score_asof
from stockreco.models.predict_expand import score_expand_asof
from stockreco.agents.pipeline import run_agents


def _ohlcv_path() -> Path:
    return settings.data_dir / "ohlcv.parquet"

def _features_path() -> Path:
    return settings.data_dir / "features.parquet"

def ensure_features_exist() -> None:
    if _features_path().exists():
        return
    ohlcv = load_ohlcv(_ohlcv_path())
    nifty = ohlcv[ohlcv["ticker"] == NIFTY_INDEX].copy()
    stocks = ohlcv[ohlcv["ticker"] != NIFTY_INDEX].copy()
    feat = add_technical_features(stocks, nifty)
    feat.to_parquet(_features_path(), index=False)

def ensure_model(asof_str: str, feat: pd.DataFrame) -> None:
    model_dir = settings.models_dir / asof_str
    if not (model_dir / "calib.pkl").exists():
        train_calibrated_lgbm(feat, asof=asof_str, model_dir=model_dir)

def ensure_expand_model(asof_str: str) -> None:
    # If you have a separate trainer for expand, you can call it here.
    # For now: backtest can run even if expand.pkl missing (it will set p_expand=0.0 in your pipeline).
    return


def next_day_metrics(ohlcv: pd.DataFrame, ticker: str, day: dt.date) -> Dict:
    """Compute next-day outcomes using daily OHLCV."""
    d = pd.Timestamp(day)
    row = ohlcv[(ohlcv["ticker"] == ticker) & (pd.to_datetime(ohlcv["date"]) == d)]
    if row.empty:
        return {"found": False}

    r = row.iloc[0]
    o = float(r["open"])
    h = float(r["high"])
    l = float(r["low"])
    c = float(r["close"])

    ret_oc = (c / o) - 1.0
    exp_oh = (h / o) - 1.0
    dd_ol = (l / o) - 1.0  # negative

    return {
        "found": True,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "ret_oc": ret_oc,
        "exp_oh": exp_oh,
        "dd_ol": dd_ol,
    }


def score_day(
    target_date: str,
    mode: str,
    max_trades: int,
    use_llm: bool = False,
) -> Dict:
    """Run your existing pipeline for one target_date."""
    target = dt.date.fromisoformat(target_date)
    as_of = previous_business_day(target)
    asof_str = as_of.isoformat()

    feat = pd.read_parquet(_features_path())
    ensure_model(asof_str, feat)
    ensure_expand_model(asof_str)

    scored = score_asof(feat, asof=asof_str, model_dir=settings.models_dir / asof_str)

    # If you want p_expand available even if pipeline doesn’t merge it:
    try:
        exp = score_expand_asof(feat, asof=asof_str, model_dir=settings.models_dir / asof_str)
        scored = scored.merge(exp, on="ticker", how="left")
        scored["p_expand"] = scored["p_expand"].fillna(0.0)
    except Exception:
        scored["p_expand"] = 0.0

    agent_out = run_agents(
        scored=scored,
        as_of=asof_str,
        use_llm=use_llm,
        mode=mode,
        max_trades=max_trades,
    )

    final = (agent_out.get("analyst") or {}).get("final", []) or []
    picks = [x["ticker"] for x in final]
    return {"target_date": target_date, "as_of": asof_str, "picks": picks, "agent_out": agent_out}


def backtest_range(
    start: str,
    end: str,
    mode: str,
    max_trades: int,
    opt_style: str,
    expand_thr: float,
    sell_be_move: float,
    buy_win_move: float,
) -> pd.DataFrame:
    ensure_features_exist()
    ohlcv = load_ohlcv(_ohlcv_path()).copy()
    ohlcv["date"] = pd.to_datetime(ohlcv["date"]).dt.date

    start_d = dt.date.fromisoformat(start)
    end_d = dt.date.fromisoformat(end)

    rows: List[Dict] = []
    d = start_d
    while d <= end_d:
        # skip weekends quickly
        if d.weekday() >= 5:
            d += dt.timedelta(days=1)
            continue

        target_date = d.isoformat()
        out = score_day(target_date, mode=mode, max_trades=max_trades, use_llm=False)
        picks = out["picks"]

        for ticker in picks:
            m = next_day_metrics(ohlcv, ticker, d)
            if not m.get("found"):
                continue

            # --- options-style scoring proxies ---
            # BUY proxy: "win" if open->high reaches buy_win_move
            buy_win = 1 if m["exp_oh"] >= buy_win_move else 0

            # SELL proxy: "win" if neither side breaches breakeven move
            up_move = m["exp_oh"]
            down_move = abs(m["dd_ol"])
            sell_win = 1 if (up_move <= sell_be_move and down_move <= sell_be_move) else 0

            rows.append({
                "target_date": target_date,
                "as_of": out["as_of"],
                "mode": mode,
                "ticker": ticker,
                "ret_oc": m["ret_oc"],
                "exp_oh": m["exp_oh"],
                "dd_ol": m["dd_ol"],
                "buy_win": buy_win,
                "sell_win": sell_win,
                "opt_style": opt_style,
            })

        d += dt.timedelta(days=1)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Aggregate summary per ticker + overall
    return df


def summarize(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df, df

    overall = pd.DataFrame([{
        "n_trades": int(len(df)),
        "avg_ret_oc": float(df["ret_oc"].mean()),
        "avg_exp_oh": float(df["exp_oh"].mean()),
        "hit_up_rate": float((df["ret_oc"] > 0).mean()),
        "buy_win_rate": float(df["buy_win"].mean()),
        "sell_win_rate": float(df["sell_win"].mean()),
    }])

    by_ticker = (
        df.groupby("ticker")
        .agg(
            n=("ticker", "count"),
            avg_ret_oc=("ret_oc", "mean"),
            avg_exp_oh=("exp_oh", "mean"),
            hit_up_rate=("ret_oc", lambda s: float((s > 0).mean())),
            buy_win_rate=("buy_win", "mean"),
            sell_win_rate=("sell_win", "mean"),
        )
        .sort_values(["n", "avg_exp_oh"], ascending=False)
        .reset_index()
    )

    return overall, by_ticker


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--mode", default="aggressive", choices=["strict","aggressive"])
    ap.add_argument("--max-trades", type=int, default=2)
    ap.add_argument("--buy-win-move", type=float, default=0.012, help="open->high move threshold (e.g. 0.012 = 1.2%)")
    ap.add_argument("--sell-be-move", type=float, default=0.010, help="breakeven move each side for sell proxy")
    ap.add_argument("--out", default="backtest_results.csv")
    args = ap.parse_args()

    df = backtest_range(
        start=args.start,
        end=args.end,
        mode=args.mode,
        max_trades=args.max_trades,
        opt_style="both",
        expand_thr=0.012,
        sell_be_move=args.sell_be_move,
        buy_win_move=args.buy_win_move,
    )

    Path(args.out).write_text(df.to_csv(index=False), encoding="utf-8")
    overall, by_ticker = summarize(df)

    print("\n=== OVERALL ===")
    print(overall.to_string(index=False))
    print("\n=== BY TICKER (top 20) ===")
    print(by_ticker.head(20).to_string(index=False))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
