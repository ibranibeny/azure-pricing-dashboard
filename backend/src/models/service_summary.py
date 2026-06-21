"""Region-first overview model (US1 landing view).

The user picks a region and sees every service available there *before* drilling into any SKUs.
``representativePrice`` is the lowest available PAYG price among the service's SKUs in the region —
an explicitly-labelled "from" preview price, not a quote (FR-001, R9). Availability flags advertise
drill-down value honestly (computed from real API rows, never assumed).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ServiceSummary(BaseModel):
    available: bool
    serviceName: str
    serviceFamily: str = ""
    armRegionName: str
    skuCount: int = 0
    representativePrice: float | None = None  # lowest available PAYG; None == "not available"
    representativeUnit: str | None = None
    currencyCode: str
    reserved1YAvailable: bool = False
    reserved3YAvailable: bool = False
    hybridBenefitEligible: bool = False
    retrievedAt: datetime


class RegionOverviewResponse(BaseModel):
    """Response for GET /api/regions/{armRegionName}/services."""

    armRegionName: str
    location: str = ""
    services: list[ServiceSummary]
    source: str
    retrievedAt: datetime
    currencyCode: str
    isStale: bool = False
    warning: str | None = None


class Region(BaseModel):
    armRegionName: str
    location: str = ""
