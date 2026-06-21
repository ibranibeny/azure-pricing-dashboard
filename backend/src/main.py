"""FastAPI application factory (T011).

Wires the catalog, pricing, and export routers, mounts the static frontend, and installs a global
handler so any upstream pricing failure surfaces as an honest 502 rather than a fabricated price
(FR-013, Principle I).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import catalog, export, pricing
from .services.retail_prices import RetailPricesError

_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Azure Pricing Dashboard",
        version="1.0.0",
        description=(
            "Region-first Azure pricing: browse every service in a region, drill into SKUs, and "
            "compare pay-as-you-go, 1-year and 3-year reserved pricing with Azure Hybrid Benefit. "
            "All figures come straight from the Azure Retail Prices API — nothing is fabricated."
        ),
    )

    @app.exception_handler(RetailPricesError)
    async def _retail_error_handler(_: Request, exc: RetailPricesError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={
                "detail": f"Upstream Azure Retail Prices API unavailable: {exc}",
                "prices": "not available",
            },
        )

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict:
        return {"status": "ok"}

    app.include_router(catalog.router)
    app.include_router(pricing.router)
    app.include_router(export.router)

    if _FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")

    return app


app = create_app()
