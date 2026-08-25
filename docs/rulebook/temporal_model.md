# Temporal model

All intervals use inclusive `effective_start` and `effective_end` dates. A
resolver must find exactly one row. Zero rows is a gap; two or more rows is an
overlap. Both fail closed.

## PFS

Snapshot selection for 2024 is:

| Version | Inclusive dates | Conversion factor |
|---|---|---:|
| RVU24A | 2024-01-01–2024-03-08 | 32.7442 |
| RVU24AR | 2024-03-09–2024-03-31 | 33.2875 |
| RVU24B | 2024-04-01–2024-06-30 | 33.2875 |
| RVU24C | 2024-07-01–2024-09-30 | 33.2875 |
| RVU24D | 2024-10-01–2024-12-31 | 33.2875 |

The March 31 endpoint for RVU24AR is a snapshot-selection boundary, not an end
to the revised statutory conversion factor. The post-March factor continues
through December 31 in later quarterly snapshots.

Quarterly implementation files can contain code rows effective on dates other
than the first day of the quarter. A changed/new row is therefore marked
`unresolved_effective_date` unless a CMS change request establishes the date in
the normalized exception set. Known boundary fixtures include J0576 on April
1, G9037/G9038 on July 1, and J1170 on October 1. The machine-readable October
attachment is pinned for future expansion of the exception set.

## OPPS

Addendum B snapshots cover Jan–Mar, Apr–Jun, Jul–Sep, and Oct–Dec. They state
what CMS published for the start of each quarter; they are not proof that every
changed row became effective on that start date. Known clean boundary fixtures
are normalized, and the C9790 January assignment includes CMS's retroactive
April correction effective January 1. Other changed rows without a normalized
code-specific date fail closed.

CMS can later restate drug/biological rates. Those overlays need explicit
as-of-release semantics and are not forward-filled. Rows identified as needing
that overlay are not eligible for a final-looking calculation.

## IPPS

IPPS follows discharge date and the federal fiscal year:

| Rule version | Inclusive dates |
|---|---|
| FY2024 | 2023-10-01–2024-09-30 |
| FY2025 | 2024-10-01–2025-09-30 |

Thus a 2024-09-30 discharge uses CMS-1785 values and a 2024-10-01 discharge
uses CMS-1808 values. FY2025 selects the September 30 interim-final-action
standardized amounts and wage tables after the low-wage-index policy was
removed; using the original August final-rule values would be wrong.

This boundary governs the entire IPPS graph, including the deferred IME, DSH,
uncompensated-care, NTAP, outlier, HRRP, VBP, HAC, transfer, and final-payment
rules. Each concept has two versioned nodes with complete fiscal-year
intervals:

| Boundary date | Active deferred namespace | Final-payment dependency |
|---|---|---|
| 2024-09-30 | `ipps.fy2024.*` | `ipps.fy2024.base_operating_payment` |
| 2024-10-01 | `ipps.fy2025.*` | `ipps.fy2025.base_operating_payment` |

Every outgoing final-payment edge remains within that same namespace and uses
the full fiscal-year interval. FY2024 nodes link to the CMS-1785 regulatory
authority and applicable FY2024 supporting artifacts; FY2025 nodes link to
CMS-1808 and applicable FY2025 rule, correction, IFC, and table artifacts. A
single CY2024 adjustment or final-payment node would combine two different
annual rule authorities and is therefore not a valid temporal model.
