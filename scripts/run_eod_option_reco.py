#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from stockreco.universe.nifty50_static import nifty50_ns


from stockreco.config.derivatives_config import load_derivatives_config
from stockreco.ingest.derivatives.option_chain_loader import get_provider
from stockreco.agents.option_reco_agent import OptionRecoAgent, OptionReco
from stockreco.report.option_reco_report import write_option_recos

def _default_universe_from_local_derivs(provider, as_of: str) -> list[str]:
    """
    Builds default universe:
      - NIFTY + BANKNIFTY
      - NIFTY50 stocks ('.NS') where options exist in local op/fo files
    """
    base = ["NIFTY", "BANKNIFTY"]

    # Candidate list
    candidates = nifty50_ns()

    # Check if options exist by trying to load chain (fast enough for 50)
    ok = []
    for sym in candidates:
        sym_provider = sym.replace(".NS", "").replace(".BO", "")
        try:
            chain = provider.get_option_chain(sym_provider)
            if chain and len(chain) > 50:  # sanity threshold: avoid tiny/partial
                ok.append(sym)
        except Exception:
            pass

    # Keep deterministic order
    return base + sorted(ok)

def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent

def _is_date_folder(name: str) -> bool:
    try:
        datetime.strptime(name, "%Y-%m-%d")
        return True
    except Exception:
        return False

def _latest_models_date(models_root: Path) -> str:
    dates = [p.name for p in models_root.iterdir() if p.is_dir() and _is_date_folder(p.name)]
    if not dates:
        raise RuntimeError(f"No dated folders under {models_root}")
    
    # Sort descending
    dates = sorted(dates, reverse=True)
    
    # Try to find a date that ALSO has derivatives data (if data/derivatives exists)
    # This prevents the issue where models has 2025-12-13 but options only has 2025-12-12
    deriv_root = models_root.parent / "derivatives"
    if deriv_root.exists():
        for d in dates:
            if (deriv_root / d).exists():
                return d
    
    # Fallback: just return latest model date
    return dates[0]

