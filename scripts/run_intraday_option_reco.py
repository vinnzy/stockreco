#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
import json

from stockreco.config.derivatives_config import load_derivatives_config
from stockreco.ingest.derivatives.option_chain_loader import get_provider
from stockreco.agents.intraday_option_agent import IntradayOptionAgent
from stockreco.universe.nifty50_static import nifty50_ns

def _default_universe_from_local_derivs(provider, as_of: str) -> list[str]:
    # Same fallback as main script
    base = ["NIFTY", "BANKNIFTY"]
    candidates = nifty50_ns()
    ok = []
    for sym in candidates:
        sym_provider = sym.replace(".NS", "").replace(".BO", "")
        try:
            chain = provider.get_option_chain(sym_provider)
            if chain and len(chain) > 50:
                ok.append(sym)
        except Exception:
            pass
    return base + sorted(ok)

def _load_signals(models_dir: Path) -> dict:
    best = {}
    for csv in models_dir.rglob("*.csv"):
        try:
            df = pd.read_csv(csv)
        except Exception:
             continue
        cols = {c.lower().strip(): c for c in df.columns}
        sym_col = cols.get("ticker") or cols.get("symbol") or cols.get("tradingsymbol")
        if not sym_col: continue
        
        for _, r in df.iterrows():
            ticker = str(r.get(sym_col) or "").strip().upper()
            if not ticker or ticker == "NAN": continue
            
            row = { "ticker": ticker }
            # Copy all potentially useful cols
            for k, v in r.items():
                if isinstance(k, str):
                    row[k.lower()] = v
            best[ticker] = row
    return best

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--universe", default=None)
    ap.add_argument("--out-dir", default="reports/options")
    args = ap.parse_args()
    
    repo = Path(__file__).resolve().parent.parent
    
    # 1. Determine Date
    if args.as_of:
        as_of = args.as_of
    else:
        # Latest models date
        models_root = repo / "data" / "models"
        dates = sorted([p.name for p in models_root.iterdir() if p.is_dir()], reverse=True)
        if not dates:
             raise RuntimeError("No model data found")
        as_of = dates[0]
        
    print(f"Running Intraday Option Reco for {as_of}")
    
    # 2. Setup Data
    models_dir = repo / "data" / "models" / as_of
    signal_map = _load_signals(models_dir)
    
    provider = get_provider("local_csv", repo_root=repo, as_of=as_of) # Force local for speed/consistency
    
    if args.universe:
        universe = [s.strip().upper() for s in args.universe.split(",")]
    else:
        universe = _default_universe_from_local_derivs(provider, as_of)
        
    # 3. Agent
    agent = IntradayOptionAgent()
    recos = []
    
    for sym in universe:
        sym_clean = sym.replace(".NS","").replace(".BO","")
        signal = signal_map.get(sym) or signal_map.get(sym_clean)
        
        if not signal:
            # Skip if no signal
            continue
            
        try:
            underlying = provider.get_underlying(sym_clean)
            chain = provider.get_option_chain(sym_clean)
            
            reco = agent.recommend(as_of, sym, signal, underlying, chain)
            if reco:
                recos.append(reco)
                print(f"  [+] Recommended {sym}: {reco.side} {reco.strike} (Conf: {reco.confidence})")
        
        except Exception as e:
            # print(f"  [-] Error {sym}: {e}")
            pass
            
    # 4. Save
    output_dir = repo / args.out_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    out_file = output_dir / f"intraday_reco_{as_of}.json"
    reco_dicts = [r.to_dict() for r in recos]
    
    # Sort by confidence descending
    reco_dicts.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Wrap in reviewer structure to satisfy UI expectations (and user request)
    # Since we filter in the agent, all are "approved" by the Intraday Agent.
    final_structure = {
        "reviewer": {
            "approved": reco_dicts,
            "rejected": []
        },
        "final": reco_dicts
    }
    
    out_file.write_text(json.dumps(final_structure, indent=2))
    print(f"Wrote {len(recos)} recommendations to {out_file}")

if __name__ == "__main__":
    main()
