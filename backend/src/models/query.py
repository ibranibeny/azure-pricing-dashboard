"""The user's current selection — drives the comparison query and export metadata."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class QueryFilters(BaseModel):
    """Filters for a drill-down pricing query.

    At least one of ``serviceName`` / ``armSkuName`` / ``serviceFamily`` is required so the
    Retail Prices API query is bounded; ``armRegionName`` is always required.
    """

    serviceName: str | None = None
    armSkuName: str | None = None
    serviceFamily: str | None = None
    armRegionName: str
    currencyCode: str = "USD"
    windowsHybridBenefit: bool = False
    sqlHybridBenefit: bool = False

    @model_validator(mode="after")
    def _require_one_service_filter(self) -> "QueryFilters":
        if not (self.serviceName or self.armSkuName or self.serviceFamily):
            raise ValueError(
                "At least one of serviceName, armSkuName, or serviceFamily is required."
            )
        return self
