"""Shared constants and the explicit "not available" representation (Principle I, FR-005).

A price/benefit that cannot be sourced from the Azure Retail Prices API is NEVER shown as zero,
blank, or a guess. It is represented by a :class:`PricePoint` whose ``available`` flag is ``False``
and whose ``price`` is ``None``. Exports render it as the token below.
"""

from __future__ import annotations

# Authoritative source string stamped on every response and export (Principle I / IV).
PRICE_SOURCE = "Azure Retail Prices API"

# Token used in CSV/XLSX cells where a value is not available (never zero/blank).
NOT_AVAILABLE_TOKEN = "Not available"
