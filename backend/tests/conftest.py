"""Shared test fixtures.

Tests run fully offline: a :class:`FakeRetailClient` returns deterministic normalized rows instead
of calling the Azure Retail Prices API, and a temp data dir keeps JSON snapshots out of the repo.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.config import Settings
from src.models.price_point import (
    NormalizedPrice,
    PurchaseOption,
    RESERVATION_TERM_1Y,
    RESERVATION_TERM_3Y,
)

RETRIEVED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _vm_rows(region: str = "eastus") -> list[NormalizedPrice]:
    """Two VM SKUs in a region, including Windows + Linux PAYG and 1/3-yr reservations."""
    common = dict(
        serviceName="Virtual Machines",
        serviceFamily="Compute",
        armRegionName=region,
        location="US East",
        currencyCode="USD",
        unitOfMeasure="1 Hour",
        retrievedAt=RETRIEVED,
    )
    return [
        # B1s — Linux PAYG, Windows PAYG, 1yr + 3yr reservations (Linux).
        NormalizedPrice(
            meterId="m1",
            armSkuName="Standard_B1s",
            skuName="B1s",
            productName="Virtual Machines BS Series",
            purchaseOption=PurchaseOption.PAYG,
            price=0.0104,
            **common,
        ),
        NormalizedPrice(
            meterId="m2",
            armSkuName="Standard_B1s",
            skuName="B1s Windows",
            productName="Virtual Machines BS Series Windows",
            purchaseOption=PurchaseOption.PAYG,
            price=0.0188,
            **common,
        ),
        NormalizedPrice(
            meterId="m3",
            armSkuName="Standard_B1s",
            skuName="B1s",
            productName="Virtual Machines BS Series",
            purchaseOption=PurchaseOption.RI_1Y,
            price=0.0072,
            reservationTerm=RESERVATION_TERM_1Y,
            **common,
        ),
        NormalizedPrice(
            meterId="m4",
            armSkuName="Standard_B1s",
            skuName="B1s",
            productName="Virtual Machines BS Series",
            purchaseOption=PurchaseOption.RI_3Y,
            price=0.0050,
            reservationTerm=RESERVATION_TERM_3Y,
            **common,
        ),
        # D2s_v5 — PAYG only (no reservation rows => "not available" for RI).
        NormalizedPrice(
            meterId="m5",
            armSkuName="Standard_D2s_v5",
            skuName="D2s v5",
            productName="Virtual Machines Dsv5 Series",
            purchaseOption=PurchaseOption.PAYG,
            price=0.096,
            **common,
        ),
    ]


def _storage_rows(region: str = "eastus") -> list[NormalizedPrice]:
    return [
        NormalizedPrice(
            meterId="s1",
            serviceName="Storage",
            serviceFamily="Storage",
            armSkuName="",
            skuName="Hot LRS",
            productName="Blob Storage",
            armRegionName=region,
            location="US East",
            currencyCode="USD",
            unitOfMeasure="1 GB/Month",
            purchaseOption=PurchaseOption.PAYG,
            price=0.0184,
            retrievedAt=RETRIEVED,
        )
    ]


class FakeRetailClient:
    """Stand-in for RetailPricesClient that serves the fixture rows."""

    def __init__(self, region: str = "eastus") -> None:
        self._region = region
        self.calls: list[dict] = []

    async def fetch(
        self,
        *,
        service_name: str | None = None,
        service_family: str | None = None,
        arm_sku_name: str | None = None,
        arm_region_name: str | None = None,
        product_name_contains: str | None = None,
        currency_code: str | None = None,
    ) -> list[NormalizedPrice]:
        self.calls.append(
            {
                "service_name": service_name,
                "arm_sku_name": arm_sku_name,
                "arm_region_name": arm_region_name,
                "product_name_contains": product_name_contains,
                "currency_code": currency_code,
            }
        )
        region = arm_region_name or self._region
        rows = _vm_rows(region) + _storage_rows(region)
        if service_name:
            rows = [r for r in rows if r.serviceName == service_name]
        if product_name_contains:
            rows = [r for r in rows if product_name_contains in r.productName]
        if arm_sku_name:
            rows = [r for r in rows if r.armSkuName == arm_sku_name]
        return rows


@pytest.fixture
def retrieved() -> datetime:
    return RETRIEVED


@pytest.fixture
def vm_rows() -> list[NormalizedPrice]:
    return _vm_rows()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        default_currency="USD",
        cache_ttl_seconds=3600,
        data_dir=tmp_path / "pricing",
        retail_prices_base_url="https://example.invalid/api/retail/prices",
        retail_prices_api_version="2023-01-01-preview",
        request_timeout_seconds=5,
    )


@pytest.fixture
def fake_client() -> FakeRetailClient:
    return FakeRetailClient()


@pytest.fixture
def cache(settings, fake_client):
    from src.services.cache import PricingCache
    from src.services.datastore import JsonDataStore

    return PricingCache(
        settings=settings,
        datastore=JsonDataStore(settings),
        client=fake_client,
    )


@pytest.fixture
def api_client(cache):
    """FastAPI TestClient with the pricing cache overridden to the offline fixture cache."""
    from fastapi.testclient import TestClient

    from src.api.deps import get_cache, get_catalog
    from src.main import create_app
    from src.services.catalog import CatalogService

    app = create_app()
    app.dependency_overrides[get_cache] = lambda: cache
    app.dependency_overrides[get_catalog] = lambda: CatalogService(cache)
    with TestClient(app) as client:
        yield client
