import csv
import json
import sys
import statistics

signals_path = "/Users/vinodkeshav/myprojects/stockreco/data/models/2025-12-17/signals.csv"

def safe_float(x):
    try:
        return float(x)
    except:
        return 0.0

try:
    print(f"Reading {signals_path}...")
    with open(signals_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    print(f"Loaded signals.csv: {len(rows)} rows")
    
    if not rows:
        print("No rows found.")
        sys.exit(0)

    direction_scores = [safe_float(r.get('direction_score', 0)) for r in rows]
    ret_ocs = [safe_float(r.get('ret_oc', 0)) for r in rows]
    
    avg_dir = statistics.mean(direction_scores)
    avg_ret_oc = statistics.mean(ret_ocs)
    neg_ret_oc_count = sum(1 for x in ret_ocs if x < 0)
    neg_ret_oc_pct = (neg_ret_oc_count / len(rows)) * 100
    
    print(f"Average Direction Score: {avg_dir:.4f}")
    print(f"Average Return (Open-Close): {avg_ret_oc:.4%}")
    print(f"Percentage of Stocks with Negative Return: {neg_ret_oc_pct:.2f}%")
    
    # FII Sentiment
    fii = safe_float(rows[0].get('fii_sentiment', 0))
    print(f"FII Sentiment (from CSV): {fii:.4f}")
    
    # Sort and show top/bottom
    # We sort by direction_score
    rows.sort(key=lambda x: safe_float(x.get('direction_score', 0)))
    
    print("\nTop 5 Bearish (Lowest Direction Score):")
    for r in rows[:5]:
        print(f"  {r.get('ticker')}: Dir={r.get('direction_score')}, Ret={r.get('ret_oc')}, SellWin={r.get('sell_win')}")
        
    print("\nTop 5 Bullish (Highest Direction Score):")
    for r in rows[-5:]:
        print(f"  {r.get('ticker')}: Dir={r.get('direction_score')}, Ret={r.get('ret_oc')}, BuyWin={r.get('buy_win')}")

except Exception as e:
    print(f"Error reading signals: {e}")

# Check Participant OI
poi_path = "/Users/vinodkeshav/myprojects/stockreco/data/derivatives/2025-12-17/participant_oi.json"
try:
    with open(poi_path, 'r') as f:
        poi = json.load(f)
        sm = poi.get("smart_money_score")
        print(f"\nSmart Money Score (from JSON): {sm}")
        fii_stats = poi.get('participant_oi', {}).get('FII', {})
        print(f"FII Stats: {json.dumps(fii_stats, indent=2)}")
except Exception as e:
    print(f"\nError reading participant_oi: {e}")
