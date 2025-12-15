from pathlib import Path
import csv
from datetime import datetime

def parse_mcx_bhavcopy(path: Path):
    """
    Returns:
      dict[key] -> quote
      key = MCXFUT:GOLD:05FEB26
    """
    quotes = {}

    with path.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("INSTRUMENT") != "FUTCOM":
                continue

            symbol = r["SYMBOL"].strip().upper()
            expiry = datetime.strptime(r["EXPIRY_DT"], "%d-%b-%Y")
            exp = expiry.strftime("%d%b%y").upper()

            key = f"MCXFUT:{symbol}:{exp}"

            ltp = float(r["SETTLE_PR"]) if r["SETTLE_PR"] else None

            quotes[key] = {
                "ok": True,
                "ltp": ltp,
                "open": float(r["OPEN"]) if r["OPEN"] else None,
                "high": float(r["HIGH"]) if r["HIGH"] else None,
                "low": float(r["LOW"]) if r["LOW"] else None,
                "close": float(r["CLOSE"]) if r["CLOSE"] else None,
                "oi": float(r["OPEN_INT"]) if r["OPEN_INT"] else None,
                "volume": float(r["TOT_TRADED_QTY"]) if r["TOT_TRADED_QTY"] else None,
                "exchange": "MCX",
                "instrument": "FUT",
            }

    return quotes
