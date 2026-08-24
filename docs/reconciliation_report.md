# Reconciliation report

## 2024 national total

The principal CMS file reports **$5,278.588B** ($5,278,588,000,000) of National Health Expenditures for calendar year 2024.

## Totals by source/component

| Source/component | Current USD (exact conversion of reported millions) |
|---|---:|
| Out of pocket | $556,554,000,000 |
| Private Health Insurance | $1,644,592,000,000 |
| Medicare | $1,118,000,000,000 |
| Medicaid | $931,692,000,000 |
| CHIP | $30,995,000,000 |
| Department of Defense | $50,009,000,000 |
| Department of Veterans Affairs | $117,580,000,000 |
| Other Third Party Payers and Programs | $432,933,000,000 |
| Government Public Health Activities | $157,569,000,000 |
| Investment | $238,664,000,000 |
| **Total NHE** | **$5,278,588,000,000** |

The source rows above are mutually exclusive at this ledger level. Health Insurance and its components, and Other Third Party Payers and Programs and its children, are retained in normalized data but are not summed together. Government Public Health Activities and Investment are expenditure components used by CMS to complete the full-NHE matrix.

## Totals by top-level service

| Service | Current USD (exact conversion of reported millions) |
|---|---:|
| Hospital Care | $1,634,738,000,000 |
| Physician and Clinical Services | $1,109,681,000,000 |
| Other Professional Services | $184,859,000,000 |
| Dental Services | $189,179,000,000 |
| Other Health, Residential, and Personal Care | $320,469,000,000 |
| Home Health Care | $169,365,000,000 |
| Nursing Care Facilities and Continuing Care Retirement Communities | $219,903,000,000 |
| Retail Prescription Drugs | $466,968,000,000 |
| Other Non-Durable Medical Products | $128,702,000,000 |
| Durable Medical Equipment | $86,358,000,000 |
| Government Administration and Non-Medical Insurance Expenditures | $372,132,000,000 |
| Government Public Health Activities | $157,569,000,000 |
| Investment | $238,664,000,000 |
| **Total NHE** | **$5,278,588,000,000** |

## Accounting identities

| Identity | 2024 residual | Historical maximum absolute residual | Tolerance | Status |
|---|---:|---:|---:|---|
| NHE from mutually exclusive service components | $-1,000,000 | $3,000,000 | $10,000,000 | PASS |
| NHE from mutually exclusive source components | $0 | $2,000,000 | $5,000,000 | PASS |
| PHC from ten service components | $0 | $2,000,000 | $5,000,000 | PASS |
| HCE from PHC, administration/non-medical insurance, and public health | $-1,000,000 | $1,000,000 | $3,000,000 | PASS |
| Investment from research and structures/equipment | $1,000,000 | $1,000,000 | $2,000,000 | PASS |
| Administration/non-medical insurance from three components | $0 | $1,000,000 | $3,000,000 | PASS |
| Sponsor total from five mutually exclusive sponsors | $-100,000,000 | $100,000,000 | $400,000,000 | PASS |
| 2024 ledger interior cross-dimensional total | $0 | $0 | $10,000,000 | PASS |

The separate-format exact-million CMS Table 19 check compared **110** 2024 cells/totals; **110 passed**. Direct cells use zero tolerance; combined administration cells allow $1 million because they sum three separately rounded Table 19 components.

Before the ledger identity is evaluated, validation requires both persisted 2024 ledger Parquets to match a fresh programmatic regeneration exactly, including every cell-level provenance field.

The historical source hierarchy suite compared **7,735** parent/child totals across seven payer subtrees, 17 service panels, and 65 years; **7,735 passed**. Its tolerances range from $1 million to $6 million based on the number of independently rounded integer-million children.

## Sponsor view (separate accounting perspective)

| Sponsor | CMS-reported current USD |
|---|---:|
| Private Business | $967,400,000,000 |
| Household | $1,458,900,000,000 |
| Other Private Sponsors | $340,500,000,000 |
| Federal Government | $1,652,000,000,000 |
| State and Local Government | $859,700,000,000 |

Table 5 reports sponsor amounts to $0.1 billion. Its five 2024 leaf sponsors total $5,278,500,000,000, versus the rounded sponsor root of $5,278,600,000,000. The $0.1 billion residual is published rounding, not an allocated adjustment.

Sponsor and source of funds are alternative perspectives on overlapping expenditures; they are not added or synthetically crossed by service.

## Rounding and source-table differences

- The principal historical CSV reports integer millions in current dollars. Summing many reported cells can therefore produce residuals of a few million dollars.
- Table 4 reports billions and is used for presentation review, not exact reconciliation. Table 19 reports 2024 levels in millions and is a separate-format cross-check from the same CMS release, not an independent estimate.
- The NHE Summary reports amounts in billions, population in millions, per-capita dollars, growth/distribution percentages, and GDP share. Those non-dollar rows are not ingested as flows.
- An explicit source dash is retained as `not_applicable`; an empty source cell is retained as `structural_blank`. Both have null amounts and are never converted to reported zeroes. Blank wide-ledger crossings are likewise null.

## Open accounting questions

- The complete service/source matrix necessarily uses Government Public Health Activities and Investment as top-level NHE components, not payer programs comparable to Medicare.
- Table 5 sponsor history begins in 1987; CMS does not supply a 1960–2024 service × sponsor cube.
- The 2024 comprehensive benchmark revision reopens the full history. A later vintage should be ingested as a new pinned release rather than silently replacing these checksums.
- Provider-establishment classification means `service_category` is not necessarily the clinical procedure performed or the legal recipient of each payment.

## Validation result

**PASS:** 8,997 of 8,997 checks passed.
