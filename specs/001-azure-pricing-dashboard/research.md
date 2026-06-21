# Phase 0 Research: Azure Pricing Dashboard

All NEEDS CLARIFICATION items from Technical Context are resolved below. Findings are grounded in
official Microsoft documentation (Microsoft Learn MCP) and the Azure MCP pricing tool.

## R1 — Azure Retail Prices API: pricing dimensions

**Decision**: Use the public Azure Retail Prices API at `https://prices.azure.com/api/retail/prices`,
with the `2023-01-01-preview` API version so savings-plan rates are available alongside reservation rates.

**Key facts (from Microsoft Learn)**:
- Filterable fields include `armRegionName`, `serviceName`, `serviceFamily`, `priceType`, `armSkuName`,
  `skuName`, `productName`, `meterId`.
- `priceType` / `type` values: `Consumption` (pay-as-you-go), `Reservation`, `DevTestConsumption`,
  `SavingsPlanConsumption`.
- `reservationTerm` field carries `1 Year` or `3 Years` for reservation meters.
- `currencyCode` query parameter sets the currency; default is `USD`. Each record carries its own
  `currencyCode`, `unitOfMeasure`, `retailPrice`/`unitPrice`, and `effectiveStartDate`.
- Pagination: max 1,000 records per response; follow `NextPageLink` until null.
- In `2023-01-01-preview` filter values are case-sensitive (e.g., `Virtual Machines`, not `virtual machines`).

**Mapping to the six required dimensions**:
| Dimension | How obtained |
|-----------|--------------|
| Service / SKU | `serviceName` + `armSkuName`/`skuName` filters |
| Region | `armRegionName` filter |
| Pay-as-you-go | records with `type = Consumption` |
| 1-year reserved | `type = Reservation` and `reservationTerm = '1 Year'` |
| 3-year reserved | `type = Reservation` and `reservationTerm = '3 Years'` |
| Azure Hybrid Benefit | derived (see R2) |

**Service coverage (ALL services, not VM-only)**: The Retail Prices API explicitly returns "retail
prices for **all** Azure services" (Microsoft Learn). Services are organized into `serviceFamily`
values; the supported families documented are: Analytics, Azure Arc, Azure Communication Services,
Azure Security, Azure Stack, Compute, Containers, Data, Databases, Developer Tools, Dynamics, Gaming,
Integration, Internet of Things, Management and Governance, Microsoft Syntex, Mixed Reality,
Networking, Other, Power Platform, Quantum Computing, Security, Storage, Telecommunications, Web,
and Windows Virtual Desktop. The concrete `serviceName` list within each family is large and changes
over time, so the dashboard MUST discover services/SKUs/regions dynamically from the API (e.g.,
faceting on `serviceFamily` → `serviceName` → `armSkuName`) rather than hardcoding Virtual Machines or
any fixed subset (FR-001a).

**Applicability of RI / Hybrid Benefit across services**: Pay-as-you-go (`type = Consumption`) exists
for essentially all priced services. Reservations (`type = Reservation`, with `reservationTerm`) and
Azure Hybrid Benefit apply only to a subset (e.g., Virtual Machines, SQL Database/Managed Instance,
Cosmos DB, App Service, and similar). For services/SKUs where the API returns no reservation meter or
no benefit-eligible counterpart, those cells MUST render as "not available" (Principle I), never zero
or blank (FR-002a).

**Rationale**: Single authoritative source satisfies Principle I; preview version is backward-compatible
and adds savings-plan visibility for future FinOps guidance.

**Alternatives considered**: Azure Pricing Calculator (no programmatic contract), hardcoded sheets
(forbidden by Principle I), Cost Management APIs (require auth + a billing account; retail prices are public).

## R2 — Azure Hybrid Benefit modeling (Windows & SQL, independent)

**Decision**: Treat Hybrid Benefit as a derived adjustment computed server-side from Retail Prices data,
never as a separate hardcoded discount.
- **Windows Server**: the eligible (benefit-applied) compute rate equals the equivalent Linux/compute-only
  rate for the same SKU/region; the Windows license component is the difference between the Windows meter
  price and the Linux-equivalent meter price. Savings = Windows PAYG − Linux-equivalent rate.
- **SQL Server**: SQL licensing is metered separately (per vCore). The benefit removes the SQL license
  meter component while keeping the underlying compute. Windows and SQL toggles are independent inputs.

