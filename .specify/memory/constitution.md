<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.1 → 1.0.2
Bump rationale: PATCH — clarified the scope of Principle I's six-dimension rule: it applies to
  detailed price-bearing comparison views (SKU drill-down); a purely navigational region overview
  MAY preview a service with a single explicitly-labelled "from" PAYG price plus availability
  indicators, provided the figure is a real Retail Prices API value. No principle added, removed,
  or redefined.

Prior change: 1.0.0 → 1.0.1
Bump rationale: PATCH — clarified deployment tooling (Azure CLI run from WSL) within the
  existing containerized-deployment principle and operations workflow; no principle added,
  removed, or redefined.

Prior change: (uninitialized template) → 1.0.0
Bump rationale: Initial ratification of the project constitution (MAJOR baseline).

Modified principles:
  - [PRINCIPLE_1_NAME] → I. Pricing Data Accuracy & Single Source of Truth (NON-NEGOTIABLE)
  - [PRINCIPLE_2_NAME] → II. FinOps & Best-Practice Grounding
  - [PRINCIPLE_3_NAME] → III. Responsive Frontend-First (HTML5, Mobile-Adaptive)
  - [PRINCIPLE_4_NAME] → IV. Export Integrity (CSV / XLSX)
  - [PRINCIPLE_5_NAME] → V. Secure & Reproducible Containerized Deployment (NON-NEGOTIABLE)

Added sections:
  - Technology & Integration Constraints
  - Deployment, Security & Operations Workflow

Removed sections: none (all template placeholders resolved)

Templates requiring updates:
  - .specify/templates/plan-template.md ✅ compatible (Constitution Check gate references this file generically)
  - .specify/templates/spec-template.md ✅ compatible (no mandatory section conflicts)
  - .specify/templates/tasks-template.md ✅ compatible (principle-driven task types covered)

Deferred / follow-up TODOs: none
-->

# Azure Pricing Dashboard Constitution

## Core Principles

### I. Pricing Data Accuracy & Single Source of Truth (NON-NEGOTIABLE)

All displayed pricing MUST originate from the official Azure Retail Prices API; hardcoded,
estimated, or manually transcribed prices are FORBIDDEN. Every price-bearing view and export
MUST cover the six required pricing dimensions: service/SKU, region, pay-as-you-go, 1-year
reserved instance, 3-year reserved instance, and Azure Hybrid Benefit (Windows Server and SQL
Server). Each result MUST carry its currency code, unit of measure, and the retrieval timestamp.
Cached pricing MUST declare a TTL and surface its age to the user; stale data MUST be visibly
flagged. When a pricing dimension is unavailable for a SKU/region, the UI MUST show an explicit
"not available" state rather than a zero, blank, or fabricated value. The six-dimension guarantee
applies to detailed price-bearing comparison views (the SKU drill-down); a purely navigational
overview MAY preview a service with a single explicitly-labelled "from" pay-as-you-go price plus
availability indicators, provided that figure is itself a real Retail Prices API value (never
fabricated) and the full six dimensions remain one interaction away in the drill-down.

**Rationale:** This is a pricing tool — incorrect numbers cause real financial decisions to fail.
Traceability to the authoritative API and explicit currency/date metadata are the only defense
against silent drift.

### II. FinOps & Best-Practice Grounding

Cost-optimization logic — reserved instance breakeven, Azure Hybrid Benefit savings, and
pay-as-you-go comparisons — MUST be grounded in current Microsoft guidance retrieved via the
Microsoft Learn MCP and validated against Azure MCP data. Hybrid Benefit calculations MUST treat
Windows Server and SQL Server licensing as distinct, separately-toggleable inputs. Any savings
figure presented to the user MUST be reproducible from displayed inputs (base price, term,
benefit applied) — no opaque or unexplained "savings" numbers.

**Rationale:** FinOps recommendations carry authority; grounding them in official sources keeps
guidance correct as Azure pricing and licensing rules evolve.

### III. Responsive Frontend-First (HTML5, Mobile-Adaptive)

The dashboard MUST be delivered as standards-based HTML5 and be fully usable on mobile, tablet,
and desktop viewports without horizontal scrolling or loss of function. Frontend work MUST follow
the `frontend-design` skill conventions. Tables and pricing grids MUST remain readable on small
screens (responsive layout, collapsing, or horizontal-scroll containers with sticky headers).
Core pricing views MUST remain functional without requiring a heavyweight SPA framework unless a
documented need justifies it.

