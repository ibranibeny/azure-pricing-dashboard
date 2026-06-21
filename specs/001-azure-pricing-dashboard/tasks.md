---
description: "Task list for Azure Pricing Dashboard implementation"
---

# Tasks: Azure Pricing Dashboard

**Input**: Design documents from `specs/001-azure-pricing-dashboard/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/pricing-api.openapi.yaml](contracts/pricing-api.openapi.yaml),
[quickstart.md](quickstart.md)

**Tests**: Included — the plan mandates contract + export-parity + unit tests, and the constitution
(Principles I & IV) requires verifying pricing accuracy and lossless screen↔export parity.

**Organization**: Tasks are grouped by user story (US1–US4) for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 / US4 (Setup, Foundational, Deployment, Polish have no story label)

## Path Conventions

Web app layout from plan.md: `backend/src/`, `backend/tests/`, `frontend/`, `deploy/`, `data/pricing/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and structure

- [x] T001 Create project structure per plan.md: `backend/src/{models,services,api}/`, `backend/tests/{contract,integration,unit}/`, `frontend/{css,js}/`, `deploy/`, `data/pricing/`
- [x] T002 Create `backend/requirements.txt` with FastAPI, uvicorn, httpx, openpyxl, pytest, pytest-asyncio, jsonschema and `backend/pyproject.toml`
- [x] T003 [P] Configure linting/formatting in `backend/pyproject.toml` (ruff + black) and add `backend/.gitignore`
- [x] T004 [P] Create `deploy/.env.example` documenting runtime config (CLOUDFLARE_API_TOKEN, APP_DOMAIN, DEFAULT_CURRENCY, CACHE_TTL_SECONDS, ACME_EMAIL) with NO real secrets, and add `.env` to `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST exist before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 [P] Implement config loader in `backend/src/config.py` (env vars, DEFAULT_CURRENCY=USD, CACHE_TTL_SECONDS, data dir path)
- [x] T006 [P] Create core models in `backend/src/models/price_point.py` (`PricePoint`, `PurchaseOption` enum) and `backend/src/models/common.py` (`NotAvailable` sentinel) per data-model.md
- [x] T007 [P] Create `backend/src/models/snapshot.py` (`PricingSnapshot`) and `backend/src/models/query.py` (`QueryFilters`) per data-model.md
- [x] T008 Implement `backend/src/services/retail_prices.py`: httpx client for `prices.azure.com` `2023-01-01-preview`, OData `$filter` builder (serviceName/serviceFamily/armSkuName/armRegionName/priceType), `currencyCode` param, full `NextPageLink` pagination
- [x] T009 Implement `backend/src/services/datastore.py`: read/write per-(service,region) JSON files in `data/pricing/{service}_{region}.json` with `source`+`retrievedAt`+filters (FR-012a)
- [x] T010 Implement `backend/src/services/cache.py`: in-memory TTL cache layered over the JSON datastore; expose data age + `isStale` (FR-012)
- [x] T011 Create FastAPI app in `backend/src/main.py`: app factory, error handling (502 → stale/empty, never fabricated prices per FR-013), and static mount of `frontend/`
- [x] T012 [P] Create mobile-adaptive HTML5 shell `frontend/index.html` and `frontend/css/tokens.css` (palette/type tokens from research.md R4 / frontend-design skill)
- [x] T013 [P] Create base responsive styles in `frontend/css/styles.css` (flex/grid, sticky headers, 360px breakpoint, visible focus, reduced-motion) per Principle III
- [x] T014 [P] Add contract-test harness in `backend/tests/contract/conftest.py` validating responses against `contracts/pricing-api.openapi.yaml` (jsonschema)

**Checkpoint**: Foundation ready — user stories can begin

---

## Phase 3: User Story 1 - Browse all services by region, then drill into SKUs (Priority: P1) 🎯 MVP

**Goal**: Select a region and see **all** Azure services available there (no service pre-selection),
each with a representative cost and 1-yr / 3-yr RI availability indicators; clicking a service (e.g.,
Virtual Machines) drills down into its SKUs with PAYG / 1-year RI / 3-year RI prices, each with
currency, unit, and retrieval timestamp; missing terms show "not available"; data age/staleness
surfaced. Covers all service families and full VM/region SKU detail. All values from the Retail Prices API.

**Independent Test**: Pick a region; confirm a list of all services renders with representative
cost + RI indicators; click Virtual Machines and confirm SKUs render three purchase options with
currency/unit/timestamp matching the Retail Prices API, and a SKU lacking an RI term shows "not available".

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [x] T015 [P] [US1] Contract test for `GET /api/pricing` (drill-down) in `backend/tests/contract/test_pricing_contract.py` (schema, required currency/unit/retrievedAt on every price)
- [x] T016 [P] [US1] Contract test for `GET /api/regions/{armRegionName}/services` (region overview) and `GET /api/regions` in `backend/tests/contract/test_catalog_contract.py` (lists ALL services in region, all families — not VM-only, FR-001/FR-001a)
- [x] T017 [P] [US1] Unit test for "not available" sentinel mapping in `backend/tests/unit/test_not_available.py` (FR-002a, FR-005 — never zero/blank/fabricated)
- [x] T018 [P] [US1] Integration test in `backend/tests/integration/test_vm_region_detail.py`: same VM size across two regions yields region-specific SKUs/prices (FR-002b)
- [x] T018a [P] [US1] Integration test in `backend/tests/integration/test_region_overview.py`: region overview lists multiple service families with honest representative prices and RI availability flags (FR-001, FR-001b)

### Implementation for User Story 1

- [x] T019 [P] [US1] Create `backend/src/models/comparison_row.py` (`ComparisonRow`) and `backend/src/models/service_summary.py` (`ServiceSummary` with skuCount, representativePrice, reserved1Y/3YAvailable, hybridBenefitEligible) per data-model.md
- [x] T020 [US1] Implement comparison assembly in `backend/src/services/pricing.py`: group PricePoints into ComparisonRows by SKU, map PAYG/Reservation(1Y/3Y), fill missing with NotAvailable (depends on T008–T010, T019)
- [x] T021 [US1] Implement region aggregation in `backend/src/services/catalog.py`: from a region's PricePoints, build the list of all services with `ServiceSummary` (lowest available PAYG as representativePrice, RI/Hybrid availability flags), plus distinct regions from API (dynamic, FR-001/FR-001a)
- [x] T022 [US1] Implement `GET /api/regions/{armRegionName}/services` (region overview, all services), `GET /api/regions`, and the optional `GET /api/services` search/typeahead (filter the overview list by name; not a precondition for browsing) in `backend/src/api/catalog.py`
- [x] T023 [US1] Implement `GET /api/pricing` (drill-down) in `backend/src/api/pricing.py` (validates service+region filter → 400; returns PricingResponse with source/retrievedAt/isStale)
- [x] T024 [P] [US1] Frontend region selector + service overview list in `frontend/js/overview.js`: populate regions from `/api/regions`, render all services for the chosen region from `/api/regions/{region}/services` with representative cost + RI indicator badges
- [x] T025 [US1] Frontend drill-down in `frontend/js/app.js`: on service click, fetch `/api/pricing`, render SKU comparison grid (currency/unit/timestamp per price, "not available" cells), show data age + stale flag, with a back path to the region overview
- [x] T026 [US1] Style the overview list + comparison grid in `frontend/css/styles.css`: tabular-figures numbers, sticky headers, clickable service rows, horizontal-scroll fallback at 360px (research.md R4 signature)

**Checkpoint**: US1 fully functional and independently testable — MVP

---

## Phase 4: User Story 2 - Apply Azure Hybrid Benefit (Windows & SQL) (Priority: P2)

**Goal**: Independent Windows Server and SQL Server benefit toggles produce eligible prices and
reproducible savings vs PAYG, applied to eligible SKUs only.

**Independent Test**: Toggle Windows benefit on a Windows VM SKU; eligible price + savings equal
base − Linux-equivalent rate; SQL toggle is independent and has no effect on a non-SQL workload.

### Tests for User Story 2 ⚠️ (write first, ensure they FAIL)

- [x] T027 [P] [US2] Unit test in `backend/tests/unit/test_hybrid_benefit.py`: Windows savings reproducible from base − Linux-equivalent; SQL savings independent; ineligible SKU → no effect (FR-006, FR-007)
- [x] T028 [P] [US2] Unit test: missing counterpart meter → eligiblePrice = NotAvailable (not guessed) in `backend/tests/unit/test_hybrid_benefit_gaps.py` (Principle I)
- [x] T028a [P] [US2] Validation test in `backend/tests/integration/test_hybrid_benefit_known_price.py`: the derived Azure Hybrid Benefit price for a known SKU matches a known published AHB reference price within tolerance; release MUST fail if the derivation method drifts (FR-007a)

### Implementation for User Story 2

- [x] T029 [P] [US2] Create `backend/src/models/hybrid_benefit.py` (`HybridBenefitResult`) per data-model.md
- [x] T030 [US2] Implement `backend/src/services/hybrid_benefit.py`: resolve Windows/Linux-equivalent and SQL license meter pairs from API results, compute reproducible windowsSavings/sqlSavings/eligiblePrice, independent toggles (depends on T020, T029)
- [x] T031 [US2] Extend `GET /api/pricing` in `backend/src/api/pricing.py` to honor `windowsHybridBenefit` & `sqlHybridBenefit` and attach `HybridBenefitResult` to rows
- [x] T032 [P] [US2] Frontend toggles in `frontend/js/filters.js`: independent Windows + SQL Hybrid Benefit controls
- [x] T033 [US2] Frontend in `frontend/js/app.js`: render eligible price + inline reproducible savings breakdown ("savings ledger"); show "not eligible"/"not available" states

**Checkpoint**: US1 + US2 both work independently

---

## Phase 5: User Story 3 - Export current view to CSV and XLSX (Priority: P2)

**Goal**: Export the exact on-screen rows to CSV and XLSX, lossless, with a metadata header/sheet
(source, retrieval timestamp, applied filters).

**Independent Test**: Filter view, export CSV and XLSX; both files match screen rows/values exactly and
include source/timestamp/filter metadata.

### Tests for User Story 3 ⚠️ (write first, ensure they FAIL)

- [x] T034 [P] [US3] Integration test in `backend/tests/integration/test_export_parity.py`: CSV and XLSX rows/values byte-faithful to the `/api/pricing` rows; no value-changing re-rounding (FR-010, Principle IV)
- [x] T035 [P] [US3] Unit test in `backend/tests/unit/test_export_metadata.py`: metadata header (CSV) and metadata sheet (XLSX) carry source, retrievedAt, generatedAt, filters

### Implementation for User Story 3

- [x] T036 [P] [US3] Create `backend/src/models/export_record.py` (`ExportRecord`) per data-model.md
- [x] T037 [US3] Implement `backend/src/services/exporters.py`: CSV (stdlib `csv`) + XLSX (`openpyxl`) from materialized ComparisonRows; metadata block/sheet; no reformatting that changes values (depends on T020, T036)
- [x] T038 [US3] Implement `GET /api/export/{format}` in `backend/src/api/export.py` (csv/xlsx, correct content-types & filename)
- [x] T039 [P] [US3] Frontend export triggers in `frontend/js/export.js`: CSV + XLSX download buttons using current filters

**Checkpoint**: US1 + US2 + US3 all independently functional

---

## Phase 6: User Story 4 - FinOps guidance grounded in official sources (Priority: P3)

**Goal**: Show contextual best-practice/FinOps guidance (e.g., RI breakeven vs PAYG) grounded in
Microsoft guidance and reproducible from displayed inputs.

**Independent Test**: For a SKU where 1-yr RI breaks even before 12 months PAYG, the dashboard surfaces a
grounded recommendation with reproducible breakeven.

### Tests for User Story 4 ⚠️ (write first, ensure they FAIL)

- [x] T040 [P] [US4] Unit test in `backend/tests/unit/test_guidance.py`: RI breakeven computed and reproducible from shown PAYG/RI prices (FR-011)

### Implementation for User Story 4

- [x] T040a [US4] Build-time guidance curation script `backend/tools/curate_guidance.py`: at BUILD/CURATION time, ground FinOps guidance text via Microsoft Learn MCP (and validate context via Azure MCP), then emit a versioned `backend/src/guidance/guidance.json` (guidance text + source references + version) shipped with the image (FR-011a — runtime MUST NOT call MCP)
- [x] T041 [US4] Implement `backend/src/services/guidance.py`: at RUNTIME compute only reproducible numeric insights (e.g., RI breakeven/savings) from ComparisonRows and render the pre-grounded text loaded from the versioned `guidance.json`; MUST NOT call MCP endpoints (FR-011a; depends on T020, T040a)
- [x] T042 [US4] Surface guidance in `GET /api/pricing` response and render it in `frontend/js/app.js` (concise, reproducible, end-user copy)

**Checkpoint**: All four user stories independently functional

---

## Phase 7: Deployment & Security (Cross-Cutting — Constitution Principle V)

**Purpose**: Containerized, HTTPS, reproducible WSL deployment to Azure Container Instance

- [x] T043 [P] Create `deploy/Dockerfile`: build the FastAPI + Uvicorn app image (serves `frontend/`), pinned base, non-root
- [x] T044 [P] Create `deploy/Caddyfile`: TLS termination, HTTP→HTTPS redirect, Let's Encrypt DNS-01 via Cloudflare module, reverse proxy to app:8000, ACME data dir on mounted volume (research.md R5)
- [x] T045 Create `deploy/deploy.sh`: re-runnable WSL Azure CLI script — `az login`, `az acr build` (versioned tag), `az storage share-rw create` (Caddy cert + `data/pricing` persistence), `az container create` for the multi-container group (Caddy 80/443 + app 8000) with Cloudflare token as **secure env var** (R6, FR-016, FR-017)
- [x] T046 Mount the Azure Files share for `data/pricing/` JSON snapshots in the deploy script so snapshots persist across restarts (FR-012a)

**Checkpoint**: App deployable to ACI over HTTPS with auto-renewing cert and externalized secrets

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T047 [P] Add backend `README.md` and frontend usage notes referencing quickstart.md
- [ ] T048 [P] Accessibility/responsive pass: verify 360px / tablet / desktop, keyboard focus, reduced-motion (SC-004, Principle III)
- [ ] T049 Performance: warm-cache comparison render < 2s, export < 3s (plan Performance Goals)
- [ ] T050 Security hardening: confirm no secrets in repo (`git grep` token names), TLS-only egress to API/MCP, secure headers in Caddyfile
- [ ] T051 Run `quickstart.md` end-to-end validation (local run + acceptance scenarios US1–US4 + deploy verification)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Stories (Phases 3–6)**: All depend on Foundational; US2/US3/US4 build on US1's `pricing.py`/ComparisonRow
- **Deployment (Phase 7)**: Can be prepared in parallel but validated after US1 (needs a runnable app)
- **Polish (Phase 8)**: After all targeted user stories complete

### User Story Dependencies

- **US1 (P1)**: After Foundational — no dependency on other stories (MVP)
- **US2 (P2)**: After US1 (extends `pricing.py` + ComparisonRow with HybridBenefitResult)
- **US3 (P2)**: After US1 (exports the materialized ComparisonRows); independent of US2
- **US4 (P3)**: After US1; independent of US2/US3

### Within Each User Story

- Tests written and FAILING before implementation
- Models → services → endpoints → frontend
- Story complete before moving to next priority

### Parallel Opportunities

- Setup: T003, T004 in parallel
- Foundational: T005, T006, T007 in parallel; T012, T013, T014 in parallel
- US1 tests T015–T018 in parallel; then T019/T024 [P]
- US2 tests T027, T028 in parallel; US3 tests T034, T035 in parallel
- Deployment T043, T044 in parallel
- Once Foundational completes, US1→(US2, US3, US4) can be split across contributors after US1 lands

---

## Parallel Example: User Story 1

```text
# After Foundational (Phase 2), launch US1 tests together:
T015 Contract test GET /api/pricing      (backend/tests/contract/test_pricing_contract.py)
T016 Contract test services/regions      (backend/tests/contract/test_catalog_contract.py)
T017 Unit test not-available sentinel     (backend/tests/unit/test_not_available.py)
T018 Integration test VM/region detail    (backend/tests/integration/test_vm_region_detail.py)

