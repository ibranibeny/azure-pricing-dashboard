"""JSON file persistence for per-(service, region) pricing snapshots (FR-012a, R8).

Each snapshot is stored at ``data/pricing/{service}_{region}.json`` (slugified), carrying its
source, API version, retrieval timestamp, and the normalized rows. In ACI this directory lives on a
mounted Azure Files share so snapshots survive restarts.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import Settings, get_settings
from ..models.snapshot import PricingSnapshot

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lowercase, hyphenate, and strip a value for safe use in a filename."""
    return _SLUG_RE.sub("-", value.strip().lower()).strip("-") or "unknown"


class JsonDataStore:
    """Reads/writes :class:`PricingSnapshot` JSON files under the configured data directory."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._dir: Path = self._settings.data_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, service_name: str, arm_region_name: str) -> Path:
        return self._dir / f"{slugify(service_name)}_{slugify(arm_region_name)}.json"

    def write(self, snapshot: PricingSnapshot) -> Path:
        path = self.path_for(snapshot.serviceName, snapshot.armRegionName)
        path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        return path

    def read(self, service_name: str, arm_region_name: str) -> PricingSnapshot | None:
        path = self.path_for(service_name, arm_region_name)
        if not path.exists():
            return None
        return PricingSnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def list_snapshots(self) -> list[Path]:
        return sorted(self._dir.glob("*.json"))
