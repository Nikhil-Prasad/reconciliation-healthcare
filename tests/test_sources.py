from __future__ import annotations

import json
import zipfile

import openpyxl
import xlrd

from reconciliation_healthcare.download import MANIFEST_PATH, RAW_DIR, SOURCES, sha256_file
from reconciliation_healthcare.inspect_nhea import (
    PRINCIPAL_ARCHIVE,
    SUMMARY_ARCHIVE,
    TABLES_ARCHIVE,
    build_inventory,
)

EXPECTED_SHA256 = {
    "nhe-tables.zip": "a09ef6d3e84e25d745047a47b6b08a0d96b303085b4c725b67ce67a0eb0c4420",
    "national-health-expenditures-type-service-source-funds-cy-1960-2024.zip": (
        "b6a9e26774ca36931d42add46204947d6335fc4898011780563196898f964746"
    ),
    "nhe-summary-including-share-gdp-cy-1960-2024.zip": (
        "ef92c5602a96ffebd5ec0d313f0e7dc55bca979178ca53d8e519cfd51bd99256"
    ),
    "definitions-sources-methods.pdf": (
        "9c5755666847a78103016f04da937326744071a9a6736f4e77e91ce9e7af8629"
    ),
    "quick-definitions-national-health-expenditures-accounts-nhea-categories.pdf": (
        "7e6af1be70ccf9aa7bc4cfdc5329e335703c3279d3cbd8f4cbfb411917945c4b"
    ),
    "summary-benchmark-changes-2024.pdf": (
        "edf3a7bc9db00b34f9569eadc2d6e8a8d80b0f5aa931633aa7d3bfdcf2146b35"
    ),
    "accounting-federal-covid-expenditures-national-health-expenditure-accounts.pdf": (
        "5350d42a84a7b1ecafdef3e3f85c9bc9c5540fcbed2f55058856d78be43d0f25"
    ),
}


def test_required_sources_exist_and_match_manifest() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    records = manifest["records"]
    assert len(records) == len(SOURCES) == 7
    assert {record["original_filename"] for record in records} == {
        source.filename for source in SOURCES
    }
    specifications = {source.filename: source for source in SOURCES}
    for record in records:
        path = RAW_DIR / record["original_filename"]
        specification = specifications[record["original_filename"]]
        assert path.is_file()
        assert path.stat().st_size == record["bytes"]
        assert sha256_file(path) == record["sha256"]
        assert record["sha256"] == EXPECTED_SHA256[record["original_filename"]]
        assert record["source_authority"] == "Centers for Medicare & Medicaid Services"
        assert record["source_page"] == (
            "https://www.cms.gov/data-research/statistics-trends-and-reports/"
            "national-health-expenditure-data/historical"
        )
        assert record["source_url"] == specification.url
        assert record["dataset"] == specification.dataset
        assert record["coverage"] == specification.coverage
        assert record["downloaded_at"]
        assert record["http_last_modified"]


def test_principal_and_summary_archive_members_and_sheets() -> None:
    with zipfile.ZipFile(RAW_DIR / PRINCIPAL_ARCHIVE) as archive:
        assert archive.namelist() == ["NHE2024.csv", "NHE2024.xls"]
        workbook = xlrd.open_workbook(file_contents=archive.read("NHE2024.xls"))
        assert workbook.sheet_names() == ["NHE24"]
    with zipfile.ZipFile(RAW_DIR / SUMMARY_ARCHIVE) as archive:
        assert archive.namelist() == ["NHE24_Summary.csv", "NHE24_Summary.xls"]
        workbook = xlrd.open_workbook(file_contents=archive.read("NHE24_Summary.xls"))
        assert workbook.sheet_names() == ["NHE24"]


def test_nhe_tables_inventory_and_expected_sheets() -> None:
    inventory = build_inventory()
    tables = inventory["nhe_tables"]
    assert tables["workbook_count"] == 31
    assert all(len(workbook["sheets"]) == 1 for workbook in tables["workbooks"])
    expected = {
        "Table 05 National Health Expenditures by Type of Sponsor.xlsx": "Table 5",
        "Table 19 National Health Expenditures by Type of Expenditure and Program.xlsx": "Table 19",
    }
    observed = {
        workbook["filename"]: workbook["sheets"][0]["name"]
        for workbook in tables["workbooks"]
    }
    assert all(observed[filename] == sheet for filename, sheet in expected.items())

    with zipfile.ZipFile(RAW_DIR / TABLES_ARCHIVE) as archive:
        assert len(archive.namelist()) == 31
        for filename, sheet in expected.items():
            workbook = openpyxl.load_workbook(
                filename=__import__("io").BytesIO(archive.read(filename)),
                read_only=True,
                data_only=True,
            )
            assert workbook.sheetnames == [sheet]


def test_inventory_captures_actual_shapes() -> None:
    inventory = build_inventory()
    principal_csv = next(
        member
        for member in inventory["principal"]["members"]
        if member["filename"] == "NHE2024.csv"
    )
    summary_csv = next(
        member
        for member in inventory["summary"]["members"]
        if member["filename"] == "NHE24_Summary.csv"
    )
    assert (principal_csv["logical_rows"], principal_csv["logical_columns"]) == (545, 66)
    assert principal_csv["observed_row_widths"] == [66]
    assert (summary_csv["logical_rows"], summary_csv["logical_columns"]) == (35, 66)
