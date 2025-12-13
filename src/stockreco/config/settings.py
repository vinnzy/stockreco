from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv
from typing import Optional


load_dotenv()

@dataclass(frozen=True)
class Settings:
    root: Path = Path(__file__).resolve().parents[3]
    data_dir: Path = root / "data"
    reports_dir: Path = root / "reports"
    models_dir: Path = root / "data" / "models"
    cache_dir: Path = root / "data" / "cache"

    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")

    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    # yfinance sometimes needs session caching; keep requests small
    yf_period_years: int = int(os.getenv("YF_PERIOD_YEARS", "8"))

settings = Settings()
