"""Reproducible Azure Hybrid Benefit calculation attached to a :class:`ComparisonRow`.

The Retail Prices API does not publish an explicit Hybrid Benefit price, so the eligible price is a
DERIVATION (FR-007a). Every field here is reproducible from ``basePaygPrice`` and the displayed
components (Principle II); when a required counterpart meter is missing, ``eligiblePrice`` is left
unavailable rather than guessed (Principle I).
"""

from __future__ import annotations

from pydantic import BaseModel


class HybridBenefitResult(BaseModel):
    windowsApplied: bool = False
    sqlApplied: bool = False
    windowsEligible: bool = False
    sqlEligible: bool = False
    basePaygPrice: float
    eligiblePrice: float | None = None  # None == "not available" (counterpart meter missing)
    windowsSavings: float = 0.0
    sqlSavings: float = 0.0
    currencyCode: str
