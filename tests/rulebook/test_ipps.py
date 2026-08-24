from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from reconciliation_healthcare.rulebook.ipps import calculate_ipps_base_payment
from reconciliation_healthcare.rulebook.models import CalculationStatus
from reconciliation_healthcare.rulebook.store import RulebookStore
from reconciliation_healthcare.rulebook.trace import validate_trace


def _rules() -> pd.DataFrame:
    records = []
    for fiscal_year, start, end in (
        ("fy2024", "2023-10-01", "2024-09-30"),
        ("fy2025", "2024-10-01", "2025-09-30"),
    ):
        artifacts = {
            "base_operating_payment": f"cms_ipps_{fiscal_year}_table1",
            "ms_drg_weight": f"cms_ipps_{fiscal_year}_table5",
            "standardized_amount": f"cms_ipps_{fiscal_year}_table1",
            "wage_index": f"cms_ipps_{fiscal_year}_wage_tables",
        }
        for suffix, artifact in artifacts.items():
            records.append(
                {
                    "rule_id": f"ipps.{fiscal_year}.{suffix}",
                    "rule_version": fiscal_year.upper(),
                    "effective_start": start,
                    "effective_end": end,
                    "execution_status": "executable",
                    "source_artifact_id": artifact,
                    "source_locator": "fixture locator",
                }
            )
    return pd.DataFrame.from_records(records)


def _amount_rows(
    fiscal_year: str,
    start: str,
    end: str,
    *,
    share: str,
    labor: str,
    nonlabor: str,
) -> list[dict[str, object]]:
    key = f"quality_submitted_ehr_user|labor_share={share}"
    artifact = f"cms_ipps_{fiscal_year}_table1"
    return [
        {
            "parameter_id": f"{fiscal_year}.labor.{share}",
            "rule_id": f"ipps.{fiscal_year}.standardized_amount",
            "parameter_name": "standardized_labor_amount",
            "effective_start": start,
            "effective_end": end,
            "key_type": "category",
            "key_value": key,
            "numeric_value": labor,
            "string_value": None,
            "provider_id": None,
            "geography": None,
            "unit": "USD",
            "value_status": "official",
            "source_artifact_id": artifact,
        },
        {
            "parameter_id": f"{fiscal_year}.nonlabor.{share}",
            "rule_id": f"ipps.{fiscal_year}.standardized_amount",
            "parameter_name": "standardized_nonlabor_amount",
            "effective_start": start,
            "effective_end": end,
            "key_type": "category",
            "key_value": key,
            "numeric_value": nonlabor,
            "string_value": None,
            "provider_id": None,
            "geography": None,
            "unit": "USD",
            "value_status": "official",
            "source_artifact_id": artifact,
        },
    ]


def _parameters() -> pd.DataFrame:
    records: list[dict[str, object]] = []
    records.extend(
        _amount_rows(
            "fy2024",
            "2023-10-01",
            "2024-09-30",
            share="67.6",
            labor="4392.49",
            nonlabor="2105.28",
        )
    )
    records.extend(
        _amount_rows(
            "fy2024",
            "2023-10-01",
            "2024-09-30",
            share="62.0",
            labor="4028.62",
            nonlabor="2469.15",
        )
    )
    records.extend(
        _amount_rows(
            "fy2025",
            "2024-10-01",
            "2025-09-30",
            share="67.6",
            labor="4478.09",
            nonlabor="2146.30",
        )
    )
    records.extend(
        _amount_rows(
            "fy2025",
            "2024-10-01",
            "2025-09-30",
            share="62",
            labor="4107.12",
            nonlabor="2517.27",
        )
    )
    wage_rows = (
        ("fy2024", "2023-10-01", "2024-09-30", "050008", "1.8744", "CA"),
        ("fy2025", "2024-10-01", "2025-09-30", "050008", "1.7807", "CA"),
        ("fy2024", "2023-10-01", "2024-09-30", "010001", "0.8573", "AL"),
        ("fy2025", "2024-10-01", "2025-09-30", "010001", "0.9009", "AL"),
        ("fy2025", "2024-10-01", "2025-09-30", "010006", "0.8076", "AL"),
        ("fy2025", "2024-10-01", "2025-09-30", "010011", "0.7742", "AL"),
        ("fy2024", "2023-10-01", "2024-09-30", "010999", "1.0000", "AL"),
        # Normalized CMS wage geography is the payment CBSA, not the state.
        ("fy2025", "2024-10-01", "2025-09-30", "020001", "1.0365", "11260"),
    )
    for fiscal_year, start, end, ccn, value, state in wage_rows:
        records.append(
            {
                "parameter_id": f"{fiscal_year}.wage.{ccn}",
                "rule_id": f"ipps.{fiscal_year}.wage_index",
                "parameter_name": "wage_index",
                "effective_start": start,
                "effective_end": end,
                "key_type": "provider_id",
                "key_value": ccn,
                "numeric_value": value,
                "string_value": "with_cap",
                "provider_id": ccn,
                "geography": state,
                "unit": "factor",
                "value_status": "official",
                "source_artifact_id": f"cms_ipps_{fiscal_year}_wage_tables",
            }
        )
    records.extend(
        [
            {
                "parameter_id": "fy2025.outmigration.010006",
                "rule_id": "ipps.fy2025.wage_index",
                "parameter_name": "out_migration_adjustment",
                "effective_start": "2024-10-01",
                "effective_end": "2025-09-30",
                "key_type": "provider_id",
                "key_value": "010006",
                "numeric_value": "0.0089",
                "string_value": None,
                "provider_id": "010006",
                "geography": "AL",
                "unit": "factor",
                "value_status": "official",
                "source_artifact_id": "cms_ipps_fy2025_wage_tables",
            },
            {
                "parameter_id": "fy2025.transition.010011",
                "rule_id": "ipps.fy2025.wage_index",
                "parameter_name": "transitional_exception_wage_factor",
                "effective_start": "2024-10-01",
                "effective_end": "2025-09-30",
                "key_type": "provider_id",
                "key_value": "010011",
                "numeric_value": "0.7764",
                "string_value": "transitional_exception",
                "provider_id": "010011",
                "geography": "AL",
                "unit": "factor",
                "value_status": "official",
                "source_artifact_id": "cms_ipps_fy2025_wage_tables",
            },
        ]
    )
    return pd.DataFrame.from_records(records)


