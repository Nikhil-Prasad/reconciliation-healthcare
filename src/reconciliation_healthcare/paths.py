"""Repository-rooted paths shared by the command-line entry points."""

from __future__ import annotations

import os
from pathlib import Path


def _project_root() -> Path:
    """Locate the checkout independently of the caller's working directory."""
    configured = os.environ.get("HCL_PROJECT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()

    source_path = Path(__file__).resolve()
    for candidate in source_path.parents:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src" / "reconciliation_healthcare"
        ).is_dir():
            return candidate
    raise RuntimeError(
        "Could not locate the reconciliation-healthcare project root. "
        "Set HCL_PROJECT_ROOT to the checkout path."
    )


PROJECT_ROOT = _project_root()

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "cms_nhea"
MANIFEST_PATH = RAW_DIR / "manifest.json"
INVENTORY_PATH = PROJECT_ROOT / "data" / "interim" / "nhea_inventory.json"

RULEBOOK_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "cms_payment_rules"
RULEBOOK_MANIFEST_PATH = RULEBOOK_RAW_DIR / "manifest.json"
RULEBOOK_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "rulebook"
PAYMENT_RULES_PATH = RULEBOOK_PROCESSED_DIR / "payment_rules.parquet"
RULE_EDGES_PATH = RULEBOOK_PROCESSED_DIR / "rule_edges.parquet"
RULE_PARAMETERS_PATH = RULEBOOK_PROCESSED_DIR / "rule_parameters.parquet"
CODE_ASSIGNMENTS_PATH = RULEBOOK_PROCESSED_DIR / "code_assignments.parquet"
SOURCE_ARTIFACTS_PATH = RULEBOOK_PROCESSED_DIR / "source_artifacts.parquet"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SOURCE_SERVICE_PATH = PROCESSED_DIR / "nhea_source_service_1960_2024.parquet"
SPONSOR_PATH = PROCESSED_DIR / "nhea_sponsor_1987_2024.parquet"
DUCKDB_PATH = PROCESSED_DIR / "healthcare.duckdb"

LEDGER_DIR = PROJECT_ROOT / "outputs" / "ledger_2024"
LEDGER_CSV_PATH = LEDGER_DIR / "national_ledger_2024.csv"
LEDGER_PARQUET_PATH = LEDGER_DIR / "national_ledger_2024.parquet"
LEDGER_CELLS_CSV_PATH = LEDGER_DIR / "national_ledger_2024_cells.csv"
LEDGER_CELLS_PARQUET_PATH = LEDGER_DIR / "national_ledger_2024_cells.parquet"
LEDGER_MARKDOWN_PATH = LEDGER_DIR / "national_ledger_2024.md"
LEDGER_SUMMARY_PATH = LEDGER_DIR / "ledger_summary.md"

REPORT_PATH = PROJECT_ROOT / "docs" / "reconciliation_report.md"

RULEBOOK_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "rulebook_2024"
RULE_CATALOG_CSV_PATH = RULEBOOK_OUTPUT_DIR / "rule_catalog.csv"
RULE_EDGES_CSV_PATH = RULEBOOK_OUTPUT_DIR / "rule_edges.csv"
RULEBOOK_VALIDATION_REPORT_PATH = RULEBOOK_OUTPUT_DIR / "validation_report.md"
RULEBOOK_EXAMPLE_TRACES_DIR = RULEBOOK_OUTPUT_DIR / "example_traces"
