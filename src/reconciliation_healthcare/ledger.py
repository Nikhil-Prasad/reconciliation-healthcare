"""Build the auditable 2024 national payer/source-by-service ledger."""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from reconciliation_healthcare.normalize_nhea import (
    DUCKDB_PATH,
    NULLABLE_INTEGER_COLUMNS,
    SERVICES,
    SOURCE_SERVICE_PATH,
    SPONSOR_PATH,
    STRING_COLUMNS,
    normalize_all,
)
from reconciliation_healthcare.paths import (
    LEDGER_CELLS_CSV_PATH,
    LEDGER_CELLS_PARQUET_PATH,
    LEDGER_CSV_PATH,
    LEDGER_DIR,
    LEDGER_MARKDOWN_PATH,
    LEDGER_PARQUET_PATH,
    LEDGER_SUMMARY_PATH,
)


LEDGER_CELL_STRING_COLUMNS = {
    "ledger_row_code",
    "ledger_row_name",
    "ledger_column_code",
    "ledger_column_name",
    "presentation_rule",
}


FUNDING_COLUMNS: tuple[tuple[str, str, int], ...] = (
    ("out_of_pocket", "Out of pocket", 10),
    ("private_health_insurance", "Private Health Insurance", 20),
    ("medicare", "Medicare", 30),
    ("medicaid", "Medicaid", 40),
    ("chip", "CHIP", 50),
    ("department_of_defense", "Department of Defense", 60),
    ("department_of_veterans_affairs", "Department of Veterans Affairs", 70),
    (
        "other_third_party_payers_programs",
        "Other Third Party Payers and Programs",
        80,
    ),
    (
        "government_public_health_activities",
        "Government Public Health Activities",
        90,
    ),
    ("investment", "Investment", 100),
)

SERVICE_ROWS = tuple(
    sorted(
        (
            service
            for service in SERVICES.values()
            if service.include_in_nhe_service_sum and service.ledger_order is not None
        ),
        key=lambda service: service.ledger_order or 0,
    )
)


def _one(
    dataframe: pd.DataFrame,
    *,
    service_code: str,
    funding_code: str,
    year: int = 2024,
) -> pd.Series:
    matches = dataframe[
        (dataframe["year"] == year)
        & (dataframe["service_category_code"] == service_code)
        & (dataframe["funding_source_code"] == funding_code)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one source record for {year}/{service_code}/{funding_code}; "
            f"found {len(matches)}"
        )
    return matches.iloc[0]


def _cell_from_source(
    source: pd.Series,
    *,
    row_code: str,
    row_name: str,
    row_order: int,
    column_code: str,
    column_name: str,
    column_order: int,
    presentation_rule: str = "direct CMS reported amount",
) -> dict[str, Any]:
    provenance_columns = [
        "amount_usd",
        "amount_unit",
        "value_status",
        "derivation",
        "accounting_view",
        "source_dataset",
        "source_file",
        "source_sheet",
        "source_row",
        "source_column",
        "source_label_raw",
        "source_value_raw",
        "source_unit",
        "source_display_precision_usd",
        "source_release",
        "ingested_at",
    ]
    cell = {
        "ledger_row_code": row_code,
        "ledger_row_name": row_name,
        "ledger_row_order": row_order,
        "ledger_column_code": column_code,
        "ledger_column_name": column_name,
        "ledger_column_order": column_order,
        "presentation_rule": presentation_rule,
    }
    for column in provenance_columns:
        value = source[column]
        cell[column] = None if pd.isna(value) else value
    return cell


