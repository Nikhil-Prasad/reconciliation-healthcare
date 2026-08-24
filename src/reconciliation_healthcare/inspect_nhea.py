"""Inspect the pinned CMS NHEA archives without normalizing their values."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import openpyxl
import xlrd

from reconciliation_healthcare.paths import INVENTORY_PATH, RAW_DIR


PRINCIPAL_ARCHIVE = "national-health-expenditures-type-service-source-funds-cy-1960-2024.zip"
SUMMARY_ARCHIVE = "nhe-summary-including-share-gdp-cy-1960-2024.zip"
TABLES_ARCHIVE = "nhe-tables.zip"


def is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def csv_shape(data: bytes, encoding: str) -> tuple[int, int, list[int]]:
    rows = list(csv.reader(io.TextIOWrapper(io.BytesIO(data), encoding=encoding, newline="")))
    widths = sorted({len(row) for row in rows})
    return len(rows), max(widths, default=0), widths


def logical_xlsx_shape(worksheet: openpyxl.worksheet.worksheet.Worksheet) -> tuple[int, int]:
    last_row = 0
    last_column = 0
    for row_number, row in enumerate(worksheet.iter_rows(values_only=True), start=1):
        nonblank_columns = [
            column_number
            for column_number, value in enumerate(row, start=1)
            if not is_blank(value)
        ]
        if nonblank_columns:
            last_row = row_number
            last_column = max(last_column, max(nonblank_columns))
    return last_row, last_column


def inspect_principal(raw_dir: Path = RAW_DIR) -> dict[str, Any]:
    archive_path = raw_dir / PRINCIPAL_ARCHIVE
    with zipfile.ZipFile(archive_path) as archive:
        members: list[dict[str, Any]] = []
        for info in archive.infolist():
            data = archive.read(info.filename)
            member: dict[str, Any] = {
                "filename": info.filename,
                "uncompressed_bytes": info.file_size,
                "compressed_bytes": info.compress_size,
            }
            if info.filename.lower().endswith(".csv"):
                rows, columns, widths = csv_shape(data, "cp1252")
                member.update(
                    {
                        "encoding": "cp1252",
                        "logical_rows": rows,
                        "logical_columns": columns,
                        "observed_row_widths": widths,
                    }
                )
            elif info.filename.lower().endswith(".xls"):
                workbook = xlrd.open_workbook(file_contents=data, formatting_info=False)
                member["sheets"] = [
                    {
                        "name": sheet.name,
                        "logical_rows": sheet.nrows,
                        "logical_columns": sheet.ncols,
                    }
                    for sheet in workbook.sheets()
                ]
            members.append(member)
    return {
        "archive": PRINCIPAL_ARCHIVE,
        "role": "principal source-of-funds by service history",
        "members": members,
        "units": "current-dollar millions (population row is millions of people)",
        "coverage": "1960-2024",
    }


def inspect_summary(raw_dir: Path = RAW_DIR) -> dict[str, Any]:
    archive_path = raw_dir / SUMMARY_ARCHIVE
    with zipfile.ZipFile(archive_path) as archive:
        members: list[dict[str, Any]] = []
        for info in archive.infolist():
            data = archive.read(info.filename)
            member: dict[str, Any] = {
                "filename": info.filename,
                "uncompressed_bytes": info.file_size,
                "compressed_bytes": info.compress_size,
            }
            if info.filename.lower().endswith(".csv"):
                rows, columns, widths = csv_shape(data, "cp1252")
                member.update(
                    {
                        "encoding": "cp1252",
                        "logical_rows": rows,
                        "logical_columns": columns,
                        "observed_row_widths": widths,
                    }
                )
            elif info.filename.lower().endswith(".xls"):
                workbook = xlrd.open_workbook(file_contents=data, formatting_info=False)
                member["sheets"] = [
                    {
                        "name": sheet.name,
                        "logical_rows": sheet.nrows,
                        "logical_columns": sheet.ncols,
                    }
                    for sheet in workbook.sheets()
                ]
            members.append(member)
    return {
        "archive": SUMMARY_ARCHIVE,
        "role": "supporting NHE/GDP summary",
        "members": members,
        "coverage": "1960-2024",
        "mixed_units": [
            "current-dollar billions",
            "population millions",
            "annual percent change",
            "percent distribution",
            "per-capita dollars",
            "percent of GDP",
        ],
    }


def inspect_tables(raw_dir: Path = RAW_DIR) -> dict[str, Any]:
    archive_path = raw_dir / TABLES_ARCHIVE
    workbooks: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            workbook = openpyxl.load_workbook(
                io.BytesIO(archive.read(info.filename)), read_only=True, data_only=True
            )
            sheets = []
            for worksheet in workbook.worksheets:
                logical_rows, logical_columns = logical_xlsx_shape(worksheet)
                sheets.append(
                    {
                        "name": worksheet.title,
                        "logical_rows": logical_rows,
                        "logical_columns": logical_columns,
                        "formatted_max_rows": worksheet.max_row,
                        "formatted_max_columns": worksheet.max_column,
                    }
                )
            workbooks.append(
                {
                    "filename": info.filename,
                    "uncompressed_bytes": info.file_size,
                    "sheets": sheets,
                }
            )
    return {
        "archive": TABLES_ARCHIVE,
        "role": "supporting detailed, sponsor, and reconciliation tables",
        "workbook_count": len(workbooks),
        "workbooks": workbooks,
    }


def build_inventory(raw_dir: Path = RAW_DIR) -> dict[str, Any]:
    return {
        "inventory_schema_version": 1,
        "inspection_rule": (
            "Logical rows and columns ignore null and whitespace-only trailing cells; "
            "no values are normalized by this inspection."
        ),
        "principal": inspect_principal(raw_dir),
        "summary": inspect_summary(raw_dir),
        "nhe_tables": inspect_tables(raw_dir),
    }


def write_inventory(path: Path = INVENTORY_PATH) -> dict[str, Any]:
    inventory = build_inventory()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    return inventory


def main() -> None:
    inventory = write_inventory()
    print(f"Inspected {inventory['nhe_tables']['workbook_count']} NHE Tables workbooks.")
    print(f"Wrote {INVENTORY_PATH}")


if __name__ == "__main__":
    main()
