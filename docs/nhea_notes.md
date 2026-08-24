# NHEA source inspection notes

Inspection was performed before normalization. The machine-readable inventory is
`data/interim/nhea_inventory.json`; this document records the accounting and parser
decisions that follow from the actual files.

## Release inspected

The official CMS Historical page currently publishes the 2024 NHEA vintage for
calendar years 1960–2024. CMS describes 2024 as a comprehensive revision of the
historical series. The methodology is dated January 2026, the downloadable files
report HTTP last-modified timestamps on January 13, 2026, and the CMS page was
updated January 14, 2026.

Legacy `.xls` document-create metadata refers to a 2018 template and is not the
release date.

## Principal service/source archive

`national-health-expenditures-type-service-source-funds-cy-1960-2024.zip`
contains:

```text
NHE2024.csv   224,377 uncompressed bytes
NHE2024.xls   295,936 uncompressed bytes
```

The XLS is true legacy BIFF with one sheet, `NHE24`. The CSV is the canonical
ingestion source because it preserves the difference between a reported zero and
the displayed not-applicable dash. The XLS stores some displayed dashes as numeric
zero under a custom format.

The CSV has 545 logical records and 66 fields:

```text
column A     hierarchical label
columns B:BN calendar years 1960–2024
```

It is CP1252 with CRLF line endings. UTF-8 decoding fails on the em dash in the
note. Values are current-dollar millions, except for the special population row.
Every data row has exactly 66 parsed CSV fields.

### Logical row blocks

Source rows are one-based and align between the CSV logical records and XLS rows:

| Rows | Panel |
|---:|---|
| 1 | Title |
| 2 | Unit/year header |
| 3–39 | Total NHE; row 39 is population and is excluded from expenditure records |
| 40–72 | Health Consumption Expenditures |
| 73–102 | Personal Health Care |
| 103–132 | Hospital |
| 133–162 | Physician and Clinical |
| 163–192 | Dental |
| 193–222 | Other Professional |
| 223–252 | Home Health |
| 253–282 | Other Non-Durable Medical Products |
| 283–312 | Prescription Drugs |
| 313–342 | Durable Medical Equipment |
| 343–372 | Nursing/CCRC |
| 373–402 | Other Health, Residential, and Personal Care |
| 403–432 | Administration + Non-Medical Insurance |
| 433–462 | State/local administration |
| 463–492 | Federal administration |
| 493–522 | Non-Medical Insurance |
| 523–525 | Public Health total/federal/state-local |
| 526–529 | Research total/private/federal/state-local |
| 530–541 | Structures and Equipment hierarchy |
| 542–545 | Footnotes, note, and source |

Rows 73–522 are fifteen exact 30-row panels. Their 29 payer/subtotal labels after
the root are byte-for-byte identical. The parser asserts this reviewed template
and the expected root labels rather than inferring parents from indentation.

### Hierarchy and duplicates

The repeated panel contains a service total, Out of pocket, a Health Insurance
tree, an Other Third Party Payers and Programs tree, and `Total CMS Programs`.
Several raw labels repeat within a panel (`Federal`, `State and Local`) under
Medicaid, CHIP, Maternal/Child Health, and Vocational Rehabilitation. They receive
parent-qualified canonical codes.

Leading spaces encode presentation hierarchy but are inconsistent: Department of
Defense and Department of Veterans Affairs are offset differently from their
sibling rows. Raw whitespace is preserved for provenance but is not used as the
sole parser.

Subtotals are explicit. In particular:

- Health Insurance = PHI + Medicare + Medicaid + CHIP + DOD + VA.
- Medicaid and CHIP have federal/state-local children; parent and children cannot
  be included in the same additive total.
- Other Third Party Payers and Programs has detailed children; its parent total is
  used at the clean ledger level.
- Total CMS Programs overlaps Medicare, Medicaid, and CHIP and is excluded from
  additive sums.

The validation suite reconciles seven source subtrees for every year in all 17
panels that carry the full source hierarchy: NHE, HCE, PHC, and the fourteen
remaining service/administration panels through Non-Medical Insurance. This is
7 × 17 × 65 = **7,735 historical hierarchy checks**. The checked identities
are Health Insurance, Medicaid, CHIP, Maternal/Child Health, Vocational
Rehabilitation, Other Third Party Payers and Programs, and Total CMS Programs.

