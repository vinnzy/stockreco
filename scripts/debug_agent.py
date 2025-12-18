import sys
from pathlib import Path
sys.path.append(str(Path(".").resolve() / "src"))

from stockreco.ingest.derivatives.local_csv_provider import LocalCsvProvider
from stockreco.agents.option_reco_agent import OptionRecoConfig, OptionRecoAgent, _days_to_expiry

def main():
    repo = Path(".").resolve()
    as_of = "2025-12-16"
    
    # 1. Get Chain
    prov = LocalCsvProvider(repo_root=repo, as_of=as_of)
    print("Fetching chain for RELIANCE...")
    chain = prov.get_option_chain("RELIANCE")
    print(f"Chain size: {len(chain)}")
    
    # 2. Simulate Filtering
    spot = 1542.3
    atr = 20.85
    side = "CE"
    
    cfg = OptionRecoConfig(mode="aggressive")
    min_dte = 2
    max_dte = 45
    min_strike = spot - cfg.max_moneyness_atr * atr
    max_strike = spot + cfg.max_moneyness_atr * atr
    
    print(f"Filter Params: Side={side}, Spot={spot}, MinDTE={min_dte}, ATR={atr}")
    print(f"Strike Range: {min_strike:.2f} to {max_strike:.2f}")
    
    candidates = []
    
    for r in chain:
        if (r.option_type or "").upper() != side:
            continue
        
        # Check DTE
        dte = _days_to_expiry(as_of, r.expiry)
        
        # Check Strike
        in_strike = (r.strike >= min_strike and r.strike <= max_strike)
        
        # Debug printing for first few CEs
        if len(candidates) < 5 and r.option_type == "CE":
            print(f"Candidate: Exp={r.expiry} DTE={dte} Strike={r.strike} InRange={in_strike}")

        if dte is None: continue
        if dte < min_dte or dte > max_dte: continue
        if not in_strike: continue
        
        candidates.append(r)
        
    print(f"Total Candidates Found: {len(candidates)}")

if __name__ == "__main__":
    main()
