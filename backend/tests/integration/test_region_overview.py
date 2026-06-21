"""Integration: region-first overview lists ALL services with a representative 'from' PAYG price (US1, R9)."""

from __future__ import annotations

from src.services.catalog import CatalogService


async def test_region_overview_lists_all_services(cache):
    catalog = CatalogService(cache)
    overview = await catalog.region_overview("eastus", currency_code="USD")

    names = {s.serviceName for s in overview.services}
    assert "Virtual Machines" in names
    assert "Storage" in names
    assert overview.source == "Azure Retail Prices API"
    assert overview.currencyCode == "USD"


async def test_representative_price_is_lowest_payg(cache):
    catalog = CatalogService(cache)
    overview = await catalog.region_overview("eastus", currency_code="USD")
    vm = next(s for s in overview.services if s.serviceName == "Virtual Machines")

    # Lowest PAYG across fixture VM SKUs is the Linux B1s rate (0.0104).
    assert vm.available is True
    assert vm.representativePrice == 0.0104
    assert vm.reserved1YAvailable is True
    assert vm.reserved3YAvailable is True
    assert vm.hybridBenefitEligible is True  # a Windows meter is present
    assert vm.skuCount == 2


async def test_list_regions_via_probe(cache):
    catalog = CatalogService(cache)
    regions = await catalog.list_regions(currency_code="USD")
    assert any(r.armRegionName == "eastus" for r in regions)