**Reproducibility**: Every savings figure is derived from displayed inputs (base price, term, applied
benefit) and is shown alongside them, satisfying Principle II.

**Rationale**: Keeps numbers traceable to the API and reproducible; avoids opaque discounts.

**Alternatives considered**: Static benefit percentages (not reproducible, drift risk) — rejected.

**Open implementation note (resolved as approach, validated at build time)**: exact SQL meter pairing
varies by product; the `guidance.py`/`hybrid_benefit.py` services will resolve meter pairs from API
results at runtime and fall back to an explicit "not available" state (Principle I) when a counterpart
meter is absent, rather than guessing.

**Accuracy limits & validation (FR-007a)**: because the Retail Prices API does not publish an explicit
Azure Hybrid Benefit price, the benefit price is a **derivation** (Windows: PAYG − Linux-equivalent
rate for the same SKU/region; SQL: remove the SQL license vCore meter). This derivation is an
approximation that can diverge from actual AHB pricing. Mitigations: (1) display the derivation
components alongside the result so the math is transparent (Principle II); (2) validate the method
against at least one known AHB price before release; (3) when a required counterpart meter cannot be
resolved, render "not available" instead of an approximate value (Principle I).

## R3 — FinOps guidance grounding (Microsoft Learn MCP + Azure MCP)

**Decision**: Generate contextual guidance (e.g., reserved-instance breakeven vs PAYG) using text grounded
through the Microsoft Learn MCP and validate pricing context with the Azure MCP pricing tool (which itself
wraps the Retail Prices API; supports `Currency` default `USD`, `SKU`, `Service`, `Region`, `ServiceFamily`,
`PriceType`, and "include savings plan").

**Runtime boundary (FR-011a)**: MCP grounding happens at **build/curation time**, not from the deployed
container. A curation step captures grounded guidance text + source references into a versioned artifact
(e.g., `backend/src/guidance/guidance.json`) that ships inside the image. At runtime, the app computes
only reproducible numeric insights (breakeven, savings) from the displayed prices and renders the
pre-grounded text — it never calls MCP endpoints from Azure Container Instance. This avoids a runtime
dependency on agent/dev-time tooling and keeps the deployed surface self-contained.

**Rationale**: Satisfies Principle II's requirement that guidance be grounded in current Microsoft sources
and validated against Azure data, while keeping the deployed runtime free of MCP reachability assumptions.

**Alternatives considered**: Live MCP calls from the container (MCP is not a deployed runtime dependency;
reachability + latency risk) and model-authored guidance without grounding (authority/accuracy risk) —
both rejected.

## R4 — Frontend approach (HTML5, mobile-adaptive, no SPA) + frontend-design skill

**Decision**: Vanilla HTML5 + modern CSS (flex/grid, container/media queries) + ES2022 modules. Pricing
grid uses a responsive layout with sticky headers and a horizontal-scroll container fallback so it stays
readable at a 360px viewport. The visual design follows the **`frontend-design` skill**
(anthropics/skills) — a deliberate, opinionated identity rather than a templated default.

**Applying the skill's two-pass process** (brainstorm a token system → critique against the brief →
build): the subject is a *financial decision tool for Azure cost/FinOps*; audience is cloud cost
analysts and licensing buyers; the page's single job is *compare Azure prices across purchase options
and export with confidence*. The skill explicitly warns away from the three AI-default looks (cream +
serif + terracotta; near-black + acid accent; broadsheet hairline columns) — so the design avoids those.

**Design token plan (v1, to be refined during build with self-critique)**:
- **Palette (4–6 named hex)** — a precise, trustworthy "instrument panel" direction, not Azure-marketing
  blue-by-default:
  - `--ink: #0B1221` (near-navy text/ground), `--surface: #F7F9FC` (cool paper), `--line: #C9D4E3`
    (hairline borders/grid), `--accent: #1F6FEB` (interactive/links, used with restraint),
    `--positive: #1B998B` (savings/benefit emphasis), `--warn: #C2410C` (stale-data / "not available" flags).
- **Type (2+ roles)** — display face with character used sparingly for headline KPIs (e.g., a grotesk
  like *Space Grotesk*), a highly legible body/UI face (*Inter*), and a **tabular/monospace face for
  numbers** (e.g., *IBM Plex Mono* or a tabular-figures setting) so prices align in columns — the data
  legibility is itself a design statement appropriate to a pricing tool.
