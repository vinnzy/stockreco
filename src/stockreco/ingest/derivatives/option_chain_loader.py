from __future__ import annotations
from pathlib import Path
from typing import Optional
from .provider_base import DerivativesProvider
from .local_csv_provider import LocalCsvProvider

# Keep your existing providers if present in repo;
# this file adds local_csv selection.
def get_provider(provider_name: str, repo_root: Optional[Path] = None, as_of: Optional[str] = None, **kwargs) -> DerivativesProvider:
    p = (provider_name or "local_csv").strip().lower()
    if p in {"local", "local_csv", "csv", "nse_fallback"}:
        if repo_root is None or as_of is None:
            raise ValueError("local_csv provider requires repo_root and as_of")
        return LocalCsvProvider(repo_root=Path(repo_root), as_of=str(as_of), **kwargs)
    raise ValueError(f"Unknown provider: {provider_name}")
