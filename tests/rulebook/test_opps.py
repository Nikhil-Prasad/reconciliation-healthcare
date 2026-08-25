from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from reconciliation_healthcare.rulebook.models import CalculationStatus
from reconciliation_healthcare.rulebook.opps import lookup_opps
from reconciliation_healthcare.rulebook.store import RulebookStore
from reconciliation_healthcare.rulebook.trace import validate_trace


QUARTERS = {
    "q1": ("2024-01-01", "2024-03-31"),
    "q2": ("2024-04-01", "2024-06-30"),
    "q3": ("2024-07-01", "2024-09-30"),
    "q4": ("2024-10-01", "2024-12-31"),
}


def _assignment(
    code: str,
    quarter: str,
    status_indicator: str,
    apc: str | None,
    relative_weight: str | None,
    payment_rate: str | None,
) -> dict[str, object]:
    start, end = QUARTERS[quarter]
    artifact = f"cms_opps_2024_{quarter}_addendum_b"
    return {
        "assignment_id": f"opps-{quarter}-{code}",
        "rule_id": f"opps.2024_{quarter}.hcpcs_status_apc",
        "payment_system": "OPPS",
        "assignment_type": "opps_hcpcs",
        "code": code,
        "effective_start": start,
        "effective_end": end,
        "status_indicator": status_indicator,
        "apc": apc,
        "relative_weight": relative_weight,
        "payment_rate": payment_rate,
        "source_artifact_id": artifact,
        "source_locator": f"Addendum B::{code}",
        "value_status": "published_quarter_snapshot",
    }


@pytest.fixture
def opps_store() -> RulebookStore:
    assignments = [
        _assignment("G0402", "q1", "V", "5012", "1.4414", "125.95"),
        _assignment("C1734", "q1", "N", None, None, None),
        _assignment("C9600", "q1", "J1", "5193", "119.9539", "10481.81"),
        _assignment("C1761", "q2", "H", "2033", None, None),
        _assignment("C1761", "q3", "N", None, None, None),
        _assignment("C1831", "q3", "H", "2034", None, None),
        _assignment("C1831", "q4", "N", None, None, None),
        _assignment("G0012", "q3", "S", "5691", "0.5179", "45.26"),
        _assignment("G0012", "q4", "S", "5692", "0.7681", "67.12"),
    ]
    rules = []
    artifacts = []
    for quarter, (start, end) in QUARTERS.items():
        artifact = f"cms_opps_2024_{quarter}_addendum_b"
        rules.append(
            {
                "rule_id": f"opps.2024_{quarter}.hcpcs_status_apc",
                "payment_system": "OPPS",
                "rule_version": quarter,
                "effective_start": start,
                "effective_end": end,
                "execution_status": "lookup_only",
                "source_artifact_id": artifact,
            }
        )
        rules.append(
            {
                "rule_id": f"opps.2024_{quarter}.published_rate",
                "payment_system": "OPPS",
                "rule_version": quarter,
                "effective_start": start,
                "effective_end": end,
                "execution_status": "lookup_only",
                "source_artifact_id": artifact,
            }
        )
        artifacts.append({"source_artifact_id": artifact})
    rules.extend(
        {
            "rule_id": rule_id,
            "payment_system": "OPPS",
            "rule_version": "CY2024",
            "effective_start": "2024-01-01",
            "effective_end": "2024-12-31",
            "execution_status": "documented_only",
            "source_artifact_id": "cms_opps_2024_final_addenda",
        }
        for rule_id in ("opps.packaging", "opps.comprehensive_apc")
    )
    artifacts.append({"source_artifact_id": "cms_opps_2024_final_addenda"})
    return RulebookStore(
        payment_rules=pd.DataFrame(rules),
        rule_parameters=pd.DataFrame(),
        code_assignments=pd.DataFrame(assignments),
        source_artifacts=pd.DataFrame(artifacts),
    )


def test_stable_separately_paid_visit_returns_published_lookup(
    opps_store: RulebookStore,
) -> None:
    trace = lookup_opps("g0402", "2024-02-15", opps_store)

    assert trace.calculation_status is CalculationStatus.LOOKUP_ONLY
    assert trace.components == {
        "code": "G0402",
        "status_indicator": "V",
        "apc": "5012",
        "relative_weight": Decimal("1.4414"),
        "published_national_rate": Decimal("125.95"),
        "packaging_rule": "Separately payable OPPS clinic or emergency-department visit.",
        "claim_context_required": False,
        "value_status": "published_quarter_snapshot",
    }
    assert trace.calculated_amount == Decimal("125.95")
    assert trace.amount_label == (
        "published national unadjusted OPPS payment rate (not final claim payment)"
    )
    assert trace.source_artifact_ids == [
        "cms_opps_2024_q1_addendum_b",
        "cms_opps_2024_final_addenda",
    ]
    validate_trace(trace)


