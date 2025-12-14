from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from rich import print

from stockreco.config.settings import settings
from stockreco.universe.nifty50_static import NIFTY50, NIFTY_INDEX
from stockreco.ingest.yfinance_fetch import fetch_ohlcv, save_ohlcv, load_ohlcv
from stockreco.features.build_features import add_technical_features
from stockreco.models.train_model import train_calibrated_lgbm
from stockreco.models.predict import score_asof
from stockreco.agents.pipeline import run_agents
from stockreco.report.render import write_json, write_markdown
from stockreco.utils.dates import previous_business_day
from stockreco.models.predict_expand import score_expand_asof
from stockreco.models.expand_model import train_expand_lgbm  # Model-B trainer

app = typer.Typer(add_completion=False)

def _ohlcv_path() -> Path:
    return settings.data_dir / "ohlcv.parquet"

def _features_path() -> Path:
    return settings.data_dir / "features.parquet"

@app.command()
def fetch(start: str = "2018-01-01"):
    """Fetch EOD OHLCV for Nifty50 + Nifty index via yfinance."""
    tickers = NIFTY50 + [NIFTY_INDEX]
    print(f"[cyan]Fetching {len(tickers)} tickers from {start} ...[/cyan]")
    df = fetch_ohlcv(tickers, start=start)
    save_ohlcv(df, _ohlcv_path())
    print(f"[green]Saved[/green] {_ohlcv_path()} rows={len(df)}")

@app.command("build-features")
def build_features():
    """Build technical features and training labels."""
    ohlcv = load_ohlcv(_ohlcv_path())
    nifty = ohlcv[ohlcv["ticker"] == NIFTY_INDEX].copy()
    stocks = ohlcv[ohlcv["ticker"] != NIFTY_INDEX].copy()
    feat = add_technical_features(stocks, nifty)
    feat.to_parquet(_features_path(), index=False)
    print(f"[green]Saved[/green] {_features_path()} rows={len(feat)}")

@app.command()
def train(asof: str):
    """Train + calibrate model using data up to asof (YYYY-MM-DD)."""
    feat = pd.read_parquet(_features_path())
    model_dir = settings.models_dir / asof
    meta = train_calibrated_lgbm(feat, asof=asof, model_dir=model_dir)
    print(f"[green]Trained[/green] model at {model_dir} meta={meta}")

@app.command("train-expand")
def train_expand(asof: str, thr: float = typer.Option(0.012, "--thr", help="Expansion threshold, e.g. 0.012=+1.2%")):
    """Train Model-B (expand) up to asof, writes expand.pkl under data/models/<asof>/."""
    feat = pd.read_parquet(_features_path())
    model_dir = settings.models_dir / asof
    meta = train_expand_lgbm(feat, asof=asof, model_dir=model_dir, thr=thr)
    print(f"[green]Trained[/green] expand model at {model_dir} meta={meta}")

def _ensure_data():
    if not _ohlcv_path().exists():
        fetch()
    if not _features_path().exists():
        build_features()

def _ensure_model(feat: pd.DataFrame, asof_str: str):
    model_dir = settings.models_dir / asof_str
    if not (model_dir / "calib.pkl").exists():
        print(f"[yellow]No model for {asof_str}; training...[/yellow]")
        train_calibrated_lgbm(feat, asof=asof_str, model_dir=model_dir)

def _ensure_expand_model(feat: pd.DataFrame, asof_str: str):
    model_dir = settings.models_dir / asof_str
    if not (model_dir / "expand.pkl").exists():
        print(f"[yellow]No expand model for {asof_str}; training Model-B...[/yellow]")
        train_expand_lgbm(feat, asof=asof_str, model_dir=model_dir, thr=0.012)

def _run_one(
    target_date: str,
    mode: str,
    max_trades: int,
    no_trade_pup: Optional[float],
    no_trade_spread: Optional[float],
):
    _ensure_data()

    target = dt.date.fromisoformat(target_date)
    as_of = previous_business_day(target)
    asof_str = as_of.isoformat()

    feat = pd.read_parquet(_features_path())

    # Model-A
    _ensure_model(feat, asof_str)

    # Model-B
    try:
        _ensure_expand_model(feat, asof_str)
        expand = score_expand_asof(feat, asof=asof_str, model_dir=settings.models_dir / asof_str)
        expand = expand[["ticker", "p_expand"]]
    except Exception as e:
        print(f"[yellow]Model-B scoring failed; continuing with p_expand=0.0. Reason: {e}[/yellow]")
        expand = None

    scored = score_asof(feat, asof=asof_str, model_dir=settings.models_dir / asof_str)

    # Merge Model-B feature into scored so pipeline can use it
    if expand is not None and len(expand) > 0:
        scored = scored.merge(expand, on="ticker", how="left")
    if "p_expand" not in scored.columns:
        scored["p_expand"] = 0.0
    scored["p_expand"] = scored["p_expand"].fillna(0.0).astype(float)

    use_llm = bool(settings.openai_api_key)

    agent_out = run_agents(
        scored=scored,
        as_of=asof_str,
        use_llm=use_llm,
        mode=mode,
        max_trades=max_trades,
        no_trade_pup=no_trade_pup,
        no_trade_spread=no_trade_spread,
    )

    out_json = {
        "target_date": target_date,
        "as_of": asof_str,
        "mode": mode,
        "max_trades": max_trades,
        "use_llm": use_llm,
        "proposer": agent_out.get("proposer"),
        "reviewer": agent_out.get("reviewer"),
        "analyst": agent_out.get("analyst"),
    }

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = settings.reports_dir / f"{target_date}_{mode}.json"
    md_path = settings.reports_dir / f"{target_date}_{mode}.md"

    write_json(json_path, out_json)

    scored_for_report = agent_out.get("scored", scored)
    write_markdown(md_path, target_date, asof_str, agent_out, scored_for_report)

    print(f"[green]Wrote[/green] {json_path}")
    print(f"[green]Wrote[/green] {md_path}")

@app.command()
def recommend(
    target_date: str,
    mode: str = typer.Option("strict", "--mode", help="strict or aggressive"),
    max_trades: int = typer.Option(10, "--max-trades", help="Max final trades to output"),
    no_trade_pup: Optional[float] = typer.Option(None, "--no-trade-pup", help="Override NO-TRADE pup threshold"),
    no_trade_spread: Optional[float] = typer.Option(None, "--no-trade-spread", help="Override NO-TRADE spread threshold"),
):
    """Generate one report for target_date."""
    _run_one(target_date, mode=mode, max_trades=max_trades, no_trade_pup=no_trade_pup, no_trade_spread=no_trade_spread)
    print("[bold]Done.[/bold]")

@app.command("recommend-both")
def recommend_both(
    target_date: str,
    aggressive_max_trades: int = typer.Option(2, "--aggressive-max-trades", help="Max trades for aggressive report"),
    no_trade_pup: Optional[float] = typer.Option(None, "--no-trade-pup", help="Override NO-TRADE pup threshold"),
    no_trade_spread: Optional[float] = typer.Option(None, "--no-trade-spread", help="Override NO-TRADE spread threshold"),
):
    """Generate BOTH strict + aggressive reports for target_date."""
    _run_one(target_date, mode="strict", max_trades=10, no_trade_pup=no_trade_pup, no_trade_spread=no_trade_spread)
    _run_one(target_date, mode="aggressive", max_trades=aggressive_max_trades, no_trade_pup=no_trade_pup, no_trade_spread=no_trade_spread)
    print("[bold]Done (both reports).[/bold]")

if __name__ == "__main__":
    app()
