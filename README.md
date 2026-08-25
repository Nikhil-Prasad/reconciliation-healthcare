# U.S. Healthcare Claims Ledger and Medicare FFS Rulebook

An auditable financial baseline built exclusively from the Centers for Medicare &
Medicaid Services (CMS) National Health Expenditure Accounts (NHEA), 1960–2024.

Stage 1 builds the national accounting baseline. Stage 2A adds an auditable,
effective-dated CY2024 Medicare fee-for-service core payment rulebook for PFS,
OPPS, and IPPS. Neither stage estimates waste, rents, margins, fraud, or
counterfactual prices, and neither makes policy recommendations.

## Reproduce everything

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

To run one stage independently:

```bash
make reproduce-stage1
make reproduce-rulebook
```

Stage 2A downloads only the pinned CMS rule files listed in
`data/raw/cms_payment_rules/manifest.json`, builds canonical Parquet rule,
parameter, assignment, edge, and source-artifact tables, loads them into the
same `healthcare.duckdb`, emits example payment traces, and runs multi-level
validation. See `docs/rulebook/scope.md` and
`outputs/rulebook_2024/validation_report.md` for the exact executable boundary.

Raw rule archives, processed Parquet, DuckDB, and all licensed CPT/HCPCS
descriptions remain uncommitted. Git contains the source manifest, high-level
code, tests, documentation, rule catalog/edges, validation report, and small
JSON traces only.

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

The Stage 1 build deliberately stops at the national baseline. Sponsor and payer/source
views remain separate; nulls are not converted to zero; and no waste, rent, margin,
fraud, or policy classifications are introduced.

## Stage 2A principal artifacts

- `data/processed/rulebook/payment_rules.parquet`, `rule_edges.parquet`,
  `rule_parameters.parquet`, `code_assignments.parquet`, and
  `source_artifacts.parquet`, plus `entity_source_links.parquet` — canonical
  portable rulebook tables with many-to-many provenance.
- `outputs/rulebook_2024/rule_catalog.csv` and `rule_edges.csv` — small,
  reviewable catalog deliverables.
- `outputs/rulebook_2024/example_traces/` — PFS, OPPS, IPPS, and fail-closed
  demonstrations with parameter/rule/source provenance.
- `docs/rulebook/` — scope, ontology, temporal semantics, source authority,
  system-specific mechanics, copyright boundary, and open questions.

The executable PFS and IPPS paths return labeled base amounts, not final claim
payments. OPPS returns a published national unadjusted lookup value and exposes
packaging/claim-context requirements. Ambiguous, unimplemented, or
insufficiently dated paths return `UNSUPPORTED` without a fabricated amount.
