# Physician Fee Schedule execution

Stage 2A executes the ordinary, geographically adjusted Medicare Physician Fee
Schedule base-payment formula for calendar year 2024. It is deliberately not a
complete professional-claim adjudicator. Every successful result is labeled
`PFS base payment before claim-level adjustments`; any row that needs an
unimplemented pricing path fails closed without returning an amount.

The authoritative inputs are CMS's five 2024
[PFS Relative Value File releases](https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files),
the 2024 locality GPCIs within those releases, and CMS's effective conversion
factor. The implementation follows the formula and nearest-cent instruction in
the [Medicare Claims Processing Manual, chapter 12, section 20.1](https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/clm104c12.pdf).

## Formula and rounding

For an effective status-A HCPCS/modifier row and canonical locality, the engine
calculates:

```text
work component = work RVU × work GPCI
PE component   = selected PE RVU × PE GPCI
MP component   = malpractice RVU × malpractice GPCI

unrounded base payment =
    (work component + PE component + MP component)
    × conversion factor

base payment = unrounded base payment rounded to cents
```

All numeric inputs and intermediate components use decimal arithmetic. No
component is rounded before multiplication or summation. CMS directs that the
payment be rounded to the nearest cent; for deterministic exact-half-cent
handling, this implementation uses `Decimal.quantize(Decimal("0.01"),
ROUND_HALF_UP)` on the final amount only. `ROUND_HALF_UP` is the engine's
documented tie convention, not a claim that the cited CMS section separately
defines a half-cent tie rule.

The displayed total RVU is not used. The engine recomputes the geographically
adjusted total from the three component RVUs and their respective GPCIs.

## Facility and nonfacility setting

The caller must explicitly select `facility` or `nonfacility`. That choice
selects the corresponding practice-expense RVU:

```text
facility    → facility PE RVU × PE GPCI
nonfacility → nonfacility PE RVU × PE GPCI
```

Work RVU, malpractice RVU, the three GPCIs, and the conversion factor are
otherwise unchanged. The trace records the selected setting, PE RVU, each
geographically adjusted component, conversion factor, unrounded amount, and
final rounded amount. If CMS marks the requested setting not applicable, or
the setting-specific PE RVU is absent, the engine returns `unsupported`.

## Two independent timelines

The RVU snapshot timeline and the statutory conversion-factor timeline are
related but distinct.

### Snapshot selection

| Snapshot | Inclusive resolver interval | Official CMS release |
|---|---|---|
| RVU24A | 2024-01-01–2024-03-08 | [RVU24A](https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu24a) |
| RVU24AR | 2024-03-09–2024-03-31 | [RVU24AR](https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu24ar) |
| RVU24B | 2024-04-01–2024-06-30 | [RVU24B](https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu24b) |
| RVU24C | 2024-07-01–2024-09-30 | [RVU24C](https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu24c) |
| RVU24D | 2024-10-01–2024-12-31 | [RVU24D](https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu24d) |

The March 31 endpoint for RVU24AR is a resolver boundary: RVU24B becomes the
next quarterly code/RVU snapshot on April 1. It is not an endpoint for the
March statutory conversion-factor increase.

### Conversion factor

| Dates of service | Exact source value |
|---|---:|
| 2024-01-01–2024-03-08 | 32.7442 |
| 2024-03-09–2024-12-31 | 33.2875 |

