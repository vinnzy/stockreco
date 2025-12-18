#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
import subprocess

from stockreco.pipeline.generate_signals_csv import generate_signals_csv, SignalConfig
from stockreco.ingest.derivatives.option_chain_loader import get_provider
from stockreco.universe.nifty50_static import nifty50_ns


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _as_csv_universe(u) -> str:
    """Accept list/tuple or comma-string and return comma-string."""
    if isinstance(u, (list, tuple)):
        return ",".join([str(s).strip().upper() for s in u if str(s).strip()])
    return ",".join([s.strip().upper() for s in str(u).split(",") if s.strip()])


def _auto_universe(repo: Path, as_of: str | None, provider_name: str) -> list[str]:
    """
    Default universe:
      - NIFTY, BANKNIFTY
      - NIFTY50 stocks ('.NS') that have option rows in local derivatives
    """
    provider = get_provider(provider_name, repo_root=repo, as_of=as_of)

    base = ["NIFTY", "BANKNIFTY"]
    candidates = nifty50_ns()

    ok: list[str] = []
    for sym in candidates:
        sym_provider = sym.replace(".NS", "")
        try:
            chain = provider.get_option_chain(sym_provider)
            # Sanity threshold so we don't include garbage/partial chains
            if chain and len(chain) > 50:
                ok.append(sym)
        except Exception:
            pass

    # deterministic order
    return base + sorted(set(ok))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD. Default: yesterday")
    ap.add_argument("--universe", required=False, help="Comma-separated tickers (optional)")
    ap.add_argument("--mode", default="aggressive", help="aggressive|balanced|conservative")
    ap.add_argument("--provider", default=None, help="local_csv|nse_fallback|zerodha|upstox")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    repo = _repo_root()
    provider_name = (args.provider or "local_csv")

    # 0) Decide universe (list of symbols) BEFORE generating signals
    if args.universe and args.universe.strip():
        universe_list = [s.strip().upper() for s in args.universe.split(",") if s.strip()]
    else:
        universe_list = _auto_universe(repo, args.as_of, provider_name)

    # 1) Generate signals CSV
    sig_path = generate_signals_csv(
        repo_root=repo,
        universe=universe_list,
        as_of=args.as_of,
        cfg=SignalConfig(mode=args.mode),
    )
    print(f"✅ Generated signals: {sig_path}")

    # 2) Run the option reco job
    as_of = (args.as_of or sig_path.parent.name)
    universe_str = _as_csv_universe(universe_list)

    cmd = [
        sys.executable,
        "scripts/run_eod_option_reco.py",
        "--as-of", as_of,
        "--universe", universe_str,
        "--provider", provider_name,
    ]

    # run_eod_option_reco.py does not accept --debug (unless you add it)
    print(f"▶ Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
