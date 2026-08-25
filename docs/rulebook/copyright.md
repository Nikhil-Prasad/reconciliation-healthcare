# Copyright and licensed-code boundary

This repository is designed to reproduce payment-rule mechanics without
redistributing licensed clinical-code content. This is a conservative project
policy, not a legal opinion or a substitute for reviewing the applicable license.

## Source terms

Some official CMS payment files contain Current Procedural Terminology (CPT)
material licensed from the American Medical Association. CMS provides the
applicable [AMA point-and-click license](https://www.cms.gov/license/ama) and
[CMS copyright disclaimers](https://www.cms.gov/disclaimers). The scope of any
CPT permission is determined by the AMA and is not enlarged by the fact that a
file is hosted on a federal website.

The Integrated Outpatient Code Editor can also contain UB-04/NUBC material.
CMS's [I/OCE page](https://www.cms.gov/medicare/coding-billing/outpatient-code-editor)
states the relevant American Hospital Association licensing restrictions. The
[quarterly I/OCE packages](https://www.cms.gov/medicare/coding-billing/outpatient-code-editor-oce/quarterly-release-files)
are not vendored or redistributed by this project.

## What the normalizer retains

For the Stage 2A payment paths, local generated tables retain only fields needed
for deterministic payment logic and auditability, such as:

- functional code identifiers and modifiers;
- status and payment-policy indicators;
- APC and MS-DRG identifiers;
- RVUs, relative weights, GPCIs, conversion factors, wage indexes, and published
  payment parameters;
- effective dates and conservative value-status flags; and
- source artifact identifiers, member/row locators, URLs, and checksums.

The numeric fee-schedule and payment parameters are kept separate from clinical
nomenclature. Retaining these fields for a local rulebook does not assert that
any broader use is licensed.

## What is excluded from Git

The repository does not commit:

- CPT short or long descriptions;
- bulk CPT or HCPCS nomenclature tables;
- UB-04/NUBC codes or descriptions;
- raw CMS ZIP, spreadsheet, CSV, text, or PDF source files that may embed
  licensed descriptions; or
- generated code-assignment and parameter Parquet files derived from those
  local sources.

In particular, the OPPS Addendum B parser locates rows by the HCPCS identifier
and reads only the status indicator, APC, relative weight, and payment-rate
fields needed by the rulebook. It does not write the Addendum B short descriptor
to a canonical table. Documentation and test fixtures use only a small set of
functional identifiers and numeric/status values; they do not reproduce code
descriptions.

`.gitignore` keeps `data/raw/cms_payment_rules/` and `data/processed/` local.
The exception is the small committed source manifest, which contains provenance,
download URLs, release metadata, filenames, byte sizes, and SHA-256 checksums,
but no clinical-code descriptions. A user must obtain source files directly from
CMS, review and accept any applicable terms, and build local artifacts.

## Contribution rule

Contributors must not paste descriptors from CMS spreadsheets, I/OCE files,
codebooks, or licensed manuals into source, tests, documentation, examples, or
generated deliverables. A proposed feature that requires code descriptions or
licensed claim-edit content must first establish a separate licensing and access
design. Until then, use neutral identifiers, numeric parameters, source locators,
and links to the official CMS material.