def build_ledger_cells(source_service: pd.DataFrame) -> pd.DataFrame:
    cells: list[dict[str, Any]] = []
    distributed_services = [
        service for service in SERVICE_ROWS if service.code not in {"public_health", "investment"}
    ]

    for service in distributed_services:
        for funding_code, funding_name, funding_order in FUNDING_COLUMNS[:8]:
            source = _one(
                source_service, service_code=service.code, funding_code=funding_code
            )
            cells.append(
                _cell_from_source(
                    source,
                    row_code=service.code,
                    row_name=service.name,
                    row_order=service.ledger_order or 0,
                    column_code=funding_code,
                    column_name=funding_name,
                    column_order=funding_order,
                )
            )
        total_source = _one(
            source_service, service_code=service.code, funding_code="all_sources"
        )
        cells.append(
            _cell_from_source(
                total_source,
                row_code=service.code,
                row_name=service.name,
                row_order=service.ledger_order or 0,
                column_code="total",
                column_name="Total",
                column_order=999,
            )
        )

    public_health = SERVICES["public_health"]
    public_health_source = _one(
        source_service, service_code="public_health", funding_code="all_sources"
    )
    for column_code, column_name, column_order in (
        (
            "government_public_health_activities",
            "Government Public Health Activities",
            90,
        ),
        ("total", "Total", 999),
    ):
        cells.append(
            _cell_from_source(
                public_health_source,
                row_code=public_health.code,
                row_name=public_health.name,
                row_order=public_health.ledger_order or 0,
                column_code=column_code,
                column_name=column_name,
                column_order=column_order,
                presentation_rule=(
                    "direct CMS public-health service total; CMS Table 4 presents this "
                    "as the Government Public Health Activities NHE component"
                ),
            )
        )

    investment = SERVICES["investment"]
    investment_source = _one(source_service, service_code="nhe", funding_code="investment")
    for column_code, column_name, column_order in (
        ("investment", "Investment", 100),
        ("total", "Total", 999),
    ):
        cells.append(
            _cell_from_source(
                investment_source,
                row_code=investment.code,
                row_name=investment.name,
                row_order=investment.ledger_order or 0,
                column_code=column_code,
                column_name=column_name,
                column_order=column_order,
                presentation_rule=(
                    "direct CMS Investment component reported in the total-NHE panel"
                ),
            )
        )

    for funding_code, funding_name, funding_order in FUNDING_COLUMNS:
        source = _one(source_service, service_code="nhe", funding_code=funding_code)
        cells.append(
            _cell_from_source(
                source,
                row_code="total",
                row_name="Total National Health Expenditures",
                row_order=999,
                column_code=funding_code,
                column_name=funding_name,
                column_order=funding_order,
            )
        )
    nhe_total = _one(source_service, service_code="nhe", funding_code="all_sources")
    cells.append(
        _cell_from_source(
            nhe_total,
            row_code="total",
            row_name="Total National Health Expenditures",
            row_order=999,
            column_code="total",
            column_name="Total",
            column_order=999,
        )
    )

    dataframe = pd.DataFrame.from_records(cells).sort_values(
        ["ledger_row_order", "ledger_column_order"], ignore_index=True
    )
    for column in STRING_COLUMNS.intersection(dataframe.columns):
        dataframe[column] = pd.array(dataframe[column], dtype="string")
    for column, dtype in NULLABLE_INTEGER_COLUMNS.items():
        if column in dataframe:
            dataframe[column] = pd.array(dataframe[column], dtype=dtype)
    for column in LEDGER_CELL_STRING_COLUMNS:
        dataframe[column] = pd.array(dataframe[column], dtype="string")
    for column in ("ledger_row_order", "ledger_column_order"):
        dataframe[column] = pd.array(dataframe[column], dtype="Int16")
    return dataframe


def build_wide_ledger(cells: pd.DataFrame) -> pd.DataFrame:
    column_names = [name for _, name, _ in FUNDING_COLUMNS] + ["Total"]
    rows: list[dict[str, Any]] = []
    row_definitions = [
        (service.code, service.name, service.ledger_order or 0) for service in SERVICE_ROWS
    ] + [("total", "Total National Health Expenditures", 999)]
    for row_code, row_name, row_order in row_definitions:
        record: dict[str, Any] = {
            "service_category_code": row_code,
            "Service": row_name,
            "service_sort_order": row_order,
        }
        selected = cells[cells["ledger_row_code"] == row_code]
        values = dict(zip(selected["ledger_column_name"], selected["amount_usd"], strict=True))
        for column_name in column_names:
            record[column_name] = values.get(column_name, pd.NA)
        rows.append(record)
    dataframe = pd.DataFrame.from_records(rows)
    dataframe["service_category_code"] = pd.array(
        dataframe["service_category_code"], dtype="string"
    )
    dataframe["Service"] = pd.array(dataframe["Service"], dtype="string")
    dataframe["service_sort_order"] = pd.array(
        dataframe["service_sort_order"], dtype="Int16"
    )
    for column_name in column_names:
        dataframe[column_name] = pd.array(dataframe[column_name], dtype="Int64")
    return dataframe