def _assignments() -> pd.DataFrame:
    return pd.DataFrame.from_records(
        [
            {
                "assignment_id": "fy2024.drg039",
                "rule_id": "ipps.fy2024.ms_drg_weight",
                "assignment_type": "ms_drg_weight",
                "code": "039",
                "relative_weight": "1.1410",
                "effective_start": "2023-10-01",
                "effective_end": "2024-09-30",
                "source_artifact_id": "cms_ipps_fy2024_table5",
                "source_locator": "Table 5, MS-DRG 039",
            },
            {
                "assignment_id": "fy2025.drg039",
                "rule_id": "ipps.fy2025.ms_drg_weight",
                "assignment_type": "ms_drg_weight",
                "code": "039",
                "relative_weight": "1.1382",
                "effective_start": "2024-10-01",
                "effective_end": "2025-09-30",
                "source_artifact_id": "cms_ipps_fy2025_table5",
                "source_locator": "Corrected Table 5, MS-DRG 039",
            },
        ]
    )


@pytest.fixture
def store() -> RulebookStore:
    return RulebookStore(
        payment_rules=_rules(),
        rule_parameters=_parameters(),
        code_assignments=_assignments(),
        source_artifacts=pd.DataFrame(),
    )


def _calculate(store: RulebookStore, **overrides: object):
    inputs: dict[str, object] = {
        "ms_drg": "039",
        "discharge_date": "2024-09-30",
        "provider_ccn": "050008",
        "quality_submitted": True,
        "meaningful_ehr_user": True,
    }
    inputs.update(overrides)
    return calculate_ipps_base_payment(store, **inputs)  # type: ignore[arg-type]


def test_ipps_fiscal_year_boundary_and_cms_reference_amounts(store: RulebookStore) -> None:
    fy2024 = _calculate(store, discharge_date="2024-09-30")
    fy2025 = _calculate(store, discharge_date="2024-10-01")

    assert fy2024.calculation_status is CalculationStatus.CALCULATED
    assert fy2024.calculated_amount == Decimal("11796.30")
    assert fy2024.components["fiscal_year"] == "FY2024"
    assert fy2024.components["base_operating_payment_9dp"] == Decimal("11796.300675096")

    assert fy2025.calculation_status is CalculationStatus.CALCULATED
    assert fy2025.calculated_amount == Decimal("11519.08")
    assert fy2025.components["fiscal_year"] == "FY2025"
    assert fy2025.components["base_operating_payment_9dp"] == Decimal("11519.078961067")


def test_low_wage_index_selects_table_1b_amounts(store: RulebookStore) -> None:
    trace = _calculate(store, provider_ccn="010001")

    assert trace.calculated_amount == Decimal("6758.01")
    assert trace.components["labor_share_percent"] == Decimal("62")
    assert trace.components["labor_standardized_amount"] == Decimal("4028.62")
    assert trace.components["nonlabor_standardized_amount"] == Decimal("2469.15")


def test_wage_index_equal_to_one_selects_table_1b_amounts(store: RulebookStore) -> None:
    trace = _calculate(store, provider_ccn="010999")

    assert trace.calculated_amount == Decimal("7413.96")
    assert trace.components["labor_share_percent"] == Decimal("62")


