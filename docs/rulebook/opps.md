# Hospital Outpatient Prospective Payment System

## Implemented boundary

Stage 2A implements an effective-dated, code-level OPPS lookup:

```text
HCPCS identifier
→ status indicator
→ APC assignment, when published
→ relative weight, when published
→ published national unadjusted payment rate, when published
```

`lookup_opps(code, service_date, store)` uppercases the identifier and searches
only `OPPS` records with assignment type `opps_hcpcs`. The inclusive service-date
interval must select exactly one assignment and its classification rule version.
A priced row must also select exactly one published-rate rule version. A missing
code, a gap, an overlap, an invalid interval, a missing rule, or a row marked
`unresolved_effective_date` returns an `UNSUPPORTED` trace with no amount.

A supported result has calculation status `LOOKUP_ONLY`. Its trace contains the
selected rule version or versions and assignment, status indicator, APC, relative
weight, source locator, source artifact, value status, packaging interpretation, and a
`claim_context_required` flag. If Addendum B publishes a rate, the trace carries
that value with the label:

```text
published national unadjusted OPPS payment rate (not final claim payment)
```

A blank rate is not converted to zero. Packaged services, cost-based
pass-through devices, and services paid outside OPPS can legitimately have no
Addendum B rate; the lookup remains traceable and emits a warning.

## Quarterly snapshots and effective dates

CMS describes quarterly Addenda A and B as snapshots of the HCPCS codes, status
indicators, APC assignments, and payment rates in effect at the beginning of a
quarter. The normalized Addendum B intervals are:

