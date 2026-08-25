# Authoritative sources

Only first-party CMS and official Federal Register files are authoritative
inputs. The complete, machine-readable inventory is
`data/raw/cms_payment_rules/manifest.json`; it currently pins 32 artifacts by
exact byte count and SHA-256. The downloader refuses to accept changed bytes at
a previously pinned URL.

## PFS

The core inputs are CMS RVU24A, RVU24AR, RVU24B, RVU24C, and RVU24D from the
[PFS Relative Value Files](https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files).
Each archive supplies the PPRRVU, GPCI, locality, anesthesia, OPPS-cap, and
release-documentation members. Stage 2A normalizes only the fields needed for
the ordinary base formula.

CMS's two [CY2024 all-states carrier files](https://www.cms.gov/medicare/payment/fee-schedules/physician/carrier-specific-files/all-states)
are independently pinned to validate calculated locality payment amounts. CMS
change requests CR13529, CR13624, CR13751, and the CR13751 attachment support
row-effective-date treatment.

## OPPS

The core inputs are the four 2024 Addendum B archives on CMS's
[Quarterly Addenda Updates](https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient-pps/quarterly-addenda-updates)
page. The [CMS-1786-FC final-rule addenda](https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient/regulations-notices/cms-1786-fc)
are pinned for status-indicator and C-APC policy definitions. CMS January,
April, revised July, and October update memoranda are pinned for exceptions and
effective-date interpretation.

## IPPS

FY2024 sources are Tables 1A–1E, corrected Tables 2/3/4, and Table 5 on CMS's
[FY2024 final/correction files page](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/acute-inpatient-files-download/files-fy-2024-final-rule-correction-notice).
The CMS-1785-F final rule and both CMS-1785-CN correction notices are
separately pinned from the official Federal Register publication so FY2024
executable and deferred nodes can identify regulatory and supporting authority
independently of numeric tables. CMS-1785-CN2 restored omitted explanatory text
but did not change a Stage 2A numeric input.

FY2025 sources are Tables 1A–1E, Tables 2/3/4, and corrected Table 5 on CMS's
[FY2025 final-rule page](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/fy-2025-ipps-final-rule-home-page).
The parser deliberately selects the FY2025 IFC Table 1 and Table 2 sheets and
the correction-notice Table 5 sheet. CMS-1808-F, CMS-1808-CN2, and
CMS-1808-IFC are also pinned as separate Federal Register artifacts. This keeps
the original annual rule, correction, and superseding wage/rate action distinct.

## Entity provenance and validation roles

The legacy source column on each canonical entity is a convenient direct
pointer, normally to its primary numeric source. Complete provenance is stored
as:

```text
entity → entity_source_links → source_artifact
```

Role labels distinguish numeric authority, regulation, implementation
guidance, corrections, superseding releases, validation references, and
supporting documentation. For example, the corrected Q1 `C9790` assignment
links separately to the Q1 Addendum B, MM13568 retroactive-correction
authority, and the Q2 Addendum B row supplying the corrected numeric fields.

Validation results are labeled by evidence type. Direct parameter checks
compare normalized cells with raw source cells. Structural checks validate
keys, intervals, graph relationships, and provenance. PFS carrier-file cases
are independent payment reproductions because carrier amounts are output
references and are never engine inputs. The expanded IPPS cases independently
exercise normalization and formula reconstruction from raw Tables 1/2/5; CMS
does not provide a separate claim-payment output for those selected cases.

## Archival policy

Raw ZIPs and PDFs are downloaded deterministically into
`data/raw/cms_payment_rules/` and are not committed. This avoids publishing CMS
archives that contain AMA/ADA descriptions and keeps large source data out of
Git. The committed manifest, code, documentation, validation report, and small
rule/trace deliverables are sufficient to redownload and verify the exact
inputs. No third-party summary is substituted for a CMS file.
