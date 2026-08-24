# Stage 2A validation report

**Result: 13/13 checks passed.**

## Checks

- **PASS — Source integrity:** 26 CMS artifacts exist and match pinned byte counts/SHA-256 values.
- **PASS — Source family coverage:** PFS, quarterly OPPS, FY2024 IPPS, and FY2025 IPPS core families are pinned.
- **PASS — Primary/foreign keys:** Unique keys and rule/source foreign keys pass across 74 rules, 9,239 parameters, and 167,302 assignments.
- **PASS — Controlled vocabularies:** Controlled taxonomies pass; rule status counts are deferred=24, documented_only=4, executable=38, lookup_only=8.
- **PASS — Temporal coverage:** PFS/OPPS calendar boundaries and the September 30/October 1 IPPS switch are contiguous.
- **PASS — Direct parameter checks:** 12 direct CMS parameter cells/rows match.
- **PASS — PFS independent formula validation:** Four PFS amounts reproduce independent CMS Alabama carrier-file values exactly to cents.
- **PASS — OPPS lookup validation:** Separate, packaged, and comprehensive-APC Addendum B paths resolve with non-final labels.
- **PASS — IPPS formula/boundary validation:** MS-DRG 039/CCN 050008 reproduces $11,796.30 (FY2024) and $11,519.08 (FY2025 IFC).
- **PASS — Fail-closed behavior:** Anesthesia, unresolved OPPS dates, and IPPS out-migration all return UNSUPPORTED without amounts.
- **PASS — Trace foreign keys:** Executed trace rule, parameter/assignment, and artifact identifiers resolve to canonical tables.
- **PASS — Integrated DuckDB:** Stage 1 and Stage 2 logical tables coexist in healthcare.duckdb with matching row counts.
- **PASS — Copyright boundary:** Normalized code/parameter schemas contain no CPT/HCPCS description fields.

## Artifact coverage

- Payment rules: 74
- Rule parameters: 9,239
- Code assignments: 167,302
- Source artifacts: 26
- Rule execution statuses: deferred=24, documented_only=4, executable=38, lookup_only=8

Changed quarterly rows without normalized row-specific dates are deliberately not counted as executable coverage. Assignment statuses:

- IPPS / `published_correction_notice`: 771
- IPPS / `published_final`: 764
- OPPS / `published_cr_effective_date`: 3
- OPPS / `published_quarter_snapshot`: 70,098
- OPPS / `published_retroactive_correction`: 1
- OPPS / `requires_restated_drug_overlay`: 870
- OPPS / `unresolved_effective_date`: 1,903
- PFS / `published`: 92,673
- PFS / `published_cr_effective_date`: 4
- PFS / `unresolved_effective_date`: 215

## Interpretation

The PFS and IPPS checks validate labeled base amounts, not final claims. The OPPS checks validate published national unadjusted lookup values and packaging context. Provider/claim adjustments listed in each trace remain outside Stage 2A.
