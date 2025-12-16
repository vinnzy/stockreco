from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from stockreco.api.routes import options_ltp, options_quotes
from fastapi import Query
from stockreco.ingest.mcx.bhavcopy import parse_mcx_bhavcopy


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

    # --- MCX reco outputs (reports/mcx) ---
    @app.get("/api/mcx/dates")
    def mcx_dates():
        folder = repo / "reports" / "mcx"
        dates = _list_dates_from_reports(folder, r"^mcx_reco_(\d{4}-\d{2}-\d{2})\.json$")
        latest = dates[-1] if dates else None
        return {"latest_as_of": latest, "dates": dates, "reports_dir": str(folder)}

    @app.get("/api/mcx/{as_of}")
    def mcx_reco(as_of: str):
        folder = repo / "reports" / "mcx"
        path = folder / f"mcx_reco_{as_of}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Missing {path}")
        return _read_json(path)


    @app.get("/api/commodities/dates")
    def commodity_dates():
        folder = repo / "reports" / "commodities"
        dates = _list_dates_from_reports(folder, r"^commodity_reco_(\d{4}-\d{2}-\d{2})\.json$")
        latest = dates[-1] if dates else None
        return {"latest_as_of": latest, "dates": dates, "reports_dir": str(folder)}

    @app.get("/api/commodities/{as_of}")
    def commodity_reco(as_of: str):
        folder = repo / "reports" / "commodities"
        path = folder / f"commodity_reco_{as_of}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Missing {path}")
        return _read_json(path)

    # --- Options reco outputs (reports/options) ---
    @app.get("/api/options/dates")
    def option_dates():
        folder = repo / "reports" / "options"
        dates = _list_dates_from_reports(folder, r"^option_reco_(\d{4}-\d{2}-\d{2})\.json$")
        latest = dates[-1] if dates else None
        return {"latest_as_of": latest, "dates": dates, "reports_dir": str(folder)}

    @app.get("/api/options/{as_of}")
    def option_reco(as_of: str):
        folder = repo / "reports" / "options"
        path = folder / f"option_reco_{as_of}.json"

        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Missing {path}")
        return _read_json(path)

    # --- Intraday Option Reco ---
    @app.get("/api/options/intraday/dates")
    def intraday_option_dates():
        folder = repo / "reports" / "options"
        dates = _list_dates_from_reports(folder, r"^intraday_reco_(\d{4}-\d{2}-\d{2})\.json$")
        latest = dates[-1] if dates else None
        return {"latest_as_of": latest, "dates": dates, "reports_dir": str(folder)}

    @app.get("/api/options/intraday/{as_of}")
    def intraday_option_reco(as_of: str):
        folder = repo / "reports" / "options"
        path = folder / f"intraday_reco_{as_of}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Missing {path}")
        return _read_json(path)

    @app.get("/api/quotes/ltp")
    def quotes_ltp(
        keys: List[str] = Query(..., description="Quote keys like MCXFUT:GOLD:05FEB26")
    ):
        as_of = max(_list_dates_from_reports(repo / "reports" / "options", r".*"))
        bhav = (
            repo
            / "data"
            / "derivatives"
            / as_of
            / f"BhavCopyDateWise_{as_of.replace('-', '')}.csv"
        )

        data = {}

        if bhav.exists():
            mcx_quotes = parse_mcx_bhavcopy(bhav)
            for k in keys:
                if k in mcx_quotes:
                    data[k] = mcx_quotes[k]

        return {"as_of": as_of, "data": data}

    # --- Live-ish LTP lookup from data/derivatives/<date>/op*.csv ---
    
    # @app.get("/api/options/ltp")
    # def option_ltp(options: List[str] = Query(..., description="Repeated option symbols")):
    #     """
    #     UI calls: /api/options/ltp?options=NIFTY06JAN2626100CE&options=ADANIENT24FEB262280CE...
    #     We load data/derivatives/<latest_date>/op*.csv and return ltp per symbol.
    #     """
    #     import csv
    #     from pathlib import Path

    #     # pick latest available derivatives folder (YYYY-MM-DD)
    #     deriv_root = repo / "data" / "derivatives"
    #     if not deriv_root.exists():
    #         raise HTTPException(status_code=404, detail=f"Missing {deriv_root}")

    #     date_folders = sorted([p for p in deriv_root.iterdir() if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)])
    #     if not date_folders:
    #         raise HTTPException(status_code=404, detail=f"No dated folders under {deriv_root}")

    #     latest_folder = date_folders[-1]

    #     # find op*.csv inside that folder
    #     op_files = sorted(latest_folder.glob("op*.csv"))
    #     if not op_files:
    #         raise HTTPException(status_code=404, detail=f"Missing op*.csv under {latest_folder}")

    #     op_path = op_files[0]

    #     # --- Build map: OPTION_SYMBOL -> ltp ---
    #     # Your UI key format: SYMBOL + DDMMMYY + STRIKE + CE/PE
    #     # We attempt to reconstruct the same key from CSV columns.
    #     # This works if CSV has: SYMBOL, EXPIRY_DT, STRIKE_PR, OPTION_TYP, CLOSE(or LTP)
    #     out: Dict[str, Dict[str, Any]] = {}

    #     def _fmt_exp(exp_raw: str) -> str:
    #         # CSV may contain: 06-JAN-2026 or 2026-01-06 or 06/01/2026
    #         exp_raw = (exp_raw or "").strip()
    #         # try dd-MMM-yyyy
    #         try:
    #             dt = datetime.strptime(exp_raw.upper(), "%d-%b-%Y")
    #             return dt.strftime("%d%b%y").upper()
    #         except Exception:
    #             pass
    #         # try yyyy-mm-dd
    #         try:
    #             dt = datetime.strptime(exp_raw, "%Y-%m-%d")
    #             return dt.strftime("%d%b%y").upper()
    #         except Exception:
    #             pass
    #         # try dd/mm/yyyy
    #         try:
    #             dt = datetime.strptime(exp_raw, "%d/%m/%Y")
    #             return dt.strftime("%d%b%y").upper()
    #         except Exception:
    #             return ""

    #     # load csv
    #     rows = []
    #     try:
    #         with op_path.open("r", newline="", encoding="utf-8") as f:
    #             reader = csv.DictReader(f)
    #             for r in reader:
    #                 rows.append(r)
    #     except Exception as e:
    #         raise HTTPException(status_code=500, detail=f"Failed reading {op_path}: {e}")

    #     # index by our normalized option symbol
    #     idx: Dict[str, Dict[str, Any]] = {}
    #     for r in rows:
    #         sym = (r.get("SYMBOL") or r.get("Symbol") or r.get("symbol") or "").strip().upper()
    #         exp = _fmt_exp(r.get("EXPIRY_DT") or r.get("Expiry") or r.get("expiry") or "")
    #         strike = r.get("STRIKE_PR") or r.get("Strike") or r.get("strike") or ""
    #         opt_typ = (r.get("OPTION_TYP") or r.get("OptionType") or r.get("option_type") or "").strip().upper()

    #         if not sym or not exp or not strike or opt_typ not in ("CE", "PE"):
    #             continue

    #         try:
    #             strike_i = str(int(round(float(strike))))
    #         except Exception:
    #             continue

    #         key = f"{sym}{exp}{strike_i}{opt_typ}"

    #         # LTP column names differ by source
    #         ltp_raw = (
    #             r.get("LTP")
    #             or r.get("ltp")
    #             or r.get("CLOSE")
    #             or r.get("Close")
    #             or r.get("close")
    #             or r.get("SETTLE_PR")
    #             or r.get("SettlePrice")
    #         )

    #         try:
    #             ltp = float(ltp_raw) if ltp_raw is not None and ltp_raw != "" else None
    #         except Exception:
    #             ltp = None

    #         idx[key] = {"ltp": ltp}

    #     # respond for requested options
    #     for raw in options:
    #         k = (raw or "").strip().upper()
    #         hit = idx.get(k)
    #         if not hit or hit.get("ltp") is None:
    #             out[k] = {"ok": False, "ltp": None}
    #         else:
    #             out[k] = {"ok": True, "ltp": round(float(hit["ltp"]), 2)}

    #     return {"as_of": latest_folder.name, "data": out, "source": str(op_path)}


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

    # ---------------------------
    # Live option LTP endpoint
    # Reads bhavcopy-style op*.csv from:
    #   data/derivatives/<YYYY-MM-DD>/op*.csv
    # ---------------------------
    from pathlib import Path
    import csv
    import math
    import re
    from datetime import datetime

    _OP_CACHE = {"key": None, "rows": None}  # simple in-process cache

    def _derivatives_root() -> Path:
        return repo / "data" / "derivatives"

    def _latest_deriv_date_folder() -> Path | None:
        root = _derivatives_root()
        if not root.exists():
            return None
        # folders are YYYY-MM-DD
        ds = sorted([p for p in root.iterdir() if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)])
        return ds[-1] if ds else None

    def _pick_op_file(folder: Path) -> Path | None:
        # user has op121225.csv etc
        ops = sorted(folder.glob("op*.csv"))
        return ops[0] if ops else None

    def _safe_float(x):
        try:
            if x is None:
                return None
            s = str(x).strip()
            if s == "" or s.upper() == "NAN":
                return None
            return float(s)
        except Exception:
            return None

    def _read_op_rows(op_path: Path) -> list[dict]:
        # op file header is truncated with ... but we only need:
        # col0 = CONTRACT_D, and any CLOSE-like column
        with op_path.open("r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return []
            rows = []
            for r in reader:
                if not r:
                    continue
                d = {}
                for i, h in enumerate(header):
                    if i < len(r):
                        d[h] = r[i]
                rows.append(d)
            return rows

    def _build_contract_map(op_rows: list[dict]) -> dict[str, dict]:
        # detect columns
        if not op_rows:
            return {}

        header = list(op_rows[0].keys())
        contract_col = header[0]  # CONTRACT_D in your file
        close_col = None
        for h in header:
            hu = h.upper()
            if hu.startswith("CLOSE"):
                close_col = h
                break
        if close_col is None:
            # fallback: sometimes CLOSE_PRICE is truncated weirdly; try any containing "CLOSE"
            for h in header:
                if "CLOSE" in h.upper():
                    close_col = h
                    break

        out = {}
        for row in op_rows:
            c = (row.get(contract_col) or "").strip().upper()
            if not c:
                continue
            ltp = _safe_float(row.get(close_col)) if close_col else None
            out[c] = {"ltp": ltp}
        return out

    _MONS = {"JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"}

    def _parse_ui_symbol(ui: str):
        """
        UI sends: SYMBOL + DDMMMYY + STRIKE + CE/PE
        Example: ADANIPORTS30DEC251520CE
        """
        s = (ui or "").strip().upper()
        m = re.match(r"^(.+?)(\d{2})([A-Z]{3})(\d{2})(\d+(?:\.\d+)?)(CE|PE)$", s)
        if not m:
            return None
        sym, dd, mon, yy, strike, opt = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
        if mon not in _MONS:
            return None
        # remove .NS if present
        sym = sym.replace(".NS", "")
        # normalize symbols like M&M in URL can arrive as M&M (fine)
        return sym, dd, mon, yy, strike, opt

    def _ui_to_contract_candidates(ui: str) -> list[str]:
        p = _parse_ui_symbol(ui)
        if not p:
            return []
        sym, dd, mon, yy, strike, opt = p
        # op file uses: OPTSTK<sym><DD>-<MON>-20<YY><CE/PE><strike>
        # and for indices: OPTIDX<sym><DD>-<MON>-20<YY><CE/PE><strike>
        exp = f"{dd}-{mon}-20{yy}"
        # Keep strike as-is, but also try integer strike (NIFTY-style)
        strikes = [strike]
        try:
            if float(strike).is_integer():
                strikes.append(str(int(float(strike))))
        except Exception:
            pass

        cands = []
        for st in strikes:
            cands.append(f"OPTSTK{sym}{exp}{opt}{st}".upper())
            cands.append(f"OPTIDX{sym}{exp}{opt}{st}".upper())
        return cands

    @app.get("/api/options/ltp")
    def option_ltp(
        options: List[str] = Query(..., description="Repeated option symbols, e.g. ?options=NIFTY06JAN2626100CE"),
        as_of: Optional[str] = Query(None, description="Optional YYYY-MM-DD to pick data/derivatives/<as_of>/"),
    ):
        # choose folder
        folder = None
        if as_of:
            cand = _derivatives_root() / as_of
            if cand.exists() and cand.is_dir():
                folder = cand
        if folder is None:
            folder = _latest_deriv_date_folder()

        if folder is None:
            raise HTTPException(status_code=404, detail="Missing data/derivatives/ folder")

        op_path = _pick_op_file(folder)
        if op_path is None or not op_path.exists():
            raise HTTPException(status_code=404, detail=f"Missing op*.csv under {folder}")

        # cache by path+mtime
        key = f"{op_path}|{op_path.stat().st_mtime}"
        if _OP_CACHE["key"] != key:
            rows = _read_op_rows(op_path)
            _OP_CACHE["rows"] = _build_contract_map(rows)
            _OP_CACHE["key"] = key

        cmap = _OP_CACHE["rows"] or {}

        out: Dict[str, Dict[str, Any]] = {}
        for ui_sym in options:
            ui_sym_u = (ui_sym or "").strip().upper()
            cands = _ui_to_contract_candidates(ui_sym_u)

            hit = None
            for c in cands:
                if c in cmap:
                    hit = cmap[c]
                    break

            if not hit or hit.get("ltp") is None:
                out[ui_sym_u] = {"ok": False, "ltp": None}
            else:
                out[ui_sym_u] = {"ok": True, "ltp": round(float(hit["ltp"]), 2)}

        return {"as_of": folder.name, "data": out, "op_file": str(op_path)}

    return app

def run(host: str = "0.0.0.0", port: int = 8000):
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")
