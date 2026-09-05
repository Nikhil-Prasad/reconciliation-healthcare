# Rulebook ontology

Portable Parquet is canonical. The same six tables are loaded into the
existing `data/processed/healthcare.duckdb`, alongside the Stage 1 tables.

## `payment_rules`

One row is an effective version of a policy or calculation rule. `rule_id` is
unique and traces select it directly. Controlled dimensions are:

- `rule_type`: classification, base rate, lookup, multiplier, add-on,
  reduction, geographic or setting adjustment, packaging, eligibility,
  exclusion, cost sharing, budget neutrality, quality adjustment, outlier,
  or composition.
- `policy_function`: a conservative functional label such as resource pricing,
  geographic adjustment, site of service, safety net, teaching subsidy,
  uncompensated care, innovation subsidy, quality incentive, utilization
  control, composite, or unknown. These describe interpreted functions, not
  demonstrated causal effects. Final-payment assembly uses `composite` so an
  aggregate does not inherit only the function of its base component.
- `execution_status`: `executable`, `lookup_only`, `documented_only`, or
  `deferred`.

`deferred` means that the rule is recognized, versioned over its truthful
effective period, and provenance-backed, but is not executable. It is not a
calendar-neutral placeholder.

`legal_authority` and `regulatory_authority` keep policy authority separate
from executable code. The retained `source_artifact_id` and `source_locator`
columns are convenient direct pointers (normally the primary numeric source);
the authoritative relationship is the many-to-many link table described
below.

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

## `entity_source_links`

This table is the authoritative provenance relationship:

```text
rule / parameter / assignment
    → entity_source_links
    → source_artifacts
```

Every canonical rule, parameter, and assignment has at least one link. The
controlled `entity_type` values are `rule`, `parameter`, and `assignment`.
`source_role` distinguishes `primary_numeric_authority`, `legal_authority`,
`regulatory_authority`, `implementation_guidance`, `correction`,
`retroactive_correction`, `superseding_release`, `validation_reference`, and
`supporting_documentation`. Link intervals describe the entity value for which
the relationship applies. Natural-key and source-link duplicates are rejected.

This design permits a corrected value to retain its original snapshot, numeric
replacement, and correction authority as separate queryable relationships
rather than packing several identifiers into one string.

## Traces

Every supported result is a `PaymentTrace` with inputs, service date, selected
rule versions, selected parameter/assignment identifiers, components, a
precisely labeled amount (if any), omitted adjustments, warnings, and source
artifact identifiers. `source_links` exposes the compact, role-labeled,
service-date-active relationships used to construct the complete deduplicated
`source_artifact_ids` set. A canonical store fails rather than emit a supported
trace whose selected entity lacks an active link. `UNSUPPORTED` traces have no
calculated amount and state the missing or unsupported rule explicitly.

Traces also carry controlled `amount_kind`, `payment_unit`, and `date_basis`
fields. The nullable quantity remains USD; the legacy `service_date` key is
interpreted using the date basis, which is `discharge_date` for IPPS. Supported
OPPS lookups can have a null amount with a known amount kind. Unsupported
attempts retain the unit/date basis but expose no amount kind or numeric amount.
`validate_trace` rejects inconsistent system/status/amount/date combinations.
The exact mapping and compatibility implications are in the
[semantic contract](../ontology/decisions.md), with
[worked examples](../ontology/worked_examples.md) generated from the traces.
