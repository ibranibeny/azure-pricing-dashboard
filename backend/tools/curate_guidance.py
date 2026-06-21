"""Build/curation-time FinOps guidance generator (FR-011a, T040a).

This script runs at BUILD/CURATION time on a developer machine or CI runner that HAS access to the
Microsoft Learn MCP and Azure MCP. It grounds the FinOps guidance text against current Microsoft
sources and writes the versioned ``backend/src/guidance/guidance.json`` artifact that ships inside
the container image. The deployed runtime then loads that artifact and NEVER calls MCP.

Usage (from the repo, in an environment with MCP available to your agent/tooling):
    python backend/tools/curate_guidance.py

NOTE: MCP calls are performed by the operator's agent tooling, not by this script directly. This
script defines the canonical guidance topics and emits a stamped artifact. Replace the ``text`` /
``references`` fields below with the freshly-grounded content captured from Microsoft Learn MCP
before each release, then commit the regenerated artifact.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

_ARTIFACT = Path(__file__).resolve().parent.parent / "src" / "guidance" / "guidance.json"

# Canonical, build-time-grounded guidance. Refresh `text`/`references` from Microsoft Learn MCP.
_GROUNDING = [
    {
        "topic": "reserved-instance-breakeven",
        "text": (
            "Reserved Instances trade a 1- or 3-year commitment for a lower effective hourly rate. "
            "A reservation pays off once cumulative pay-as-you-go spend would exceed the "
            "reservation's effective cost over the same period; for steady, always-on workloads the "
            "breakeven typically arrives well inside the term."
        ),
        "references": [
            "https://learn.microsoft.com/azure/cost-management-billing/reservations/save-compute-costs-reservations"
        ],
    },
    {
        "topic": "hybrid-benefit",
        "text": (
            "Azure Hybrid Benefit lets you apply existing Windows Server and SQL Server licences "
            "with Software Assurance to reduce the licence component of eligible Azure resources. "
            "Windows and SQL benefits are independent and stack only on eligible SKUs."
        ),
        "references": [
            "https://learn.microsoft.com/azure/cost-management-billing/scope-level/azure-hybrid-benefit"
        ],
    },
    {
        "topic": "rightsizing",
        "text": (
            "Before committing to a reservation, confirm the SKU is correctly sized. Reserving an "
            "oversized VM locks in waste; rightsize first, then reserve the steady-state baseline."
        ),
        "references": [
            "https://learn.microsoft.com/azure/well-architected/cost-optimization/"
        ],
    },
]


def build_artifact() -> dict:
    return {
        "version": date.today().isoformat(),
        "source": (
            "Azure Retail Prices API + Microsoft Learn FinOps guidance "
            "(grounded at build/curation time)"
        ),
        "grounding": _GROUNDING,
    }


def main() -> None:
    _ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    _ARTIFACT.write_text(json.dumps(build_artifact(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {_ARTIFACT}")


if __name__ == "__main__":
    main()
