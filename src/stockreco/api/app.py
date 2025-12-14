from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from stockreco.api.routes import options_ltp, options_quotes


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    # src/stockreco/api/app.py -> repo root is 4 levels up
    return here.parents[3]

def _list_dates_from_reports(folder: Path, pattern: str) -> List[str]:
    rx = re.compile(pattern)
    dates = []
    if folder.exists():
        for p in folder.glob("*.json"):
            m = rx.match(p.name)
            if m:
                dates.append(m.group(1))
    return sorted(set(dates))

def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed reading {path.name}: {e}")

def create_app(repo_root: Optional[Path] = None) -> FastAPI:
    repo = repo_root or _repo_root()
    app = FastAPI(title="stockreco-ui-api", version="0.1")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"ok": True, "repo_root": str(repo)}
    
    # Initialize routers with repo root
    options_ltp.set_repo_root(repo)
    
    # Include routers
    app.include_router(options_ltp.router)
    app.include_router(options_quotes.router)

    # --- Options reco outputs (reports/options) ---
    @app.get("/api/options/dates")
    def option_dates():
        folder = repo / "reports" / "options" / "options"
        dates = _list_dates_from_reports(folder, r"^option_reco_(\d{4}-\d{2}-\d{2})\.json$")
        latest = dates[-1] if dates else None
        return {"latest_as_of": latest, "dates": dates, "reports_dir": str(folder)}

    @app.get("/api/options/{as_of}")
    def option_reco(as_of: str):
        folder = repo / "reports" / "options" / "options"
        path = folder / f"option_reco_{as_of}.json"

        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Missing {path}")
        return _read_json(path)

    # --- Live-ish LTP lookup from data/derivatives/<date>/op*.csv ---
    @app.get("/api/options/ltp")
    def option_ltp(options: List[str] = Query(..., description="Repeated option symbols")):
        """
        UI calls: /api/options/ltp?options=NIFTY06JAN2626100CE&options=ADANIENT24FEB262280CE...
        We load data/derivatives/<latest_date>/op*.csv and return ltp per symbol.
        """
        import csv
        from pathlib import Path

        # pick latest available derivatives folder (YYYY-MM-DD)
        deriv_root = repo / "data" / "derivatives"
        if not deriv_root.exists():
            raise HTTPException(status_code=404, detail=f"Missing {deriv_root}")

        date_folders = sorted([p for p in deriv_root.iterdir() if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)])
        if not date_folders:
            raise HTTPException(status_code=404, detail=f"No dated folders under {deriv_root}")

        latest_folder = date_folders[-1]

        # find op*.csv inside that folder
        op_files = sorted(latest_folder.glob("op*.csv"))
        if not op_files:
            raise HTTPException(status_code=404, detail=f"Missing op*.csv under {latest_folder}")

        op_path = op_files[0]

        # --- Build map: OPTION_SYMBOL -> ltp ---
        # Your UI key format: SYMBOL + DDMMMYY + STRIKE + CE/PE
        # We attempt to reconstruct the same key from CSV columns.
        # This works if CSV has: SYMBOL, EXPIRY_DT, STRIKE_PR, OPTION_TYP, CLOSE(or LTP)
        out: Dict[str, Dict[str, Any]] = {}

        def _fmt_exp(exp_raw: str) -> str:
            # CSV may contain: 06-JAN-2026 or 2026-01-06 or 06/01/2026
            exp_raw = (exp_raw or "").strip()
            # try dd-MMM-yyyy
            try:
                dt = datetime.strptime(exp_raw.upper(), "%d-%b-%Y")
                return dt.strftime("%d%b%y").upper()
            except Exception:
                pass
            # try yyyy-mm-dd
            try:
                dt = datetime.strptime(exp_raw, "%Y-%m-%d")
                return dt.strftime("%d%b%y").upper()
            except Exception:
                pass
            # try dd/mm/yyyy
            try:
                dt = datetime.strptime(exp_raw, "%d/%m/%Y")
                return dt.strftime("%d%b%y").upper()
            except Exception:
                return ""

        # load csv
        rows = []
        try:
            with op_path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    rows.append(r)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed reading {op_path}: {e}")

        # index by our normalized option symbol
        idx: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            sym = (r.get("SYMBOL") or r.get("Symbol") or r.get("symbol") or "").strip().upper()
            exp = _fmt_exp(r.get("EXPIRY_DT") or r.get("Expiry") or r.get("expiry") or "")
            strike = r.get("STRIKE_PR") or r.get("Strike") or r.get("strike") or ""
            opt_typ = (r.get("OPTION_TYP") or r.get("OptionType") or r.get("option_type") or "").strip().upper()

            if not sym or not exp or not strike or opt_typ not in ("CE", "PE"):
                continue

            try:
                strike_i = str(int(round(float(strike))))
            except Exception:
                continue

            key = f"{sym}{exp}{strike_i}{opt_typ}"

            # LTP column names differ by source
            ltp_raw = (
                r.get("LTP")
                or r.get("ltp")
                or r.get("CLOSE")
                or r.get("Close")
                or r.get("close")
                or r.get("SETTLE_PR")
                or r.get("SettlePrice")
            )

            try:
                ltp = float(ltp_raw) if ltp_raw is not None and ltp_raw != "" else None
            except Exception:
                ltp = None

            idx[key] = {"ltp": ltp}

        # respond for requested options
        for raw in options:
            k = (raw or "").strip().upper()
            hit = idx.get(k)
            if not hit or hit.get("ltp") is None:
                out[k] = {"ok": False, "ltp": None}
            else:
                out[k] = {"ok": True, "ltp": round(float(hit["ltp"]), 2)}

        return {"as_of": latest_folder.name, "data": out, "source": str(op_path)}


    # --- Stock momentum reports (reports/stockreco) ---
    @app.get("/api/stockreco/dates")
    def stockreco_dates():
        folder = repo / "reports" / "stockreco"
        strict = _list_dates_from_reports(folder, r"^(\d{4}-\d{2}-\d{2})_strict\.json$")
        aggressive = _list_dates_from_reports(folder, r"^(\d{4}-\d{2}-\d{2})_aggressive\.json$")
        dates = sorted(set(strict) | set(aggressive))
        latest = dates[-1] if dates else None
        # Build index map for UI
        index: Dict[str, Dict[str, str]] = {}
        for d in dates:
            index[d] = {
                "strict": str(folder / f"{d}_strict.json") if (folder / f"{d}_strict.json").exists() else "",
                "aggressive": str(folder / f"{d}_aggressive.json") if (folder / f"{d}_aggressive.json").exists() else "",
            }
        return {"latest_target_date": latest, "dates": dates, "index": index, "reports_dir": str(folder)}

    @app.get("/api/stockreco/{target_date}/{mode}")
    def stockreco_report(target_date: str, mode: str):
        mode = mode.lower().strip()
        if mode not in ("strict", "aggressive"):
            raise HTTPException(status_code=400, detail="mode must be strict|aggressive")
        folder = repo / "reports" / "stockreco"
        path = folder / f"{target_date}_{mode}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Missing {path}")
        return {"target_date": target_date, "mode": mode, "report": _read_json(path)}

    return app

def run(host: str = "0.0.0.0", port: int = 8000):
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")
