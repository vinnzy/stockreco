# stockreco report — target date 2025-12-15

- As-of EOD used: **2025-12-12**
- Final picks: **2**

## Notes
- EOD-based; take options only on intraday confirmation.
- Low conviction: mean p_up of top 3 is 0.50 (< 0.55).
- Low separation: p_up spread (P90-P10) is 0.02 (< 0.06).
- NO-TRADE for options recommended (edge too small / too clustered).
- Aggressive override: strict NO-TRADE triggered, but emitting up to 2 tactical candidates.

## Final bullish momentum list (next day)
### 1) TATAMOTORS.NS
- Calibrated P(up tomorrow): **0.51** (Low)
- Rationale: Aggressive mode: strict NO-TRADE gate may be active; this is a tactical candidate ranked by options suitability (ATR/ADX/RSI impulse) plus calibrated score. Take only on intraday confirmation.
- Options playbook:
  - Prefer liquid weekly expiry; choose ~0.35–0.50 delta call (or slightly ITM).
  - Entry only on confirmation: (a) gap-up holds above VWAP for 10–15m, OR (b) breakout above first 30m high with volume.
  - Stop: premium -15% (moderate) OR underlying breaks VWAP/structure; also use time-stop (exit by 2:30pm if no move).
  - Targets: scale out +20–30%, trail remainder for +40–50% when momentum continues.
  - Avoid entries if bid-ask spreads are wide or IV is extremely elevated vs recent days.

### 2) SHRIRAMFIN.NS
- Calibrated P(up tomorrow): **0.51** (Low)
- Rationale: Aggressive mode: strict NO-TRADE gate may be active; this is a tactical candidate ranked by options suitability (ATR/ADX/RSI impulse) plus calibrated score. Take only on intraday confirmation.
- Options playbook:
  - Prefer liquid weekly expiry; choose ~0.35–0.50 delta call (or slightly ITM).
  - Entry only on confirmation: (a) gap-up holds above VWAP for 10–15m, OR (b) breakout above first 30m high with volume.
  - Stop: premium -15% (moderate) OR underlying breaks VWAP/structure; also use time-stop (exit by 2:30pm if no move).
  - Targets: scale out +20–30%, trail remainder for +40–50% when momentum continues.
  - Avoid entries if bid-ask spreads are wide or IV is extremely elevated vs recent days.

## Top 15 by options suitability (for reference)

| ticker        |     p_up |    score |   options_score |   rel_strength_5d |   rsi_14 |   adx_14 |   atr_pct |
|:--------------|---------:|---------:|----------------:|------------------:|---------:|---------:|----------:|
| TATAMOTORS.NS | 0.511327 | 0.508295 |        0.785585 |      -0.0120653   |  25.4486 |  60.6891 | 0.024432  |
| SHRIRAMFIN.NS | 0.505959 | 0.504383 |        0.596428 |      -0.00274397  |  60.8296 |  31.7898 | 0.0232882 |
| ADANIENT.NS   | 0.48614  | 0.486714 |        0.566964 |       0.0128314   |  45.7855 |  25.5592 | 0.0270119 |
| APOLLOHOSP.NS | 0.382353 | 0.380578 |        0.506897 |      -0.00698244  |  33.0748 |  54.0031 | 0.0145583 |
| HINDALCO.NS   | 0.502153 | 0.507204 |        0.475533 |       0.0403712   |  67.6605 |  17.6148 | 0.0200882 |
| HINDUNILVR.NS | 0.502153 | 0.496979 |        0.456501 |      -0.0280261   |  24.8572 |  28.485  | 0.0194036 |
| AXISBANK.NS   | 0.505959 | 0.506459 |        0.456471 |       0.00813418  |  61.214  |  43.6219 | 0.0143969 |
| SBILIFE.NS    | 0.5      | 0.500107 |        0.454674 |       0.00641434  |  60.8245 |  32.2133 | 0.0171013 |
| TECHM.NS      | 0.502153 | 0.502839 |        0.453427 |       0.0101655   |  67.0065 |  32.7569 | 0.0167755 |
| INDUSINDBK.NS | 0.505959 | 0.501437 |        0.442482 |      -0.0221983   |  54.6128 |  23.4681 | 0.0238432 |
| TATASTEEL.NS  | 0.5      | 0.504071 |        0.436261 |       0.0339311   |  54.7305 |  27.7638 | 0.0203829 |
| HCLTECH.NS    | 0.48614  | 0.485265 |        0.429053 |      -0.000495782 |  64.2968 |  33.5717 | 0.0160125 |
| JSWSTEEL.NS   | 0.505959 | 0.500841 |        0.426239 |      -0.0262508   |  44.9935 |  22.3783 | 0.0236036 |
| LT.NS         | 0.48614  | 0.487504 |        0.422146 |       0.0142173   |  61.4961 |  32.6974 | 0.0153674 |
| BPCL.NS       | 0.5      | 0.501652 |        0.410447 |       0.0185106   |  55.9002 |  17.0549 | 0.0224846 |
