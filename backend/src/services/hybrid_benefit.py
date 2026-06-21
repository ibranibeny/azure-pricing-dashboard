"""Azure Hybrid Benefit derivation (US2) — Windows Server and SQL Server, independent toggles.

The Retail Prices API publishes no explicit Hybrid Benefit price, so the eligible price is DERIVED
(FR-007a):

* **Windows**: the benefit removes the Windows license component, leaving the Linux-equivalent
  compute rate for the same SKU/region. ``windowsSavings = windows_payg - linux_equivalent``.
* **SQL**: the benefit removes the separately-metered SQL license vCore component.
  ``sqlSavings = sql_license_component``.

Every figure is reproducible from ``basePaygPrice`` and the displayed components (Principle II).
When a required counterpart meter cannot be resolved, ``eligiblePrice`` is left ``None`` — rendered
as "not available" rather than guessed (Principle I, FR-007a).
"""

from __future__ import annotations

from ..models.hybrid_benefit import HybridBenefitResult
from ..models.price_point import NormalizedPrice, PurchaseOption

_WINDOWS_MARKERS = ("windows",)
_SQL_MARKERS = ("sql",)


def _is_windows(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in _WINDOWS_MARKERS)


def _is_sql(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in _SQL_MARKERS)


def find_linux_equivalent(
    sku: NormalizedPrice, candidates: list[NormalizedPrice]
) -> NormalizedPrice | None:
    """Find the Linux/compute-only PAYG counterpart for the same SKU/region."""
    for cand in candidates:
        if (
            cand.purchaseOption is PurchaseOption.PAYG
            and cand.armSkuName == sku.armSkuName
            and cand.armRegionName == sku.armRegionName
            and not _is_windows(cand.productName)
            and not _is_windows(cand.skuName)
        ):
            return cand
    return None


def compute_hybrid_benefit(
    *,
    base_payg: NormalizedPrice,
    windows_applied: bool,
    sql_applied: bool,
    candidates: list[NormalizedPrice],
    sql_license_component: float | None = None,
) -> HybridBenefitResult:
    """Compute a reproducible Hybrid Benefit result for one SKU's PAYG price."""
    currency = base_payg.currencyCode
    windows_eligible = _is_windows(base_payg.productName) or _is_windows(base_payg.skuName)
    sql_eligible = _is_sql(base_payg.productName) or _is_sql(base_payg.skuName)

    eligible_price: float | None = base_payg.price
    windows_savings = 0.0
    sql_savings = 0.0
    resolvable = True

    if windows_applied and windows_eligible:
        linux = find_linux_equivalent(base_payg, candidates)
        if linux is not None:
            windows_savings = max(0.0, base_payg.price - linux.price)
            eligible_price = (eligible_price or base_payg.price) - windows_savings
        else:
            resolvable = False  # counterpart meter missing -> not available

    if sql_applied and sql_eligible:
        if sql_license_component is not None:
            sql_savings = max(0.0, sql_license_component)
            eligible_price = (eligible_price or base_payg.price) - sql_savings
        else:
            resolvable = False  # SQL license meter not resolvable -> not available

    if not resolvable:
        eligible_price = None

    return HybridBenefitResult(
        windowsApplied=windows_applied,
        sqlApplied=sql_applied,
        windowsEligible=windows_eligible,
        sqlEligible=sql_eligible,
        basePaygPrice=base_payg.price,
        eligiblePrice=eligible_price,
        windowsSavings=windows_savings,
        sqlSavings=sql_savings,
        currencyCode=currency,
    )
