"""FinOps guidance (US4) — RUNTIME side (FR-011a).

At runtime this module does **two** things and never calls any MCP endpoint:

1. Loads the versioned, pre-grounded ``guidance.json`` artifact shipped inside the image
   (curated at build time by ``backend/tools/curate_guidance.py``).
2. Computes reproducible *numeric* insights (e.g., reserved-instance breakeven / savings) directly
   from the displayed prices.

The guidance text is grounded in Microsoft sources at build time; the runtime only renders it and
the numbers it can reproduce from the on-screen comparison rows.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..models.comparison_row import ComparisonRow

_GUIDANCE_PATH = Path(__file__).resolve().parent.parent / "guidance" / "guidance.json"

# Approximate hours/month for converting an hourly PAYG rate to a monthly figure (730 = 365*24/12).
_HOURS_PER_MONTH = 730


@lru_cache(maxsize=1)
def load_guidance() -> dict:
    """Load the versioned, pre-grounded guidance artifact (no MCP at runtime)."""
    if not _GUIDANCE_PATH.exists():
        return {"version": "none", "grounding": []}
    return json.loads(_GUIDANCE_PATH.read_text(encoding="utf-8"))


def _grounding_text(topic: str) -> str | None:
    for entry in load_guidance().get("grounding", []):
        if entry.get("topic") == topic:
            return entry.get("text")
    return None


def reserved_breakeven_savings(row: ComparisonRow) -> str | None:
    """Reproducible 1-yr RI savings vs PAYG for a single row, or None if not derivable.

    Both prices are compared on an effective-hourly basis (the Retail Prices API reports reservation
    rates per hour for compute SKUs). Returns an end-user sentence with the percentage shown.
    """
    payg = row.payg
    ri = row.reserved1Y
    if not (payg.available and ri.available):
        return None
    if payg.price is None or ri.price is None or payg.price <= 0:
        return None
    if ri.price >= payg.price:
        return None
    pct = round((payg.price - ri.price) / payg.price * 100, 1)
    monthly_saving = round((payg.price - ri.price) * _HOURS_PER_MONTH, 2)
    return (
        f"{row.armSkuName}: a 1-year reservation is ~{pct}% below pay-as-you-go "
        f"(~{monthly_saving} {row.currencyCode}/month for an always-on instance)."
    )


def build_guidance(rows: list[ComparisonRow], *, max_items: int = 3) -> list[str]:
    """Assemble a short, reproducible guidance list for a comparison view."""
    insights: list[str] = []
    intro = _grounding_text("reserved-instance-breakeven")
    if intro:
        insights.append(intro)
    for row in rows:
        sentence = reserved_breakeven_savings(row)
        if sentence:
            insights.append(sentence)
        if len(insights) >= max_items:
            break
    return insights
