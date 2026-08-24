# Acute Inpatient Prospective Payment System

## Implemented boundary

Stage 2A executes the ordinary, full-federal-rate IPPS base operating-payment
path. It takes MS-DRG as an input; it does not group diagnoses and procedures
into an MS-DRG. The public entry point is:

```python
calculate_ipps_base_payment(
    store,
    ms_drg="039",
    discharge_date="2024-09-30",
    provider_ccn="050008",
    quality_submitted=True,
    meaningful_ehr_user=True,
)
```

The engine resolves exactly one effective rule version, MS-DRG weight,
provider wage index, labor standardized amount, and nonlabor standardized
amount. A successful result is labeled
`base_operating_payment_before_adjustments`; it is not a final IPPS claim
payment.

For the supported path, the CMS Pricer formula reduces to:

```text
base operating payment
  = MS-DRG relative weight
    × (
        labor standardized amount × provider wage index
        + nonlabor standardized amount × operating COLA
      )
```

The full Pricer expression also contains the national percentage and midnight
adjustment factor. Both are `1.0` in this ordinary FY2024/FY2025 path. Stage 2A
sets operating COLA to `1.0` only after excluding Alaska and Hawaii. It does not
execute hospital-specific, Puerto Rico, transfer, capital, or add-on paths.

The trace records the four selected rule IDs, four selected parameter or
assignment records, source artifact IDs and cell/row locators, all intermediate
components, the nine-decimal payment, the cent-denominated amount, warnings,
and omitted adjustments.

## Discharge-date fiscal-year resolution

IPPS uses discharge date, not calendar-year service date:

| Rule version | Inclusive discharge dates | CY2024 portion |
|---|---|---|
| FY2024 | 2023-10-01–2024-09-30 | 2024-01-01–2024-09-30 |
| FY2025 | 2024-10-01–2025-09-30 | 2024-10-01–2024-12-31 |

Therefore, a September 30, 2024 discharge resolves to CMS-1785 and an October
1, 2024 discharge resolves to CMS-1808. A date outside the two normalized
fiscal years, a gap, or an overlap returns `UNSUPPORTED`; the engine does not
choose the nearest version.

## Final-rule and correction precedence

### FY2024

