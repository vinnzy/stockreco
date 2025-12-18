import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
import math

def load_fovolt_volatility(derivatives_dir: Path, as_of: str) -> Dict[str, float]:
    """
    Loads FOVOLT_<date>.csv and returns a map of Symbol -> Annualized Volatility.
    
    File format example:
    Date, Symbol, ..., Applicable Annualised Volatility (N) = Max (F or L)
    16-Dec-25,360ONE,...,0.43518145
    """
    # File naming: FOVOLT_16122025.csv or FOVOLT_16-Dec-2025.csv?
    # User showed: FOVOLT_16122025.csv for 2025-12-16
    # Let's try flexible matching
    
    date_clean = as_of.replace("-", "") # 20251216
    ddmmyyyy = f"{date_clean[6:8]}{date_clean[4:6]}{date_clean[0:4]}" # 16122025
    
    # Try multiple patterns
    patterns = [
        f"FOVOLT_{ddmmyyyy}.csv",
        f"FOVOLT_{ddmmyyyy}.CSV",
        "FOVOLT_*.csv" # Fallback if inside dated folder
    ]
    
    target_file = None
    # If derivatives_dir is the dated folder itself (e.g. data/derivatives/2025-12-16)
    for pat in patterns:
        files = list(derivatives_dir.glob(pat))
        if files:
            target_file = files[0]
            break
            
    if not target_file:
        return {}
        
    try:
        df = pd.read_csv(target_file)
        # Clean columns: strip spaces
        df.columns = [c.strip() for c in df.columns]
        
        # Locate Volatility Column
        # "Applicable Annualised Volatility (N) = Max (F or L)"
        # Or just look for "Applicable Annualised Volatility"
        vol_col = next((c for c in df.columns if "Applicable Annualised Volatility" in c), None)
        
        if not vol_col:
            return {}
            
        vol_map = {}
        for _, row in df.iterrows():
            sym = str(row.get("Symbol", "")).strip().upper()
            if not sym:
                continue
            
            try:
                v = float(row[vol_col])
                vol_map[sym] = v
            except (ValueError, TypeError):
                continue
                
        return vol_map
        
    except Exception:
        return {}

def load_fii_sentiment(derivatives_dir: Path, as_of: str) -> float:
    """
    Loads fao_participant_oi_<date>.csv and calculates FII Sentiment Score.
    Score = (Longs - Shorts) / (Longs + Shorts) for Index Futures.
    Range: -1.0 to 1.0
    
    Returns 0.0 if not found.
    """
    date_clean = as_of.replace("-", "") 
    ddmmyyyy = f"{date_clean[6:8]}{date_clean[4:6]}{date_clean[0:4]}"
    
    patterns = [
        f"fao_participant_oi_{ddmmyyyy}.csv",
        "fao_participant_oi_*.csv"
    ]
    
    target_file = None
    for pat in patterns:
        files = list(derivatives_dir.glob(pat))
        if files:
            target_file = files[0]
            break
            
    if not target_file:
        return 0.0
        
    try:
        # The file has a header on the second line often, or first line is metadata
        # User showed: ""Participant wise ..."" then header
        # Let's try reading normally, skipping rows if needed
        with open(target_file, 'r') as f:
            lines = f.readlines()
            
        # Find header line
        start_row = 0
        for i, line in enumerate(lines):
            if "Client Type" in line:
                start_row = i
                break
                
        df = pd.read_csv(target_file, skiprows=start_row)
        df.columns = [c.strip() for c in df.columns]
        
        # Look for FII row
        fii_row = df[df["Client Type"].str.contains("FII", case=False, na=False)]
        if fii_row.empty:
            return 0.0
            
        # Columns: "Future Index Long", "Future Index Short"
        longs = float(fii_row.iloc[0]["Future Index Long"])
        shorts = float(fii_row.iloc[0]["Future Index Short"])
        
        total = longs + shorts
        if total == 0:
            return 0.0
            
        return (longs - shorts) / total
        
    except Exception:
        return 0.0

def load_market_turnover(derivatives_dir: Path, as_of: str) -> Dict[str, float]:
    """
    Loads fao_top10cm_<date>.csv and returns aggregate activity stats.
    Useful for logging context.
    """
    # Implementation optional for now as it's just top 10 CM
    return {}
