"""Effective-dated CY2024 OPPS HCPCS classification and rate lookup."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

import pandas as pd

from reconciliation_healthcare.rulebook.models import (
    AmountKind,
    CalculationStatus,
    DateBasis,
    PaymentTrace,
    PaymentUnit,
)
from reconciliation_healthcare.rulebook.provenance import enrich_trace_sources
from reconciliation_healthcare.rulebook.store import RulebookStore
from reconciliation_healthcare.rulebook.temporal import (
    TemporalResolutionError,
    as_date,
    select_effective,
)


_CLAIM_CONTEXT_STATUS_INDICATORS = {
    "H",
    "J1",
    "J2",
    "N",
    "P",
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "T",
}

_PACKAGING_RULES = {
    "A": "Not paid under OPPS; another Medicare fee schedule or payment system applies.",
    "B": "Not recognized for payment on a hospital outpatient Part B bill.",
    "C": "Inpatient-only procedure; not paid under OPPS.",
    "D": "Discontinued code; not paid under OPPS.",
    "E1": "Not payable by Medicare on an outpatient claim.",
    "E2": "Not payable because OPPS pricing or claims information is unavailable.",
    "F": "Not paid under OPPS; reasonable-cost payment applies.",
    "G": "Separately payable OPPS pass-through drug or biological.",
    "H": "Separate cost-based pass-through device payment; claim costs are required.",
    "J1": (
        "Comprehensive APC: covered Part B claim services are generally packaged into the "
        "primary J1 service, subject to CMS exclusions."
    ),
    "J2": (
        "Comprehensive-APC treatment may apply based on the services reported together; "
        "otherwise the service may be separately paid or packaged."
    ),
    "K": "Separately payable non-pass-through drug or biological under OPPS.",
    "L": "Not paid under OPPS; reasonable-cost vaccine or biological payment applies.",
    "M": "Not billable to the Medicare Administrative Contractor.",
    "N": "Packaged into payment for other services; there is no separate APC payment.",
    "P": "Paid under OPPS through a partial-hospitalization or intensive-outpatient per diem.",
    "Q1": (
        "Conditionally packaged with an S, T, or V service or under composite-APC rules; "
        "otherwise separately payable."
    ),
    "Q2": "Conditionally packaged with a T service; otherwise separately payable.",
    "Q3": "Composite-APC criteria may package the service; otherwise separate or packaged payment applies.",
    "Q4": (
        "Conditionally packaged laboratory test when reported with specified OPPS services; "
        "otherwise the Clinical Laboratory Fee Schedule applies."
    ),
    "R": "Separately payable blood or blood product under OPPS.",
    "S": "Separately payable OPPS service without a multiple-procedure discount.",
    "T": "Separately payable OPPS service subject to a possible multiple-procedure reduction.",
    "U": "Separately payable brachytherapy source under OPPS.",
    "V": "Separately payable OPPS clinic or emergency-department visit.",
    "Y": "Not paid under OPPS; durable-medical-equipment billing rules apply.",
}


def _optional_text(value: Any) -> str | None:
    if value is None or value is pd.NA:
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text or None


def _optional_decimal(value: Any, *, field: str) -> Decimal | None:
    text = _optional_text(value)
    if text is None:
        return None
    normalized = text.replace("$", "").replace(",", "")
    try:
        return Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(f"Invalid OPPS {field} value {value!r}") from error


def _unsupported_trace(
    *,
    code: str,
    service_date: date,
    missing_rule: str,
    warning: str,
    missing_parameters: list[str] | None = None,
    selected_rule_versions: list[dict[str, Any]] | None = None,
    selected_parameters: list[dict[str, Any]] | None = None,
    source_artifact_ids: list[str] | None = None,
) -> PaymentTrace:
    return PaymentTrace(
        payment_system="OPPS",
        service_date=service_date,
        payment_unit=PaymentUnit.OUTPATIENT_HCPCS_LOOKUP,
        date_basis=DateBasis.SERVICE_DATE,
        calculation_status=CalculationStatus.UNSUPPORTED,
        input_context={"code": code},
        selected_rule_versions=selected_rule_versions or [],
        selected_parameters=selected_parameters or [],
        source_artifact_ids=source_artifact_ids or [],
        missing_rule=missing_rule,
        missing_parameters=missing_parameters or [],
        warnings=[warning],
    )


def _selected_rule(
    assignment: Mapping[str, Any], service_date: date, store: RulebookStore
) -> dict[str, Any]:
    rule_id = _optional_text(assignment.get("rule_id"))
    if rule_id is None:
        raise KeyError("OPPS assignment has no rule_id")
    rule = store.rule(rule_id)
    select_effective([rule], service_date, label=f"OPPS rule {rule_id}")
    return rule


def _claim_context_warning(status_indicator: str) -> str:
    if status_indicator in {"J1", "J2"}:
        return (
            f"Status indicator {status_indicator} requires the complete claim for comprehensive-APC "
            "primary-service ranking, packaging, complexity adjustments, and exclusions."
        )
    if status_indicator == "N":
        return (
            "Status indicator N has no separate APC payment; claim context is required to identify "
            "the service into which it is packaged."
        )
    return (
        f"Status indicator {status_indicator} requires claim context before its claim-level payment "
        "treatment can be determined."
    )


def _lookup_opps(
    code: str,
    service_date: date | str,
    store: RulebookStore,
) -> PaymentTrace:
    """Look up the effective OPPS status, APC, and published national rate.

    This intentionally stops before claim adjudication.  The returned amount, when present, is the
    Addendum B national unadjusted lookup value and is never represented as a final OPPS payment.
    """

    target = as_date(service_date)
    normalized_code = str(code).strip().upper()
    if not normalized_code:
        return _unsupported_trace(
            code=normalized_code,
            service_date=target,
            missing_rule="opps_hcpcs:<blank>",
            warning="An OPPS lookup requires a nonblank HCPCS code.",
        )

    assignments = store.code_assignments
    candidates = assignments[
        assignments["payment_system"].astype("string").str.upper().eq("OPPS")
        & assignments["assignment_type"].astype("string").eq("opps_hcpcs")
        & assignments["code"].astype("string").str.upper().eq(normalized_code)
    ]
    if candidates.empty:
        return _unsupported_trace(
            code=normalized_code,
            service_date=target,
            missing_rule=f"opps_hcpcs:{normalized_code}",
            warning=f"No OPPS HCPCS assignment exists for {normalized_code}; lookup failed closed.",
        )

    try:
        assignment = select_effective(
            candidates.to_dict(orient="records"),
            target,
            label=f"OPPS HCPCS assignment for {normalized_code}",
        )
    except (TemporalResolutionError, ValueError) as error:
        return _unsupported_trace(
            code=normalized_code,
            service_date=target,
            missing_rule=f"effective opps_hcpcs:{normalized_code}",
            missing_parameters=["unambiguous effective OPPS assignment for service_date"],
            warning=f"OPPS effective-date resolution failed closed: {error}",
        )

    value_status = _optional_text(assignment.get("value_status"))
    if value_status == "unresolved_effective_date":
        return _unsupported_trace(
            code=normalized_code,
            service_date=target,
            missing_rule=_optional_text(assignment.get("rule_id"))
            or f"effective opps_hcpcs:{normalized_code}",
            missing_parameters=["resolved code-specific effective date"],
            warning=(
                "The selected quarterly OPPS row changed without a normalized code-specific "
                "effective date; lookup failed closed."
            ),
        )

    try:
        rule = _selected_rule(assignment, target, store)
    except (KeyError, TemporalResolutionError, ValueError) as error:
        return _unsupported_trace(
            code=normalized_code,
            service_date=target,
            missing_rule=_optional_text(assignment.get("rule_id"))
            or f"effective opps_hcpcs:{normalized_code}",
            missing_parameters=["effective OPPS rule version"],
            warning=f"OPPS rule resolution failed closed: {error}",
        )

    source_artifact_id = _optional_text(assignment.get("source_artifact_id"))
    if value_status == "requires_restated_drug_overlay":
        return _unsupported_trace(
            code=normalized_code,
            service_date=target,
            missing_rule="opps.restated_drug_rate",
            missing_parameters=["versioned restated drug/biological rate overlay"],
            selected_rule_versions=[rule],
            selected_parameters=[
                {
                    "assignment_id": _optional_text(assignment.get("assignment_id")),
                    "value_status": value_status,
                    "source_artifact_id": source_artifact_id,
                    "source_locator": _optional_text(assignment.get("source_locator")),
                }
            ],
            source_artifact_ids=[source_artifact_id] if source_artifact_id else [],
            warning=(
                "The selected drug/biological row requires a versioned CMS restatement overlay; "
                "lookup failed closed rather than returning a potentially superseded rate."
            ),
        )

    status_indicator = (_optional_text(assignment.get("status_indicator")) or "").upper()
    if not status_indicator:
        return _unsupported_trace(
            code=normalized_code,
            service_date=target,
            missing_rule=str(rule["rule_id"]),
            missing_parameters=["status_indicator"],
            warning="The effective OPPS assignment has no status indicator; lookup failed closed.",
        )

    apc = _optional_text(assignment.get("apc"))
    relative_weight = _optional_decimal(
        assignment.get("relative_weight"), field="relative weight"
    )
    payment_rate = _optional_decimal(assignment.get("payment_rate"), field="payment rate")
    claim_context_required = status_indicator in _CLAIM_CONTEXT_STATUS_INDICATORS
    packaging_rule = _PACKAGING_RULES.get(
        status_indicator,
        f"Status indicator {status_indicator} is not modeled; no payment treatment is inferred.",
    )

    warnings = [
        "This is an OPPS Addendum B lookup, not a final hospital outpatient claim payment.",
        (
            "Provider wage adjustment, outlier payment, claim-level packaging, beneficiary cost "
            "sharing, units, modifiers, and other claim/provider-specific adjustments are not applied."
        ),
    ]
    unsupported_adjustments = [
        "provider-specific OPPS wage adjustment",
        "OPPS outlier payment",
        "claim-level packaging",
        "final claim adjudication",
    ]
    if claim_context_required:
        warnings.append(_claim_context_warning(status_indicator))
        unsupported_adjustments.append("status-indicator-specific claim-level treatment")
    if status_indicator not in _PACKAGING_RULES:
        warnings.append(
            f"Status indicator {status_indicator} has no modeled packaging interpretation."
        )
        unsupported_adjustments.append("unmodeled status-indicator treatment")
    if payment_rate is None:
        warnings.append("The effective Addendum B row has no published national payment rate.")
    selected_rules = [rule]
    if payment_rate is not None:
        rate_rule_id = str(rule["rule_id"]).replace(".hcpcs_status_apc", ".published_rate")
        try:
            rate_rule = store.rule(rate_rule_id)
            select_effective([rate_rule], target, label=f"OPPS rule {rate_rule_id}")
            selected_rules.append(rate_rule)
        except (KeyError, TemporalResolutionError, ValueError) as error:
            return _unsupported_trace(
                code=normalized_code,
                service_date=target,
                missing_rule=rate_rule_id,
                missing_parameters=["effective OPPS published-rate rule"],
                selected_rule_versions=[rule],
                source_artifact_ids=[source_artifact_id] if source_artifact_id else [],
                warning=f"OPPS published-rate rule resolution failed closed: {error}",
            )

    policy_rule_ids = ["opps.packaging"]
    if status_indicator in {"J1", "J2"}:
        policy_rule_ids.append("opps.comprehensive_apc")
    for policy_rule_id in policy_rule_ids:
        try:
            policy_rule = store.rule(policy_rule_id)
            select_effective(
                [policy_rule], target, label=f"OPPS rule {policy_rule_id}"
            )
            selected_rules.append(policy_rule)
        except (KeyError, TemporalResolutionError, ValueError) as error:
            return _unsupported_trace(
                code=normalized_code,
                service_date=target,
                missing_rule=policy_rule_id,
                missing_parameters=["effective OPPS packaging-policy rule"],
                selected_rule_versions=selected_rules,
                source_artifact_ids=[source_artifact_id] if source_artifact_id else [],
                warning=f"OPPS packaging-policy resolution failed closed: {error}",
            )

    selected_parameter = {
        "assignment_id": _optional_text(assignment.get("assignment_id")),
        "assignment_type": "opps_hcpcs",
        "code": normalized_code,
        "effective_start": assignment.get("effective_start"),
        "effective_end": assignment.get("effective_end"),
        "status_indicator": status_indicator,
        "apc": apc,
        "relative_weight": relative_weight,
        "payment_rate": payment_rate,
        "value_status": value_status,
        "source_artifact_id": source_artifact_id,
        "source_locator": _optional_text(assignment.get("source_locator")),
    }
    selected_source_ids: list[str] = []
    for record in (assignment, *selected_rules):
        selected_source_id = _optional_text(record.get("source_artifact_id"))
        if selected_source_id and selected_source_id not in selected_source_ids:
            selected_source_ids.append(selected_source_id)

    return PaymentTrace(
        payment_system="OPPS",
        service_date=target,
        amount_kind=AmountKind.OPPS_PUBLISHED_RATE,
        payment_unit=PaymentUnit.OUTPATIENT_HCPCS_LOOKUP,
        date_basis=DateBasis.SERVICE_DATE,
        calculation_status=CalculationStatus.LOOKUP_ONLY,
        input_context={"code": normalized_code},
        selected_rule_versions=selected_rules,
        selected_parameters=[selected_parameter],
        components={
            "code": normalized_code,
            "status_indicator": status_indicator,
            "apc": apc,
            "relative_weight": relative_weight,
            "published_national_rate": payment_rate,
            "packaging_rule": packaging_rule,
            "claim_context_required": claim_context_required,
            "value_status": value_status,
        },
        calculated_amount=payment_rate,
        amount_label="published national unadjusted OPPS payment rate (not final claim payment)",
        unsupported_adjustments=unsupported_adjustments,
        warnings=warnings,
        source_artifact_ids=selected_source_ids,
    )


def lookup_opps(
    code: str,
    service_date: date | str,
    store: RulebookStore,
) -> PaymentTrace:
    """Return the OPPS lookup trace with all linked source authorities."""

    return enrich_trace_sources(_lookup_opps(code, service_date, store), store)
