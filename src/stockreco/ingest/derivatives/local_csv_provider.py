from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import re
import pandas as pd
import yfinance as yf

from .provider_base import OptionChainRow, UnderlyingSnapshot, normalize_symbol, normalize_to_nse_symbol

# CONTRACT_D examples:
#   OPTIDXNIFTY16-DEC-2025CE24100
#   OPTIDXBANKNIFTY30-DEC-2025PE54100
#   OPTSTKBHEL30-DEC-2025PE272.5

_CONTRACT_RE = re.compile(
    r"^(?P<inst>OPTIDX|OPTSTK)"
    r"(?P<und>[A-Z0-9&_-]+?)"
    r"(?P<exp>\d{1,2}-[A-Z]{3}-\d{4})"
    r"(?P<cp>CE|PE)"
    r"(?P<strike>\d+(?:\.\d+)?)$"
)

def _scalar(x) -> float:
    try:
        return float(x.item())
    except Exception:
        try:
            return float(x.iloc[0])
        except Exception:
            return float(x)

def _yf_spot(symbol: str) -> float:
    s = normalize_to_nse_symbol(symbol)
    if s == "NIFTY":
        ysym = "^NSEI"
    elif s == "BANKNIFTY":
        ysym = "^NSEBANK"
    else:
        ysym = f"{s}.NS"
    df = yf.download(ysym, period="5d", interval="1d", progress=False, auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError(f"Yahoo spot fallback empty for {symbol} ({ysym})")
    return _scalar(df.iloc[-1]["Close"])

def _read_csv_any(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df

def _find_best_bulk_file(folder: Path, prefixes: Tuple[str, ...]) -> Optional[Path]:
    cands = []
    for p in folder.glob("*.csv"):
        name = p.name.lower()
        if any(name.startswith(px) for px in prefixes):
            cands.append(p)
    if not cands:
        return None
    return sorted(cands, key=lambda x: x.stat().st_size, reverse=True)[0]

def _pick_cols(df: pd.DataFrame) -> Dict[str, str]:
    cols = {c: c for c in df.columns}
    def has(*names):
        for n in names:
            if n in cols:
                return n
        return ""
    return {
        "contract": has("CONTRACT_D"),
        "spot": has("UNDRLNG_ST"),
        "close": has("CLOSE_PRIC", "CLOSE_PRICE", "CLOSE"),
        "settle": has("SETTLEMENT", "SETTLE_PR", "SETTLEPRICE"),
        "open": has("OPEN_PRICE", "OPEN"),
        "high": has("HIGH_PRICE", "HI_PRICE", "HIGH"),
        "low": has("LOW_PRICE", "LO_PRICE", "LOW"),
        "oi": has("OI_NO_CON", "OPEN_INT", "OPENINTEREST", "OI", "OI_LAKHS", "OPEN_INT*"),
        "vol": has("TRADED_QUA", "TOTTRDQTY", "VOLUME", "CONTRACTS"),
        "oi_ch": has("CHG_IN_OI", "CHANGE_IN_OI"),
    }

def _parse_contract(desc: str) -> Optional[Dict[str, str]]:
    if desc is None:
        return None
    s = str(desc).strip().upper()
    m = _CONTRACT_RE.match(s)
    if not m:
        return None
    return {
        "inst": m.group("inst"),
        "underlying": m.group("und"),
        "expiry": m.group("exp"),
        "cp": m.group("cp"),
        "strike": m.group("strike"),
    }

def _aliases(nse_sym: str) -> List[str]:
    if nse_sym == "NIFTY":
        return ["NIFTY", "NIFTY 50", "NIFTY50"]
    if nse_sym == "BANKNIFTY":
        return ["BANKNIFTY", "NIFTY BANK", "BANK NIFTY"]
    return [nse_sym]

def _fnum(v) -> Optional[float]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return None

def _build_chain(df: pd.DataFrame, nse_sym: str) -> List[OptionChainRow]:
    m = _pick_cols(df)
    
    # Format 1: CONTRACT_D
    if m["contract"]:
        aliases = set([a.upper() for a in _aliases(nse_sym)])
        out: List[OptionChainRow] = []
        
        # Optimization: Pre-filter dataframe using vectorized string match
        # Construct regex for aliases: OPTIDXNIFTY... or OPTSTKBHEL...
        # Anchored to start to avoid false positives
        # Pattern: ^(OPTIDX|OPTSTK)(ALIAS)(\d|-)
        # Actually simpler: just contains ONE of the aliases in the right place?
        # Let's rely on basic string containment first, then parse.
        # But rigorous way:
        pat = "|".join([re.escape(a) for a in aliases])
        # We need to match underlying. 
        # CONTRACT_D usually: OPTIDX(UND)DD-MMM...
        # So check if UND is in aliases.
        
        # Vectorized filter (much faster than iterating 100k rows)
        # We look for the underlying inside the string. 
        # To be safe, specific regex search on the series:
        # This might still be slow if regex is complex, but faster than python loop.
        
        # Fast path: str.contains with regex
        mask = df[m["contract"]].astype(str).str.contains(pat, regex=True)
        subset = df[mask]

        contract_col = m["contract"]
        close_col = m["close"]
        settle_col = m["settle"]
        vol_col = m["vol"]
        oi_col = m["oi"]
        oi_ch_col = m["oi_ch"]
        high_col = m["high"]
        low_col = m["low"]
        
        for _, r in subset.iterrows():
            info = _parse_contract(r.get(contract_col))
            if not info:
                continue
            if info["underlying"].upper() not in aliases:
                continue
            cp = info["cp"]
            try:
                strike = float(info["strike"])
            except Exception:
                continue

            ltp = _fnum(r.get(close_col))
            if (ltp is None or ltp <= 0) and settle_col:
                ltp = _fnum(r.get(settle_col))
            if ltp is None or ltp <= 0:
                continue

            out.append(OptionChainRow(
                strike=strike,
                expiry=str(info["expiry"]),
                option_type=cp,
                ltp=float(ltp),
                volume=_fnum(r.get(vol_col)),
                oi=_fnum(r.get(oi_col)),
                oi_change=_fnum(r.get(oi_ch_col)) if oi_ch_col else None,
                iv=None,
                bid=None,
                ask=None,
                high=_fnum(r.get(high_col)) if high_col else None,
                low=_fnum(r.get(low_col)) if low_col else None,
            ))
        return out

    # Format 2: SPlit Columns (INSTRUMENT, SYMBOL, EXP_DATE, STR_PRICE, OPT_TYPE)
    # Check required columns
    req = ["SYMBOL", "EXP_DATE", "STR_PRICE", "OPT_TYPE"]
    if all(c in df.columns for c in req):
         aliases = set([a.upper() for a in _aliases(nse_sym)])
         out: List[OptionChainRow] = []
         
         # Optimization: Pre-filter by symbol
         # Vectorized filter much faster than row-by-row
         mask = df["SYMBOL"].astype(str).str.strip().str.upper().isin(aliases)
         subset = df[mask]
         
         for _, r in subset.iterrows():
             # Symbol check already done by mask

             
             try:
                 strike = float(r["STR_PRICE"])
             except:
                 continue
                 
             cp = str(r["OPT_TYPE"]).strip().upper() # CE/PE
             expiry = str(r["EXP_DATE"]).strip() # usually DD/MM/YYYY or DD-MMM-YYYY
             
             ltp_val = r.get(m["close"])
             if (ltp_val is None or _fnum(ltp_val) is None) and m["settle"]:
                  ltp_val = r.get(m["settle"])
             ltp = _fnum(ltp_val)
             
             if ltp is None or ltp <= 0:
                 continue
                 
             out.append(OptionChainRow(
                strike=strike,
                expiry=expiry,
                option_type=cp,
                ltp=float(ltp),
                volume=_fnum(r.get(m["vol"])),
                oi=_fnum(r.get(m["oi"])),
                oi_change=_fnum(r.get(m["oi_ch"])) if m["oi_ch"] else None,
                iv=None,
                bid=None,
                ask=None,
                high=_fnum(r.get(m["high"])) if m["high"] else None,
                low=_fnum(r.get(m["low"])) if m["low"] else None,
            ))
         return out

    # If neither format matches
    raise RuntimeError(f"Unsupported op/fo format: missing CONTRACT_D or split cols. Have: {list(df.columns)[:25]}")

def _spot_from_df(df: pd.DataFrame) -> Optional[float]:
    m = _pick_cols(df)
    if not m["spot"]:
        return None
    s = pd.to_numeric(df[m["spot"]], errors="coerce").dropna()
    if s.empty:
        return None
    return float(s.median())

class LocalCsvProvider:
    name = "LOCAL_CSV"

    def __init__(self, repo_root: Path, as_of: str, derivatives_subdir: str = "data/derivatives"):
        self.repo_root = Path(repo_root)
        self.as_of = str(as_of)
        self.folder = self.repo_root / derivatives_subdir / self.as_of
        if not self.folder.exists():
            raise RuntimeError(f"Local derivatives folder not found: {self.folder}")

        self.op_file = _find_best_bulk_file(self.folder, ("op",))
        self.fo_file = _find_best_bulk_file(self.folder, ("fo",))
        if not self.op_file and not self.fo_file:
            raise RuntimeError(f"No bulk derivatives CSV found in {self.folder} (expected op*.csv or fo*.csv)")

        self._op_df: Optional[pd.DataFrame] = None
        self._fo_df: Optional[pd.DataFrame] = None

    def _load_op_df(self) -> Optional[pd.DataFrame]:
        if self.op_file is None:
            return None
        if self._op_df is None:
            self._op_df = _read_csv_any(self.op_file)
        return self._op_df

    def _load_fo_df(self) -> Optional[pd.DataFrame]:
        if self.fo_file is None:
            return None
        if self._fo_df is None:
            self._fo_df = _read_csv_any(self.fo_file)
        return self._fo_df

    def get_underlying(self, symbol: str) -> UnderlyingSnapshot:
        sym = normalize_symbol(symbol)
        nse_sym = normalize_to_nse_symbol(sym)
        spot = None

        # quick filter prefix without capturing groups
        # quick filter prefix without capturing groups
        def _filter(df: pd.DataFrame) -> pd.DataFrame:
            al = _aliases(nse_sym)
            if "CONTRACT_D" in df.columns:
                pat = "|".join([re.escape(f"OPTIDX{a}") + "|" + re.escape(f"OPTSTK{a}") for a in al])
                return df[df["CONTRACT_D"].astype(str).str.contains(pat, regex=True, na=False)]
            elif "SYMBOL" in df.columns:
                 # Exact match on symbol
                 return df[df["SYMBOL"].str.strip().str.upper().isin([a.upper() for a in al])]
            return pd.DataFrame() # Should not happen if _build_chain checked cols

        op_df = self._load_op_df()
        if op_df is not None:
            f = _filter(op_df)
            spot = _spot_from_df(f) if not f.empty else None

        if spot is None:
            fo_df = self._load_fo_df()
            if fo_df is not None:
                f = _filter(fo_df)
                spot = _spot_from_df(f) if not f.empty else None

        # Fallback: Equity Bhavcopy in data/stocks/{as_of}/sec_bhavdata_full*.csv
        if spot is None or spot <= 0:
            try:
                stock_dir = self.repo_root / "data" / "stocks" / self.as_of
                if stock_dir.exists():
                    bhav_files = list(stock_dir.glob("sec_bhavdata_full*.csv"))
                    if bhav_files:
                        # Load only necessary columns
                        # file: SYMBOL, SERIES, ... CLOSE_PRICE ...
                        # normalize cols
                        df_eq = pd.read_csv(bhav_files[0])
                        df_eq.columns = [c.strip().upper() for c in df_eq.columns]
                        
                        # Find symbol row
                        # NSE symbol might be "RELIANCE", provided "RELIANCE.NS" or "RELIANCE"
                        # Normalize to pure symbol name
                        target = nse_sym.replace(".NS", "").upper()
                        
                        row = df_eq[df_eq["SYMBOL"].str.strip().str.upper() == target]
                        if not row.empty:
                            # Prefer "EQ" series if multiple? Usually one row per symbol in full bhav
                            val = row.iloc[0].get("CLOSE_PRICE")
                            if val is not None:
                                spot = float(val)
            except Exception as e:
                print(f"[WARN] Failed to load spot from equity bhavcopy: {e}")
                pass

        if spot is None or spot <= 0:
            spot = _yf_spot(sym)

        return UnderlyingSnapshot(symbol=sym, spot=float(spot), as_of_iso=datetime.utcnow().isoformat())

    def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> List[OptionChainRow]:
        sym = normalize_symbol(symbol)
        nse_sym = normalize_to_nse_symbol(sym)

        chain: List[OptionChainRow] = []
        op_df = self._load_op_df()
        if op_df is not None:
            chain = _build_chain(op_df, nse_sym)

        if not chain:
            fo_df = self._load_fo_df()
            if fo_df is not None:
                chain = _build_chain(fo_df, nse_sym)

        if not chain:
            msg = f"No option rows found in local derivatives for {symbol} (using files {self.op_file}, {self.fo_file})."
            if self._op_df is not None:
                msg += f" OP_DF size: {len(self._op_df)}."
            if self._fo_df is not None:
                msg += f" FO_DF size: {len(self._fo_df)}."
            # Don't crash, just log and return empty to allow graceful degradation/other providers? 
            # Actually, per contract, we raise. But let's raise a clearer error.
            raise RuntimeError(msg)

        if expiry:
            chain = [r for r in chain if str(r.expiry).upper() == str(expiry).upper()]
            if not chain:
                raise RuntimeError(f"No rows for expiry={expiry} for {symbol} in local derivatives")

        return chain
