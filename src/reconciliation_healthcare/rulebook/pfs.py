"""Fail-closed execution of the core Medicare Physician Fee Schedule formula."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

import pandas as pd

from reconciliation_healthcare.rulebook.models import CalculationStatus, PaymentTrace
from reconciliation_healthcare.rulebook.provenance import enrich_trace_sources
from reconciliation_healthcare.rulebook.store import RulebookStore


_CENT = Decimal("0.01")
_PFS = "PFS"

_SPECIAL_INDICATORS = {
    "multiple_procedure_indicator": "pfs.multiple_procedure",
    "bilateral_surgery_indicator": "pfs.bilateral_surgery",
    "assistant_surgery_indicator": "pfs.assistant_surgery",
    "co_surgery_indicator": "pfs.co_surgery",
    "team_surgery_indicator": "pfs.team_surgery",
}


class _ResolutionError(ValueError):
    """Internal error carrying a stable fail-closed reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    try:
        return bool(result)
    except (TypeError, ValueError):
        return False


def _text(value: object) -> str:
    if _is_missing(value):
        return ""
    return str(value).strip()


def _key(value: object) -> str:
    return _text(value).upper()


def _as_date(value: object) -> date:
    if _is_missing(value):
        raise ValueError("missing date")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid date {value!r}") from error


def _as_decimal(value: object, *, label: str) -> Decimal:
    if _is_missing(value) or not _text(value):
        raise _ResolutionError(f"{label}:missing_numeric_value")
    try:
        result = value if isinstance(value, Decimal) else Decimal(_text(value))
    except (InvalidOperation, ValueError) as error:
        raise _ResolutionError(f"{label}:invalid_numeric_value") from error
    if not result.is_finite():
        raise _ResolutionError(f"{label}:invalid_numeric_value")
    return result


def _records_matching(
    frame: pd.DataFrame,
    conditions: Mapping[str, object],
    *,
    label: str,
) -> list[dict[str, Any]]:
    missing_columns = [column for column in conditions if column not in frame.columns]
    if missing_columns:
        joined = ",".join(sorted(missing_columns))
        raise _ResolutionError(f"{label}:missing_columns:{joined}")

    records: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        if all(_key(record[column]) == _key(expected) for column, expected in conditions.items()):
            records.append(record)
    return records


def _select_effective_record(
    records: Iterable[dict[str, Any]],
    service_date: date,
    *,
    label: str,
) -> dict[str, Any]:
    candidates = list(records)
    if not candidates:
        raise _ResolutionError(f"{label}:not_found")

    matches: list[dict[str, Any]] = []
    unresolved_dates = False
    for record in candidates:
        try:
            start = _as_date(record.get("effective_start"))
            end = _as_date(record.get("effective_end"))
        except ValueError:
            unresolved_dates = True
            continue
        if end < start:
            unresolved_dates = True
            continue
        if start <= service_date <= end:
            matches.append(record)

    # An undated candidate with the same lookup key could overlap the selected row.
    # Ignoring it would silently guess at the effective rule version.
    if unresolved_dates:
        raise _ResolutionError(f"{label}:unresolved_effective_date")
    if not matches:
        raise _ResolutionError(f"{label}:no_effective_record")
    if len(matches) != 1:
        raise _ResolutionError(f"{label}:ambiguous_effective_record")
    return matches[0]


def _value_is_unresolved(value: object) -> bool:
    status = _text(value).lower().replace("-", "_").replace(" ", "_")
    if not status:
        return True
    return any(
        marker in status
        for marker in (
            "unresolved",
            "missing",
            "not_published",
            "not_available",
            "unavailable",
            "invalid",
            "unknown",
            "deferred",
            "not_applicable",
        )
    )


def _indicator_requires_special_rule(value: object) -> bool:
    raw = _text(value)
    if not raw:
        return False
    try:
        # CMS uses 0 for no adjustment and 9 when the concept does not apply.
        return Decimal(raw) not in {Decimal("0"), Decimal("9")}
    except InvalidOperation:
        return True


def _trace_assignment(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "assignment_id": _text(record.get("assignment_id")),
        "parameter_id": _text(record.get("assignment_id")),
        "rule_id": _text(record.get("rule_id")),
        "parameter_name": "code_assignment",
        "assignment_type": _text(record.get("assignment_type")),
        "code": _text(record.get("code")),
        "modifier": _text(record.get("modifier")),
        "status_code": _text(record.get("status_code")),
        "effective_start": _text(record.get("effective_start")),
        "effective_end": _text(record.get("effective_end")),
        "source_artifact_id": _text(record.get("source_artifact_id")),
        "source_locator": _text(record.get("source_locator")),
        "value_status": _text(record.get("value_status")),
    }


