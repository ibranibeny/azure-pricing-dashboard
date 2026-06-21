"""Export endpoint (US3): download the current comparison as CSV or XLSX, matching the screen."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response

from ..models.export_record import ExportFormat
from ..services.cache import PricingCache
from ..services.exporters import build_export_record, to_csv, to_xlsx
from ..services.pricing import assemble_rows
from ..services.retail_prices import RetailPricesError
from .deps import get_cache
from .pricing import _apply_hybrid_benefit, _build_filters, resolve_records

router = APIRouter(prefix="/api", tags=["export"])

_MEDIA = {
    ExportFormat.csv: "text/csv",
    ExportFormat.xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("/export/{fmt}")
async def export_pricing(
    fmt: ExportFormat = Path(...),
    serviceName: str | None = Query(default=None),
    armSkuName: str | None = Query(default=None),
    serviceFamily: str | None = Query(default=None),
    armRegionName: str = Query(...),
    currencyCode: str = Query(default="USD"),
    windowsHybridBenefit: bool = Query(default=False),
    sqlHybridBenefit: bool = Query(default=False),
    cache: PricingCache = Depends(get_cache),
) -> Response:
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
        raise HTTPException(
            status_code=502, detail=f"Upstream pricing API unavailable: {exc}"
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

    record = build_export_record(rows, filters, cached.snapshot.retrievedAt, fmt)
    if fmt is ExportFormat.csv:
        body = to_csv(record)
        ext = "csv"
    else:
        body = to_xlsx(record)
        ext = "xlsx"

    region = filters.armRegionName
    service = filters.serviceName or filters.serviceFamily or "all-services"
    filename = f"azure-pricing_{service}_{region}.{ext}".replace(" ", "-").lower()
    return Response(
        content=body,
        media_type=_MEDIA[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
