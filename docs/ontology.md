# Healthcare Claims Ledger v0.1 ontology

## Scope and unit of observation

The v0.1 ledger is a national expenditure account, not a database of adjudicated
insurance claims. Its canonical object is a **reported financial-flow observation**:

> a CMS-reported amount for one calendar year, accounting view, service context,
> and payer/source or sponsor category, with source-cell provenance.

CMS's NHEA includes provider and retail revenue, public-health activity,
administration, non-medical insurance expenditures, and medical-sector investment.
The word “claims” in the project name therefore refers to claims on economic
resources in the broader Reconciliation project. It must not be read as implying
claim-line data.

## CMS accounting hierarchy

The current CMS methodology defines the following nested goods-and-services
hierarchy:

```text
National Health Expenditures (NHE)
├── Health Consumption Expenditures (HCE)
│   ├── Personal Health Care (PHC)
│   │   ├── Hospital Care
│   │   ├── Physician and Clinical Services
│   │   ├── Other Professional Services
│   │   ├── Dental Services
│   │   ├── Other Health, Residential, and Personal Care
│   │   ├── Home Health Care
│   │   ├── Nursing Care Facilities and Continuing Care Retirement Communities
│   │   ├── Retail Prescription Drugs
│   │   ├── Other Non-Durable Medical Products
│   │   └── Durable Medical Equipment
│   ├── Government Administration
│   ├── Non-Medical Insurance Expenditures
│   └── Government Public Health Activities
└── Investment
    ├── Non-Commercial Research
    └── Structures and Equipment
```

The principal historical file supplies one combined
`physician_clinical_services` panel. It does not support a complete 1960–2024
split between physicians and clinics, so v0.1 does not infer one.

The convenient CMS presentation rollups `Professional Services` and `Retail
Outlet Sales of Medical Products` do not appear as independent panels in the
principal historical file. v0.1 does not add derived copies of them.

## Dimensions

### `service_category`

The good or service purchased, classified primarily by the establishment that
received the revenue. This is not necessarily a procedure, care setting, or legal
recipient entity.

Important consequences of CMS's establishment-based approach include:

- Hospital Care includes hospital-billed inpatient pharmacy, nursing, home health,
  hospice, appropriations, and non-patient revenue.
- Separately billing professionals can appear under Physician and Clinical
  Services even when care occurs at a hospital.
- The standalone Home Health and Nursing/CCRC categories generally describe
  freestanding establishments.
- Retail product categories exclude products embedded in provider bills.

Every record preserves the reviewed canonical code/name and the raw panel label.
Parents, levels, subtotal flags, and ledger order are explicit fields.

### `funding_source`

The payer, program, or source category directly represented in the CMS
source-of-funds view. The repeated hierarchy is:

```text
All sources
├── Out of pocket
├── Health Insurance
│   ├── Private Health Insurance
│   ├── Medicare
│   ├── Medicaid
│   │   ├── Federal
│   │   └── State and Local
│   ├── CHIP
│   │   ├── Federal
│   │   └── State and Local
│   ├── Department of Defense
│   └── Department of Veterans Affairs
└── Other Third Party Payers and Programs
    ├── Worksite Health Care
    ├── Other Private Revenues
    ├── Indian Health Service
    ├── Workers' Compensation
    ├── General Assistance
    ├── Maternal/Child Health
    │   ├── Federal
    │   └── State and Local
    ├── Vocational Rehabilitation
    │   ├── Federal
    │   └── State and Local
    ├── Other Federal Programs
    ├── SAMHSA
    ├── Other State and Local Programs
    └── School Health
```

`Health Insurance` and `Other Third Party Payers and Programs` are subtotals.
They cannot be added to their children. `Total CMS Programs` is an overlapping
analytical subtotal equal to Medicare + Medicaid + CHIP; it is never an additional
funding source.

The additive 2024 matrix uses mutually exclusive reported categories:

```text
Out of pocket
Private Health Insurance
Medicare
Medicaid (parent total, not federal/state children)
CHIP (parent total, not federal/state children)
Department of Defense
Department of Veterans Affairs
Other Third Party Payers and Programs (parent total, not its children)
Government Public Health Activities
Investment
```