- **Layout** — controls rail (service/region/Hybrid Benefit toggles) + a dense, sticky-header comparison
  grid as the hero; the *numbers themselves* are the hero, not decorative chrome.
- **Signature** — the per-row "savings ledger": PAYG vs 1-yr vs 3-yr with a reproducible, inline
  breakdown of Windows/SQL Hybrid Benefit savings, presented as a compact, tabular "receipt" that makes
  the math visible (ties directly to Principles I, II, IV).

**Quality floor (from the skill)**: responsive down to mobile (360px, no horizontal scroll), visible
keyboard focus, `prefers-reduced-motion` respected, restrained motion (no gratuitous animation), and
end-user-oriented copy (e.g., "Not available in this region", "Prices retrieved 3 min ago"). CSS selector
specificity managed to avoid section padding/margin conflicts.

**Rationale**: Principle III mandates mobile-adaptive HTML5 and discourages heavyweight SPA frameworks
without justification; the UI is read-mostly (select → render table → export), which does not justify a
SPA. The `frontend-design` skill ensures the result is distinctive and intentional, not a generic dashboard.

**Alternatives considered**: React/Vue SPA — rejected (unjustified weight per Principle III); the three
AI-default aesthetics — rejected per the skill's guidance to spend free axes on deliberate choices.

## R5 — TLS: Let's Encrypt DNS-01 on Cloudflare in a container

**Decision**: Front the app with Caddy 2 built with the Cloudflare DNS module. Caddy performs the ACME
DNS-01 challenge using a Cloudflare API token, auto-renews certificates, serves HTTPS, and redirects HTTP→HTTPS
automatically. Caddy's certificate/state directory is persisted on a mounted Azure Files share to survive
container restarts and avoid Let's Encrypt rate limits.

**Rationale**: DNS-01 avoids needing inbound port-80 reachability during issuance and is the cleanest
container-native path; Caddy gives auto-renew + HTTP→HTTPS redirect out of the box (Principle V).

