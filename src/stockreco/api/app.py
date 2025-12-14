from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

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
