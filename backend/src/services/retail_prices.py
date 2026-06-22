"""Async client for the Azure Retail Prices API (Principle I, FR-004, R1).

Builds OData ``$filter`` expressions, follows ``NextPageLink`` pagination to completion, and
normalizes each record into :class:`NormalizedPrice`. No prices are ever fabricated — only rows the
API returns are emitted.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ..config import Settings, get_settings
from ..models.price_point import (
    RESERVATION_TERM_1Y,
    RESERVATION_TERM_3Y,
    NormalizedPrice,
    PurchaseOption,
)

# API ``type`` value for pay-as-you-go.
_TYPE_CONSUMPTION = "Consumption"
_TYPE_RESERVATION = "Reservation"


class RetailPricesError(RuntimeError):
    """Raised when the upstream Retail Prices API is unreachable or returns an error."""


def _odata_escape(value: str) -> str:
    return value.replace("'", "''")


def build_filter(
    *,
    service_name: str | None = None,
    arm_sku_name: str | None = None,
    service_family: str | None = None,
    arm_region_name: str | None = None,
    product_name_contains: str | None = None,
) -> str:
    """Build a case-sensitive OData ``$filter`` (preview API is case-sensitive — R1)."""
    clauses: list[str] = []
    if service_name:
        clauses.append(f"serviceName eq '{_odata_escape(service_name)}'")
    if arm_sku_name:
        clauses.append(f"armSkuName eq '{_odata_escape(arm_sku_name)}'")
    if service_family:
        clauses.append(f"serviceFamily eq '{_odata_escape(service_family)}'")
    if arm_region_name:
        clauses.append(f"armRegionName eq '{_odata_escape(arm_region_name)}'")
    if product_name_contains:
        clauses.append(f"contains(productName, '{_odata_escape(product_name_contains)}')")
    return " and ".join(clauses)


def _classify(item: dict) -> tuple[PurchaseOption, str | None] | None:
    """Map an API record to a (PurchaseOption, reservationTerm) pair, or None if not relevant."""
    raw_type = (item.get("type") or item.get("priceType") or "").strip()
    if raw_type == _TYPE_CONSUMPTION:
        return PurchaseOption.PAYG, None
    if raw_type == _TYPE_RESERVATION:
        term = (item.get("reservationTerm") or "").strip()
        if term == RESERVATION_TERM_1Y:
            return PurchaseOption.RI_1Y, RESERVATION_TERM_1Y
        if term == RESERVATION_TERM_3Y:
            return PurchaseOption.RI_3Y, RESERVATION_TERM_3Y
    return None


def _normalize(item: dict, retrieved_at: datetime) -> NormalizedPrice | None:
    classified = _classify(item)
    if classified is None:
        return None
    option, term = classified
    price = item.get("retailPrice", item.get("unitPrice"))
    if price is None:
        return None
    return NormalizedPrice(
        meterId=item.get("meterId", ""),
        meterName=item.get("meterName", ""),
        serviceName=item.get("serviceName", ""),
        serviceFamily=item.get("serviceFamily", ""),
        armSkuName=item.get("armSkuName", ""),
        skuName=item.get("skuName", ""),
        productName=item.get("productName", ""),
        armRegionName=item.get("armRegionName", ""),
        location=item.get("location", ""),
        purchaseOption=option,
        price=float(price),
        currencyCode=item.get("currencyCode", ""),
        unitOfMeasure=item.get("unitOfMeasure", ""),
        reservationTerm=term,
        retrievedAt=retrieved_at,
        effectiveStartDate=item.get("effectiveStartDate"),
    )


class RetailPricesClient:
    """Thin async wrapper over ``prices.azure.com`` with full pagination."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def fetch(
        self,
        *,
        service_name: str | None = None,
        arm_sku_name: str | None = None,
        service_family: str | None = None,
        arm_region_name: str | None = None,
        product_name_contains: str | None = None,
        currency_code: str | None = None,
        max_pages: int = 1000,
    ) -> list[NormalizedPrice]:
        """Fetch and normalize all matching rows, following ``NextPageLink`` to completion."""
        currency = (currency_code or self._settings.default_currency).upper()
        filter_expr = build_filter(
            service_name=service_name,
            arm_sku_name=arm_sku_name,
            service_family=service_family,
            arm_region_name=arm_region_name,
            product_name_contains=product_name_contains,
        )
        params = {
            "api-version": self._settings.retail_prices_api_version,
            "currencyCode": currency,
        }
        if filter_expr:
            params["$filter"] = filter_expr

        retrieved_at = datetime.now(timezone.utc)
        results: list[NormalizedPrice] = []
        url: str | None = self._settings.retail_prices_base_url
        next_params: dict | None = params

        try:
            async with httpx.AsyncClient(
                timeout=self._settings.request_timeout_seconds
            ) as client:
                pages = 0
                while url and pages < max_pages:
                    response = await client.get(url, params=next_params)
                    response.raise_for_status()
                    payload = response.json()
                    for item in payload.get("Items", []):
                        normalized = _normalize(item, retrieved_at)
                        if normalized is not None:
                            results.append(normalized)
                    url = payload.get("NextPageLink")
                    next_params = None  # NextPageLink already carries the query string.
                    pages += 1
        except httpx.HTTPError as exc:  # network, timeout, non-2xx
            raise RetailPricesError(str(exc)) from exc

        return results