| Source subtree | Allowed rounding residual | Maximum observed absolute residual |
|---|---:|---:|
| Health Insurance (6 children) | $3 million | $2 million |
| Medicaid (2 children) | $1 million | $1 million |
| CHIP (2 children) | $1 million | $1 million |
| Maternal/Child Health (2 children) | $1 million | $1 million |
| Vocational Rehabilitation (2 children) | $1 million | $1 million |
| Other Third Party Payers and Programs (11 children) | $6 million | $3 million |
| Total CMS Programs (3 children) | $2 million | $1 million |

The tolerances cover accumulation of independently rounded integer-million cells;
they are not balancing adjustments. Source-authored null cells are treated as zero
only inside these parent/child comparisons, while their normalized amounts remain
null.

### Nulls and footnotes

The principal CSV contains no suppression symbols and no literal numeric-zero
cells. Of its 34,970 normalized source cells, 23,287 contain reported amounts,
8,953 contain an explicit whitespace-padded hyphen, and 2,730 are empty. The
parser preserves every raw token and distinguishes the two null representations:

- an explicit dash becomes `value_status=not_applicable`;
- an empty token becomes `value_status=structural_blank`.

All structural blanks occur in source/payer crossings of the State and Local
Administration, Federal Administration, and Non-Medical Insurance panels that
CMS leaves unreported for every year. Both statuses have null `amount_usd`; neither
is converted to a reported zero.

CMS notes that Medicare and Medicaid became effective in July 1966 and CHIP in
1998. Pre-program dashes are not changed to zero.

CMS's file also states:

- Other Federal Programs includes OEO, Federal General and Medical, Federal
  General and Medical NEC, and ACA high-risk pools.
- Other State and Local Programs includes state/local subsidies and TDI.
- Amounts are current dollars and may not add because of rounding.

## Summary/GDP archive

`nhe-summary-including-share-gdp-cy-1960-2024.zip` contains
`NHE24_Summary.csv` and `NHE24_Summary.xls`, with one XLS sheet named `NHE24`.
The logical shape is 35 records × 66 columns. The CSV title contains an embedded
newline, so physical line counting is invalid; it must be read with a CSV parser.

The file deliberately mixes:

- expenditure and GDP amounts in billions,
- population in millions,
- annual percent change,
- percent distribution,
- per-capita dollars,
- NHE as a percent of GDP.

It is archived and inspected, but its percentage, population, per-capita, and GDP
rows are not loaded into the financial-flow table. This prevents accidental
parsing of a percentage as dollars. The Summary CSV and principal file both show
2024 population rounded to 341 million; the supporting NHE Table 1 supplies the
more precise 341.1 million presentation value.

## NHE Tables archive

`nhe-tables.zip` contains 31 individual `.xlsx` workbooks: Tables 01–25 plus
Tables 05-1 through 05-6. Every workbook has one visible static-values worksheet
named for the table. There are no formulas.

The complete archive inventory is:

