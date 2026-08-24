# Authoritative sources

Only first-party CMS files are executable inputs. The complete, machine-readable
inventory is `data/raw/cms_payment_rules/manifest.json`; it currently pins 26
artifacts by exact byte count and SHA-256. The downloader refuses to accept
changed bytes at a previously pinned URL.

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

FY2025 sources are Tables 1A–1E, Tables 2/3/4, and corrected Table 5 on CMS's
[FY2025 final-rule page](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/fy-2025-ipps-final-rule-home-page).
The parser deliberately selects the FY2025 IFC Table 1 and Table 2 sheets and
the correction-notice Table 5 sheet.

## Archival policy

Raw ZIPs and PDFs are downloaded deterministically into
`data/raw/cms_payment_rules/` and are not committed. This avoids publishing CMS
archives that contain AMA/ADA descriptions and keeps large source data out of
Git. The committed manifest, code, documentation, validation report, and small
rule/trace deliverables are sufficient to redownload and verify the exact
inputs. No third-party summary is substituted for a CMS file.
