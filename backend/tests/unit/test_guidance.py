"""Unit: FinOps guidance is reproducible from displayed prices and loads the versioned artifact."""

from __future__ import annotations

from datetime import datetime, timezone

from src.services.guidance import build_guidance, load_guidance, reserved_breakeven_savings
from src.services.pricing import assemble_rows
from tests.conftest import _vm_rows

RETRIEVED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_guidance_artifact_is_versioned():
    data = load_guidance()
    assert "version" in data
    assert isinstance(data.get("grounding"), list)
    assert any(e.get("topic") == "reserved-instance-breakeven" for e in data["grounding"])


def test_reserved_savings_reproducible():
    rows = assemble_rows(_vm_rows(), currency="USD", retrieved_at=RETRIEVED)
    b1s = next(r for r in rows if r.armSkuName == "Standard_B1s")
    sentence = reserved_breakeven_savings(b1s)
    # (0.0104 - 0.0072) / 0.0104 = ~30.8%
    assert sentence is not None
    assert "30.8%" in sentence


def test_no_savings_sentence_when_reservation_missing():
    rows = assemble_rows(_vm_rows(), currency="USD", retrieved_at=RETRIEVED)
    d2 = next(r for r in rows if r.armSkuName == "Standard_D2s_v5")
    assert reserved_breakeven_savings(d2) is None


def test_build_guidance_includes_intro_and_insight():
    rows = assemble_rows(_vm_rows(), currency="USD", retrieved_at=RETRIEVED)
    items = build_guidance(rows)
    assert items  # non-empty
    assert any("reservation" in i.lower() for i in items)
