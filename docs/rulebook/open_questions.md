# Open questions and Stage 2B candidates

Stage 2A deliberately leaves these questions open rather than embedding an
unverified assumption:

1. Expand PFS code-level effective-date overlays from every quarterly change
   request, including the machine-readable October attachment, and determine
   whether CMS can supply structured April/July exception files.
2. Normalize OPPS quarterly change-request exceptions and the full versioned
   sequence of later drug/biological restatements with an explicit
   `as_of_release` dimension.
3. Add provider-specific OPPS wage adjustment only after CCN, OQR status,
   reclassification, cap, rural SCH/EACH, and out-migration inputs can all be
   resolved without inventing context.
4. Decide whether the licensed I/OCE runtime can be used locally as an optional
   validation layer without redistributing licensed content. It should not
   replace Addendum B as the published-rate authority.
5. Implement PFS anesthesia, OPPS caps, therapy and multiple-procedure
   reductions, PC/TC and modifier paths, and global-surgery interactions.
6. Add IPPS transfer/per-diem, Alaska/Hawaii COLA, Puerto Rico, SCH/MDH,
   low-volume, capital, IME, traditional DSH, uncompensated-care, NTAP,
   outlier, HRRP, VBP, and HAC logic as separately traced components.
7. Add an ICD-10 to MS-DRG grouper only as a distinct later project. Stage 2A
   intentionally treats MS-DRG as an input.
8. Establish version-retention policy when CMS mutates a URL in place. The
   current downloader correctly stops on a checksum mismatch and requires a
   reviewed manifest update.

Recommended Stage 2B: finish row-effective PFS/OPPS overlays and provider-aware
OPPS geography before expanding to full institutional claim adjudication.
