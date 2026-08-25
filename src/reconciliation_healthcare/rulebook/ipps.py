"""Auditable Stage 2A IPPS base operating-payment calculation."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

import pandas as pd

from reconciliation_healthcare.rulebook.models import CalculationStatus, PaymentTrace
from reconciliation_healthcare.rulebook.provenance import enrich_trace_sources
from reconciliation_healthcare.rulebook.store import RulebookStore
from reconciliation_healthcare.rulebook.temporal import as_date


_NINE_PLACES = Decimal("0.000000001")
_CENTS = Decimal("0.01")
_ONE = Decimal("1")

_OMITTED_FINAL_PAYMENT_ADJUSTMENTS = [
    "ime",
    "dsh",
    "uncompensated_care",
    "ntap",
    "outlier",
    "hrrp",
    "vbp",
    "hac",
    "transfer_policy",
    "capital_payment",
    "other_provider_specific_adjustments",
]


def _normal_date(value: date | str) -> date:
    parsed = as_date(value)
    if isinstance(parsed, datetime):
        return parsed.date()
    # pandas.Timestamp is date-like but its comparison semantics differ from date.
    if hasattr(parsed, "date") and type(parsed) is not date:
        return parsed.date()
    return parsed


def _fiscal_year(discharge_date: date) -> tuple[str, str] | None:
    if date(2023, 10, 1) <= discharge_date <= date(2024, 9, 30):
        return "fy2024", "FY2024"
    if date(2024, 10, 1) <= discharge_date <= date(2025, 9, 30):
        return "fy2025", "FY2025"
    return None


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    try:
        if bool(pd.isna(value)):
            return False
    except (TypeError, ValueError):
        pass
    return not isinstance(value, str) or bool(value.strip())


def _as_decimal(value: Any, *, label: str) -> Decimal:
    if not _has_value(value):
        raise ValueError(f"{label} is blank")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{label} is not numeric: {value!r}") from error
    if not result.is_finite():
        raise ValueError(f"{label} is not finite: {value!r}")
    return result


def _normal_ccn(value: Any) -> str:
    if not _has_value(value):
        return ""
    normalized = str(value).strip().upper()
    return normalized.zfill(6) if normalized.isdigit() else normalized


def _normal_drg(value: Any) -> str:
    if not _has_value(value):
        return ""
    normalized = str(value).strip()
    if normalized.endswith(".0") and normalized[:-2].isdigit():
        normalized = normalized[:-2]
    return normalized.zfill(3) if normalized.isdigit() else normalized.upper()


def _effective_records(frame: pd.DataFrame, target: date) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    records: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        try:
            start = _normal_date(record["effective_start"])
            end = _normal_date(record["effective_end"])
        except (KeyError, TypeError, ValueError):
            continue
        if start <= target <= end:
            records.append(record)
    return records


def _provider_parameter_records(
    store: RulebookStore,
    *,
    parameter_name: str,
    provider_ccn: str,
    discharge_date: date,
) -> list[dict[str, Any]]:
    frame = store.rule_parameters
    if frame.empty or "parameter_name" not in frame:
        return []
    matches = frame[frame["parameter_name"] == parameter_name]
    records = _effective_records(matches, discharge_date)
    result: list[dict[str, Any]] = []
    for record in records:
        candidates = [
            record.get(column)
            for column in ("provider_id", "key_value")
            if _has_value(record.get(column))
        ]
        if any(_normal_ccn(candidate) == provider_ccn for candidate in candidates):
            result.append(record)
    return result


def _category_key(record: Mapping[str, Any]) -> str:
    for column in ("key_value", "string_value"):
        value = record.get(column)
        if _has_value(value):
            return str(value).strip()
    return ""


def _matches_standardized_category(
    record: Mapping[str, Any],
    *,
    quality_submitted: bool,
    meaningful_ehr_user: bool,
    labor_share: Decimal,
) -> bool:
    quality = "quality_submitted" if quality_submitted else "quality_not_submitted"
    ehr = "ehr_user" if meaningful_ehr_user else "not_ehr_user"
    expected_prefix = f"{quality}_{ehr}"
    key = _category_key(record)
    prefix, separator, suffix = key.partition("|")
    if prefix != expected_prefix or not separator or not suffix.startswith("labor_share="):
        return False
    try:
        return Decimal(suffix.removeprefix("labor_share=").strip()) == labor_share
    except InvalidOperation:
        return False


def _standardized_amount_records(
    store: RulebookStore,
    *,
    parameter_name: str,
    discharge_date: date,
    quality_submitted: bool,
    meaningful_ehr_user: bool,
    labor_share: Decimal,
) -> list[dict[str, Any]]:
    frame = store.rule_parameters
    if frame.empty or "parameter_name" not in frame:
        return []
    matches = frame[frame["parameter_name"] == parameter_name]
    return [
        record
        for record in _effective_records(matches, discharge_date)
        if _matches_standardized_category(
            record,
            quality_submitted=quality_submitted,
            meaningful_ehr_user=meaningful_ehr_user,
            labor_share=labor_share,
        )
    ]


def _drg_weight_records(
    store: RulebookStore,
    *,
    ms_drg: str,
    discharge_date: date,
) -> list[dict[str, Any]]:
    frame = store.code_assignments
    if frame.empty or "assignment_type" not in frame or "code" not in frame:
        return []
    matches = frame[
        (frame["assignment_type"] == "ms_drg_weight")
        & (frame["code"].map(_normal_drg) == ms_drg)
    ]
    return _effective_records(matches, discharge_date)


def _numeric_record_value(record: Mapping[str, Any], *, label: str) -> Decimal:
    for column in ("numeric_value", "relative_weight", "value"):
        value = record.get(column)
        if _has_value(value):
            return _as_decimal(value, label=label)
    raise ValueError(f"{label} has no numeric value column")


def _trace_rule(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "rule_id",
            "rule_version",
            "effective_start",
            "effective_end",
            "execution_status",
            "source_artifact_id",
            "source_locator",
        )
        if _has_value(record.get(key))
    }


def _trace_parameter(
    record: Mapping[str, Any],
    *,
    parameter_name: str,
    numeric_value: Decimal | None = None,
) -> dict[str, Any]:
    result = {
        key: record.get(key)
        for key in (
            "parameter_id",
            "assignment_id",
            "rule_id",
            "key_type",
            "key_value",
            "provider_id",
            "code",
            "effective_start",
            "effective_end",
            "unit",
            "value_status",
            "source_artifact_id",
            "source_locator",
        )
        if _has_value(record.get(key))
    }
    result["parameter_name"] = parameter_name
    if numeric_value is not None:
        result["numeric_value"] = numeric_value
    return result


def _artifact_ids(*groups: Iterable[Mapping[str, Any]]) -> list[str]:
    result: list[str] = []
    for group in groups:
        for record in group:
            value = record.get("source_artifact_id")
            if _has_value(value) and str(value) not in result:
                result.append(str(value))
    return result


def _selected_rules(
    store: RulebookStore, *, fiscal_year: str, discharge_date: date
) -> tuple[list[dict[str, Any]], str | None]:
    ids = [
        f"ipps.{fiscal_year}.base_operating_payment",
        f"ipps.{fiscal_year}.ms_drg_weight",
        f"ipps.{fiscal_year}.standardized_amount",
        f"ipps.{fiscal_year}.wage_index",
    ]
    if store.payment_rules.empty or "rule_id" not in store.payment_rules:
        return [], ids[0]
    selected: list[dict[str, Any]] = []
    for rule_id in ids:
        candidates = store.payment_rules[store.payment_rules["rule_id"] == rule_id]
        records = _effective_records(candidates, discharge_date)
        if len(records) != 1:
            return selected, rule_id
        selected.append(records[0])
    return selected, None


def _unsupported_trace(
    *,
    discharge_date: date,
    input_context: dict[str, Any],
    rules: Iterable[Mapping[str, Any]] = (),
    parameters: Iterable[Mapping[str, Any]] = (),
    missing_rule: str | None = None,
    missing_parameters: Iterable[str] = (),
    unsupported_adjustments: Iterable[str] = (),
    warnings: Iterable[str] = (),
) -> PaymentTrace:
    rule_records = list(rules)
    parameter_records = list(parameters)
    return PaymentTrace(
        payment_system="IPPS",
        service_date=discharge_date,
        calculation_status=CalculationStatus.UNSUPPORTED,
        input_context=input_context,
        selected_rule_versions=[_trace_rule(record) for record in rule_records],
        selected_parameters=list(parameter_records),
        unsupported_adjustments=list(unsupported_adjustments),
        warnings=list(warnings),
        source_artifact_ids=_artifact_ids(rule_records, parameter_records),
        missing_rule=missing_rule,
        missing_parameters=list(missing_parameters),
    )


def _state_code(
    provider_state: str | None,
    wage_record: Mapping[str, Any],
    provider_ccn: str,
) -> str:
    # The first two CCN digits encode CMS's state/territory number. Check
    # these authoritative provider identifiers before caller-supplied context.
    ccn_special_state = {"02": "AK", "12": "HI", "40": "PR"}.get(provider_ccn[:2])
    if ccn_special_state:
        return ccn_special_state
    value: Any = provider_state
    if not _has_value(value):
        for column in ("state", "state_code", "geography"):
            if _has_value(wage_record.get(column)):
                value = wage_record[column]
                break
    if not _has_value(value):
        return ""
    normalized = str(value).strip().upper()
    names = {"ALASKA": "AK", "HAWAII": "HI", "PUERTO RICO": "PR"}
    if normalized in names:
        return names[normalized]
    if len(normalized) == 2:
        return normalized
    # Accommodate geography labels such as "San Francisco, CA" without
    # attempting to infer a state from arbitrary free text.
    tail = normalized.rsplit(",", maxsplit=1)[-1].strip()
    return tail if len(tail) == 2 else normalized


def _calculate_ipps_base_payment(
    store: RulebookStore,
    *,
    ms_drg: str | int,
    discharge_date: date | str,
    provider_ccn: str | int,
    quality_submitted: bool | None,
    meaningful_ehr_user: bool | None,
    provider_state: str | None = None,
) -> PaymentTrace:
    """Calculate the wage-adjusted IPPS base operating payment.

    MS-DRG classification is deliberately out of scope: ``ms_drg`` is an
    input. The returned amount excludes transfer policy, capital, add-ons,
    quality programs, and other provider/claim adjustments.
    """

    target = _normal_date(discharge_date)
    normalized_drg = _normal_drg(ms_drg)
    normalized_ccn = _normal_ccn(provider_ccn)
    context = {
        "ms_drg": normalized_drg,
        "discharge_date": target,
        "provider_ccn": normalized_ccn,
        "quality_submitted": quality_submitted,
        "meaningful_ehr_user": meaningful_ehr_user,
        "provider_state": provider_state,
    }

    missing_inputs: list[str] = []
    if not normalized_drg:
        missing_inputs.append("ms_drg")
    if not normalized_ccn:
        missing_inputs.append("provider_ccn")
    if type(quality_submitted) is not bool:
        missing_inputs.append("quality_submitted")
    if type(meaningful_ehr_user) is not bool:
        missing_inputs.append("meaningful_ehr_user")
    if missing_inputs:
        return _unsupported_trace(
            discharge_date=target,
            input_context=context,
            missing_parameters=missing_inputs,
            warnings=["IPPS base payment requires explicit provider and quality/EHR inputs."],
        )

    fiscal_year = _fiscal_year(target)
    if fiscal_year is None:
        return _unsupported_trace(
            discharge_date=target,
            input_context=context,
            missing_rule="ipps.base_operating_payment",
            warnings=["No Stage 2A IPPS fiscal-year rule covers this discharge date."],
        )
    fiscal_year_id, fiscal_year_label = fiscal_year
    context["fiscal_year"] = fiscal_year_label

    rule_records, missing_rule = _selected_rules(
        store, fiscal_year=fiscal_year_id, discharge_date=target
    )
    if missing_rule is not None:
        return _unsupported_trace(
            discharge_date=target,
            input_context=context,
            rules=rule_records,
            missing_rule=missing_rule,
        )

    weight_records = _drg_weight_records(store, ms_drg=normalized_drg, discharge_date=target)
    wage_records = _provider_parameter_records(
        store,
        parameter_name="wage_index",
        provider_ccn=normalized_ccn,
        discharge_date=target,
    )
    missing_parameters: list[str] = []
    if len(weight_records) != 1:
        missing_parameters.append("ms_drg_weight")
    if len(wage_records) != 1:
        missing_parameters.append("wage_index")
    if missing_parameters:
        return _unsupported_trace(
            discharge_date=target,
            input_context=context,
            rules=rule_records,
            missing_parameters=missing_parameters,
            warnings=["A required lookup was missing or ambiguous."],
        )

    weight_record = weight_records[0]
    wage_record = wage_records[0]
    try:
        relative_weight = _numeric_record_value(weight_record, label="MS-DRG relative weight")
        wage_index = _numeric_record_value(wage_record, label="wage index")
    except ValueError as error:
        return _unsupported_trace(
            discharge_date=target,
            input_context=context,
            rules=rule_records,
            missing_parameters=["numeric_value"],
            warnings=[str(error)],
        )
    if relative_weight <= 0 or wage_index <= 0:
        invalid = "ms_drg_weight" if relative_weight <= 0 else "wage_index"
        return _unsupported_trace(
            discharge_date=target,
            input_context=context,
            rules=rule_records,
            missing_parameters=[f"{invalid}:expected_positive_value"],
            warnings=["IPPS base-payment factors must be finite positive numbers."],
        )
    preliminary_parameters = [
        _trace_parameter(
            weight_record,
            parameter_name="ms_drg_weight",
            numeric_value=relative_weight,
        ),
        _trace_parameter(wage_record, parameter_name="wage_index", numeric_value=wage_index),
    ]

    state = _state_code(provider_state, wage_record, normalized_ccn)
    if state in {"AK", "HI", "PR"}:
        special = "puerto_rico_standardized_amount" if state == "PR" else "operating_cola"
        return _unsupported_trace(
            discharge_date=target,
            input_context=context,
            rules=rule_records,
            parameters=preliminary_parameters,
            missing_parameters=[special],
            unsupported_adjustments=[special],
            warnings=[f"Stage 2A does not execute the {state} IPPS special-rate path."],
        )

    out_migration = _provider_parameter_records(
        store,
        parameter_name="out_migration_adjustment",
        provider_ccn=normalized_ccn,
        discharge_date=target,
    )
    transition = _provider_parameter_records(
        store,
        parameter_name="transitional_exception_wage_factor",
        provider_ccn=normalized_ccn,
        discharge_date=target,
    )
    if out_migration or transition:
        unsupported = []
        special_records: list[dict[str, Any]] = []
        if out_migration:
            unsupported.append("out_migration_adjustment")
            special_records.extend(
                _trace_parameter(record, parameter_name="out_migration_adjustment")
                for record in out_migration
            )
        if transition:
            unsupported.append("transitional_exception_wage_factor")
            special_records.extend(
                _trace_parameter(record, parameter_name="transitional_exception_wage_factor")
                for record in transition
            )
        return _unsupported_trace(
            discharge_date=target,
            input_context=context,
            rules=rule_records,
            parameters=[*preliminary_parameters, *special_records],
            unsupported_adjustments=unsupported,
            warnings=[
                "The published wage index is preserved, but this separate provider-specific "
                "payment adjustment is not executable in Stage 2A."
            ],
        )

    labor_share = Decimal("62") if wage_index <= _ONE else Decimal("67.6")
    labor_records = _standardized_amount_records(
        store,
        parameter_name="standardized_labor_amount",
        discharge_date=target,
        quality_submitted=quality_submitted,
        meaningful_ehr_user=meaningful_ehr_user,
        labor_share=labor_share,
    )
    nonlabor_records = _standardized_amount_records(
        store,
        parameter_name="standardized_nonlabor_amount",
        discharge_date=target,
        quality_submitted=quality_submitted,
        meaningful_ehr_user=meaningful_ehr_user,
        labor_share=labor_share,
    )
    missing_amounts: list[str] = []
    if len(labor_records) != 1:
        missing_amounts.append("standardized_labor_amount")
    if len(nonlabor_records) != 1:
        missing_amounts.append("standardized_nonlabor_amount")
    if missing_amounts:
        return _unsupported_trace(
            discharge_date=target,
            input_context=context,
            rules=rule_records,
            parameters=preliminary_parameters,
            missing_parameters=missing_amounts,
            warnings=["A standardized-amount category was missing or ambiguous."],
        )

    labor_record = labor_records[0]
    nonlabor_record = nonlabor_records[0]
    try:
        labor_amount = _numeric_record_value(labor_record, label="labor standardized amount")
        nonlabor_amount = _numeric_record_value(
            nonlabor_record, label="nonlabor standardized amount"
        )
    except ValueError as error:
        return _unsupported_trace(
            discharge_date=target,
            input_context=context,
            rules=rule_records,
            parameters=preliminary_parameters,
            missing_parameters=["numeric_value"],
            warnings=[str(error)],
        )

    labor_component = labor_amount * wage_index
    wage_adjusted_standardized_amount = labor_component + nonlabor_amount
    unrounded_payment = wage_adjusted_standardized_amount * relative_weight
    payment_nine_places = unrounded_payment.quantize(_NINE_PLACES, rounding=ROUND_HALF_UP)
    payment_cents = payment_nine_places.quantize(_CENTS, rounding=ROUND_HALF_UP)

    parameter_records = [
        *preliminary_parameters,
        _trace_parameter(
            labor_record,
            parameter_name="standardized_labor_amount",
            numeric_value=labor_amount,
        ),
        _trace_parameter(
            nonlabor_record,
            parameter_name="standardized_nonlabor_amount",
            numeric_value=nonlabor_amount,
        ),
    ]
    source_ids = _artifact_ids(
        rule_records,
        weight_records,
        wage_records,
        labor_records,
        nonlabor_records,
    )
    return PaymentTrace(
        payment_system="IPPS",
        service_date=target,
        calculation_status=CalculationStatus.CALCULATED,
        input_context=context,
        selected_rule_versions=[_trace_rule(record) for record in rule_records],
        selected_parameters=parameter_records,
        components={
            "fiscal_year": fiscal_year_label,
            "ms_drg_relative_weight": relative_weight,
            "wage_index": wage_index,
            "labor_share_percent": labor_share,
            "operating_cola": _ONE,
            "labor_standardized_amount": labor_amount,
            "nonlabor_standardized_amount": nonlabor_amount,
            "wage_adjusted_labor_component": labor_component,
            "wage_adjusted_standardized_amount": wage_adjusted_standardized_amount,
            "unrounded_base_operating_payment": unrounded_payment,
            "base_operating_payment_9dp": payment_nine_places,
        },
        calculated_amount=payment_cents,
        amount_label="base_operating_payment_before_adjustments",
        unsupported_adjustments=list(_OMITTED_FINAL_PAYMENT_ADJUSTMENTS),
        warnings=["Base IPPS operating payment is not a final claim payment."],
        source_artifact_ids=source_ids,
    )


def calculate_ipps_base_payment(
    store: RulebookStore,
    *,
    ms_drg: str | int,
    discharge_date: date | str,
    provider_ccn: str | int,
    quality_submitted: bool | None,
    meaningful_ehr_user: bool | None,
    provider_state: str | None = None,
) -> PaymentTrace:
    """Calculate the IPPS base trace and attach all linked source authorities."""

    trace = _calculate_ipps_base_payment(
        store,
        ms_drg=ms_drg,
        discharge_date=discharge_date,
        provider_ccn=provider_ccn,
        quality_submitted=quality_submitted,
        meaningful_ehr_user=meaningful_ehr_user,
        provider_state=provider_state,
    )
    return enrich_trace_sources(trace, store)


__all__ = ["calculate_ipps_base_payment"]
