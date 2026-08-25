# Stage 2A scope

Stage 2A is an effective-dated Medicare fee-for-service payment rulebook for
calendar year 2024. It extends the Stage 1 national accounting ledger; it does
not replace or reinterpret any Stage 1 category, null, provenance, or
reconciliation rule.

The implemented boundary is deliberately narrow:

- Physician Fee Schedule (PFS): the geographically adjusted professional base
  formula, explicit facility/nonfacility practice-expense RVUs, 2024 GPCIs,
  and the March 9 conversion-factor change.
- Hospital Outpatient PPS (OPPS): an effective quarterly HCPCS → status
  indicator → APC → published national unadjusted rate lookup. Packaging and
  comprehensive-APC semantics are visible, but full claims are not adjudicated.
- Acute Inpatient PPS (IPPS): MS-DRG as an input, corrected relative weights,
  provider wage index, labor/nonlabor standardized amounts, and the ordinary
  base operating payment. The resolver switches fiscal years on October 1.

The outputs are rule and parameter artifacts, not claims, utilization,
provider-margin, or policy-savings estimates. No HCRIS analysis, Medicare
Advantage, Part D, ICD-to-MSDRG grouper, ASC payment engine, fraud analysis,
waste classification, or counterfactual pricing is in scope.

The calculated PFS and IPPS amounts have precise labels: respectively,
`PFS base payment before claim-level adjustments` and
`IPPS base operating payment before transfer/provider/claim adjustments`.
An OPPS amount is a `published national unadjusted OPPS payment rate`, not a
final claim payment.

Unsupported mechanics fail closed. A partial or stale-looking number is never
substituted for a missing rule, ambiguous interval, unresolved code-level
effective date, or required provider/claim adjustment.
