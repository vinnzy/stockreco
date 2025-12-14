# src/stockreco/universe/nifty50.py
from __future__ import annotations

from typing import List

# Static NIFTY 50 list (NSE symbols) – update occasionally if needed.
# We keep NSE cash symbols; pipeline will use ".NS" for Yahoo where needed.
NIFTY50: List[str] = [
    "ADANIENT","ADANIPORTS","APOLLOHOSP","ASIANPAINT","AXISBANK","BAJAJ-AUTO","BAJFINANCE",
    "BAJAJFINSV","BPCL","BHARTIARTL","BRITANNIA","CIPLA","COALINDIA","DIVISLAB","DRREDDY",
    "EICHERMOT","GRASIM","HCLTECH","HDFCBANK","HDFCLIFE","HEROMOTOCO","HINDALCO","HINDUNILVR",
    "ICICIBANK","INDUSINDBK","INFY","ITC","JSWSTEEL","KOTAKBANK","LT","M&M","MARUTI","NESTLEIND",
    "NTPC","ONGC","POWERGRID","RELIANCE","SBILIFE","SBIN","SUNPHARMA","TATACONSUM","TATAMOTORS",
    "TATASTEEL","TECHM","TITAN","ULTRACEMCO","WIPRO"
]

def nifty50_ns() -> List[str]:
    """Return NIFTY50 tickers in Yahoo format ('.NS')."""
    return [f"{s}.NS" for s in NIFTY50]
