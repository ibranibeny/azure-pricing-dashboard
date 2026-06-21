# Phase 1 Data Model: Azure Pricing Dashboard

Derived from the spec's Key Entities and functional requirements. No database — these are in-memory /
transfer models (Pydantic on the backend, JSON to the frontend). All monetary values keep their own
currency code and never appear without unit + retrieval timestamp (Principle I).

## Entity: PricePoint

A single retrieved price for one SKU/region/purchase option.

| Field | Type | Notes / Validation |
|-------|------|--------------------|
| `meterId` | string | From Retail Prices API; unique meter identifier |
| `serviceName` | string | e.g., "Virtual Machines" |
| `serviceFamily` | string | e.g., "Compute" |
| `armSkuName` | string | e.g., "Standard_D4s_v5" |
| `skuName` | string | e.g., "D4s v5" |
| `productName` | string | e.g., "Virtual Machines Dsv5 Series Windows" |
| `armRegionName` | string | e.g., "eastus" |
| `location` | string | Human-readable region (e.g., "US East") |
| `purchaseOption` | enum | `PAYG` \| `RI_1Y` \| `RI_3Y` |
| `price` | decimal | `retailPrice`; never re-rounded for storage |
| `currencyCode` | string | Required; default view USD but each price keeps its own |
| `unitOfMeasure` | string | e.g., "1 Hour"; required |
| `reservationTerm` | string? | "1 Year" / "3 Years" for RI rows; null for PAYG |
| `retrievedAt` | datetime (UTC) | When fetched from the API; required |
| `effectiveStartDate` | datetime? | From API when present |

**Rules**: A `PricePoint` is only created from API data. If the API has no value for a requested
purchase option, no fabricated `PricePoint` is created — the absence is rendered as "not available".

**Service scope**: `serviceName`/`serviceFamily`/`armSkuName` are not limited to Virtual Machines.
The model represents any Azure service the Retail Prices API returns across all service families;
selection lists are populated dynamically from the API (FR-001a). Reserved-instance and Hybrid Benefit
fields are populated only when the API offers them for that service/SKU; otherwise they are
`NotAvailable` (FR-002a).

## Entity: ServiceSummary

One Azure service as it appears in the **region-first overview** (US1 landing view): the user picks a
region and sees every service available there before drilling into any SKUs. Aggregated from the
region's `PricePoint`s; the `representativePrice` is the lowest available PAYG price among the
service's SKUs in that region and is used only for preview/ranking — exact prices come from drill-down.

| Field | Type | Notes / Validation |
|-------|------|--------------------|
| `serviceName` | string | e.g., "Virtual Machines" |
| `serviceFamily` | string | e.g., "Compute" |
| `armRegionName` | string | the region being browsed |
| `skuCount` | integer | number of SKUs for this service in the region |
| `representativePrice` | decimal \| `NotAvailable` | lowest available PAYG price in region (labelled) |
| `representativeUnit` | string? | unit of the representative price |
| `currencyCode` | string | default view USD; each value keeps its own code |
| `reserved1YAvailable` | boolean | whether any SKU has a 1-yr RI price in this region |
| `reserved3YAvailable` | boolean | whether any SKU has a 3-yr RI price in this region |
| `hybridBenefitEligible` | boolean | whether the service is AHB-eligible (e.g., VMs, SQL) |
| `retrievedAt` | datetime (UTC) | oldest retrievedAt among aggregated price points |

**Rules**: A `ServiceSummary` is only built from real `PricePoint`s returned by the Retail Prices API
for the region (FR-001, FR-004). When a service has no PAYG price in the region, `representativePrice`
is `NotAvailable` (never zero/blank). RI/Hybrid availability flags are computed from actual API rows,
not assumed — they advertise drill-down value honestly (FR-001b, FR-005).

## Entity: ComparisonRow

One row of the on-screen comparison: a SKU in a region with its three purchase options and any applied
Hybrid Benefit results. This is the unit that is both rendered and exported (guarantees screen↔export parity).

| Field | Type | Notes |
|-------|------|-------|
| `serviceName` | string | |
| `armSkuName` | string | |
| `armRegionName` | string | |
| `location` | string | |
| `unitOfMeasure` | string | |
| `currencyCode` | string | |
| `payg` | PricePoint \| `NotAvailable` | |
| `reserved1Y` | PricePoint \| `NotAvailable` | |
| `reserved3Y` | PricePoint \| `NotAvailable` | |
| `hybridBenefit` | HybridBenefitResult? | present when a benefit toggle is on and SKU is eligible |
| `retrievedAt` | datetime (UTC) | oldest retrievedAt among contained price points |
| `dataAgeSeconds` | integer | derived; drives staleness flag |
| `isStale` | boolean | true when `dataAgeSeconds` > cache TTL |