def test_packaged_service_exposes_no_separate_rate(opps_store: RulebookStore) -> None:
    trace = lookup_opps("C1734", date(2024, 3, 31), opps_store)

    assert trace.calculation_status is CalculationStatus.LOOKUP_ONLY
    assert trace.components["status_indicator"] == "N"
    assert trace.components["apc"] is None
    assert trace.components["published_national_rate"] is None
    assert trace.calculated_amount is None
    assert trace.components["claim_context_required"] is True
    assert "no separate APC payment" in trace.components["packaging_rule"]
    assert {rule["rule_id"] for rule in trace.selected_rule_versions} >= {
        "opps.packaging"
    }
    assert any("claim context" in warning.lower() for warning in trace.warnings)
    validate_trace(trace)


def test_j1_returns_apc_base_but_requires_full_claim(opps_store: RulebookStore) -> None:
    trace = lookup_opps("C9600", "2024-01-01", opps_store)

    assert trace.calculation_status is CalculationStatus.LOOKUP_ONLY
    assert trace.components["status_indicator"] == "J1"
    assert trace.components["apc"] == "5193"
    assert trace.calculated_amount == Decimal("10481.81")
    assert trace.components["claim_context_required"] is True
    assert "Comprehensive APC" in trace.components["packaging_rule"]
    assert {rule["rule_id"] for rule in trace.selected_rule_versions} >= {
        "opps.packaging",
        "opps.comprehensive_apc",
    }
    assert any("complete claim" in warning for warning in trace.warnings)
    assert "not final claim payment" in trace.amount_label
    validate_trace(trace)


def test_july_first_boundary_changes_device_to_packaged(opps_store: RulebookStore) -> None:
    june = lookup_opps("C1761", "2024-06-30", opps_store)
    july = lookup_opps("C1761", "2024-07-01", opps_store)

    assert (june.components["status_indicator"], june.components["apc"]) == ("H", "2033")
    assert (july.components["status_indicator"], july.components["apc"]) == ("N", None)
    assert "cost-based pass-through" in june.components["packaging_rule"]
    assert "no separate APC payment" in july.components["packaging_rule"]


def test_october_first_boundaries_select_exact_quarter(opps_store: RulebookStore) -> None:
    september_device = lookup_opps("C1831", "2024-09-30", opps_store)
    october_device = lookup_opps("C1831", "2024-10-01", opps_store)
    september_service = lookup_opps("G0012", "2024-09-30", opps_store)
    october_service = lookup_opps("G0012", "2024-10-01", opps_store)

    assert (september_device.components["status_indicator"], september_device.components["apc"]) == (
        "H",
        "2034",
    )
    assert (october_device.components["status_indicator"], october_device.components["apc"]) == (
        "N",
        None,
    )
    assert september_service.calculated_amount == Decimal("45.26")
    assert september_service.components["apc"] == "5691"
    assert october_service.calculated_amount == Decimal("67.12")
    assert october_service.components["apc"] == "5692"


def test_missing_code_fails_closed(opps_store: RulebookStore) -> None:
    trace = lookup_opps("XXXXX", "2024-07-01", opps_store)

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.calculated_amount is None
    assert trace.selected_rule_versions == []
    assert trace.missing_rule == "opps_hcpcs:XXXXX"
    assert "failed closed" in trace.warnings[0]
    validate_trace(trace)


def test_date_without_effective_assignment_fails_closed(opps_store: RulebookStore) -> None:
    trace = lookup_opps("G0402", "2024-07-01", opps_store)

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.calculated_amount is None
    assert trace.missing_parameters == [
        "unambiguous effective OPPS assignment for service_date"
    ]
    assert "found 0" in trace.warnings[0]
    validate_trace(trace)


def test_unresolved_code_specific_effective_date_fails_closed(
    opps_store: RulebookStore,
) -> None:
    index = opps_store.code_assignments.index[
        opps_store.code_assignments["code"].eq("G0402")
    ][0]
    opps_store.code_assignments.loc[index, "value_status"] = "unresolved_effective_date"

    trace = lookup_opps("G0402", "2024-02-15", opps_store)

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.calculated_amount is None
    assert trace.missing_parameters == ["resolved code-specific effective date"]
    assert "failed closed" in trace.warnings[0]
    validate_trace(trace)
