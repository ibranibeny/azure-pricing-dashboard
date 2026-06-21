"""Unit: missing purchase options render as explicit 'not available', never 0/blank (FR-002a, FR-005)."""

from __future__ import annotations

from datetime import datetime, timezone

from src.models.price_point import PricePoint, PurchaseOption
from src.services.pricing import assemble_rows
from tests.conftest import _vm_rows

RETRIEVED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_not_available_cell_has_no_price():
    cell = PricePoint.not_available(PurchaseOption.RI_1Y, "USD", RETRIEVED, "1 Hour")
    assert cell.available is False
    assert cell.price is None
    assert cell.currencyCode == "USD"
    assert cell.reservationTerm == "1 Year"


def test_sku_without_reservation_is_not_available():
    rows = assemble_rows(_vm_rows(), currency="USD", retrieved_at=RETRIEVED)
    by_sku = {r.armSkuName: r for r in rows}

    d2 = by_sku["Standard_D2s_v5"]
    assert d2.payg.available is True
    assert d2.payg.price == 0.096
    # No reservation rows in the fixture for this SKU.
    assert d2.reserved1Y.available is False
    assert d2.reserved1Y.price is None
    assert d2.reserved3Y.available is False
    assert d2.reserved3Y.price is None


def test_sku_with_reservation_keeps_real_prices():
    rows = assemble_rows(_vm_rows(), currency="USD", retrieved_at=RETRIEVED)
    by_sku = {r.armSkuName: r for r in rows}

    b1s = by_sku["Standard_B1s"]
    assert b1s.payg.available and b1s.payg.price == 0.0104  # cheapest PAYG (Linux) wins
    assert b1s.reserved1Y.available and b1s.reserved1Y.price == 0.0072
    assert b1s.reserved3Y.available and b1s.reserved3Y.price == 0.0050
