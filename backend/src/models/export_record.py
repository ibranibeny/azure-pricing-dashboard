"""The materialized payload used to generate CSV/XLSX — identical to what was rendered (Principle IV)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .comparison_row import ComparisonRow
from .common import PRICE_SOURCE
from .query import QueryFilters


class ExportFormat(str, Enum):
    csv = "csv"
    xlsx = "xlsx"


class ExportRecord(BaseModel):
    rows: list[ComparisonRow]
    filters: QueryFilters
    source: str = PRICE_SOURCE
    retrievedAt: datetime
    generatedAt: datetime
    format: ExportFormat
