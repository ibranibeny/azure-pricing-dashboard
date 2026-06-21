# Feature Specification: Azure Pricing Dashboard

**Feature Branch**: `001-azure-pricing-dashboard`

**Created**: 2026-06-21

**Status**: Draft

**Input**: User description: "Azure pricing dashboard showing services, region, pay-as-you-go, 1-year reserved instance, 3-year reserved instance, and Azure Hybrid Benefit (Windows + SQL); grounded in Microsoft Learn MCP (best practice / FinOps), Azure MCP, and the Azure Retail Prices API; HTML5 mobile-adaptive frontend; export to XLS and CSV; HTTPS via Let's Encrypt (DNS-01 on Cloudflare); deployed to Azure Container Instance using Azure CLI from WSL."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse all services by region, then drill into SKUs (Priority: P1)

A cloud cost analyst picks a region and immediately sees a list of **all** Azure services available in
that region, each with its cost and — where feasible — 1-year and 3-year reserved-instance pricing. The
user does not pre-select a service. Clicking a service (e.g., Virtual Machines) drills down into that
service's list of SKUs (e.g., VM sizes), each with pay-as-you-go, 1-year RI, and 3-year RI prices. All
values come straight from the Azure Retail Prices API — nothing is fabricated.

**Why this priority**: This region-first browse-then-drill experience is the core of the dashboard.
Without it, no other feature delivers value. It is the minimum viable product.

**Independent Test**: Pick a region; verify a list of all services in that region appears, each with a
representative cost and RI indicators where applicable; click Virtual Machines and verify the SKU list
appears with PAYG / 1-yr RI / 3-yr RI prices that match the official Azure Retail Prices API for that
region, each labelled with currency, unit, and retrieval timestamp.

**Acceptance Scenarios**:

1. **Given** the dashboard is open, **When** the user selects a region, **Then** a list of all Azure
   services available in that region is shown, each with a representative price and an indication of
   whether 1-year / 3-year reserved instances are available for that service.
2. **Given** the region service list, **When** the user clicks a service (e.g., Virtual Machines),
   **Then** the service's SKUs are listed, each with PAYG, 1-year RI, and 3-year RI prices plus
   currency, unit, and retrieval timestamp.
3. **Given** a service or SKU where a reserved-instance price is not published, **When** it is shown,
   **Then** the RI cell shows an explicit "not available" state (never zero, blank, or a guess).
4. **Given** displayed prices, **When** the underlying data was served from a stored snapshot/cache,
   **Then** the age of the data is visible and stale data is flagged.

---

### User Story 2 - Apply Azure Hybrid Benefit (Windows & SQL) (Priority: P2)

A licensing-aware buyer toggles Azure Hybrid Benefit for Windows Server and, separately, for SQL
Server, and sees the resulting eligible prices and the savings versus PAYG, with the calculation
reproducible from the displayed inputs.

**Why this priority**: Hybrid Benefit materially changes total cost for customers with existing
licenses and is a primary FinOps lever, but it builds on the core comparison (P1).

**Independent Test**: For a Windows VM SKU, toggle Hybrid Benefit (Windows) on; verify the eligible
price and the displayed savings equal base price minus the Windows license component, and that the
SQL toggle is independent and does not affect a non-SQL workload.

**Acceptance Scenarios**:

1. **Given** a Windows-based service, **When** the user enables Azure Hybrid Benefit for Windows
   Server, **Then** the eligible price and a reproducible savings figure (relative to PAYG) are shown.
2. **Given** a SQL-based service, **When** the user enables Azure Hybrid Benefit for SQL Server,
   **Then** the SQL benefit is applied independently of the Windows toggle.
3. **Given** any displayed savings, **When** the user inspects it, **Then** the figure is derivable
   from the shown base price, term, and applied benefit (no opaque numbers).

---

### User Story 3 - Export current view to CSV and XLSX (Priority: P2)

A user who has filtered the dashboard to a specific service/region/benefit context exports the
exact data on screen to a CSV file and to an XLSX file for use in budgets and procurement.

**Why this priority**: Exports feed downstream financial work and are explicitly required, but they
depend on having correct on-screen data first (P1).

**Independent Test**: Filter the dashboard, export to CSV and to XLSX, and verify both files contain
the same rows and numeric values as the screen, with a metadata header/sheet recording source,
retrieval timestamp, and applied filters.

**Acceptance Scenarios**:

1. **Given** a filtered pricing view, **When** the user exports to CSV, **Then** the file contains
   the same rows, values, currency, unit, region, term, and Hybrid Benefit context shown on screen.
2. **Given** a filtered pricing view, **When** the user exports to XLSX, **Then** the file is a
   lossless representation of the screen and includes a metadata header/sheet (source = Azure Retail
   Prices API, retrieval timestamp, applied filters).
3. **Given** an export, **When** values are written, **Then** no number is re-rounded or reformatted
   in a way that changes its value relative to the on-screen data.

---

### User Story 4 - FinOps guidance grounded in official sources (Priority: P3)

A user reviewing a comparison sees contextual best-practice / FinOps guidance (e.g., when a reserved
instance breaks even versus PAYG) that is grounded in current Microsoft guidance.

