from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Literal, Protocol

OptionType = Literal["CE", "PE"]

@dataclass
class OptionChainRow:
    strike: float
    expiry: str
    option_type: OptionType
    ltp: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    oi: Optional[float] = None
    oi_change: Optional[float] = None
    iv: Optional[float] = None  # decimal (0.15 = 15%)
    high: Optional[float] = None
    low: Optional[float] = None

@dataclass
class UnderlyingSnapshot:
    symbol: str
    spot: float
    as_of_iso: str

class DerivativesProvider(Protocol):
    name: str
    def get_underlying(self, symbol: str) -> UnderlyingSnapshot: ...
    def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> List[OptionChainRow]: ...

def normalize_symbol(sym: str) -> str:
    return sym.strip().upper()

def normalize_to_nse_symbol(sym: str) -> str:
    s = normalize_symbol(sym)
    for suf in (".NS", ".BO"):
        if s.endswith(suf):
            s = s[:-len(suf)]
    return s

def guess_index_vs_equity(sym: str) -> str:
    s = normalize_to_nse_symbol(sym)
    if s in {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"}:
        return "index"
    return "equity"
