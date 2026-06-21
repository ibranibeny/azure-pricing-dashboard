"""Runtime configuration loaded from environment variables (FR-003a, FR-012, FR-012a).

No secrets live in this file; values come from the process environment (see deploy/.env.example).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Repository root: backend/src/config.py -> parents[2] == repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Immutable application settings resolved once at startup."""

    default_currency: str
    cache_ttl_seconds: int
    data_dir: Path
    retail_prices_base_url: str
    retail_prices_api_version: str
    request_timeout_seconds: float

    @property
    def data_dir_str(self) -> str:
        return str(self.data_dir)


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = _env_path("DATA_DIR", _REPO_ROOT / "data" / "pricing")
    settings = Settings(
        default_currency=os.environ.get("DEFAULT_CURRENCY", "USD").upper(),
        cache_ttl_seconds=int(os.environ.get("CACHE_TTL_SECONDS", "3600")),
        data_dir=data_dir,
        retail_prices_base_url=os.environ.get(
            "RETAIL_PRICES_BASE_URL", "https://prices.azure.com/api/retail/prices"
        ),
        retail_prices_api_version=os.environ.get(
            "RETAIL_PRICES_API_VERSION", "2023-01-01-preview"
        ),
        request_timeout_seconds=float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30")),
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
