"""Integration: VM drill-down returns per-SKU PAYG/1yr/3yr with honest 'not available' (US1, FR-001b)."""

from __future__ import annotations


def test_pricing_drilldown_returns_sku_rows(api_client):
    resp = api_client.get(
        "/api/pricing",
        params={"serviceName": "Virtual Machines", "armRegionName": "eastus", "currencyCode": "USD"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "Azure Retail Prices API"
    skus = {row["armSkuName"] for row in body["rows"]}
    assert {"Standard_B1s", "Standard_D2s_v5"} <= skus


def test_missing_reservation_is_not_available(api_client):
    resp = api_client.get(
        "/api/pricing",
        params={"serviceName": "Virtual Machines", "armRegionName": "eastus"},
    )
    body = resp.json()
    d2 = next(r for r in body["rows"] if r["armSkuName"] == "Standard_D2s_v5")
    assert d2["payg"]["available"] is True
    assert d2["reserved1Y"]["available"] is False
    assert d2["reserved1Y"]["price"] is None


def test_missing_service_filter_is_rejected(api_client):
    resp = api_client.get("/api/pricing", params={"armRegionName": "eastus"})
    assert resp.status_code == 400


def test_region_overview_endpoint(api_client):
    resp = api_client.get("/api/regions/eastus/services", params={"currencyCode": "USD"})
    assert resp.status_code == 200
    body = resp.json()
    names = {s["serviceName"] for s in body["services"]}
    assert "Virtual Machines" in names and "Storage" in names


def test_regions_endpoint(api_client):
    resp = api_client.get("/api/regions")
    assert resp.status_code == 200
    assert any(r["armRegionName"] == "eastus" for r in resp.json())