# Then parallel implementation where files differ:
T019 ComparisonRow model + T024 filters.js  (different files)
```

---

## Implementation Strategy

### MVP first

Complete Phases 1–2, then **US1 (Phase 3)** → a working dashboard that compares PAYG / 1-yr / 3-yr
across all services and VM/region SKUs with accurate, sourced, timestamped prices. This is a
demoable, independently valuable MVP.

### Incremental delivery

1. **MVP**: Setup + Foundational + US1.
2. **+ Licensing value**: US2 (Hybrid Benefit Windows/SQL).
3. **+ Procurement value**: US3 (CSV/XLSX export).
4. **+ Advisory value**: US4 (FinOps guidance).
5. **Ship**: Deployment (Phase 7) + Polish (Phase 8).

### Summary

- **Total tasks**: 51
- **US1 (P1, MVP)**: 12 tasks (T015–T026)
- **US2 (P2)**: 7 tasks (T027–T033)
- **US3 (P2)**: 6 tasks (T034–T039)
- **US4 (P3)**: 3 tasks (T040–T042)
- **Setup/Foundational**: 14 tasks (T001–T014)
- **Deployment**: 4 tasks (T043–T046)
- **Polish**: 5 tasks (T047–T051)
- **Suggested MVP scope**: Phases 1–3 (T001–T026)
