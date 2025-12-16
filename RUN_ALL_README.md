# Unified Pipeline Script

## Overview

The `run_all.py` script orchestrates the complete end-of-day stock recommendation pipeline and starts the application servers. This is your **one-stop script** to run everything.

## Quick Start

### Run Everything (Default)
```bash
# From the project root
python scripts/run_all.py
```
Or use the convenience wrapper:
```bash
./run_all.sh
```

This will:
1. ✅ Generate models for yesterday's data
2. ✅ Generate stock recommendations
3. ✅ Generate options recommendations
4. ✅ Generate MCX recommendations
5. ✅ Start the backend API server (http://localhost:8000)
6. ✅ Start the frontend UI server (http://localhost:5173)

Press `Ctrl+C` to stop both servers.

## Usage Options

### Specify a Date
```bash
python scripts/run_all.py --as-of 2025-12-14
```

### Skip Model Generation (Use Existing Models)
```bash
python scripts/run_all.py --skip-models
```

### Skip Server Startup (Just Generate Reports)
```bash
python scripts/run_all.py --skip-servers
```

### Specify Trading Mode
```bash
python scripts/run_all.py --mode balanced
# Options: aggressive, balanced, conservative
```

### Specify Data Provider
```bash
python scripts/run_all.py --provider nse_fallback
# Options: local_csv, nse_fallback, zerodha, upstox
```

### Specify Universe (Custom Stock List)
```bash
python scripts/run_all.py --universe "NIFTY,BANKNIFTY,RELIANCE.NS"
```

### Combine Options
```bash
# Generate reports for a specific date without starting servers
python scripts/run_all.py --as-of 2025-12-14 --skip-servers

# Use existing models and just start servers
python scripts/run_all.py --skip-models --skip-servers=false
```

## Pipeline Steps

### Step 1: Model Generation & Stock Recommendations
- Runs: `scripts/run_daily_full_pipeline.py`
- Generates: `data/models/{date}/` (ML models)
- Generates: `reports/{date}/` (stock recommendations)

### Step 2: Options Recommendations
- Runs: `scripts/run_eod_option_reco.py`
- Generates: `reports/options/option_reco_{date}.json`
- Generates: `reports/options/option_reco_{date}.csv`

### Step 3: MCX Recommendations
- Runs: `scripts/generate_mcx_recos.py`
- Generates: `reports/mcx/mcx_reco_{date}.json`
- Generates: `reports/mcx/mcx_reco_{date}.csv`

### Step 4: Server Startup
- Backend: `python scripts/run_ui_api.py` → http://localhost:8000
- Frontend: `npm run dev` (in frontend/) → http://localhost:5173

## Error Handling

The script is designed to be resilient:
- If one step fails, it continues with the remaining steps
- A summary is displayed at the end showing which steps succeeded/failed
- The script exits with code 1 if any step failed

## Full Command Reference

```bash
python scripts/run_all.py \
  [--as-of YYYY-MM-DD] \
  [--skip-models] \
  [--skip-servers] \
  [--mode aggressive|balanced|conservative] \
  [--provider local_csv|nse_fallback|zerodha|upstox] \
  [--universe TICKER1,TICKER2,...]
```

## Examples

### Daily Production Run
```bash
# Run at end of trading day to generate all reports and start servers
python scripts/run_all.py
```

### Backfill Historical Date
```bash
# Generate reports for a past date
python scripts/run_all.py --as-of 2025-12-10 --skip-servers
```

### Development Mode
```bash
# Use existing models, just start servers for UI development
python scripts/run_all.py --skip-models
```

### Conservative Trading Mode
```bash
# Generate reports with conservative signal thresholds
python scripts/run_all.py --mode conservative
```

## Troubleshooting

### "No dated folders under data/models"
- Run without `--skip-models` to generate models first
- Or specify a date with `--as-of` that has existing models

### "No BhavCopyDateWise_*.csv found"
- Ensure MCX bhavcopy data exists in `data/derivatives/{date}/`
- The MCX step will fail but other steps will continue

### Servers won't start
- Check if ports 8000 (backend) or 5173 (frontend) are already in use
- Kill existing processes: `lsof -ti:8000 | xargs kill` and `lsof -ti:5173 | xargs kill`

### Frontend build errors
- Ensure dependencies are installed: `cd frontend && npm install`

## See Also

- Individual scripts in `scripts/` directory for running steps separately
- `run.md` for additional workflow documentation
