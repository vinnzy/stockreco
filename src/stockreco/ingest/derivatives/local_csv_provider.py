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
        "oi": has("OI_NO_CON", "OPEN_INT", "OPENINTEREST", "OI"),
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
        return ["NIFTY"]
    if nse_sym == "BANKNIFTY":
        return ["BANKNIFTY"]
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
    if not m["contract"]:
        raise RuntimeError(f"Unsupported op/fo format: missing CONTRACT_D. Have: {list(df.columns)[:25]}")

    aliases = set([a.upper() for a in _aliases(nse_sym)])
    out: List[OptionChainRow] = []
    for _, r in df.iterrows():
        info = _parse_contract(r.get(m["contract"]))
        if not info:
            continue
        if info["underlying"].upper() not in aliases:
            continue
        cp = info["cp"]
        try:
            strike = float(info["strike"])
        except Exception:
            continue

        ltp = _fnum(r.get(m["close"]))
        if (ltp is None or ltp <= 0) and m["settle"]:
            ltp = _fnum(r.get(m["settle"]))
        if ltp is None or ltp <= 0:
            continue

        out.append(OptionChainRow(
            strike=strike,
            expiry=str(info["expiry"]),
            option_type=cp,
            ltp=float(ltp),
            volume=_fnum(r.get(m["vol"])),
            oi=_fnum(r.get(m["oi"])),
            oi_change=_fnum(r.get(m["oi_ch"])) if m["oi_ch"] else None,
            iv=None,
            bid=None,
            ask=None,
        ))
    return out

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
        def _filter(df: pd.DataFrame) -> pd.DataFrame:
            al = _aliases(nse_sym)
            pat = "|".join([re.escape(f"OPTIDX{a}") + "|" + re.escape(f"OPTSTK{a}") for a in al])
            return df[df["CONTRACT_D"].astype(str).str.contains(pat, regex=True, na=False)]

        op_df = self._load_op_df()
        if op_df is not None:
            f = _filter(op_df)
            spot = _spot_from_df(f) if not f.empty else None

        if spot is None:
            fo_df = self._load_fo_df()
            if fo_df is not None:
                f = _filter(fo_df)
                spot = _spot_from_df(f) if not f.empty else None

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
            raise RuntimeError(f"No option rows found in local derivatives for {symbol} (op/fo parsed 0 rows)")

        if expiry:
            chain = [r for r in chain if str(r.expiry).upper() == str(expiry).upper()]
            if not chain:
                raise RuntimeError(f"No rows for expiry={expiry} for {symbol} in local derivatives")

        return chain