**Alternatives considered**: certbot sidecar with cron (more moving parts), Azure Front Door/App Gateway
managed certs (extra cost/complexity, and the requirement is explicitly Let's Encrypt + Cloudflare) — rejected.

## R6 — Hosting & deployment (Azure Container Instance via WSL Azure CLI)

**Decision**: Deploy a multi-container ACI **container group**: a Caddy container (public, ports 80/443) and
the FastAPI app container (internal, port 8000) sharing the group's network namespace. An Azure Files share
is mounted into the Caddy container for cert persistence. The image is built and pushed (Azure Container
Registry), then deployed with a re-runnable `deploy/deploy.sh` using `az login` + `az container create`
executed from WSL. Secrets (Cloudflare token, any API keys) are passed as ACI **secure environment variables**,
never committed.

**Rationale**: Satisfies Principle V — versioned image, reproducible scripted deploy from WSL, externalized
secrets, single-region ACI as assumed in the spec.

**Alternatives considered**: Azure Container Apps / AKS (heavier than the single-region requirement),
manual portal deploy (violates reproducibility) — rejected.

## R7 — Export integrity (CSV + XLSX)

**Decision**: Generate exports server-side from the exact materialized comparison rows that produced the
on-screen view (passed back / recomputed deterministically), so screen and file cannot diverge. CSV via the
Python `csv` stdlib; XLSX via `openpyxl`. Both include a metadata block/sheet recording source = Azure Retail
Prices API, retrieval timestamp, and applied filters. Numeric values are written without value-changing
re-rounding.

**Rationale**: Principle IV requires lossless parity and metadata; server-side generation from the same row
set guarantees it.

**Alternatives considered**: Client-side export from DOM (fragile, formatting drift) — rejected.

## R8 — VM detail across all regions, and JSON file persistence

**Decision (VM/region detail)**: For Virtual Machines, query the Retail Prices API per region using the
`armRegionName` filter (combined with `serviceName eq 'Virtual Machines'`) and capture full per-SKU
detail: `armSkuName` (VM size), `skuName`, `productName` (series + OS), `unitOfMeasure`, and the three
purchase options (PAYG / 1-yr RI / 3-yr RI). Because the available SKUs and their prices differ by
region, the dataset is materialized per (service, region) and the same VM size is made comparable across
regions. Regions are enumerated dynamically from the API (distinct `armRegionName`/`location` values),
not hardcoded, so new regions are picked up automatically. Pagination (`NextPageLink`, 1,000/page) is
followed to completion so no region's SKUs are truncated.

**Decision (JSON persistence)**: Persist each retrieved dataset as a JSON file on disk under
`data/pricing/` (e.g., `virtual-machines_eastus.json`), each file carrying `source`, `retrievedAt`,
the applied filters, and the raw/normalized rows. A `datastore.py` service reads from and writes to
these JSON files; an in-memory TTL cache layers over them for hot reads. The dashboard can serve from a
stored snapshot between refreshes and shows the snapshot's age + staleness flag (Principle I). In ACI,
`data/pricing/` lives on a mounted Azure Files share so snapshots persist across restarts.

**Rationale**: Satisfies FR-002b (full VM/region detail) and FR-012a (JSON file storage); per-(service,
region) JSON keeps files bounded and refreshable, and keeps the app responsive without a database.

**Alternatives considered**: One giant JSON blob for all services/regions (unwieldy, slow partial
refresh) — rejected in favor of per-(service, region) files; a relational DB (heavier than needed for a
read-mostly snapshot tool) — rejected.

## R9 — Region-first overview (all services) and drill-down (US1)

**Decision**: The landing experience is region-first, not service-first. The user picks a region and
the backend returns **every** Azure service available in that region as a `ServiceSummary` (one per
distinct `serviceName`), aggregated from the region's `PricePoint`s. For each service the summary
carries: `skuCount`, a `representativePrice` = the lowest available PAYG `retailPrice` among that
service's SKUs in the region (clearly labelled as a "from" preview price, not a quote), the unit of that
price, and honest `reserved1YAvailable` / `reserved3YAvailable` / `hybridBenefitEligible` flags computed
from whether real RI/AHB rows exist for the service in that region. Clicking a service drills down via
`GET /api/pricing` to the SKU-level `ComparisonRow`s (PAYG / 1-yr RI / 3-yr RI) for that service+region.

**Rationale**: Matches the requested UX (FR-001/FR-001b): list all services by region with cost and RI
feasibility, then expand a service (e.g., VM) into its SKUs. Aggregating from already-materialized
per-(service, region) rows (R8) keeps the overview cheap and reuses the same honest, API-sourced data —
no fabricated or estimated rollups. Missing PAYG for a service surfaces as `NotAvailable`, never zero.

**Alternatives considered**: Averaging SKU prices for the representative figure (misleading, hides the
cheapest option) — rejected in favor of an explicit lowest-available "from" price; computing the overview
on the client (would require shipping all SKU rows for all services up front, heavy on mobile) — rejected
in favor of a server-side aggregate endpoint.

**Performance (overview prefetch)**: The region overview aggregates many services (potentially many API
pages) for one region, so it MUST be served from a warm per-region snapshot to meet the < 2 s goal. A
background refresh materializes per-(service, region) JSON snapshots (R8); the overview endpoint reads
the aggregated `ServiceSummary` list from those snapshots/cache rather than fanning out live Retail
Prices API calls per request. A cold region (no snapshot yet) fetches on demand and is flagged as
freshly retrieved; subsequent reads are warm.

## Resolved unknowns summary

| Unknown | Resolution |
|---------|------------|
| Pricing source & dimension mapping | Retail Prices API `2023-01-01-preview` (R1) |
| Hybrid Benefit math (Win/SQL) | Derived, reproducible, independent toggles (R2) |
| FinOps guidance grounding | Microsoft Learn MCP + Azure MCP (R3) |
| Frontend stack | Vanilla HTML5/CSS/JS, no SPA (R4) |
| TLS / Let's Encrypt DNS-01 | Caddy + Cloudflare DNS module, Azure Files cert persistence (R5) |
| Hosting & deploy tooling | ACI container group, WSL `az` script, secure env vars (R6) |
| Export generation | Server-side from materialized rows; csv + openpyxl (R7) |
| VM/region detail & JSON persistence | Per-region VM SKU detail; per-(service,region) JSON files on Azure Files (R8) |
| Region-first overview + drill-down | All-services `ServiceSummary` per region; lowest-PAYG "from" price; drill into SKUs (R9) |
