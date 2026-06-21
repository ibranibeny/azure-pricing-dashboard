# Implementation Plan: Azure Pricing Dashboard

**Branch**: `001-azure-pricing-dashboard` | **Date**: 2026-06-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-azure-pricing-dashboard/spec.md`

## Summary

A public, read-only HTML5 dashboard with a region-first experience: the user picks an Azure region and
sees **all** services available there (each with a representative "from" pay-as-you-go price and 1-year /
3-year reserved-instance availability indicators), then drills into a service (e.g., Virtual Machines) to
see its SKUs across pay-as-you-go, 1-year reserved, and 3-year reserved terms, with independent Azure
Hybrid Benefit toggles for Windows Server and SQL Server. All pricing comes from the official Azure
Retail Prices API (default currency USD, each price keeping its own currency code). FinOps guidance is
grounded via the Microsoft Learn MCP and validated with the Azure MCP **at build/curation time** and
shipped as a versioned artifact (the runtime does not call MCP). The current view exports losslessly to
CSV and XLSX. The app is containerized and deployed to Azure Container Instance, fronted by a reverse
proxy that obtains an auto-renewing Let's Encrypt certificate via DNS-01 challenge on Cloudflare, with
secrets injected at runtime. Deployment is driven by a re-runnable Azure CLI script executed from WSL.

## Technical Context

**Language/Version**: Python 3.12 (backend/API proxy); HTML5 + modern CSS + vanilla ES2022 JavaScript (frontend)

**Primary Dependencies**: FastAPI + Uvicorn (API + static hosting); httpx (Retail Prices API client);
openpyxl (XLSX export); Python `csv` stdlib (CSV export); Caddy 2 with the Cloudflare DNS module (TLS
termination + Let's Encrypt DNS-01 auto-renewal). No frontend SPA framework (constitution Principle III).
Frontend visual design follows the **`frontend-design` skill** (anthropics/skills) — deliberate token
system (palette/type/layout/signature), not templated defaults; see research.md R4.

**Storage**: No relational database. Retrieved pricing is persisted as **JSON files on disk** (one
logical dataset per service/region scope, each carrying source + retrieval timestamp), backed by an
in-memory TTL cache for hot reads. The JSON data directory and Caddy's ACME certificate/state directory
are persisted on an Azure Files share mounted into the ACI container group, so snapshots and certs
survive container restarts (and avoid Let's Encrypt rate limits).

**Testing**: pytest (backend unit + contract tests against the Retail Prices API schema; export-integrity
tests comparing rendered rows to CSV/XLSX output); JSON-schema validation for the internal API contract;
manual responsive checks at 360px / tablet / desktop breakpoints.

**Target Platform**: Linux container (Azure Container Instance, single region). Browsers: evergreen mobile + desktop.

**Project Type**: Web application (frontend + backend) — backend proxies the pricing API, applies caching,
computes Hybrid Benefit/savings, performs MCP-grounded guidance lookups, and generates exports; frontend
renders the mobile-adaptive UI.

**Performance Goals**: The region overview (all services in a region) renders in < 2 s served from a
warm snapshot; SKU drill-down for a service/region renders in < 2 s when cache-warm; export generation
for a typical filtered view completes in < 3 s.

**Constraints**: No fabricated prices ever (explicit "not available" states); HTTPS-only with HTTP→HTTPS
redirect; secrets never committed; mobile-adaptive with no horizontal scroll at 360px; exports faithful
to on-screen values; reproducible WSL Azure CLI deployment.

**Scale/Scope**: Single-region public tool; pricing dataset bounded by Retail Prices API (paginated 1,000
records/page) and spanning **all** Azure service families (Compute, Storage, Databases, Networking,
Containers, Analytics, AI, Web, IoT, etc.) — not VM-only; services/SKUs/regions discovered dynamically
from the API. 4 user stories, ~25 functional requirements.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.2 — five principles:

| Principle | Gate | Status |
|-----------|------|--------|
| I. Pricing Data Accuracy & Single Source of Truth (NON-NEGOTIABLE) | All prices from Retail Prices API; six dimensions; currency/unit/timestamp on every price; "not available" states; cache TTL + staleness surfaced | PASS — backend is a thin proxy over `prices.azure.com`; no hardcoded prices; cache carries `retrievedAt` + TTL; missing terms render as "not available". Six-dimension scope: the detailed SKU **drill-down** view carries all six dimensions; the region **overview** is a navigational preview whose only price is an explicitly-labelled "from" PAYG figure plus RI/AHB availability indicators (not a price-bearing comparison view) |
| II. FinOps & Best-Practice Grounding | Guidance via Microsoft Learn MCP, validated via Azure MCP; Windows vs SQL benefits distinct; reproducible savings | PASS — savings computed from displayed inputs; guidance text grounded through MCP at build/curation time and shipped as a versioned artifact (runtime does not call MCP, FR-011a); Windows & SQL handled separately |
| III. Responsive Frontend-First (HTML5, mobile-adaptive) | HTML5; usable 360px→desktop, no horizontal scroll; readable grids; no heavyweight SPA without justification | PASS — vanilla HTML5/CSS/JS, responsive grid with sticky headers / horizontal-scroll container; no SPA framework |
| IV. Export Integrity (CSV / XLSX) | Both formats; lossless to screen; metadata header/sheet; no value-changing reformatting | PASS — exports built from the exact materialized rows the UI rendered; metadata with source + timestamp + filters |
| V. Secure & Reproducible Containerized Deployment (NON-NEGOTIABLE) | ACI from versioned image; Let's Encrypt DNS-01 on Cloudflare; HTTP→HTTPS; secrets externalized; TLS egress; WSL `az` script | PASS — Caddy DNS-01 auto-renew; cert state persisted on Azure Files; secrets via secure env vars; re-runnable `deploy/deploy.sh` using `az container` |

**Initial gate: PASS** — no violations; Complexity Tracking not required.

**Post-design re-check (after Phase 1): PASS** — data model, API contract, and quickstart introduce no
new dependencies or deviations; export columns mirror the comparison rows (Principle IV), and the
contract exposes no endpoint that returns a price without currency/unit/timestamp (Principle I).

## Project Structure

### Documentation (this feature)

```text
specs/001-azure-pricing-dashboard/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── pricing-api.openapi.yaml
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── main.py                 # FastAPI app: API routes + static frontend mount
│   ├── models/                 # Pydantic models: PricePoint, ServiceSummary, ComparisonRow, ExportRecord
│   ├── services/
│   │   ├── retail_prices.py    # Azure Retail Prices API client (httpx, pagination, currency)
│   │   ├── catalog.py          # Region enumeration + all-services ServiceSummary aggregation (overview)
│   │   ├── datastore.py        # JSON file persistence (read/write snapshots + retrievedAt/source)
│   │   ├── cache.py            # In-memory TTL cache layered over the JSON datastore
│   │   ├── pricing.py          # Group PricePoints into ComparisonRows (drill-down)
│   │   ├── hybrid_benefit.py   # Windows/SQL benefit + reproducible savings logic
│   │   ├── guidance.py         # Runtime numeric insights + render pre-grounded versioned guidance.json (no MCP at runtime)
│   │   └── exporters.py        # CSV + XLSX generation from materialized rows
│   └── api/
│       ├── catalog.py          # GET /api/regions, GET /api/regions/{region}/services (overview)
│       ├── pricing.py          # GET /api/pricing (SKU drill-down)
│       └── export.py           # GET /api/export/{csv|xlsx}
└── tests/
    ├── contract/               # Retail Prices API schema + internal API contract tests
    ├── integration/            # End-to-end: query → render rows → export parity
    └── unit/                   # hybrid_benefit, cache, datastore, exporters