```text
Table 01 National Health Expenditures; Aggregate and Per Capita Amounts.xlsx → Table 1
Table 02 National Health Expenditures, Aggregate and Per Capita Amounts, by Type of Expenditure.xlsx → Table 2
Table 03 National Health Expenditures, by Source of Funds.xlsx → Table 3
Table 04 National Health Expenditures by Source of Funds and Type of Expenditures.xlsx → Table 4
Table 05 National Health Expenditures by Type of Sponsor.xlsx → Table 5
Table 05-1 Private Business Sponsor Expenditures.xlsx → Table 5-1
Table 05-2 Household Sponsor Expenditures.xlsx → Table 5-2
Table 05-3 Federal Government Sponsor Expenditures.xlsx → Table 5-3
Table 05-4 State and Local Government Sponsor Expenditures.xlsx → Table 5-4
Table 05-5 Medicare Spending by Sponsor.xlsx → Table 5-5
Table 05-6 Private Health Insurance by Sponsor.xlsx → Table 5-6
Table 06 Personal Health Care Expenditures.xlsx → Table 6
Table 07 Hospital Care Expenditures.xlsx → Table 7
Table 08 Physician and Clinical Services Expenditures.xlsx → Table 8
Table 09 Physician Services Expenditures.xlsx → Table 9
Table 10 Clinical Services Expenditures.xlsx → Table 10
Table 11 Other Professional Services Expenditures.xlsx → Table 11
Table 12 Dental Services Expenditures.xlsx → Table 12
Table 13 Other Health, Residential, and Personal Care Expenditures.xlsx → Table 13
Table 14 Home Health Care Expenditures.xlsx → Table 14
Table 15 Nursing Care Facilities and Continuing Care Retirement Communities Expenditures.xlsx → Table 15
Table 16 Retail Prescription Drugs Expenditures.xlsx → Table 16
Table 17 Durable Medical Equipment Expenditures.xlsx → Table 17
Table 18 Other Non-Durable Medical Products Expenditures.xlsx → Table 18
Table 19 National Health Expenditures by Type of Expenditure and Program.xlsx → Table 19
Table 20 Private Health Insurance Benefits and  Non-Medical Insurance Expenditures.xlsx → Table 20
Table 21 Expenditures, Enrollment and Per Enrollee Estimates of Health Insurance.xlsx → Table 21
Table 22 Health Insurance Enrollment and Uninsured.xlsx → Table 22
Table 23 National Health Expenditures; Nominal, Real, Price Indexes.xlsx → Table 23
Table 24 Employer-Sponsored Private Health Insurance.xlsx → Table 24
Table 25 Expenditures by Type of Insurer, Annual Percent Change and Ratios.xlsx → Table 25
```

Layouts are intentionally table-specific:

- Tables 1–3 use years across columns and stacked metric sections.
- Table 4 covers only 2017–2024 and uses repeated vertical year blocks. Amounts
  are billions; displayed `0.0` can mean less than $50 million.
- Table 5 uses years 1987–2024 across columns and separate amount, growth, and
  distribution sections.
- Tables 6–18 put years down rows and payer categories across columns, with stacked
  amount/growth/distribution sections.
- Table 19 is an exact-million 2024 payer/program × service matrix and is used as
  a separate-format cross-check from the same CMS release.
- Table 23 has nominal, real, and price-index sections.

Worksheet reported dimensions are often inflated by formatting, merged cells,
and whitespace-only cells. The inspection inventory records both worksheet bounds
and trimmed logical bounds. No generic parser is applied across these workbooks.

### Table 5 sponsor view

Table 5 covers 1987–2024, not 1960–2024. Its first amount block reports NHE and a
sponsor hierarchy in billions to one decimal. Only those amount rows are
normalized. Annual-change and percent-distribution sections are excluded.

Root percentage cells are stored as fractions with Excel percentage formatting
while some child cells are stored as percentage-point numbers. This confirms that
raw numeric magnitude alone is not a safe cross-section unit detector.

The five 2024 sponsor leaves sum to $5,278.5 billion, while the rounded NHE root is
$5,278.6 billion. The $0.1 billion residual is retained and documented.

### Table 19 separate-format check

Table 19 reports 2024 levels in millions. The validation suite compares the
principal file with:

- 88 payer/service cells,
- 11 service totals,
- 8 payer/source totals,
- NHE, Public Health, and Investment totals.

Direct cells use zero tolerance. Combining Table 19's separately rounded state
administration, federal administration, and non-medical insurance cells requires
a $1 million tolerance for two combined payer cells. No value is altered to force
agreement.

## Historical breaks and warnings

The 2024 comprehensive revision incorporated 2022 Economic Census benchmarks and
revised parts of the complete historical series. Values from older NHEA vintages
must not be mixed with this pinned release without an explicit vintage comparison.

COVID-era changes are intentional. CMS classifies Paycheck Protection Program and
Provider Relief Fund subsidies under Other Federal Programs and allocates them to
provider service categories. Other Federal Programs rises to $180.756 billion in
2020 and $85.403 billion in 2021 before declining. That pattern is documented, not
treated as a parser anomaly.

## Accounting questions kept visible

- PHC, HCE, and NHE are nested totals, not additive peer rows.
- Sponsor is not ultimate-incidence proof and is not directly crossable with every
  service.
- Government Public Health Activities and Investment complete the national
  service/source matrix but are not payer programs comparable to Medicare.
- NHEA service classification often follows the provider establishment, so it does
  not directly establish a recipient entity or procedure-level service.
- Research excludes commercial product/provider research that remains embedded in
  the applicable product or service category.
