"""Pydantic models for prices.

Two complementary shapes:

* :class:`NormalizedPrice` — one rich, raw row as returned by the Azure Retail Prices API
  (all fields we care about), used internally and persisted in snapshots.
* :class:`PricePoint` — the contract-facing per-cell summary for a single purchase option
  (PAYG / 1-yr RI / 3-yr RI), carrying the explicit ``available`` flag (FR-005). This is what the
  frontend and exports consume; every price keeps its currency, unit, and retrieval timestamp
  (Principle I, FR-003).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PurchaseOption(str, Enum):
    """The three purchase options compared by the dashboard."""

    PAYG = "PAYG"
    RI_1Y = "RI_1Y"
    RI_3Y = "RI_3Y"


# Azure Retail Prices API ``type`` values mapped to our purchase options.
RESERVATION_TERM_1Y = "1 Year"
RESERVATION_TERM_3Y = "3 Years"


class NormalizedPrice(BaseModel):
    """A single normalized row from the Azure Retail Prices API."""

    meterId: str = ""
    serviceName: str
    serviceFamily: str = ""
    armSkuName: str = ""
    skuName: str = ""
    productName: str = ""
    armRegionName: str = ""
    location: str = ""
    purchaseOption: PurchaseOption
    price: float
    currencyCode: str
    unitOfMeasure: str = ""
    reservationTerm: str | None = None
    retrievedAt: datetime
    effectiveStartDate: datetime | None = None


class PricePoint(BaseModel):
    """Contract-facing price for one purchase option of one SKU.

    ``available`` is ``False`` and ``price`` is ``None`` when the API offers no value for this
    option/region (rendered as an explicit "not available" state, never zero/blank — FR-005).
    """

    available: bool
    purchaseOption: PurchaseOption
    price: float | None = None
    currencyCode: str
    unitOfMeasure: str = ""
    reservationTerm: str | None = None
    retrievedAt: datetime

    @classmethod
    def from_normalized(cls, record: NormalizedPrice) -> "PricePoint":
        return cls(
            available=True,
            purchaseOption=record.purchaseOption,
            price=record.price,
            currencyCode=record.currencyCode,
            unitOfMeasure=record.unitOfMeasure,
            reservationTerm=record.reservationTerm,
            retrievedAt=record.retrievedAt,
        )

    @classmethod
    def not_available(
        cls,
        option: PurchaseOption,
        currency: str,
        retrieved_at: datetime,
        unit: str = "",
    ) -> "PricePoint":
        """Build the explicit "not available" cell for a missing purchase option (FR-005)."""
        term = None
        if option is PurchaseOption.RI_1Y:
            term = RESERVATION_TERM_1Y
        elif option is PurchaseOption.RI_3Y:
            term = RESERVATION_TERM_3Y
        return cls(
            available=False,
            purchaseOption=option,
            price=None,
            currencyCode=currency,
            unitOfMeasure=unit,
            reservationTerm=term,
            retrievedAt=retrieved_at,
        )
