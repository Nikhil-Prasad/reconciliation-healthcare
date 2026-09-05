# Ontology decisions and open choices

This is a reviewable record of the semantic foundation. Proposals below do not
authorize new economic labels on the national ledger.

## Implemented: explicit trace semantics

Every PFS, OPPS, and IPPS entry point now supplies `payment_unit` and
`date_basis`, including unsupported attempts. Supported traces also specify
`amount_kind`. Unsupported traces have no `amount_kind` and no amount.

| System | `amount_kind` on a supported result | `payment_unit` | `date_basis` |
|---|---|---|---|
| PFS | `pfs_base_payment` | `professional_service` | `service_date` |
| OPPS | `opps_published_national_unadjusted_rate` | `outpatient_hcpcs_lookup` | `service_date` |
| IPPS | `ipps_base_operating_payment` | `inpatient_discharge` | `discharge_date` |

An OPPS supported lookup with no separate published rate retains its amount
kind while `calculated_amount` stays null. The kind describes the nullable
quantity, not a claim that a numeric amount exists.

The historical `service_date` JSON key is retained for compatibility. For
IPPS its value has always been the discharge date; `date_basis` now makes this
explicit. New consumers should read both fields. Existing numeric formulas,
amount labels, rounding, and source selection are unchanged.

The three new keys are additive to serialized traces. Strict consumers must
allow or adopt them. Manually constructed traces must supply the correct
semantic fields to pass `validate_trace`. These fields do not establish
comparability across settings, populations, sources, or complete episodes.

## Implemented: composite payment assembly

The OPPS and both fiscal-year IPPS `final_payment` nodes are labeled
`rule_type=composition` and `policy_function=composite`. Their dependencies can include resource payment,
teaching support, safety-net support, and other adjustments. The aggregate
cannot safely inherit the resource-pricing interpretation of its base.

`composite` means assembly of components with potentially different functions.
It makes no claim about their magnitudes, desirability, or observed effects.
The nodes remain deferred. Existing component-level labels are retained as
functional interpretations, rather than causal findings.

## Proposed: replace a future single claim class with separate axes

Stage 1's reserved `claim_class` remains null. The suggested labels in the
original ontology overlap, so they should not become a mutually exclusive enum.
Before filling any classification, design separate sourced dimensions:

| Proposed dimension | Question to establish | Example alternatives, not assignments |
|---|---|---|
| Financing arrangement | Through what arrangement is spending financed? | Public program, insurance, direct household payment |
| Price-setting mechanism | How is the rate determined? | Administered formula, negotiated contract, other mechanism |
| Delivery ownership | Who owns the delivering entity during this period? | Public, private nonprofit, private for-profit |
| Risk allocation | Who bears which kind of financial uncertainty? | Government, plan, provider, household; risk type must be specified |
| Public support | Which explicit subsidy, guarantee, or support applies? | A sourced program-specific relationship, potentially multiple |

Financing, price setting, and ownership are not proxies for one another.
An absence of evidence does not justify a "private" or "no subsidy" label.
These axes require dated evidence, unknown states, and potentially multiple
relationships. They are not added as empty columns to canonical data yet.

## Proposed: distinguish interpretation from effect

Later economic claims should record the hypothesis, target population,
intervention or comparison, outcome, evidence, uncertainty, and potential
disconfirming results. A stated policy purpose, an analyst interpretation, and
an estimated causal effect should be separate assertions with their own sources.

Questions to settle together include the cost benchmark, the treatment of
access/quality trade-offs, and whether a proposed saving is a transfer between
actors or a release of real resources. A payment that conforms to law can still
create poor incentives; a payment above a base rate can finance an intended
additional function. Neither conclusion follows from the rate difference alone.

## Proposed: complete knowledge-time semantics

The current resolver selects effective dates and pinned correction precedence.
It does not reconstruct all releases available at every historical point.
A later `as_of_release` design needs immutable release identities, publication
and retrieval timestamps, supersession/correction relationships, and a rule
for selecting the knowledge set. Retrieval time must not stand in for legal
effective date or publication date.

Use two explicit questions in its eventual acceptance examples: "What is the
applicable value using the chosen corrected vintage?" and "What could have
been known using the releases available at the assessment time?" Do not add an
as-of API until the retained source history can answer both truthfully.

## Proposed: retain explicit inference boundaries

Before connecting datasets, document their population, observation unit,
identifier system, period, amount meaning, and coverage. Keep source estimates,
engine calculations, observed transfers, and economic estimates distinguishable.
Source release and missing-value status are part of a record's meaning.

The next empirical project should be chosen using the
[data connection inventory](data_connections.md), after agreeing on one
question whose required relationships can actually be established.
