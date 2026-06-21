"""One row of the on-screen comparison: a SKU in a region with its three purchase options.

This is the unit that is both rendered and exported, guaranteeing screen↔export parity (Principle IV).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .hybrid_benefit import HybridBenefitResult
from .price_point import PricePoint


class ComparisonRow(BaseModel):
    serviceName: str
    serviceFamily: str = ""
    armSkuName: str
    skuName: str = ""
    productName: str = ""
    armRegionName: str
    location: str = ""
    unitOfMeasure: str = ""
    currencyCode: str
    payg: PricePoint
    reserved1Y: PricePoint
    reserved3Y: PricePoint
    hybridBenefit: HybridBenefitResult | None = None
    retrievedAt: datetime
    dataAgeSeconds: int = 0
    isStale: bool = False


class PricingResponse(BaseModel):
    """Drill-down response for a service+region (GET /api/pricing)."""

    rows: list[ComparisonRow]
    source: str
    retrievedAt: datetime
    currencyCode: str
    isStale: bool = False
    warning: str | None = None
    guidance: list[str] = []
