"""Unit: when a Hybrid Benefit counterpart meter is missing, the eligible price is 'not available'
rather than guessed (Principle I, FR-007a)."""

from __future__ import annotations

from datetime import datetime, timezone

from src.models.price_point import NormalizedPrice, PurchaseOption
from src.services.hybrid_benefit import compute_hybrid_benefit, find_linux_equivalent

RETRIEVED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _windows_only(price: float = 0.4) -> NormalizedPrice:
    return NormalizedPrice(
        meterId="w",
        serviceName="Virtual Machines",
        serviceFamily="Compute",
        armSkuName="Standard_NOLINUX",
        skuName="NoLinux Windows",
        productName="Virtual Machines NoLinux Windows",
        armRegionName="eastus",
        location="US East",
        purchaseOption=PurchaseOption.PAYG,
        price=price,
        currencyCode="USD",
        unitOfMeasure="1 Hour",
        retrievedAt=RETRIEVED,
    )


def test_find_linux_equivalent_returns_none_when_absent():
    base = _windows_only()
    assert find_linux_equivalent(base, [base]) is None


def test_windows_benefit_eligible_price_none_without_counterpart():
    base = _windows_only()
    result = compute_hybrid_benefit(
        base_payg=base,
        windows_applied=True,
        sql_applied=False,
        candidates=[base],
    )
    assert result.windowsEligible is True
    assert result.eligiblePrice is None
    assert result.basePaygPrice == base.price


def test_sql_benefit_eligible_price_none_without_license_component():
    base = NormalizedPrice(
        meterId="s",
        serviceName="SQL Database",
        serviceFamily="Databases",
        armSkuName="GP_Gen5_2",
        skuName="vCore SQL",
        productName="SQL Database General Purpose",
        armRegionName="eastus",
        location="US East",
        purchaseOption=PurchaseOption.PAYG,
        price=0.5,
        currencyCode="USD",
        unitOfMeasure="1 Hour",
        retrievedAt=RETRIEVED,
    )
    result = compute_hybrid_benefit(
        base_payg=base,
        windows_applied=False,
        sql_applied=True,
        candidates=[base],
        sql_license_component=None,  # cannot resolve -> not available
    )
    assert result.sqlEligible is True
    assert result.eligiblePrice is None
