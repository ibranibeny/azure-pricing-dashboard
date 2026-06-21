# Quickstart: Azure Pricing Dashboard

This guide gets the dashboard running locally and deployed to Azure Container Instance (ACI) with
HTTPS via Let's Encrypt DNS-01 on Cloudflare. Run all commands from **WSL**.

## Prerequisites

- WSL with: Python 3.12, Docker, and the Azure CLI (`az`).
- An Azure subscription and an Azure Container Registry (ACR) or another registry.
- A domain whose DNS is managed by **Cloudflare**, plus a Cloudflare API token scoped to edit that
  zone's DNS records (used for the ACME DNS-01 challenge).
- Never commit secrets. Copy `deploy/.env.example` to `deploy/.env` and fill it locally.

## Configuration (runtime, injected — not committed)

| Variable | Purpose |
|----------|---------|
| `CLOUDFLARE_API_TOKEN` | DNS-01 challenge for Let's Encrypt (secure env var) |
| `APP_DOMAIN` | Public hostname (e.g., `pricing.example.com`) |
| `DEFAULT_CURRENCY` | Default display currency (`USD`) |
| `CACHE_TTL_SECONDS` | Pricing cache TTL; drives the staleness flag |
| `ACME_EMAIL` | Contact email for Let's Encrypt |

## Run locally

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
# Frontend is served by FastAPI at http://localhost:8000
```

Open http://localhost:8000, select a service (e.g., "Virtual Machines") and a region (e.g., "eastus"),
and confirm PAYG / 1-year RI / 3-year RI prices appear with currency, unit, and a retrieval timestamp.

## Validate the acceptance scenarios

1. **Price comparison (US1)** — select a service + region; confirm three purchase options render, each
   with currency/unit/timestamp; confirm a SKU lacking an RI term shows "not available" (not zero/blank).
2. **Hybrid Benefit (US2)** — toggle Windows Server benefit on a Windows VM SKU; confirm eligible price +
   reproducible savings; confirm the SQL toggle is independent.
3. **Export (US3)** — export CSV and XLSX; open both and confirm rows/values match the screen exactly and
   that a metadata header/sheet lists source, retrieval timestamp, and applied filters.
4. **Staleness** — leave the page until cache TTL elapses; confirm the data age shows and stale data is flagged.

## Run tests

```bash
cd backend
pytest                 # unit + contract + integration
pytest tests/integration/test_export_parity.py   # screen↔export lossless check (Principle IV)
```

## Build & deploy to ACI (from WSL)

```bash
cd deploy
cp .env.example .env          # fill in real values locally; do NOT commit
az login
./deploy.sh                   # re-runnable: builds image, pushes to registry, creates/updates the ACI group
```

`deploy.sh` performs, idempotently:
1. `az acr build` (or `docker build` + `az acr login` + `docker push`) to produce a **versioned** image tag.
2. `az storage share-rw create` for the Azure Files share that persists Caddy's ACME certificates.
3. `az container create` for a **container group** with:
   - a **Caddy** container (ports 80/443) configured by `Caddyfile` for Cloudflare DNS-01 + HTTP→HTTPS redirect,
     with the Azure Files share mounted at Caddy's data dir;
   - the **app** container (FastAPI on 8000), reachable by Caddy over the shared localhost.
   - `CLOUDFLARE_API_TOKEN` and other secrets passed as **secure environment variables**.

## Verify the deployment

```bash
curl -I http://$APP_DOMAIN     # expect 301/308 redirect to https
curl -I https://$APP_DOMAIN    # expect 200 with a valid Let's Encrypt certificate
```

- Confirm the certificate is issued by Let's Encrypt and auto-renews (Caddy handles renewal; cert state
  persists on the mounted share across restarts).
- Confirm no secrets are present in source control (`git grep` for token names should return nothing).

## Constitution checkpoints

- **I**: every visible/exported price has currency + unit + timestamp; missing data shows "not available".
- **II**: savings are reproducible from shown inputs; Windows and SQL benefits are independent.
- **III**: usable at 360px with no horizontal scroll.
- **IV**: CSV and XLSX are lossless to the screen and include source/timestamp/filter metadata.
- **V**: HTTPS-only with auto-renewing Let's Encrypt cert; reproducible WSL `az` deploy; secrets externalized.
