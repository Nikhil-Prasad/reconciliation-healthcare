from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

import reconciliation_healthcare.validation as validation
from reconciliation_healthcare.normalize_nhea import DUCKDB_PATH
from reconciliation_healthcare.validation import (
    EXPECTED_SOURCE_HIERARCHY_CHECK_COUNT,
    EXPECTED_VALIDATION_CHECK_COUNT,
    KNOWN_2024_USD,
    SOURCE_HIERARCHY_SERVICE_CODES,
    accounting_checks,
    run_validation,
    source_hierarchy_checks,
)


def _amount(dataframe: pd.DataFrame, service: str, source: str) -> int:
    value = dataframe.loc[
        (dataframe["year"] == 2024)
        & (dataframe["service_category_code"] == service)
        & (dataframe["funding_source_code"] == source),
        "amount_usd",
    ]
    assert len(value) == 1
    return int(value.iloc[0])


def test_all_accounting_and_cross_table_checks_pass(
    built_artifacts: dict[str, pd.DataFrame],
) -> None:
    results = run_validation()
    failed = [result for result in results if not result["passed"]]
    assert not failed, failed[:10]
    assert EXPECTED_VALIDATION_CHECK_COUNT == 8_997
    assert len(results) == EXPECTED_VALIDATION_CHECK_COUNT
    table19 = [result for result in results if result["identity"].startswith("Table 19")]
    assert len(table19) == 110
    assert all(result["passed"] for result in table19)


def test_all_historical_source_hierarchies_reconcile(
    built_artifacts: dict[str, pd.DataFrame],
) -> None:
    results = source_hierarchy_checks(built_artifacts["source_service"])
    assert len(results) == EXPECTED_SOURCE_HIERARCHY_CHECK_COUNT == 7_735
    assert all(result["passed"] for result in results)
    assert {result["service_category_code"] for result in results} == set(
        SOURCE_HIERARCHY_SERVICE_CODES
    )

    by_parent: dict[str, list[dict[str, object]]] = {}
    for result in results:
        by_parent.setdefault(str(result["funding_source_code"]), []).append(result)
    assert {parent: len(checks) for parent, checks in by_parent.items()} == {
        "health_insurance": 1_105,
        "medicaid": 1_105,
        "chip": 1_105,
        "maternal_child_health": 1_105,
        "vocational_rehabilitation": 1_105,
        "other_third_party_payers_programs": 1_105,
        "total_cms_programs": 1_105,
    }
    assert {
        parent: max(abs(int(check["residual_usd"])) for check in checks)
        for parent, checks in by_parent.items()
    } == {
        "health_insurance": 2_000_000,
        "medicaid": 1_000_000,
        "chip": 1_000_000,
        "maternal_child_health": 1_000_000,
        "vocational_rehabilitation": 1_000_000,
        "other_third_party_payers_programs": 3_000_000,
        "total_cms_programs": 1_000_000,
    }


def test_missing_ledger_cells_is_a_hard_validation_failure(
    built_artifacts: dict[str, pd.DataFrame],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing-ledger-cells.parquet"
    monkeypatch.setattr(validation, "LEDGER_CELLS_PATH", missing_path)
    with pytest.raises(FileNotFoundError, match="Required generated ledger artifact"):
        validation.ledger_cross_check(built_artifacts["source_service"])


def test_2024_known_cms_values(built_artifacts: dict[str, pd.DataFrame]) -> None:
    source_service = built_artifacts["source_service"]
    for (service, source), expected in KNOWN_2024_USD.items():
        assert _amount(source_service, service, source) == expected


def test_2024_national_service_and_source_reconciliations(
    built_artifacts: dict[str, pd.DataFrame],
) -> None:
    checks = [
        result
        for result in accounting_checks(built_artifacts["source_service"])
        if result["year"] == 2024
    ]
    by_name = {result["identity"]: result for result in checks}
    assert by_name["NHE from mutually exclusive source components"]["residual_usd"] == 0
    assert by_name["PHC from ten service components"]["residual_usd"] == 0
    assert by_name[
        "NHE from mutually exclusive service components"
    ]["residual_usd"] == -1_000_000
    assert by_name[
        "HCE from PHC, administration/non-medical insurance, and public health"
    ]["residual_usd"] == -1_000_000
    assert by_name["Investment from research and structures/equipment"]["residual_usd"] == 1_000_000


def test_ledger_matrix_and_cell_provenance(built_artifacts: dict[str, pd.DataFrame]) -> None:
    ledger = built_artifacts["ledger"]
    cells = built_artifacts["ledger_cells"]
    assert len(ledger) == 14
    assert len(cells) == 114
    total = ledger[ledger["service_category_code"] == "total"].iloc[0]
    assert int(total["Total"]) == 5_278_588_000_000
    interior = cells[
        (cells["ledger_row_code"] != "total")
        & (cells["ledger_column_code"] != "total")
    ]
    assert int(interior["amount_usd"].sum()) == int(total["Total"])
    populated = cells[cells["amount_usd"].notna()]
    for column in (
        "source_file",
        "source_sheet",
        "source_row",
        "source_column",
        "source_label_raw",
        "source_value_raw",
        "source_release",
    ):
        assert populated[column].notna().all()

    assert not cells.duplicated(["ledger_row_code", "ledger_column_code"]).any()
    source_service = built_artifacts["source_service"]
    source_2024 = source_service[source_service["year"] == 2024].set_index(
        ["source_row", "source_column"]
    )
    for cell in cells.itertuples(index=False):
        source = source_2024.loc[(cell.source_row, cell.source_column)]
        assert cell.source_file == source.source_file
        assert cell.source_sheet == source.source_sheet
        assert cell.source_label_raw == source.source_label_raw
        assert cell.source_value_raw == source.source_value_raw
        assert cell.value_status == source.value_status
        if pd.isna(source.amount_usd):
            assert pd.isna(cell.amount_usd)
        else:
            assert int(cell.amount_usd) == int(source.amount_usd)
    public_row = ledger[ledger["service_category_code"] == "public_health"].iloc[0]
    assert pd.isna(public_row["Medicare"])
    assert int(public_row["Government Public Health Activities"]) == 157_569_000_000


def test_duckdb_contains_separate_views_and_ledger(
    built_artifacts: dict[str, pd.DataFrame],
) -> None:
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as connection:
        tables = {
            row[0]
            for row in connection.execute("SHOW TABLES").fetchall()
        }
        assert {
            "nhea_source_service",
            "nhea_sponsor",
            "national_ledger_2024",
            "national_ledger_2024_cells",
        }.issubset(tables)
        assert connection.execute("SELECT count(*) FROM nhea_source_service").fetchone()[0] == 34_970
        assert connection.execute("SELECT count(*) FROM nhea_sponsor").fetchone()[0] == 304
        assert connection.execute("SELECT count(*) FROM national_ledger_2024").fetchone()[0] == 14
