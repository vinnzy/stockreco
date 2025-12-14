# stockreco – Options/Derivatives Add-on (Drop-in)

This is an **additive** module set for your `stockreco` repo. It does **not** modify existing code.
It adds an end-of-day (EOD) job that:

- reads your existing model output CSVs under `data/models/YYYY-MM-DD/`
- pulls option chain + IV (and spot) via a **pluggable provider**
- produces a **next-market-day** recommendation (CE/PE or Futures)
- writes outputs to `reports/options/` as JSON + CSV

## Quick start

1) Copy the `src/stockreco/...` folders in this zip into your repo (same paths).
2) Run:

```bash
python scripts/run_eod_option_reco.py --as-of 2025-12-12 --universe "NIFTY,BANKNIFTY"
```

If `--as-of` is omitted it will auto-pick the **latest** date folder in `data/models/`.

Outputs:
- `reports/options/option_reco_<as-of>.json`
- `reports/options/option_reco_<as-of>.csv`

## Providers

Default provider in this drop-in is `NSE_FALLBACK` (dev-only).
For production, implement `ZerodhaProvider`/`UpstoxProvider` using licensed APIs and set:

```bash
--provider zerodha
```

(or in config: `provider: zerodha`)

> Note: automated scraping of exchange websites can violate ToS. Prefer licensed broker/vendor APIs.

## Assumptions about your model CSVs

The loader scans all CSVs under `data/models/<as-of>/` and looks for columns:
- `ticker` (or `symbol`)
- `buy_win` and `sell_win` (0/1)
- optional: `mode`, `exp_oh`, `dd_ol`

Rows without both `buy_win` and `sell_win` are ignored.

## Configuration

Optional YAML (create in your repo):

`src/stockreco/config/derivatives.yaml`
```yaml
enabled: true
provider: nse_fallback
risk_free_rate: 0.065
default_atr_points:
  NIFTY: 220
  BANKNIFTY: 480
entry_slippage_pct: 0.5
stop_loss_premium_factor: 0.65
```
