"""Validation (FR-007a): the DERIVED Azure Hybrid Benefit price must match a known reference within
tolerance. If the derivation method drifts, this test fails and blocks the release.

The reference models the documented Windows Hybrid Benefit behavior: applying the benefit removes
the Windows licence component, leaving the Linux-equivalent compute rate for the same SKU/region.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.models.price_point import NormalizedPrice, PurchaseOption
from src.services.hybrid_benefit import compute_hybrid_benefit

RETRIEVED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

# Known reference (illustrative but internally consistent): a Windows VM that costs the Linux rate
# plus a Windows licence component. With AHB, the eligible price equals the Linux rate.
_LINUX_RATE = 0.096
_WINDOWS_LICENSE = 0.092
_WINDOWS_PAYG = _LINUX_RATE + _WINDOWS_LICENSE  # 0.188
_TOLERANCE = 1e-6


def _rows():
    common = dict(
        serviceName="Virtual Machines",
        serviceFamily="Compute",
        armSkuName="Standard_D2s_v5",
        armRegionName="eastus",
        location="US East",
        currencyCode="USD",
        unitOfMeasure="1 Hour",
        purchaseOption=PurchaseOption.PAYG,
        retrievedAt=RETRIEVED,
    )
    linux = NormalizedPrice(
        meterId="lin", skuName="D2s v5", productName="Virtual Machines Dsv5 Series",
        price=_LINUX_RATE, **common,
    )
    windows = NormalizedPrice(
        meterId="win", skuName="D2s v5 Windows",
        productName="Virtual Machines Dsv5 Series Windows", price=_WINDOWS_PAYG, **common,
    )
    return windows, [linux, windows]


def test_derived_windows_ahb_matches_reference_within_tolerance():
    windows, candidates = _rows()
    result = compute_hybrid_benefit(
        base_payg=windows,
        windows_applied=True,
        sql_applied=False,
        candidates=candidates,
    )
    assert result.eligiblePrice is not None
    assert abs(result.eligiblePrice - _LINUX_RATE) <= _TOLERANCE
    assert abs(result.windowsSavings - _WINDOWS_LICENSE) <= _TOLERANCE
