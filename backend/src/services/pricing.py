"""Assemble :class:`ComparisonRow` objects from normalized price rows (US1 drill-down).

Groups a service+region's :class:`NormalizedPrice` rows by SKU and maps the PAYG / 1-yr RI / 3-yr RI
purchase options. Any option the API does not provide is filled with an explicit "not available"
cell (FR-002a, FR-005) — never zero/blank/fabricated.
"""

from __future__ import annotations

from datetime import datetime

from ..models.comparison_row import ComparisonRow
from ..models.price_point import NormalizedPrice, PricePoint, PurchaseOption


def _group_key(rec: NormalizedPrice) -> str:
    if rec.armSkuName:
        # Compute SKUs (VMs) carry one billable dimension per SKU, so PAYG + reserved meters of
        # the same armSkuName belong on one row.
        return rec.armSkuName
    # Multi-dimensional services (Storage, Bandwidth, etc.) expose many distinct meters per
    # skuName (Read Operations, Write Operations, Data Stored, ...), each with its own unit. Keep
    # every meter as its own row instead of collapsing them — otherwise we reduce to the single
    # cheapest meter (usually a $0.00 free-tier operation) and hide every real price.
    parts = (rec.skuName, rec.productName, rec.meterName, rec.unitOfMeasure)
    return "|".join(p for p in parts if p)


def _is_spot(rec: NormalizedPrice) -> bool:
    """Spot meters are billed below on-demand and have no reservations.

    Treat every VM SKU as on-demand by ignoring its Spot PAYG meter so the
    pay-as-you-go anchor compares like-for-like against the reserved prices.
    """
    blob = f"{rec.skuName} {rec.productName}".lower()
    return "spot" in blob


def assemble_rows(
    records: list[NormalizedPrice],
    *,
    currency: str,
    retrieved_at: datetime,
    data_age_seconds: int = 0,
    is_stale: bool = False,
) -> list[ComparisonRow]:
    """Group normalized rows into per-SKU comparison rows."""
    groups: dict[str, dict[PurchaseOption, NormalizedPrice]] = {}
    order: list[str] = []
    for rec in records:
        if _is_spot(rec):
            continue
        key = _group_key(rec)
        if key not in groups:
            groups[key] = {}
            order.append(key)
        # Keep the cheapest record per purchase option (defensive against duplicates).
        existing = groups[key].get(rec.purchaseOption)
        if existing is None or rec.price < existing.price:
            groups[key][rec.purchaseOption] = rec

    rows: list[ComparisonRow] = []
    for key in order:
        options = groups[key]
        anchor = (
            options.get(PurchaseOption.PAYG)
            or options.get(PurchaseOption.RI_1Y)
            or options.get(PurchaseOption.RI_3Y)
        )
        if anchor is None:
            continue
        unit = anchor.unitOfMeasure

        def cell(option: PurchaseOption) -> PricePoint:
            rec = options.get(option)
            if rec is not None:
                return PricePoint.from_normalized(rec)
            return PricePoint.not_available(option, currency, retrieved_at, unit)

        rows.append(
            ComparisonRow(
                serviceName=anchor.serviceName,
                serviceFamily=anchor.serviceFamily,
                armSkuName=anchor.armSkuName,
                skuName=anchor.skuName,
                meterName=anchor.meterName,
                productName=anchor.productName,
                armRegionName=anchor.armRegionName,
                location=anchor.location,
                unitOfMeasure=unit,
                currencyCode=currency,
                payg=cell(PurchaseOption.PAYG),
                reserved1Y=cell(PurchaseOption.RI_1Y),
                reserved3Y=cell(PurchaseOption.RI_3Y),
                hybridBenefit=None,
                retrievedAt=retrieved_at,
                dataAgeSeconds=data_age_seconds,
                isStale=is_stale,
            )
        )

    # Stable, user-friendly ordering by SKU name (then meter for multi-dimensional services).
    rows.sort(key=lambda r: (r.serviceName, r.armSkuName or r.skuName, r.meterName))
    return rows
