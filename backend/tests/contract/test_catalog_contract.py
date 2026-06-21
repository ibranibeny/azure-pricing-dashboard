"""Contract: catalog endpoints (region overview + regions list) match the OpenAPI schemas."""

from __future__ import annotations


def test_region_overview_services_match_contract(api_client, validate_schema):
    resp = api_client.get("/api/regions/eastus/services", params={"currencyCode": "USD"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["armRegionName"] == "eastus"
    assert isinstance(body["services"], list) and body["services"]
    for summary in body["services"]:
        validate_schema("ServiceSummary", summary)


def test_regions_list_shape(api_client):
    resp = api_client.get("/api/regions")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    for region in body:
        assert "armRegionName" in region and "location" in region
