# U.S. Healthcare Claims Ledger v0.1

An auditable financial baseline built exclusively from the Centers for Medicare &
Medicaid Services (CMS) National Health Expenditure Accounts (NHEA), 1960–2024.

This repository is deliberately limited to Stage 1: source archival, source
inspection, normalization, provenance, and reconciliation. It does not estimate
waste, rents, margins, fraud, or counterfactual prices, and it makes no policy
recommendations.

## Reproduce the ledger

```bash
make reproduce
```

This uses the committed `uv.lock` in locked mode to install dependencies, archive
sources, inspect them, rebuild every ledger artifact, and run the test suite. The
individual `hcl-*` commands resolve paths from the project checkout, so they also
work when invoked from another directory (or with `HCL_PROJECT_ROOT` explicitly
set to a checkout).

Generated outputs are documented in `docs/reconciliation_report.md`. Raw files
under `data/raw/cms_nhea/` are preserved byte-for-byte as downloaded; the
machine-readable manifest records their source URLs, sizes, timestamps, and
SHA-256 checksums.

Raw CMS downloads, processed Parquet files, DuckDB databases, and cell-level CSV
exports are deliberately excluded from Git. The repository tracks the checksum
manifest, code, tests, documentation, and small human-readable 2024 ledger
deliverables; `make reproduce` reconstructs the excluded artifacts locally.

## Principal artifacts

- `data/processed/nhea_source_service_1960_2024.parquet` — 34,970 long-form
  source/service observations, preserving explicit not-applicable dashes and
  structural source blanks as distinct null statuses.
- `data/processed/nhea_sponsor_1987_2024.parquet` — separate 1987–2024 sponsor
  view.
- `data/processed/healthcare.duckdb` — queryable copies of both views and the 2024
  outputs. It is a generated convenience layer; Parquet is the portable canonical
  format and DuckDB is verified by logical table content/schema rather than a
  binary checksum.
- `outputs/ledger_2024/national_ledger_2024.csv` and `.parquet` — clean 2024
  matrix in current USD, converted exactly from CMS-reported integer millions.
- `outputs/ledger_2024/national_ledger_2024_cells.csv` and `.parquet` — cell-level
  ledger provenance.
- `docs/ontology.md`, `docs/nhea_notes.md`, `docs/sources.md`, and
  `docs/reconciliation_report.md` — data model, source inspection, authority, and
  reconciliation decisions.

The build deliberately stops at the national baseline. Sponsor and payer/source
views remain separate; nulls are not converted to zero; and no waste, rent, margin,
fraud, or policy classifications are introduced.