def test_trace_identifies_rules_parameters_sources_and_partial_amount(store: RulebookStore) -> None:
    trace = _calculate(store, ms_drg=39)

    validate_trace(trace)
    assert {rule["rule_id"] for rule in trace.selected_rule_versions} == {
        "ipps.fy2024.base_operating_payment",
        "ipps.fy2024.ms_drg_weight",
        "ipps.fy2024.standardized_amount",
        "ipps.fy2024.wage_index",
    }
    assert {parameter["parameter_name"] for parameter in trace.selected_parameters} == {
        "ms_drg_weight",
        "wage_index",
        "standardized_labor_amount",
        "standardized_nonlabor_amount",
    }
    assert set(trace.source_artifact_ids) == {
        "cms_ipps_fy2024_table1",
        "cms_ipps_fy2024_table5",
        "cms_ipps_fy2024_wage_tables",
    }
    assert trace.amount_label == "base_operating_payment_before_adjustments"
    assert "transfer_policy" in trace.unsupported_adjustments
    assert trace.input_context["ms_drg"] == "039"


@pytest.mark.parametrize(
    ("quality_submitted", "meaningful_ehr_user", "missing"),
    [
        (None, True, "quality_submitted"),
        (True, None, "meaningful_ehr_user"),
        (1, True, "quality_submitted"),
    ],
)
def test_quality_and_ehr_inputs_must_be_explicit_booleans(
    store: RulebookStore,
    quality_submitted: object,
    meaningful_ehr_user: object,
    missing: str,
) -> None:
    trace = _calculate(
        store,
        quality_submitted=quality_submitted,
        meaningful_ehr_user=meaningful_ehr_user,
    )

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.calculated_amount is None
    assert missing in trace.missing_parameters
    validate_trace(trace)


def test_unavailable_quality_ehr_category_does_not_fall_back_to_full_update(
    store: RulebookStore,
) -> None:
    trace = _calculate(store, quality_submitted=False)

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.missing_parameters == [
        "standardized_labor_amount",
        "standardized_nonlabor_amount",
    ]


def test_missing_or_ambiguous_parameter_fails_closed(store: RulebookStore) -> None:
    missing = _calculate(store, provider_ccn="999999")
    assert missing.calculation_status is CalculationStatus.UNSUPPORTED
    assert missing.missing_parameters == ["wage_index"]

    duplicated = pd.concat(
        [store.rule_parameters, store.rule_parameters.iloc[[8]]], ignore_index=True
    )
    ambiguous_store = RulebookStore(
        payment_rules=store.payment_rules,
        rule_parameters=duplicated,
        code_assignments=store.code_assignments,
        source_artifacts=store.source_artifacts,
    )
    ambiguous = _calculate(ambiguous_store)
    assert ambiguous.calculation_status is CalculationStatus.UNSUPPORTED
    assert ambiguous.missing_parameters == ["wage_index"]


def test_out_migration_adjustment_fails_closed(store: RulebookStore) -> None:
    trace = _calculate(
        store,
        discharge_date="2024-10-01",
        provider_ccn="010006",
    )

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.calculated_amount is None
    assert trace.components == {}
    assert trace.unsupported_adjustments == ["out_migration_adjustment"]
    assert any(
        parameter["parameter_name"] == "out_migration_adjustment"
        for parameter in trace.selected_parameters
    )


def test_transitional_exception_is_not_substituted_for_wage_index(
    store: RulebookStore,
) -> None:
    trace = _calculate(
        store,
        discharge_date="2024-10-01",
        provider_ccn="010011",
    )

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.unsupported_adjustments == ["transitional_exception_wage_factor"]
    actual_wage = next(
        parameter
        for parameter in trace.selected_parameters
        if parameter["parameter_name"] == "wage_index"
    )
    assert actual_wage["numeric_value"] == Decimal("0.7742")


@pytest.mark.parametrize(
    ("provider_state", "missing"),
    [
        ("AK", "operating_cola"),
        ("HI", "operating_cola"),
        ("PR", "puerto_rico_standardized_amount"),
    ],
)
def test_special_geographies_fail_closed(
    store: RulebookStore, provider_state: str, missing: str
) -> None:
    trace = _calculate(store, provider_state=provider_state)

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.missing_parameters == [missing]
    assert trace.unsupported_adjustments == [missing]


def test_state_on_wage_parameter_also_triggers_special_geography(store: RulebookStore) -> None:
    trace = _calculate(
        store,
        discharge_date=date(2024, 10, 1),
        provider_ccn="020001",
    )

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.missing_parameters == ["operating_cola"]


def test_ccn_special_geography_cannot_be_overridden_by_conflicting_state(
    store: RulebookStore,
) -> None:
    trace = _calculate(
        store,
        discharge_date=date(2024, 10, 1),
        provider_ccn="020001",
        provider_state="CA",
    )

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.missing_parameters == ["operating_cola"]


def test_date_outside_implemented_fiscal_years_fails_closed(store: RulebookStore) -> None:
    trace = _calculate(store, discharge_date="2023-09-30")

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.missing_rule == "ipps.base_operating_payment"
    assert trace.calculated_amount is None
