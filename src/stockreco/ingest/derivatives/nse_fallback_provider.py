from __future__ import annotations
import json
import time
from datetime import datetime
from typing import List, Optional
import requests
import yfinance as yf

from .provider_base import DerivativesProvider, OptionChainRow, UnderlyingSnapshot, normalize_symbol, guess_index_vs_equity

class NseFallbackProvider:
    """Dev-only fallback provider for NSE option chain.

    NOTE:
      Exchange sites often employ anti-bot measures and may disallow automated extraction.
      Use licensed broker/vendor APIs (Zerodha/Upstox/etc.) for production.

    This provider tries a minimal cookie bootstrap approach and then hits the JSON endpoint.
    """

    name = "NSE_FALLBACK"

    def __init__(self, timeout: int = 20, throttle_s: float = 0.4):
        self.timeout = timeout
        self.throttle_s = throttle_s
        self._session = requests.Session()
        self._base = "https://www.nseindia.com"
        self._headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "accept": "application/json,text/plain,*/*",
            "accept-language": "en-US,en;q=0.9",
            "referer": "https://www.nseindia.com/option-chain",
            "connection": "keep-alive",
        }

    def _bootstrap(self):
        # bootstrap cookies
        self._session.get(self._base, headers=self._headers, timeout=self.timeout)
        time.sleep(self.throttle_s)

    def _get_json(self, path: str):
        self._bootstrap()
        url = f"{self._base}{path}"
        resp = self._session.get(url, headers=self._headers, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"NSE fetch failed {resp.status_code}: {resp.text[:200]}")
        time.sleep(self.throttle_s)
        return resp.json()

    def get_underlying(self, symbol: str) -> UnderlyingSnapshot:
        sym = normalize_symbol(symbol)
        kind = guess_index_vs_equity(sym)
        path = "/api/option-chain-indices" if kind == "index" else "/api/option-chain-equities"
        js = self._get_json(f"{path}?symbol={sym}")

        if kind != "index":
            raise NotImplementedError("NSE_FALLBACK currently supports indices. Use a broker provider for equities.")

        kind = guess_index_vs_equity(sym)
        path = "/api/option-chain-indices" if kind == "index" else "/api/option-chain-equities"
        js = self._get_json(f"{path}?symbol={sym}")

        spot = self._parse_spot(js)

        if spot is None or spot <= 0:
            # fallback to yfinance (so pipeline still works)
            spot = self._yf_spot(sym)

        return UnderlyingSnapshot(symbol=sym, spot=float(spot), as_of_iso=datetime.utcnow().isoformat())


    def _yf_spot(self, symbol: str) -> float:
        # Yahoo mapping
        s = symbol.strip().upper()
        ysym = "^NSEI" if s == "NIFTY" else "^NSEBANK" if s == "BANKNIFTY" else None
        if not ysym:
            raise RuntimeError(f"Yahoo fallback not supported for {symbol}")
        df = yf.download(ysym, period="5d", interval="1d", progress=False)
        if df is None or df.empty:
            raise RuntimeError(f"Yahoo fallback empty for {symbol}")
        last = df.iloc[-1]
        # scalar-safe
        try:
            return float(last["Close"].item())
        except Exception:
            return float(last["Close"].iloc[0])

    def _parse_spot(self, js: dict) -> Optional[float]:
        try:
            v = js.get("records", {}).get("underlyingValue", None)
            if v is None:
                # sometimes present under filtered/other keys
                v = js.get("filtered", {}).get("underlyingValue", None)
            return float(v) if v is not None else None
        except Exception:
            return None

    def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> List[OptionChainRow]:
        sym = normalize_symbol(symbol)
        kind = guess_index_vs_equity(sym)
        if kind != "index":
            raise NotImplementedError("NSE_FALLBACK currently supports indices. Use a broker provider for equities.")
        js = self._get_json(f"/api/option-chain-indices?symbol={sym}")
        if not isinstance(js, dict) or "records" not in js:
            raise RuntimeError("NSE response is not valid JSON option chain (blocked or rate-limited). Try --provider zerodha/upstox for production.")

        records = js.get("records", {})
        exp = expiry or (records.get("expiryDates") or [None])[0]
        if not exp:
            return []

        if not records.get("data"):
            raise RuntimeError("NSE option chain has no records.data (blocked/empty).")

        out: List[OptionChainRow] = []
        for row in records.get("data") or []:
            if row.get("expiryDate") != exp:
                continue
            strike = float(row.get("strikePrice"))

            ce = row.get("CE")
            if ce:
                out.append(OptionChainRow(
                    strike=strike,
                    expiry=exp,
                    option_type="CE",
                    ltp=float(ce.get("lastPrice") or 0.0),
                    bid=float(ce.get("bidprice") or ce.get("bidPrice") or 0.0) if (ce.get("bidprice") or ce.get("bidPrice")) else None,
                    ask=float(ce.get("askPrice") or 0.0) if ce.get("askPrice") is not None else None,
                    volume=float(ce.get("totalTradedVolume") or 0.0) if ce.get("totalTradedVolume") is not None else None,
                    oi=float(ce.get("openInterest") or 0.0) if ce.get("openInterest") is not None else None,
                    oi_change=float(ce.get("changeinOpenInterest") or 0.0) if ce.get("changeinOpenInterest") is not None else None,
                    iv=(float(ce.get("impliedVolatility"))/100.0) if ce.get("impliedVolatility") is not None else None,
                ))

            pe = row.get("PE")
            if pe:
                out.append(OptionChainRow(
                    strike=strike,
                    expiry=exp,
                    option_type="PE",
                    ltp=float(pe.get("lastPrice") or 0.0),
                    bid=float(pe.get("bidprice") or pe.get("bidPrice") or 0.0) if (pe.get("bidprice") or pe.get("bidPrice")) else None,
                    ask=float(pe.get("askPrice") or 0.0) if pe.get("askPrice") is not None else None,
                    volume=float(pe.get("totalTradedVolume") or 0.0) if pe.get("totalTradedVolume") is not None else None,
                    oi=float(pe.get("openInterest") or 0.0) if pe.get("openInterest") is not None else None,
                    oi_change=float(pe.get("changeinOpenInterest") or 0.0) if pe.get("changeinOpenInterest") is not None else None,
                    iv=(float(pe.get("impliedVolatility"))/100.0) if pe.get("impliedVolatility") is not None else None,
                ))

        return out
