"""Shared API dependencies (singletons wired once per process)."""

from __future__ import annotations

from functools import lru_cache

from ..services.cache import PricingCache
from ..services.catalog import CatalogService


@lru_cache(maxsize=1)
def get_cache() -> PricingCache:
    return PricingCache()


@lru_cache(maxsize=1)
def get_catalog() -> CatalogService:
    return CatalogService(get_cache())