data/
└── pricing/                    # JSON snapshots: {service}_{region}.json (source + retrievedAt + rows)

frontend/
├── index.html                  # Mobile-adaptive HTML5 shell
├── css/
│   ├── tokens.css              # Design tokens from frontend-design skill (palette/type/scale)
│   └── styles.css              # Responsive layout, sticky headers, 360px breakpoint
└── js/
    ├── overview.js             # Region selector + all-services overview list (landing)
    ├── app.js                  # Service drill-down: fetch, render SKU grid, staleness flagging
    ├── filters.js              # Hybrid Benefit (Windows/SQL) controls in drill-down
    └── export.js               # Trigger CSV/XLSX downloads

deploy/
├── Dockerfile                  # App image (FastAPI + Uvicorn)
├── Caddyfile                   # TLS termination, HTTP→HTTPS, Cloudflare DNS-01
├── deploy.sh                   # Re-runnable Azure CLI (WSL) ACI deployment script
└── .env.example               # Documented runtime config (NO secrets committed)
```

**Structure Decision**: Web application — a Python/FastAPI backend acts as a caching proxy and
computation/export layer over the Azure Retail Prices API and serves the static HTML5 frontend.
A separate Caddy container in the same ACI container group terminates TLS and manages Let's Encrypt
DNS-01 certificates. This keeps the frontend framework-free (Principle III) while centralizing
pricing accuracy, benefit math, and export generation server-side (Principles I, II, IV). The frontend's
visual identity is produced via the `frontend-design` skill's brainstorm→critique→build process
(design tokens in `frontend/css/tokens.css`), avoiding generic AI-default dashboard looks.

## Complexity Tracking

> No constitution violations — section intentionally empty.