**Why this priority**: Guidance increases the dashboard's decision-making value but is additive on
top of accurate pricing and benefit calculations.

**Independent Test**: For a SKU where a 1-year RI breaks even before 12 months of PAYG, verify the
dashboard surfaces a grounded recommendation and that the breakeven is reproducible from shown prices.

**Acceptance Scenarios**:

1. **Given** a comparison with reserved-instance prices, **When** guidance is shown, **Then** it is
   consistent with current Microsoft best-practice / FinOps guidance and reproducible from displayed
   inputs.

---

### Edge Cases

- A SKU exists for PAYG but has no 1-year or 3-year reserved price in the selected region → show
  "not available" for the missing terms.
- Selected service is not available in the selected region → show an empty-but-explained state.
- The Azure Retail Prices API is unreachable or rate-limited → show a clear error/stale-data state;
  never display fabricated prices.
- A service is ineligible for Hybrid Benefit (e.g., Linux, non-SQL) → the relevant toggle has no
  effect and this is communicated.
- Very large result sets (a service with many SKUs) → results remain readable and exportable on
  mobile and desktop.
- Currency differs by region/billing account → each price retains its own currency code; no mixing
  into a single unlabelled total.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST present a region-first overview: when the user selects a region, the system
  MUST list **all** Azure services available in that region (no pre-selection of a service), each with
  a representative cost (the lowest available pay-as-you-go price among that service's SKUs in the
  region, explicitly labelled as a "from" preview price) and an indicator of whether 1-year / 3-year
  reserved-instance pricing is available for that service. The region overview is a navigational
  preview, not the full six-dimension comparison; the six pricing dimensions are guaranteed in the
  drill-down view (FR-001b).
- **FR-001b**: System MUST support drill-down: clicking a listed service (e.g., Virtual Machines)
  MUST display that service's individual SKUs, each with pay-as-you-go, 1-year RI, and 3-year RI prices
  (or an explicit "not available" state per FR-005).
- **FR-001a**: System MUST support the full breadth of Azure services exposed by the Azure Retail
  Prices API across all service families (e.g., Compute, Storage, Databases, Networking, Containers,
  Analytics, AI, Web, Integration, IoT, Security, Management and Governance, and others) — the catalog
  MUST NOT be limited to Virtual Machines or any hardcoded subset, and service/SKU/region choices MUST
  be discovered dynamically from the API so coverage tracks the API automatically.
- **FR-002**: System MUST display, for matching SKUs, pay-as-you-go, 1-year reserved instance, and
  3-year reserved instance prices.
- **FR-002a**: System MUST render 1-year and 3-year reserved-instance and Azure Hybrid Benefit values
  as "not available" for services/SKUs where the Retail Prices API does not offer them (these options
  apply only to a subset of services, e.g., VMs and SQL), while still showing pay-as-you-go for any
  service that has it.
- **FR-002b**: For Virtual Machines, the system MUST provide detailed per-SKU pricing (e.g., VM size /
  `armSkuName`, OS/series, unit of measure) and MUST cover all Azure regions returned by the Retail
  Prices API, recognizing that the available SKUs and their prices differ from region to region; the
  same VM size MUST be comparable across regions.
- **FR-003**: System MUST display, for every price, its currency code, unit of measure, and the
  timestamp at which the price was retrieved.
- **FR-003a**: System MUST use USD as the default display currency; each price MUST always retain
  and display its own currency code so values are never shown in an ambiguous or unlabelled currency.
- **FR-004**: System MUST source all pricing exclusively from the official Azure Retail Prices API;
  hardcoded or estimated prices are prohibited.
- **FR-005**: System MUST show an explicit "not available" state for any pricing dimension a SKU/region
  lacks, never a zero, blank, or fabricated value. (FR-002a is a specialization of this rule for
  reserved-instance and Hybrid Benefit dimensions.)
- **FR-006**: System MUST provide independent Azure Hybrid Benefit toggles for Windows Server and for
  SQL Server, and apply each to eligible SKUs only.
- **FR-007**: System MUST present any savings figure such that it is reproducible from the displayed
  base price, term, and applied benefit.
- **FR-007a**: Azure Hybrid Benefit prices are DERIVED from Retail Prices API meters (the API does not
  publish an explicit Hybrid Benefit price). The system MUST show the derivation components alongside
  the result, MUST validate the derivation method against at least one known Hybrid Benefit price
  before release, and MUST fall back to "not available" whenever the required counterpart meter cannot
  be resolved rather than presenting an approximate or guessed value.
- **FR-008**: Users MUST be able to export the currently displayed data to CSV.
- **FR-009**: Users MUST be able to export the currently displayed data to XLSX (XLS-family).
- **FR-010**: Exports MUST be a lossless representation of the on-screen data (same rows, values,
  currency, unit, region, term, Hybrid Benefit context) and MUST include metadata recording the data
  source, retrieval timestamp, and applied filters.
- **FR-011**: System MUST present contextual best-practice / FinOps guidance grounded in current
  Microsoft guidance (via Microsoft Learn MCP) and validated against Azure data (via Azure MCP).