def _trace_parameter(record: Mapping[str, Any], numeric_value: Decimal) -> dict[str, Any]:
    return {
        "parameter_id": _text(record.get("parameter_id")),
        "rule_id": _text(record.get("rule_id")),
        "parameter_name": _text(record.get("parameter_name")),
        "key_type": _text(record.get("key_type")),
        "key_value": _text(record.get("key_value")),
        "numeric_value": numeric_value,
        "unit": _text(record.get("unit")),
        "effective_start": _text(record.get("effective_start")),
        "effective_end": _text(record.get("effective_end")),
        "source_artifact_id": _text(record.get("source_artifact_id")),
        "source_locator": _text(record.get("source_locator")),
        "value_status": _text(record.get("value_status")),
    }


def _trace_rule(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": _text(record.get("rule_id")),
        "rule_name": _text(record.get("rule_name")),
        "rule_version": _text(record.get("rule_version")),
        "effective_start": _text(record.get("effective_start")),
        "effective_end": _text(record.get("effective_end")),
        "execution_status": _text(record.get("execution_status")),
        "source_artifact_id": _text(record.get("source_artifact_id")),
        "source_locator": _text(record.get("source_locator")),
    }


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _source_ids(records: Iterable[Mapping[str, Any]]) -> list[str]:
    return _dedupe(_text(record.get("source_artifact_id")) for record in records)


def _unsupported(
    *,
    service_date: date,
    input_context: dict[str, Any],
    selected_rules: list[dict[str, Any]] | None = None,
    selected_parameters: list[dict[str, Any]] | None = None,
    source_artifact_ids: list[str] | None = None,
    missing_rule: str | None = None,
    missing_parameters: Iterable[str] = (),
    unsupported_adjustments: Iterable[str] = (),
    warnings: Iterable[str] = (),
) -> PaymentTrace:
    return PaymentTrace(
        payment_system=_PFS,
        service_date=service_date,
        calculation_status=CalculationStatus.UNSUPPORTED,
        input_context=input_context,
        selected_rule_versions=selected_rules or [],
        selected_parameters=selected_parameters or [],
        unsupported_adjustments=_dedupe(unsupported_adjustments),
        warnings=list(warnings),
        source_artifact_ids=source_artifact_ids or [],
        missing_rule=missing_rule,
        missing_parameters=_dedupe(missing_parameters),
    )


