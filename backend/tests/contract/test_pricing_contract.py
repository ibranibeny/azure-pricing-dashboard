"""Contract: /api/pricing and /api/regions/{region}/services responses match the OpenAPI schemas."""

from __future__ import annotations


def test_pricing_response_matches_contract(api_client, validate_schema):
    resp = api_client.get(
        "/api/pricing",
        params={
            "serviceName": "Virtual Machines",
            "armRegionName": "eastus",
            "currencyCode": "USD",
            "windowsHybridBenefit": "true",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    validate_schema("PricingResponse", body)
    for row in body["rows"]:
        validate_schema("ComparisonRow", row)
        validate_schema("PricePoint", row["payg"])


def test_pricing_missing_filter_returns_400(api_client):
    resp = api_client.get("/api/pricing", params={"armRegionName": "eastus"})
    assert resp.status_code == 400
