# Authoritative sources

All v0.1 source data and reference material come from the Centers for Medicare &
Medicaid Services (CMS). The landing page is the [CMS Historical NHEA page](https://www.cms.gov/data-research/statistics-trends-and-reports/national-health-expenditure-data/historical).

The checked-in machine-readable authority is
`data/raw/cms_nhea/manifest.json`. It records download timestamps, source URLs,
HTTP last-modified values, byte sizes, and SHA-256 checksums. The table below
describes the pinned files downloaded on 2026-08-24 UTC.

| Dataset | File | Bytes | SHA-256 |
|---|---|---:|---|
| NHE Tables | `nhe-tables.zip` | 520,391 | `a09ef6d3e84e25d745047a47b6b08a0d96b303085b4c725b67ce67a0eb0c4420` |
| NHE by service/source | `national-health-expenditures-type-service-source-funds-cy-1960-2024.zip` | 123,721 | `b6a9e26774ca36931d42add46204947d6335fc4898011780563196898f964746` |
| NHE Summary/GDP | `nhe-summary-including-share-gdp-cy-1960-2024.zip` | 19,575 | `ef92c5602a96ffebd5ec0d313f0e7dc55bca979178ca53d8e519cfd51bd99256` |
| Definitions, Sources, and Methods | `definitions-sources-methods.pdf` | 658,261 | `9c5755666847a78103016f04da937326744071a9a6736f4e77e91ce9e7af8629` |
| Quick Definitions | `quick-definitions-national-health-expenditures-accounts-nhea-categories.pdf` | 123,539 | `7e6af1be70ccf9aa7bc4cfdc5329e335703c3279d3cbd8f4cbfb411917945c4b` |
| 2024 benchmark revision | `summary-benchmark-changes-2024.pdf` | 283,164 | `edf3a7bc9db00b34f9569eadc2d6e8a8d80b0f5aa931633aa7d3bfdcf2146b35` |
| Federal COVID accounting | `accounting-federal-covid-expenditures-national-health-expenditure-accounts.pdf` | 282,105 | `5350d42a84a7b1ecafdef3e3f85c9bc9c5540fcbed2f55058856d78be43d0f25` |

## Principal historical dataset

[National Health Expenditures by type of service and source of funds, CY 1960–2024](https://www.cms.gov/files/zip/national-health-expenditures-type-service-source-funds-cy-1960-2024.zip)

- **Represents:** annual current-dollar expenditures by CMS service panel and
  payer/source hierarchy.
- **Coverage:** 1960–2024.
- **Why used:** full-history, integer-million authority for the normalized ledger.
- **Canonical member:** `NHE2024.csv`; the paired `NHE2024.xls` is inspected but
  not normalized because its display formatting can obscure not-applicable values.
- **Does not establish:** sponsor, ultimate incidence, procedure, recipient entity,
  FFS/MA split, provider-level payment, real resource cost, or policy merit.

## NHE Tables

[NHE Tables](https://www.cms.gov/files/zip/nhe-tables.zip)

- **Represents:** 31 official detailed and presentation tables with table-specific
  coverage and units.
- **Coverage used:** Table 5 sponsor amounts, 1987–2024; Table 19 separate-format
  2024 matrix validation. Other tables are archived and structurally inspected.
- **Why used:** authoritative sponsor view and a separate-format exact-million check of
  the 2024 principal matrix.
- **Does not establish:** a service × sponsor cube. Table 4's rounded billions are
  not substituted for the principal exact-million history.

## NHE Summary including GDP share

[NHE Summary, CY 1960–2024](https://www.cms.gov/files/zip/nhe-summary-including-share-gdp-cy-1960-2024.zip)

- **Represents:** NHE/HCE/PHC amounts, population, GDP, growth, distributions,
  per-capita spending, and NHE/GDP.
- **Coverage:** 1960–2024.
- **Why used:** supporting headline and unit review.
- **Does not establish:** payer/service flows for non-dollar rows. Percentage,
  population, per-capita, and GDP rows are not ingested as expenditures.

## Definitions, Sources, and Methods

[NHEA Methodology Paper, 2024](https://www.cms.gov/files/document/definitions-sources-methods.pdf)

- **Version:** last updated January 2026; National Health Expenditures for
  1960–2024.
- **Why used:** governing definitions, NHE/HCE/PHC hierarchy, service methods,
  payer/program definitions, sponsor concepts, and source limitations.
- **Limitation:** methodology defines the account; it is not an additional dollar
  dataset.

## Quick Definitions

[Quick Definitions for NHEA Categories](https://www.cms.gov/files/document/quick-definitions-national-health-expenditures-accounts-nhea-categories.pdf)

- **Why used:** concise CMS terminology for service/type-of-expenditure and
  source-of-funds categories.
- **Limitation:** definitions do not authorize inferred dimensions or policy labels.

## Revision and COVID references

- [Summary of the 2024 comprehensive revision](https://www.cms.gov/files/document/summary-benchmark-changes-2024.pdf) documents the current benchmark vintage and historical revisions.
- [Accounting for Federal COVID Expenditures](https://www.cms.gov/files/document/accounting-federal-covid-expenditures-national-health-expenditure-accounts.pdf) documents the treatment of federal COVID programs and explains unusual 2020–2022 patterns.

These references explain source behavior. They are not added to expenditure totals.

## Deliberately excluded sources

No HCRIS cost reports, Medicare provider claims, Medicare Advantage drill-downs,
hospital price-transparency files, Transparency in Coverage files, international
comparisons, or non-CMS datasets were downloaded for v0.1.