def _billions(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"${int(value) / 1_000_000_000:,.3f}B"


def write_markdown_ledger(wide: pd.DataFrame) -> None:
    display = wide.drop(columns=["service_category_code", "service_sort_order"]).copy()
    for column in display.columns[1:]:
        display[column] = display[column].map(_billions)
    lines = [
        "# 2024 National Healthcare Claims Ledger",
        "",
        "Current-dollar amounts. Displayed in billions to three decimals; canonical CSV/Parquet "
        "store exact USD converted from CMS's reported integer millions.",
        "",
        display.to_markdown(index=False),
        "",
        "Blank cells are structurally outside the applicable CMS panel, not reported zeroes. "
        "The long-form companion file contains cell-level source provenance.",
        "",
    ]
    LEDGER_MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_ledger_summary(source_service: pd.DataFrame, sponsor: pd.DataFrame) -> None:
    def amount(service_code: str, funding_code: str) -> int:
        value = _one(
            source_service, service_code=service_code, funding_code=funding_code
        )["amount_usd"]
        return int(value)

    def dollars(value: int) -> str:
        return f"${value / 1_000_000_000:,.3f} billion"

    nhe = amount("nhe", "all_sources")
    hce = amount("hce", "all_sources")
    phc = amount("phc", "all_sources")
    investment = amount("nhe", "investment")
    other_and_public = amount("nhe", "other_third_party_payers_programs") + amount(
        "nhe", "government_public_health_activities"
    )
    sponsor_2024 = sponsor[sponsor["year"] == 2024].set_index("sponsor_code")
    sponsor_leaf_sum = int(
        sponsor_2024[sponsor_2024["include_in_sponsor_sum"]]["amount_usd"].sum()
    )
    sponsor_total = int(sponsor_2024.loc["all_sponsors", "amount_usd"])
    lines = [
        "# Ledger summary",
        "",
        "Neutral accounting observations from the CMS 2024 NHEA vintage:",
        "",
        f"1. Reported 2024 National Health Expenditures are {dollars(nhe)}.",
        f"2. Health Consumption Expenditures are {dollars(hce)}; Investment is {dollars(investment)}.",
        f"3. Personal Health Care is {dollars(phc)}.",
        f"4. Health Insurance is {dollars(amount('nhe', 'health_insurance'))}.",
        f"5. Private Health Insurance is {dollars(amount('nhe', 'private_health_insurance'))}.",
        f"6. Medicare is {dollars(amount('nhe', 'medicare'))}; Medicaid is {dollars(amount('nhe', 'medicaid'))}.",
        f"7. Out-of-pocket spending is {dollars(amount('nhe', 'out_of_pocket'))}.",
        (
            "8. Other Third Party Payers and Programs plus Government Public Health "
            f"Activities are {dollars(other_and_public)}; the ledger retains them as separate CMS rows."
        ),
        f"9. Hospital Care is {dollars(amount('hospital_care', 'all_sources'))}.",
        (
            "10. Physician and Clinical Services are "
            f"{dollars(amount('physician_clinical_services', 'all_sources'))}."
        ),
        f"11. Retail Prescription Drugs are {dollars(amount('prescription_drugs', 'all_sources'))}.",
        (
            "12. The separate sponsor view reports "
            f"{dollars(sponsor_total)} after rounding to $0.1 billion; its five leaf sponsors "
            f"sum to {dollars(sponsor_leaf_sum)}."
        ),
        "",
        "These are parallel accounting descriptions, not policy findings. Sponsor amounts are not "
        "added to payer/service amounts.",
        "",
    ]
    LEDGER_SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def load_ledger_into_duckdb() -> None:
    with duckdb.connect(str(DUCKDB_PATH)) as connection:
        connection.execute(
            "CREATE OR REPLACE TABLE national_ledger_2024_cells AS SELECT * FROM read_parquet(?)",
            [str(LEDGER_CELLS_PARQUET_PATH)],
        )
        connection.execute(
            "CREATE OR REPLACE TABLE national_ledger_2024 AS SELECT * FROM read_parquet(?)",
            [str(LEDGER_PARQUET_PATH)],
        )


def build_ledger() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SOURCE_SERVICE_PATH.exists() or not SPONSOR_PATH.exists():
        normalize_all()
    source_service = pd.read_parquet(SOURCE_SERVICE_PATH)
    sponsor = pd.read_parquet(SPONSOR_PATH)
    cells = build_ledger_cells(source_service)
    wide = build_wide_ledger(cells)
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    cells.to_csv(LEDGER_CELLS_CSV_PATH, index=False)
    cells.to_parquet(LEDGER_CELLS_PARQUET_PATH, index=False)
    wide.to_csv(LEDGER_CSV_PATH, index=False, na_rep="")
    wide.to_parquet(LEDGER_PARQUET_PATH, index=False)
    write_markdown_ledger(wide)
    write_ledger_summary(source_service, sponsor)
    load_ledger_into_duckdb()
    return wide, cells


def main() -> None:
    normalize_all()
    wide, cells = build_ledger()
    from reconciliation_healthcare.validation import validate_and_write_report

    results = validate_and_write_report()
    failed = [result for result in results if not result["passed"]]
    if failed:
        raise SystemExit(f"{len(failed)} reconciliation checks failed")
    print(f"Wrote {len(wide)} ledger rows to {LEDGER_CSV_PATH} and {LEDGER_PARQUET_PATH}")
    print(f"Wrote {len(cells)} provenance records to {LEDGER_CELLS_PARQUET_PATH}")
    print("All reconciliation checks passed.")


if __name__ == "__main__":
    main()
