"""Catalog endpoints: regions, region-first overview (all services), and optional service search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..services.catalog import CatalogService
from ..services.retail_prices import RetailPricesError
from ..models.service_summary import Region, RegionOverviewResponse
from .deps import get_catalog

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/regions", response_model=list[Region])
async def list_regions(
    currencyCode: str = Query(default="USD"),
    catalog: CatalogService = Depends(get_catalog),
) -> list[Region]:
    try:
        return await catalog.list_regions(currency_code=currencyCode)
    except RetailPricesError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream pricing API unavailable: {exc}")


@router.get("/regions/{armRegionName}/services", response_model=RegionOverviewResponse)
async def region_overview(
    armRegionName: str = Path(...),
    currencyCode: str = Query(default="USD"),
    catalog: CatalogService = Depends(get_catalog),
) -> RegionOverviewResponse:
    """Region-first overview (US1): all services available in the region with representative cost."""
    try:
        return await catalog.region_overview(armRegionName, currency_code=currencyCode)
    except RetailPricesError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream pricing API unavailable: {exc}")


@router.get("/services")
async def search_services(
    armRegionName: str | None = Query(default=None),
    search: str | None = Query(default=None),
    catalog: CatalogService = Depends(get_catalog),
) -> dict:
    """Optional typeahead used inside the region overview to filter the service list by name."""
    try:
        services = await catalog.search_services(armRegionName, search)
    except RetailPricesError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream pricing API unavailable: {exc}")
    return {"services": services}
