import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def check_marketdata_api():
    token = os.environ.get('TRADER_TOKEN')
    if not token:
        print("Error: TRADER_TOKEN environment variable not set.")
        return

    print(f"Using TRADER_TOKEN: {token[:4]}...{token[-4:] if len(token) > 8 else ''}")

    # Try fetching option chain for APOLLOHOSP and AAPL (as a control)
    symbols_to_try = ["AAPL", "APOLLOHOSP"]
    
    # Also, we can try to search for the symbol if there is a search endpoint, but let's stick to chain.
    # Documentation says: https://api.marketdata.app/v1/options/chain/{symbol}/
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    success = False
    
    for symbol in symbols_to_try:
        url = f"https://api.marketdata.app/v1/options/chain/{symbol}/"
        print(f"Testing URL: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print("Success! Data received.")
                # We want to find the specific contract: 30-DEC-2025 6900 PE
                # Start looking for expiry around 2025-12-30
                # The response structure usually has lists of strikes, expirations, etc.
                # Or it returns a list of contracts.
                # Let's verify the keys.
                print(f"Keys in response: {list(data.keys())}")
                
                # We'll save the response to a file for inspection
                with open(f"marketdata_response_{symbol}.json", "w") as f:
                    json.dump(data, f, indent=2)
                
                success = True
                break
            else:
                print(f"Response: {response.text[:200]}")
        except Exception as e:
            print(f"Exception: {e}")

    if not success:
        print("Failed to fetch data for APOLLOHOSP from marketdata.app")
    
if __name__ == "__main__":
    check_marketdata_api()
