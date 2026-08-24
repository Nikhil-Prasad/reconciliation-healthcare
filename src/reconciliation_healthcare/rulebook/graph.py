"""Static rule ontology and dependency graph for Stage 2A."""

from __future__ import annotations

from typing import Any

import pandas as pd

from reconciliation_healthcare.rulebook.models import (
    ExecutionStatus,
    PolicyFunction,
    RuleType,
)
from reconciliation_healthcare.rulebook.sources import SOURCES


RULE_COLUMNS = [
    "rule_id",
    "payment_system",
    "rule_name",
    "rule_version",
    "effective_start",
    "effective_end",
    "rule_type",
    "policy_function",
    "unit_of_payment",
    "trigger",
    "input_description",
    "output_description",
    "execution_status",
    "legal_authority",
    "regulatory_authority",
    "source_artifact_id",
    "source_locator",
    "notes",
]

EDGE_COLUMNS = [
    "edge_id",
    "from_rule_id",
    "edge_type",
    "to_rule_id",
    "effective_start",
    "effective_end",
    "notes",
]


def _rule(
    rule_id: str,
    payment_system: str,
    rule_name: str,
    version: str,
    start: str,
    end: str,
    rule_type: RuleType,
    policy_function: PolicyFunction,
    unit: str,
    trigger: str,
    inputs: str,
    outputs: str,
    status: ExecutionStatus,
    legal: str,
    regulatory: str,
    artifact: str,
    locator: str,
    notes: str = "",
) -> dict[str, Any]:
    return dict(
        zip(
            RULE_COLUMNS,
            (
                rule_id,
                payment_system,
                rule_name,
                version,
                start,
                end,
                rule_type.value,
                policy_function.value,
                unit,
                trigger,
                inputs,
                outputs,
                status.value,
                legal,
                regulatory,
                artifact,
                locator,
                notes,
            ),
            strict=True,
        )
    )


def _edge(
    source: str,
    edge_type: str,
    target: str,
    start: str,
    end: str,
    notes: str = "",
) -> dict[str, str]:
    return dict(
        zip(
            EDGE_COLUMNS,
            (
                f"{source}--{edge_type}--{target}",
                source,
                edge_type,
                target,
                start,
                end,
                notes,
            ),
            strict=True,
        )
    )


