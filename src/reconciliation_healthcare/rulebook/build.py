"""Build canonical Medicare FFS rulebook Parquet tables and integrated DuckDB views."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from reconciliation_healthcare.paths import (
    CODE_ASSIGNMENTS_PATH,
    DUCKDB_PATH,
    PAYMENT_RULES_PATH,
    RULEBOOK_PROCESSED_DIR,
    RULE_CATALOG_CSV_PATH,
    RULE_EDGES_CSV_PATH,
    RULE_EDGES_PATH,
    RULE_PARAMETERS_PATH,
    SOURCE_ARTIFACTS_PATH,
)
from reconciliation_healthcare.rulebook.graph import build_rule_graph
from reconciliation_healthcare.rulebook.normalize import normalize_sources


def _normalize_catalog_types(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ("effective_start", "effective_end"):
        result[column] = pd.to_datetime(result[column]).dt.date
    for column in result.columns:
        if column not in {"effective_start", "effective_end"}:
            result[column] = pd.array(result[column], dtype="string")
    return result


def _write_duckdb(paths: dict[str, Path]) -> None:
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(DUCKDB_PATH)) as connection:
        for table_name, path in paths.items():
            escaped_path = str(path).replace("'", "''")
            connection.execute(
                f'CREATE OR REPLACE TABLE "{table_name}" AS '
                f"SELECT * FROM read_parquet('{escaped_path}')"
            )


def build_rulebook() -> dict[str, int]:
    RULEBOOK_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    RULE_CATALOG_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    rules, edges = build_rule_graph()
    rules = _normalize_catalog_types(rules)
    edges = _normalize_catalog_types(edges)
    parameters, assignments, source_artifacts = normalize_sources()

    tables = {
        "payment_rules": (rules, PAYMENT_RULES_PATH),
        "rule_edges": (edges, RULE_EDGES_PATH),
        "rule_parameters": (parameters, RULE_PARAMETERS_PATH),
        "code_assignments": (assignments, CODE_ASSIGNMENTS_PATH),
        "source_artifacts": (source_artifacts, SOURCE_ARTIFACTS_PATH),
    }
    for frame, path in tables.values():
        frame.to_parquet(path, index=False)

    _write_duckdb({name: path for name, (_, path) in tables.items()})

    rules.to_csv(RULE_CATALOG_CSV_PATH, index=False)
    edges.to_csv(RULE_EDGES_CSV_PATH, index=False)
    return {name: len(frame) for name, (frame, _) in tables.items()}


def main() -> None:
    counts = build_rulebook()
    for table_name, row_count in counts.items():
        print(f"{table_name}: {row_count:,} rows")


if __name__ == "__main__":
    main()