**Rationale:** Decision-makers consult pricing on varied devices; a mobile-adaptive HTML5 baseline
guarantees reach and longevity with minimal dependencies.

### IV. Export Integrity (CSV / XLSX)

Users MUST be able to export the currently displayed pricing data to both CSV and XLSX (XLS-family)
formats. Exports MUST be a faithful, lossless representation of what is shown: identical rows,
identical numeric values, and the same currency, unit, region, term, and Hybrid Benefit context.
Exports MUST include a metadata header or sheet recording the data source (Azure Retail Prices API),
retrieval timestamp, and applied filters. Exported numbers MUST NOT be re-rounded or reformatted in
a way that changes their value relative to the on-screen data.

**Rationale:** Exports feed budgets and procurement; any divergence between screen and file
silently corrupts downstream financial work.

### V. Secure & Reproducible Containerized Deployment (NON-NEGOTIABLE)

The application MUST deploy to Azure Container Instance from a versioned container image — no manual,
unscripted production changes. Deployments MUST be driven by the Azure CLI (`az`) executed from the
maintainer's WSL environment (or an equivalent CI runner) using authenticated, scripted, repeatable
commands; the exact `az` invocation sequence MUST be captured in a re-runnable script. HTTPS MUST be
enforced end-to-end using a Let's Encrypt certificate
issued via DNS-01 challenge on Cloudflare; plain HTTP MUST redirect to HTTPS and certificates MUST be
auto-renewable. Secrets (API keys, Cloudflare DNS tokens, ACME credentials) MUST NEVER be committed to
source control and MUST be injected via environment variables or a secrets store. Outbound calls to
the Azure Retail Prices API and MCP integrations MUST occur over TLS.

**Rationale:** A public, internet-facing pricing dashboard is an attack surface; enforced TLS,
externalized secrets, and reproducible container deploys are the minimum bar for trustworthy operation.

## Technology & Integration Constraints

- **Pricing data source:** Azure Retail Prices API (public, authoritative) for all SKU pricing.
- **Required integrations:**
  - Microsoft Learn MCP — best practices and FinOps guidance.
  - Azure MCP — Azure resource/pricing context and validation.
  - Azure Retail Prices API — primary pricing data feed.
- **Frontend:** HTML5, mobile-adaptive, built per the `frontend-design` skill.
- **Export formats:** CSV and XLSX MUST both be supported and kept in lockstep with on-screen data.
- **Deployment target:** Azure Container Instance, deployed from a tagged container image.
- **Deployment tooling:** Azure CLI (`az`) run from WSL (or equivalent CI runner); the `az login`
  and `az container`/deployment command sequence MUST live in a re-runnable script.
- **TLS/Certificates:** Let's Encrypt via DNS-01 challenge on Cloudflare; auto-renewal required.
- New runtime dependencies and integrations MUST be justified against these constraints before adoption.

## Deployment, Security & Operations Workflow

- All infrastructure and deployment steps MUST be scripted/reproducible (IaC or documented,
  re-runnable scripts); manual portal changes to production are prohibited except for break-glass
  incidents, which MUST be back-filled into code.
- Secrets MUST be provided at runtime via environment variables or a secrets store; a committed
  `.env` or embedded credential is a release blocker.
- Certificate issuance and renewal MUST be validated in a non-production path before production use.
- Pricing-affecting changes (new dimensions, currency handling, Hybrid Benefit logic, export columns)
  MUST be reviewed against Principles I, II, and IV before merge.
- Every release MUST be traceable to a container image tag and the constitution version in force.

## Governance

This constitution supersedes other development practices for the Azure Pricing Dashboard. All pull
requests and reviews MUST verify compliance with the five core principles; reviewers MUST block merges
that introduce hardcoded pricing, screen/export divergence, non-HTTPS paths, committed secrets, or
non-reproducible deployments. Amendments MUST be documented in this file, include a version bump and
rationale, and update the Sync Impact Report. Versioning follows semantic rules: MAJOR for
backward-incompatible governance or principle removal/redefinition, MINOR for new principles or
materially expanded guidance, PATCH for clarifications and non-semantic refinements. Complexity that
deviates from these principles MUST be explicitly justified in the relevant plan's Constitution Check.

**Version**: 1.0.2 | **Ratified**: 2026-06-21 | **Last Amended**: 2026-06-21