The last two are NHE expenditure components rather than payer programs comparable
to Medicare. CMS uses them to complete the full-NHE source/type matrix. They are
named and documented distinctly rather than being silently treated as payers.

### `sponsor`

The household, business, government, or other private entity ultimately financing
health expenditures in CMS's separate sponsor view. The available Table 5 history
is 1987–2024:

```text
All sponsors
├── Business, Households and Other Private
│   ├── Private Business
│   ├── Household
│   └── Other Private Sponsors
└── Government
    ├── Federal Government
    └── State and Local Government
```

Sponsor and funding source are not interchangeable. The sponsor ledger is not
joined to service categories to invent a three-dimensional cube that CMS does not
publish.

### `program`

A specific program only when the source explicitly supplies it. It is null in the
v0.1 aggregate ledgers. No Original Medicare/Medicare Advantage/Part D split is
inferred.

### `recipient`

A provider or recipient class only when explicitly represented. It is null in
v0.1. A service category is not copied into this field.

### `claim_class`

Reserved for a future analytical classification such as direct public,
formula-based, government-subsidized private, guaranteed/backstopped,
predominantly private, mixed, or unknown. It is null throughout v0.1 because the
current sources do not establish a reviewed, unambiguous mapping at the flow level.

## Accounting views

- `source_of_funds_by_service`: the principal payer/source and service history.
- `sponsor`: ultimate-financing totals from Table 5.

These are alternative views of overlapping dollars. They are stored in separate
Parquet files and DuckDB tables and are never added together.

## Canonical record

The required fields are:

| Field | Meaning |
|---|---|
| `year` | Calendar year represented by the source cell. |
| `amount_usd` | Current dollars, converted exactly from the published unit. Nullable. |
| `amount_unit` | `USD current dollars`. |
| `service_category_code/name/parent` | Reviewed CMS-aligned service hierarchy. |
| `funding_source_code/name` | Reviewed, parent-qualified source hierarchy. |
| `sponsor_code/name` | Sponsor category in the separate sponsor view. |
| `program_code/name` | Explicit program only; null in v0.1. |
| `recipient_code/name` | Explicit recipient only; null in v0.1. |
| `claim_class` | Reserved analytical classification; null in v0.1. |
| `accounting_view` | Prevents adding alternative views. |
| `source_dataset` | CMS product/table description. |
| `source_file` | Outer archive and inner member. |
| `source_sheet` | CSV table name or Excel worksheet. |
| `source_row/source_column` | Logical source cell address. |
| `source_label_raw` | Original row label, including whitespace/footnote markers. |
| `value_status` | Source representation: `reported`, `not_applicable` (explicit dash), or `structural_blank` (empty source cell). |
| `derivation` | Formula when derived; null for v0.1 normalized amounts. |
| `source_release` | Pinned CMS release description. |
| `ingested_at` | Download timestamp inherited from the manifest. |

Additional audit fields retain raw tokens, source unit/display precision, category
levels, subtotal flags, additive-use flags, and presentation order.

## Units, precision, and nulls

- Principal history: integer **USD millions**, current dollars. Multiplication by
  1,000,000 changes the unit but does not create sub-million precision.
- Sponsor Table 5: **USD billions** displayed to one decimal. Multiplication by
  1,000,000,000 does not imply precision below $0.1 billion.
- A padded hyphen in the principal CSV is retained as `not_applicable`, not zero.
  The pinned file contains 8,953 such cells.
- An empty principal CSV cell is retained separately as `structural_blank`. The
  2,730 cells in this release occur in structurally unreported payer crossings of
  the state/local administration, federal administration, and non-medical
  insurance panels. This status describes the source representation; it does not
  assert a numeric zero.
- Both non-reported statuses preserve `source_value_raw` and have null
  `amount_usd`. Blank cells in the wide ledger likewise are not asserted zeroes.
- No suppressed values occur in the principal file.

## Provenance and keys

The normalized principal key is unique on:

```text
year + service_category_code + funding_source_code
```

The sponsor key is unique on:

```text
year + sponsor_code
```

The wide ledger has a long companion table with one row per populated or
source-reported cell. That table carries the exact file, table, row, column, raw
label, raw value, unit, precision, status, and release metadata used for each
displayed amount.
