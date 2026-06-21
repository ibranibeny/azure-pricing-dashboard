"""Catalog services: region enumeration, service search, and region-first overview aggregation (US1).

The region overview (R9) aggregates a whole-region snapshot into one :class:`ServiceSummary` per
distinct ``serviceName``. The representative price is the *lowest available PAYG* price among the
service's SKUs in the region — an explicitly-labelled "from" preview, never an average or a guess.
Availability flags are computed from real API rows.
"""

from __future__ import annotations

from datetime import datetime

from ..models.price_point import NormalizedPrice, PurchaseOption
from ..models.service_summary import Region, RegionOverviewResponse, ServiceSummary
from ..models.common import PRICE_SOURCE
from .cache import CachedSnapshot, PricingCache

# A lightweight, broadly-available VM SKU used to enumerate regions cheaply and dynamically.
_REGION_PROBE_SERVICE = "Virtual Machines"
_REGION_PROBE_SKU = "Standard_B1s"


def _hybrid_eligible(rec: NormalizedPrice) -> bool:
    blob = f"{rec.productName} {rec.skuName} {rec.serviceName}".lower()
    return "windows" in blob or "sql" in blob


def aggregate_region_overview(
    records: list[NormalizedPrice],
    *,
    arm_region_name: str,
    currency: str,
    retrieved_at: datetime,
) -> list[ServiceSummary]:
    """Build one ServiceSummary per service from a whole-region snapshot."""
    by_service: dict[str, dict] = {}
    for rec in records:
        name = rec.serviceName
        if not name:
            continue
        agg = by_service.setdefault(
            name,
            {
                "family": rec.serviceFamily,
                "skus": set(),
                "min_payg": None,
                "min_unit": None,
                "ri1": False,
                "ri3": False,
                "hybrid": False,
                "location": rec.location,
            },
        )
        if rec.armSkuName:
            agg["skus"].add(rec.armSkuName)
        if rec.purchaseOption is PurchaseOption.PAYG:
            if agg["min_payg"] is None or rec.price < agg["min_payg"]:
                agg["min_payg"] = rec.price
                agg["min_unit"] = rec.unitOfMeasure
        elif rec.purchaseOption is PurchaseOption.RI_1Y:
            agg["ri1"] = True
        elif rec.purchaseOption is PurchaseOption.RI_3Y:
            agg["ri3"] = True
        if _hybrid_eligible(rec):
            agg["hybrid"] = True

    summaries: list[ServiceSummary] = []
    for name, agg in by_service.items():
        min_payg = agg["min_payg"]
        summaries.append(
            ServiceSummary(
                available=min_payg is not None,
                serviceName=name,
                serviceFamily=agg["family"],
                armRegionName=arm_region_name,
                skuCount=len(agg["skus"]),
                representativePrice=min_payg,
                representativeUnit=agg["min_unit"],
                currencyCode=currency,
                reserved1YAvailable=agg["ri1"],
                reserved3YAvailable=agg["ri3"],
                hybridBenefitEligible=agg["hybrid"],
                retrievedAt=retrieved_at,
            )
        )

    summaries.sort(key=lambda s: (s.serviceFamily, s.serviceName))
    return summaries


class CatalogService:
    """High-level catalog operations backed by the pricing cache."""

    def __init__(self, cache: PricingCache) -> None:
        self._cache = cache

    async def list_regions(self, currency_code: str | None = None) -> list[Region]:
        """Enumerate regions dynamically via a lightweight VM-SKU probe (no hardcoded list)."""
        records = await self._cache._client.fetch(  # noqa: SLF001 (intentional internal reuse)
            service_name=_REGION_PROBE_SERVICE,
            arm_sku_name=_REGION_PROBE_SKU,
            currency_code=currency_code,
        )
        seen: dict[str, str] = {}
        for rec in records:
            if rec.armRegionName and rec.armRegionName not in seen:
                seen[rec.armRegionName] = rec.location
        return [Region(armRegionName=name, location=loc) for name, loc in sorted(seen.items())]

    async def region_overview(
        self, arm_region_name: str, currency_code: str | None = None
    ) -> RegionOverviewResponse:
        cached: CachedSnapshot = await self._cache.get_region_snapshot(
            arm_region_name=arm_region_name, currency_code=currency_code
        )
        snap = cached.snapshot
        services = aggregate_region_overview(
            snap.pricePoints,
            arm_region_name=arm_region_name,
            currency=snap.currencyCode,
            retrieved_at=snap.retrievedAt,
        )
        location = snap.pricePoints[0].location if snap.pricePoints else ""
        return RegionOverviewResponse(
            armRegionName=arm_region_name,
            location=location,
            services=services,
            source=PRICE_SOURCE,
            retrievedAt=snap.retrievedAt,
            currencyCode=snap.currencyCode,
            isStale=cached.is_stale,
            warning=None,
        )

    async def search_services(
        self, arm_region_name: str | None, search: str | None
    ) -> list[str]:
        """Optional typeahead over service names; region-scoped when a region is given."""
        if arm_region_name:
            cached = await self._cache.get_region_snapshot(arm_region_name=arm_region_name)
            names = {r.serviceName for r in cached.snapshot.pricePoints if r.serviceName}
        else:
            return []
        term = (search or "").strip().lower()
        result = sorted(n for n in names if not term or term in n.lower())
        return result
