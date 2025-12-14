# stockreco report — target date 2025-12-15

- As-of EOD used: **2025-12-12**
- Final picks: **2**

## Notes
- EOD-based; take options only on intraday confirmation.
- STRICT NO-TRADE would have triggered; proceeding in AGGRESSIVE mode.
- Low conviction: mean p_up of top 3 is 0.50 (< 0.55).
- Low separation: p_up spread (P90-P10) is 0.02 (< 0.06).
- Low expansion: mean p_expand of top 3 is 0.28 (< 0.55).
- NO-TRADE for options recommended (edge too small / too clustered).

## Final bullish momentum list (next day)
### 1) SHRIRAMFIN.NS
- Calibrated P(up tomorrow): **0.51** (Low)
- Model-B P(expand ≥ thr): **0.36**
- Rationale: Ranked for options suitability (ATR/ADX/RSI impulse + Model-B p_expand) plus calibrated p_up; confirm intraday price action before entry.
- Options playbook:
  - Prefer liquid weekly expiry; choose ~0.35–0.50 delta call (or slightly ITM).
  - Entry only on confirmation: (a) gap-up holds above VWAP for 10–15m, OR (b) breakout above first 30m high with volume.
  - Stop: premium -15% (moderate) OR underlying breaks VWAP/structure; also use time-stop (exit by 2:30pm if no move).
  - Targets: scale out +20–30%, trail remainder for +40–50% when momentum continues.
  - Avoid entries if bid-ask spreads are wide or IV is extremely elevated vs recent days.

### 2) ADANIENT.NS
- Calibrated P(up tomorrow): **0.49** (Low)
- Model-B P(expand ≥ thr): **0.33**
- Rationale: Ranked for options suitability (ATR/ADX/RSI impulse + Model-B p_expand) plus calibrated p_up; confirm intraday price action before entry.
- Options playbook:
  - Prefer liquid weekly expiry; choose ~0.35–0.50 delta call (or slightly ITM).
  - Entry only on confirmation: (a) gap-up holds above VWAP for 10–15m, OR (b) breakout above first 30m high with volume.
  - Stop: premium -15% (moderate) OR underlying breaks VWAP/structure; also use time-stop (exit by 2:30pm if no move).
  - Targets: scale out +20–30%, trail remainder for +40–50% when momentum continues.
  - Avoid entries if bid-ask spreads are wide or IV is extremely elevated vs recent days.

## Top 15 by options suitability (for reference)

| ticker        |     p_up |   p_expand |    score |   options_score |   rel_strength_5d |   rsi_14 |   adx_14 |   atr_pct |
|:--------------|---------:|-----------:|---------:|----------------:|------------------:|---------:|---------:|----------:|
| TATAMOTORS.NS | 0.511327 |   0.157352 | 0.508295 |        0.697039 |       -0.0120653  |  25.4486 |  60.6891 | 0.024432  |
| SHRIRAMFIN.NS | 0.505959 |   0.358425 | 0.504383 |        0.654778 |       -0.00274397 |  60.8296 |  31.7898 | 0.0232882 |
| ADANIENT.NS   | 0.48614  |   0.331767 | 0.486714 |        0.629648 |        0.0128314  |  45.7855 |  25.5592 | 0.0270119 |
| HINDALCO.NS   | 0.502153 |   0.353464 | 0.507204 |        0.554827 |        0.0403712  |  67.6605 |  17.6148 | 0.0200882 |
| INDUSINDBK.NS | 0.505959 |   0.36974  | 0.501437 |        0.538742 |       -0.0221983  |  54.6128 |  23.4681 | 0.0238432 |
| HINDUNILVR.NS | 0.502153 |   0.336121 | 0.496979 |        0.517341 |       -0.0280261  |  24.8572 |  28.485  | 0.0194036 |
| BPCL.NS       | 0.5      |   0.335829 | 0.501652 |        0.497787 |        0.0185106  |  55.9002 |  17.0549 | 0.0224846 |
| JSWSTEEL.NS   | 0.505959 |   0.316242 | 0.500841 |        0.493697 |       -0.0262508  |  44.9935 |  22.3783 | 0.0236036 |
| APOLLOHOSP.NS | 0.382353 |   0.200572 | 0.380578 |        0.480166 |       -0.00698244 |  33.0748 |  54.0031 | 0.0145583 |
| TECHM.NS      | 0.502153 |   0.252603 | 0.502839 |        0.470423 |        0.0101655  |  67.0065 |  32.7569 | 0.0167755 |
| SBILIFE.NS    | 0.5      |   0.243546 | 0.500107 |        0.466012 |        0.00641434 |  60.8245 |  32.2133 | 0.0171013 |
| AXISBANK.NS   | 0.505959 |   0.217308 | 0.506459 |        0.449985 |        0.00813418 |  61.214  |  43.6219 | 0.0143969 |
| TATASTEEL.NS  | 0.5      |   0.211293 | 0.504071 |        0.448354 |        0.0339311  |  54.7305 |  27.7638 | 0.0203829 |
| INFY.NS       | 0.48614  |   0.268427 | 0.484421 |        0.439606 |       -0.00581005 |  61.707  |  27.029  | 0.0169415 |
| LT.NS         | 0.48614  |   0.223478 | 0.487504 |        0.426889 |        0.0142173  |  61.4961 |  32.6974 | 0.0153674 |