| Snapshot | Inclusive lookup interval | Official archive |
|---|---|---|
| January | 2024-01-01–2024-03-31 | [January 2024 Addendum B](https://www.cms.gov/files/zip/january-2024-opps-addendum-b.zip) |
| April | 2024-04-01–2024-06-30 | [April 2024 Addendum B](https://www.cms.gov/files/zip/april-2024-addendum-b.zip) |
| July | 2024-07-01–2024-09-30 | [July 2024 Addendum B](https://www.cms.gov/files/zip/july-2024-addendum-b-080524.zip) |
| October | 2024-10-01–2024-12-31 | [October 2024 Addendum B](https://www.cms.gov/files/zip/october-2024-web-addendum-b.zip) |

Quarter membership alone is not evidence that every new or changed row took
effect on the first day of that quarter. CMS update instructions contain
retroactive and mid-quarter effective dates. Stage 2A therefore compares each
April, July, and October row's status indicator, APC, relative weight, and rate
with the preceding snapshot. A new or changed row is marked
`unresolved_effective_date` unless its code-specific boundary is in the reviewed
exception set. The lookup refuses those rows instead of silently assigning the
quarter start. A code removed from a later snapshot likewise has no active row
for that later date and fails closed.

The currently normalized clean boundaries are:

| Identifier | Boundary | Published change represented |
|---|---|---|
| `C1761` | 2024-07-01 | SI `H`, APC `2033` through June 30; SI `N` from July 1 |
| `C1831` | 2024-10-01 | SI `H`, APC `2034` through September 30; SI `N` from October 1 |
| `G0012` | 2024-10-01 | APC `5691`, rate $45.26 through September 30; APC `5692`, rate $67.12 from October 1 |

The dollar values in this table are published national unadjusted lookup rates,
not final payments.

There is no preceding 2024 snapshot against which to compare January rows.
Except for the explicit C9790 correction below, a January
`published_quarter_snapshot` record means only that the value was published in
the January file. More generally, Stage 2A has not converted every memorandum
table into a retroactive exception index. The value status is therefore a
statement about normalized source coverage, not proof that all later CMS
corrections have been applied to that code and date.

### C9790 retroactive correction

The January snapshot originally placed `C9790` in APC `1575` with a published
rate of $12,500.50. CMS's [April update MM13568](https://www.cms.gov/files/document/mm13568-hospital-outpatient-prospective-payment-system-april-2024-update.pdf)
changed it to APC `1576` and $17,500.50 retroactive to January 1, 2024. The
normalizer copies only the corrected public numeric/status fields confirmed in
the April Addendum B into the January record and marks it
`published_retroactive_correction`. Thus a first-quarter lookup returns APC
`1576` and the corrected published national unadjusted rate.

The Q1 assignment has three explicit `entity_source_links`: the original Q1
Addendum B as supporting documentation, MM13568 as the
`retroactive_correction`, and the Q2 Addendum B as the
`primary_numeric_authority` for the replacement APC/rate. A trace returns all
three artifacts and their roles without parsing the prose locator.

This is the only retroactive OPPS row correction made executable in Stage 2A.
The January, April, revised July, and October update memoranda are pinned, but
their other heterogeneous row-effective exceptions have not all been normalized.

## Restated drug and biological rates

CMS can issue retroactive corrections after a quarterly Addendum B is published.
The [Restated Drug and Biological Payment Rates](https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient/restated-drug-biological-payment-rates)
files are correction overlays, not complete replacement snapshots, and later
releases can revise an earlier 2024 effective date.

Stage 2A does not ingest the full versioned restatement sequence. A quarterly row
with SI `G` or `K`, or a rate published with more than two decimal places, is
marked `requires_restated_drug_overlay`. `lookup_opps` fails closed for such a
row: it returns `UNSUPPORTED`, reports `opps.restated_drug_rate` as the missing
rule, and emits no amount. A future implementation needs the correction release
date as an explicit `as_of_release` dimension and must not forward-fill a
correction into later quarters without authority.

## Status indicators and packaging

The policy interpretation comes from Addendum D1 in the
[CMS-1786-FC final-rule addenda](https://www.cms.gov/files/zip/2024-nfrm-opps-addenda.zip).
The rulebook records the following conservative treatment:

| SI | Stage 2A interpretation |
|---|---|
| `N` | Packaged into another service; no separate APC payment. |
| `J1` | Comprehensive APC; covered claim services are generally packaged into the primary J1 service, subject to CMS exclusions. |
| `J2` | C-APC treatment depends on the combination of services; otherwise separate or packaged treatment can apply. |
| `Q1`–`Q4` | Conditional or composite packaging; the other services on the claim determine the path. |
| `G`, `K`, `R`, `S`, `T`, `U`, `V` | Separately payable under the status-specific OPPS rule; `T` can require a multiple-procedure reduction. |
| `H` | Separate cost-based device pass-through treatment; a blank published rate is expected and claim costs are required. |
| `P` | Partial-hospitalization or intensive-outpatient per-diem treatment. |
| `A`, `F`, `L`, `Y` | Another fee schedule, reasonable-cost method, or DME billing path applies. |
| `B`, `C`, `D`, `E1`, `E2`, `M` | No OPPS payment under the status-specific reason. |

These are policy semantics, not a promise that every status reaches the lookup
result path. In particular, all canonical `G` and `K` rows currently require the
unmodeled restated-rate overlay and therefore fail closed before packaging
components are returned.

`claim_context_required` is set for `H`, `J1`, `J2`, `N`, `P`, `Q1`–`Q4`, and
`T`. This flag identifies a known claim-dependent status; it does not imply that
other rows can produce final payment without units, modifiers, provider facts,
or claim adjudication.

For `J1` and `J2`, a published APC rate is only the national unadjusted lookup
value. Stage 2A does not execute C-APC primary-service ranking, Addendum J
complexity pairs, exclusions, or claim-wide packaging. It therefore never calls
the rate a C-APC claim payment.

If a future source row contains a nonblank status indicator outside the mapping
above, the lookup reports the source value but does not infer its payment
treatment. The trace warns that the status is unmodeled and lists that treatment
as an unsupported adjustment.

## Adjustments not executed

Every supported OPPS trace warns that it omits at least:

- provider-specific wage-index adjustment;
- OPPS outlier payment;
- claim-level packaging and final adjudication;
- service units and modifiers;
- beneficiary deductible, coinsurance, and copayment calculations; and
- other provider- and claim-specific adjustments.

Depending on the status and provider, omitted mechanics can also include
multiple-procedure reduction, composite/C-APC logic, device pass-through cost,
off-campus department treatment, quality-reporting effects, and the rural
SCH/EACH adjustment. The CY2024 national rate's labor-related share is adjusted
using the provider wage index under the final rule; Stage 2A does not apply that
formula because CCN, reclassification, cap, out-migration, provider class, and
quality-reporting inputs are not all resolved in this path.

## Official source links

- [CMS-1786-FC OPPS final-rule page](https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient/regulations-notices/cms-1786-fc)
- [Published Federal Register rule](https://www.govinfo.gov/content/pkg/FR-2023-11-22/pdf/2023-24293.pdf)
- [CMS quarterly Addenda landing page](https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient-pps/quarterly-addenda-updates)
- [January update MM13488](https://www.cms.gov/files/document/mm13488-hospital-outpatient-prospective-payment-system-january-2024-update.pdf)
- [April update MM13568](https://www.cms.gov/files/document/mm13568-hospital-outpatient-prospective-payment-system-april-2024-update.pdf)
- [Revised July update MM13632](https://www.cms.gov/files/document/mm13632-hospital-outpatient-prospective-payment-system-july-2024-update.pdf)
- [October update MM13784](https://www.cms.gov/files/document/mm13784-hospital-outpatient-prospective-payment-system-october-2024-update.pdf)
- [FY2024 IPPS wage-index files used as the OPPS provider-wage source](https://www.cms.gov/medicare/medicare-fee-service-payment/acuteinpatientpps/wage-index-files/fy-2024-wage-index-home-page)

Exact filenames, release labels, inclusive intervals, byte sizes, and SHA-256
checksums are recorded in `data/raw/cms_payment_rules/manifest.json`.
