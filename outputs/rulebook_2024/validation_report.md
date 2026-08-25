# Stage 2A.1 validation report

**Result: 15/15 checks passed.**

## Checks

- **PASS — Source integrity:** 32 official first-party artifacts exist and match pinned byte counts/SHA-256 values.
- **PASS — Source family coverage:** PFS, quarterly OPPS, FY2024 IPPS, and FY2025 IPPS core families are pinned.
- **PASS — Primary/foreign keys:** Unique keys and rule/source foreign keys pass across 84 rules, 9,239 parameters, and 167,302 assignments.
- **PASS — Many-to-many source provenance:** 184,112 valid entity-to-source links cover every canonical entity; 7,449 entities have multiple authoritative sources, including the three-artifact C9790 correction path.
- **PASS — Controlled vocabularies:** Controlled taxonomies pass; rule status counts are deferred=34, documented_only=4, executable=38, lookup_only=8.
- **PASS — Temporal coverage:** PFS/OPPS calendar boundaries and the September 30/October 1 IPPS switch are contiguous.
- **PASS — Direct parameter checks:** 12 direct CMS parameter cells/rows match.
- **PASS — PFS independent formula validation:** 40 independent CMS carrier-payment amounts reproduce exactly to cents across 4 codes, 5 localities, 5 engine-effective periods, and both settings, backed by 2 carrier effective ranges.
- **PASS — OPPS lookup validation:** Separate, packaged, and comprehensive-APC Addendum B paths resolve with non-final labels.
- **PASS — IPPS formula/boundary validation:** MS-DRG 039/CCN 050008 reproduces $11,796.30 (FY2024) and $11,519.08 (FY2025 IFC).
- **PASS — Expanded IPPS raw-table reconstruction:** 8 base-payment cases reconstruct directly from pinned raw CMS Tables 1/2/5 across 2 MS-DRGs, 2 geographies, both fiscal years, and labor-share branches 62, 67.6%. These are independent normalization/formula checks, not independently published claim amounts.
- **PASS — Fail-closed behavior:** Anesthesia, unresolved OPPS dates, and IPPS out-migration all return UNSUPPORTED without amounts.
- **PASS — Trace foreign keys:** Executed trace rule, parameter/assignment, linked-source, and artifact identifiers resolve to canonical tables.
- **PASS — Integrated DuckDB:** Stage 1 and Stage 2 logical tables coexist in healthcare.duckdb with matching row counts.
- **PASS — Copyright boundary:** Normalized code/parameter schemas contain no CPT/HCPCS description fields.

## Artifact coverage

- Payment rules: 84
- Rule parameters: 9,239
- Code assignments: 167,302
- Source artifacts: 32
- Entity-source links: 184,112
- Entities with multiple linked sources: 7,449
- Source roles: correction=4125, implementation_guidance=16, legal_authority=0, primary_numeric_authority=176587, regulatory_authority=28, retroactive_correction=1, superseding_release=3288, supporting_documentation=62, validation_reference=5
- Rule execution statuses: deferred=34, documented_only=4, executable=38, lookup_only=8

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

PFS carrier cases independently reproduce published payment outputs. IPPS raw-table cases independently test normalization and formula reconstruction, but are not separate published claim-payment comparisons. Direct parameter checks and structural checks are labeled separately above. All PFS/IPPS amounts remain base amounts rather than final claims; OPPS remains a published national unadjusted lookup. Provider/claim adjustments listed in each trace remain outside Stage 2A.
