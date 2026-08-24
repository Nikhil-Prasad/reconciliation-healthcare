# Rulebook ontology

Portable Parquet is canonical. The same five tables are loaded into the
existing `data/processed/healthcare.duckdb`, alongside the Stage 1 tables.

## `payment_rules`

One row is an effective version of a policy or calculation rule. `rule_id` is
unique and traces select it directly. Controlled dimensions are:

- `rule_type`: classification, base rate, lookup, multiplier, add-on,
  reduction, geographic or setting adjustment, packaging, eligibility,
  exclusion, cost sharing, budget neutrality, quality adjustment, or outlier.
- `policy_function`: a conservative functional label such as resource pricing,
  geographic adjustment, site of service, safety net, teaching subsidy,
  uncompensated care, innovation subsidy, quality incentive, utilization
  control, or unknown.
- `execution_status`: `executable`, `lookup_only`, `documented_only`, or
  `deferred`.

`legal_authority`, `regulatory_authority`, `source_artifact_id`, and
`source_locator` keep the authority chain separate from executable code.

## `rule_edges`

Edges make dependencies explicit. `depends_on` is required for a base path;
`may_add` and `may_apply` identify omitted claim/provider adjustments;
`routes_to` and `may_combine_with` represent site-of-service paths. Every edge
endpoint is a valid `rule_id`.

## `rule_parameters`

Parameters hold effective values outside rule logic. Stage 2A contains PFS
conversion factors and locality GPCIs, plus IPPS standardized amounts,
provider wage indexes, and separately identified transition/out-migration
values. `parameter_id` is unique. Numeric value, unit, key, interval, source
artifact, source cell/member locator, and value status are retained.

## `code_assignments`

This table holds code-specific numeric/status values without copyrighted CPT
descriptions:

- PFS HCPCS/modifier RVUs and payment-policy indicators;
- OPPS HCPCS status indicator, APC, relative weight, and published rate;
- IPPS MS-DRG relative weight.

`value_status` is operational. `unresolved_effective_date` and
`requires_restated_drug_overlay` are not silently treated as normal published
values by an executable path.

## `source_artifacts`

This is the normalized form of `data/raw/cms_payment_rules/manifest.json`.
It records CMS authority, payment system, dataset, original/local filename,
landing page and download URL, download and HTTP metadata, release, inclusive
effective interval, SHA-256, byte count, and description. Raw bytes stay local
and are excluded from Git.

## Traces

Every supported result is a `PaymentTrace` with inputs, service date, selected
rule versions, selected parameter/assignment identifiers, components, a
precisely labeled amount (if any), omitted adjustments, warnings, and source
artifact identifiers. `UNSUPPORTED` traces have no calculated amount and state
the missing or unsupported rule explicitly.