def _resolve_rule_versions(
    store: RulebookStore,
    service_date: date,
    rule_ids: Iterable[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_rules: list[dict[str, Any]] = []
    for rule_id in _dedupe(rule_ids):
        candidates = _records_matching(
            store.payment_rules,
            {"rule_id": rule_id},
            label=f"payment_rule:{rule_id}",
        )
        rule = _select_effective_record(
            candidates,
            service_date,
            label=f"payment_rule:{rule_id}",
        )
        execution_status = _text(rule.get("execution_status")).lower()
        if execution_status and execution_status != "executable":
            raise _ResolutionError(f"payment_rule:{rule_id}:not_executable")
        raw_rules.append(rule)
    return [_trace_rule(rule) for rule in raw_rules], raw_rules


def _calculate_pfs(
    code: str,
    date_of_service: date | str,
    locality: str,
    setting: str,
    store: RulebookStore,
    modifier: str | None = "",
) -> PaymentTrace:
    """Calculate the traceable core PFS base payment or return ``unsupported``.

    The calculation covers only an active status-A code without an indicated
    specialized payment path. Effective-dated code, GPCI, and conversion-factor
    records must each resolve to exactly one authoritative value.
    """

    target_date = _as_date(date_of_service)
    normalized_code = _key(code)
    normalized_modifier = _key(modifier)
    normalized_locality = _key(locality)
    normalized_setting = _text(setting).lower().replace("-", "").replace("_", "")
    if normalized_setting == "nonfacility":
        normalized_setting = "nonfacility"
    elif normalized_setting == "facility":
        normalized_setting = "facility"

    context = {
        "code": normalized_code,
        "modifier": normalized_modifier,
        "date_of_service": target_date,
        "locality": normalized_locality,
        "setting": normalized_setting,
    }
    if normalized_setting not in {"facility", "nonfacility"}:
        return _unsupported(
            service_date=target_date,
            input_context=context,
            missing_parameters=["setting:expected_facility_or_nonfacility"],
        )
    if not normalized_code:
        return _unsupported(
            service_date=target_date,
            input_context=context,
            missing_parameters=["code"],
        )
    if not normalized_locality:
        return _unsupported(
            service_date=target_date,
            input_context=context,
            missing_parameters=["locality"],
        )

    try:
        assignment_candidates = _records_matching(
            store.code_assignments,
            {
                "payment_system": _PFS,
                "assignment_type": "pfs_rvu",
                "code": normalized_code,
                "modifier": normalized_modifier,
            },
            label="code_assignment",
        )
        assignment = _select_effective_record(
            assignment_candidates,
            target_date,
            label="code_assignment",
        )
    except _ResolutionError as error:
        return _unsupported(
            service_date=target_date,
            input_context=context,
            missing_parameters=[error.reason],
        )

    assignment_trace = _trace_assignment(assignment)
    selected_parameters = [assignment_trace]
    selected_sources = _source_ids([assignment])
    assignment_rule_id = _text(assignment.get("rule_id"))

    if _value_is_unresolved(assignment.get("value_status")):
        return _unsupported(
            service_date=target_date,
            input_context=context,
            selected_parameters=selected_parameters,
            source_artifact_ids=selected_sources,
            missing_parameters=["code_assignment:value_status"],
        )

    status_code = _key(assignment.get("status_code"))
    if status_code == "J":
        return _unsupported(
            service_date=target_date,
            input_context=context,
            selected_parameters=selected_parameters,
            source_artifact_ids=selected_sources,
            missing_rule="pfs.anesthesia",
            unsupported_adjustments=["pfs.anesthesia"],
        )
    if status_code != "A":
        return _unsupported(
            service_date=target_date,
            input_context=context,
            selected_parameters=selected_parameters,
            source_artifact_ids=selected_sources,
            missing_rule="pfs.code_status",
            unsupported_adjustments=[f"status_code:{status_code or 'missing'}"],
        )

    special_rules = [
        rule_id
        for indicator, rule_id in _SPECIAL_INDICATORS.items()
        if _indicator_requires_special_rule(assignment.get(indicator))
    ]
    if special_rules:
        return _unsupported(
            service_date=target_date,
            input_context=context,
            selected_parameters=selected_parameters,
            source_artifact_ids=selected_sources,
            missing_rule=special_rules[0],
            unsupported_adjustments=special_rules,
        )

    pe_column = f"{normalized_setting}_pe_rvu"
    na_column = f"{normalized_setting}_na_indicator"
    if _indicator_requires_special_rule(assignment.get(na_column)):
        return _unsupported(
            service_date=target_date,
            input_context=context,
            selected_parameters=selected_parameters,
            source_artifact_ids=selected_sources,
            missing_rule="pfs.practice_expense_rvu",
            unsupported_adjustments=[f"{normalized_setting}_practice_expense_not_applicable"],
        )

    try:
        work_rvu = _as_decimal(assignment.get("work_rvu"), label="work_rvu")
        pe_rvu = _as_decimal(assignment.get(pe_column), label=pe_column)
        malpractice_rvu = _as_decimal(
            assignment.get("malpractice_rvu"), label="malpractice_rvu"
        )
    except _ResolutionError as error:
        return _unsupported(
            service_date=target_date,
            input_context=context,
            selected_parameters=selected_parameters,
            source_artifact_ids=selected_sources,
            missing_parameters=[error.reason],
        )

    parameter_specs = (
        ("work_gpci", normalized_locality),
        ("pe_gpci", normalized_locality),
        ("mp_gpci", normalized_locality),
        ("conversion_factor", None),
    )
    parameter_rows: dict[str, dict[str, Any]] = {}
    parameter_values: dict[str, Decimal] = {}
    try:
        for parameter_name, key_value in parameter_specs:
            conditions: dict[str, object] = {"parameter_name": parameter_name}
            if key_value is not None:
                conditions["key_value"] = key_value
            candidates = _records_matching(
                store.rule_parameters,
                conditions,
                label=f"parameter:{parameter_name}",
            )
            row = _select_effective_record(
                candidates,
                target_date,
                label=f"parameter:{parameter_name}",
            )
            if _value_is_unresolved(row.get("value_status")):
                raise _ResolutionError(f"parameter:{parameter_name}:value_status")
            value = _as_decimal(row.get("numeric_value"), label=parameter_name)
            parameter_rows[parameter_name] = row
            parameter_values[parameter_name] = value
    except _ResolutionError as error:
        return _unsupported(
            service_date=target_date,
            input_context=context,
            selected_parameters=selected_parameters,
            source_artifact_ids=selected_sources,
            missing_parameters=[error.reason],
        )

    for name, _ in parameter_specs:
        selected_parameters.append(_trace_parameter(parameter_rows[name], parameter_values[name]))

    referenced_rule_ids = [assignment_rule_id]
    if assignment_rule_id.endswith(".base_payment"):
        version_prefix = assignment_rule_id.removesuffix(".base_payment")
        referenced_rule_ids.extend(
            f"{version_prefix}.{suffix}"
            for suffix in (
                "work_rvu",
                "practice_expense_rvu",
                "malpractice_rvu",
            )
        )
    referenced_rule_ids.extend(_text(row.get("rule_id")) for row in parameter_rows.values())
    if any(not rule_id for rule_id in referenced_rule_ids):
        return _unsupported(
            service_date=target_date,
            input_context=context,
            selected_parameters=selected_parameters,
            source_artifact_ids=_source_ids([assignment, *parameter_rows.values()]),
            missing_parameters=["rule_id"],
        )

    try:
        selected_rules, raw_rules = _resolve_rule_versions(
            store,
            target_date,
            referenced_rule_ids,
        )
    except _ResolutionError as error:
        return _unsupported(
            service_date=target_date,
            input_context=context,
            selected_parameters=selected_parameters,
            source_artifact_ids=_source_ids([assignment, *parameter_rows.values()]),
            missing_rule=error.reason,
        )

    all_sources = _source_ids([assignment, *parameter_rows.values(), *raw_rules])
    if not all_sources:
        return _unsupported(
            service_date=target_date,
            input_context=context,
            selected_rules=selected_rules,
            selected_parameters=selected_parameters,
            missing_parameters=["source_artifact_id"],
        )

    work_component = work_rvu * parameter_values["work_gpci"]
    pe_component = pe_rvu * parameter_values["pe_gpci"]
    malpractice_component = malpractice_rvu * parameter_values["mp_gpci"]
    geographically_adjusted_rvu = work_component + pe_component + malpractice_component
    unrounded_amount = geographically_adjusted_rvu * parameter_values["conversion_factor"]
    amount = unrounded_amount.quantize(_CENT, rounding=ROUND_HALF_UP)

    return PaymentTrace(
        payment_system=_PFS,
        service_date=target_date,
        calculation_status=CalculationStatus.CALCULATED,
        input_context=context,
        selected_rule_versions=selected_rules,
        selected_parameters=selected_parameters,
        components={
            "setting": normalized_setting,
            "work_rvu": work_rvu,
            "practice_expense_rvu": pe_rvu,
            "malpractice_rvu": malpractice_rvu,
            "work_gpci": parameter_values["work_gpci"],
            "practice_expense_gpci": parameter_values["pe_gpci"],
            "malpractice_gpci": parameter_values["mp_gpci"],
            "work_component": work_component,
            "practice_expense_component": pe_component,
            "malpractice_component": malpractice_component,
            "geographically_adjusted_rvu": geographically_adjusted_rvu,
            "conversion_factor": parameter_values["conversion_factor"],
            "unrounded_amount": unrounded_amount,
            "rounding": "nearest_cent_half_up",
        },
        calculated_amount=amount,
        amount_label="PFS base payment before claim-level adjustments",
        unsupported_adjustments=[
            "coverage determination and claim edits",
            "beneficiary cost sharing and nonparticipating-provider rules",
            "sequestration and other post-fee-schedule adjustments",
        ],
        warnings=[
            "The calculated amount is the core PFS base amount, not final claim adjudication."
        ],
        source_artifact_ids=all_sources,
    )


def calculate_pfs(
    code: str,
    date_of_service: date | str,
    locality: str,
    setting: str,
    store: RulebookStore,
    modifier: str | None = "",
) -> PaymentTrace:
    """Calculate the PFS base trace and attach all linked source authorities."""

    trace = _calculate_pfs(
        code,
        date_of_service,
        locality,
        setting,
        store,
        modifier,
    )
    return enrich_trace_sources(trace, store)