def build_rule_graph() -> tuple[pd.DataFrame, pd.DataFrame]:
    rules: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    specs = {source.source_artifact_id: source for source in SOURCES}

    pfs_legal = "Social Security Act §1848"
    pfs_reg = "42 CFR Part 414, Subpart B; CY2024 PFS rule CMS-1784-F"
    for artifact_id in (
        "cms_pfs_rvu24a",
        "cms_pfs_rvu24ar",
        "cms_pfs_rvu24b",
        "cms_pfs_rvu24c",
        "cms_pfs_rvu24d",
    ):
        source = specs[artifact_id]
        version = artifact_id.removeprefix("cms_pfs_")
        prefix = f"pfs.{version}"
        if version == "rvu24ar":
            reg = pfs_reg + "; Consolidated Appropriations Act, 2024 conversion-factor update"
        else:
            reg = pfs_reg
        components = (
            ("work_rvu", "Work RVU lookup", RuleType.LOOKUP, PolicyFunction.RESOURCE_PRICING),
            (
                "practice_expense_rvu",
                "Facility/nonfacility practice-expense RVU selection",
                RuleType.SETTING_ADJUSTMENT,
                PolicyFunction.SITE_OF_SERVICE,
            ),
            (
                "malpractice_rvu",
                "Malpractice RVU lookup",
                RuleType.LOOKUP,
                PolicyFunction.RESOURCE_PRICING,
            ),
            (
                "gpci",
                "Locality GPCI lookup",
                RuleType.GEOGRAPHIC_ADJUSTMENT,
                PolicyFunction.GEOGRAPHIC_ADJUSTMENT,
            ),
            (
                "conversion_factor",
                "PFS conversion factor",
                RuleType.BASE_RATE,
                PolicyFunction.BUDGET_NEUTRALITY,
            ),
        )
        for suffix, name, rule_type, policy in components:
            rules.append(
                _rule(
                    f"{prefix}.{suffix}",
                    "PFS",
                    name,
                    version,
                    source.effective_start,
                    source.effective_end,
                    rule_type,
                    policy,
                    "parameter",
                    "Covered PFS code and date of service",
                    "HCPCS/modifier, locality, and setting as applicable",
                    "Effective RVU, GPCI, or conversion-factor parameter",
                    ExecutionStatus.EXECUTABLE,
                    pfs_legal,
                    reg,
                    artifact_id,
                    "PPRRVU and GPCI CSV members",
                )
            )
        base_id = f"{prefix}.base_payment"
        rules.append(
            _rule(
                base_id,
                "PFS",
                "Core geographically adjusted PFS base payment",
                version,
                source.effective_start,
                source.effective_end,
                RuleType.BASE_RATE,
                PolicyFunction.RESOURCE_PRICING,
                "professional service",
                "Active PFS code without an unimplemented special-pricing path",
                "Code, date of service, canonical locality, facility/nonfacility setting",
                "PFS base payment before claim-level adjustments",
                ExecutionStatus.EXECUTABLE,
                pfs_legal,
                reg,
                artifact_id,
                "RVU release documentation formula and numeric CSV members",
                "Final claim adjudication and beneficiary liability are outside this rule.",
            )
        )
        for dependency in (
            "work_rvu",
            "practice_expense_rvu",
            "malpractice_rvu",
            "gpci",
            "conversion_factor",
        ):
            edges.append(
                _edge(
                    base_id,
                    "depends_on",
                    f"{prefix}.{dependency}",
                    source.effective_start,
                    source.effective_end,
                )
            )

    pfs_specials = (
        ("pfs.code_status", "PFS status-code eligibility and special payment path", RuleType.ELIGIBILITY),
        ("pfs.multiple_procedure", "Multiple-procedure pricing", RuleType.REDUCTION),
        ("pfs.bilateral_surgery", "Bilateral-surgery pricing", RuleType.MULTIPLIER),
        ("pfs.assistant_surgery", "Assistant-at-surgery pricing", RuleType.REDUCTION),
        ("pfs.co_surgery", "Co-surgery pricing", RuleType.MULTIPLIER),
        ("pfs.team_surgery", "Team-surgery pricing", RuleType.MULTIPLIER),
        ("pfs.therapy_reduction", "Multiple procedure payment reduction for therapy", RuleType.REDUCTION),
        ("pfs.opps_cap", "OPPS-based imaging payment cap", RuleType.REDUCTION),
        ("pfs.anesthesia", "Anesthesia conversion-factor payment path", RuleType.BASE_RATE),
    )
    for rule_id, name, rule_type in pfs_specials:
        rules.append(
            _rule(
                rule_id,
                "PFS",
                name,
                "CY2024",
                "2024-01-01",
                "2024-12-31",
                rule_type,
                PolicyFunction.UTILIZATION_CONTROL
                if rule_type in {RuleType.REDUCTION, RuleType.ELIGIBILITY}
                else PolicyFunction.RESOURCE_PRICING,
                "professional service or claim",
                "Applicable code indicator and claim context",
                "Claim lines and modifiers not present in Stage 2A",
                "Adjusted payment",
                ExecutionStatus.DEFERRED,
                pfs_legal,
                pfs_reg,
                "cms_pfs_rvu24a",
                "RVU24A documentation and payment-policy indicators",
                "The PFS engine fails closed when the selected code requires this path.",
            )
        )

    opps_legal = "Social Security Act §1833(t)"
    opps_reg = "42 CFR Part 419; CY2024 OPPS rule CMS-1786-FC and correction CMS-1786-CN"
    for artifact_id in (
        "cms_opps_2024_q1_addendum_b",
        "cms_opps_2024_q2_addendum_b",
        "cms_opps_2024_q3_addendum_b",
        "cms_opps_2024_q4_addendum_b",
    ):
        source = specs[artifact_id]
        version = artifact_id.split("_")[3]
        prefix = f"opps.2024_{version}"
        classification = f"{prefix}.hcpcs_status_apc"
        rate = f"{prefix}.published_rate"
        rules.extend(
            [
                _rule(
                    classification,
                    "OPPS",
                    "HCPCS status-indicator and APC assignment",
                    version,
                    source.effective_start,
                    source.effective_end,
                    RuleType.CLASSIFICATION,
                    PolicyFunction.RESOURCE_PRICING,
                    "hospital outpatient service",
                    "HCPCS present in effective Addendum B",
                    "HCPCS and service date",
                    "Status indicator and APC assignment",
                    ExecutionStatus.LOOKUP_ONLY,
                    opps_legal,
                    opps_reg,
                    artifact_id,
                    "Addendum B CSV",
                ),
                _rule(
                    rate,
                    "OPPS",
                    "Published national OPPS payment rate",
                    version,
                    source.effective_start,
                    source.effective_end,
                    RuleType.BASE_RATE,
                    PolicyFunction.RESOURCE_PRICING,
                    "hospital outpatient service",
                    "Addendum B row has a published payment rate",
                    "HCPCS, service date, status indicator, APC",
                    "Published national base rate before provider-specific adjustments",
                    ExecutionStatus.LOOKUP_ONLY,
                    opps_legal,
                    opps_reg,
                    artifact_id,
                    "Addendum B Payment Rate column",
                    "Lookup is not a final OPPS claim payment.",
                ),
            ]
        )
        edges.append(
            _edge(rate, "depends_on", classification, source.effective_start, source.effective_end)
        )

    opps_documented = (
        ("opps.packaging", "OPPS packaging", RuleType.PACKAGING, ExecutionStatus.DOCUMENTED_ONLY),
        (
            "opps.comprehensive_apc",
            "Comprehensive APC packaging",
            RuleType.PACKAGING,
            ExecutionStatus.DOCUMENTED_ONLY,
        ),
        (
            "opps.wage_adjustment",
            "Provider wage-index adjustment",
            RuleType.GEOGRAPHIC_ADJUSTMENT,
            ExecutionStatus.DEFERRED,
        ),
        ("opps.outlier", "OPPS outlier payment", RuleType.OUTLIER, ExecutionStatus.DEFERRED),
        (
            "opps.pass_through",
            "Device and drug pass-through payment",
            RuleType.ADD_ON,
            ExecutionStatus.DEFERRED,
        ),
        (
            "opps.restated_drug_rate",
            "Versioned restated drug and biological rate overlay",
            RuleType.BASE_RATE,
            ExecutionStatus.DEFERRED,
        ),
        ("opps.final_payment", "Final OPPS claim payment", RuleType.BASE_RATE, ExecutionStatus.DEFERRED),
    )
    for rule_id, name, rule_type, status in opps_documented:
        policy = {
            RuleType.GEOGRAPHIC_ADJUSTMENT: PolicyFunction.GEOGRAPHIC_ADJUSTMENT,
            RuleType.OUTLIER: PolicyFunction.RISK_ADJUSTMENT,
            RuleType.PACKAGING: PolicyFunction.UTILIZATION_CONTROL,
            RuleType.ADD_ON: PolicyFunction.INNOVATION_SUBSIDY,
        }.get(rule_type, PolicyFunction.RESOURCE_PRICING)
        rules.append(
            _rule(
                rule_id,
                "OPPS",
                name,
                "CY2024",
                "2024-01-01",
                "2024-12-31",
                rule_type,
                policy,
                "hospital outpatient claim",
                "Applicable status, APC, provider, or claim context",
                "Full outpatient claim context",
                "Payment adjustment or final payment",
                status,
                opps_legal,
                opps_reg,
                "cms_opps_2024_final_addenda",
                "CY2024 OPPS regulation and quarterly Addendum B status indicators",
            )
        )
    for artifact_id in (
        "cms_opps_2024_q1_addendum_b",
        "cms_opps_2024_q2_addendum_b",
        "cms_opps_2024_q3_addendum_b",
        "cms_opps_2024_q4_addendum_b",
    ):
        source = specs[artifact_id]
        version = artifact_id.split("_")[3]
        rate = f"opps.2024_{version}.published_rate"
        edges.append(
            _edge(
                "opps.final_payment",
                "depends_on",
                rate,
                source.effective_start,
                source.effective_end,
            )
        )
    for target in ("opps.packaging", "opps.comprehensive_apc", "opps.wage_adjustment"):
        edges.append(_edge("opps.final_payment", "may_apply", target, "2024-01-01", "2024-12-31"))
    for target in ("opps.outlier", "opps.pass_through"):
        edges.append(_edge("opps.final_payment", "may_add", target, "2024-01-01", "2024-12-31"))
    edges.append(
        _edge(
            "opps.final_payment",
            "may_apply",
            "opps.restated_drug_rate",
            "2024-01-01",
            "2024-12-31",
        )
    )

    ipps_legal = "Social Security Act §1886(d)"
    ipps_sources = (
        (
            "fy2024",
            "2023-10-01",
            "2024-09-30",
            "cms_ipps_fy2024_table1",
            "cms_ipps_fy2024_wage_tables",
            "cms_ipps_fy2024_table5",
            "42 CFR Part 412; CMS-1785-F, CMS-1785-CN, and CMS-1785-CN2",
        ),
        (
            "fy2025",
            "2024-10-01",
            "2025-09-30",
            "cms_ipps_fy2025_table1",
            "cms_ipps_fy2025_wage_tables",
            "cms_ipps_fy2025_table5",
            "42 CFR Part 412; CMS-1808-F, CMS-1808-CN2, and CMS-1808-IFC",
        ),
    )
    for version, start, end, table1, wage, table5, regulatory in ipps_sources:
        prefix = f"ipps.{version}"
        component_specs = (
            ("ms_drg_weight", "MS-DRG relative-weight lookup", RuleType.LOOKUP, table5),
            (
                "standardized_amount",
                "Operating standardized labor/nonlabor amounts",
                RuleType.BASE_RATE,
                table1,
            ),
            (
                "wage_index",
                "Provider wage-index lookup",
                RuleType.GEOGRAPHIC_ADJUSTMENT,
                wage,
            ),
        )
        for suffix, name, rule_type, artifact in component_specs:
            rules.append(
                _rule(
                    f"{prefix}.{suffix}",
                    "IPPS",
                    name,
                    version.upper(),
                    start,
                    end,
                    rule_type,
                    PolicyFunction.GEOGRAPHIC_ADJUSTMENT
                    if suffix == "wage_index"
                    else PolicyFunction.RESOURCE_PRICING,
                    "inpatient discharge",
                    "Acute IPPS discharge in fiscal year",
                    "MS-DRG, provider CCN, quality/EHR category",
                    "Effective IPPS base-payment parameter",
                    ExecutionStatus.EXECUTABLE,
                    ipps_legal,
                    regulatory,
                    artifact,
                    "Corrected/final table workbook",
                )
            )
        base = f"{prefix}.base_operating_payment"
        rules.append(
            _rule(
                base,
                "IPPS",
                "Wage-adjusted base operating MS-DRG payment",
                version.upper(),
                start,
                end,
                RuleType.BASE_RATE,
                PolicyFunction.RESOURCE_PRICING,
                "inpatient discharge",
                "MS-DRG and provider CCN resolve to effective CMS parameters",
                "MS-DRG, discharge date, provider CCN, quality/EHR flags",
                "Base operating payment before transfer and provider/claim adjustments",
                ExecutionStatus.EXECUTABLE,
                ipps_legal,
                regulatory,
                table1,
                "Tables 1A/1B, 2, and 5",
                "MS-DRG is an input; Stage 2A is not a grouper and does not calculate final payment.",
            )
        )
        for dependency in ("ms_drg_weight", "standardized_amount", "wage_index"):
            edges.append(_edge(base, "depends_on", f"{prefix}.{dependency}", start, end))

    ipps_adjustments = (
        ("ipps.ime", "Indirect medical education", RuleType.ADD_ON, PolicyFunction.TEACHING_SUBSIDY),
        ("ipps.dsh", "Disproportionate share hospital", RuleType.ADD_ON, PolicyFunction.SAFETY_NET),
        (
            "ipps.uncompensated_care",
            "Uncompensated care payment",
            RuleType.ADD_ON,
            PolicyFunction.UNCOMPENSATED_CARE,
        ),
        ("ipps.ntap", "New technology add-on payment", RuleType.ADD_ON, PolicyFunction.INNOVATION_SUBSIDY),
        ("ipps.outlier", "High-cost outlier", RuleType.OUTLIER, PolicyFunction.RISK_ADJUSTMENT),
        ("ipps.hrrp", "Hospital Readmissions Reduction Program", RuleType.QUALITY_ADJUSTMENT, PolicyFunction.QUALITY_INCENTIVE),
        ("ipps.vbp", "Hospital Value-Based Purchasing", RuleType.QUALITY_ADJUSTMENT, PolicyFunction.QUALITY_INCENTIVE),
        ("ipps.hac", "Hospital-Acquired Condition Reduction Program", RuleType.QUALITY_ADJUSTMENT, PolicyFunction.QUALITY_INCENTIVE),
        ("ipps.transfer", "Post-acute and short-stay transfer policy", RuleType.REDUCTION, PolicyFunction.UTILIZATION_CONTROL),
        ("ipps.final_payment", "Final IPPS claim payment", RuleType.BASE_RATE, PolicyFunction.RESOURCE_PRICING),
    )
    for rule_id, name, rule_type, policy in ipps_adjustments:
        rules.append(
            _rule(
                rule_id,
                "IPPS",
                name,
                "CY2024 coverage",
                "2024-01-01",
                "2024-12-31",
                rule_type,
                policy,
                "inpatient discharge or provider",
                "Applicable claim/provider conditions",
                "Provider-specific and claim-level context outside Stage 2A",
                "Adjustment or final payment",
                ExecutionStatus.DEFERRED,
                ipps_legal,
                "42 CFR Part 412; FY2024/FY2025 IPPS annual rules",
                "cms_ipps_fy2024_table1",
                "Annual rule and supporting tables",
            )
        )
    for version, start, end, *_ in ipps_sources:
        base = f"ipps.{version}.base_operating_payment"
        edges.append(
            _edge(
                "ipps.final_payment",
                "depends_on",
                base,
                max(start, "2024-01-01"),
                min(end, "2024-12-31"),
            )
        )
    for target in ("ipps.ime", "ipps.dsh", "ipps.uncompensated_care", "ipps.ntap", "ipps.outlier"):
        edges.append(_edge("ipps.final_payment", "may_add", target, "2024-01-01", "2024-12-31"))
    for target in ("ipps.hrrp", "ipps.vbp", "ipps.hac", "ipps.transfer"):
        edges.append(_edge("ipps.final_payment", "may_apply", target, "2024-01-01", "2024-12-31"))

    rules.extend(
        [
            _rule(
                "site.office_professional_path",
                "CROSS_SYSTEM",
                "Office professional payment path",
                "CY2024",
                "2024-01-01",
                "2024-12-31",
                RuleType.SETTING_ADJUSTMENT,
                PolicyFunction.SITE_OF_SERVICE,
                "professional service",
                "Office/nonfacility setting",
                "Code, service date, locality",
                "PFS nonfacility professional base-payment path",
                ExecutionStatus.DOCUMENTED_ONLY,
                pfs_legal,
                pfs_reg,
                "cms_pfs_rvu24a",
                "RVU release facility/nonfacility formula",
            ),
            _rule(
                "site.hospital_outpatient_path",
                "CROSS_SYSTEM",
                "Hospital outpatient professional plus facility paths",
                "CY2024",
                "2024-01-01",
                "2024-12-31",
                RuleType.SETTING_ADJUSTMENT,
                PolicyFunction.SITE_OF_SERVICE,
                "professional service and possible outpatient facility service",
                "Hospital outpatient/facility setting",
                "Code, service date, locality, outpatient facility context",
                "PFS facility professional path plus a potentially separate OPPS facility path",
                ExecutionStatus.DOCUMENTED_ONLY,
                "Social Security Act §§1833(t), 1848",
                f"{pfs_reg}; {opps_reg}",
                "cms_opps_2024_final_addenda",
                "PFS setting formula and OPPS Addendum B",
            ),
        ]
    )
    for artifact_id in (
        "cms_pfs_rvu24a",
        "cms_pfs_rvu24ar",
        "cms_pfs_rvu24b",
        "cms_pfs_rvu24c",
        "cms_pfs_rvu24d",
    ):
        source = specs[artifact_id]
        version = artifact_id.removeprefix("cms_pfs_")
        edges.append(
            _edge(
                "site.office_professional_path",
                "routes_to",
                f"pfs.{version}.base_payment",
                source.effective_start,
                source.effective_end,
                "Select nonfacility PE RVU.",
            )
        )
        edges.append(
            _edge(
                "site.hospital_outpatient_path",
                "routes_to",
                f"pfs.{version}.base_payment",
                source.effective_start,
                source.effective_end,
                "Select facility PE RVU.",
            )
        )
    for artifact_id in (
        "cms_opps_2024_q1_addendum_b",
        "cms_opps_2024_q2_addendum_b",
        "cms_opps_2024_q3_addendum_b",
        "cms_opps_2024_q4_addendum_b",
    ):
        source = specs[artifact_id]
        quarter = artifact_id.split("_")[3]
        edges.append(
            _edge(
                "site.hospital_outpatient_path",
                "may_combine_with",
                f"opps.2024_{quarter}.published_rate",
                source.effective_start,
                source.effective_end,
                "A separate facility payment is possible; claim adjudication is not inferred.",
            )
        )

    rule_frame = pd.DataFrame.from_records(rules, columns=RULE_COLUMNS)
    edge_frame = pd.DataFrame.from_records(edges, columns=EDGE_COLUMNS)
    return rule_frame.sort_values("rule_id", ignore_index=True), edge_frame.sort_values(
        "edge_id", ignore_index=True
    )
