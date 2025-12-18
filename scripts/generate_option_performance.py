#!/usr/bin/env python3
import sys
import argparse
import json
import re
from pathlib import Path
from datetime import datetime

# ----------------- Data Loading -----------------
from stockreco.ingest.derivatives.option_chain_loader import get_provider

def _normalize_expiry(d_str: str) -> str:
    # d_str could be '2025-12-23', '23/12/2025', '23-Dec-2025'
    if not d_str: return ""
    try:
        # try ISO
        dt = datetime.strptime(d_str, "%Y-%m-%d")
        return dt.strftime("%d-%b-%Y").upper() # 23-DEC-2025
    except:
        pass
    try:
        dt = datetime.strptime(d_str, "%d/%m/%Y")
        return dt.strftime("%d-%b-%Y").upper()
    except:
        pass
    return d_str.upper()

def _key(r): 
    s = (r.get("symbol") or "").upper()
    st = float(r.get("strike") or 0)
    sd = (r.get("side") or "").upper()
    ex = _normalize_expiry(r.get("expiry") or "")
    return f"{s}|{st}|{sd}|{ex}"

def load_json(p: Path):
    if not p.exists(): return {}
    with p.open("r") as f:
        return json.load(f)

def save_json(data, p: Path):
    with p.open("w") as f:
        json.dump(data, f, indent=2)

