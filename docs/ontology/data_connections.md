# Data connection inventory

Review date: 2026-09-05. This is a feasibility inventory, not an implemented
crosswalk or an expanded data-ingestion manifest. Candidate source documentation
can change; a later implementation must select and pin its actual release.

## Connections supported by the current repository

| Connection | Existing evidence | Supported operation | Boundary |
|---|---|---|---|
| NHEA source cell → normalized observation → ledger cell | Source-cell provenance and fixed hierarchy | Explain a reported aggregate and reproduce its unit conversion | No individual payment records or recipient identity |
| NHEA sponsor totals ↔ source/service totals | Two accounting views with reconciliation to national totals | Compare views at supported aggregate levels | No complete joint sponsor × payer × service distribution |
| Code/context → effective rule/parameter/assignment → trace | Rulebook and source-link tables | Reproduce supported base amounts or rate lookups | Neither utilization nor observed paid amounts |
| IPPS CCN/date → provider wage parameter | Pinned provider wage-index tables | Resolve the provider-specific input for the supported fiscal year | No ownership, clinical outcome, or cost observation follows from the identifier |

## Candidate next connections

| Candidate | What a small investigation would establish | Keys and grain to verify | Blocking inference to avoid |
|---|---|---|---|
| Physician utilization/payment aggregates ↔ PFS benchmarks | Whether a chosen release permits a comparable provider/service/setting analysis | Rendering NPI, HCPCS, setting, reporting year; inspect aggregate definition, suppression, and payment fields | An annual mean is not a fully specified claim; it need not equal a single-date base formula |
| Hospital cost reports ↔ IPPS provider parameters | Whether reported provider characteristics and cost centers can be aligned to a payment period | Report identifier, provider identifier, fiscal-period start/end, report version/status, worksheet/cell | Provider annual cost cannot be treated as case-level resource cost without an allocation model |
| Hospital quality data ↔ provider observations | Which selected measures have usable periods, denominators, exclusions, and identifier mappings | Verify facility-ID system, measure ID, population and measurement period in the selected dictionary | Matching hospital IDs does not establish matched patients, temporal alignment, or causal effects |
| Observed provider activity ↔ national accounting | Whether a bounded subset has a documented aggregation bridge | Program coverage, provider/billing category, period, non-claim revenue, adjustments | Medicare FFS activity is not the entire NHEA Medicare category or total hospital revenue |

CMS documents HCRIS as provider annual reporting that includes utilization,
costs/charges by cost center, settlement information, and financial statements.
That makes it a candidate for provider accounting context. It does not by
itself supply an efficient production frontier or patient-level costs.
[CMS cost-report overview](https://www.cms.gov/data-research/statistics-trends-and-reports/cost-reports)

For physician aggregates, CMS identifies rendering NPI in the
[provider-and-service dictionary](https://data.cms.gov/resources/medicare-physician-other-practitioners-by-provider-and-service-data-dictionary).
The [methodology resource](https://data.cms.gov/resources/medicare-physician-other-practitioners-methodology-2022)
is a starting point for coverage questions, not a pinned release for this
project. A matching 2024 source and its exact fields still need inspection.

The [hospital data catalog entry](https://data.cms.gov/provider-data/dataset/xubh-q36u)
is a discovery pointer. Its landing page did not expose a readable dictionary
in this review, so specific keys, measure availability, and join validity are
not treated as verified here.

## A bounded autonomous investigation

Select one source family and return:

1. The actual source, release, license/access conditions, and exact dictionary.
2. A minimal sample with documented observation unit, identifiers, amount
   meanings, reporting periods, and null/suppression statuses.
3. Candidate joins, expected cardinalities, duplicate/unmatched rates, and
   evidence supporting every identifier crosswalk.
4. One answerable question and a list of questions that remain unidentified.

Do not choose a cost benchmark or assign waste, rent, or fraud labels during
this source-feasibility work. Those are separate analytical decisions.