- **FR-011a**: MCP-grounded guidance MUST be resolved at BUILD/CURATION time (not by live calls from
  the deployed container). Guidance text and its source references MUST be captured into a versioned
  artifact shipped with the image; the runtime computes only reproducible numeric insights (e.g.,
  reserved-instance breakeven) from displayed prices and renders the pre-grounded guidance. The runtime
  MUST NOT depend on MCP endpoints being reachable from Azure Container Instance.
- **FR-012**: System MUST surface the age of cached pricing data and visibly flag stale data.
- **FR-012a**: System MUST persist retrieved pricing data to JSON files on disk (one logical dataset
  per service/region scope), recording the retrieval timestamp and source, and MUST be able to serve
  from and refresh these JSON files so the dashboard works from a stored snapshot between refreshes.
- **FR-013**: System MUST handle Azure Retail Prices API unavailability or rate-limiting with a clear
  error/stale state and MUST NOT display fabricated prices.
- **FR-014**: The dashboard MUST be a mobile-adaptive HTML5 interface usable on mobile, tablet, and
  desktop without horizontal scrolling or loss of function; pricing grids MUST remain readable on
  small screens.
- **FR-015**: The service MUST be served over HTTPS, with plain HTTP redirected to HTTPS, using an
  auto-renewable Let's Encrypt certificate issued via DNS-01 challenge on Cloudflare.
- **FR-016**: The application MUST be deployable to Azure Container Instance from a versioned container
  image via a re-runnable Azure CLI script executed from WSL.
- **FR-017**: Secrets (API keys, Cloudflare DNS token, ACME credentials) MUST be injected at runtime
  and MUST NOT be committed to source control.

### Key Entities *(include if feature involves data)*

- **Service / SKU**: An Azure offering identified by service name, SKU/meter, and product; the unit
  being priced (e.g., per hour, per GB).
- **Region**: An Azure region in which a SKU is priced and available.
- **Price Point**: A single retrieved price — value, currency, unit, purchase option (PAYG / 1-yr RI /
  3-yr RI), retrieval timestamp.
- **Hybrid Benefit Context**: The on/off state of Windows Server and SQL Server benefits and each
  SKU's eligibility.
- **Export Record**: The materialized rows of a filtered view plus metadata (source, retrieval
  timestamp, applied filters) used to generate CSV and XLSX files.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of displayed prices are traceable to the Azure Retail Prices API and carry a
  currency code, unit, and retrieval timestamp.
- **SC-002**: For any chosen service/region, a user can view PAYG, 1-year RI, and 3-year RI prices
  in a single comparison without leaving the page.
- **SC-003**: CSV and XLSX exports match the on-screen rows and values exactly (zero value-changing
  discrepancies) and include source/timestamp/filter metadata.
- **SC-004**: The dashboard is fully usable (no horizontal scroll, no loss of function) on a 360px-wide
  mobile viewport as well as on tablet and desktop.
- **SC-005**: Every displayed savings figure can be reproduced by a reviewer from the shown inputs.
- **SC-006**: The deployed site serves exclusively over HTTPS with a valid auto-renewing certificate;
  HTTP requests redirect to HTTPS.
- **SC-007**: A clean deployment can be reproduced from the documented Azure CLI (WSL) script without
  manual portal steps.

## Assumptions

- **Audience & access**: The dashboard is a public, read-only pricing tool; no end-user login is
  required. (Operational/secret access is separate and governed by the constitution.)
- **Default currency**: USD is the default display currency. Each price always retains and displays
  its own currency code; the dashboard never shows an unlabelled or mixed-currency total.
- **Service coverage**: The dashboard exposes all services/SKUs available through the Azure Retail
  Prices API across every service family, with search/filtering rather than a hardcoded subset, so
  coverage tracks the API and is never limited to Virtual Machines. Reserved-instance and Hybrid
  Benefit options are shown only where the API provides them; elsewhere they render as "not available".
- **Region coverage**: Regions are those represented in the Azure Retail Prices API.
- **Reserved instance terms**: Only 1-year and 3-year reserved terms are shown (per requirements);
  other commitment models are out of scope for this feature.
- **Domain & DNS**: A domain managed via Cloudflare DNS is available for the Let's Encrypt DNS-01
  challenge; the specific domain is provided at deployment time as configuration.
- **Hosting**: Single-region Azure Container Instance hosting is sufficient for this feature; multi-
  region/high-availability hosting is out of scope unless later required.
- **MCP availability**: Microsoft Learn MCP and Azure MCP are reachable in the **build/curation**
  environment used to ground FinOps guidance; the deployed runtime does not call MCP endpoints and
  instead ships pre-grounded, versioned guidance (FR-011a).

## Dependencies

- Azure Retail Prices API (authoritative pricing source).
- Microsoft Learn MCP (best-practice / FinOps guidance).
- Azure MCP (Azure data validation/context).
- Cloudflare DNS (Let's Encrypt DNS-01 challenge) and a managed domain.
- Azure subscription with permission to deploy to Azure Container Instance.
- Azure CLI available in the WSL environment used for deployment.
