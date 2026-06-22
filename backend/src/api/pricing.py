"""Drill-down pricing endpoint (US1 + US2): per-SKU PAYG / 1-yr RI / 3-yr RI with Hybrid Benefit.

Validation failures return HTTP 400 (Principle never fabricates). Upstream API failures return HTTP
502 with an explicit warning and zero rows — the UI shows "not available", never invented numbers
(FR-013, Principle I).
"""

from __future__ import annotations

from pydantic import ValidationError

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models.comparison_row import ComparisonRow, PricingResponse
from ..models.common import PRICE_SOURCE
from ..models.price_point import NormalizedPrice, PurchaseOption
from ..models.query import QueryFilters
from ..services.cache import PricingCache
from ..services.guidance import build_guidance
from ..services.hybrid_benefit import compute_hybrid_benefit
from ..services.pricing import assemble_rows
from ..services.retail_prices import RetailPricesError
from .deps import get_cache

router = APIRouter(prefix="/api", tags=["pricing"])

# Some catalog services are really a ``productName`` slice of a broader Retail Prices
# ``serviceName``. The Azure Retail Prices API has no "Azure Files" service — those meters live
# under ``serviceName = "Storage"`` (productName contains "Files"); likewise ADLS Gen2. Map the
# friendly label to the real (serviceName, productName-substring) to fetch so prices resolve.
_SUBSERVICE_MAP: dict[str, tuple[str, str]] = {
    "Azure Files": ("Storage", "Files"),
    "Azure Data Lake Storage Gen2": ("Storage", "Data Lake"),
}


def _build_filters(
    serviceName: str | None,
    armSkuName: str | None,
    serviceFamily: str | None,
    armRegionName: str,
    currencyCode: str,
    windowsHybridBenefit: bool,
    sqlHybridBenefit: bool,
) -> QueryFilters:
    try:
        return QueryFilters(
            serviceName=serviceName,
            armSkuName=armSkuName,
            serviceFamily=serviceFamily,
            armRegionName=armRegionName,
            currencyCode=currencyCode,
            windowsHybridBenefit=windowsHybridBenefit,
            sqlHybridBenefit=sqlHybridBenefit,
        )
    except ValidationError as exc:
        messages = [e.get("msg", "Invalid query") for e in exc.errors()]
        raise HTTPException(status_code=400, detail="; ".join(messages))


async def resolve_records(
    cache: PricingCache, filters: QueryFilters
) -> tuple[list[NormalizedPrice], object]:
    """Fetch the relevant normalized rows for the filter set, plus the cache wrapper."""
    if filters.serviceName:
        sub = _SUBSERVICE_MAP.get(filters.serviceName)
        if sub is not None:
            fetch_service_name, product_contains = sub
            cached = await cache.get_snapshot(
                service_name=filters.serviceName,
                arm_region_name=filters.armRegionName,
                currency_code=filters.currencyCode,
                fetch_service_name=fetch_service_name,
                product_contains=product_contains,
            )
        else:
            cached = await cache.get_snapshot(
                service_name=filters.serviceName,
                arm_region_name=filters.armRegionName,
                currency_code=filters.currencyCode,
            )
        records = list(cached.snapshot.pricePoints)
    else:
        cached = await cache.get_region_snapshot(
            arm_region_name=filters.armRegionName, currency_code=filters.currencyCode
        )
        records = list(cached.snapshot.pricePoints)
        if filters.serviceFamily:
            records = [r for r in records if r.serviceFamily == filters.serviceFamily]

    if filters.armSkuName:
        records = [r for r in records if r.armSkuName == filters.armSkuName]
    return records, cached


def _apply_hybrid_benefit(
    rows: list[ComparisonRow], records: list[NormalizedPrice], filters: QueryFilters
) -> None:
    """Attach a derived Hybrid Benefit result to each eligible row (in place)."""
    payg_by_sku: dict[str, NormalizedPrice] = {}
    for rec in records:
        if rec.purchaseOption is PurchaseOption.PAYG and rec.armSkuName:
            existing = payg_by_sku.get(rec.armSkuName)
            if existing is None or rec.price > existing.price:
                # Prefer the Windows/SQL (higher) PAYG meter as the benefit base.
                payg_by_sku[rec.armSkuName] = rec
    for row in rows:
        base = payg_by_sku.get(row.armSkuName)
        if base is None:
            continue
        row.hybridBenefit = compute_hybrid_benefit(
            base_payg=base,
            windows_applied=filters.windowsHybridBenefit,
            sql_applied=filters.sqlHybridBenefit,
            candidates=records,
        )


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing(
    serviceName: str | None = Query(default=None),
    armSkuName: str | None = Query(default=None),
    serviceFamily: str | None = Query(default=None),
    armRegionName: str = Query(...),
    currencyCode: str = Query(default="USD"),
    windowsHybridBenefit: bool = Query(default=False),
    sqlHybridBenefit: bool = Query(default=False),
    cache: PricingCache = Depends(get_cache),
) -> PricingResponse:
    filters = _build_filters(
        serviceName,
        armSkuName,
        serviceFamily,
        armRegionName,
        currencyCode,
        windowsHybridBenefit,
        sqlHybridBenefit,
    )

    try:
        records, cached = await resolve_records(cache, filters)
    except RetailPricesError as exc:
        # Never fabricate: return zero rows with an explicit warning (FR-013).
        from datetime import datetime, timezone

        return PricingResponse(
            rows=[],
            source=PRICE_SOURCE,
            retrievedAt=datetime.now(timezone.utc),
            currencyCode=filters.currencyCode,
            isStale=True,
            warning=f"Live pricing is temporarily unavailable ({exc}). No prices are shown.",
            guidance=[],
        )

    rows = assemble_rows(
        records,
        currency=filters.currencyCode,
        retrieved_at=cached.snapshot.retrievedAt,
        data_age_seconds=cached.data_age_seconds,
        is_stale=cached.is_stale,
    )

    if filters.windowsHybridBenefit or filters.sqlHybridBenefit:
        _apply_hybrid_benefit(rows, records, filters)

    warning = None
    if cached.is_stale:
        minutes = cached.data_age_seconds // 60
        warning = f"Showing cached prices retrieved ~{minutes} min ago (upstream not refreshed)."

    return PricingResponse(
        rows=rows,
        source=PRICE_SOURCE,
        retrievedAt=cached.snapshot.retrievedAt,
        currencyCode=filters.currencyCode,
        isStale=cached.is_stale,
        warning=warning,
        guidance=build_guidance(rows),
    )
