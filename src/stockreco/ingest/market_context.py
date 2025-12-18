from __future__ import annotations

import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class MarketContext:
    volatility: Dict[str, float]  # Symbol -> Annualized Volatility
    participant_oi: Dict[str, Dict[str, Any]] # Client Type -> {Long/Short data}
    bulk_deals: Dict[str, List[Dict[str, Any]]] # Symbol -> List of deals
    delivery_stats: Dict[str, float] # Symbol -> Delivery %

class MarketContextLoader:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.stocks_dir = data_dir / "stocks"
        self.derivs_dir = data_dir / "derivatives"

    def load_context(self, as_of: str) -> MarketContext:
        """
        Loads all available context for a specific date.
        
        Args:
            as_of: Date string in YYYY-MM-DD format
        """
        # Convert YYYY-MM-DD to DDMMYYYY for file searching if needed, 
        # but folders are usually YYYY-MM-DD.
        # Inside the folder, files often use DDMMYYYY.
        
        date_obj = pd.to_datetime(as_of)
        date_suffix = date_obj.strftime("%d%m%Y") # e.g. 16122025
        
        stocks_date_dir = self.stocks_dir / as_of
        derivs_date_dir = self.derivs_dir / as_of
        
        volatility = self._load_volatility(stocks_date_dir, date_suffix)
        participant_oi = self._load_participant_oi(derivs_date_dir, date_suffix)
        bulk_deals = self._load_bulk_deals(stocks_date_dir) # bulk.csv is usually just bulk.csv
        delivery_stats = self._load_delivery_stats(stocks_date_dir, date_suffix)

        return MarketContext(
            volatility=volatility,
            participant_oi=participant_oi,
            bulk_deals=bulk_deals,
            delivery_stats=delivery_stats
        )

    def _load_volatility(self, dir_path: Path, suffix: str) -> Dict[str, float]:
        """
        Loads CMVOLT_{suffix}.CSV
        Returns dict: Symbol -> Annualized Volatility (as float, e.g. 0.45 for 45%)
        """
        if not dir_path.exists():
            return {}
            
        # File name example: CMVOLT_16122025.CSV
        try:
            # Case insensitive search
            files = list(dir_path.glob(f"*VOLT*{suffix}*"))
            if not files:
                return {}
            
            f = files[0]
            df = pd.read_csv(f)
            
            # Columns usually: Date,Symbol,Underlying Close Price (A),... Underlying Annualized Volatility (F) ...
            # We need to map column names carefully. 
            # Real file header from previous step: 
            # Date,Symbol,...,Underlying Annualized Volatility (F) = E*Sqrt(365)
            
            # Normalize cols
            df.columns = [c.strip() for c in df.columns]
            
            # Find the volatility column (NSE uses 'Annualised')
            vol_col = next((c for c in df.columns if "Annualized Volatility" in c or "Annualised Volatility" in c), None)
            
            if not vol_col:
                return {}
            
            result = {}
            for _, row in df.iterrows():
                sym = str(row['Symbol']).strip().upper()
                try:
                    val = float(row[vol_col])
                    result[sym] = val
                except ValueError:
                    pass
            
            return result
        except Exception as e:
            logger.warning(f"Error loading volatility: {e}")
            return {}

    def _load_participant_oi(self, dir_path: Path, suffix: str) -> Dict[str, Dict[str, Any]]:
        """
        Loads fao_participant_oi_{suffix}.csv
        Returns dict: Client Type (FII/DII/Client/Pro) -> Stats
        """
        if not dir_path.exists():
            return {}
            
        try:
            files = list(dir_path.glob(f"fao_participant_oi*{suffix}*"))
            # Fallback to just fao_participant_oi.csv if suffixed one not found (sometimes they are renamed)
            if not files:
                 files = list(dir_path.glob(f"fao_participant_oi.csv"))
            
            if not files:
                return {}

            f = files[0]
            # This file often has specific structure.
            # Header line might be line 2 if line 1 is title.
            # From `head` output earlier: 
            # ""Participant wise Open Interest...""
            # Client Type,Future Index Long...
            
            # We'll try reading with header=1 (skipping line 0)
            df = pd.read_csv(f, header=1)
            
            # If that failed to get correct columns, try header=0
            if 'Client Type' not in df.columns:
                 df = pd.read_csv(f, header=0)

            result = {}
            if 'Client Type' in df.columns:
                for _, row in df.iterrows():
                    ctype = str(row['Client Type']).strip()
                    # Convert row to dict and strip keys
                    result[ctype] = {k.strip(): v for k, v in row.to_dict().items()}
            
            return result
        except Exception as e:
            logger.warning(f"Error loading participant OI: {e}")
            return {}

    def _load_bulk_deals(self, dir_path: Path) -> Dict[str, List[Dict[str, Any]]]:
        """
        Loads bulk.csv and block.csv
        Returns dict: Symbol -> List of deals
        """
        if not dir_path.exists():
            return {}
        
        deals = {}
        
        for fname in ["bulk.csv", "block.csv"]:
            f = dir_path / fname
            if not f.exists():
                continue
                
            try:
                # Columns: Date,Symbol,Security Name,Client Name,Buy/Sell,Quantity Traded,Trade Price...
                df = pd.read_csv(f)
                df.columns = [c.strip() for c in df.columns]
                
                for _, row in df.iterrows():
                    sym = str(row['Symbol']).strip().upper()
                    if sym not in deals:
                        deals[sym] = []
                    
                    deals[sym].append({
                        "client": row.get('Client Name'),
                        "type": row.get('Buy/Sell'),
                        "qty": row.get('Quantity Traded'),
                        "price": row.get('Trade Price / Wght. Avg. Price'),
                        "source": fname.replace(".csv", "")
                    })
            except Exception as e:
                 logger.warning(f"Error loading {fname}: {e}")
        
        return deals

    def _load_delivery_stats(self, dir_path: Path, suffix: str) -> Dict[str, float]:
        """
        Loads sec_bhavdata_full_{suffix}.csv
        Returns dict: Symbol -> Delivery Percentage (0-100)
        """
        if not dir_path.exists():
            return {}
            
        try:
             files = list(dir_path.glob(f"sec_bhavdata_full*{suffix}*"))
             if not files:
                 return {}
             
             f = files[0]
             df = pd.read_csv(f)
             df.columns = [c.strip() for c in df.columns]
             
             # Look for DELIV_PER or similar
             deliv_col = next((c for c in df.columns if "DELIV_PER" in c), None)
             sym_col = next((c for c in df.columns if "SYMBOL" in c), 'SYMBOL')
             
             if not deliv_col:
                 return {}
             
             result = {}
             for _, row in df.iterrows():
                 sym = str(row[sym_col]).strip().upper()
                 try:
                     val = float(row[deliv_col])
                     result[sym] = val
                 except ValueError:
                     pass
             
             return result

        except Exception as e:
            logger.warning(f"Error loading delivery stats: {e}")
            return {}
