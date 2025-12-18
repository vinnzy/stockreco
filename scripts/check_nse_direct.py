import requests
import json
import time
from datetime import datetime

class NseDirectChecker:
    def __init__(self):
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
        print("Bootstrapping session...")
        try:
            # Visit homepage
            self._session.get("https://www.nseindia.com", headers=self._headers, timeout=10)
            # Visit option chain page
            self._session.get("https://www.nseindia.com/option-chain", headers=self._headers, timeout=10)
            time.sleep(1)
        except Exception as e:
            print(f"Bootstrap failed: {e}")

    def fetch_data(self, symbol="APOLLOHOSP"):
        self._bootstrap()
        clean_symbol = symbol.replace(".NS", "").replace("NSE:", "")
        
        if symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
             path = f"/api/option-chain-indices?symbol={clean_symbol}"
        else:
             path = f"/api/option-chain-equities?symbol={clean_symbol}"
        url = f"{self._base}{path}"
        
        print(f"Fetching data from: {url}")
        
        try:
            resp = self._session.get(url, headers=self._headers, timeout=10)
            print(f"Status Code: {resp.status_code}")
            
            try:
                data = resp.json()
                print(f"Response Keys: {list(data.keys())}")
                if "records" in data:
                    print(f"Records Keys: {list(data['records'].keys())}")
            except Exception as e:
                print(f"FAILED TO PARSE JSON: {e}")
                print(f"First 500 chars: {resp.text[:500]}")
                return
            
            # Check for underlying value
            records = data.get("records", {})
            underlying_val = records.get("underlyingValue")
            print(f"Underlying Spot Price (APOLLOHOSP): {underlying_val}")
            
            timestamp = records.get("timestamp")
            print(f"Data Timestamp: {timestamp}")

            expiry_dates = records.get("expiryDates", [])
            print(f"Available Expiries: {expiry_dates}")
            
            # We are looking for 2025-12-30, note NSE format is usually like 26-Dec-2024
            # 30-DEC-2025 from the JSON report might map to 24-Dec-2024 or similar if it's a monthly.
            # Wait, the JSON report said 30-DEC-2025? Let's check the date format.
            # Report said: "expiry": "30-DEC-2025"
            # It's possible this is a far month expiry.
            
            target_expiry = "30-Dec-2025" 
            # Note: The JSON report used uppercase MON, NSE uses Title case Mon usually (e.g. 26-Dec-2024)
            # Let's try to match case insensitive
            
            found_expiry = None
            for exp in expiry_dates:
                if exp.upper() == target_expiry.upper():
                    found_expiry = exp
                    break
            
            if not found_expiry:
                print(f"Target expiry {target_expiry} not found in list.")
                # Maybe closest expiry?
                # current date is Dec 2025 (Wait, metadata said 2025-12-18).
                # So the recommendation expiry 30-Dec-2025 is the end of this month.
                # Let's just list all expirations for Dec 2025.
                dec_expiries = [e for e in expiry_dates if "Dec-2025" in e]
                print(f"Dec 2025 Expiries: {dec_expiries}")
                if dec_expiries:
                    found_expiry = dec_expiries[-1] # Usually monthly is the last one
            
            if found_expiry:
                print(f"Checking Data for Expiry: {found_expiry}")
                
                target_strike = 6900
                found_option = None
                
                for item in data.get("records", {}).get("data", []):
                    if item.get("expiryDate") == found_expiry and item.get("strikePrice") == target_strike:
                        found_option = item.get("PE") # We want PE
                        break
                
                if found_option:
                    print("-" * 30)
                    print(f"Option: {clean_symbol} {found_expiry} {target_strike} PE")
                    print(f"LTP: {found_option.get('lastPrice')}")
                    print(f"Change: {found_option.get('change')}")
                    print(f"Bid: {found_option.get('bidprice')} (Qty: {found_option.get('bidQty')})")
                    print(f"Ask: {found_option.get('askPrice')} (Qty: {found_option.get('askQty')})")
                    print(f"IV: {found_option.get('impliedVolatility')}")
                    print(f"OI: {found_option.get('openInterest')}")
                    print("-" * 30)
                    
                    # original recommendation details
                    # "entry_price": 69.06 (LTP)
                    current_ltp = found_option.get('lastPrice')
                    if current_ltp:
                         print(f"Rec Entry: 69.06 vs Current LTP: {current_ltp}")
                else:
                    print(f"Option contract {target_strike} PE not found for expiry {found_expiry}")

        except Exception as e:
            print(f"Fetch failed: {e}")

if __name__ == "__main__":
    checker = NseDirectChecker()
    print("\n--- Testing NIFTY ---")
    checker.fetch_data(symbol="NIFTY")
    
    print("\n--- Testing APOLLOHOSP ---")
    checker.fetch_data(symbol="APOLLOHOSP")
