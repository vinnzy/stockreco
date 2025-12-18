#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from datetime import datetime
import json
from typing import List, Dict, Any, Optional
import csv
from stockreco.universe.nifty50_static import nifty50_ns


from stockreco.config.derivatives_config import load_derivatives_config
from stockreco.ingest.derivatives.option_chain_loader import get_provider
from stockreco.agents.option_reco_agent import OptionRecoAgent, OptionReco
from stockreco.report.option_reco_report import write_option_recos
from stockreco.ingest.derivatives.market_stats_loader import load_fovolt_volatility, load_fii_sentiment
from stockreco.ingest.derivatives.store import DerivativesDataStore

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
    for csv_file in models_dir.rglob("*.csv"):
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    continue
                
                # Normalize columns to lowercase stripped
                cols_map = {c: c.lower().strip() for c in reader.fieldnames}
                # inverse map for lookup
                inv_cols = {v: k for k, v in cols_map.items()}
                
                if "buy_win" not in inv_cols or "sell_win" not in inv_cols:
                    continue
                
                sym_col = inv_cols.get("ticker") or inv_cols.get("symbol") or inv_cols.get("tradingsymbol") or inv_cols.get("sym")
                if not sym_col:
                    continue

                for row in reader:
                    ticker = str(row.get(sym_col) or "").strip().upper()
                    if not ticker or ticker == "NAN":
                        continue
                    
                    data_row = { "ticker": ticker }
                    try:
                        data_row["buy_win"] = int(float(row.get(inv_cols["buy_win"], 0) or 0))
                        data_row["sell_win"] = int(float(row.get(inv_cols["sell_win"], 0) or 0))
                    except ValueError:
                        continue

                    # carry extra numeric fields if present
                    for k in ["mode","ret_oc","exp_oh","dd_ol","atr_points","atr_pct","buy_thr","sell_thr", "direction_score", "buy_soft", "sell_soft", "strength"]:
                        if k in inv_cols:
                            val = row.get(inv_cols[k])
                            if val:
                                try:
                                    data_row[k] = float(val)
                                except ValueError:
                                    data_row[k] = val
                    best[ticker] = data_row
        except Exception as e:
            print(f"Error reading {csv_file}: {e}")
            continue
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

    # NEW: Fetch Derivatives Context (Smart Money, PCR, VIX)
    store = DerivativesDataStore()
    participant_data = store.get_participant_oi(as_of)
    bhav_stats = store.get_bhavcopy_stats(as_of)
    vol_data_new = store.get_market_volatility(as_of)
    
    # Global VIX Proxy (NIFTY annualized vol)
    global_vix = vol_data_new.get("NIFTY", 0.0)
    print(f"Derivatives Context ({as_of}): SmartMoneyScore={participant_data.get('smart_money_score', 0.0):.2f}, VIX(Nifty)={global_vix:.2f}, PCR Coverage={len(bhav_stats.get('pcr', {}))}")

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
        # Normalize: strip spaces, upper, remove suffix for uniq set
        raw_univ = [s.strip().upper() for s in args.universe.split(",") if s.strip()]
        # We want to keep the unified format (e.g. without NS) for processing?
        # Actually, the script uses sym.replace(".NS","") for provider but relies on sym_out for output.
        # Let's standardize on NO-SUFFIX for internal logic, or allow duplicates if user explicitly asked?
        # Standardizing on suffix-less seems safer for deduplication.
        universe = sorted(list(set([u.replace(".NS","").replace(".BO","") for u in raw_univ])))
    else:
        universe = _default_universe_from_local_derivs(provider, as_of=as_of)
        # Ensure default universe is also clean
        universe = sorted(list(set([u.replace(".NS","").replace(".BO","") for u in universe])))

    from stockreco.agents.option_reco_agent import OptionRecoAgent, OptionRecoConfig
    from stockreco.agents.option_reviewer import review_option_recommendations
    
    agent = OptionRecoAgent(OptionRecoConfig(mode=args.mode))

    # --- Load Auxiliary Data (FOVOLT, FII Sentiment) ---
    deriv_date_dir = repo / "data" / "derivatives" / as_of
    vol_map = {}
    fii_sent = 0.0
    
    if deriv_date_dir.exists():
        print(f"Loading auxiliary derivatives data from {deriv_date_dir}...")
        vol_map = load_fovolt_volatility(deriv_date_dir, as_of)
        fii_sent = load_fii_sentiment(deriv_date_dir, as_of)
        
        if vol_map:
            print(f"  > Loaded {len(vol_map)} stocks with volatility data.")
        else:
            print("  > No FOVOLT volatility data found.")
            
        if fii_sent != 0.0:
            sentiment_str = "Bullish" if fii_sent > 0 else "Bearish"
            print(f"  > FII Sentiment Score: {fii_sent:.3f} ({sentiment_str})")
        else:
            print("  > No FII sentiment data found (or neutral).")
    else:
        print(f"Warning: Derivatives data folder {deriv_date_dir} not found. Skipping auxiliary stats.")

    # 1. Proposer Step: Generate candidates
    recos: List[OptionReco] = []
    candidates_for_llm = []
    
    for sym_out in universe:
        sym_provider = sym_out.replace(".NS","").replace(".BO","")
        # Try exact match, then with .NS suffix (common in signal files)
        signal_row = signal_map.get(sym_out) or signal_map.get(sym_out + ".NS") or signal_map.get(sym_provider)
        
        if not signal_row:
             signal_row = _default_signal(sym_out, mode=getattr(cfg, "mode", "aggressive"))

        # Inject Aux Data
        signal_row["volatility_annualized"] = vol_map.get(sym_provider, 0.0)
        signal_row["fii_sentiment"] = fii_sent
        
        # Inject NEW Context
        signal_row["smart_money_score"] = participant_data.get("smart_money_score", 0.0)
        signal_row["pcr"] = bhav_stats.get("pcr", {}).get(sym_out, bhav_stats.get("pcr", {}).get(sym_provider, 0.0))

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
                    "entry": reco.entry_price,
                    "iv": reco.iv,
                    "theta_per_day": reco.theta_per_day,
                    "rationale": reco.rationale,
                    "diagnostics": reco.diagnostics
                })
                
        except Exception as e:
            recos.append(OptionReco(as_of=as_of, symbol=sym_out, bias="NEUTRAL", instrument="NONE", action="HOLD",
                                   confidence=0.0, rationale=[f"Failed to load derivatives/provider data: {e}"]))

    # 2. Rule-Based Reviewer
    reviewed = review_option_recommendations(recos, mode=args.mode, vix=global_vix)
    
    # SORT: Sort BOTH lists by confidence descending
    # This ensures the 'recommender' list in JSON (used by UI for rejected items) is also sorted
    recos.sort(key=lambda x: getattr(x, "confidence", 0.0), reverse=True)
    reviewed["final"].sort(key=lambda x: getattr(x, "confidence", 0.0), reverse=True)
    
    # DEBUG: Log Nifty details if present
    for r in recos:
        if "NIFTY" in r.symbol.upper():
            print(f"[DEBUG] Nifty Reco: {r.symbol} Action={r.action} Conf={r.confidence} Rationale={r.rationale[:2]}")
            
    # 3. LLM Reviewer & Analyst (Optional) -> Now formally the "Analyst Layer"
    # We run the Analyst Agent regardless of LLM flag (it has rule-based fallback)
    from stockreco.agents.option_analyst_agent import OptionAnalystAgent

    
    # Filter original OptionReco objects that were approved
    # Note: reviewed["final"] contains OptionReco objects, not dicts
    # CRITICAL: Preserve the SORTED order from reviewed['final']
    # Create a map for fast lookup but iterate over reviewed['final'] to keep order
    approved_symbols_set = {r.symbol for r in reviewed["final"]}
    
    # We want the FULL option reco objects corresponding to the approved symbols, sorted by confidence.
    # reviewed['final'] ALREADY contains the full objects (from line 218 in reviewer.py)
    # So we can just use reviewed['final'] directly filtering for BUY action if needed.
    # The original code re-filtered 'recos' to be safe? 
    # Let's trust reviewed['final'] but ensure it matches the 'recos' objects (which it does, by reference).
    # But wait, Analyst might expect BUY only?
    approved_recos_objs = [r for r in reviewed["final"] if r.action == "BUY"]
    
    # Double check sort order is preserved (it is, since we sorted reviewed['final'])
    print(f"\nRunning Analyst Layer on {len(approved_recos_objs)} approved trades (Sorted by Confidence)...")
    if approved_recos_objs:
        print(f"  Top pick: {approved_recos_objs[0].symbol} ({approved_recos_objs[0].confidence:.2f})")
        
    analyst_agent = OptionAnalystAgent(use_llm=args.use_llm)
    analyst_results = analyst_agent.analyze(approved_recos_objs, as_of, vol_map=vol_map, fii_sent=fii_sent)
    
    # Save Analyst Report
    analyst_report = {
        "as_of": as_of,
        "analyst_recos": [r.to_dict() for r in analyst_results]
    }
    
    analyst_json_path = repo / "reports" / "options" / f"option_analyst_{as_of}.json"
    with open(analyst_json_path, "w") as f:
        json.dump(analyst_report, f, indent=2)
    print(f"Wrote Analyst Report: {analyst_json_path}")
    
    # Legacy LLM logic (embedded in script) - REMOVED/REPLACED by Analyst Agent above
    # The Analyst Agent now encapsulates the LLM analysis logic logic.
    # We update the 'reviewed' object with analyst insights if we want to keep one single truth file?
    # Or start relying on the analyst file?
    # User requested separate page, so separate file is good.
    # But for backward compatibility, we can perform the "merge back" logic here too if needed.
    # For now, let's keep the 'reviewed' object as is (Raw Recommender + Reviewer)
    # And the 'analyst' object as the premium layer.
    
    # Optional: Update the reviewed['final'] confidence/rationale based on analyst for the main page?
    # The user asked for "another page", so maybe keep them distinct.
    # But improving the main accuracy was also a goal.
    # Let's start with distinct to avoid confusion.
    
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
