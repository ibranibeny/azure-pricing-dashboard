"""Persisted JSON snapshot for one (service, region) scope (FR-012a).

Stored at ``data/pricing/{service}_{region}.json`` (slugified). Serves the dashboard from a stored
snapshot between refreshes and is the on-disk backing for the in-memory cache.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .common import PRICE_SOURCE
from .price_point import NormalizedPrice


class PricingSnapshot(BaseModel):
    """All normalized price rows for one service+region scope, with provenance."""

    serviceName: str
    armRegionName: str
    currencyCode: str
    source: str = PRICE_SOURCE
    apiVersion: str
    retrievedAt: datetime
    pricePoints: list[NormalizedPrice] = Field(default_factory=list)
