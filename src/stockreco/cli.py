from __future__ import annotations
import typer
from rich import print
from pathlib import Path
import pandas as pd
import datetime as dt

from stockreco.config.settings import settings
from stockreco.universe.nifty50_static import NIFTY50, NIFTY_INDEX
from stockreco.ingest.yfinance_fetch import fetch_ohlcv, save_ohlcv, load_ohlcv
from stockreco.features.build_features import add_technical_features
from stockreco.models.train_model import train_calibrated_lgbm
from stockreco.models.predict import score_asof
from stockreco.agents.pipeline import run_agents
from stockreco.report.render import write_json, write_markdown
from stockreco.utils.dates import previous_business_day

app = typer.Typer(add_completion=False)

def _ohlcv_path():
    return settings.data_dir / "ohlcv.parquet"

def _features_path():
    return settings.data_dir / "features.parquet"

@app.command()
def fetch(start: str = "2018-01-01"):
    """Fetch EOD OHLCV for Nifty50 + Nifty index via yfinance."""
    tickers = NIFTY50 + [NIFTY_INDEX]
    print(f"[cyan]Fetching {len(tickers)} tickers from {start} ...[/cyan]")
    df = fetch_ohlcv(tickers, start=start)
    save_ohlcv(df, _ohlcv_path())
    print(f"[green]Saved[/green] {_ohlcv_path()} rows={len(df)}")

@app.command()
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

@app.command()
def recommend(target_date: str):
    """Generate next-day recommendations for target_date (YYYY-MM-DD)."""
    # Ensure data exists
    if not _ohlcv_path().exists():
        fetch()
    if not _features_path().exists():
        build_features()

    target = dt.date.fromisoformat(target_date)
    as_of = previous_business_day(target)  # simplistic; replace with proper holiday calendar later
    asof_str = as_of.isoformat()

    # Train if missing
    feat = pd.read_parquet(_features_path())
    model_dir = settings.models_dir / asof_str
    if not (model_dir / "calib.pkl").exists():
        print(f"[yellow]No model for {asof_str}; training...[/yellow]")
        train_calibrated_lgbm(feat, asof=asof_str, model_dir=model_dir)

    scored = score_asof(feat, asof=asof_str, model_dir=model_dir)
    use_llm = bool(settings.openai_api_key)
    agent_out = run_agents(scored, as_of=asof_str, use_llm=use_llm)

    out_json = {
        "target_date": target_date,
        "as_of": asof_str,
        "use_llm": use_llm,
        "proposer": agent_out.get("proposer"),
        "reviewer": agent_out.get("reviewer"),
        "analyst": agent_out.get("analyst"),
        "top15": scored.head(15)[["ticker","p_up","score"]].to_dict(orient="records"),
    }

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = settings.reports_dir / f"{target_date}.json"
    md_path = settings.reports_dir / f"{target_date}.md"
    write_json(json_path, out_json)
    write_markdown(md_path, target_date, asof_str, agent_out, scored)

    print(f"[green]Wrote[/green] {json_path}")
    print(f"[green]Wrote[/green] {md_path}")
    print(f"[bold]Done.[/bold]")

@app.command()
def backtest(start: str, end: str):
    """Walk-forward backtest summary."""
    from stockreco.backtest.simple_backtest import walk_forward
    feat = pd.read_parquet(_features_path())
    df = walk_forward(feat, start=start, end=end, model_root=settings.models_dir)
    out = settings.reports_dir / f"backtest_{start}_to_{end}.csv"
    df.to_csv(out, index=False)
    print(f"[green]Saved[/green] {out}")
    print(df.tail(10).to_string(index=False))

if __name__ == "__main__":
    app()
