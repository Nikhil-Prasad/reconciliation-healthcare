from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from reconciliation_healthcare.rulebook.graph import build_rule_graph
from reconciliation_healthcare.rulebook.models import (
    AmountKind,
    CalculationStatus,
    DateBasis,
    PaymentTrace,
    PaymentUnit,
)
from reconciliation_healthcare.rulebook.trace import validate_trace


@pytest.fixture
def professional_trace() -> PaymentTrace:
    return PaymentTrace(
        payment_system="PFS",
        service_date=date(2024, 3, 9),
        calculation_status=CalculationStatus.CALCULATED,
        input_context={"code": "99213", "setting": "nonfacility"},
        selected_rule_versions=[{"rule_id": "pfs.rvu24ar.base_payment"}],
        selected_parameters=[{"parameter_id": "test_parameter"}],
        source_artifact_ids=["test_source"],
        calculated_amount=Decimal("83.66"),
        amount_label="PFS base payment before claim-level adjustments",
        amount_kind=AmountKind.PFS_BASE_PAYMENT,
        payment_unit=PaymentUnit.PROFESSIONAL_SERVICE,
        date_basis=DateBasis.SERVICE_DATE,
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"amount_kind": AmountKind.OPPS_PUBLISHED_RATE}, "amount kind"),
        ({"amount_kind": None}, "amount kind"),
        ({"payment_unit": PaymentUnit.INPATIENT_DISCHARGE}, "payment unit"),
        ({"date_basis": DateBasis.DISCHARGE_DATE}, "date basis"),
        ({"calculation_status": CalculationStatus.LOOKUP_ONLY}, "calculation status"),
        ({"calculated_amount": 83.66}, "finite Decimal"),
        ({"calculated_amount": Decimal("NaN")}, "finite Decimal"),
        ({"calculated_amount": Decimal("Infinity")}, "finite Decimal"),
        ({"amount_label": None}, "readable label"),
    ],
)
def test_rejects_misleading_amount_contract(professional_trace, changes, message) -> None:
    with pytest.raises(ValueError, match=message):
        validate_trace(replace(professional_trace, **changes))


def test_serialization_retains_exact_decimal_and_controlled_meanings(professional_trace) -> None:
    validate_trace(professional_trace)
    payload = professional_trace.to_dict()
    assert payload["calculated_amount"] == "83.66"
    assert payload["amount_kind"] == "pfs_base_payment"
    assert payload["payment_unit"] == "professional_service"
    assert payload["service_date"] == "2024-03-09"
    assert payload["date_basis"] == "service_date"


def test_packaged_lookup_is_supported_without_a_numeric_rate(professional_trace) -> None:
    trace = replace(
        professional_trace,
        payment_system="OPPS",
        calculation_status=CalculationStatus.LOOKUP_ONLY,
        calculated_amount=None,
        amount_label="published national unadjusted OPPS payment rate",
        amount_kind=AmountKind.OPPS_PUBLISHED_RATE,
        payment_unit=PaymentUnit.OUTPATIENT_HCPCS_LOOKUP,
    )
    validate_trace(trace)
    assert trace.to_dict()["calculated_amount"] is None
    assert trace.to_dict()["amount_kind"] == "opps_published_national_unadjusted_rate"


def test_unsupported_attempt_retains_context_without_an_amount_kind(professional_trace) -> None:
    trace = replace(
        professional_trace,
        calculation_status=CalculationStatus.UNSUPPORTED,
        amount_kind=None,
        calculated_amount=None,
        amount_label=None,
        missing_rule="pfs.anesthesia",
    )
    validate_trace(trace)
    assert trace.payment_unit is PaymentUnit.PROFESSIONAL_SERVICE
    assert trace.date_basis is DateBasis.SERVICE_DATE
    with pytest.raises(ValueError, match="amount kind"):
        validate_trace(replace(trace, amount_kind=AmountKind.PFS_BASE_PAYMENT))
    with pytest.raises(ValueError, match="Unsupported trace must not expose a calculated amount"):
        validate_trace(replace(trace, calculated_amount=Decimal("0"), amount_label="bad zero"))


def test_ipps_compatibility_date_requires_discharge_semantics(professional_trace) -> None:
    trace = replace(
        professional_trace,
        payment_system="IPPS",
        service_date=date(2024, 10, 1),
        amount_kind=AmountKind.IPPS_BASE_OPERATING_PAYMENT,
        payment_unit=PaymentUnit.INPATIENT_DISCHARGE,
        date_basis=DateBasis.DISCHARGE_DATE,
    )
    validate_trace(trace)
    assert trace.to_dict()["service_date"] == "2024-10-01"
    with pytest.raises(ValueError, match="date basis"):
        validate_trace(replace(trace, date_basis=DateBasis.SERVICE_DATE))


def test_final_payment_assembly_preserves_multiple_policy_functions() -> None:
    rules, edges = build_rule_graph()
    by_id = rules.set_index("rule_id")
    final_ids = set(rules.loc[rules["rule_id"].str.endswith(".final_payment"), "rule_id"])
    assert final_ids == {"opps.final_payment", "ipps.fy2024.final_payment", "ipps.fy2025.final_payment"}
    for rule_id in final_ids:
        final = by_id.loc[rule_id]
        assert final["rule_type"] == "composition"
        assert final["policy_function"] == "composite"
        assert final["execution_status"] == "deferred"
        children = edges.loc[edges["from_rule_id"].eq(rule_id), "to_rule_id"]
        assert len(set(by_id.loc[children, "policy_function"])) > 1
    assert by_id.loc["ipps.fy2024.base_operating_payment", "policy_function"] == "resource_pricing"
