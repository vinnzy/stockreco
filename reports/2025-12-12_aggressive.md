# stockreco report — target date 2025-12-12

- As-of EOD used: **2025-12-11**
- Final picks: **2**

## Notes
- EOD-based; take options only on intraday confirmation.
- STRICT NO-TRADE would have triggered; proceeding in AGGRESSIVE mode.
- Low conviction: mean p_up of top 3 is 0.50 (< 0.55).
- Low separation: p_up spread (P90-P10) is 0.05 (< 0.06).
- Low expansion: mean p_expand of top 3 is 0.31 (< 0.55).
- NO-TRADE for options recommended (edge too small / too clustered).

## Final bullish momentum list (next day)
### 1) SHRIRAMFIN.NS
- Calibrated P(up tomorrow): **0.51** (Low)
- Model-B P(expand ≥ thr): **0.38**
- Rationale: Ranked for options suitability (ATR/ADX/RSI impulse + Model-B p_expand) plus calibrated p_up; confirm intraday price action before entry.
- Options playbook:
  - Prefer liquid weekly expiry; choose ~0.35–0.50 delta call (or slightly ITM).
  - Entry only on confirmation: (a) gap-up holds above VWAP for 10–15m, OR (b) breakout above first 30m high with volume.
  - Stop: premium -15% (moderate) OR underlying breaks VWAP/structure; also use time-stop (exit by 2:30pm if no move).
  - Targets: scale out +20–30%, trail remainder for +40–50% when momentum continues.
  - Avoid entries if bid-ask spreads are wide or IV is extremely elevated vs recent days.

### 2) ADANIENT.NS
- Calibrated P(up tomorrow): **0.51** (Low)
- Model-B P(expand ≥ thr): **0.37**
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
| TATAMOTORS.NS | 0.486427 |   0.193937 | 0.481814 |        0.710376 |      -0.0223002   |  24.5252 |  60.7701 | 0.0253513 |
| SHRIRAMFIN.NS | 0.514244 |   0.379234 | 0.517269 |        0.691103 |       0.0281359   |  60.5847 |  32.738  | 0.0239017 |
| ADANIENT.NS   | 0.514244 |   0.371661 | 0.517655 |        0.67066  |       0.0321557   |  45.2373 |  25.8306 | 0.0282514 |
| INDUSINDBK.NS | 0.514244 |   0.392319 | 0.509024 |        0.534836 |      -0.0266144   |  50.5989 |  24.3973 | 0.0245622 |
| APOLLOHOSP.NS | 0.542398 |   0.336695 | 0.538467 |        0.528406 |      -0.0214003   |  22.6915 |  54.0001 | 0.0144123 |
| JSWSTEEL.NS   | 0.514244 |   0.356974 | 0.507918 |        0.491891 |      -0.0340906   |  38.6259 |  22.0598 | 0.024253  |
| HCLTECH.NS    | 0.525199 |   0.269992 | 0.52677  |        0.481368 |       0.0159511   |  64.1474 |  34.1145 | 0.0164292 |
| TECHM.NS      | 0.484339 |   0.251263 | 0.484829 |        0.470814 |       0.00896965  |  65.2705 |  32.5679 | 0.0171141 |
| HEROMOTOCO.NS | 0.484339 |   0.322947 | 0.475523 |        0.46169  |      -0.051668    |  51.7029 |  35.4051 | 0.0213151 |
| SUNPHARMA.NS  | 0.484339 |   0.163473 | 0.483477 |        0.456665 |      -0.000911428 |  61.1061 |  51.4553 | 0.0145151 |
| BPCL.NS       | 0.514244 |   0.362673 | 0.511953 |        0.452982 |      -0.00800905  |  42.4713 |  17.6689 | 0.0218008 |
| INFY.NS       | 0.484339 |   0.256134 | 0.48429  |        0.444273 |       0.00544362  |  61.6649 |  26.5425 | 0.0173228 |
| EICHERMOT.NS  | 0.484339 |   0.215198 | 0.487488 |        0.442463 |       0.0271651   |  61.5619 |  20.3709 | 0.0185184 |
| TATASTEEL.NS  | 0.533429 |   0.237546 | 0.532865 |        0.422761 |       0.00285468  |  44.0554 |  29.5766 | 0.0198483 |
| ASIANPAINT.NS | 0.484339 |   0.241116 | 0.475122 |        0.413088 |      -0.0549312   |  46.4455 |  41.6312 | 0.0195486 |
