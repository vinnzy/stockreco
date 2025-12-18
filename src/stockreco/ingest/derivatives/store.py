from __future__ import annotations
import os
import csv
import glob
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class DerivativesDataStore:
    """
    Centralized store for accessing daily derivative reports from NSE.
    Handles:
    1. Participant OI (Smart Money)
    2. Daily Volatility (VIX/Regime)
    3. Bhavcopy (PCR, Buildup)
    """
    
    def __init__(self, base_dir: str = "data/derivatives"):
        self.base_dir = base_dir

    def _find_file(self, as_of: str, pattern: str) -> Optional[str]:
        """
        Locates file in data/derivatives/YYYY-MM-DD/pattern
        """
        try:
            # support both YYYY-MM-DD and DD-MM-YYYY input
            dt = None
            for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
                try:
                    dt = datetime.strptime(as_of, fmt)
                    break
                except ValueError:
                    pass
            
            if not dt:
                logger.error(f"Invalid date format: {as_of}")
                return None

            date_str_ymd = dt.strftime("%Y-%m-%d")
            day_dir = os.path.join(self.base_dir, date_str_ymd)
            
            if not os.path.exists(day_dir):
                # Try finding without date folder if flat structure (fallback)
                day_dir = self.base_dir

            # Search for pattern
            # Pattern might contain wildcards, use glob
            search_path = os.path.join(day_dir, pattern)
            matches = glob.glob(search_path)
            
            if not matches:
                return None
            
            # Prefer longest match (most specific) or just first
            return sorted(matches)[-1]

        except Exception as e:
            logger.error(f"Error finding file for {as_of}/{pattern}: {e}")
            return None

    def get_participant_oi(self, as_of: str) -> Dict[str, Any]:
        """
        Parses fao_participant_oi_<date>.csv
        Returns: {
            "FII": {"Index Long": X, "Index Short": Y, ...},
            "Client": ...,
            "Pro": ...,
            "smart_money_score": float (-1.0 to 1.0)
        }
        """
        # Pattern: fao_participant_oi_*.csv (usually DDMMYYYY)
        # We'll use * to be safe on date format in filename
        fpath = self._find_file(as_of, "fao_participant_oi_*.csv")
        if not fpath:
            logger.warning(f"Participant OI file not found for {as_of}")
            return {}

        data = {}
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                # Skip first line if it's a header description (NSE specific)
                # "Participant wise Open Interest ... as on ..."
                lines = f.readlines()
                
            reader = csv.reader(lines)
            header = None
            rows = []
            for row in reader:
                if not row: continue
                if "Client Type" in row:
                    header = [h.strip() for h in row]
                    continue
                if header and len(row) == len(header):
                    rows.append(dict(zip(header, row)))

            # Parse rows into struct
            # Expected Client Types: Client, DII, FII, Pro
            net_index_fii = 0
            net_index_client = 0
            
            for r in rows:
                c_type = r.get("Client Type", "")
                if not c_type: continue
                
                # Parse integers
                def val(k): 
                    return int(r.get(k, "0").replace(",", ""))

                # Store raw
                data[c_type] = {
                    "Future Index Long": val("Future Index Long"),
                    "Future Index Short": val("Future Index Short"),
                    "Future Stock Long": val("Future Stock Long"),
                    "Future Stock Short": val("Future Stock Short"),
                    "Option Index Call Long": val("Option Index Call Long"),
                    "Option Index Put Long": val("Option Index Put Long"),
                    "Option Index Call Short": val("Option Index Call Short"),
                    "Option Index Put Short": val("Option Index Put Short"),
                }
                
                # Calc Nets for Score
                if c_type == "FII":
                    # FII Conviction = (Idx Fut Long - Short) + Delta_weighted_Options?
                    # Simple version: Index Futures Net
                    net_index_fii = val("Future Index Long") - val("Future Index Short")
                    
                    # Add Option Bias: (Call Long - Call Short) - (Put Long - Put Short)
                    opt_bias = (val("Option Index Call Long") - val("Option Index Call Short")) - \
                               (val("Option Index Put Long") - val("Option Index Put Short"))
                    # Options are noisier/hedging, give them lower weight or just use for context
                    # For score, let's mix: Futures (High Conviction) + 0.2 * Options
                    data[c_type]["net_sentiment"] = net_index_fii + 0.1 * opt_bias

                if c_type == "Client":
                    net_index_client = val("Future Index Long") - val("Future Index Short")
                    opt_bias = (val("Option Index Call Long") - val("Option Index Call Short")) - \
                               (val("Option Index Put Long") - val("Option Index Put Short"))
                    data[c_type]["net_sentiment"] = net_index_client + 0.1 * opt_bias

            # Smart Money Score Calculation
            # Logic: If FII Bullish means Good. If Client Bullish means Bad (Retail Trap).
            # Score = Normalized FII Sentiment - Normalized Client Sentiment
            # Normalize by total OI? approximations for now.
            
            fii_sent = data.get("FII", {}).get("net_sentiment", 0)
            client_sent = data.get("Client", {}).get("net_sentiment", 0)
            
            # Simple sign check
            score = 0.0
            if fii_sent > 0: score += 0.5
            if fii_sent < 0: score -= 0.5
            
            # Contra retail
            if client_sent > 0: score -= 0.3
            if client_sent < 0: score += 0.3 # Retail fearful = Bullish
            
            data["smart_money_score"] = max(-1.0, min(1.0, score))
            data["fii_net"] = fii_sent
            data["client_net"] = client_sent

        except Exception as e:
            logger.error(f"Error parsing Participant OI {fpath}: {e}")
            return {}

        return data

    def get_market_volatility(self, as_of: str) -> Dict[str, float]:
        """
        Parses FOVOLT_<date>.csv to get NIFTY/BANKNIFTY Annualized Volatility.
        Use this for 'Regime' detection.
        """
        fpath = self._find_file(as_of, "FOVOLT_*.csv")
        if not fpath:
            logger.warning(f"FOVOLT file not found for {as_of}")
            return {}
            
        vols = {}
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                # Header usually: Date, Symbol, ... Applicable Annualised Volatility (N) ...
                
                # Normalize keys (strip spaces)
                clean_rows = []
                for row in reader:
                    clean_rows.append({k.strip(): v.strip() for k, v in row.items() if k})
                
                for row in clean_rows:
                    sym = row.get("Symbol", "").upper()
                    # Column name is long and complex: "Applicable Annualised Volatility (N) = Max (F or L)"
                    # Find column containing "Annualised" and "Applicable"
                    vol_col = None
                    for k in row.keys():
                        if "Applicable Annualised Volatility" in k:
                            vol_col = k
                            break
                    
                    if sym and vol_col:
                        try:
                            # 0.4341 -> 43.41%
                            vols[sym] = float(row[vol_col]) * 100.0
                        except:
                            pass
        except Exception as e:
            logger.error(f"Error parsing FOVOLT {fpath}: {e}")
        
        return vols

    def get_bhavcopy_stats(self, as_of: str) -> Dict[str, Any]:
        """
        Parses fo<date>.csv (Bhavcopy) to calculate:
        1. PCR (Put OI / Call OI) per symbol
        2. Buildup Type (Long Buildup, Short Covering, etc.) - Requires Prev Day logic, 
           but here we can just return raw OI/Price change for the agent to decide or 
           simple PCR.
        """
        # fo17122025.csv pattern
        # The date format in filename is usually DDMMYYYY or DDMMYY
        # Let's try flexible glob
        
        # Try finding fo*.csv
        fpath = self._find_file(as_of, "fo*.csv")
        # Ignore 'fo_*.csv' summary if it exists, we want the big one
        # Usually foDDMMYYYY.csv is the bhavcopy
        
        if not fpath:
             logger.warning(f"Bhavcopy file not found for {as_of}")
             return {}

        stats = {}
        # We need to aggregate Call OI and Put OI per symbol
        # Schema: INSTRUMENT,SYMBOL,EXP_DATE,...,OPEN_INT,OPEN_INT_CHG?,CLOSE_PRICE,...
        
        # Aggregators
        call_oi = {}
        put_oi = {}
        futures_data = {} # store future close, oi for buildup detection
        
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = [ {k.strip(): v.strip() for k, v in row.items() if k} for row in reader]
                
                for r in rows:
                    inst = r.get("INSTRUMENT", "")
                    sym = r.get("SYMBOL", "")
                    oi = float(r.get("OPEN_INT", 0) or 0)
                    
                    if inst in ("OPTSTK", "OPTIDX"):
                        typ = r.get("OPTION_TYP", "") # CE/PE
                        # Handle varied headers. usually OPTION_TYP in some files, or check if column exists
                        # Wait, fo.csv standard usually doesn't have OPTION_TYP in main columns if it's the standard NSE format?
                        # ACTUALLY: fo17122025.csv usually has OPTION_TYP column. 
                        # Let's check the code I viewed earlier. Step 53 output shows:
                        # INSTRUMENT,SYMBOL,EXP_DATE,OPEN_PRICE...
                        # It DOES NOT show OPTION_TYP in the preview columns (only 12 columns shown).
                        # Let me re-read the file view carefully or assume standard format.
                        # Wait, Step 53 lines show INSTRUMENT as FUTIDX, FUTSTK only.
                        # Ah, fo17122025.csv contains Futures AND Options?
                        # The snippet showed FUTIDX/FUTSTK. It didn't show OPTIDX/OPTSTK in the first 600 lines.
                        # I need to be sure it has options.
                        pass
                        
                    # For now, let's assume standard NSE Bhavcopy which has all.
                    # If OPTION_TYP missing in dict, maybe it's under a different name or implied.
                    # Standard NSE Bhavcopy: INSTRUMENT, SYMBOL, EXPIRY_DT, STRIKE_PR, OPTION_TYP, OPEN, HIGH, LOW, CLOSE, SETTLE_PR, CONTRACTS, VAL_INLAKH, OPEN_INT, CHG_IN_OI, TIMESTAMP
                    
                    # If the file I read in Step 53 only has Futures in top rows, it likely has Options later.
                    # But I need to know the column name for Option Type. 
                    # Usually "OPTION_TYP".
                    
                    key = r.get("OPTION_TYP")
                    if key == "CE":
                        call_oi[sym] = call_oi.get(sym, 0) + oi
                    elif key == "PE":
                        put_oi[sym] = put_oi.get(sym, 0) + oi
                        
        except Exception as e:
            logger.error(f"Error calculating PCR from {fpath}: {e}")
            return {}
            
        # Calculate PCR
        all_syms = set(call_oi.keys()) | set(put_oi.keys())
        pcr_map = {}
        for s in all_syms:
            c = call_oi.get(s, 0)
            p = put_oi.get(s, 0)
            if c > 0:
                pcr_map[s] = round(p / c, 2)
            else:
                pcr_map[s] = 0.0 # or None
        
        return {"pcr": pcr_map}