The governing sequence is the [CMS-1785-F final rule](https://www.federalregister.gov/documents/2023/08/28/2023-16252/medicare-program-hospital-inpatient-prospective-payment-systems-for-acute-care-hospitals-and-the),
followed by the [CMS-1785-CN correction](https://www.federalregister.gov/documents/2023/10/04/2023-22060/medicare-program-hospital-inpatient-prospective-payment-systems-for-acute-care-hospitals-and-the),
both applicable to discharges beginning October 1, 2023. The correction changed
provider and area wage-index values and uncompensated-care data. CMS did not
recalculate the national standardized amounts, and the fixed-loss outlier
threshold did not change. [CMS-1785-CN2](https://www.federalregister.gov/documents/2023/11/09/2023-24670/medicare-program-hospital-inpatient-prospective-payment-systems-for-acute-care-hospitals-and-the)
restored an omitted comment and response but did not change the payment method
or the Stage 2A numeric inputs.

The normalizer consequently selects:

- final-rule Tables 1A/1B for standardized amounts;
- correction-notice Table 2 for provider wage indexes; and
- final-rule Table 5, column `Weights - 10% Cap Applied`, for MS-DRG weights.

### FY2025

The governing sequence is the [CMS-1808-F final rule](https://www.federalregister.gov/documents/2024/08/28/2024-17021/medicare-and-medicaid-programs-and-the-childrens-health-insurance-program-hospital-inpatient),
the [CMS-1808-CN2 correction](https://www.federalregister.gov/documents/2024/10/02/2024-22501/medicare-and-medicaid-programs-and-the-childrens-health-insurance-program-hospital-inpatient),
and the [CMS-1808-IFC interim final action](https://www.federalregister.gov/documents/2024/10/03/2024-22765/medicare-program-changes-to-the-fiscal-year-2025-hospital-inpatient-prospective-payment-system-ipps).
The correction is applicable to discharges beginning October 1, 2024. The IFC
is effective September 30, 2024 and supplies the FY2025 payment values after
CMS removed the low-wage-index hospital policy following the Bridgeport court
decision.

The normalizer consequently selects:

- IFC Tables 1A/1B, not the August final or correction-only amounts;
- the nested IFC Table 2 provider wage-index sheet; and
- correction-notice Table 5, column `Weights - 10% Cap Applied`.

The IFC did not replace the corrected MS-DRG weights. Combining an August
Table 1 or Table 2 value with the correction-notice Table 5 weight would create
a release mixture that CMS did not use for FY2025 payment.

## Standardized-amount category

Table 1 publishes four operating-rate categories. Both booleans are required;
there is no default to the highest update:

| `quality_submitted` | `meaningful_ehr_user` | Normalized category key |
|---|---|---|
| `True` | `True` | `quality_submitted_ehr_user` |
| `True` | `False` | `quality_submitted_not_ehr_user` |
| `False` | `True` | `quality_not_submitted_ehr_user` |
| `False` | `False` | `quality_not_submitted_not_ehr_user` |

Each category has a labor and nonlabor amount for each labor-share regime. The
parameter key combines the category with `labor_share=67.6` or
`labor_share=62.0`. Missing, non-Boolean, duplicated, or nonnumeric category
inputs fail closed instead of falling back to the full-update amount.

## Provider wage-index selection

Provider CCN is the wage lookup key. Table 2 is preferred to the area-level
Table 3 because Table 2 carries provider reclassification and payment-policy
effects. The executable fields are:

- FY2024 correction notice: `FY 2024 Wage Index With Quartile and Cap`;
- FY2025 IFC: `FY 2025 Wage Index With Cap`.

The normalized wage row stores that actual published value as `wage_index` with
`string_value=with_cap`. An effective date must select exactly one provider row.
A missing or duplicate row is unsupported.

After the final wage index is resolved, the standardized-amount labor share is:

```text
wage index > 1.0000   → 67.6% labor / 32.4% nonlabor → Table 1A
wage index <= 1.0000  → 62.0% labor / 38.0% nonlabor → Table 1B
```

Exactly `1.0000` uses Table 1B. The engine does not choose the share from the
provider's geographic area before reclassification or cap policy.

### Provider-specific wage exceptions

Some Table 2 rows need additional logic beyond the published wage index:

- A nonzero `out_migration_adjustment` is a separate increment in wage-index
  derivation. Stage 2A preserves it as its own parameter and returns
  `UNSUPPORTED`; it does not ignore the increment or expose a partial amount.
- FY2025's `transitional_exception_wage_factor` is a separate payment
  exception for hospitals affected by removal of the low-wage policy. CMS
  explicitly did not redefine the hospital's actual wage index. Stage 2A keeps
  both values separate and returns `UNSUPPORTED`; it never substitutes the
  transition factor into the `wage_index` field.
- Alaska and Hawaii require an operating COLA on the nonlabor component. Until
  the applicable COLA parameter is normalized and traced, CCN prefixes `02`
  and `12`, or explicit AK/HI state context, fail closed.
- Puerto Rico uses the Table 1C special path. CCN prefix `40`, or explicit PR
  context, fails closed rather than using Table 1A/1B.

The CCN-prefix check takes precedence over contradictory caller-supplied state
context, so a known special-geography provider cannot be forced through the
ordinary path.

## Arithmetic and rounding

The engine uses `Decimal`; it does not convert CMS values to binary floating
point. Source precision is retained for standardized amounts, the four-decimal
wage index, and the four-decimal MS-DRG weight. It calculates the complete
expression without rounding the wage-adjusted labor component to cents.

The [official CMS IPPS Pricer source](https://www.cms.gov/PricerSourceCodeSoftware)
calculates the operating federal-specific portion to nine decimal places with
`HALF_UP` rounding. Stage 2A follows that sequence:

```text
1. labor component = labor amount × wage index
2. wage-adjusted standardized amount = labor component + nonlabor amount × COLA
3. unrounded base = wage-adjusted standardized amount × MS-DRG weight
4. quantize base to 0.000000001 using HALF_UP
5. quantize the nine-decimal value to $0.01 using HALF_UP
```

The nine-decimal component remains in the trace so the final cents can be
reproduced without reverse-engineering a displayed amount.

## September 30 / October 1 trace

This boundary fixture uses CCN `050008`, MS-DRG `039`, submitted quality data,
meaningful EHR use, and operating COLA `1.0`. The provider has neither an
out-migration adjustment nor the FY2025 transition exception.

| Component | 2024-09-30 | 2024-10-01 |
|---|---:|---:|
| Rule version | FY2024 | FY2025 |
| MS-DRG weight | 1.1410 | 1.1382 |
| Provider wage index | 1.8744 | 1.7807 |
| Labor share | 67.6% | 67.6% |
| Labor standardized amount | $4,392.49 | $4,478.09 |
| Nonlabor standardized amount | $2,105.28 | $2,146.30 |
| Wage-adjusted labor component | $8,233.283256 | $7,974.134863 |
| Wage-adjusted standardized amount | $10,338.563256 | $10,120.434863 |
| Unrounded base operating payment | $11,796.300675096 | $11,519.0789610666 |
| Nine-decimal base | $11,796.300675096 | $11,519.078961067 |
| Returned amount | **$11,796.30** | **$11,519.08** |

The October change reflects the complete authoritative FY switch: IFC
standardized amounts and provider wage index plus the corrected FY2025 MS-DRG
weight. It is not a statement about hospital cost, adequacy, or overpayment.

## Base operating payment is not final payment

The returned amount prices the ordinary wage-adjusted MS-DRG resource component
only. A calculated trace always warns that it is not a final claim and lists
the omitted mechanisms. The rule graph separates each mechanism by policy
function rather than treating every dollar as the price of medical production:

| Mechanism | Policy function | Stage 2A status | Why it is separate or deferred |
|---|---|---|---|
| MS-DRG base and standardized amount | `resource_pricing` | Executable | Ordinary operating resource-price path described above. |
| Wage index | `geographic_adjustment` | Executable for clean Table 2 rows | Adjusts only the labor-related portion; provider exceptions fail closed. |
| Out-migration and FY2025 transition exception | `geographic_adjustment` | Deferred; fail closed | Separate provider-specific increments/exceptions are preserved but not folded into the published wage index. |
| Alaska/Hawaii operating COLA | `geographic_adjustment` | Deferred; fail closed | Requires an effective nonlabor COLA parameter. |
| Puerto Rico Table 1C path | `geographic_adjustment` | Deferred; fail closed | Uses a special standardized-amount path rather than ordinary Table 1A/1B selection. |
| IME | `teaching_subsidy` | Deferred | Requires provider resident-to-bed and graduate-medical-education context. |
| Traditional DSH | `safety_net` | Deferred | Requires provider eligibility and disproportionate-patient inputs. |
| Uncompensated care | `uncompensated_care` | Deferred | Separate statutory pool and provider Factor 3 allocation; not part of the DRG base. |
| NTAP | `innovation_subsidy` | Deferred | Requires technology-identifying claim codes, case cost, CCR, pathway, and maximum-add-on rules. |
| High-cost outlier | `risk_adjustment` | Deferred | Requires covered charges, provider CCR, fixed-loss threshold, and other payment components. |
| HRRP | `quality_incentive` | Deferred | Provider-specific readmission adjustment is not applied to the Stage 2A base. |
| VBP | `quality_incentive` | Deferred | Actual provider VBP factor and eligibility are not applied. |
| HAC reduction | `quality_incentive` | Deferred | Hospital-specific program status and reduction are not applied. |
| Post-acute/short-stay transfer policy | `utilization_control` | Deferred | Requires discharge status, covered days, geometric mean length of stay, and transfer-specific per-diem logic. |
| Capital IPPS | `resource_pricing` | Deferred | Capital is a distinct federal payment calculation, not part of operating base. |
| SCH/MDH, low-volume, hospital-specific and other adjustments | `unknown` until individually classified | Deferred | Provider-specific eligibility and parameters are outside this execution boundary. |

Beneficiary cost sharing, sequestration, claim edits, payment recoupments, and
Medicare Secondary Payer coordination are also outside this amount. The trace
must not be relabeled `final_payment` unless every applicable dependency is
actually executed.

## Official CMS sources

### FY2024 machine-readable inputs

- [FY2024 final/correction files landing page](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/acute-inpatient-files-download/files-fy-2024-final-rule-correction-notice)
- [Tables 1A–1E](https://www.cms.gov/files/zip/fy2024-ipps-fr-table-1a-1e.zip)
- [Corrected Tables 2/3/4](https://www.cms.gov/files/zip/fy2024-ipps-fr-tables-2-3-4.zip)
- [Table 5](https://www.cms.gov/files/zip/fy2024-ipps-fr-table-5.zip)
- [CMS-1785 regulations and notices](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/ipps-regulations-and-notices/cms-1785)

### FY2025 machine-readable inputs

- [FY2025 final-rule landing page](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/fy-2025-ipps-final-rule-home-page)
- [Tables 1A–1E with IFC sheet](https://www.cms.gov/files/zip/fy-2025-ipps-final-rule-table-1a-1e.zip)
- [Tables 2/3/4 with nested IFC workbook](https://www.cms.gov/files/zip/fy-2025-ipps-final-rule-tables-2-3-and-4a-and-4b.zip)
- [Corrected Table 5](https://www.cms.gov/files/zip/fy-2025-ipps-final-rule-table-5.zip)
- [CMS-1808 regulations and notices](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/ipps-regulations-and-notices/cms-1808)

Exact local filenames, release labels, inclusive intervals, HTTP metadata,
byte sizes, and SHA-256 checksums are recorded in
`data/raw/cms_payment_rules/manifest.json`. Raw CMS files remain local and are
not committed.