def _load_signals(models_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load signals from any CSV under models_dir. Returns map ticker->row."""
    best: Dict[str, Dict[str, Any]] = {}
    for csv in models_dir.rglob("*.csv"):
        try:
            df = pd.read_csv(csv)
        except Exception:
            continue
        cols = {c.lower().strip(): c for c in df.columns}
        if "buy_win" not in cols or "sell_win" not in cols:
            continue
        sym_col = cols.get("ticker") or cols.get("symbol") or cols.get("tradingsymbol") or cols.get("sym")
        if not sym_col:
            continue

        for _, r in df.iterrows():
            ticker = str(r.get(sym_col) or "").strip().upper()
            if not ticker or ticker == "NAN":
                continue
            row = { "ticker": ticker }
            row["buy_win"] = int(float(r.get(cols["buy_win"]) or 0))
            row["sell_win"] = int(float(r.get(cols["sell_win"]) or 0))
            # carry extra numeric fields if present
            for k in ["mode","ret_oc","exp_oh","dd_ol","atr_points","atr_pct","buy_thr","sell_thr", "direction_score", "buy_soft", "sell_soft", "strength"]:
                if k in cols:
                    row[k] = r.get(cols[k])
            best[ticker] = row
    return best

def _default_signal(ticker: str, mode: str = "aggressive") -> Dict[str, Any]:
    # ensures we still emit a reco row even if signal is neutral/missing
    return dict(
        ticker=ticker,
        mode=mode,
        buy_win=0,
        sell_win=0,
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD under data/models/")
    ap.add_argument("--provider", default=None, help="local_csv|nse_fallback|zerodha|upstox")
    ap.add_argument("--universe", default=None, help="Comma-separated tickers")
    ap.add_argument("--out-dir", default="reports")
    ap.add_argument("--mode", default="strict", choices=["strict", "opportunistic", "speculative"])
    ap.add_argument("--use-llm", action="store_true", help="Enable LLM-based qualitative review and analysis (requires OPENAI_API_KEY)")

    args = ap.parse_args()

    repo = _repo_root()
    cfg = load_derivatives_config(repo)

    models_root = repo / "data" / "models"
    as_of = args.as_of or _latest_models_date(models_root)
    models_dir = models_root / as_of

    signal_map = _load_signals(models_dir)

    if not args.universe:
        # if no universe passed, use all tickers in signal_map
        universe = sorted(signal_map.keys())
    else:
        universe = [s.strip().upper() for s in args.universe.split(",") if s.strip()]

    if not universe:
        raise RuntimeError("Universe is empty; pass --universe or ensure signals exist.")

    provider_name = (args.provider or cfg.provider)
    provider = get_provider(provider_name, repo_root=repo, as_of=as_of)

    if args.universe:
        universe = [s.strip().upper() for s in args.universe.split(",") if s.strip()]
    else:
        universe = _default_universe_from_local_derivs(provider, as_of=as_of)

    from stockreco.agents.option_reco_agent import OptionRecoAgent, OptionRecoConfig
    from stockreco.agents.option_reviewer import review_option_recommendations
    
    agent = OptionRecoAgent(OptionRecoConfig(mode=args.mode))

    # 1. Proposer Step: Generate candidates
    recos: List[OptionReco] = []
    candidates_for_llm = []
    
    for sym_out in universe:
        sym_provider = sym_out.replace(".NS","").replace(".BO","")
        signal_row = signal_map.get(sym_out) or signal_map.get(sym_provider) or _default_signal(sym_out, mode=getattr(cfg, "mode", "aggressive"))

        try:
            underlying = provider.get_underlying(sym_provider)
            chain = provider.get_option_chain(sym_provider)
            reco = agent.recommend(as_of=as_of, symbol=sym_out, signal_row=signal_row, underlying=underlying, chain=chain)
            
            if reco is None:
                reco = OptionReco(as_of=as_of, symbol=sym_out, bias="NEUTRAL", instrument="NONE", action="HOLD",
                                  confidence=0.0, rationale=["No actionable signal for next session."])
            
            recos.append(reco)
            
            # Prepare for LLM (only actionable calls/puts)
            if reco.instrument == "OPTION" and reco.action == "BUY" and args.use_llm:
                candidates_for_llm.append({
                    "symbol": reco.symbol,
                    "action": reco.action,
                    "side": reco.side,
                    "strike": reco.strike,
                    "expiry": reco.expiry,
                    "confidence": reco.confidence,
                    "entry": reco.entry,
                    "iv": reco.iv,
                    "theta_per_day": reco.theta_per_day,
                    "rationale": reco.rationale,
                    "diagnostics": reco.diagnostics
                })
                
        except Exception as e:
            recos.append(OptionReco(as_of=as_of, symbol=sym_out, bias="NEUTRAL", instrument="NONE", action="HOLD",
                                   confidence=0.0, rationale=[f"Failed to load derivatives/provider data: {e}"]))

    # 2. Rule-Based Reviewer
    reviewed = review_option_recommendations(recos, mode=args.mode)
    
    # 3. LLM Reviewer & Analyst (Optional)
    if args.use_llm and candidates_for_llm:
        try:
            from stockreco.agents.options_llm import review_options_llm, analyze_options_llm
            print("\nRunning LLM qualitative review...")
            
            # A) LLM Review
            llm_review = review_options_llm(candidates_for_llm, as_of)
            llm_rejected = {r["symbol"]: r["reason"] for r in llm_review.get("rejected", [])}
            
            # Merge LLM rejections into structured output
            # We move items from approved to rejected if LLM rejects them
            final_approved_objs = []
            for item in reviewed["reviewer"]["approved"]:
                sym = item["symbol"]
                if sym in llm_rejected:
                    # Move to rejected list with LLM reason
                    reason = f"[LLM] {llm_rejected[sym]}"
                    reviewed["reviewer"]["rejected"].append({"symbol": sym, "reason": reason})
                    # Remove from final list
                else:
                    final_approved_objs.append(item)
            
            # Update approved list
            reviewed["reviewer"]["approved"] = final_approved_objs
            reviewed["final"] = final_approved_objs
            
            # B) LLM Analyst (Thesis generation)
            if final_approved_objs:
                print("Running LLM analyst for trading thesis...")
                # Convert back to dicts for LLM if they are not already
                # (They are dicts in the reviewed['final'] output)
                llm_analysis = analyze_options_llm(final_approved_objs, as_of)
                
                # Merge qualitative analysis
                analysis_map = {r["symbol"]: r for r in llm_analysis.get("recommendations", [])}
                
                for item in reviewed["final"]:
                    sym = item["symbol"]
                    if sym in analysis_map:
                        ana = analysis_map[sym]
                        # Replace rationale with LLM thesis
                        item["rationale"] = [ana.get("rationale_summary", "")]
                        # Apply confidence adjustment
                        adj = ana.get("confidence_adjustment", 0.0)
                        if adj:
                            old_conf = item["confidence"]
                            new_conf = min(1.0, max(0.0, old_conf + adj))
                            item["confidence"] = new_conf
                            item["diagnostics"]["llm_confidence_adj"] = adj

        except Exception as e:
            print(f"LLM stage failed (falling back to rule-based): {e}")

    out = repo / args.out_dir
    paths = write_option_recos(out, as_of, reviewed)
    print(f"Wrote: {paths['json']}")
    print(f"Wrote: {paths['csv']}")
    
    # Print summary
    total = len(recos)
    approved = len(reviewed['reviewer']['approved'])
    rejected = len(reviewed['reviewer']['rejected'])
    print(f"\nReviewer Summary ({args.mode} mode" + (" + LLM" if args.use_llm else "") + "):")
    print(f"  Total recommendations: {total}")
    print(f"  Approved: {approved}")
    print(f"  Rejected: {rejected}")
    if rejected > 0:
        print(f"\nRejection reasons:")
        for r in reviewed['reviewer']['rejected']:
            reason = r['reason']
            # Highlight LLM rejections
            prefix = "🤖 " if "[LLM]" in reason else "  - "
            print(f"{prefix}{r.get('symbol')} ({r.get('side', 'N/A')} {r.get('strike', 'N/A')}): {reason}")


if __name__ == "__main__":
    main()
