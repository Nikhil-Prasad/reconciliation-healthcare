# Concept dictionary

These definitions distinguish domain concepts from current storage fields.
"Future" means there is no canonical representation in the present data model.
Examples illustrate a meaning; they do not assign new classifications to CMS
observations. Payment codes are identifiers only; licensed descriptions are
not reproduced.

## Accounting and actor roles

The accounting definitions follow the [ledger ontology](../ontology.md) and
[CMS NHEA methodology](https://www.cms.gov/files/document/definitions-sources-methods.pdf).

| Concept | Meaning and example | Distinguish from | Current representation |
|---|---|---|---|
| Financial-flow observation | A published amount for a specified year, category crossing, and accounting view; for example Medicare × Hospital Care in 2024. | An individual transfer or adjudicated claim | Stage 1 normalized row with source-cell provenance |
| Accounting view | A perspective under which spending is organized. | An additional pool of spending to add to another view | `accounting_view`: source/service or sponsor |
| Funding source / payer category | The payer, program, or funding category represented in the CMS source view. | The ultimate economic bearer of the burden | `funding_source_code`; some national matrix columns are expenditure components, explicitly documented |
| Sponsor | Household, business, government, or other private financing attributed in the CMS sponsor account. | Payer category; economic incidence | Separate sponsor table, 1987–2024 |
| Economic incidence | How the burden ultimately falls through wages, taxes, premiums, returns, and other adjustments. | Sponsor accounting attribution | Future economic analysis |
| Provider / recipient | A person or organization receiving payment or delivering care in a specified role. | A service category or physical care location | Stage 1 `recipient` is null; IPPS uses explicit provider CCN context |
| Care setting | The context where a service is furnished; facility/nonfacility is one payment distinction. | Provider ownership; NHEA service category | PFS `input_context.setting` |
| Service category | A CMS accounting category shaped by establishment and billing boundaries. | A clinical procedure or a payment code | `service_category_code` and hierarchy |
| Program | A specifically identified program within the source's coverage. | A guessed split of a broad payer total | Stage 1 `program` remains null; rulebook scope is Medicare FFS |
| Subtotal | A reported rollup that overlaps its children. | An additional independent flow | Explicit hierarchy and additive-use flags |

In a simple fully insured employment arrangement, household and employer
contributions finance premiums, while an insurer makes covered provider
payments. These stages describe overlapping financing activity. NHEA sponsor
and payer views cannot be added together, and the current tables do not publish
a complete sponsor × payer × service cube.

## Care and billing objects

These are working analytical definitions. Only the limited payment units in
[rulebook scope](../rulebook/scope.md) are implemented.

| Concept | Meaning and example | Distinguish from | Current representation |
|---|---|---|---|
| Encounter | A particular interaction with care delivery. | Every separate bill arising from it | Future |
| Episode | A deliberately specified span of related care, potentially across encounters and providers. | An intrinsically fixed unit shared by all datasets | Future; requires explicit inclusion and time boundaries |
| Claim | A billing submission subject to coverage and payment adjudication. | Observed clinical reality or final remittance | Future; this is not the meaning of "claims" in the Stage 1 project name |
| Claim line | An item within a billing submission, carrying codes and other context. | An independently payable service in every system | Future; engines do not adjudicate complete claim lines |
| HCPCS identifier | A coded identifier used in payment assignments, such as `99213` or `C1734`. | A complete clinical description or complete payment context | `code_assignments.code`, with assignment type and dates |
| APC | An Ambulatory Payment Classification used in hospital outpatient payment. | A clinical encounter identifier; guaranteed separate payment | OPPS assignment and packaging context |
| MS-DRG | A Medicare Severity Diagnosis Related Group used to classify inpatient cases for payment. | A diagnosis code or the actual resources used by one patient | IPPS input and effective relative-weight assignment; no grouper |
| Payment unit | The object the current output concerns. | A comparable bundle across all systems | Typed `payment_unit` in traces |

## Monetary quantities

| Concept | Meaning | Current representation |
|---|---|---|
| Published rate | A value published for a specified payment context. It may precede provider and claim adjustments. | OPPS `opps_published_national_unadjusted_rate` |
| Base payment | A calculated component before omitted adjustments. | `pfs_base_payment` or `ipps_base_operating_payment` |
| Billed charge | The submitted amount requested by a biller. | Future |
| Allowed amount | An amount recognized after applicable pricing/adjudication rules; it must be defined for the source and payer. | Future; no base trace is relabeled as allowed amount |
| Paid amount | A recorded payment, with payer, payee, timing, and any reversal/recoupment treatment specified. | Future |
| Beneficiary liability | The patient's responsibility under the applicable coverage and cost-sharing rules. | Future |
| Provider accounting cost | Resources valued and allocated under a defined accounting method and reporting boundary. | Future |
| Economic resource cost | An estimate of opportunity cost under an explicit perspective and counterfactual. | Future; neither a fee schedule nor reported accounting cost establishes it alone |

All current trace amounts are USD. `amount_kind` specifies their meaning,
`payment_unit` specifies their grain, and `amount_label` remains the readable
explanation. An OPPS lookup can identify a valid assignment with a null amount:
packaging or a different payment path can make a separate published rate
inapplicable. Null is not a zero-dollar resource cost.

## Rules, evidence, and time

These definitions follow the [rulebook ontology](../rulebook/ontology.md) and
[temporal model](../rulebook/temporal_model.md).

| Concept | Meaning and example | Current representation |
|---|---|---|
| Payment rule | A version of a classification, calculation, or policy operation. | `payment_rules` |
| Parameter | An effective value supplied separately from logic, such as a conversion factor or locality index. | `rule_parameters` |
| Code assignment | Effective code-specific values, statuses, or group membership. | `code_assignments` |
| Dependency | A relationship between rules; required and potentially applicable adjustments have different edge types. | `rule_edges` |
| Policy function | A functional interpretation of a mechanism, such as teaching support; it is not evidence of the mechanism's effect. | `policy_function`; `composite` for final-payment assembly |
| Trace | The selected inputs, rules, values, components, limitations, and sources for a calculation or lookup. | `PaymentTrace`; not an observed remittance |
| Provenance | The evidence connecting an assertion/value to its source and location. | Source-cell fields in Stage 1; `entity_source_links` in Stage 2A |
| Date basis | Which real-world date selects the applicable rules. | `date_basis`: service date for PFS/OPPS, discharge date for IPPS |
| Effective interval | The period during which a version applies. | Inclusive `effective_start` / `effective_end` |
| Publication / knowledge time | When a release became available, relevant to historical reconstruction. | Source metadata partially records this; a complete as-of query is future work |
| Source vintage | The particular release whose estimates and definitions are being used. | Pinned manifests; historical NHEA revisions are not silently mixed |
| Execution status | Whether a rule is executable, lookup-only, documented-only, or deferred. | `execution_status`; separate from the status of one trace |
| Counterfactual | A specified alternative world or intervention used for comparison. | Future; it must name what changes and what is held fixed |

An executable rule can still reject particular inputs. A documented rule can
have strong source provenance while remaining unimplemented. A supported
lookup can return no numeric rate. These are separate dimensions of knowledge.
