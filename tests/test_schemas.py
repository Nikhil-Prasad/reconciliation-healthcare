from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from reconciliation_healthcare.ledger import (
    LEDGER_CELLS_PARQUET_PATH,
    LEDGER_PARQUET_PATH,
)
from reconciliation_healthcare.normalize_nhea import (
    DUCKDB_PATH,
    SOURCE_SERVICE_PATH,
    SPONSOR_PATH,
)


LS = pa.large_string()
PROJECT_ROOT = Path(__file__).resolve().parents[1]

COMMON_FIELDS = [
    ("year", pa.int16()),
    ("amount_usd", pa.int64()),
    ("amount_unit", LS),
    ("service_category_code", LS),
    ("service_category_name", LS),
    ("service_category_parent", LS),
    ("funding_source_code", LS),
    ("funding_source_name", LS),
    ("sponsor_code", LS),
    ("sponsor_name", LS),
    ("program_code", LS),
    ("program_name", LS),
    ("recipient_code", LS),
    ("recipient_name", LS),
    ("claim_class", LS),
    ("accounting_view", LS),
    ("source_dataset", LS),
    ("source_file", LS),
    ("source_sheet", LS),
    ("source_row", pa.int16()),
    ("source_column", LS),
    ("source_label_raw", LS),
    ("value_status", LS),
    ("derivation", LS),
    ("source_release", LS),
    ("ingested_at", LS),
    ("source_value_raw", LS),
    ("source_unit", LS),
    ("source_display_precision_usd", pa.int64()),
    ("service_category_name_raw", LS),
    ("service_category_level", pa.int8()),
    ("service_category_is_subtotal", pa.bool_()),
    ("service_sort_order", pa.int16()),
    ("funding_source_parent", LS),
    ("funding_source_level", pa.int8()),
    ("funding_source_is_subtotal", pa.bool_()),
    ("funding_source_sort_order", pa.int16()),
]

SOURCE_SERVICE_SCHEMA = pa.schema(
    COMMON_FIELDS
    + [
        ("include_in_nhe_service_sum", pa.bool_()),
        ("include_in_service_funding_sum", pa.bool_()),
        ("observation_role", LS),
    ]
)

SPONSOR_SCHEMA = pa.schema(
    COMMON_FIELDS
    + [
        ("sponsor_parent", LS),
        ("sponsor_level", pa.int8()),
        ("sponsor_is_subtotal", pa.bool_()),
        ("include_in_sponsor_sum", pa.bool_()),
        ("include_in_nhe_service_sum", pa.bool_()),
        ("include_in_service_funding_sum", pa.bool_()),
        ("observation_role", LS),
    ]
)

LEDGER_SCHEMA = pa.schema(
    [
        ("service_category_code", LS),
        ("Service", LS),
        ("service_sort_order", pa.int16()),
        ("Out of pocket", pa.int64()),
        ("Private Health Insurance", pa.int64()),
        ("Medicare", pa.int64()),
        ("Medicaid", pa.int64()),
        ("CHIP", pa.int64()),
        ("Department of Defense", pa.int64()),
        ("Department of Veterans Affairs", pa.int64()),
        ("Other Third Party Payers and Programs", pa.int64()),
        ("Government Public Health Activities", pa.int64()),
        ("Investment", pa.int64()),
        ("Total", pa.int64()),
    ]
)

LEDGER_CELLS_SCHEMA = pa.schema(
    [
        ("ledger_row_code", LS),
        ("ledger_row_name", LS),
        ("ledger_row_order", pa.int16()),
        ("ledger_column_code", LS),
        ("ledger_column_name", LS),
        ("ledger_column_order", pa.int16()),
        ("presentation_rule", LS),
        ("amount_usd", pa.int64()),
        ("amount_unit", LS),
        ("value_status", LS),
        ("derivation", LS),
        ("accounting_view", LS),
        ("source_dataset", LS),
        ("source_file", LS),
        ("source_sheet", LS),
        ("source_row", pa.int16()),
        ("source_column", LS),
        ("source_label_raw", LS),
        ("source_value_raw", LS),
        ("source_unit", LS),
        ("source_display_precision_usd", pa.int64()),
        ("source_release", LS),
        ("ingested_at", LS),
    ]
)


def test_artifact_build_is_isolated_from_project_outputs(
    built_artifacts: dict[str, pd.DataFrame],
) -> None:
    build_root = SOURCE_SERVICE_PATH.parents[2].resolve()
    assert build_root != PROJECT_ROOT.resolve()
    for path in (
        SOURCE_SERVICE_PATH,
        SPONSOR_PATH,
        DUCKDB_PATH,
        LEDGER_PARQUET_PATH,
        LEDGER_CELLS_PARQUET_PATH,
    ):
        assert path.is_file()
        assert path.resolve().is_relative_to(build_root)


def test_parquet_artifacts_have_exact_arrow_schemas(
    built_artifacts: dict[str, pd.DataFrame],
) -> None:
    expected = {
        SOURCE_SERVICE_PATH: SOURCE_SERVICE_SCHEMA,
        SPONSOR_PATH: SPONSOR_SCHEMA,
        LEDGER_PARQUET_PATH: LEDGER_SCHEMA,
        LEDGER_CELLS_PARQUET_PATH: LEDGER_CELLS_SCHEMA,
    }
    for path, schema in expected.items():
        assert pq.read_schema(path).remove_metadata() == schema, path


def _duckdb_schema(arrow_schema: pa.Schema) -> list[tuple[str, str]]:
    type_names = {
        "bool": "BOOLEAN",
        "int8": "TINYINT",
        "int16": "SMALLINT",
        "int64": "BIGINT",
        "large_string": "VARCHAR",
    }
    return [(field.name, type_names[str(field.type)]) for field in arrow_schema]


def test_duckdb_tables_have_exact_column_schemas(
    built_artifacts: dict[str, pd.DataFrame],
) -> None:
    expected = {
        "nhea_source_service": SOURCE_SERVICE_SCHEMA,
        "nhea_sponsor": SPONSOR_SCHEMA,
        "national_ledger_2024": LEDGER_SCHEMA,
        "national_ledger_2024_cells": LEDGER_CELLS_SCHEMA,
    }
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as connection:
        for table, arrow_schema in expected.items():
            observed = [
                (row[0], row[1])
                for row in connection.execute(f'DESCRIBE "{table}"').fetchall()
            ]
            assert observed == _duckdb_schema(arrow_schema), table