**States**: each price cell is either a populated `PricePoint` or the sentinel `NotAvailable`
(never zero/blank). `isStale` surfaces cache age (Principle I).

## Entity: HybridBenefitResult

Reproducible benefit calculation attached to a `ComparisonRow`.

| Field | Type | Notes |
|-------|------|-------|
| `windowsApplied` | boolean | Windows Server benefit toggle state |
| `sqlApplied` | boolean | SQL Server benefit toggle state (independent of Windows) |
| `windowsEligible` | boolean | whether SKU qualifies for Windows benefit |
| `sqlEligible` | boolean | whether SKU qualifies for SQL benefit |
| `basePaygPrice` | decimal | the PAYG price the savings is measured against |
| `eligiblePrice` | decimal \| `NotAvailable` | price after applicable benefits |
| `windowsSavings` | decimal | 0 when not applied/eligible; reproducible from base − Linux-equivalent |
| `sqlSavings` | decimal | 0 when not applied/eligible; reproducible from removed SQL license meter |
| `currencyCode` | string | matches the row |

**Rules (Principle II)**: `eligiblePrice` and each savings figure MUST be derivable from
`basePaygPrice` and the displayed components; Windows and SQL contributions are computed and shown
separately. When a counterpart meter needed for the calculation is missing, `eligiblePrice` is
`NotAvailable` rather than guessed.

## Entity: QueryFilters

The user's current selection — drives both the comparison and the export metadata.

| Field | Type | Notes |
|-------|------|-------|
| `serviceName` | string? | at least one of service/skuName/serviceFamily required |
| `armSkuName` | string? | |
| `serviceFamily` | string? | |
| `armRegionName` | string | required |
| `currencyCode` | string | default `USD` |
| `windowsHybridBenefit` | boolean | default false |
| `sqlHybridBenefit` | boolean | default false |

## Entity: ExportRecord

The materialized payload used to generate CSV/XLSX — identical to what was rendered.

| Field | Type | Notes |
|-------|------|-------|
| `rows` | ComparisonRow[] | exact rows shown on screen |
| `filters` | QueryFilters | applied filters (written to metadata) |
| `source` | string | constant: "Azure Retail Prices API" |
| `retrievedAt` | datetime (UTC) | data retrieval timestamp |
| `generatedAt` | datetime (UTC) | when the export file was created |
| `format` | enum | `csv` \| `xlsx` |

**Rules (Principle IV)**: the exporter writes `rows` verbatim (no value-changing reformatting) and
emits a metadata header (CSV) or dedicated metadata sheet (XLSX) carrying `source`, `retrievedAt`,
`generatedAt`, and `filters`.

## Entity: PricingSnapshot

The persisted JSON dataset for one (service, region) scope. Serves the dashboard from a stored snapshot
between refreshes (FR-012a) and is the on-disk backing for the in-memory cache.

| Field | Type | Notes |
|-------|------|-------|
| `serviceName` | string | scope key (e.g., "Virtual Machines") |
| `armRegionName` | string | scope key (e.g., "eastus") — SKUs/prices differ per region |
| `currencyCode` | string | currency the snapshot was fetched in (default USD) |
| `source` | string | constant: "Azure Retail Prices API" |
| `apiVersion` | string | e.g., "2023-01-01-preview" |
| `retrievedAt` | datetime (UTC) | when the snapshot was fetched |
| `pricePoints` | PricePoint[] | all SKUs/purchase options for the scope (paginated to completion) |

**Persistence (FR-012a)**: stored as a JSON file at `data/pricing/{service}_{region}.json` (slugified),
on a mounted Azure Files share in ACI. Reads prefer the in-memory cache, fall back to the JSON file, and
refresh from the API when the snapshot age exceeds the cache TTL. For Virtual Machines, snapshots are
captured for every region the API exposes so the same VM size is comparable across regions (FR-002b).

## Sentinel: NotAvailable

A typed sentinel (serialized as `null` + an explicit `"available": false` flag, or a string token
`"N/A"` in exports) used wherever a price/benefit cannot be sourced from the API. Guarantees the UI and
exports never present a fabricated value (Principle I).

## Relationships

```text
QueryFilters ──drives──▶ [Retail Prices API fetch] ──▶ PricePoint[]
PricePoint[] ──persisted as──▶ PricingSnapshot (JSON file per service+region) ──cached──▶ in-memory TTL cache
PricePoint[] ──assembled into──▶ ComparisonRow (payg / reserved1Y / reserved3Y)
ComparisonRow ──optional──▶ HybridBenefitResult (when toggles on & eligible)
ComparisonRow[] + QueryFilters ──materialized into──▶ ExportRecord ──▶ CSV / XLSX
```