CMS describes the March 9 statutory update on its
[Physician Fee Schedule overview](https://www.cms.gov/medicare/payment/fee-schedules/physician):
the 2.93 percent update applies to services furnished March 9 through December
31, replacing the earlier 1.25 percent update. Later quarterly snapshots repeat
the exact `33.2875` factor; they do not create new factor intervals. The initial
factor and budget-neutrality calculation are also documented in CMS's
[CY2024 final-rule small-entity compliance guide](https://www.cms.gov/files/document/cy2024-pfs-final-rule-small-entity-compliance-guide-1-23-24.pdf)
and on the [CMS-1784-F final-rule page](https://www.cms.gov/medicare/medicare-fee-service-payment/physicianfeesched/pfs-federal-regulation-notices/cms-1784-f).

For every date, the resolver requires exactly one effective code assignment,
one conversion factor, and one each of work, PE, and malpractice GPCI. Gaps,
overlaps, invalid endpoints, and missing endpoints fail closed.

## Code-row effective dates

A quarterly archive is a publication snapshot, not proof that every changed
code row became effective on the first day of that quarter. CMS quarterly
change requests contain heterogeneous dates, including retroactive dates and
dates within a quarter:

- [CR13529 / R12501CP](https://www.cms.gov/files/document/r12501cp.pdf) supports
  April changes, including the April 1 `J0576` status transition.
- [CR13624 / R12629CP](https://www.cms.gov/files/document/r12629cp.pdf) contains
  January, March, April, and July dates and establishes the July 1 activation of
  `G9037` and `G9038`.
- [CR13751 / R12774CP](https://www.cms.gov/files/document/r12774cp.pdf) and its
  [machine-readable attachment](https://www.cms.gov/files/zip/r12774cp1.zip)
  contain record dates including June 17, July 2, September 15, and October 1.
  The transmittal's October 7 implementation date is not substituted for those
  dates of service.

Normalization compares a code/modifier row with its preceding snapshot. A new
or changed row is executable at a quarterly boundary only when a normalized CMS
change-request fact supports that date. Otherwise its `value_status` is
`unresolved_effective_date`, and `calculate_pfs` refuses to produce a number.
This is intentionally stricter than treating all quarterly differences as
quarter-day-one changes.

## Executable boundary

The core path executes only when all of the following are true:

- an exact PFS HCPCS and modifier assignment resolves for the date of service;
- the assignment has a resolved effective date and published value status;
- the CMS status code is `A`;
- the requested facility/nonfacility PE value is applicable and present;
- work, selected PE, and malpractice RVUs are numeric;
- the canonical locality, such as `AL:00` or `NY:01`, resolves to all three
  GPCIs;
- one effective conversion factor resolves;
- the referenced base, RVU-component, GPCI, and conversion-factor rules are
  executable; and
- multiple-procedure, bilateral-surgery, assistant-at-surgery, co-surgery, and
  team-surgery indicators do not identify a specialized path. CMS indicator
  values `0` and `9` are treated as no applicable special adjustment.

Any other status fails closed. Status `J` returns `missing_rule=pfs.anesthesia`
rather than interpreting its zero RVUs as a zero-dollar payment. Other non-A
statuses, including contractor-priced or conditionally paid categories, do not
pass through the ordinary formula.

## Deterministic fixtures

Descriptions from AMA-licensed source members are not retained. The fixtures
use identifiers and numeric CMS fields only.

### Stable code 99213

The 2024 RVUs are work `1.30`, nonfacility PE `1.33`, facility PE `0.56`, and
malpractice `0.10`.

| Locality | GPCIs: work / PE / MP | Jan 1–Mar 8 NF / facility | Mar 9–Dec 31 NF / facility |
|---|---|---:|---:|
| Alabama `AL:00` | 1.000 / 0.869 / 0.575 | $82.30 / $60.38 | $83.66 / $61.39 |
| Manhattan `NY:01` | 1.065 / 1.166 / 1.656 | $101.54 / $72.14 | $103.22 / $73.33 |

This vector exercises both settings, two materially different geographic
adjustments, final-cent rounding, the March 8/9 factor boundary, and stable-row
selection across all later quarterly snapshots.

### July boundary code G9037

`G9037` has work RVU `0.57`, facility and nonfacility PE RVU `0.59`, and
malpractice RVU `0.04`. It has no effective assignment on June 30 and therefore
returns `unsupported`. On July 1 it resolves to RVU24C and calculates `$36.81`
in Alabama and `$45.31` in Manhattan. CMS's
[July national payment revision file](https://www.cms.gov/medicare/payment/fee-schedules/physician/national-payment-amount-file/pfrev24c)
provides an additional published-output check for this boundary.

### Anesthesia fail-closed code 01951

`01951` is status `J` in the RVU files. It is a negative fixture: the ordinary
PFS formula must return `unsupported`, no amount, and
`missing_rule=pfs.anesthesia`. Anesthesia requires base units, time units, and
an anesthesia conversion factor, none of which the core path pretends to
implement.

## Independent published-output validation

The component formula is validated against CMS's separately published
[CY2024 all-states carrier files](https://www.cms.gov/medicare/payment/fee-schedules/physician/carrier-specific-files/all-states).
CMS publishes one file set for
[January 1 through March 8](https://www.cms.gov/files/zip/cy-2024-carrier-files-effective-date-january-1-2024-march-8-2024-updated-04/02/2024.zip)
and another for
[March 9 through December 31](https://www.cms.gov/files/zip/cy-2024-carrier-files-effective-date-march-9-2024-december-31-2024-updated-04/02/2024.zip).

The four `99213` Alabama/Manhattan facility/nonfacility results above match the
corresponding carrier-file amounts exactly in both factor intervals. These
files are validation outputs, not formula inputs, so the test does not compare
the calculator with values derived from its own normalized result. Raw carrier
and RVU archives remain local and checksummed because they contain licensed
descriptions; public artifacts omit descriptions.

## Explicit exclusions

The calculated amount is not a Medicare allowed charge, remittance result,
beneficiary liability, or final payment. Stage 2A does not execute:

- anesthesia base-unit, time-unit, modifier, and locality conversion-factor
  payment;
- contractor pricing and all non-A status-specific payment mechanisms;
- multiple-procedure, bilateral-surgery, assistant-at-surgery, co-surgery, or
  team-surgery adjustments;
- therapy multiple-procedure reductions or the OPPS-based imaging payment cap;
- PC/TC splitting, technical-component or professional-component modifier
  logic, endoscopic-base logic, or diagnostic-test supervision rules;
- global-surgery preoperative, intraoperative, postoperative, or same-day
  interaction rules;
- claim-line units, modifier adjudication, place-of-service validation, or
  payment interaction among multiple claim lines;
- NCCI edits, medically unlikely edits, coverage, medical necessity, prior
  authorization, or other claims-processing edits;
- provider participation, assignment, limiting-charge, deductible,
  coinsurance, secondary-payer, sequestration, or quality-program effects;
- locality derivation from a provider address or MAC enrollment: locality is an
  explicit canonical input; or
- any year outside the pinned 2024 rule versions.

Where one of these paths is indicated by the selected source row, the engine
returns `unsupported_adjustments` and/or `missing_rule` with no calculated
amount. It never substitutes a zero, stale-quarter value, or ordinary-formula
estimate for an unimplemented rule.
