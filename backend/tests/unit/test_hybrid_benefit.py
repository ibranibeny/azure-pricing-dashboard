"""Unit: Azure Hybrid Benefit derivation (US2, FR-007, FR-007a).

Windows benefit = Windows PAYG minus the Linux-equivalent compute rate for the same SKU/region.
When the counterpart meter can't be resolved, eligiblePrice is None ("not available"), never guessed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.models.price_point import NormalizedPrice, PurchaseOption
from src.services.hybrid_benefit import compute_hybrid_benefit
from tests.conftest import _vm_rows

RETRIEVED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _windows_base(rows):
    return next(
        r
        for r in rows
        if r.purchaseOption is PurchaseOption.PAYG and "windows" in r.productName.lower()
    )


def test_windows_hybrid_benefit_reduces_to_linux_rate():
    rows = _vm_rows()
    base = _windows_base(rows)  # 0.0188 Windows PAYG; Linux equivalent is 0.0104
    result = compute_hybrid_benefit(
        base_payg=base,
        windows_applied=True,
        sql_applied=False,
        candidates=rows,
    )
    assert result.windowsEligible is True
    # savings = 0.0188 - 0.0104 = 0.0084 ; eligible = 0.0104
    assert round(result.windowsSavings, 4) == 0.0084
    assert round(result.eligiblePrice, 4) == 0.0104


def test_windows_benefit_not_available_when_no_linux_counterpart():
    base = NormalizedPrice(
        meterId="x",
        serviceName="Virtual Machines",
        serviceFamily="Compute",
        armSkuName="Standard_ZZZ",
        skuName="ZZZ Windows",
        productName="Virtual Machines ZZZ Windows",
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
        windows_applied=True,
        sql_applied=False,
        candidates=[base],  # no Linux counterpart
    )
    assert result.windowsEligible is True
    assert result.eligiblePrice is None  # not fabricated


def test_no_toggle_leaves_base_price():
    rows = _vm_rows()
    base = _windows_base(rows)
    result = compute_hybrid_benefit(
        base_payg=base,
        windows_applied=False,
        sql_applied=False,
        candidates=rows,
    )
    assert result.eligiblePrice == base.price
    assert result.windowsSavings == 0.0
    assert result.sqlSavings == 0.0