def evaluate(reco_file: Path, outcome_date: str):
    print(f"Loading recos from {reco_file}...")
    reco_data = load_json(reco_file)
    recos = reco_data.get("recommender", [])
    if not recos:
        print("No recommendations found.")
        return

    # Deterministic Output Filename: option_performance_<RECO_DATE>.json
    # This ensures we keep updating the same file for a given recommendation batch.
    reco_date = reco_data.get("as_of", "unknown")
    if reco_date == "unknown":
        # try fallback from filename
        m = re.search(r"(\d{4}-\d{2}-\d{2})", reco_file.name)
        if m:
            reco_date = m.group(1)
            
    repo_root = Path(__file__).resolve().parent.parent
    perf_file = repo_root / "reports" / "options" / f"option_performance_{reco_date}.json"
    perf_file = repo_root / "reports" / "options" / f"option_performance_{reco_date}.json"
    print(f"Target Performance File: {perf_file}")
    
    # Validation: Outcome Date MUST be > Reco Date
    try:
        rdt = datetime.strptime(reco_date, "%Y-%m-%d")
        odt = datetime.strptime(outcome_date, "%Y-%m-%d")
        if odt <= rdt:
            print(f"Skipping evaluation: Outcome {outcome_date} is not strictly after Reco {reco_date}.")
            return
    except Exception as e:
        print(f"Date parsing warning: {e}")
    
    # Load Existing Performance (State)
    existing_data = load_json(perf_file)
    existing_results = { _key(r): r for r in existing_data.get("results", []) }
    
    # Check Reviewer Status
    reviewer_status = {}
    rev_data = reco_data.get("reviewer", {})
    if rev_data:
        for r in rev_data.get("approved", []):
            reviewer_status[_key(r)] = {"status": "APPROVED", "reason": "Passed checks"}
        for r in rev_data.get("rejected", []):
            reviewer_status[_key(r)] = {"status": "REJECTED", "reason": r.get("reason", "")}

    # Load Market Data for Outcome Date
    print(f"Loading market data for {outcome_date}...")
    try:
        provider = get_provider("local_csv", repo_root=repo_root, as_of=outcome_date)
    except Exception as e:
        print(f"Failed to load provider for {outcome_date}: {e}")
        return
    
    results = []
    
    # Current Date Object for Sell By check
    try:
        outcome_dt = datetime.strptime(outcome_date, "%Y-%m-%d")
    except:
        outcome_dt = None

    for r in recos:
        symbol = r.get("symbol")
        strike = r.get("strike")
        side = r.get("side") # CE/PE/None
        expiry = _normalize_expiry(r.get("expiry"))
        action = r.get("action")
        
        # Reco Attributes
        entry = float(r.get("entry_price") or 0)
        sl_val = float(r.get("sl_premium") or 0)
        targets = r.get("targets") or []
        sell_by_str = r.get("sell_by")
        
        # Reviewer Info
        k = _key(r)
        rev_info = reviewer_status.get(k, {"status": "UNKNOWN", "reason": ""})
        
        # Existing State
        prev_res = existing_results.get(k)
        
        # Initialize basic result if new
        res = prev_res or {
            "symbol": symbol,
            "strike": strike,
            "side": side,
            "expiry": expiry,
            "entry": entry,
            "target1": float(targets[0].get("premium") or targets[0].get("price")) if len(targets) > 0 else None,
            "target2": float(targets[1].get("premium") or targets[1].get("price")) if len(targets) > 1 else None,
            "sl": sl_val,
            "day_high": 0, # Max High seen
            "day_low": 999999, # Min Low seen
            "day_close": 0, # Latest Close
            "outcome": "PENDING",
            "details": "",
            "t1_hit_date": None,
            "t2_hit_date": None,
            "failure_date": None,
            "reco_confidence": r.get("confidence"),
            "reco_rationale": r.get("rationale"),
            "reviewer_decision": rev_info["status"],
            "reviewer_reason": rev_info["reason"],
            "as_of_reco": reco_date,
            "sell_by": sell_by_str,
            "history": [] # track daily [date, high, low, close]
        }
        
        # Preserve existing dates if they exist in prev_res but were missed by "or" above if prev_res was partial
        if prev_res:
            if "t1_hit_date" not in res: res["t1_hit_date"] = prev_res.get("t1_hit_date")
            if "t2_hit_date" not in res: res["t2_hit_date"] = prev_res.get("t2_hit_date")
            if "failure_date" not in res: res["failure_date"] = prev_res.get("failure_date")

        # Skip invalid/HOLD rows that are not options
        if action == "HOLD" and not side:
            res["outcome"] = "HOLD"
            results.append(res)
            continue
            
        # Optional: If already terminated, we skip heavy processing, BUT we still might want to update history if we want to see post-exit moves.
        # Actually, if SL Hit, trade is over. If T2 Hit, trade is over.
        # We will assume "Trade Active" check.
        # is_terminated = res["outcome"] in ["FAILURE", "SUCCESS_T2", "EXPIRED"]
        
        # Fetch Data for Today
        chain = []
        try:
             chain = provider.get_option_chain(symbol, expiry)
        except:
             pass
             
        contract = None
        for c in chain:
            if abs(c.strike - float(strike or 0)) < 0.1 and c.option_type == side:
                contract = c
                break
        
        day_high = None
        day_low = None
        day_close = None
        
        if contract:
            day_high = contract.high
            day_low = contract.low
            day_close = contract.ltp
            
            # Update State
            if day_high is not None:
                res["day_high"] = max(res["day_high"] or 0, day_high)
            if day_low is not None:
                # If simplified 999999 init
                curr_min = res["day_low"] if res["day_low"] != 999999 else day_low
                res["day_low"] = min(curr_min, day_low)
            if day_close is not None:
                res["day_close"] = day_close
                
            # Log History
            if day_high is not None and day_low is not None:
                hist_entry = { "date": outcome_date, "h": day_high, "l": day_low, "c": day_close }
                # Remove existing entry for same date if re-running
                clean_hist = [h for h in res.get("history", []) if h["date"] != outcome_date]
                clean_hist.append(hist_entry)
                clean_hist.sort(key=lambda x: x["date"])
                res["history"] = clean_hist
        
        # --- Evaluate New Outcome ---
        
        # Check Targets (High >= Tx)
        t1 = res.get("target1")
        t2 = res.get("target2")
        h = res.get("day_high", 0)
        
        if t2 and h >= t2:
            res["outcome"] = "SUCCESS_T2"
            if not res.get("t2_hit_date"):
                res["t2_hit_date"] = outcome_date
            # Implicitly T1 is also hit if T2 is hit
            if not res.get("t1_hit_date"):
                res["t1_hit_date"] = outcome_date

        elif t1 and h >= t1:
            # Only update outcome if it wasn't already SUCCESS_T2
            if res["outcome"] != "SUCCESS_T2":
                res["outcome"] = "SUCCESS_T1"
            
            if not res.get("t1_hit_date"):
                res["t1_hit_date"] = outcome_date
        
        # Determine if we are "safe" (Target Hit)
        is_safe = res["outcome"] in ["SUCCESS_T1", "SUCCESS_T2"]
        
        # Check SL (Low <= SL) - ONLY if not safe and not already failed
        # Note: We check against TODAY's low.
        if not is_safe and res["outcome"] != "FAILURE" and res["outcome"] != "EXPIRED":
             # We check specifically if TODAY's low hit the SL, or if the overall low hit SL?
             # Since we are re-evaluating incrementally, we should check if *cumulative* low hit SL *before* target was hit?
             # BUT, if we run purely incrementally, we know "previously it wasn't safe".
             # So if we are not safe now, we check if we failed NOW.
             
             # If we just use res["day_low"], that is the all-time low.
             # If the all-time low is below SL, it failed at SOME point.
             # However, if it hit target yesterday, and drops today, we are SAFE.
             # So we must rely on `is_safe` flag which comes from `res["outcome"]`.
             # If `res["outcome"]` was already SUCCESS_*, `is_safe` is True.
             
             if res.get("sl") and res["day_low"] <= res["sl"]:
                 res["outcome"] = "FAILURE"
                 res["details"] = f"SL Hit ({res['day_low']} <= {res['sl']})"
                 if not res.get("failure_date"):
                     res["failure_date"] = outcome_date

        # Update Details for Success
        details = []
        if res.get("t1_hit_date"): details.append(f"T1 Hit")
        if res.get("t2_hit_date"): details.append(f"T2 Hit")
        if res["outcome"] in ["SUCCESS_T1", "SUCCESS_T2"]:
             res["details"] = ", ".join(details)
        
        # Check Expiry/SellBy
        is_expired = False
        if mysellby := res.get("sell_by"):
            try:
                sb_dt = datetime.strptime(mysellby, "%Y-%m-%d")
                if outcome_dt and outcome_dt > sb_dt:
                    is_expired = True
            except: pass

        # Still pending? check expiry
        if res["outcome"] == "PENDING":
            if is_expired:
                res["outcome"] = "EXPIRED" # Treated as Failure usually
                res["details"] = f"Time Expired (Sell By {mysellby})"
                if not res.get("failure_date"):
                    res["failure_date"] = outcome_date # Expired is a form of failure date
            else:
                res["outcome"] = "PENDING"
        
        results.append(res)

    # Save
    out_obj = {
        "reco_date": reco_date,
        "last_updated": outcome_date,
        "results": results
    }
    
    print(f"Saving updated performance to {perf_file}...")
    save_json(out_obj, perf_file)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reco-file", required=True, help="Original reco file (e.g. option_reco_2025-12-16.json)")
    ap.add_argument("--outcome-date", required=True, help="Date of market data to check against (YYYY-MM-DD)")
    args = ap.parse_args()
    
    evaluate(Path(args.reco_file), args.outcome_date)
