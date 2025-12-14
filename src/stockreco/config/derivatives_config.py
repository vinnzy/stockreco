from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
from pathlib import Path
import yaml

@dataclass
class DerivativesConfig:
    enabled: bool = True
    provider: str = "nse_fallback"
    risk_free_rate: float = 0.065
    entry_slippage_pct: float = 0.5
    stop_loss_premium_factor: float = 0.65
    default_atr_points: Optional[Dict[str, float]] = None

def load_derivatives_config(repo_root: Path) -> DerivativesConfig:
    cfg_path = repo_root / "src" / "stockreco" / "config" / "derivatives.yaml"
    if not cfg_path.exists():
        return DerivativesConfig(default_atr_points={"NIFTY": 220.0, "BANKNIFTY": 480.0})
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return DerivativesConfig(
        enabled=bool(data.get("enabled", True)),
        provider=str(data.get("provider", "nse_fallback")),
        risk_free_rate=float(data.get("risk_free_rate", 0.065)),
        entry_slippage_pct=float(data.get("entry_slippage_pct", 0.5)),
        stop_loss_premium_factor=float(data.get("stop_loss_premium_factor", 0.65)),
        default_atr_points=dict(data.get("default_atr_points") or {"NIFTY": 220.0, "BANKNIFTY": 480.0}),
    )
