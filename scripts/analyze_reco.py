import json
import sys

filepath = "/Users/vinodkeshav/myprojects/stockreco/reports/options/option_reco_2025-12-17.json"

try:
    with open(filepath, 'r') as f:
        data = json.load(f)
        
    recos = data.get("recommender", [])
    
    # Sort by confidence descending
    recos.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    
    print(f"Total Recommendations: {len(recos)}")
    print(f"Top 20 Recommendations:")
    for i, r in enumerate(recos[:20]):
        print(f"{i+1}. {r['symbol']} - {r['side']} - Conf: {r['confidence']} - Bias: {r['bias']}")

    pe_count = sum(1 for r in recos if r['side'] == 'PE')
    ce_count = sum(1 for r in recos if r['side'] == 'CE')
    print(f"\nOverall Counts: PE={pe_count}, CE={ce_count}")
    
    top_20_pe = sum(1 for r in recos[:20] if r['side'] == 'PE')
    print(f"Top 20 PE Count: {top_20_pe}")

except Exception as e:
    print(f"Error: {e}")
