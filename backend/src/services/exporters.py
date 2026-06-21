"""CSV + XLSX export generation from materialized comparison rows (US3, Principle IV, R7).

Exports are built from the exact :class:`ComparisonRow` objects the API returned, so screen and file
cannot diverge. Numeric values are written verbatim (no value-changing re-rounding). "Not available"
cells render as an explicit token, never zero/blank. Each export carries a metadata header (CSV) or a
dedicated metadata sheet (XLSX) recording source, retrieval timestamp, generation time, and filters.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from openpyxl import Workbook

from ..models.common import NOT_AVAILABLE_TOKEN
from ..models.export_record import ExportRecord
from ..models.price_point import PricePoint

_COLUMNS = [
    "Service",
    "Service family",
    "SKU",
    "SKU name",
    "Region",
    "Location",
    "Unit",
    "Currency",
    "Pay-as-you-go",
    "1-year reserved",
    "3-year reserved",
    "Hybrid Benefit eligible price",
    "Windows savings",
    "SQL savings",
    "Retrieved at",
]


def _cell(point: PricePoint) -> object:
    """Return the numeric price verbatim, or the not-available token (never zero/blank)."""
    if point.available and point.price is not None:
        return point.price
    return NOT_AVAILABLE_TOKEN


def _hybrid_cells(row) -> tuple[object, object, object]:
    hb = row.hybridBenefit
    if hb is None:
        return (NOT_AVAILABLE_TOKEN, "", "")
    eligible = hb.eligiblePrice if hb.eligiblePrice is not None else NOT_AVAILABLE_TOKEN
    return (eligible, hb.windowsSavings, hb.sqlSavings)


def _row_values(row) -> list[object]:
    eligible, win, sql = _hybrid_cells(row)
    return [
        row.serviceName,
        row.serviceFamily,
        row.armSkuName,
        row.skuName,
        row.armRegionName,
        row.location,
        row.unitOfMeasure,
        row.currencyCode,
        _cell(row.payg),
        _cell(row.reserved1Y),
        _cell(row.reserved3Y),
        eligible,
        win,
        sql,
        row.retrievedAt.isoformat(),
    ]


def _metadata_pairs(record: ExportRecord) -> list[tuple[str, str]]:
    f = record.filters
    return [
        ("Source", record.source),
        ("Retrieved at", record.retrievedAt.isoformat()),
        ("Generated at", record.generatedAt.isoformat()),
        ("Region", f.armRegionName),
        ("Service", f.serviceName or ""),
        ("Service family", f.serviceFamily or ""),
        ("SKU", f.armSkuName or ""),
        ("Currency", f.currencyCode),
        ("Windows Hybrid Benefit", str(f.windowsHybridBenefit)),
        ("SQL Hybrid Benefit", str(f.sqlHybridBenefit)),
    ]


def to_csv(record: ExportRecord) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    # Metadata header block (commented), then a blank line, then the table.
    for key, value in _metadata_pairs(record):
        writer.writerow([f"# {key}", value])
    writer.writerow([])
    writer.writerow(_COLUMNS)
    for row in record.rows:
        writer.writerow(_row_values(row))
    return buf.getvalue().encode("utf-8")


def to_xlsx(record: ExportRecord) -> bytes:
    wb = Workbook()

    meta = wb.active
    meta.title = "Metadata"
    meta.append(["Field", "Value"])
    for key, value in _metadata_pairs(record):
        meta.append([key, value])

    sheet = wb.create_sheet("Pricing")
    sheet.append(_COLUMNS)
    for row in record.rows:
        sheet.append(_row_values(row))

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def build_export_record(rows, filters, retrieved_at: datetime, fmt) -> ExportRecord:
    return ExportRecord(
        rows=rows,
        filters=filters,
        retrievedAt=retrieved_at,
        generatedAt=datetime.now(timezone.utc),
        format=fmt,
    )
