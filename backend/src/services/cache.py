"""In-memory cache layered over the JSON datastore with once-per-day fetching (FR-012).

The Retail Prices API is queried at most once per UTC day per (service, region). Once a snapshot
is saved to JSON, every later request that day is served from that file — no second API call.

Resolution order for a snapshot:
  1. In-memory entry retrieved today -> served, ``is_stale=False``.
  2. On-disk JSON snapshot retrieved today -> loaded and served, ``is_stale=False`` (no API call).
  3. Otherwise a live fetch -> persisted to JSON + cached. If the API is unreachable but an older
     saved snapshot exists, that snapshot is served stale instead of failing.

Exposes the data age so the UI can surface "Prices retrieved N min ago" and flag stale data.

Two scopes are cached:
  * per (service, region) for drill-down (:meth:`get_snapshot`);
  * per region (all services) for the region-first overview (:meth:`get_region_snapshot`), stored
    under the synthetic service label ``_region`` (R9 warm-snapshot strategy).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..config import Settings, get_settings
from ..models.snapshot import PricingSnapshot
from ..models.price_point import NormalizedPrice
from .datastore import JsonDataStore
from .retail_prices import RetailPricesClient, RetailPricesError

# Synthetic service label used to persist a whole-region overview snapshot.
REGION_SCOPE_LABEL = "_region"


@dataclass
class CachedSnapshot:
    snapshot: PricingSnapshot
    data_age_seconds: int
    is_stale: bool


class PricingCache:
    """Once-per-day cache that prefers today's memory entry, then today's saved JSON, then a fetch."""

    def __init__(
        self,
        settings: Settings | None = None,
        datastore: JsonDataStore | None = None,
        client: RetailPricesClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._store = datastore or JsonDataStore(self._settings)
        self._client = client or RetailPricesClient(self._settings)
        self._mem: dict[tuple[str, str], PricingSnapshot] = {}

    @staticmethod
    def _normalize_retrieved(snapshot: PricingSnapshot) -> datetime:
        retrieved = snapshot.retrievedAt
        if retrieved.tzinfo is None:
            retrieved = retrieved.replace(tzinfo=timezone.utc)
        return retrieved.astimezone(timezone.utc)

    def _age_seconds(self, snapshot: PricingSnapshot) -> int:
        retrieved = self._normalize_retrieved(snapshot)
        return max(0, int((datetime.now(timezone.utc) - retrieved).total_seconds()))

    def _retrieved_today(self, snapshot: PricingSnapshot) -> bool:
        """True when the snapshot was fetched earlier on the current UTC day."""
        return self._normalize_retrieved(snapshot).date() == datetime.now(timezone.utc).date()

    def _wrap(self, snapshot: PricingSnapshot) -> CachedSnapshot:
        return CachedSnapshot(
            snapshot=snapshot,
            data_age_seconds=self._age_seconds(snapshot),
            is_stale=not self._retrieved_today(snapshot),
        )

    async def _materialize(
        self,
        *,
        storage_service: str,
        arm_region_name: str,
        currency: str,
        fetch_service_name: str | None,
        force_refresh: bool,
        fetch_product_contains: str | None = None,
    ) -> CachedSnapshot:
        key = (storage_service, arm_region_name)
        fallback: PricingSnapshot | None = None

        if not force_refresh:
            cached = self._mem.get(key)
            if cached and cached.currencyCode == currency:
                if self._retrieved_today(cached):
                    return self._wrap(cached)
                fallback = cached

            on_disk = self._store.read(storage_service, arm_region_name)
            if on_disk and on_disk.currencyCode == currency:
                self._mem[key] = on_disk
                if self._retrieved_today(on_disk):
                    # Already fetched today — serve the saved JSON, skip the API entirely.
                    return self._wrap(on_disk)
                fallback = on_disk

        try:
            records: list[NormalizedPrice] = await self._client.fetch(
                service_name=fetch_service_name,
                arm_region_name=arm_region_name,
                product_name_contains=fetch_product_contains,
                currency_code=currency,
            )
        except RetailPricesError:
            # Upstream unreachable. Reuse the last saved snapshot (served stale) rather than
            # failing, so a transient API outage doesn't wipe out already-persisted prices.
            if fallback is not None:
                return self._wrap(fallback)
            raise

        snapshot = PricingSnapshot(
            serviceName=storage_service,
            armRegionName=arm_region_name,
            currencyCode=currency,
            apiVersion=self._settings.retail_prices_api_version,
            retrievedAt=datetime.now(timezone.utc),
            pricePoints=records,
        )
        self._store.write(snapshot)
        self._mem[key] = snapshot
        return self._wrap(snapshot)

    async def get_snapshot(
        self,
        *,
        service_name: str,
        arm_region_name: str,
        currency_code: str | None = None,
        force_refresh: bool = False,
        fetch_service_name: str | None = None,
        product_contains: str | None = None,
    ) -> CachedSnapshot:
        """Drill-down snapshot for one service in one region.

        ``service_name`` is the cache/storage label. When a service is really a ``productName``
        slice of a broader Retail Prices service (e.g. Azure Files lives under ``Storage``), pass
        ``fetch_service_name`` (the real serviceName to query) and ``product_contains`` (a
        productName substring) so only the relevant meters are fetched and persisted.
        """
        currency = (currency_code or self._settings.default_currency).upper()
        return await self._materialize(
            storage_service=service_name,
            arm_region_name=arm_region_name,
            currency=currency,
            fetch_service_name=fetch_service_name or service_name,
            fetch_product_contains=product_contains,
            force_refresh=force_refresh,
        )

    async def get_region_snapshot(
        self,
        *,
        arm_region_name: str,
        currency_code: str | None = None,
        force_refresh: bool = False,
    ) -> CachedSnapshot:
        """Whole-region snapshot (all services) for the region-first overview (R9)."""
        currency = (currency_code or self._settings.default_currency).upper()
        return await self._materialize(
            storage_service=REGION_SCOPE_LABEL,
            arm_region_name=arm_region_name,
            currency=currency,
            fetch_service_name=None,
            force_refresh=force_refresh,
        )

